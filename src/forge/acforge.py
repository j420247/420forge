# imports
from collections import defaultdict
from forge.aws_cfn_stack.stack import Stack
from flask import Flask, request, session, redirect, url_for, current_app, \
    render_template, flash
from flask_restful import Resource
from ruamel import yaml
from pathlib import Path
from os import path
from logging import ERROR
import boto3
import botocore
import configparser
import os
from forge.version import __version__
import glob
from forge.saml_auth.saml_auth import RestrictedResource
import json

##
#### REST Endpoint classes
##

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
            print(e)
            mystack.log_msg(ERROR, f'Error occurred upgrading stack: {e}')
            mystack.log_change('Upgrade failed, see action log for details')
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class DoClone(RestrictedResource):
    def post(self):
        content = request.get_json()[0]
        app_type = '' #TODO is there a better way to do this?
        instance_type = 'DataCenter' #TODO support server
        for param in content:
            if param['ParameterKey'] == 'TemplateName':
                template_name = param['ParameterValue']
            elif param['ParameterKey'] == 'StackName':
                stack_name = param['ParameterValue']
            elif param['ParameterKey'] == 'ClonedFromStackName':
                cloned_from = param['ParameterValue']
            elif param['ParameterKey'] == 'Region':
                region = param['ParameterValue']
            elif param['ParameterKey'] == 'ConfluenceVersion':
                app_type = 'Confluence'
            elif param['ParameterKey'] == 'JiraVersion':
                app_type = 'Jira'
            elif param['ParameterKey'] == 'CrowdVersion':
                app_type = 'Crowd'
            elif param['ParameterKey'] == 'EBSSnapshotId':
                param['ParameterValue'] = param['ParameterValue'].split(': ')[1]
            elif param['ParameterKey'] == 'DBSnapshotName':
                param['ParameterValue'] = param['ParameterValue'].split(': ')[1]
        #remove stackName, region and templateName from params to send
        content.remove(next(param for param in content if param['ParameterKey'] == 'StackName'))
        content.remove(next(param for param in content if param['ParameterKey'] == 'Region'))
        content.remove(next(param for param in content if param['ParameterKey'] == 'TemplateName'))
        # remove any params that are not in the Clone template
        if template_name:
            template_file = get_template_file(template_name)
        else:
            template_file = f'atlassian-aws-deployment/templates/{app_type}{instance_type}Clone.template.yaml'
        yaml.SafeLoader.add_multi_constructor(u'!', general_constructor)
        template_params = yaml.safe_load(open(template_file, 'r'))['Parameters']
        params_to_send = []
        for param in content:
            if next((template_param for template_param in template_params if template_param == param['ParameterKey']), None):
                params_to_send.append(param)
        mystack = Stack(stack_name, region)
        if not mystack.store_current_action('clone', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        creator = session['saml']['subject'] if 'saml' in session else 'unknown'
        outcome = mystack.clone(params_to_send, template_file, app_type.lower(), instance_type, region, creator, cloned_from)
        mystack.clear_current_action()
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
                print(f'Stack {stack_name} does not exist')
                return f'Stack {stack_name} does not exist'
            print(e)
        template_name = next(param for param in new_params if param['ParameterKey'] == 'TemplateName')['ParameterValue']
        for param in new_params:
            # if param was not in previous template, always pass it in the change set
            if not next((existing_param for existing_param in existing_template_params if existing_param['ParameterKey'] == param['ParameterKey']), None):
                continue
            # if param has not changed from previous, delete the value and set UsePreviousValue to true
            if param['ParameterValue'] == next(orig_param for orig_param in orig_params if orig_param['ParameterKey'] == param['ParameterKey'])['ParameterValue']:
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
        env = next(tag for tag in stack_details['Stacks'][0]['Tags'] if tag['Key'] == 'environment')['Value']
        if env == 'stg' or env == 'dr':
            if not next((parm for parm in params_for_update if parm['ParameterKey'] == 'EBSSnapshotId'), None):
                params_for_update.append({'ParameterKey': 'EBSSnapshotId', 'UsePreviousValue': True})
            if not next((parm for parm in params_for_update if parm['ParameterKey'] == 'DBSnapshotName'), None):
                params_for_update.append({'ParameterKey': 'DBSnapshotName', 'UsePreviousValue': True})
        outcome = mystack.update(params_for_update, get_template_file(template_name))
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
            print(e)
            mystack.log_msg(ERROR, f'Error occurred doing full restart: {e}')
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
            print(e)
            mystack.log_msg(ERROR, f'Error occurred doing rolling restart: {e}')
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
            print(e)
            mystack.log_msg(ERROR, f'Error occurred doing rolling rebuild: {e}')
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class DoDestroy(RestrictedResource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        if not mystack.store_current_action('destroy', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        try:
            outcome = mystack.destroy()
        except Exception as e:
            print(e)
            mystack.log_msg(ERROR, f'Error occurred destroying stack: {e}')
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
            outcome = mystack.thread_dump()
        except Exception as e:
            print(e)
            mystack.log_msg(ERROR, f'Error occurred taking thread dumps: {e}')
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class DoGetThreadDumpLinks(RestrictedResource):
    def get(self, stack_name):
        urls = []
        try:
            accountId = boto3.client('sts').get_caller_identity().get('Account')
            s3_bucket = f'atl-cfn-forge-{accountId}'
            client = boto3.client('s3', region_name=session['region'])
            list_objects = client.list_objects_v2(
                Bucket=s3_bucket,
                Prefix=f'diagnostics/{stack_name}/'
            )
            if 'Contents' in list_objects:
                for thread_dump in list_objects['Contents']:
                    url = client.generate_presigned_url(
                        ClientMethod='get_object',
                        Params={
                            'Bucket': s3_bucket,
                            'Key': thread_dump['Key']
                        }
                    )
                    urls.append(url)
        except Exception as e:
            if e.response['Error']['Code'] == 'NoSuchBucket':
                print(f"S3 bucket '{s3_bucket}' has not yet been created")
            print(e)
        return urls


class DoHeapDumps(RestrictedResource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        if not mystack.store_current_action('diagnostics', stack_locking_enabled(), False, False):
            return False
        try:
            outcome = mystack.heap_dump()
        except Exception as e:
            print(e)
            mystack.log_msg(ERROR, f'Error occurred taking heap dumps: {e}')
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
            print(e)
            mystack.log_msg(ERROR, f'Error occurred running SQL: {e}')
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
            print(e)
            mystack.log_msg(ERROR, f'Error occurred tagging stack: {e}')
            mystack.clear_current_action()
            return False
        mystack.clear_current_action()
        return outcome


class DoCreate(RestrictedResource):
    def post(self):
        content = request.get_json()[0]
        for param in content:
            if param['ParameterKey'] == 'StackName':
                stack_name = param['ParameterValue']
                continue
            elif param['ParameterKey'] == 'TemplateName':
                template_name = param['ParameterValue']
                continue
            elif param['ParameterKey'] == 'ConfluenceVersion':
                app_type = 'confluence'
            elif param['ParameterKey'] == 'JiraVersion':
                app_type = 'jira'
            elif param['ParameterKey'] == 'CrowdVersion':
                app_type = 'crowd'
        mystack = Stack(stack_name, session['region'] if 'region' in session else '')
        if not mystack.store_current_action('create', stack_locking_enabled(), True, session['saml']['subject'] if 'saml' in session else False):
            return False
        params_for_create = [param for param in content if param['ParameterKey'] != 'StackName' and param['ParameterKey'] != 'TemplateName']
        creator = session['saml']['subject'] if 'saml' in session else 'unknown'
        outcome = mystack.create(params_for_create, get_template_file(template_name), app_type, creator, session['region'])
        session['stacks'] = sorted(get_cfn_stacks_for_region())
        mystack.clear_current_action()
        return outcome


class GetLogs(Resource):
    def get(self, stack_name):
        log = get_current_log(stack_name)
        return log if log else f'No current status for {stack_name}'


class ServiceStatus(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        return mystack.check_service_status(logMsgs=False)


class StackState(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        cfn = boto3.client('cloudformation', region_name=region)
        try:
            stack_state = cfn.describe_stacks(StackName=stack_name)
        except Exception as e:
            if e.response and "does not exist" in e.response['Error']['Message']:
                print(f'Stack {stack_name} does not exist')
                return f'Stack {stack_name} does not exist'
            print(e)
            return f'Error checking stack state: {e}'
        return stack_state['Stacks'][0]['StackStatus']


class TemplateParams(Resource):
    def get(self, repo_name, template_name):
        if 'atlassian-aws-deployment' in repo_name:
            template_file = open(f"atlassian-aws-deployment/templates/{template_name}", "r")
        else:
            for file in glob.glob(f'../custom-templates/{repo_name}/**/*.yaml'):
                if template_name in file:
                    template_file = open(file, "r")
        yaml.SafeLoader.add_multi_constructor(u'!', general_constructor)
        template_params = yaml.safe_load(template_file)['Parameters']

        params_to_send = []
        for param in template_params:
            params_to_send.append({'ParameterKey': param,
                                    'ParameterValue': template_params[param]['Default'] if 'Default' in template_params[param] else '',
                                    'ParameterDescription': template_params[param]['Description'] if 'Description' in template_params[param] else ''})
            if 'AllowedValues' in template_params[param]:
                next(param_to_send for param_to_send in params_to_send if param_to_send['ParameterKey'] == param)['AllowedValues'] = \
                    template_params[param]['AllowedValues']
        return params_to_send


class TemplateParamsForStack(Resource):
    def get(self, region, stack_name, template_name):
        cfn = boto3.client('cloudformation', region_name=region)
        try:
            stack_details = cfn.describe_stacks(StackName=stack_name)
        except botocore.exceptions.ClientError as e:
            print(e)
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
            if param != 'DBSnapshotName' and param != 'EBSSnapshotId':
                if param not in [stack_param['ParameterKey'] for stack_param in stack_params]:
                    compared_params.append({'ParameterKey': param,
                                            'ParameterValue': template_params['Parameters'][param]['Default'] if 'Default' in template_params['Parameters'][param] else ''})
                if 'AllowedValues' in template_params['Parameters'][param]:
                    next(compared_param for compared_param in compared_params if compared_param['ParameterKey'] == param)['AllowedValues'] = \
                        template_params['Parameters'][param]['AllowedValues']
                    next(compared_param for compared_param in compared_params if compared_param['ParameterKey'] == param)['Default'] = \
                        template_params['Parameters'][param]['Default'] if 'Default' in template_params['Parameters'][param] else ''
            compared_param = next((compared_param for compared_param in compared_params if compared_param['ParameterKey'] == param), None)
            if compared_param and 'Description' in template_params['Parameters'][param]:
                compared_param['ParameterDescription'] = \
                    template_params['Parameters'][param]['Description']
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
        return mystack.get_param('Version')


class GetNodes(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        mystack.get_stacknodes()
        nodes = []
        for instance in mystack.instancelist:
            node = {}
            node_ip = list(instance.values())[0]
            node['ip'] = node_ip
            node['status'] = mystack.check_node_status(node_ip, False)
            nodes.append(node)
        return nodes


class GetTags(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        tags = mystack.get_tags()
        return tags


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


class GetEbsSnapshots(Resource):
    def get(self, region, stack_name):
        ec2 = boto3.client('ec2', region_name=region)
        snap_name_format = f'{stack_name}_ebs_snap_*'
        if region != session['region']:
            snap_name_format = f'dr_{snap_name_format}'
        try:
            snapshots = ec2.describe_snapshots(Filters=[
                {
                    'Name': 'tag-value',
                    'Values': [
                        snap_name_format,
                    ]
                },
            ],)
        except botocore.exceptions.ClientError as e:
            print(e)
            return
        snapshotIds = []
        for snap in snapshots['Snapshots']:
            start_time = str(snap['StartTime'])
            if '.' in start_time:
                start_time = start_time.split('.')[0]
            else:
                start_time = start_time.split('+')[0]
            snapshotIds.append(start_time + ": " + snap['SnapshotId'])
        snapshotIds.sort(reverse=True)
        return snapshotIds


class GetRdsSnapshots(Resource):
    def get(self, region, stack_name):
        rds = boto3.client('rds', region_name=region)
        snapshotIds = []
        try:
            # get snapshots and append ids to list
            snapshots_response = rds.describe_db_snapshots(DBInstanceIdentifier=stack_name)
            for snap in snapshots_response['DBSnapshots']:
                snapshotIds.append(str(snap['SnapshotCreateTime']).split('.').__getitem__(0) + ": " + snap['DBSnapshotIdentifier'])
            # if there are more than 100 snapshots the response will contain a marker, get the next lot of snapshots and add them to the list
            while 'Marker' in snapshots_response:
                snapshots_response = rds.describe_db_snapshots(DBInstanceIdentifier=stack_name, Marker=snapshots_response['Marker'])
                for snap in snapshots_response['DBSnapshots']:
                    snapshotIds.append(str(snap['SnapshotCreateTime']).split('.').__getitem__(0) + ": " + snap['DBSnapshotIdentifier'])
        except botocore.exceptions.ClientError as e:
            print(e)
            return
        snapshotIds.sort(reverse=True)
        return snapshotIds


class GetTemplates(Resource):
    def get(self, template_type):
        templates = []
        template_folder = Path('atlassian-aws-deployment/templates')
        custom_template_folder = Path('../custom-templates')
        # get default templates
        if template_type == 'all':
            default_templates = list(template_folder.glob(f"**/*.yaml"))
        else:
            default_templates = list(template_folder.glob(f"**/*{template_type}*.yaml"))
        for file in default_templates:
            # TODO support Server and Bitbucket
            if 'Server' in file.name:
                continue
            templates.append(('atlassian-aws-deployment', file.name))
        # get custom templates
        if custom_template_folder.exists():
            if template_type == 'all':
                custom_templates = list(custom_template_folder.glob(f"**/*/*/*.yaml"))
            else:
                custom_templates = list(custom_template_folder.glob(f"**/*/*/*{template_type}*.yaml"))
            for file in custom_templates:
                if 'Server' in file.name:
                    continue
                templates.append((file.parent.parent.name, file.name))
        templates.sort()
        return templates


class GetVpcs(Resource):
    def get(self, region):
        ec2 = boto3.client('ec2', region_name=region)
        try:
            vpcs = ec2.describe_vpcs()
        except botocore.exceptions.ClientError as e:
            print(e)
            return
        vpc_ids = []
        for vpc in vpcs['Vpcs']:
            vpc_ids.append(vpc['VpcId'])
        return vpc_ids


class GetSubnetsForVpc(Resource):
    def get(self, region, vpc):
        ec2 = boto3.client('ec2', region_name=region)
        try:
            subnets = ec2.describe_subnets(
                Filters=[
                    {
                        'Name': 'vpc-id',
                        'Values': [
                            vpc,
                        ]
                    },
                ]
            )
        except botocore.exceptions.ClientError as e:
            print(e)
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
        except botocore.exceptions.ClientError as e:
            print(e)
            return
        subnet_ids = []
        for subnet in subnets['Subnets']:
            subnet_ids.append(subnet['SubnetId'])
        return subnet_ids

class GetLockedStacks(Resource):
    def get(self):
        locked_stacks = [dir.name for dir in os.scandir(f'locks/') if dir.is_dir()]
        locked_stacks.sort()
        return locked_stacks


class SetStackLocking(Resource):
    def post(self, lock):
        lockfile = Path(f'locks/locking')
        with open(lockfile, 'w') as lock_state:
            lock_state.write(lock)
            session['stack_locking'] = lock
            return lock

class ForgeStatus(Resource):
    def get(self):
        return {'state': 'RUNNING'}

##
#### Common functions
##

def get_cfn_stacks_for_region(region=None):
    cfn = boto3.client('cloudformation', region if region else session['region'])
    stack_name_list = []
    try:
        stack_list = cfn.list_stacks(
            StackStatusFilter=current_app.config['VALID_STACK_STATUSES'])
        session['credentials'] = True
        for stack in stack_list['StackSummaries']:
            stack_name_list.append(stack['StackName'])
    except (KeyError, botocore.exceptions.NoCredentialsError):
        session['credentials'] = False
        stack_name_list.append('No credentials')
    return stack_name_list


def get_current_log(stack_name):
    logs = glob.glob(f'stacks/{stack_name}/logs/{stack_name}_*.action.log')
    if len(logs) > 0:
        logs.sort(key=os.path.getctime, reverse=True)
        with open(logs[0], 'r') as logfile:
            try:
                return logfile.read()
            except Exception as e:
                print(e)
    return False


def general_constructor(loader, tag_suffix, node):
    return node.value


def get_template_file(template_name):
    if 'atlassian-aws-deployment' in template_name:
        template_folder = Path('atlassian-aws-deployment/templates')
    else:
        template_folder = Path('../custom-templates')
    return list(template_folder.glob(f"**/{template_name.split(': ')[1]}"))[0]


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
        'rollingrebuild': 'Rolling rebuild',
        'runsql': 'Run SQL',
        'viewlog': 'Stack logs',
        'tag': 'Tag stack',
        'update': 'Update stack',
        'upgrade': 'Upgrade',
    }
    return switcher.get(action, '')


def stack_locking_enabled():
    lockfile = path.join(path.dirname(__file__), 'locks/locking')
    with open(lockfile, 'r') as lock_state:
        try:
            return lock_state.read() == 'true'
        except Exception as e:
            print(e)


def get_config_properties():
    config_props = configparser.ConfigParser()
    config_props.read(path.join(path.dirname(__file__), 'config/forge.properties'))
    return config_props


def get_forge_settings():
    get_config_properties()
    # use first region in forge.properties if no region selected (eg first load)
    if 'region' not in session:
        session['region'] = current_app.config['REGIONS'][0][0]
        session['stacks'] = sorted(get_cfn_stacks_for_region(session['region']))
    session['products'] = current_app.config['PRODUCTS']
    session['regions'] = current_app.config['REGIONS']
    session['stack_locking'] = stack_locking_enabled()
    session['forge_version'] = __version__
    session['default_vpcs'] = json.dumps(current_app.config['DEFAULT_VPCS']).replace(' ','').encode(errors='xmlcharrefreplace')
    session['default_subnets'] = json.dumps(current_app.config['DEFAULT_SUBNETS']).replace(' ','').encode(errors='xmlcharrefreplace')
    session['hosted_zone'] = current_app.config['HOSTED_ZONE']
    session['ssh_key_name'] = current_app.config['SSH_KEY_NAME']