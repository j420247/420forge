# imports
import glob
import json
import logging
import re
from datetime import datetime
from logging import ERROR
from os import getenv, getppid, system
from os.path import dirname
from pathlib import Path

import boto3
import botocore
import git
import psutil
from flask import current_app, request, session
from flask_restful import Resource
from forge.aws_cfn_stack.stack import Stack
from forge.saml_auth.saml_auth import RestrictedResource
from ruamel import yaml


##
#### REST Endpoint classes
##

log = logging.getLogger('app_log')


class DoUpgrade(RestrictedResource):
    def post(self, region, stack_name, new_version, zdu):
        mystack = Stack(stack_name, region)
        if not mystack.store_current_action('upgrade', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        try:
            if zdu == 'true':
                auth = request.get_json()[0]
                mystack.upgrade_zdu(new_version, auth['username'], auth['password'])
            else:
                mystack.upgrade(new_version)
        except Exception as e:
            log.exception('Error occurred upgrading stack')
            mystack.log_msg(ERROR, f'Error occurred upgrading stack: {e}', write_to_changelog=True)
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class DoClone(RestrictedResource):
    def post(self):
        content = request.get_json()[0]
        for param in content:
            if param['ParameterKey'] == 'TemplateName':
                template_name = param['ParameterValue']
            elif param['ParameterKey'] == 'StackName':
                stack_name = param['ParameterValue']
            elif param['ParameterKey'] == 'ClonedFromStackName':
                cloned_from = param['ParameterValue']
            elif param['ParameterKey'] == 'Region':
                region = param['ParameterValue']
        # find product type for source stack
        source_stack = Stack(
            next(param for param in content if param['ParameterKey'] == 'ClonedFromStackName')['ParameterValue'],
            next(param for param in content if param['ParameterKey'] == 'ClonedFromRegion')['ParameterValue'],
        )
        app_type = source_stack.get_tag('product')
        # remove stackName, region and templateName from params to send
        content.remove(next(param for param in content if param['ParameterKey'] == 'StackName'))
        content.remove(next(param for param in content if param['ParameterKey'] == 'Region'))
        content.remove(next(param for param in content if param['ParameterKey'] == 'TemplateName'))
        # remove any params that are not in the Clone template
        template_file = get_template_file(template_name)
        yaml.SafeLoader.add_multi_constructor(u'!', general_constructor)
        template_params = yaml.safe_load(open(template_file, 'r'))['Parameters']
        params_to_send = []
        for param in content:
            if next((template_param for template_param in template_params if template_param == param['ParameterKey']), None):
                params_to_send.append(param)
        clone_stack = Stack(stack_name, region)
        if not clone_stack.store_current_action('clone', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        clustered = 'true' if 'Server' not in template_name else 'false'
        creator = session['saml']['subject'] if 'saml' in session else 'unknown'
        outcome = clone_stack.clone(params_to_send, template_file, app_type.lower(), clustered, creator, region, cloned_from)
        clone_stack.clear_current_action()
        return outcome


class DoUpdate(RestrictedResource):
    def post(self, stack_name):
        content = request.get_json()
        new_params = content[0]
        orig_params = content[1]
        mystack = Stack(stack_name, session['region'] if 'region' in session else '')
        if not mystack.store_current_action('update', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        mystack.log_change('Original parameters')
        for param in orig_params:
            mystack.log_change(f"{param['ParameterKey']}: {param['ParameterValue']}")
        cfn_client = boto3.client('cloudformation', region_name=session['region'])
        cfn_resource = boto3.resource('cloudformation', region_name=session['region'])
        try:
            stack_details = cfn_client.describe_stacks(StackName=stack_name)
            existing_template_params = cfn_resource.Stack(stack_name).parameters
        except Exception as e:
            if e.response and "does not exist" in e.response['Error']['Message']:
                log.error(f'Stack {stack_name} does not exist')
                return f'Stack {stack_name} does not exist'
            log.exception('Error occurred getting stack parameters for update')
            return False
        template_name = next(param for param in new_params if param['ParameterKey'] == 'TemplateName')['ParameterValue']
        for param in new_params:
            # if param was not in previous template, always pass it in the change set
            if not next((existing_param for existing_param in existing_template_params if existing_param['ParameterKey'] == param['ParameterKey']), None):
                continue
            # if param has not changed from previous, delete the value and set UsePreviousValue to true
            if (
                'ParameterValue' in param
                and param['ParameterValue'] == next(orig_param for orig_param in orig_params if orig_param['ParameterKey'] == param['ParameterKey'])['ParameterValue']
            ):
                del param['ParameterValue']
                param['UsePreviousValue'] = True
            # if param is subnets and the value has not changed from previous (even if the order has), do not pass in changeset, or pass in correct order if there are additional
            elif param['ParameterKey'] in ('InternalSubnets', 'ExternalSubnets'):
                orig_subnets = next((subnet_param for subnet_param in orig_params if param['ParameterKey'] == subnet_param['ParameterKey']), None)
                if orig_subnets:
                    orig_subnets_list = orig_subnets['ParameterValue'].split(',')
                    new_subnets_list = param['ParameterValue'].split(',')
                    subnets_to_send = []
                    for subnet in orig_subnets_list:
                        subnets_to_send.append(subnet)
                    # append newly added subnets
                    for new_subnet in new_subnets_list:
                        if new_subnet not in orig_subnets_list:
                            subnets_to_send.append(new_subnet)
                    # remove any deleted subnets
                    for orig_subnet in orig_subnets_list:
                        if orig_subnet not in new_subnets_list:
                            subnets_to_send.remove(orig_subnet)
                if subnets_to_send == orig_subnets_list:
                    del param['ParameterValue']
                    param['UsePreviousValue'] = True
                else:
                    param['ParameterValue'] = ','.join(subnets_to_send)
        params_for_update = [param for param in new_params if (param['ParameterKey'] != 'StackName' and param['ParameterKey'] != 'TemplateName')]
        env_param = next((tag for tag in stack_details['Stacks'][0]['Tags'] if tag['Key'] == 'environment'), None)
        if not env_param:
            log.warning('Stack is not tagged with environment, assuming prod')
        else:
            env = env_param['Value']
            if env == 'stg' or env == 'dr':
                if not next((param for param in params_for_update if param['ParameterKey'] == 'EBSSnapshotId'), None):
                    params_for_update.append({'ParameterKey': 'EBSSnapshotId', 'UsePreviousValue': True})
                if not next((param for param in params_for_update if param['ParameterKey'] == 'DBSnapshotName'), None):
                    params_for_update.append({'ParameterKey': 'DBSnapshotName', 'UsePreviousValue': True})
        outcome = mystack.create_change_set(params_for_update, get_template_file(template_name))
        mystack.clear_current_action()
        return outcome


class DoExecuteChangeset(RestrictedResource):
    def post(self, stack_name, change_set_name):
        mystack = Stack(stack_name, session['region'] if 'region' in session else '')
        if not mystack.store_current_action('update', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        outcome = mystack.execute_change_set(change_set_name)
        mystack.clear_current_action()
        return outcome


class DoFullRestart(RestrictedResource):
    def get(self, region, stack_name, threads, heaps):
        mystack = Stack(stack_name, region)
        if not mystack.store_current_action('fullrestart', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        try:
            if threads == 'true':
                mystack.thread_dump(alsoHeaps=heaps)
            if heaps == 'true':
                mystack.heap_dump()
            mystack.full_restart()
        except Exception as e:
            log.exception('Error occurred doing full restart')
            mystack.log_msg(ERROR, f'Error occurred doing full restart: {e}', write_to_changelog=True)
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class DoRollingRestart(RestrictedResource):
    def get(self, region, stack_name, threads, heaps):
        mystack = Stack(stack_name, region)
        if not mystack.store_current_action('rollingrestart', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        try:
            if threads == 'true':
                mystack.thread_dump(alsoHeaps=heaps)
            if heaps == 'true':
                mystack.heap_dump()
            mystack.rolling_restart()
        except Exception as e:
            log.exception('Error occurred doing rolling restart')
            mystack.log_msg(ERROR, f'Error occurred doing rolling restart: {e}', write_to_changelog=True)
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class DoRollingRebuild(RestrictedResource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        if not mystack.store_current_action('rollingrebuild', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        try:
            mystack.rolling_rebuild()
        except Exception as e:
            log.exception('Error occurred doing rolling rebuild')
            mystack.log_msg(ERROR, f'Error occurred doing rolling rebuild: {e}', write_to_changelog=True)
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class DoDestroy(RestrictedResource):
    def get(self, region, stack_name, delete_changelogs, delete_threaddumps):
        mystack = Stack(stack_name, region)
        if not mystack.store_current_action('destroy', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        try:
            mystack.destroy(bool(delete_changelogs), bool(delete_threaddumps))
        except Exception as e:
            log.exception('Error occurred destroying stack')
            mystack.log_msg(ERROR, f'Error occurred destroying stack: {e}', write_to_changelog=True)
            mystack.clear_current_action()
        session['stacks'] = sorted(get_cfn_stacks_for_region())
        mystack.clear_current_action()
        return


class DoThreadDumps(RestrictedResource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        if not mystack.store_current_action('diagnostics', stack_locking_enabled(), False, False):
            return False
        try:
            mystack.thread_dump()
        except Exception as e:
            log.exception('Error occurred taking thread dumps')
            mystack.log_msg(ERROR, f'Error occurred taking thread dumps: {e}', write_to_changelog=True)
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class DoGetThreadDumpLinks(RestrictedResource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        return mystack.get_thread_dump_links()


class DoHeapDumps(RestrictedResource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        if not mystack.store_current_action('diagnostics', stack_locking_enabled(), False, False):
            return False
        try:
            mystack.heap_dump()
        except Exception as e:
            log.exception('Error occurred taking heap dumps')
            mystack.log_msg(ERROR, f'Error occurred taking heap dumps: {e}', write_to_changelog=True)
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class DoRunSql(RestrictedResource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        if not mystack.store_current_action('runsql', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        try:
            outcome = mystack.run_sql()
        except Exception as e:
            log.exception('Error occurred running SQL')
            mystack.log_msg(ERROR, f'Error occurred running SQL: {e}', write_to_changelog=True)
            mystack.clear_current_action()
            return False
        mystack.clear_current_action()
        return outcome


class DoTag(RestrictedResource):
    def post(self, region, stack_name):
        tags = request.get_json()
        mystack = Stack(stack_name, region)
        if not mystack.store_current_action('tag', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        try:
            outcome = mystack.tag(tags)
        except Exception as e:
            log.exception('Error occurred tagging stack')
            mystack.log_msg(ERROR, f'Error occurred tagging stack: {e}', write_to_changelog=True)
            mystack.clear_current_action()
            return False
        mystack.clear_current_action()
        return outcome


class DoCreate(RestrictedResource):
    def post(self):
        content = request.get_json()[0]
        for param in content:
            if param['ParameterKey'] == 'Product':
                app_type = param['ParameterValue']
                continue
            if param['ParameterKey'] == 'StackName':
                stack_name = param['ParameterValue']
                continue
            elif param['ParameterKey'] == 'TemplateName':
                template_name = param['ParameterValue']
                continue
        mystack = Stack(stack_name, session['region'] if 'region' in session else '')
        if not mystack.store_current_action('create', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        params_for_create = [param for param in content if param['ParameterKey'] != 'StackName' and param['ParameterKey'] != 'TemplateName' and param['ParameterKey'] != 'Product']
        clustered = 'true' if 'Server' not in template_name else 'false'
        creator = session['saml']['subject'] if 'saml' in session else 'unknown'
        outcome = mystack.create(params_for_create, get_template_file(template_name), app_type, clustered, creator, session['region'])
        session['stacks'] = sorted(get_cfn_stacks_for_region())
        mystack.clear_current_action()
        return outcome


class GetLogs(Resource):
    def get(self, stack_name):
        log = get_current_log(stack_name)
        return log if log else f'No current status for {stack_name}'


class GetSysLogs(Resource):
    def get(self):
        with open(Path('logs/forge.log'), 'r') as logfile:
            try:
                return logfile.read()
            except Exception:
                log.exception(f'Error occurred getting system logs')


class GetGitBranch(Resource):
    def get(self, template_repo):
        repo = get_git_repo_base(template_repo)
        if repo.head.is_detached:
            return 'Detached HEAD'
        else:
            return repo.active_branch.name


class GetGitCommitDifference(Resource):
    def get(self, template_repo):
        repo = get_git_repo_base(template_repo)
        if not repo.head.is_detached:
            for remote in repo.remotes:
                remote.fetch(env=dict(GIT_SSH_COMMAND=getenv('GIT_SSH_COMMAND', 'ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -i /home/forge/gitkey')))
        return get_git_commit_difference(repo)


class DoGitPull(RestrictedResource):
    def get(self, template_repo, stack_name):
        repo = get_git_repo_base(template_repo)
        if template_repo == 'Forge (requires restart)':
            log.info('Updating Forge')
            log.info(f'Stashing: {repo.git.stash()}')
            log.info(f'Pulling: {repo.git.pull()}')
            log.info('Reapplying config')
            log.info(repo.git.checkout('stash', '--', 'forge/config/config.py', 'forge/saml_auth/permissions.json'))
            result = 'Forge updated successfully'
        else:
            result = repo.git.reset('--hard', f'origin/{repo.active_branch.name}')
        log.info(result)
        return result


class GetGitRevision(Resource):
    def get(self, template_repo):
        repo = get_git_repo_base(template_repo)
        result = get_git_revision(repo)
        log.info(result)
        return result[:7]


class ServiceStatus(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        return mystack.check_service_status(logMsgs=False)


class StackState(Resource):
    def get(self, region, stack_name):
        cfn = boto3.client('cloudformation', region_name=region)
        try:
            stack_state = cfn.describe_stacks(StackName=stack_name)
        except Exception as e:
            if e.response and "does not exist" in e.response['Error']['Message']:
                print(f'Stack {stack_name} does not exist')
                return f'Stack {stack_name} does not exist'
            log.exception('Error checking stack state')
            return f'Error checking stack state: {e}'
        return stack_state['Stacks'][0]['StackStatus']


class TemplateParams(Resource):
    def get(self, repo_name, template_name):
        if 'atlassian-aws-deployment' in repo_name:
            template_file = open(f'atlassian-aws-deployment/templates/{template_name}', 'r')
        else:
            for file in glob.glob(f'custom-templates/{repo_name}/**/*.yaml'):
                if template_name in file:
                    template_file = open(file, 'r')
        yaml.SafeLoader.add_multi_constructor(u'!', general_constructor)
        template_params = yaml.safe_load(template_file)['Parameters']

        params_to_send = []
        for param in template_params:
            params_to_send.append(
                {
                    'ParameterKey': param,
                    'ParameterValue': template_params[param]['Default'] if 'Default' in template_params[param] else '',
                    'ParameterDescription': template_params[param]['Description'] if 'Description' in template_params[param] else '',
                }
            )
            # Add validation values to params to send to the front end
            if 'AllowedValues' in template_params[param]:
                next(param_to_send for param_to_send in params_to_send if param_to_send['ParameterKey'] == param)['AllowedValues'] = template_params[param]['AllowedValues']
            if 'AllowedPattern' in template_params[param]:
                next(param_to_send for param_to_send in params_to_send if param_to_send['ParameterKey'] == param)['AllowedPattern'] = template_params[param]['AllowedPattern']
            if 'MinValue' in template_params[param]:
                next(param_to_send for param_to_send in params_to_send if param_to_send['ParameterKey'] == param)['MinValue'] = template_params[param]['MinValue']
            if 'MaxValue' in template_params[param]:
                next(param_to_send for param_to_send in params_to_send if param_to_send['ParameterKey'] == param)['MaxValue'] = template_params[param]['MaxValue']
            if 'MinLength' in template_params[param]:
                next(param_to_send for param_to_send in params_to_send if param_to_send['ParameterKey'] == param)['MinLength'] = template_params[param]['MinLength']
            if 'MaxLength' in template_params[param]:
                next(param_to_send for param_to_send in params_to_send if param_to_send['ParameterKey'] == param)['MaxLength'] = template_params[param]['MaxLength']
        return params_to_send


class TemplateParamsForStack(Resource):
    def get(self, region, stack_name, template_name):
        cfn = boto3.client('cloudformation', region_name=region)
        try:
            stack_details = cfn.describe_stacks(StackName=stack_name)
        except botocore.exceptions.ClientError:
            log.exception('Error occurred getting stack parameters')
            return
        stack_params = stack_details['Stacks'][0]['Parameters']
        # load the template params
        template_file = open(get_template_file(template_name), "r")
        yaml.SafeLoader.add_multi_constructor(u'!', general_constructor)
        template_params = yaml.safe_load(template_file)
        # Remove old stack params that are no longer on the template
        # To do this we need to build a new list
        compared_params = []
        for stack_param in stack_params:
            if stack_param['ParameterKey'] in template_params['Parameters']:
                compared_params.append(stack_param)
            else:
                print("Parameter not found: " + stack_param['ParameterKey'])
        # Add new params from the template to the stack params
        for param in template_params['Parameters']:
            if param not in ('DBSnapshotName', 'EBSSnapshotId'):
                if param not in [stack_param['ParameterKey'] for stack_param in stack_params]:
                    compared_params.append(
                        {'ParameterKey': param, 'ParameterValue': template_params['Parameters'][param]['Default'] if 'Default' in template_params['Parameters'][param] else ''}
                    )
                if 'AllowedValues' in template_params['Parameters'][param]:
                    next(compared_param for compared_param in compared_params if compared_param['ParameterKey'] == param)['AllowedValues'] = template_params['Parameters'][param][
                        'AllowedValues'
                    ]
                    next(compared_param for compared_param in compared_params if compared_param['ParameterKey'] == param)['Default'] = (
                        template_params['Parameters'][param]['Default'] if 'Default' in template_params['Parameters'][param] else ''
                    )
                if 'AllowedPattern' in template_params['Parameters'][param]:
                    next(compared_param for compared_param in compared_params if compared_param['ParameterKey'] == param)['AllowedPattern'] = template_params['Parameters'][param][
                        'AllowedPattern'
                    ]
                if 'MinValue' in template_params['Parameters'][param]:
                    next(compared_param for compared_param in compared_params if compared_param['ParameterKey'] == param)['MinValue'] = template_params['Parameters'][param][
                        'MinValue'
                    ]
                if 'MaxValue' in template_params['Parameters'][param]:
                    next(compared_param for compared_param in compared_params if compared_param['ParameterKey'] == param)['MaxValue'] = template_params['Parameters'][param][
                        'MaxValue'
                    ]
                if 'MinLength' in template_params['Parameters'][param]:
                    next(compared_param for compared_param in compared_params if compared_param['ParameterKey'] == param)['MinLength'] = template_params['Parameters'][param][
                        'MinLength'
                    ]
                if 'MaxLength' in template_params['Parameters'][param]:
                    next(compared_param for compared_param in compared_params if compared_param['ParameterKey'] == param)['MaxLength'] = template_params['Parameters'][param][
                        'MaxLength'
                    ]
            compared_param = next((compared_param for compared_param in compared_params if compared_param['ParameterKey'] == param), None)
            if compared_param and 'Description' in template_params['Parameters'][param]:
                compared_param['ParameterDescription'] = template_params['Parameters'][param]['Description']
        return compared_params


class GetSql(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        return mystack.get_sql()


class GetStackActionInProgress(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        action = mystack.get_stack_action_in_progress()
        return action if action else 'None'


class ClearStackActionInProgress(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        mystack.clear_current_action()
        return True


class GetVersion(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        return mystack.get_param_value('ProductVersion')


class GetNodes(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        instances = mystack.get_stacknodes()
        nodes_list = []
        for instance in instances:
            node = {}
            node_ip = list(instance.values())[0]
            node['ip'] = node_ip
            node['status'] = mystack.check_node_status(node_ip, False)
            nodes_list.append(node)
        return nodes_list


class GetTags(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        tags = mystack.get_tags()
        return tags


class HasTerminationProtection(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        return mystack.has_termination_protection()


class GetCloneDefaults(Resource):
    def get(self, stack_name):
        clone_defaults = current_app.config['CLONE_DEFAULTS']['all']
        if stack_name in current_app.config['CLONE_DEFAULTS']:
            clone_defaults.update(current_app.config['CLONE_DEFAULTS'][stack_name])
        return clone_defaults


class GetZDUCompatibility(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        return mystack.get_zdu_compatibility()


class GetChangeSetDetails(Resource):
    def get(self, region, stack_name, change_set_name):
        mystack = Stack(stack_name, region)
        return mystack.get_change_set_details(change_set_name)


class GetEbsSnapshots(Resource):
    def get(self, region, stack_name):
        ec2 = boto3.client('ec2', region_name=region)
        snap_name_format = f'{stack_name}_ebs_snap_*'
        if region != session['region']:
            snap_name_format = f'dr_{snap_name_format}'
        try:
            snapshots = ec2.describe_snapshots(Filters=[{'Name': 'tag-value', 'Values': [snap_name_format]}])
        except botocore.exceptions.ClientError:
            log.exception('Error occurred getting EBS snapshots')
            return
        snapshotIds = []
        for snap in snapshots['Snapshots']:
            start_time = str(snap['StartTime'])
            if '.' in start_time:
                start_time = start_time.split('.')[0]
            else:
                start_time = start_time.split('+')[0]
            snapshotIds.append({'label': f"{start_time} ({snap['SnapshotId']})", 'value': snap['SnapshotId']})
        snapshotIds = sorted(snapshotIds, key=lambda x: x['label'], reverse=True)
        return snapshotIds


class GetRdsSnapshots(Resource):
    def get(self, region, stack_name):
        cfn = boto3.client('cloudformation', region_name=request.args.get('clonedfrom_region'))
        rds = boto3.client('rds', region_name=region)
        snapshotIds = []
        try:
            # get RDS instance from stack resources
            rds_name = cfn.describe_stack_resource(LogicalResourceId='DB', StackName=stack_name)['StackResourceDetail']['PhysicalResourceId']
            # get snapshots and append ids to list
            snapshots_response = rds.describe_db_snapshots(DBInstanceIdentifier=rds_name)
            for snap in snapshots_response['DBSnapshots']:
                if 'SnapshotCreateTime' in snap and 'DBSnapshotIdentifier' in snap:
                    snapshotIds.append({'label': f"{str(snap['SnapshotCreateTime']).split('.')[0]} ({snap['DBSnapshotIdentifier']})", 'value': snap['DBSnapshotIdentifier']})
            # if there are more than 100 snapshots the response will contain a marker, get the next lot of snapshots and add them to the list
            while 'Marker' in snapshots_response:
                snapshots_response = rds.describe_db_snapshots(DBInstanceIdentifier=rds_name, Marker=snapshots_response['Marker'])
                for snap in snapshots_response['DBSnapshots']:
                    if 'SnapshotCreateTime' in snap and 'DBSnapshotIdentifier' in snap:
                        snapshotIds.append({'label': f"{str(snap['SnapshotCreateTime']).split('.')[0]} ({snap['DBSnapshotIdentifier']})", 'value': snap['DBSnapshotIdentifier']})
        except botocore.exceptions.ClientError:
            log.exception('Error occurred getting RDS snapshots')
            return
        snapshotIds = sorted(snapshotIds, key=lambda x: x['label'], reverse=True)
        return snapshotIds


class GetTemplates(Resource):
    def get(self, template_type):
        templates = []
        template_folder = Path('atlassian-aws-deployment/templates')
        custom_template_folder = Path('custom-templates')
        # get default templates
        if template_type == 'all':
            default_templates = [f for f in template_folder.glob('**/*') if re.match(r'^.*\.yaml$', f.name, flags=re.IGNORECASE)]
        else:
            default_templates = [f for f in template_folder.glob('**/*') if re.match(rf'^.*{template_type}.*\.yaml$', f.name, flags=re.IGNORECASE)]
        for file in default_templates:
            # TODO support Bitbucket?
            if 'Bitbucket' in file.name:
                continue
            templates.append(('atlassian-aws-deployment', file.name))
        # get custom templates
        if custom_template_folder.exists():
            if template_type == 'all':
                custom_templates = [f for f in custom_template_folder.glob('**/*/*/*') if re.match(r'^.*\.yaml$', f.name, flags=re.IGNORECASE)]
            else:
                custom_templates = [f for f in custom_template_folder.glob('**/*/*/*') if re.match(rf'^.*{template_type}.*\.yaml$', f.name, flags=re.IGNORECASE)]
            for file in custom_templates:
                templates.append((file.parent.parent.name, file.name))
        templates.sort()
        return templates


class GetVpcs(Resource):
    def get(self, region):
        ec2 = boto3.client('ec2', region_name=region)
        try:
            vpcs = ec2.describe_vpcs()
        except botocore.exceptions.ClientError:
            log.exception('Error occurred getting VPCs')
            return
        vpc_ids = []
        for vpc in vpcs['Vpcs']:
            vpc_ids.append(vpc['VpcId'])
        return vpc_ids


class GetSubnetsForVpc(Resource):
    def get(self, region, vpc):
        ec2 = boto3.client('ec2', region_name=region)
        try:
            subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc]}])
        except botocore.exceptions.ClientError:
            log.exception('Error occurred getting subnets')
            return
        subnet_ids = []
        sorted_subnets = sorted(subnets['Subnets'], key=lambda subnet: subnet['AvailabilityZone'])
        for subnet in sorted_subnets:
            subnet_ids.append(subnet['SubnetId'])
        return subnet_ids


class GetAllSubnetsForRegion(Resource):
    def get(self, region):
        ec2 = boto3.client('ec2', region_name=region)
        try:
            subnets = ec2.describe_subnets()
        except botocore.exceptions.ClientError:
            log.exception('Error occurred getting subnets')
            return
        subnet_ids = []
        for subnet in subnets['Subnets']:
            subnet_ids.append(subnet['SubnetId'])
        return subnet_ids


class GetLockedStacks(Resource):
    def get(self):
        locked_stacks = []
        if 'LOCKS' in current_app.config:
            locked_stacks = list(current_app.config['LOCKS'].keys())
        return locked_stacks


class GetTemplateRepos(Resource):
    def get(self):
        repos = ['atlassian-aws-deployment', 'Forge (requires restart)']
        custom_template_folder = Path('custom-templates')
        if custom_template_folder.exists():
            for directory in glob.glob(f'{custom_template_folder}/*'):
                repos.append(directory.split('/')[1])
        repos.sort()
        return repos


class GetKmsKeys(Resource):
    def get(self, region):
        keys = []
        account_id = boto3.client('sts').get_caller_identity().get('Account')
        client = boto3.client('kms', region)
        paginator = client.get_paginator('list_aliases')
        response_iterator = paginator.paginate()
        for kms_keys_aliases in response_iterator:
            for key in kms_keys_aliases['Aliases']:
                if key.get('TargetKeyId') and not key['AliasName'].startswith('alias/aws'):
                    keys.append({'label': key['AliasName'].replace('alias/', ''), 'value': f'arn:aws:kms:{region}:{account_id}:key/{key["TargetKeyId"]}'})
        return keys


class GetSslCerts(Resource):
    def get(self, region):
        ssl_certs = []
        client = boto3.client('acm', region)
        paginator = client.get_paginator('list_certificates')
        response_iterator = paginator.paginate()
        for ssl_certs_aliases in response_iterator:
            for cert in ssl_certs_aliases['CertificateSummaryList']:
                ssl_certs.append({'label': cert['DomainName'], 'value': cert['CertificateArn']})
        ssl_certs = sorted(ssl_certs, key=lambda x: x['label'])
        return ssl_certs


class SetStackLocking(Resource):
    def post(self, lock):
        current_app.config['STACK_LOCKING'] = lock
        session['stack_locking'] = lock
        return lock


class ForgeStatus(Resource):
    def get(self):
        return {'state': 'RUNNING'}


class DoForgeRestart(RestrictedResource):
    def get(self, stack_name):
        log.warning('Forge restart has been triggered')
        if not restart_forge():
            return 'unsupported'


##
#### Common functions
##


def get_cfn_stacks_for_region(region=None):
    cfn = boto3.client('cloudformation', region if region else session['region'])
    stack_name_list = []
    try:
        stack_list = cfn.list_stacks(StackStatusFilter=current_app.config['VALID_STACK_STATUSES'])
        session['credentials'] = True
        for stack in stack_list['StackSummaries']:
            stack_name_list.append(stack['StackName'])
    except (KeyError, botocore.exceptions.NoCredentialsError):
        session['credentials'] = False
        stack_name_list.append('No credentials')
    return stack_name_list


def get_current_log(stack_name):
    logs = glob.glob(f'stacks/{stack_name}/logs/{stack_name}_*.action.log')
    logs_by_time = {}
    if len(logs) > 0:
        for log in logs:
            str_timestamp = log[log.index(f'logs/{stack_name}') + 6 + len(stack_name) : log.rfind('_')]
            datetime_timestamp = datetime.strptime(str_timestamp, '%Y%m%d-%H%M%S')
            logs_by_time[log] = datetime_timestamp
        sorted_logs = sorted(logs_by_time, key=logs_by_time.get, reverse=True)
        with open(sorted_logs[0], 'r') as logfile:
            try:
                return logfile.read()
            except Exception:
                log.exception(f'Error occurred getting log for {stack_name}')
    return False


def general_constructor(loader, tag_suffix, node):
    return node.value


def get_git_commit_difference(repo):
    try:
        behind = sum(1 for c in repo.iter_commits(f'HEAD..origin/{repo.active_branch.name}'))
        ahead = sum(1 for d in repo.iter_commits(f'origin/{repo.active_branch.name}..HEAD'))
    except (TypeError, git.exc.GitCommandError):
        behind = -1
        ahead = -1
    return [behind, ahead]


def get_git_revision(repo):
    return repo.head.object.hexsha


def get_template_file(template_name):
    if 'atlassian-aws-deployment' in template_name:
        template_folder = Path('atlassian-aws-deployment/templates')
    else:
        template_folder = Path('custom-templates')
    return list(template_folder.glob(f"**/{template_name.split(': ')[1]}"))[0]


def get_forge_revision(repo):
    git_hash = get_git_revision(repo)[:7]
    diff = get_git_commit_difference(repo)
    if int(diff[0]) > 0:
        update_available = '(update available)'
    else:
        update_available = '(up to date)'
    return f'{git_hash} {update_available}'


def get_nice_action_name(action):
    switcher = {
        'admin': 'Admin',
        'backup': 'Backup stack',
        'clone': 'Clone stack',
        'create': 'Create stack',
        'destroy': 'Destroy stack',
        'diagnostics': 'Diagnostics',
        'fullrestart': 'Full restart',
        'rollingrestart': 'Rolling restart',
        'rollingrebuild': 'Rebuild nodes',
        'runsql': 'Run SQL',
        'viewlog': 'Stack logs',
        'syslog': 'System logs',
        'tag': 'Tag stack',
        'update': 'Update stack',
        'upgrade': 'Upgrade',
    }
    return switcher.get(action, '')


def stack_locking_enabled():
    return current_app.config['STACK_LOCKING']


def restart_forge():
    # get the parent process ID (the gunicorn master, not the worker)
    log.warning(f'Forge restarting via admin function on pid {getppid()}')
    process = psutil.Process(getppid())
    if 'gunicorn' in str(process.cmdline()):
        system(f'kill -HUP {getppid()}')
        return True
    else:
        log.warning('*** Restarting only supported in gunicorn. Please restart/reload manually ***')
        return False


def get_git_repo_base(repo_name):
    if repo_name == 'Forge (requires restart)':
        repo = git.Repo(Path(dirname(current_app.root_path)))
    else:
        if repo_name != 'atlassian-aws-deployment':
            repo_name = f'custom-templates/{repo_name}'
        repo = git.Repo(Path(repo_name))
    return repo


def get_forge_settings():
    # use first region in config.py if no region selected (eg first load)
    if 'region' not in session:
        session['region'] = current_app.config['REGIONS'][0][0]
        session['stacks'] = sorted(get_cfn_stacks_for_region(session['region']))
    session['products'] = current_app.config['PRODUCTS']
    session['regions'] = current_app.config['REGIONS']
    session['stack_locking'] = current_app.config['STACK_LOCKING']
    session['forge_version'] = session.get('forge_version') or f'{get_forge_revision(git.Repo(Path(dirname(current_app.root_path))))}'
    session['default_vpcs'] = json.dumps(current_app.config['DEFAULT_VPCS']).replace(' ', '').encode(errors='xmlcharrefreplace')
    session['default_subnets'] = json.dumps(current_app.config['DEFAULT_SUBNETS']).replace(' ', '').encode(errors='xmlcharrefreplace')
    session['hosted_zone'] = current_app.config['HOSTED_ZONE']
    session['ssh_key_name'] = current_app.config['SSH_KEY_NAME']
    session['avatar_url'] = current_app.config['AVATAR_URL']
