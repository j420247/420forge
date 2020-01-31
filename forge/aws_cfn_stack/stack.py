import errno
import itertools
import json
import logging
import os
import time
from datetime import datetime
from logging import DEBUG, ERROR, INFO, WARN, getLevelName
from pathlib import Path

import boto3
import botocore
import requests
import tenacity
from botocore.exceptions import ClientError
from flask import Blueprint, current_app
from humanfriendly import format_timespan
from requests_toolbelt.sessions import BaseUrlSession
from retry import retry


def version_tuple(version):
    return tuple(int(i) for i in version.replace('-m', '.').split('.'))


ZDU_MINIMUM_JIRACORE_VERSION = version_tuple('7.3')
ZDU_MINIMUM_SERVICEDESK_VERSION = version_tuple('3.6')

aws_cfn_stack_blueprint = Blueprint('aws_cfn_stack', __name__)

log = logging.getLogger('app_log')


class Stack:
    """An object describing an instance of an aws cloudformation stack:

    Attributes:
        stackstate: A dict of dicts containing all state information.
        stack_name: The name of the stack we are keeping state for
    """

    def __init__(self, stack_name, region):
        self.stack_name = stack_name
        if region == '':
            error_string = 'No region defined for stack - your session may have timed out. Go back and retry the operation.'
            self.log_msg(ERROR, error_string, write_to_changelog=False)
            raise ValueError(error_string)
        self.region = region
        self.logfile = None
        self.changelogfile = None
        self.preupgrade_version = None
        self.preupgrade_app_node_count = None
        self.preupgrade_synchrony_node_count = None

    ## Stack - micro function methods
    @tenacity.retry(
        wait=tenacity.wait_exponential(),
        stop=tenacity.stop_after_attempt(5),
        retry=tenacity.retry_if_exception_type(botocore.exceptions.ClientError),
        before=tenacity.after_log(log, DEBUG),
    )
    def get_service_url(self):
        if hasattr(self, 'service_url'):
            return self.service_url
        else:
            try:
                cfn = boto3.client('cloudformation', region_name=self.region)
                stack_details = cfn.describe_stacks(StackName=self.stack_name)
                product = self.get_tag('product')
                service_url = f"{[p['OutputValue'] for p in stack_details['Stacks'][0]['Outputs'] if p['OutputKey'] == 'ServiceURL'][0]}/"
                if product == 'crowd':
                    service_url = f'{service_url}{product}/'
                self.service_url = service_url
                return True
            except botocore.exceptions.ClientError as e:
                # log and allow tenacity to retry
                self.log_msg(ERROR, f'ClientError received during get_service_url. Request will be retried a maximum of 5 times. Exception is: {e}', write_to_changelog=False)
                raise
            except Exception as e:
                log.exception(f'Exception occurred during get_service_url')
                return False

    def get_params(self):
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack_details = cfn.describe_stacks(StackName=self.stack_name)
            params = stack_details['Stacks'][0]['Parameters']
        except botocore.exceptions.ClientError:
            log.exception('Error getting stack parameters')
            return False
        return params

    def get_param_value(self, param_to_get, params=None):
        if params is None:
            params = self.get_params()
        param_value = ''
        legacy_params = []
        if param_to_get == 'ProductVersion':
            legacy_params = ['confluenceversion', 'jiraversion', 'crowdversion']
        elif param_to_get == 'ClusterNodeCount':
            legacy_params = ['clusternodemax']
        elif param_to_get == 'SynchronyClusterNodeCount':
            legacy_params = ['synchronyclusternodemax']
        try:
            for param in params:
                if param['ParameterKey'].lower() == param_to_get.lower() or param['ParameterKey'].lower() in legacy_params:
                    param_value = param['ParameterValue'] if param['ParameterValue'] else ''
        except TypeError:
            log.exception('Error retrieving parameter value; no params available')
        return param_value

    def update_paramlist(self, params_list, param_key, param_value):
        key_found = False
        for param in params_list:
            for key, value in param.items():
                if value == param_key:
                    param['ParameterValue'] = param_value
                    key_found = True
                if value == 'DBMasterUserPassword' or value == 'DBPassword':
                    try:
                        del param['ParameterValue']
                    except KeyError:
                        pass
                    param['UsePreviousValue'] = True
        if not key_found:
            params_list.append({'ParameterKey': param_key, 'ParameterValue': param_value})
        return params_list

    def upload_template(self, file, s3_name):
        s3 = boto3.resource('s3', region_name=self.region)
        try:
            s3.meta.client.upload_file(file, current_app.config['S3_BUCKET'], f'forge-templates/{s3_name}')
        except botocore.exceptions.ClientError:
            log.exception('boto ClientError')
            return False
        return True

    def ssm_send_command(self, node, cmd):
        logs_bucket = f"{current_app.config['S3_BUCKET']}/logs"
        ssm = boto3.client('ssm', region_name=self.region)
        ssm_command = ssm.send_command(
            InstanceIds=[node],
            DocumentName='AWS-RunShellScript',
            Parameters={'commands': [cmd], 'executionTimeout': ["900"]},
            OutputS3BucketName=logs_bucket,
            OutputS3KeyPrefix='run-command-logs',
        )
        self.log_msg(INFO, f'for command: {cmd}, command_id is {ssm_command["Command"]["CommandId"]}', write_to_changelog=False)
        if ssm_command['ResponseMetadata']['HTTPStatusCode'] == requests.codes.ok:
            return ssm_command['Command']['CommandId']
        return False

    def ssm_cmd_check(self, cmd_id):
        ssm = boto3.client('ssm', region_name=self.region)
        try:
            list_command = ssm.list_commands(CommandId=cmd_id)
            cmd_status = list_command[u'Commands'][0][u'Status']
            node = list_command[u'Commands'][0][u'InstanceIds'][0]
            self.log_msg(INFO, f'result of ssm command {cmd_id} on node {node} is {cmd_status}', write_to_changelog=False)
            return cmd_status, node
        except botocore.exceptions.ClientError:
            log.exception('boto ClientError')
            self.log_msg(ERROR, f'retrieving ssm command {cmd_id} status failed', write_to_changelog=False)

    def ssm_send_and_wait_response(self, node, cmd):
        cmd_id = self.ssm_send_command(node, cmd)
        if not cmd_id:
            self.log_msg(ERROR, f'Command {cmd} on node {node} failed to send', write_to_changelog=False)
            return False
        else:
            result = self.wait_for_cmd_result(cmd_id)
        return result

    ## Stack - helper methods

    def spindown_to_zero_appnodes(self, app_type):
        self.log_msg(INFO, f'Spinning {self.stack_name} stack down to 0 nodes', write_to_changelog=True)
        cfn = boto3.client('cloudformation', region_name=self.region)
        spindown_params = self.get_params()
        if any(param for param in spindown_params if param['ParameterKey'] == 'ClusterNodeMax'):
            spindown_params = self.update_paramlist(spindown_params, 'ClusterNodeMax', '0')
            spindown_params = self.update_paramlist(spindown_params, 'ClusterNodeMin', '0')
        else:
            spindown_params = self.update_paramlist(spindown_params, 'ClusterNodeCount', '0')
        if app_type == 'confluence':
            if any(param for param in spindown_params if param['ParameterKey'] == 'SynchronyClusterNodeMax'):
                spindown_params = self.update_paramlist(spindown_params, 'SynchronyClusterNodeMax', '0')
                spindown_params = self.update_paramlist(spindown_params, 'SynchronyClusterNodeMin', '0')
            else:
                spindown_params = self.update_paramlist(spindown_params, 'SynchronyClusterNodeCount', '0')
        try:
            cfn.update_stack(StackName=self.stack_name, Parameters=spindown_params, UsePreviousTemplate=True, Capabilities=['CAPABILITY_IAM'])
        except Exception as e:
            if 'No updates are to be performed' in e:
                self.log_msg(INFO, 'Stack is already at 0 nodes', write_to_changelog=True)
                return True
            else:
                log.exception('An error occurred spinning down to 0 nodes')
                self.log_msg(ERROR, f'An error occurred spinning down to 0 nodes: {e}', write_to_changelog=True)
                return False
        if self.wait_stack_action_complete("UPDATE_IN_PROGRESS"):
            self.log_msg(INFO, "Successfully spun down to 0 nodes", write_to_changelog=True)
            return True
        return False

    def wait_stack_action_complete(self, in_progress_state, stack_id=None):
        self.log_msg(INFO, "Waiting for stack action to complete", write_to_changelog=False)
        stack_state = self.check_stack_state()
        if stack_state is None and in_progress_state == "DELETE_IN_PROGRESS":
            return True
        while 'IN_PROGRESS' in stack_state or stack_state in (in_progress_state, 'throttled'):
            time.sleep(10)
            stack_state = self.check_stack_state(stack_id if stack_id else self.stack_name)
        if 'ROLLBACK' in stack_state:
            self.log_msg(ERROR, f'Stack action was rolled back: {stack_state}', write_to_changelog=True)
            return False
        elif 'FAILED' in stack_state:
            self.log_msg(ERROR, f'Stack action failed: {stack_state}', write_to_changelog=False)
            return False
        return True

    def wait_stack_change_set_creation_complete(self, change_set_arn):
        self.log_msg(INFO, "Waiting for change set creation to complete", write_to_changelog=False)
        cfn = boto3.client('cloudformation', region_name=self.region)
        waiter = cfn.get_waiter('change_set_create_complete')
        try:
            waiter.wait(ChangeSetName=change_set_arn, StackName=self.stack_name)
        except tenacity.RetryError:
            self.log_msg(ERROR, 'Change set creation complete - failed (timed out)', write_to_changelog=True)
            return False
        except Exception as e:
            log.exception('An error occurred waiting for change set to create')
            self.log_msg(ERROR, f'An error occurred waiting for change set to create: {e}', write_to_changelog=True)
            return False
        self.log_msg(INFO, 'Change set creation complete', write_to_changelog=True)
        return True

    def spinup_to_one_appnode(self, app_type, new_version):
        self.log_msg(INFO, "Spinning stack up to one app node", write_to_changelog=True)
        # for connie 1 app node and 1 synchrony
        cfn = boto3.client('cloudformation', region_name=self.region)
        spinup_params = self.get_params()
        if any(param for param in spinup_params if param['ParameterKey'] == 'ClusterNodeMax'):
            spinup_params = self.update_paramlist(spinup_params, 'ClusterNodeMax', '1')
            spinup_params = self.update_paramlist(spinup_params, 'ClusterNodeMin', '1')
        else:
            spinup_params = self.update_paramlist(spinup_params, 'ClusterNodeCount', '1')
        if any(param for param in spinup_params if param['ParameterKey'] == 'ProductVersion'):
            spinup_params = self.update_paramlist(spinup_params, 'ProductVersion', new_version)
        elif app_type == 'jira':
            spinup_params = self.update_paramlist(spinup_params, 'JiraVersion', new_version)
        elif app_type == 'confluence':
            spinup_params = self.update_paramlist(spinup_params, 'ConfluenceVersion', new_version)
        elif app_type == 'crowd':
            spinup_params = self.update_paramlist(spinup_params, 'CrowdVersion', new_version)
        if hasattr(self, 'preupgrade_synchrony_node_count'):
            if any(param for param in spinup_params if param['ParameterKey'] == 'SynchronyClusterNodeMax'):
                spinup_params = self.update_paramlist(spinup_params, 'SynchronyClusterNodeMax', '1')
                spinup_params = self.update_paramlist(spinup_params, 'SynchronyClusterNodeMin', '1')
            else:
                spinup_params = self.update_paramlist(spinup_params, 'SynchronyClusterNodeCount', '1')
        try:
            update_stack = cfn.update_stack(StackName=self.stack_name, Parameters=spinup_params, UsePreviousTemplate=True, Capabilities=['CAPABILITY_IAM'])
        except botocore.exceptions.ClientError as e:
            self.log_msg(INFO, f'Stack spinup failed: {e}', write_to_changelog=True)
            return False
        if not self.wait_stack_action_complete('UPDATE_IN_PROGRESS'):
            return False
        self.log_msg(INFO, 'Spun up to 1 node, waiting for service to respond', write_to_changelog=False)
        if not self.validate_service_responding():
            return False
        self.log_msg(INFO, f'Updated stack: {update_stack}', write_to_changelog=True)
        return True

    def validate_service_responding(self):
        self.log_msg(INFO, 'Waiting for service to reply on /status', write_to_changelog=False)
        service_state = self.check_service_status()
        action_start = time.time()
        action_timeout = current_app.config['ACTION_TIMEOUTS']['validate_service_responding']
        while service_state not in ['RUNNING', 'FIRST_RUN']:
            if (time.time() - action_start) > action_timeout:
                self.log_msg(
                    ERROR,
                    f'{self.stack_name} failed to come up after {format_timespan(action_timeout)}. ' f'Status endpoint is returning: {service_state}',
                    write_to_changelog=True,
                )
                return False
            time.sleep(60)
            service_state = self.check_service_status()
        self.get_service_url()
        self.log_msg(INFO, f'{self.service_url}status is now reporting {service_state}', write_to_changelog=True)
        return True

    def validate_node_responding(self, node_ip):
        self.log_msg(INFO, f'Waiting for node {node_ip} to reply on /status', write_to_changelog=False)
        result = self.check_node_status(node_ip, False)
        action_start = time.time()
        action_timeout = current_app.config['ACTION_TIMEOUTS']['validate_node_responding']
        while result not in ['RUNNING', 'FIRST_RUN']:
            if (time.time() - action_start) > action_timeout:
                self.log_msg(ERROR, f'{node_ip} failed to come up after {format_timespan(action_timeout)}. Status endpoint is returning: {result}', write_to_changelog=True)
                return False
            result = self.check_node_status(node_ip, False)
            time.sleep(10)
        self.log_msg(INFO, f'Startup result for {node_ip}: {result}', write_to_changelog=False)
        return True

    def check_service_status(self, logMsgs=True):
        try:
            if not self.get_service_url():
                return 'Timed Out'
        except tenacity.RetryError:
            return 'Timed Out'
        if logMsgs:
            self.log_msg(INFO, f' ==> checking service status at {self.service_url}status', write_to_changelog=False)
        try:
            service_status = requests.get(self.service_url + 'status', timeout=5)
            if service_status.status_code == requests.codes.ok:
                json_status = service_status.json()
                if 'state' in json_status:
                    status = json_status['state']
            else:
                status = str(service_status.status_code) + ": " + service_status.reason[:21] if service_status.reason else str(service_status.status_code)
            if logMsgs:
                self.log_msg(INFO, f' ==> service status is: {status}', write_to_changelog=False)
            return status
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
            if logMsgs:
                self.log_msg(INFO, f'Service status check timed out', write_to_changelog=False)
        except json.decoder.JSONDecodeError:
            log.exception(f'Error checking service status: {service_status}')
            if logMsgs:
                self.log_msg(WARN, f'Service status check failed: returned 200 but response was empty', write_to_changelog=False)
        return 'Timed Out'

    def check_stack_state(self, stack_id=None):
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack_state = cfn.describe_stacks(StackName=stack_id if stack_id else self.stack_name)
        except Exception as e:
            if 'Throttling' in e.response['Error']['Message'] or 'Rate exceeded' in e.response['Error']['Message']:
                self.log_msg(WARN, f'Stack actions are being throttled: {e}', write_to_changelog=False)
                return 'throttled'
            if 'does not exist' in e.response['Error']['Message']:
                self.log_msg(INFO, f'Stack {self.stack_name} does not exist', write_to_changelog=False)
                return
            log.exception('Error checking stack state')
            self.log_msg(ERROR, 'Error checking stack state', write_to_changelog=False)
            return
        state = stack_state['Stacks'][0]['StackStatus']
        return state

    def check_node_status(self, node_ip, logMsgs=True):
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack = cfn.describe_stacks(StackName=self.stack_name)
        except Exception as e:
            log.exception('Error checking node status')
            return f'Error checking node status: {e}'
        context_path = [param['ParameterValue'] for param in stack['Stacks'][0]['Parameters'] if param['ParameterKey'] == 'TomcatContextPath'][0]
        port = [param['ParameterValue'] for param in stack['Stacks'][0]['Parameters'] if param['ParameterKey'] == 'TomcatDefaultConnectorPort'][0]
        if logMsgs:
            self.log_msg(INFO, f' ==> checking node status at {node_ip}:{port}{context_path}/status', write_to_changelog=False)
        try:
            node_status = requests.get(f'http://{node_ip}:{port}{context_path}/status', timeout=5).json()
            if 'state' in node_status:
                status = node_status['state']
            else:
                self.log_msg(ERROR, f'Node status not in expected format: {node_status}', write_to_changelog=False)
            if logMsgs:
                self.log_msg(INFO, f' ==> node status is: {status}', write_to_changelog=False)
            return status
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout):
            if logMsgs:
                self.log_msg(INFO, f'Node status check timed out', write_to_changelog=False)
        except requests.exceptions.ConnectionError:
            if logMsgs:
                self.log_msg(INFO, f'Node not currently listening on {port}', write_to_changelog=False)
        except Exception as e:
            log.exception('Error checking node status')
            return f'Error checking node status: {e}'
        return 'Timed Out'

    def spinup_remaining_nodes(self):
        self.log_msg(INFO, 'Spinning up any remaining nodes in stack', write_to_changelog=True)
        cfn = boto3.client('cloudformation', region_name=self.region)
        spinup_params = self.get_params()
        if any(param for param in spinup_params if param['ParameterKey'] == 'ClusterNodeMax'):
            spinup_params = self.update_paramlist(spinup_params, 'ClusterNodeMax', self.preupgrade_app_node_count)
            spinup_params = self.update_paramlist(spinup_params, 'ClusterNodeMin', self.preupgrade_app_node_count)
        else:
            spinup_params = self.update_paramlist(spinup_params, 'ClusterNodeCount', self.preupgrade_app_node_count)
        if hasattr(self, 'preupgrade_synchrony_node_count'):
            if any(param for param in spinup_params if param['ParameterKey'] == 'SynchronyClusterNodeMax'):
                spinup_params = self.update_paramlist(spinup_params, 'SynchronyClusterNodeMax', self.preupgrade_synchrony_node_count)
                spinup_params = self.update_paramlist(spinup_params, 'SynchronyClusterNodeMin', self.preupgrade_synchrony_node_count)
            else:
                spinup_params = self.update_paramlist(spinup_params, 'SynchronyClusterNodeCount', self.preupgrade_synchrony_node_count)
        try:
            cfn.update_stack(StackName=self.stack_name, Parameters=spinup_params, UsePreviousTemplate=True, Capabilities=['CAPABILITY_IAM'])
        except Exception as e:
            log.exception('Error occurred spinning up remaining nodes')
            self.log_msg(ERROR, f'Error occurred spinning up remaining nodes: {e}', write_to_changelog=True)
            return False
        if self.wait_stack_action_complete("UPDATE_IN_PROGRESS"):
            self.log_msg(INFO, "Stack restored to full node count", write_to_changelog=True)
        return True

    @retry(botocore.exceptions.ClientError, tries=5, delay=2, backoff=2)
    def get_stacknodes(self):
        ec2 = boto3.resource('ec2', region_name=self.region)
        filters = [
            {'Name': 'tag:aws:cloudformation:stack-name', 'Values': [self.stack_name]},
            {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'shutting-down', 'stopping', 'stopped']},
        ]
        if self.is_app_clustered():
            filters.append({'Name': 'tag:aws:cloudformation:logical-id', 'Values': ['ClusterNodeGroup']})
        nodes = []
        try:
            instances = ec2.instances.filter(Filters=filters)
            for i in instances:
                instancedict = {i.instance_id: i.private_ip_address}
                nodes.append(instancedict)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'RequestLimitExceeded':
                log.exception('RequestLimitExceeded received during get_stacknodes')
                self.log_msg(ERROR, 'RequestLimitExceeded received during get_stacknodes', write_to_changelog=False)
                raise e
        return nodes

    def shutdown_app(self, app_type, nodes):
        cmd_id_list = []
        for node in nodes:
            node_id = list(node.keys())[0]
            node_ip = list(node.values())[0]
            self.log_msg(INFO, f'Shutting down {app_type} on {node_id} ({node_ip})', write_to_changelog=True)
            cmd = f'service {app_type} stop'
            cmd_id_list.append(self.ssm_send_command(node_id, cmd))
        for cmd_id in cmd_id_list:
            result = self.wait_for_cmd_result(cmd_id)
            if result == 'Failed':
                self.log_msg(ERROR, f'Shutdown result for {cmd_id}: {result}', write_to_changelog=True)
            else:
                self.log_msg(INFO, f'Shutdown result for {cmd_id}: {result}', write_to_changelog=True)
        return True

    def startup_app(self, app_type, nodes):
        for node in nodes:
            node_id = list(node.keys())[0]
            node_ip = list(node.values())[0]
            if app_type == 'jira':
                if not self.cleanup_jira_temp_files(str(node_id)):
                    self.log_msg(ERROR, f'Failure cleaning up temp files for {node_id}', write_to_changelog=False)
            self.log_msg(INFO, f'Starting up {node_id} ({node_ip})', write_to_changelog=True)
            cmd = f'service {app_type} start'
            cmd_id = self.ssm_send_command(node_id, cmd)
            result = self.wait_for_cmd_result(cmd_id)
            if result == 'Failed':
                self.log_msg(ERROR, f'Startup result for {cmd_id}: {result}', write_to_changelog=True)
                return False
            else:
                if not self.validate_node_responding(node_ip):
                    return False
            self.log_msg(INFO, f'Application started on node {node_id}', write_to_changelog=True)
        return True

    def cleanup_jira_temp_files(self, node):
        cmd = f'find /opt/atlassian/jira/temp/ -type f -delete'
        cmd_id = self.ssm_send_command(node, cmd)
        result = self.wait_for_cmd_result(cmd_id)
        if result == 'Failed':
            self.log_msg(ERROR, f'Cleanup temp files result for {cmd_id}: {result}', write_to_changelog=False)
            return False
        self.log_msg(INFO, f'Deleted Jira temp files on {node}', write_to_changelog=False)
        return True

    def run_command(self, nodes, cmd):
        cmd_id_dict = {}
        for node in nodes:
            node_id = list(node.keys())[0]
            node_ip = list(node.values())[0]
            self.log_msg(INFO, f'Running command {cmd} on {node_ip}', write_to_changelog=False)
            cmd_id_dict[self.ssm_send_command(node_id, cmd)] = node_ip
        for cmd_id in cmd_id_dict:
            result = self.wait_for_cmd_result(cmd_id)
            if result == 'Failed':
                self.log_msg(ERROR, f'Command result for {cmd_id}: {result}', write_to_changelog=True)
                return False
            else:
                self.log_msg(INFO, f'Command result for {cmd_id}: {result}', write_to_changelog=True)
        return True

    def wait_for_cmd_result(self, cmd_id):
        result, cmd_instance = self.ssm_cmd_check(cmd_id)
        while result != 'Success' and result != 'Failed':
            result, cmd_instance = self.ssm_cmd_check(cmd_id)
            time.sleep(10)
        return result

    def get_stack_action_in_progress(self):
        if 'LOCKS' in current_app.config and self.stack_name in current_app.config['LOCKS']:
            return current_app.config['LOCKS'][self.stack_name]
        return False

    def store_current_action(self, action, locking_enabled, changelog, actor):
        self.create_action_log(action)
        if locking_enabled:
            action_already_in_progress = self.get_stack_action_in_progress()
            if action_already_in_progress:
                self.log_msg(ERROR, f'Cannot begin action: {action}. Another action is in progress: {action_already_in_progress}', write_to_changelog=False)
                return False
        if 'LOCKS' not in current_app.config:
            current_app.config['LOCKS'] = {}
        current_app.config['LOCKS'][self.stack_name] = action
        if changelog:
            self.create_change_log(action)
            if actor:
                self.log_change(f'Action triggered by {actor}')
        return True

    def clear_current_action(self):
        self.save_change_log()
        if 'LOCKS' in current_app.config and self.stack_name in current_app.config['LOCKS']:
            del current_app.config['LOCKS'][self.stack_name]
        return True

    def get_tags(self):
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack = cfn.describe_stacks(StackName=self.stack_name)
        except Exception as e:
            self.log_msg(ERROR, f'Error getting tags: {e}', write_to_changelog=True)
            log.exception('Error getting tags')
            return False
        tags = stack['Stacks'][0]['Tags']
        return tags

    def get_tag(self, tag_name, log_msgs=True):
        tags = self.get_tags()
        if tags:
            tag = [tag for tag in tags if tag['Key'] == tag_name]
            if tag:
                tag_value = tag[0]['Value']
                if log_msgs and hasattr(self, 'logfile'):
                    self.log_msg(INFO, f'Tag \'{tag_name}\' is \'{tag_value}\'', write_to_changelog=False)
                return tag_value.lower()
        if log_msgs and hasattr(self, 'logfile'):
            self.log_msg(WARN, f'Tag {tag_name} not found', write_to_changelog=True)
        return False

    def is_app_clustered(self):
        clustered = self.get_tag('clustered', False)
        if not clustered:
            self.log_msg(WARN, 'App clustering status is unknown (tag is missing from stack); proceeding as if clustered = true', write_to_changelog=False)
            return True
        return True if clustered == 'true' else False

    def get_sql_from_s3(self, stack, sql_dir):
        # try to pull latest from s3
        s3_bucket = current_app.config['S3_BUCKET']
        try:
            s3 = boto3.client('s3')
            bucket_list = s3.list_objects(Bucket=s3_bucket, Prefix=f'config/{sql_dir}')['Contents']
            if bucket_list:
                if not os.path.exists(sql_dir):
                    os.makedirs(sql_dir)
                s3 = boto3.resource('s3')
                for bucket_item in bucket_list:
                    if bucket_item['Size'] > 0:  # this is to catch when s3 sometimes weirdly returns the path as an object
                        sql_file_name = os.path.basename(bucket_item['Key'])
                        s3.meta.client.download_file(s3_bucket, bucket_item['Key'], f'{sql_dir}{sql_file_name}')
            self.log_msg(INFO, f'Retrieved latest SQL for {stack} from {sql_dir}', write_to_changelog=False)
            return True
        except KeyError as e:
            if e.args[0] == 'Contents':
                self.log_msg(WARN, f'No SQL files exist at s3://{s3_bucket}/config/{sql_dir} for stack {stack}', write_to_changelog=True)
                return True
            log.exception(f'Could not retrieve sql from s3 for stack {stack}')
            self.log_msg(ERROR, f'Could not retrieve sql from s3 for stack {stack}: {e}', write_to_changelog=False)
            return False
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            log.exception(f'Could not retrieve sql from s3 for stack {stack}: {error_code}')
            self.log_msg(ERROR, f'Could not retrieve sql from s3 for stack {stack}: {error_code}', write_to_changelog=False)
            return False
        except Exception as e:
            log.exception(f'Could not retrieve sql from s3 for stack {stack}')
            self.log_msg(ERROR, f'Could not retrieve sql from s3 for stack {stack}: {e}', write_to_changelog=True)
            return False

    def get_sql(self):
        sql_to_run = ''
        # get SQL for the stack this stack was cloned from (ie the master stack)
        cloned_from_stack = self.get_tag('cloned_from')
        if cloned_from_stack:
            cloned_from_stack_sql_dir = f'stacks/{cloned_from_stack}/{cloned_from_stack}-clones-sql.d/'
            if not self.get_sql_from_s3(cloned_from_stack, cloned_from_stack_sql_dir):
                return False
            if Path(cloned_from_stack_sql_dir).exists():
                sql_files = os.listdir(cloned_from_stack_sql_dir)
                if len(sql_files) > 0:
                    sql_to_run = f'---- ***** SQL to run for clones of {cloned_from_stack} *****\n\n'
                    for file in sql_files:
                        sql_file = open(os.path.join(cloned_from_stack_sql_dir, file), "r")
                        sql_to_run = f"{sql_to_run}-- *** SQL from {cloned_from_stack} {sql_file.name} ***\n\n{sql_file.read()}\n\n"
        # get SQL for this stack
        own_sql_dir = f'stacks/{self.stack_name}/local-post-clone-sql.d/'
        if not self.get_sql_from_s3(self.stack_name, own_sql_dir):
            return False
        if Path(own_sql_dir).exists():
            sql_files = os.listdir(own_sql_dir)
            if len(sql_files) > 0:
                sql_to_run = f'{sql_to_run}---- ***** SQL to run for {self.stack_name} *****\n\n'
                for file in sql_files:
                    sql_file = open(os.path.join(own_sql_dir, file), "r")
                    sql_to_run = f"{sql_to_run}-- *** SQL from {sql_file.name} ***\n\n{sql_file.read()}\n\n"
        if len(sql_to_run) > 0:
            return sql_to_run
        return 'No SQL script exists for this stack'

    def get_pre_upgrade_information(self, app_type):
        # get preupgrade version and node counts
        params = self.get_params()
        self.preupgrade_version = self.get_param_value('ProductVersion', params)
        if self.is_app_clustered():
            self.preupgrade_app_node_count = self.get_param_value('ClusterNodeCount', params)
            if app_type == 'confluence':
                self.preupgrade_synchrony_node_count = self.get_param_value('SynchronyClusterNodeCount', params)
        # create changelog
        self.log_change(f'Pre upgrade version: {self.preupgrade_version}')

    def get_zdu_state(self):
        try:
            response = self.session.get('rest/api/2/cluster/zdu/state', timeout=5)
            if response.status_code != requests.codes.ok:
                self.log_msg(ERROR, f'Unable to get ZDU state: /rest/api/2/cluster/zdu/state returned status code: {response.status_code}', write_to_changelog=True)
                return False
            return response.json()['state']
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
            log.exception('ZDU state check timed out')
            self.log_msg(INFO, f'ZDU state check timed out', write_to_changelog=False)
        except Exception as e:
            log.exception('Error occurred getting ZDU state')
            self.log_msg(ERROR, f'Could not retrieve ZDU state: {e}', write_to_changelog=True)
        return False

    def enable_zdu_mode(self):
        try:
            response = self.session.post('rest/api/2/cluster/zdu/start', timeout=5)
            if response.status_code != requests.codes.created:
                self.log_msg(ERROR, f'Unable to enable ZDU mode: /rest/api/2/cluster/zdu/start returned status code: {response.status_code}', write_to_changelog=True)
                return False
            action_start = time.time()
            action_timeout = current_app.config['ACTION_TIMEOUTS']['enable_zdu_mode']
            while self.get_zdu_state() != 'READY_TO_UPGRADE':
                if (time.time() - action_start) > action_timeout:
                    self.log_msg(ERROR, f'Stack is not in READY_TO_UPGRADE mode after {format_timespan(action_timeout)} - aborting', write_to_changelog=True)
                    return False
                time.sleep(5)
            self.log_msg(INFO, 'ZDU mode enabled', write_to_changelog=True)
            return True
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as e:
            log.exception('Could not enable ZDU mode')
            self.log_msg(ERROR, f'Could not enable ZDU mode: {e}', write_to_changelog=True)
        except Exception as e:
            log.exception('Error occurred enabling ZDU mode')
            self.log_msg(ERROR, f'Error occurred enabling ZDU mode: {e}', write_to_changelog=True)
        return False

    def cancel_zdu_mode(self):
        try:
            response = self.session.post('rest/api/2/cluster/zdu/cancel', timeout=5)
            if response.status_code != requests.codes.ok:
                self.log_msg(ERROR, f'Unable to cancel ZDU mode: /rest/api/2/cluster/zdu/cancel returned status code: {response.status_code}', write_to_changelog=True)
                return False
            action_start = time.time()
            action_timeout = current_app.config['ACTION_TIMEOUTS']['cancel_zdu_mode']
            while self.get_zdu_state() != 'STABLE':
                if (time.time() - action_start) > action_timeout:
                    self.log_msg(ERROR, f'Stack is not in STABLE mode after {format_timespan(action_timeout)} - ZDU mode cancel failed', write_to_changelog=True)
                    return False
                time.sleep(5)
            self.log_msg(INFO, 'ZDU mode cancelled', write_to_changelog=True)
            return True
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as e:
            log.exception('Could not cancel ZDU mode')
            self.log_msg(ERROR, f'Could not cancel ZDU mode: {e}', write_to_changelog=True)
        except Exception as e:
            log.exception('Error occurred cancelling ZDU mode')
            self.log_msg(ERROR, f'Error occurred cancelling ZDU mode: {e}', write_to_changelog=True)
        return False

    def approve_zdu_upgrade(self):
        self.log_msg(INFO, 'Approving upgrade and running upgrade tasks', write_to_changelog=True)
        try:
            response = self.session.post('rest/api/2/cluster/zdu/approve', timeout=30)
            if response.status_code != requests.codes.ok:
                self.log_msg(ERROR, f'Unable to approve upgrade: /rest/api/2/cluster/zdu/approve returned status code: {response.status_code}', write_to_changelog=True)
                return False
            self.log_msg(INFO, 'Upgrade tasks are running, waiting for STABLE state', write_to_changelog=True)
            state = self.get_zdu_state()
            action_start = time.time()
            action_timeout = current_app.config['ACTION_TIMEOUTS']['approve_zdu_upgrade']
            while state != 'STABLE':
                if (time.time() - action_start) > action_timeout:
                    self.log_msg(
                        ERROR,
                        f'Stack is not in STABLE mode after {format_timespan(action_timeout)} - ' 'upgrade tasks may still be running but Forge is aborting',
                        write_to_changelog=True,
                    )
                    return False
                self.log_msg(INFO, f'ZDU state is {state}', write_to_changelog=False)
                time.sleep(5)
                state = self.get_zdu_state()
            self.log_msg(INFO, 'Upgrade tasks complete', write_to_changelog=True)
            return True
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as e:
            log.exception('Could not cancel ZDU mode')
            self.log_msg(ERROR, f'Could not approve ZDU mode: {e}', write_to_changelog=True)
        except Exception as e:
            log.exception('Error occurred approving ZDU mode')
            self.log_msg(ERROR, f'Error occurred approving ZDU mode: {e}', write_to_changelog=True)
        return False

    def get_zdu_compatibility(self):
        if not self.get_tag('product') == 'jira':
            return ['not Jira']
        nodes = self.get_stacknodes()
        if not len(nodes) > 1:
            return ['too few nodes']
        params = self.get_params()
        version = version_tuple(self.get_param_value('ProductVersion', params))
        jira_product = self.get_param_value('JiraProduct', params)
        if jira_product == 'ServiceDesk':
            if version >= ZDU_MINIMUM_SERVICEDESK_VERSION:
                return True
        elif version >= ZDU_MINIMUM_JIRACORE_VERSION:
            return True
        return [f'Jira {jira_product} {version} is incompatible with ZDU']

    ## Stack - Major Action Methods

    def upgrade(self, new_version):
        self.log_msg(INFO, f'Beginning upgrade for {self.stack_name}', write_to_changelog=False)
        if self.is_app_clustered():
            if not self.upgrade_dc(new_version):
                self.log_msg(INFO, 'Upgrade complete - failed', write_to_changelog=True)
                return False
        else:
            if not self.upgrade_server(new_version):
                self.log_msg(INFO, 'Upgrade complete - failed', write_to_changelog=True)
                return False
        self.log_msg(INFO, f'Upgrade successful for {self.stack_name} at {self.region} to version {new_version}', write_to_changelog=False)
        self.log_msg(INFO, 'Upgrade complete', write_to_changelog=True)
        return True

    def upgrade_dc(self, new_version):
        # get product
        app_type = self.get_tag('product')
        if not app_type:
            self.log_msg(ERROR, 'Upgrade complete - failed', write_to_changelog=True)
            return False
        self.get_pre_upgrade_information(app_type)
        self.log_change(f'New version: {new_version}')
        self.log_change('Upgrade is underway')
        # spin stack down to 0 nodes
        if not self.spindown_to_zero_appnodes(app_type):
            self.log_msg(INFO, 'Upgrade complete - failed', write_to_changelog=True)
            return False
        # spin stack up to 1 node on new release version
        if not self.spinup_to_one_appnode(app_type, new_version):
            self.log_msg(INFO, 'Upgrade complete - failed', write_to_changelog=True)
            return False
        # spinup remaining nodes in stack if needed
        if self.preupgrade_app_node_count > "1":
            self.spinup_remaining_nodes()
        # TODO wait for remaining nodes to respond ??? ## maybe a LB check for active node count
        # TODO enable traffic at VTM
        return True

    def upgrade_server(self, new_version):
        # get product
        app_type = self.get_tag('product')
        if not app_type:
            self.log_msg(ERROR, 'Upgrade complete - failed', write_to_changelog=True)
            return False
        self.get_pre_upgrade_information(app_type)
        self.log_change(f'New version: {new_version}')
        self.log_change('Upgrade is underway')
        # update the version in stack parameters
        stack_params = self.get_params()
        if any(param for param in stack_params if param['ParameterKey'] == 'ProductVersion'):
            stack_params = self.update_paramlist(stack_params, 'ProductVersion', new_version)
        elif app_type == 'jira':
            stack_params = self.update_paramlist(stack_params, 'JiraVersion', new_version)
        elif app_type == 'confluence':
            stack_params = self.update_paramlist(stack_params, 'ConfluenceVersion', new_version)
        elif app_type == 'crowd':
            stack_params = self.update_paramlist(stack_params, 'CrowdVersion', new_version)
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            cfn.update_stack(StackName=self.stack_name, Parameters=stack_params, UsePreviousTemplate=True, Capabilities=['CAPABILITY_IAM'])
        except Exception as e:
            if 'No updates are to be performed' in e.args[0]:
                self.log_msg(INFO, f'Stack is already at {new_version}', write_to_changelog=True)
            else:
                log.exception('An error occurred updating the version')
                self.log_msg(ERROR, f'An error occurred updating the version: {e}', write_to_changelog=True)
                return False
        if self.wait_stack_action_complete('UPDATE_IN_PROGRESS'):
            self.log_msg(INFO, 'Successfully updated version in stack parameters', write_to_changelog=False)
        else:
            self.log_msg(INFO, 'Could not update version in stack parameters', write_to_changelog=True)
            self.log_msg(INFO, 'Upgrade complete - failed', write_to_changelog=True)
            return False
        # terminate the node and allow new one to spin up
        if not self.rolling_rebuild():
            self.log_msg(ERROR, 'Upgrade complete - failed', write_to_changelog=True)
            return False
        return True

    def upgrade_zdu(self, new_version, username, password):
        self.log_msg(INFO, f'Beginning upgrade for {self.stack_name}', write_to_changelog=False)
        # get product
        app_type = self.get_tag('product')
        if not app_type:
            self.log_msg(ERROR, 'Upgrade complete - failed', write_to_changelog=True)
            return False
        try:
            if not self.get_service_url():
                self.log_msg(ERROR, 'Upgrade complete - failed', write_to_changelog=True)
                return False
        except tenacity.RetryError:
            self.log_msg(ERROR, 'Upgrade complete - failed', write_to_changelog=True)
            return False
        self.session = BaseUrlSession(base_url=self.service_url)
        self.session.auth = (username, password)
        self.get_pre_upgrade_information(app_type)
        self.log_change(f'New version: {new_version}')
        self.log_change('Upgrade is underway')
        # set upgrade mode on
        zdu_state = self.get_zdu_state()
        if zdu_state != 'STABLE':
            self.log_msg(INFO, f'Expected STABLE but ZDU state is {zdu_state}', write_to_changelog=True)
            self.log_msg(INFO, 'Upgrade complete - failed', write_to_changelog=True)
            return False
        if not self.enable_zdu_mode():
            self.log_msg(ERROR, 'Could not enable ZDU mode', write_to_changelog=True)
            self.log_msg(ERROR, 'Upgrade complete - failed', write_to_changelog=True)
            return False
        # update the version in stack parameters
        stack_params = self.get_params()
        stack_params = self.update_paramlist(stack_params, 'JiraVersion', new_version)
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            cfn.update_stack(StackName=self.stack_name, Parameters=stack_params, UsePreviousTemplate=True, Capabilities=['CAPABILITY_IAM'])
        except Exception as e:
            if 'No updates are to be performed' in e.args[0]:
                self.log_msg(INFO, f'Stack is already at {new_version}', write_to_changelog=True)
            else:
                log.exception('An error occurred updating the version')
                self.log_msg(ERROR, f'An error occurred updating the version: {e}', write_to_changelog=True)
                self.cancel_zdu_mode()
                return False
        if self.wait_stack_action_complete('UPDATE_IN_PROGRESS'):
            self.log_msg(INFO, 'Successfully updated version in stack parameters', write_to_changelog=False)
        else:
            self.log_msg(INFO, 'Could not update version in stack parameters', write_to_changelog=True)
            self.log_msg(INFO, 'Upgrade complete - failed', write_to_changelog=True)
            self.cancel_zdu_mode()
            return False
        # terminate the nodes and allow new ones to spin up
        if not self.rolling_rebuild():
            self.log_msg(ERROR, 'Upgrade complete - failed', write_to_changelog=True)
        state = self.get_zdu_state()
        action_start = time.time()
        action_timeout = current_app.config['ACTION_TIMEOUTS']['zdu_ready_to_run_upgrade_tasks']
        while state != 'READY_TO_RUN_UPGRADE_TASKS':
            if (time.time() - action_start) > action_timeout:
                self.log_msg(ERROR, f'Stack is not in READY_TO_RUN_UPGRADE_TASKS mode after {format_timespan(action_timeout)} - aborting', write_to_changelog=True)
                return False
            time.sleep(5)
            state = self.get_zdu_state()
        # approve the upgrade and allow upgrade tasks to run
        if self.approve_zdu_upgrade():
            self.log_msg(INFO, f'Upgrade successful for {self.stack_name} at {self.region} to version {new_version}', write_to_changelog=False)
            self.log_msg(INFO, 'Upgrade complete', write_to_changelog=True)
            return True
        else:
            self.log_msg(ERROR, 'Could not approve upgrade. The upgrade will need to be manually approved or cancelled.', write_to_changelog=True)
            self.log_msg(ERROR, 'Upgrade complete - failed', write_to_changelog=True)

    def destroy(self, delete_changelogs):
        self.log_msg(INFO, f'Destroying stack {self.stack_name} in {self.region}', write_to_changelog=False)
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack_state = cfn.describe_stacks(StackName=self.stack_name)
        except botocore.exceptions.ClientError as e:
            if 'does not exist' in e.response['Error']['Message']:
                self.log_msg(INFO, f'Stack {self.stack_name} does not exist', write_to_changelog=True)
                self.log_msg(INFO, 'Destroy complete - not required', write_to_changelog=True)
                return True
            else:
                log.exception('An error occurred destroying stack')
                self.log_msg(ERROR, f'An error occurred destroying stack: {e}', write_to_changelog=True)
                return False
        stack_id = stack_state['Stacks'][0]['StackId']
        cfn.delete_stack(StackName=self.stack_name)
        if self.wait_stack_action_complete('DELETE_IN_PROGRESS', stack_id):
            self.log_msg(INFO, f'Destroy successful for stack {self.stack_name}', write_to_changelog=True)
            if delete_changelogs:
                s3_bucket = current_app.config['S3_BUCKET']
                s3 = boto3.client('s3', region_name=self.region)
                changelogs = s3.list_objects_v2(Bucket=s3_bucket, Prefix=f'changelogs/{self.stack_name}/')
                keys_to_delete = []
                if 'Contents' in changelogs:
                    for changelog in changelogs['Contents']:
                        keys_to_delete.append({'Key': changelog['Key']})
                    keys_to_delete.append({'Key': f'changelogs/{self.stack_name}'})
                    response = s3.delete_objects(Bucket=s3_bucket, Delete={'Objects': keys_to_delete},)
                    if 'Errors' in response:
                        self.log_msg(ERROR, 'Failed to delete some changelogs from S3', write_to_changelog=True)
        self.log_msg(INFO, 'Destroy complete', write_to_changelog=True)
        return True

    def clone(self, stack_params, template_file, app_type, clustered, creator, region, cloned_from):
        self.log_msg(INFO, 'Initiating clone', write_to_changelog=True)
        # TODO popup confirming if you want to destroy existing
        if not self.destroy(delete_changelogs=False):
            self.log_msg(INFO, 'Clone complete - failed', write_to_changelog=True)
            self.clear_current_action()
        if not self.create(stack_params, template_file, app_type, clustered, creator, region, cloned_from):
            self.log_msg(INFO, 'Clone complete - failed', write_to_changelog=True)
            self.clear_current_action()
            return False
        self.log_change('Create complete, looking for post-clone SQL')
        if self.run_sql():
            self.log_change('SQL complete, restarting {self.stack_name}')
            self.full_restart()
        else:
            self.clear_current_action()
            self.log_msg(INFO, 'Clone complete - Run SQL failed', write_to_changelog=True)
        self.log_msg(INFO, 'Clone complete', write_to_changelog=True)
        return True

    def create_change_set(self, stack_params, template_file):
        self.log_msg(INFO, f"Creating change set for stack with params: {str([param for param in stack_params if 'UsePreviousValue' not in param])}", write_to_changelog=True)
        template_filename = template_file.name
        template = str(template_file)
        self.upload_template(template, template_filename)
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            change_set = cfn.create_change_set(
                ChangeSetName=f'{self.stack_name}-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
                ChangeSetType='UPDATE',
                StackName=self.stack_name,
                Parameters=stack_params,
                TemplateURL=f"https://s3.amazonaws.com/{current_app.config['S3_BUCKET']}/forge-templates/{template_filename}",
                Capabilities=['CAPABILITY_IAM'],
            )
        except botocore.exceptions.ClientError as e:
            log.exception('An error occurred creating change set')
            self.log_msg(ERROR, f'An error occurred creating change set: {e}', write_to_changelog=True)
            self.log_msg(INFO, 'Change set creation complete - failed', write_to_changelog=True)
            return e.response['Error']['Message']
        if not self.wait_stack_change_set_creation_complete(change_set['Id']):
            # reasons we might get here?
            #  - changeset doesn't exist (if creation failed, should've been caught in previous block)
            #  - waiter timed out; changeset creation is taking too long
            self.log_msg(INFO, 'Change set creation complete - failed', write_to_changelog=True)
            return False
        self.log_msg(INFO, f'Change set created {change_set["Id"]}', write_to_changelog=True)
        return change_set

    def get_change_set_details(self, change_set_name):
        self.log_msg(INFO, f'Retrieving details for change set: {change_set_name}', write_to_changelog=False)
        cfn = boto3.client('cloudformation', region_name=self.region)
        change_set_changes = []
        try:
            paginator = cfn.get_paginator('describe_change_set')
            page_iterator = paginator.paginate(ChangeSetName=change_set_name, StackName=self.stack_name)
            for page in page_iterator:
                change_set_changes.extend(page['Changes'])
        except Exception as e:
            log.exception('An error occurred retrieving change set details')
            self.log_msg(ERROR, f'An error occurred retrieving change set details: {e}', write_to_changelog=True)
            return False
        self.log_msg(INFO, 'Change set details retrieved', write_to_changelog=False)
        return change_set_changes

    def execute_change_set(self, change_set_name):
        self.log_msg(INFO, f'Updating stack with changeset: {change_set_name}', write_to_changelog=True)
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            cfn.execute_change_set(ChangeSetName=change_set_name, StackName=self.stack_name)
        except Exception as e:
            log.exception('An error occurred applying change set to stack')
            self.log_msg(ERROR, f'An error occurred applying change set to stack: {e}', write_to_changelog=True)
            self.log_msg(INFO, 'Changeset execution complete - failed', write_to_changelog=True)
            return False
        if not self.wait_stack_action_complete('UPDATE_IN_PROGRESS'):
            self.log_msg(INFO, 'Changeset execution complete - failed', write_to_changelog=True)
            return False
        # only check for response from service if stack is server (should always have one node) or if cluster has more than 0 nodes
        cluster_node_count = self.get_param_value('ClusterNodeCount') or 0
        if not self.is_app_clustered() or int(cluster_node_count) > 0:
            self.log_msg(INFO, 'Waiting for stack to respond', write_to_changelog=False)
            if not self.validate_service_responding():
                self.log_msg(INFO, 'Changeset execution complete - failed', write_to_changelog=True)
                return False
        self.log_msg(INFO, 'Changeset execution complete', write_to_changelog=True)
        return True

    def create(self, stack_params, template_file, app_type, clustered, creator, region, cloned_from=False):
        self.log_msg(INFO, f'Creating stack: {self.stack_name}', write_to_changelog=True)
        self.log_msg(INFO, f'Creation params: {stack_params}', write_to_changelog=True)
        template = str(template_file)
        self.log_change(f'Template is {template}')
        # create tags
        template_path_components = template.split('/')
        if template_path_components[0] != 'atlassian-aws-deployment':
            template_path_components.pop(0)
        tags = [
            {'Key': 'product', 'Value': app_type},
            {'Key': 'clustered', 'Value': clustered},
            {'Key': 'environment', 'Value': next((param['ParameterValue'] for param in stack_params if param['ParameterKey'] == 'DeployEnvironment'), 'not-specified')},
            {'Key': 'created_by', 'Value': creator},
            {'Key': 'repository', 'Value': template_path_components[0]},
            {'Key': 'template', 'Value': template_path_components[-1]},
        ]
        if cloned_from:
            tags.append({'Key': 'cloned_from', 'Value': cloned_from})
        try:
            self.upload_template(template, template_file.name)
            cfn = boto3.client('cloudformation', region_name=region)
            # wait for the template to upload to avoid race conditions
            if 'TESTING' not in current_app.config:
                time.sleep(5)
            # TODO spin up to one node first, then spin up remaining nodes
            created_stack = cfn.create_stack(
                StackName=self.stack_name,
                Parameters=stack_params,
                TemplateURL=f"https://s3.amazonaws.com/{current_app.config['S3_BUCKET']}/forge-templates/{template_file.name}",
                Capabilities=['CAPABILITY_IAM'],
                Tags=tags,
            )
        except Exception as e:
            log.exception('Error occurred creating stack')
            self.log_msg(WARN, f'Error occurred creating stack: {e}', write_to_changelog=True)
            self.log_msg(INFO, 'Create complete - failed', write_to_changelog=True)
            return False
        self.log_msg(INFO, f'Create has begun: {created_stack}', write_to_changelog=False)
        if not self.wait_stack_action_complete('CREATE_IN_PROGRESS'):
            self.log_msg(INFO, 'Create complete - failed', write_to_changelog=True)
            return False
        self.log_msg(INFO, f'Stack {self.stack_name} created, waiting on service responding', write_to_changelog=False)
        if not self.validate_service_responding():
            self.log_msg(INFO, 'Create complete - failed', write_to_changelog=True)
            return False
        self.log_msg(INFO, 'Create complete', write_to_changelog=True)
        return True

    def rolling_restart(self):
        self.log_msg(INFO, f'Beginning Rolling Restart for {self.stack_name}', write_to_changelog=True)
        app_type = self.get_tag('product')
        if not app_type:
            self.log_msg(ERROR, 'Could not determine product', write_to_changelog=True)
            self.log_msg(ERROR, 'Rolling restart complete - failed', write_to_changelog=True)
            return False
        nodes = self.get_stacknodes()
        self.log_msg(INFO, f'{self.stack_name} nodes are {nodes}', write_to_changelog=False)
        # determine if app is clustered or has a single node (rolling restart may cause an unexpected outage)
        if not self.is_app_clustered():
            self.log_msg(ERROR, 'App is not clustered - rolling restart not supported (use full restart)', write_to_changelog=True)
            self.log_msg(ERROR, 'Rolling restart complete - failed', write_to_changelog=True)
            return False
        if len(nodes) == 0:
            self.log_msg(ERROR, 'Node count is 0: nothing to restart', write_to_changelog=True)
            self.log_msg(ERROR, 'Rolling restart complete - failed', write_to_changelog=True)
            return False
        elif len(nodes) == 1:
            self.log_msg(ERROR, 'App only has one node - rolling restart not supported (use full restart)', write_to_changelog=True)
            self.log_msg(ERROR, 'Rolling restart complete - failed', write_to_changelog=True)
            return False
        # determine if the nodes are running or not
        running_nodes = []
        non_running_nodes = []
        for node in nodes:
            node_ip = list(node.values())[0]
            if self.check_node_status(node_ip, False) == 'RUNNING':
                running_nodes.append(node)
            else:
                non_running_nodes.append(node)
        # restart non running nodes first
        for node in itertools.chain(non_running_nodes, running_nodes):
            if not self.shutdown_app(app_type, [node]):
                self.log_msg(INFO, f'Failed to stop application on node {node}', write_to_changelog=True)
                self.log_msg(ERROR, 'Rolling restart complete - failed', write_to_changelog=True)
                return False
            if not self.startup_app(app_type, [node]):
                self.log_msg(INFO, f'Failed to start application on node {node}', write_to_changelog=True)
                self.log_msg(ERROR, 'Rolling restart complete - failed', write_to_changelog=True)
                return False
            node_ip = list(node.values())[0]
            if not self.validate_node_responding(node_ip):
                self.log_msg(INFO, 'Rolling restart complete - failed', write_to_changelog=True)
                return False
        self.log_msg(INFO, 'Rolling restart complete', write_to_changelog=True)
        return True

    def full_restart(self):
        self.log_msg(INFO, f'Beginning Full Restart for {self.stack_name}', write_to_changelog=True)
        app_type = self.get_tag('product')
        if not app_type:
            self.log_msg(ERROR, 'Full restart complete - failed', write_to_changelog=True)
            return False
        nodes = self.get_stacknodes()
        if len(nodes) == 0:
            self.log_msg(ERROR, 'Node count is 0: nothing to restart', write_to_changelog=True)
            self.log_msg(ERROR, 'Full restart complete - failed', write_to_changelog=True)
            return False
        self.log_msg(INFO, f'{self.stack_name} nodes are {nodes}', write_to_changelog=False)
        if not self.shutdown_app(app_type, nodes):
            self.log_msg(ERROR, 'Full restart complete - failed', write_to_changelog=True)
            return False
        for node in nodes:
            self.startup_app(app_type, [node])
        self.log_msg(INFO, 'Full restart complete', write_to_changelog=True)
        return True

    def rolling_rebuild(self):
        self.log_msg(INFO, 'Rolling rebuild has begun', write_to_changelog=True)
        ec2 = boto3.client('ec2', region_name=self.region)
        old_nodes = self.get_stacknodes()
        self.log_msg(INFO, f'Old nodes: {old_nodes}', write_to_changelog=True)
        new_nodes = []
        try:
            for node in old_nodes:
                # destroy each node and wait for another to be created to replace it
                self.log_msg(INFO, f'Replacing node {node}', write_to_changelog=True)
                ec2.terminate_instances(InstanceIds=[list(node.keys())[0]])
                time.sleep(30)
                nodes = self.get_stacknodes()
                waiting_for_new_node_creation = True
                replacement_node = {}
                action_start = time.time()
                action_timeout = current_app.config['ACTION_TIMEOUTS']['node_initialisation']
                while waiting_for_new_node_creation:
                    for node in nodes:
                        # check the node id against the old nodes
                        if list(node.keys())[0] not in set().union(*(node.keys() for node in old_nodes)):
                            # if the node is new, track it
                            if node not in new_nodes:
                                # check for IP, break out if not assigned yet
                                if list(node.values())[0] is None:
                                    break
                                # otherwise, store the node and proceed
                                replacement_node = node
                                self.log_msg(INFO, f'New node: {replacement_node}', write_to_changelog=True)
                                new_nodes.append(replacement_node)
                                waiting_for_new_node_creation = False
                    if (time.time() - action_start) > action_timeout:
                        self.log_msg(ERROR, f'New node failed to be created after {format_timespan(action_timeout)} - aborting', write_to_changelog=True)
                        return False
                    time.sleep(30)
                    nodes = self.get_stacknodes()
                # wait for the new node to come up
                node_ip = list(replacement_node.values())[0]
                if not self.validate_node_responding(node_ip):
                    self.log_msg(ERROR, 'Rolling rebuild complete - failed', write_to_changelog=True)
                    return False
            self.log_msg(INFO, 'Rolling rebuild complete', write_to_changelog=True)
            self.log_change(f'New nodes are: {new_nodes}')
            return True
        except Exception as e:
            log.exception('An error occurred during rolling rebuild')
            self.log_msg(ERROR, f'An error occurred during rolling rebuild: {e}', write_to_changelog=True)
            self.log_msg(ERROR, 'Rolling rebuild complete - failed', write_to_changelog=True)
            return False

    def thread_dump(self, alsoHeaps=False):
        heaps_to_come_log_line = ''
        if alsoHeaps == 'true':
            heaps_to_come_log_line = ', heap dumps to follow'
        self.log_msg(INFO, f'Beginning thread dumps on {self.stack_name}{heaps_to_come_log_line}', write_to_changelog=False)
        nodes = self.get_stacknodes()
        self.log_msg(INFO, f'{self.stack_name} nodes are {nodes}', write_to_changelog=False)
        self.run_command(nodes, '/usr/local/bin/j2ee_thread_dump')
        self.log_msg(INFO, 'Successful thread dumps can be downloaded from the main Diagnostics page', write_to_changelog=False)
        self.log_msg(INFO, 'Thread dumps complete', write_to_changelog=False)
        return True

    def heap_dump(self):
        self.log_msg(INFO, f'Beginning heap dumps on {self.stack_name}', write_to_changelog=False)
        nodes = self.get_stacknodes()
        self.log_msg(INFO, f'{self.stack_name} nodes are {nodes}', write_to_changelog=False)
        # Wait for each heap dump to finish before starting the next, to avoid downtime
        for node in nodes:
            self.ssm_send_and_wait_response(list(node.keys())[0], '/usr/local/bin/j2ee_heap_dump_live')
            if 'TESTING' not in current_app.config:
                time.sleep(30)  # give node time to recover and rejoin cluster
        self.log_msg(INFO, 'Heap dumps complete', write_to_changelog=False)
        return True

    def run_sql(self):
        self.log_msg(INFO, 'Running post clone SQL', write_to_changelog=True)
        nodes = self.get_stacknodes()
        sql_to_run = self.get_sql()
        if sql_to_run != 'No SQL script exists for this stack':
            cloned_from_stack = self.get_tag('cloned_from')
            db_conx_string = 'PGPASSWORD=${ATL_DB_PASSWORD} /usr/bin/psql -v ON_ERROR_STOP=1 -h ${ATL_DB_HOST} -p ${ATL_DB_PORT} -U postgres -w ${ATL_DB_NAME}'
            # on node, grab cloned_from sql from s3
            self.run_command(
                [nodes[0]],
                f"aws s3 sync s3://{current_app.config['S3_BUCKET']}/config/stacks/{cloned_from_stack}/{cloned_from_stack}-clones-sql.d /tmp/{cloned_from_stack}-clones-sql.d",
            )
            # run that sql
            if not self.run_command(
                [nodes[0]], f'source /etc/atl; for file in `ls /tmp/{cloned_from_stack}-clones-sql.d/*.sql`;do {db_conx_string} -a -f $file >> /var/log/sql.out 2>&1; done',
            ):
                self.log_msg(ERROR, f'Running SQL script failed', write_to_changelog=True)
                return False
            # on node, grab local-stack sql from s3
            self.run_command([nodes[0]], f"aws s3 sync s3://{current_app.config['S3_BUCKET']}/config/stacks/{self.stack_name}/local-post-clone-sql.d /tmp/local-post-clone-sql.d")
            # run that sql
            if not self.run_command(
                [nodes[0]], f'source /etc/atl; for file in `ls /tmp/local-post-clone-sql.d/*.sql`;do {db_conx_string} -a -f $file >> /var/log/sql.out 2>&1; done'
            ):
                self.log_msg(ERROR, f'Running SQL script failed', write_to_changelog=True)
        else:
            self.log_msg(INFO, 'No post clone SQL files found', write_to_changelog=True)
            return False
        self.log_msg(INFO, 'Run SQL complete', write_to_changelog=True)
        return True

    def tag(self, tags):
        self.log_msg(INFO, 'Tagging stack', write_to_changelog=True)
        params = self.get_params()
        stackname_param = [param for param in params if param['ParameterKey'] == 'StackName']
        if len(stackname_param) > 0:
            params.remove(stackname_param[0])
        for param in params:
            for key, value in param.items():
                if value == 'DBMasterUserPassword' or value == 'DBPassword':
                    try:
                        del param['ParameterValue']
                    except KeyError:
                        pass
                    param['UsePreviousValue'] = True
        self.log_change(f'Parameters for update: {params}')
        try:
            cfn = boto3.client('cloudformation', region_name=self.region)
            cfn.update_stack(StackName=self.stack_name, Parameters=params, UsePreviousTemplate=True, Tags=tags, Capabilities=['CAPABILITY_IAM'])
            self.log_msg(INFO, f'Tagging successfully initiated', write_to_changelog=False)
        except Exception as e:
            log.exception('An error occurred tagging stack')
            self.log_msg(ERROR, f'An error occurred tagging stack: {e}', write_to_changelog=True)
            return False
        if self.wait_stack_action_complete('UPDATE_IN_PROGRESS'):
            self.log_msg(INFO, 'Tag complete', write_to_changelog=True)
            return True
        return False

    # Logging functions
    def create_action_log(self, action):
        # create a datestamped file for the action
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f'stacks/{self.stack_name}/logs/{self.stack_name}_{timestamp}_{action}.action.log'
        if not os.path.exists(os.path.dirname(filename)):
            try:
                os.makedirs(os.path.dirname(filename))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
        open(filename, 'w').close()
        self.logfile = filename

    def log_msg(self, level, message, write_to_changelog):
        if self.logfile is not None:
            logline = f'{datetime.now().strftime("%Y-%m-%d %X")} {getLevelName(level)} {message}'
            log.log(level, message)
            with open(self.logfile, 'a') as logfile:
                logfile.write(f'{logline}\n')
        # consider carefully whether this msg needs to go into the changelog
        # if more appropriate, use log_change directly to log an altered message to the changelog
        if write_to_changelog:
            self.log_change(message)

    def create_change_log(self, action):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f'stacks/{self.stack_name}/logs/{self.stack_name}_{timestamp}_{action}.change.log'
        open(filename, 'w').close()
        self.changelogfile = filename

    def log_change(self, message):
        if self.changelogfile is not None:
            logline = f'{datetime.now()} {message} \n'
            with open(self.changelogfile, 'a') as logfile:
                logfile.write(logline)

    def save_change_log(self):
        if self.changelogfile is not None:
            changelog = os.path.relpath(self.changelogfile)
            changelog_filename = os.path.basename(self.changelogfile)
            s3 = boto3.resource('s3', region_name=self.region)
            s3.meta.client.upload_file(changelog, current_app.config['S3_BUCKET'], f'changelogs/{self.stack_name}/{changelog_filename}')
