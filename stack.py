import boto3
import botocore
import time
import requests
import json
from pathlib import Path
import log
import os
import shutil
import configparser
from datetime import datetime
import itertools
import errno
import re
import json


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
            print(f'{datetime.now()} {log.ERROR} {error_string}')
            raise ValueError(error_string)
        self.region = region

## Stack - micro function methods
    def getLburl(self):
        if hasattr(self, 'lburl'):
            return self.lburl
        else:
            try:
                cfn = boto3.client('cloudformation', region_name=self.region)
                stack_details = cfn.describe_stacks(StackName=self.stack_name)
            except Exception as e:
                print(e.args[0])
                return f'Error checking service status: {e.args[0]}'
            context_path_param = next((parm for parm in stack_details['Stacks'][0]['Parameters'] if parm['ParameterKey'] == 'TomcatContextPath'), None)
            if context_path_param:
                context_path = context_path_param['ParameterValue']
                rawlburl = [p['OutputValue'] for p in stack_details['Stacks'][0]['Outputs'] if
                            p['OutputKey'] == 'LoadBalancerURL'][0] + context_path
                self.lburl = rawlburl

    def getparms(self):
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack_details = cfn.describe_stacks(StackName=self.stack_name)
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return False
        return stack_details['Stacks'][0]['Parameters']

    def getparamvalue(self, param_to_get):
        params = self.getparms()
        for param in params:
            if param['ParameterKey'].lower() == param_to_get.lower():
                return param['ParameterValue']

    def update_parmlist(self, parmlist, parmkey, parmvalue):
        key_found=False
        for dict in parmlist:
            for k, v in dict.items():
                if v == parmkey:
                    dict['ParameterValue'] = parmvalue
                    key_found=True
                if v == 'DBMasterUserPassword' or v == 'DBPassword':
                    try:
                        del dict['ParameterValue']
                    except:
                        pass
                    dict['UsePreviousValue'] = True
        if not key_found:
            parmlist.append({'ParameterKey': parmkey, 'ParameterValue': parmvalue})
        return parmlist

    def upload_template(self, file, s3_name):
        config = configparser.ConfigParser()
        config.read('forge.properties')
        s3_bucket = config['s3']['bucket']
        s3 = boto3.resource('s3', region_name=self.region)
        s3.meta.client.upload_file(file, s3_bucket, f'forge-templates/{s3_name}')

    def ssm_send_command(self, instance, cmd):
        config = configparser.ConfigParser()
        config.read('forge.properties')
        logs_bucket = f"{config['s3']['bucket']}/logs"
        ssm = boto3.client('ssm', region_name=self.region)
        ssm_command = ssm.send_command(
            InstanceIds=[instance],
            DocumentName='AWS-RunShellScript',
            Parameters={'commands': [cmd], 'executionTimeout': ["900"]},
            OutputS3BucketName=logs_bucket,
            OutputS3KeyPrefix='run-command-logs'
        )
        self.log_msg(log.INFO, f'for command: {cmd}, command_id is {ssm_command["Command"]["CommandId"]}')
        if ssm_command['ResponseMetadata']['HTTPStatusCode'] == 200:
            return (ssm_command['Command']['CommandId'])
        return False

    def ssm_cmd_check(self, cmd_id):
        ssm = boto3.client('ssm', region_name=self.region)
        list_command = ssm.list_commands(CommandId=cmd_id)
        cmd_status = list_command[u'Commands'][0][u'Status']
        instance = list_command[u'Commands'][0][u'InstanceIds'][0]
        self.log_msg(log.INFO, f'result of ssm command {cmd_id} on instance {instance} is {cmd_status}')
        return (cmd_status, instance)

    def ssm_send_and_wait_response(self, instance, cmd):
        cmd_id = self.ssm_send_command(instance, cmd)
        if not cmd_id:
            self.log_msg(log.ERROR, f'Command {cmd} on instance {instance} failed to send')
            return False
        else:
            result = self.wait_for_cmd_result(cmd_id)
        return result


