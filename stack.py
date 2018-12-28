from stackstate import Stackstate
import boto3
import botocore
import time
import requests
import json
from pprint import pprint
from pathlib import Path
import log
import os
import shutil
import configparser
from datetime import datetime


class Stack:
    """An object describing an instance of an aws cloudformation stack:

    Attributes:
        stackstate: A dict of dicts containing all state information.
        stack_name: The name of the stack we are keeping state for
    """

    def __init__(self, stack_name, region, app_type=None):
        self.state = Stackstate(stack_name)
        self.stack_name = stack_name
        if region == '':
            error_string = 'No region defined for stack - your session may have timed out. Go back and retry the operation.'
            print(f'{datetime.now()} {log.ERROR} {error_string}')
            raise ValueError(error_string)
        self.region = region
        self.state.update('region', self.region)
            # try:
            #     cfn = boto3.client('cloudformation', region_name=self.region)
            #     stack_details = cfn.describe_stacks(StackName=self.stack_name)
            #     if len(stack_details['Stacks'][0]['Tags']) > 0:
            #         product_tag = next((tag for tag in stack_details['Stacks'][0]['Tags'] if tag['Key'] == 'product'), None)
            #         if product_tag:
            #             self.app_type = product_tag['Value']
            #             self.log_msg(log.INFO, f'{self.stack_name} is a {self.app_type}')
            #         env_tag = next((tag for tag in stack_details['Stacks'][0]['Tags'] if tag['Key'] == 'environment'), None)
            #         if env_tag:
            #             self.state.update('environment', env_tag['Value'])
            # except Exception as e:
            #     print(e.args[0])
            #     self.log_msg(log.WARN, f'An error occurred getting stack details from AWS (stack may not exist yet): {e.args[0]}')