## Stack - helper methods

    def spindown_to_zero_appnodes(self, app_type):
        self.log_msg(log.INFO, f'Spinning {self.stack_name} stack down to 0 nodes')
        cfn = boto3.client('cloudformation', region_name=self.region)
        spindown_parms = self.getparms()
        spindown_parms = self.update_parmlist(spindown_parms, 'ClusterNodeMax', '0')
        spindown_parms = self.update_parmlist(spindown_parms, 'ClusterNodeMin', '0')
        if app_type == 'confluence':
            spindown_parms = self.update_parmlist(spindown_parms, 'SynchronyClusterNodeMax', '0')
            spindown_parms = self.update_parmlist(spindown_parms, 'SynchronyClusterNodeMin', '0')
        try:
            cfn.update_stack(
                StackName=self.stack_name,
                Parameters=spindown_parms,
                UsePreviousTemplate=True,
                Capabilities=['CAPABILITY_IAM']
            )
        except Exception as e:
            if 'No updates are to be performed' in e.args[0]:
                self.log_msg(log.INFO, 'Stack is already at 0 nodes')
                return True
            else:
                print(e.args[0])
                self.log_msg(log.ERROR, f'An error occurred spinning down to 0 nodes: {e.args[0]}')
                return False
        if self.wait_stack_action_complete("UPDATE_IN_PROGRESS"):
            self.log_msg(log.INFO, "Successfully spun down to 0 nodes")
            return True
        return False

    def wait_stack_action_complete(self, in_progress_state, stack_id=None):
        self.log_msg(log.INFO, "Waiting for stack action to complete")
        stack_state = self.check_stack_state()
        while stack_state == in_progress_state:
            time.sleep(10)
            stack_state = self.check_stack_state(stack_id if stack_id else self.stack_name)
        if 'ROLLBACK' in stack_state:
            self.log_msg(log.ERROR,f'Stack action was rolled back: {stack_state}')
            return False
        elif 'FAILED' in stack_state:
            self.log_msg(log.ERROR,f'Stack action failed: {stack_state}')
            return False
        return True

    def spinup_to_one_appnode(self, app_type, new_version):
        self.log_msg(log.INFO, "Spinning stack up to one appnode")
        # for connie 1 app node and 1 synchrony
        cfn = boto3.client('cloudformation', region_name=self.region)
        spinup_parms = self.getparms()
        spinup_parms = self.update_parmlist(spinup_parms, 'ClusterNodeMax', '1')
        spinup_parms = self.update_parmlist(spinup_parms, 'ClusterNodeMin', '1')
        if app_type == 'jira':
            spinup_parms = self.update_parmlist(spinup_parms, 'JiraVersion', new_version)
        elif app_type == 'confluence':
            spinup_parms = self.update_parmlist(spinup_parms, 'ConfluenceVersion', new_version)
            spinup_parms = self.update_parmlist(spinup_parms, 'SynchronyClusterNodeMax', '1')
            spinup_parms = self.update_parmlist(spinup_parms, 'SynchronyClusterNodeMin', '1')
        elif app_type == 'crowd':
            spinup_parms = self.update_parmlist(spinup_parms, 'CrowdVersion', new_version)
        try:
            update_stack = cfn.update_stack(
                StackName=self.stack_name,
                Parameters=spinup_parms,
                UsePreviousTemplate=True,
                Capabilities=['CAPABILITY_IAM']
            )
        except botocore.exceptions.ClientError as e:
            self.log_msg(log.INFO, f'Stack spinup failed: {e.args[0]}')
            return False
        if not self.wait_stack_action_complete('UPDATE_IN_PROGRESS'):
            return False
        self.log_msg(log.INFO, 'Spun up to 1 node, waiting for service to respond')
        self.validate_service_responding()
        self.log_msg(log.INFO, f'Updated stack: {update_stack}')
        return True

    def validate_service_responding(self):
        self.log_msg(log.INFO, 'Waiting for service to reply on /status')
        service_state = self.check_service_status()
        while service_state  not in ['RUNNING', 'FIRST_RUN']:
            time.sleep(60)
            service_state = self.check_service_status()
        self.log_msg(log.INFO, f'{self.stack_name} /status now reporting {service_state}')
        return

    def check_service_status(self, logMsgs=True):
        self.getLburl()
        if logMsgs:
            self.log_msg(log.INFO,
                        f' ==> checking service status at {self.lburl}/status')
        try:
            service_status = requests.get(self.lburl + '/status', timeout=5)
            if service_status.status_code == 200:
                status = service_status.text
                json_status = json.loads(status)
                if 'state' in json_status:
                    status = json_status['state']
            else:
                status = str(service_status.status_code) + ": " + service_status.reason[:19] if service_status.reason else str(service_status.status_code)
            if logMsgs:
                self.log_msg(log.INFO,
                            f' ==> service status is: {status}')
            return status
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
            if logMsgs:
                self.log_msg(log.INFO, f'Service status check timed out')
        return 'Timed Out'

    def check_stack_state(self, stack_id=None):
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack_state = cfn.describe_stacks(StackName=stack_id if stack_id else self.stack_name)
        except Exception as e:
            if "does not exist" in e.response['Error']['Message']:
                self.log_msg(log.INFO, f'Stack {self.stack_name} does not exist')
                return
            print(e.args[0])
            self.log_msg(log.ERROR, f'Error checking stack state: {e.args[0]}')
            return
        state = stack_state['Stacks'][0]['StackStatus']
        return state

    def check_node_status(self, node_ip, logMsgs=True):
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack = cfn.describe_stacks(StackName=self.stack_name)
        except Exception as e:
            print(e.args[0])
            return f'Error checking node status: {e.args[0]}'
        context_path = [param['ParameterValue'] for param in stack['Stacks'][0]['Parameters']  if param['ParameterKey'] == 'TomcatContextPath'][0]
        port = [param['ParameterValue'] for param in stack['Stacks'][0]['Parameters'] if param['ParameterKey'] == 'TomcatDefaultConnectorPort'][0]
        if logMsgs:
            self.log_msg(log.INFO, f' ==> checking node status at {node_ip}:{port}{context_path}/status')
        try:
            node_status = json.loads(requests.get(f'http://{node_ip}:{port}{context_path}/status', timeout=5).text)
            if 'state' in node_status:
                status = node_status['state']
            else:
                self.log_msg(log.ERROR, f'Node status not in expected format: {node_status}')
            if logMsgs:
                self.log_msg(log.INFO, f' ==> node status is: {status}')
            return status
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout) as e:
            if logMsgs:
                self.log_msg(log.INFO, f'Node status check timed out')
        except Exception as e:
            print(e.args[0])
        return "Timed Out"

    def spinup_remaining_nodes(self, app_type, app_node_count, synchrony_node_count=False):
        self.log_msg(log.INFO, 'Spinning up any remaining nodes in stack')
        cfn = boto3.client('cloudformation', region_name=self.region)
        spinup_parms = self.getparms()
        spinup_parms = self.update_parmlist(spinup_parms, 'ClusterNodeMax', app_node_count)
        spinup_parms = self.update_parmlist(spinup_parms, 'ClusterNodeMin', app_node_count)
        if synchrony_node_count:
            spinup_parms = self.update_parmlist(spinup_parms, 'SynchronyClusterNodeMax', synchrony_node_count)
            spinup_parms = self.update_parmlist(spinup_parms, 'SynchronyClusterNodeMin', synchrony_node_count)
        try:
            cfn.update_stack(
                StackName=self.stack_name,
                Parameters=spinup_parms,
                UsePreviousTemplate=True,
                Capabilities=['CAPABILITY_IAM']
            )
        except Exception as e:
            print(e.args[0])
            self.log_msg(log.ERROR, f'Error occurred spinning up remaining nodes: {e.args[0]}')
            return False
        if self.wait_stack_action_complete("UPDATE_IN_PROGRESS"):
            self.log_msg(log.INFO, "Stack restored to full node count")
        return True

    def get_stacknodes(self):
        ec2 = boto3.resource('ec2', region_name=self.region)
        filters = [
            {'Name': 'tag:aws:cloudformation:stack-name', 'Values': [self.stack_name]},
            {'Name': 'tag:aws:cloudformation:logical-id', 'Values': ['ClusterNodeGroup']},
            {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'shutting-down', 'stopping', 'stopped']}
        ]
        self.instancelist = []
        for i in ec2.instances.filter(Filters=filters):
            instancedict = {i.instance_id: i.private_ip_address}
            self.instancelist.append(instancedict)
        return

    def shutdown_app(self, instancelist, app_type):
        cmd_id_list = []
        for i in range(0, len(instancelist)):
            for key in instancelist[i]:
                instance = key
                node_ip = instancelist[i][instance]
            self.log_msg(log.INFO, f'Shutting down {app_type} on {instance} ({node_ip})')
            self.log_change(f'Shutting down {app_type} on {instance} ({node_ip})')
            cmd = f'/etc/init.d/{app_type} stop'
            cmd_id_list.append(self.ssm_send_command(instance, cmd))
        for cmd_id in cmd_id_list:
            result = self.wait_for_cmd_result(cmd_id)
            if result == 'Failed':
                self.log_msg(log.ERROR, f'Shutdown result for {cmd_id}: {result}')
            else:
                self.log_msg(log.INFO, f'Shutdown result for {cmd_id}: {result}')
            self.log_change(f'Shutdown result for {cmd_id}: {result}')
        return True

    def startup_app(self, instancelist, app_type):
        for instancedict in instancelist:
            instance = list(instancedict.keys())[0]
            node_ip = list(instancedict.values())[0]
            self.log_msg(log.INFO, f'Starting up {instance} ({node_ip})')
            self.log_change(f'Starting up {instance} ({node_ip})')
            cmd = f'/etc/init.d/{app_type} start'
            cmd_id = self.ssm_send_command(instance, cmd)
            result = self.wait_for_cmd_result(cmd_id)
            if result == 'Failed':
                self.log_msg('ERROR', f'Startup result for {cmd_id}: {result}')
                return False
            else:
                result = ""
                while result not in ['RUNNING', 'FIRST_RUN']:
                    result = self.check_node_status(node_ip)
                    self.log_msg(log.INFO, f'Startup result for {cmd_id}: {result}')
                    time.sleep(60)
            self.log_msg(log.INFO, f'Application started on instance {instance}')
            self.log_change(f'Application started on instance {instance}')
        return True

    def run_command(self, instancelist, cmd):
        cmd_id_dict = {}
        for instancedict in instancelist:
            instance = list(instancedict.keys())[0]
            node_ip = list(instancedict.values())[0]
            self.log_msg(log.INFO, f'Running command {cmd} on {node_ip}')
            cmd_id_dict[self.ssm_send_command(instance, cmd)] = node_ip
        for cmd_id in cmd_id_dict:
            result = self.wait_for_cmd_result(cmd_id)
            if result == 'Failed':
                self.log_msg(log.ERROR, f'Command result for {cmd_id}: {result}')
                return False
            else:
                self.log_msg(log.INFO, f'Command result for {cmd_id}: {result}')
        return True

    def wait_for_cmd_result(self, cmd_id):
        result = ""
        while result != 'Success' and result != 'Failed':
            result, cmd_instance = self.ssm_cmd_check(cmd_id)
            time.sleep(10)
        return result

    def get_stack_action_in_progress(self):
        if Path(f'locks/{self.stack_name}').exists():
            return os.listdir(f'locks/{self.stack_name}')[0]
        return False

    def store_current_action(self, action, locking_enabled, changelog, actor):
        action_already_in_progress = self.get_stack_action_in_progress()
        if not action_already_in_progress:
            os.mkdir(f'locks/{self.stack_name}')
            os.mkdir(f'locks/{self.stack_name}/{action}')
        elif locking_enabled:
            self.log_msg(log.ERROR, f'Cannot begin action: {action}. Another action is in progress: {action_already_in_progress}')
            return False
        self.create_action_log(action)
        if changelog:
            self.create_change_log(action)
            if actor:
                self.log_change(f"Action triggered by {actor}")
        return True

    def clear_current_action(self):
        self.save_change_log()
        if Path(f'locks/{self.stack_name}').exists():
            shutil.rmtree(f'locks/{self.stack_name}')
        return True

    def get_parms_for_update(self):
        parms = self.getparms()
        stackName_param = next((param for param in parms if param['ParameterKey'] == 'StackName'), None)
        if stackName_param:
            parms.remove(stackName_param)
        for dict in parms:
            for k, v in dict.items():
                if v == 'DBMasterUserPassword' or v == 'DBPassword':
                    try:
                        del dict['ParameterValue']
                    except:
                        pass
                    dict['UsePreviousValue'] = True
        return parms

    def get_tags(self):
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack = cfn.describe_stacks(StackName=self.stack_name)
        except Exception as e:
            self.log_msg(log.ERROR, f'Error getting tags: {e.args[0]}')
            print(f'Error getting tags: {e.args[0]}')
            return False
        tags = stack['Stacks'][0]['Tags']
        return tags

    def get_tag(self, tag_name):
        tags = self.get_tags()
        if tags:
            tag= [tag for tag in tags if tag['Key'] == tag_name]
            if tag:
                tag_value = tag[0]['Value']
                if hasattr(self, 'logfile'):
                    self.log_msg(log.INFO, f'{tag_name} is {tag_value}')
                return tag_value.lower()
        if hasattr(self, 'logfile'):
            self.log_msg(log.WARN, f'Tag {tag_name} not found')
        return False

    def get_sql(self):
        sql_to_run = ''
        # get SQL for the stack this stack was cloned from (ie the master stack)
        cloned_from_stack = self.get_tag('cloned_from')
        if cloned_from_stack:
            cloned_from_stack_sql_dir = f'stacks/{cloned_from_stack}/{cloned_from_stack}-clones-sql.d/'
            if Path(cloned_from_stack_sql_dir).exists():
                sql_files = os.listdir(cloned_from_stack_sql_dir)
                if len(sql_files) > 0:
                    sql_to_run = f'---- ***** SQL to run for clones of {cloned_from_stack} *****\n\n'
                    sql_exists = True
                    for file in sql_files:
                        sql_file = open(os.path.join(cloned_from_stack_sql_dir, file), "r")
                        sql_to_run = f"{sql_to_run}-- *** SQL from {cloned_from_stack} {sql_file.name} ***\n\n{sql_file.read()}\n\n"
        # get SQL for this stack
        own_sql_dir = f'stacks/{self.stack_name}/local-post-clone-sql.d/'
        if Path(own_sql_dir).exists():
            sql_files = os.listdir(own_sql_dir)
            if len(sql_files) > 0:
                sql_to_run = f'{sql_to_run}---- ***** SQL to run for {self.stack_name} *****\n\n'
                sql_exists = True
                for file in sql_files:
                    sql_file = open(os.path.join(own_sql_dir, file), "r")
                    sql_to_run = f"{sql_to_run}-- *** SQL from {sql_file.name} ***\n\n{sql_file.read()}\n\n"
        if len(sql_to_run) > 0:
            return sql_to_run
        return 'No SQL script exists for this stack'

    def get_pre_upgrade_information(self):
        self.log_msg(log.INFO, f'Beginning upgrade for {self.stack_name}')
        # get pre-upgrade state information
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack_details = cfn.describe_stacks(StackName=self.stack_name)
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            self.log_msg(log.ERROR, 'Upgrade complete - failed')
            return False
        # get product
        self.app_type = self.get_tag('product')
        if not self.app_type:
            self.log_msg(log.ERROR, 'Upgrade complete - failed')
            return False
        # get preupgrade version and node counts
        self.preupgrade_version = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                              p['ParameterKey'] in ('ConfluenceVersion', 'JiraVersion', 'CrowdVersion')][0]
        self.preupgrade_app_node_count = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                                     p['ParameterKey'] == 'ClusterNodeMax'][0]
        if self.app_type.lower() == 'confluence':
            self.preupgrade_synchrony_node_count = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                                               p['ParameterKey'] == 'SynchronyClusterNodeMax'][0]
        # create changelog
        self.log_change(f'Pre upgrade version: {self.preupgrade_version}')

    def get_zdu_state(self, username, password):
        try:
            self.get_session_cookie(username, password)
            response = requests.get(self.lburl + '/rest/api/2/cluster/zdu/state', timeout=5, headers={'Authorization': f'Basic {username}:{password}'}).text
            response_json = json.loads(response)
            return response_json['state']
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
            self.log_msg(log.INFO, f'ZDU state check timed out')
            return False
        except Exception:
            self.log_msg(log.INFO, 'Could not retrieve ZDU state')
            return False

    def enable_zdu_mode(self, auth_string):
        try:
            requests.post(self.lburl + '/rest/api/2/cluster/zdu/start', data={'Authorization': f'Basic {auth_string}'}, timeout=5)
            while self.get_zdu_state() != 'READY':
                time.sleep(5)
            return True
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
            self.log_msg(log.INFO, f'Could not enable ZDU mode')
            return False

    def get_session_cookie(self, username, password):
        try:
            result = requests.post(self.lburl + '/rest/auth/1/session', json={'username': username, 'password': password}, timeout=5)
            if result.status_code == 200:
                json_result = json.loads(result.text)
                json_result['session']['value'] # cookie
                while self.get_zdu_state(username, password) != 'READY':
                    time.sleep(5)
                    return True
            else:
                #TODO handle error
                pass
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
            self.log_msg(log.INFO, f'Could not get session cookie')
            return False


## Stack - Major Action Methods

    def upgrade(self, new_version):
        self.get_pre_upgrade_information()
        self.log_change(f'New version: {new_version}')
        self.log_change('Upgrade is underway')
        # spin stack down to 0 nodes
        if not self.spindown_to_zero_appnodes(self.app_type):
            self.log_msg(log.INFO, 'Upgrade complete - failed')
            self.log_change('Upgrade failed, see action log for details')
            return False
        # spin stack up to 1 node on new release version
        if not self.spinup_to_one_appnode(self.app_type, new_version):
            self.log_msg(log.INFO, 'Upgrade complete - failed')
            self.log_change('Change failed, see action log for details')
            return False
        # spinup remaining nodes in stack if needed
        if self.preupgrade_app_node_count > "1":
            if self.app_type.lower() == 'confluence':
                self.spinup_remaining_nodes(self.app_type, self.preupgrade_app_node_count, self.preupgrade_synchrony_node_count)
            else:
                self.spinup_remaining_nodes(self.app_type, self.preupgrade_app_node_count)
        # TODO wait for remaining nodes to respond ??? ## maybe a LB check for active node count
        # TODO enable traffic at VTM
        self.log_msg(log.INFO, f'Upgrade successful for {self.stack_name} at {self.region} to version {new_version}')
        self.log_msg(log.INFO, 'Upgrade complete')
        self.log_change('Upgrade successful')
        return True

    def upgrade_zdu(self, new_version, username, password):
        self.getLburl()
        self.get_pre_upgrade_information()
        self.log_change(f'New version: {new_version}')
        self.log_change('Upgrade is underway')
        # set upgrade mode on
        zdu_state = self.get_zdu_state(username, password)
        if zdu_state == 'STABLE':
            if self.enable_zdu_mode(username, password):
                # update the version in stack parameters
                stack_params = self.getparms()
                stack_params = self.update_parmlist(stack_params, 'JiraVersion', new_version)
                cfn = boto3.client('cloudformation', region_name=self.region)
                try:
                    cfn.update_stack(
                        StackName=self.stack_name,
                        Parameters=stack_params,
                        UsePreviousTemplate=True,
                        Capabilities=['CAPABILITY_IAM'])
                except Exception as e:
                    if 'No updates are to be performed' in e.args[0]:
                        self.log_msg(log.INFO, f'Stack is already at {new_version}')
                    else:
                        print(e.args[0])
                        self.log_msg(log.ERROR, f'An error occurred updating the version: {e.args[0]}')
                        return False
                if self.wait_stack_action_complete('UPDATE_IN_PROGRESS'):
                    self.log_msg(log.INFO, 'Successfully updated version in stack parameters')
                else:
                    self.log_msg(log.INFO, 'Could not update version in stack parameters')
                    self.log_msg(log.INFO, 'Upgrade complete - failed')
                    self.log_change('Upgrade failed - could not update version in stack parameters')
                    return False
                # terminate the nodes and allow new ones to spin up
                if self.rolling_rebuild():
                    zdu_json = self.get_zdu_state()
                    if zdu_json and 'state' in zdu_json:
                        zdu_state = zdu_json['state']
                        if zdu_state == 'STABLE':
                            pass
            else:
                self.log_msg(log.ERROR, 'Could not enable ZDU mode')
                self.log_change('Could not enable ZDU mode')
        else:
            self.log_msg(log.INFO, f'Expected STABLE but ZDU state is {zdu_state}')
            self.log_msg(log.INFO, 'Upgrade complete - failed')
            self.log_change(f'Upgrade failed, expected STABLE but ZDU state is {zdu_state}')
            return False
        # spin stack up to 1 node on new release version
        if not self.spinup_to_one_appnode(self.app_type, new_version):
            self.log_msg(log.INFO, 'Upgrade complete - failed')
            self.log_change('Change failed, see action log for details')
            return False
        # spinup remaining nodes in stack if needed
        if self.preupgrade_app_node_count > "1":
            if self.app_type.lower() == 'confluence':
                self.spinup_remaining_nodes(self.app_type, self.preupgrade_app_node_count, self.preupgrade_synchrony_node_count)
            else:
                self.spinup_remaining_nodes(self.app_type, self.preupgrade_app_node_count)
        # TODO wait for remaining nodes to respond ??? ## maybe a LB check for active node count
        # TODO enable traffic at VTM
        self.log_msg(log.INFO, f'Upgrade successful for {self.stack_name} at {self.region} to version {new_version}')
        self.log_msg(log.INFO, 'Upgrade complete')
        self.log_change('Upgrade successful')
        return True

    def destroy(self):
        self.log_msg(log.INFO, f'Destroying stack {self.stack_name} in {self.region}')
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack_state = cfn.describe_stacks(StackName=self.stack_name)
        except botocore.exceptions.ClientError as e:
            if "does not exist" in e.response['Error']['Message']:
                self.log_msg(log.INFO, f'Stack {self.stack_name} does not exist')
                self.log_msg(log.INFO, "Destroy complete - not required")
                self.log_change(f'Stack {self.stack_name} does not exist, destroy not required')
                return True
        stack_id = stack_state['Stacks'][0]['StackId']
        cfn.delete_stack(StackName=self.stack_name)
        if self.wait_stack_action_complete("DELETE_IN_PROGRESS", stack_id):
            self.log_msg(log.INFO, f'Destroy successful for stack {self.stack_name}')
            self.log_change(f'Destroy successful for stack {self.stack_name}')
        self.log_msg(log.INFO, 'Destroy complete')
        return True

    def clone(self, stack_parms, template_file, app_type, instance_type, region, creator, cloned_from):
        self.log_msg(log.INFO, 'Initiating clone')
        self.log_change('Initiating clone')
        # TODO popup confirming if you want to destroy existing
        if self.destroy():
            if self.create(stack_parms, template_file, app_type, creator, region, cloned_from):
                self.log_change('Create complete, looking for post-clone SQL')
                if self.run_sql():
                    self.log_change('SQL complete, restarting {self.stack_name}')
                    self.full_restart()
                else:
                    self.clear_current_action()
            else:
                self.log_msg(log.INFO, 'Clone complete - failed')
                self.log_change('Clone complete - failed')
                self.clear_current_action()
                return False
        else:
            self.clear_current_action()
        self.log_msg(log.INFO, 'Clone complete')
        self.log_change('Clone complete')
        return True

    def update(self, stack_parms, template_file):
        self.log_msg(log.INFO, f"Updating stack with params: {str([param for param in stack_parms if 'UsePreviousValue' not in param])}")
        self.log_change(f"Changeset is: {str([param for param in stack_parms if 'UsePreviousValue' not in param])}")
        template_filename = template_file.name
        template= str(template_file)
        self.upload_template(template, template_filename)
        cfn = boto3.client('cloudformation', region_name=self.region)
        config = configparser.ConfigParser()
        config.read('forge.properties')
        s3_bucket = config['s3']['bucket']
        try:
            cfn.update_stack(
                StackName=self.stack_name,
                Parameters=stack_parms,
                TemplateURL=f'https://s3.amazonaws.com/{s3_bucket}/forge-templates/{template_filename}',
                Capabilities=['CAPABILITY_IAM']
            )
        except Exception as e:
            print(e.args[0])
            self.log_msg(log.ERROR, f'An error occurred updating stack: {e.args[0]}')
            self.log_msg(log.INFO, 'Update complete - failed')
            self.log_change('Update complete - failed')
            return False
        self.getLburl()
        if not self.wait_stack_action_complete('UPDATE_IN_PROGRESS'):
            self.log_msg(log.INFO, 'Update complete - failed')
            self.log_change('Update complete - failed')
            return False
        if 'ParameterValue' in [param for param in stack_parms if param['ParameterKey'] == 'ClusterNodeMax'][0] and \
                int([param['ParameterValue'][0] for param in stack_parms if param['ParameterKey'] == 'ClusterNodeMax'][0]) > 0:
            self.log_msg(log.INFO, 'Waiting for stack to respond')
            self.validate_service_responding()
        self.log_msg(log.INFO, 'Update complete')
        self.log_change('Update successful')
        return True

    #  TODO create like
    # def create_like(self, like_stack, changeparms):
    #     # grab stack parms from like stack
    #     # changedParms = param list with changed parms
    #     create(parms=changedParms)

    def create(self, stack_parms, template_file, app_type, creator, region, cloned_from=False):
        self.log_msg(log.INFO, f'Creating stack: {self.stack_name}')
        self.log_msg(log.INFO, f'Creation params: {stack_parms}')
        self.log_change(f'Creating stack {self.stack_name} with parameters: {stack_parms}')
        template = str(template_file)
        self.log_change(f'Template is {template}')
        # create tags
        tags = [{
            'Key': 'product',
            'Value': app_type
        },{
            'Key': 'environment',
            'Value': next(parm['ParameterValue'] for parm in stack_parms if parm['ParameterKey'] == 'DeployEnvironment')
        },{
            'Key': 'created_by',
            'Value': creator
        }]
        if cloned_from:
            tags.append({'Key': 'cloned_from',
                        'Value': cloned_from})
        try:
            self.upload_template(template, template_file.name)
            cfn = boto3.client('cloudformation', region_name=region)
            config = configparser.ConfigParser()
            config.read('forge.properties')
            s3_bucket = config['s3']['bucket']
            # wait for the template to upload to avoid race conditions
            time.sleep(5)
            # TODO spin up to one node first, then spin up remaining nodes
            created_stack = cfn.create_stack(
                StackName=self.stack_name,
                Parameters=stack_parms,
                TemplateURL=f'https://s3.amazonaws.com/{s3_bucket}/forge-templates/{template_file.name}',
                Capabilities=['CAPABILITY_IAM'],
                Tags=tags
            )
        except Exception as e:
            print(e.args[0])
            self.log_msg(log.WARN, f'Error occurred creating stack: {e.args[0]}')
            self.log_msg(log.INFO, 'Create complete - failed')
            self.log_change('Create complete - failed')
            return False
        self.log_msg(log.INFO, f'Create has begun: {created_stack}')
        if not self.wait_stack_action_complete('CREATE_IN_PROGRESS'):
            self.log_msg(log.INFO, 'Create complete - failed')
            self.log_change('Create complete - failed')
            return False
        self.log_msg(log.INFO, f'Stack {self.stack_name} created, waiting on service responding')
        self.validate_service_responding()
        self.log_msg(log.INFO, 'Create complete')
        self.log_change('Create complete')
        return True

    def rolling_restart(self):
        self.log_msg(log.INFO, f'Beginning Rolling Restart for {self.stack_name}')
        self.log_change(f'Beginning Rolling Restart for {self.stack_name}')
        app_type = self.get_tag('product')
        if not app_type:
            self.log_msg(log.ERROR, 'Rolling restart complete - failed')
            return False
        self.get_stacknodes()
        instance_list = self.instancelist
        self.log_msg(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        # determine if the nodes are running or not
        running_nodes = []
        non_running_nodes = []
        for node in instance_list:
            node_ip = list(node.values())[0]
            if self.check_node_status(node_ip, False).lower() == 'running':
                running_nodes.append(node)
            else:
                non_running_nodes.append(node)
        # restart non running nodes first
        for instance in itertools.chain(non_running_nodes, running_nodes):
            if self.shutdown_app([instance], app_type):
                node_ip = list(instance.values())[0]
                if self.startup_app([instance], app_type):
                    result = ""
                    while result not in ['RUNNING', 'FIRST_RUN']:
                        result = self.check_node_status(node_ip, False)
                        time.sleep(10)
                    self.log_msg(log.INFO, f'Startup result for {node_ip}: {result}')
                else:
                    self.log_msg(log.INFO, f'Failed to start application on instance {instance}')
                    self.log_msg(log.ERROR, 'Rolling restart complete - failed')
                    self.log_change('Rolling restart complete - failed')
                    return False
            else:
                self.log_msg(log.INFO, f'Failed to stop application on instance {instance}')
                self.log_msg(log.ERROR, 'Rolling restart complete - failed')
                self.log_change('Rolling restart complete - failed')
                return False
        self.log_msg(log.INFO, 'Rolling restart complete')
        self.log_change('Rolling restart complete')
        return True

    def full_restart(self):
        self.log_msg(log.INFO, f'Beginning Full Restart for {self.stack_name}')
        self.log_change(f'Beginning Full Restart for {self.stack_name}')
        app_type = self.get_tag('product')
        if not app_type:
            self.log_msg(log.ERROR, 'Full restart complete - failed')
            self.log_change('Full restart complete - failed')
            return False
        self.get_stacknodes()
        self.log_msg(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        if self.shutdown_app(self.instancelist, app_type):
            for instance in self.instancelist:
                self.startup_app([instance], app_type)
            self.log_msg(log.INFO, 'Full restart complete')
            self.log_change('Full restart complete')
        else:
            self.log_msg(log.ERROR, 'Full restart complete - failed')
            self.log_change('Full restart complete - failed')
            return False
        return True

    def rolling_rebuild(self):
        self.log_msg(log.INFO, 'Rolling rebuild has begun')
        self.log_change('Rolling rebuild has begun')
        ec2 = boto3.client('ec2', region_name=self.region)
        self.get_stacknodes()
        old_nodes = self.instancelist
        self.log_msg(log.INFO, f'Old nodes: {old_nodes}')
        self.log_change(f'Old nodes: {old_nodes}')
        new_nodes = []
        try:
            for node in old_nodes:
                # destroy each node and wait for another to be created to replace it
                self.log_msg(log.INFO, f'Replacing node {node}')
                self.log_change(f'Replacing node {node}')
                ec2.terminate_instances(InstanceIds=[list(node.keys())[0]])
                time.sleep(30)
                self.get_stacknodes()
                current_instances = self.instancelist
                waiting_for_new_node = True
                replacement_node = {}
                while waiting_for_new_node:
                    for instance in current_instances:
                        if instance not in old_nodes:
                            # if the instance is new, track it
                            replacement_node = instance
                            self.log_msg(log.INFO, f'New node: {replacement_node}')
                            self.log_change(f'New node: {replacement_node}')
                            new_nodes.append(replacement_node)
                            waiting_for_new_node = False
                    time.sleep(30)
                    self.get_stacknodes()
                    current_instances = self.instancelist
                # wait for the new node to come up
                result = ''
                while result not in ['RUNNING', 'FIRST_RUN']:
                    node_ip = list(replacement_node.values())[0]
                    result = self.check_node_status(node_ip)
                    self.log_msg(log.INFO, f'Startup result for {node_ip}: {result}')
                    time.sleep(30)
            self.log_msg(log.INFO, 'Rolling rebuild complete')
            self.log_change(f'Rolling rebuild complete, new nodes are: {new_nodes}')
            return True
        except Exception as e:
            print(e.args[0])
            self.log_msg(log.ERROR, f'An error occurred during rolling rebuild: {e.args[0]}')
            self.log_change(f'An error occurred during rolling rebuild: {e.args[0]}')
            return False

    def thread_dump(self, alsoHeaps=False):
        heaps_to_come_log_line = ''
        if alsoHeaps == 'true':
            heaps_to_come_log_line = ', heap dumps to follow'
        self.log_msg(log.INFO, f'Beginning thread dumps on {self.stack_name}{heaps_to_come_log_line}')
        self.get_stacknodes()
        self.log_msg(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        self.run_command(self.instancelist, '/usr/local/bin/j2ee_thread_dump')
        self.log_msg(log.INFO, 'Successful thread dumps can be downloaded from the main Diagnostics page')
        self.log_msg(log.INFO, 'Thread dumps complete')
        return True

    def heap_dump(self):
        self.log_msg(log.INFO, f'Beginning heap dumps on {self.stack_name}')
        self.get_stacknodes()
        self.log_msg(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        # Wait for each heap dump to finish before starting the next, to avoid downtime
        for instance in self.instancelist:
            self.ssm_send_and_wait_response(list(instance.keys())[0], '/usr/local/bin/j2ee_heap_dump_live')
            time.sleep(30) # give node time to recover and rejoin cluster
        self.log_msg(log.INFO, "Heap dumps complete")
        return True

    def run_sql(self):
        self.log_msg(log.INFO, 'Running post clone SQL')
        self.log_change('Running post clone SQL')
        self.get_stacknodes()
        sql_to_run = self.get_sql()
        if sql_to_run != 'No SQL script exists for this stack':
            sql_as_escaped_string = re.sub(r'([\"\$])', r'\\\1', sql_to_run)
            if self.run_command([self.instancelist[0]], f'echo "{sql_as_escaped_string}" > /usr/local/bin/{self.stack_name}.post-clone.sql') :
                db_conx_string = 'PGPASSWORD=${ATL_DB_PASSWORD} /usr/bin/psql -h ${ATL_DB_HOST} -p ${ATL_DB_PORT} -U postgres -w ${ATL_DB_NAME}'
                if not self.run_command([self.instancelist[0]], f'source /etc/atl; {db_conx_string} -a -f /usr/local/bin/{self.stack_name}.post-clone.sql'):
                    self.log_msg(log.ERROR, f'Running SQL script failed')
                    return False
            else:
                self.log_msg(log.ERROR, 'Dumping SQL file to target machine failed')
                self.log_change('Dumping SQL file to target machine failed')
                return False
        else:
            self.log_msg(log.INFO, 'No post clone SQL file found')
            self.log_change('No post clone SQL file found')
            return False
        self.log_msg(log.INFO, 'Run SQL complete')
        self.log_change('Run SQL complete')
        return True

    def tag(self, tags):
        self.log_msg(log.INFO, 'Tagging stack')
        self.log_change('Tagging stack')
        params = self.get_parms_for_update()
        self.log_change(f'Parameters for update: {params}')
        try:
            cfn = boto3.client('cloudformation', region_name=self.region)
            cfn.update_stack(
                StackName=self.stack_name,
                Parameters=params,
                UsePreviousTemplate=True,
                Tags=tags,
                Capabilities=['CAPABILITY_IAM']
            )
            self.log_msg(log.INFO, f'Tagging successfully initiated')
        except Exception as e:
            print(e.args[0])
            self.log_msg(log.ERROR, f'An error occurred tagging stack: {e.args[0]}')
            self.log_change(f'An error occurred tagging stack: {e.args[0]}')
            return False
        if self.wait_stack_action_complete('UPDATE_IN_PROGRESS'):
            self.log_msg(log.INFO, 'Tag complete')
            self.log_change('Tag complete')
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

    def log_msg(self, level, message):
        logline = f'{datetime.now()} {level} {message} \n'
        print(logline)
        logfile = open(self.logfile, 'a')
        logfile.write(logline)
        logfile.close()

    def create_change_log(self, action):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f'stacks/{self.stack_name}/logs/{self.stack_name}_{timestamp}_{action}.change.log'
        open(filename, 'w').close()
        self.changelogfile = filename

    def log_change(self, message):
        logline = f'{datetime.now()} {message} \n'
        print(logline)
        logfile = open(self.changelogfile, 'a')
        logfile.write(logline)
        logfile.close()

    def save_change_log(self):
        if self.changelogfile:
            changelog = os.path.relpath(self.changelogfile)
            changelog_filename = os.path.basename(self.changelogfile)
            config = configparser.ConfigParser()
            config.read('forge.properties')
            s3_bucket = config['s3']['bucket']
            s3 = boto3.resource('s3', region_name=self.region)
            s3.meta.client.upload_file(changelog, s3_bucket, f'changelogs/{self.stack_name}/{changelog_filename}')