## Stack - micro function methods
    def debug_stackstate(self):
        self.state.load_state()
        pprint(self.state.stackstate)
        return

    def getLburl(self, stack_details):
        if 'lburl' in self.state.stackstate:
            return self.state.stackstate['lburl'].replace("https", "http")
        else:
            rawlburl = [p['OutputValue'] for p in stack_details['Stacks'][0]['Outputs'] if
                        p['OutputKey'] == 'LoadBalancerURL'][0] + \
                        next(parm for parm in stack_details['Stacks'][0]['Parameters'] if parm['ParameterKey'] == 'TomcatContextPath')['ParameterValue']
            return rawlburl.replace("https", "http")

    def getparms(self):
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack_details = cfn.describe_stacks(StackName=self.stack_name)
            self.state.update('stack_parms', stack_details['Stacks'][0]['Parameters'])
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return False
        return stack_details['Stacks'][0]['Parameters']

    def getparamvalue(self, param_to_get):
        params = self.getparms()
        for param in params:
            if param['ParameterKey'].lower() == param_to_get.lower():
                return param['ParameterValue']
        return ''

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

    def get_current_state(self, like_stack=None, like_region=None):
        self.log_msg(log.INFO, f'Getting pre-upgrade stack state for {self.stack_name}')
        # use the "like" stack and parms in preference to self
        query_stack = like_stack if like_stack else self.stack_name
        query_region = like_region if like_region else self.region
        cfn = boto3.client('cloudformation', region_name=query_region)
        try:
            stack_details = cfn.describe_stacks(StackName=query_stack)
            template = cfn.get_template(StackName=query_stack)
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return
        # get tags
        if len(stack_details['Stacks'][0]['Tags']) > 0:
            product_tag = next((tag for tag in stack_details['Stacks'][0]['Tags'] if tag['Key'] == 'product'), None)
            if product_tag:
                app_type = product_tag['Value']
                self.log_msg(log.INFO, f"{self.stack_name} is a {app_type}")
            else:
                self.log_msg(log.ERROR, f'Stack {self.stack_name} is not tagged with product')
                return False
            env_tag = next((tag for tag in stack_details['Stacks'][0]['Tags'] if tag['Key'] == 'environment'), None)
            if env_tag:
                self.state.update('environment', env_tag['Value'])
            else:
                self.log_msg(log.ERROR, f'Stack {self.stack_name} is not tagged with environment')
                return False
        else:
            self.log_msg(log.ERROR, f'Stack {self.stack_name} is not tagged')
            return False
        # store the template
        self.state.update('TemplateBody', template['TemplateBody'])
        # store the most recent parms (list of dicts)
        self.state.update('stack_parms', stack_details['Stacks'][0]['Parameters'])
        self.state.update('appnodemax', [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                                        p['ParameterKey'] == 'ClusterNodeMax'][0])
        self.state.update('appnodemin', [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                                                p['ParameterKey'] == 'ClusterNodeMin'][0])
        self.state.update('tomcatcontextpath',
        [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
         p['ParameterKey'] == 'TomcatContextPath'][0] )
        # force lburl to always be http as we offoad SSL at the VTM before traffic hits ELB/ALB
        self.state.update('lburl', self.getLburl(stack_details))
        # all the following parms are dependent on stack type and will fail list index out of range when not matching so wrap in try by apptype
        # versions in different parms relative to products - we should probably abstract the product
        # connie
        if app_type.lower() == 'confluence':
            self.state.update('preupgrade_confluence_version',
                [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                 p['ParameterKey'] == 'ConfluenceVersion'][0])
            # synchrony only exists for connie
            self.state.update('syncnodemax',
                [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                 p['ParameterKey'] == 'SynchronyClusterNodeMax'][0])
            self.state.update('syncnodemin',
                [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                 p['ParameterKey'] == 'SynchronyClusterNodeMin'][0])
        # jira
        elif app_type.lower() == 'jira':
            self.state.update('preupgrade_jira_version',
                [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                 p['ParameterKey'] == 'JiraVersion'][0])
        # crowd
        elif app_type.lower() == 'crowd':
            self.state.update('preupgrade_crowd_version',
                [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                 p['ParameterKey'] == 'CrowdVersion'][0])
        self.log_msg(log.INFO, f'Finished getting stack_state for {self.stack_name}')
        return True

    def spindown_to_zero_appnodes(self, app_type):
        self.log_msg(log.INFO, f'Spinning {self.stack_name} stack down to 0 nodes')
        cfn = boto3.client('cloudformation', region_name=self.region)
        spindown_parms = self.getparms()
        spindown_parms = self.update_parmlist(spindown_parms, 'ClusterNodeMax', '0')
        spindown_parms = self.update_parmlist(spindown_parms, 'ClusterNodeMin', '0')
        if app_type == 'confluence':
            spindown_parms = self.update_parmlist(spindown_parms, 'SynchronyClusterNodeMax', '0')
            spindown_parms = self.update_parmlist(spindown_parms, 'SynchronyClusterNodeMin', '0')
        self.log_msg(log.INFO, f'Spindown params: {spindown_parms}')
        try:
            update_stack = cfn.update_stack(
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
        self.log_msg(log.INFO, str(update_stack))
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

    def spinup_to_one_appnode(self, app_type):
        self.log_msg(log.INFO, "Spinning stack up to one appnode")
        # for connie 1 app node and 1 synchrony
        cfn = boto3.client('cloudformation', region_name=self.region)
        spinup_parms = self.state.stackstate['stack_parms']
        spinup_parms = self.update_parmlist(spinup_parms, 'ClusterNodeMax', '1')
        spinup_parms = self.update_parmlist(spinup_parms, 'ClusterNodeMin', '1')
        if app_type == 'jira':
            spinup_parms = self.update_parmlist(spinup_parms, 'JiraVersion', self.state.stackstate['new_version'])
        elif app_type == 'confluence':
            spinup_parms = self.update_parmlist(spinup_parms, 'ConfluenceVersion', self.state.stackstate['new_version'])
            spinup_parms = self.update_parmlist(spinup_parms, 'SynchronyClusterNodeMax', '1')
            spinup_parms = self.update_parmlist(spinup_parms, 'SynchronyClusterNodeMin', '1')
        elif app_type == 'crowd':
            spinup_parms = self.update_parmlist(spinup_parms, 'CrowdVersion', self.state.stackstate['new_version'])
        self.log_msg(log.INFO, f'Spinup params: {spinup_parms}')
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
        if not self.wait_stack_action_complete("UPDATE_IN_PROGRESS"):
            return False
        self.log_msg(log.INFO, "Spun up to 1 node, waiting for service to respond")
        self.validate_service_responding()
        self.log_msg(log.INFO, f'Updated stack: {update_stack}')
        return True

    def validate_service_responding(self):
        self.log_msg(log.INFO, "Waiting for service to reply on /status")
        service_state = self.check_service_status()
        while service_state  not in ['RUNNING', 'FIRST_RUN']:
            time.sleep(60)
            service_state = self.check_service_status()
        self.log_msg(log.INFO, f' {self.stack_name} /status now reporting {service_state}')
        return

    def check_service_status(self, logMsgs=True):
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack_details = cfn.describe_stacks(StackName=self.stack_name)
        except Exception as e:
            print(e.args[0])
            return f'Error checking service status: {e.args[0]}'
        self.state.update('lburl', self.getLburl(stack_details))
        if logMsgs:
            self.log_msg(log.INFO,
                        f' ==> checking service status at {self.state.stackstate["lburl"]}/status')
        try:
            service_status = requests.get(self.state.stackstate['lburl'] + '/status', timeout=5)
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
        return "Timed Out"

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
            print('type is:', e.__class__.__name__)
        return "Timed Out"

    def spinup_remaining_nodes(self, app_type):
        self.log_msg(log.INFO, 'Spinning up any remaining nodes in stack')
        cfn = boto3.client('cloudformation', region_name=self.region)
        spinup_parms = self.state.stackstate['stack_parms']
        spinup_parms = self.update_parmlist(spinup_parms, 'ClusterNodeMax', self.state.stackstate['appnodemax'])
        spinup_parms = self.update_parmlist(spinup_parms, 'ClusterNodeMin', self.state.stackstate['appnodemin'])
        if app_type == 'jira':
            spinup_parms = self.update_parmlist(spinup_parms, 'JiraVersion', self.state.stackstate['new_version'])
        if app_type == 'crowd':
            spinup_parms = self.update_parmlist(spinup_parms, 'CrowdVersion', self.state.stackstate['new_version'])
        if app_type == 'confluence':
            spinup_parms = self.update_parmlist(spinup_parms, 'ConfluenceVersion', self.state.stackstate['new_version'])
            spinup_parms = self.update_parmlist(spinup_parms, 'SynchronyClusterNodeMax', self.state.stackstate['syncnodemax'])
            spinup_parms = self.update_parmlist(spinup_parms, 'SynchronyClusterNodeMin', self.state.stackstate['syncnodemin'])
        self.log_msg(log.INFO, f'Spinup params: {spinup_parms}')
        try:
            update_stack = cfn.update_stack(
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
            cmd = f'/etc/init.d/{app_type} stop'
            cmd_id_list.append(self.ssm_send_command(instance, cmd))
        for cmd_id in cmd_id_list:
            result = self.wait_for_cmd_result(cmd_id)
            if result == 'Failed':
                self.log_msg(log.ERROR, f'Shutdown result for {cmd_id}: {result}')
            else:
                self.log_msg(log.INFO, f'Shutdown result for {cmd_id}: {result}')
        return True

    def startup_app(self, instancelist, app_type):
        for instancedict in instancelist:
            instance = list(instancedict.keys())[0]
            node_ip = list(instancedict.values())[0]
            self.log_msg(log.INFO, f'Starting up {instance} ({node_ip})')
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

    def store_current_action(self, action, locking_enabled):
        action_already_in_progress = self.get_stack_action_in_progress()
        if not action_already_in_progress:
            os.mkdir(f'locks/{self.stack_name}')
            os.mkdir(f'locks/{self.stack_name}/{action}')
        elif locking_enabled:
            self.log_msg(log.ERROR, f'Cannot begin action: {action}. Another action is in progress: {action_already_in_progress}')
            return False
        self.create_action_log(action)
        return True

    def clear_current_action(self):
        self.archive_action_log()
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
            self.log_msg(log.ERROR, f'Error checking node status: {e.args[0]}')
            print(f'Error checking node status: {e.args[0]}')
            return [{'error': e.args[0]}]
        tags = stack['Stacks'][0]['Tags']
        return tags


## Stack - Major Action Methods

    def upgrade(self, new_version):
        self.log_msg(log.INFO, f'Beginning upgrade for {self.stack_name}')
        self.state.update('new_version', new_version)
        # TODO block traffic at vtm
        # get pre-upgrade state information
        if not self.get_current_state():
            self.log_msg(log.ERROR, 'Upgrade complete - failed')
            return False
        # get product
        app_type = self.get_product()
        if not app_type:
            self.log_msg(log.ERROR, 'Upgrade complete - failed')
            return False
        # spin stack down to 0 nodes
        if not self.spindown_to_zero_appnodes(app_type):
            self.log_msg(log.INFO, 'Upgrade complete - failed')
            return False
        # TODO change template if required
        # spin stack up to 1 node on new release version
        if not self.spinup_to_one_appnode(app_type):
            self.log_msg(log.INFO, 'Upgrade complete - failed')
            return False
        # spinup remaining appnodes in stack if needed
        if self.state.stackstate['appnodemin'] != "1":
            self.spinup_remaining_nodes(app_type)
        elif 'syncnodemin' in self.state.stackstate.keys() and self.state.stackstate[
            'syncnodemin'] != "1":
            self.spinup_remaining_nodes(app_type)
        # TODO wait for remaining nodes to respond ??? ## maybe a LB check for active node count
        # TODO enable traffic at VTM
        self.log_msg(log.INFO, f'Upgrade successful for {self.stack_name} at {self.region} to version {new_version}')
        self.log_msg(log.INFO, "Upgrade complete")
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
                return True
        stack_id = stack_state['Stacks'][0]['StackId']
        cfn.delete_stack(StackName=self.stack_name)
        if self.wait_stack_action_complete("DELETE_IN_PROGRESS", stack_id):
            self.log_msg(log.INFO, f'Destroy successful for stack {self.stack_name}')
        self.log_msg(log.INFO, "Destroy complete")
        return True

    def clone(self, stack_parms, template_file, app_type, instance_type, region, creator):
        self.log_msg(log.INFO, 'Initiating clone')
        self.state.update('stack_parms', stack_parms)
        self.state.update('app_type', app_type)
        self.state.update('region', region)
        self.region = region
        deploy_type = 'Clone'
        # TODO popup confirming if you want to destroy existing
        if self.destroy():
            if self.create(parms=stack_parms, template_file=template_file, app_type=app_type, creator=creator, region=region):
                if self.run_post_clone_sql():
                    self.full_restart()
                else:
                    self.clear_current_action()
            else:
                self.clear_current_action()
        else:
            self.clear_current_action()
        self.log_msg(log.INFO, "Clone complete")
        return True

    def update(self, stack_parms, template_file):
        self.log_msg(log.INFO, 'Updating stack with params: ' + str([param for param in stack_parms if 'UsePreviousValue' not in param]))
        template_filename = template_file.name
        template= str(template_file)
        self.upload_template(template, template_filename)
        cfn = boto3.client('cloudformation', region_name=self.region)
        config = configparser.ConfigParser()
        config.read('forge.properties')
        s3_bucket = config['s3']['bucket']
        try:
            updated_stack = cfn.update_stack(
                StackName=self.stack_name,
                Parameters=stack_parms,
                TemplateURL=f'https://s3.amazonaws.com/{s3_bucket}/forge-templates/{template_filename}',
                Capabilities=['CAPABILITY_IAM']
            )
            stack_details = cfn.describe_stacks(StackName=self.stack_name)
        except Exception as e:
            print(e.args[0])
            self.log_msg(log.ERROR, f'An error occurred updating stack: {e.args[0]}')
            self.log_msg(log.INFO, "Update complete - failed")
            return False
        self.state.update('lburl', self.getLburl(stack_details))
        self.log_msg(log.INFO, f'Stack {self.stack_name} is being updated: {updated_stack}')
        if not self.wait_stack_action_complete("UPDATE_IN_PROGRESS"):
            self.log_msg(log.INFO, "Update complete - failed")
            return False
        if 'ParameterValue' in [param for param in stack_parms if param['ParameterKey'] == 'ClusterNodeMax'][0] and \
                int([param['ParameterValue'][0] for param in stack_parms if param['ParameterKey'] == 'ClusterNodeMax'][0]) > 0:
            self.log_msg(log.INFO, 'Waiting for stack to respond')
            self.validate_service_responding()
        self.log_msg(log.INFO, "Update complete")
        return True

    #  TODO create like
    # def create_like(self, like_stack, changeparms):
    #     # grab stack parms from like stack
    #     # changedParms = param list with changed parms
    #     create(parms=changedParms)

    def create(self, parms, template_file, app_type, creator, region, like_stack=None):
        if like_stack:
            self.get_current_state(like_stack, region)
            stack_parms = self.state.stackstate['stack_parms']
            self.log_msg(log.INFO, f'Creating stack: {self.stack_name}, like source stack {like_stack}')
        elif parms:
            stack_parms = parms
            self.log_msg(log.INFO, f'Creating stack: {self.stack_name}')
        self.log_msg(log.INFO, f'Creation params: {stack_parms}')
        template = str(template_file)
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
                Tags=[{
                        'Key': 'product',
                        'Value': app_type
                    },{
                        'Key': 'environment',
                        'Value': next(parm['ParameterValue'] for parm in parms if parm['ParameterKey'] == 'DeployEnvironment')
                    },{
                        'Key': 'created_by',
                        'Value': creator
                    }]
            )
            time.sleep(5)
            stack_details = cfn.describe_stacks(StackName=self.stack_name)
        except Exception as e:
            print(e.args[0])
            self.log_msg(log.WARN, f'Error occurred creating stack: {e.args[0]}')
            self.log_msg(log.INFO, "Create complete - failed")
            return False
        self.log_msg(log.INFO, f'Create has begun: {created_stack}')
        if not self.wait_stack_action_complete("CREATE_IN_PROGRESS"):
            self.log_msg(log.INFO, "Create complete - failed")
            return False
        self.log_msg(log.INFO, f'Stack {self.stack_name} created, waiting on service responding')
        self.validate_service_responding()
        self.log_msg(log.INFO, "Create complete")
        return True

    def rolling_restart(self):
        self.log_msg(log.INFO, f'Beginning Rolling Restart for {self.stack_name}')
        app_type = self.get_product()
        if not app_type:
            self.log_msg(log.ERROR, 'Rolling restart complete - failed')
            return False
        self.get_stacknodes()
        self.log_msg(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        for instance in self.instancelist:
            if self.shutdown_app([instance], app_type):
                node_ip = list(instance.values())[0]
                self.log_msg(log.INFO, f'Starting application on instance {instance} for {self.stack_name}')
                if self.startup_app([instance], app_type):
                    self.log_msg(log.INFO, f'Application started on instance {instance}')
                    result = ""
                    while result not in ['RUNNING', 'FIRST_RUN']:
                        result = self.check_node_status(node_ip, False)
                        time.sleep(10)
                    self.log_msg(log.INFO, f'Startup result for {node_ip}: {result}')
                else:
                    self.log_msg(log.INFO, f'Failed to start application on instance {instance}')
                    self.log_msg(log.ERROR, "Rolling restart complete - failed")
                    return False
            else:
                self.log_msg(log.INFO, f'Failed to stop application on instance {instance}')
                self.log_msg(log.ERROR, "Rolling restart complete - failed")
                return False
        self.log_msg(log.INFO, "Rolling restart complete")
        return True

    def full_restart(self):
        self.log_msg(log.INFO, f'Beginning Full Restart for {self.stack_name}')
        app_type = self.get_product()
        if not app_type:
            self.log_msg(log.ERROR, 'Full restart complete - failed')
            return False
        self.get_stacknodes()
        self.log_msg(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        if self.shutdown_app(self.instancelist, app_type):
            for instance in self.instancelist:
                self.log_msg(log.INFO, f'starting application on {instance} for {self.stack_name}')
                startup = self.startup_app([instance], app_type)
            self.log_msg(log.INFO, "Full restart complete")
        else:
            self.log_msg(log.INFO, "Full restart complete - failed")
            return False
        return True

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

    def run_post_clone_sql(self):
        self.log_msg(log.INFO, f'Running post clone SQL')
        self.get_stacknodes()
        sqlfile = Path(f'stacks/{self.stack_name}/{self.stack_name}.post-clone.sql')
        if sqlfile.is_file():
            with open(sqlfile, 'r') as outfile:
                if self.run_command([self.instancelist[0]], f'echo "{outfile.read()}" > /usr/local/bin/{self.stack_name}.post-clone.sql') :
                    db_conx_string = 'PGPASSWORD=${ATL_DB_PASSWORD} /usr/bin/psql -h ${ATL_DB_HOST} -p ${ATL_DB_PORT} -U postgres -w ${ATL_DB_NAME}'
                    if not self.run_command([self.instancelist[0]], f'source /etc/atl; {db_conx_string} -a -f /usr/local/bin/{self.stack_name}.post-clone.sql'):
                        self.log_msg(log.ERROR, f'Running SQL script failed')
                        return False
                else:
                    self.log_msg(log.ERROR, f'Dumping SQL file to target machine failed')
                    return False
        else:
            self.log_msg(log.INFO, f'No post clone SQL file found')
            return False
        self.log_msg(log.INFO, f'Run SQL complete')
        return True

    def tag(self, tags):
        self.log_msg(log.INFO, f'Tagging stack')
        product = next((tag for tag in tags if tag['Key'] == 'product'), None)
        environment = next((tag for tag in tags if tag['Key'] == 'environment'), None)
        if 'environment':
            self.state.update('environment', environment['Value'])
        params = self.get_parms_for_update()
        try:
            cfn = boto3.client('cloudformation', region_name=self.region)
            outcome = cfn.update_stack(
                StackName=self.stack_name,
                Parameters=params,
                UsePreviousTemplate=True,
                Tags=tags,
                Capabilities=['CAPABILITY_IAM']
            )
            self.log_msg(log.INFO, f'Tagging successfully initiated: {outcome}')
        except Exception as e:
            print(e.args[0])
            self.log_msg(log.ERROR, f'An error occurred tagging stack: {e.args[0]}')
        if self.wait_stack_action_complete("UPDATE_IN_PROGRESS"):
            self.log_msg(log.INFO, f'Tag complete')
            return True
        return False

    def get_product(self):
        try:
            cfn = boto3.client('cloudformation', region_name=self.region)
            stack_details = cfn.describe_stacks(StackName=self.stack_name)
            if len(stack_details['Stacks'][0]['Tags']) > 0:
                product_tag = next((tag for tag in stack_details['Stacks'][0]['Tags'] if tag['Key'] == 'product'), None)
                if product_tag:
                    app_type = product_tag['Value']
                    self.log_msg(log.INFO, f'{self.stack_name} is a {app_type}')
                    return app_type.lower()
            self.log_msg(log.WARN, f'Stack is not tagged with product')
            return False
        except Exception as e:
            print(e.args[0])
            self.log_msg(log.WARN, f'An error occurred getting stack product tag: {e.args[0]}')
            return False

    # Logging functions
    def create_action_log(self, action):
        # create a datestamped file for the action
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f'stacks/{self.stack_name}/{self.stack_name}_{timestamp}_{action}-current.log'
        open(filename, 'w').close()
        self.state.update('logfile', filename)

    def log_msg(self, level, message):
        logline = f'{datetime.now()} {level} {message} \n'
        print(logline)
        logfile = open(self.state.stackstate['logfile'], 'a')
        logfile.write(logline)
        logfile.close()

    def archive_action_log(self):
        os.rename(self.state.stackstate['logfile'], self.state.stackstate['logfile'].replace('-current', ''))