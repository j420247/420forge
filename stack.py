from forgestate import Forgestate
import boto3
import botocore
import time
import requests
import json
import sys
from pprint import pprint
from pathlib import Path
import log
import os

class Stack:
    """An object describing an instance of an aws cloudformation stack:

    Attributes:
        forgestate: A dict of dicts containing all state information.
        stack_name: The name of the stack we are keeping state for
    """

    def __init__(self, stack_name, env, app_type=None):
        self.state = Forgestate(stack_name)
        self.state.logaction(log.INFO, f'Initialising stack object for {stack_name}')
        self.stack_name = stack_name
        self.env = env
        self.region = self.setRegion(env)
        if app_type:
            self.app_type = app_type
        else:
            try:
                cfn = boto3.client('cloudformation', region_name=self.region)
                stack_details = cfn.describe_stacks(StackName=self.stack_name)
                if len([p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'JiraVersion']) == 1:
                    self.app_type = "jira"
                elif len([p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'ConfluenceVersion']) == 1:
                    self.app_type = "confluence"
                self.state.logaction(log.INFO, f'{stack_name} is a {self.app_type}')
            except Exception as e:
                print(e.args[0])
                self.state.logaction(log.WARN, f'An error occurred getting stack details from AWS (stack may not exist yet): {e.args[0]}')
        self.state.update('environment', env)
        self.state.update('region', self.region)


## Stack - micro function methods
    def debug_forgestate(self):
        self.state.load_state()
        pprint(self.state.forgestate)
        return

    def setRegion(self, env):
        if env == 'prod':
            return 'us-west-2'
        else:
            return 'us-east-1'

    def getLburl(self, stack_details):
        rawlburl = [p['OutputValue'] for p in stack_details['Stacks'][0]['Outputs'] if
                    p['OutputKey'] == 'LoadBalancerURL'][0] + self.getparamvalue('tomcatcontextpath')
        return rawlburl.replace("https", "http")

    def writeparms(self, parms):
        with open(f'stacks/{self.stack_name}/{self.stack_name}.parms.json', 'w') as outfile:
            json.dump(parms, outfile)
        outfile.close()
        return (self)

    def readparms(self):
        try:
            with open(f'stacks/{self.stack_name}/{self.stack_name}.parms.json', 'r') as infile:
                parms = json.load(infile)
                return parms
        except FileNotFoundError:
            self.state.logaction(log.ERROR, f'can not load parms, stacks/{self.stack_name}/{self.stack_name}.parms.json does not exist')
            sys.exit() # do we really want to stop Forge at this point? If so, remove the 'return' because it's unreachable.
            return

    def getparamvalue(self, param_to_get):
        params = self.readparms()
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
                if self.state.forgestate['action'] == 'upgrade' and (v == 'DBMasterUserPassword' or v == 'DBPassword'):
                    try:
                        del dict['ParameterValue']
                    except:
                        pass
                    dict['UsePreviousValue'] = True
        if not key_found:
            parmlist.append({'ParameterKey': parmkey, 'ParameterValue': parmvalue})
        return parmlist

    def upload_template(self, file, s3_name):
        s3 = boto3.resource('s3', region_name=self.region)
        s3.meta.client.upload_file(file, 'wpe-public-software', f'forge-templates/{s3_name}')

    def ssm_send_command(self, instance, cmd):
        ssm = boto3.client('ssm', region_name=self.region)
        ssm_command = ssm.send_command(
            InstanceIds=[instance],
            DocumentName='AWS-RunShellScript',
            Parameters={'commands': [cmd], 'executionTimeout': ["900"]},
            OutputS3BucketName='wpe-logs',
            OutputS3KeyPrefix='run-command-logs'
        )
        self.state.logaction(log.INFO, f'for command: {cmd}, command_id is {ssm_command["Command"]["CommandId"]}')
        if ssm_command['ResponseMetadata']['HTTPStatusCode'] == 200:
            return (ssm_command['Command']['CommandId'])
        return False

    def ssm_cmd_check(self, cmd_id):
        ssm = boto3.client('ssm', region_name=self.region)
        list_command = ssm.list_commands(CommandId=cmd_id)
        cmd_status = list_command[u'Commands'][0][u'Status']
        instance = list_command[u'Commands'][0][u'InstanceIds'][0]
        self.state.logaction(log.INFO, f'result of ssm command {cmd_id} on instance {instance} is {cmd_status}')
        return (cmd_status, instance)


    def ssm_send_and_wait_response(self, instance, cmd):
        cmd_id = self.ssm_send_command(instance, cmd)
        if not cmd_id:
            self.state.logaction(log.ERROR, f'Command {cmd} on instance {instance} failed to send')
        else:
            result = self.wait_for_cmd_result(cmd_id)
        return result


## Stack - helper methods

    def get_current_state(self, like_stack=None, like_env=None):
        self.state.logaction(log.INFO, f'Getting pre-upgrade stack state for {self.stack_name}')
        # use the "like" stack and parms in preference to self
        query_stack = like_stack if like_stack else self.stack_name
        query_env = like_env if like_env else self.env
        query_region = self.setRegion(query_env)
        cfn = boto3.client('cloudformation', region_name=query_region)
        try:
            stack_details = cfn.describe_stacks(StackName=query_stack)
            template = cfn.get_template(StackName=query_stack)
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return
        # store the template
        self.state.update('TemplateBody', template['TemplateBody'])
        # write out the most recent parms to a file
        self.writeparms(stack_details['Stacks'][0]['Parameters'])
        # store the most recent parms (list of dicts)
        self.state.update('stack_parms', stack_details['Stacks'][0]['Parameters'] )
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
        if self.app_type == 'confluence':
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
        elif self.app_type == 'jira':
            self.state.update('preupgrade_jira_version',
                [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                 p['ParameterKey'] == 'JiraVersion'][0])
        self.state.logaction(log.INFO, f'finished getting stack_state for {self.stack_name}')
        return

    def spindown_to_zero_appnodes(self):
        self.state.logaction(log.INFO, f'Spinning {self.stack_name} stack down to 0 nodes')
        cfn = boto3.client('cloudformation', region_name=self.region)
        spindown_parms = self.state.forgestate['stack_parms']
        spindown_parms = self.update_parmlist(spindown_parms, 'ClusterNodeMax', '0')
        spindown_parms = self.update_parmlist(spindown_parms, 'ClusterNodeMin', '0')
        if self.app_type == 'confluence':
            spindown_parms = self.update_parmlist(spindown_parms, 'SynchronyClusterNodeMax', '0')
            spindown_parms = self.update_parmlist(spindown_parms, 'SynchronyClusterNodeMin', '0')
        self.state.logaction(log.INFO, f'Spindown params: {spindown_parms}')
        try:
            update_stack = cfn.update_stack(
                StackName=self.stack_name,
                Parameters=spindown_parms,
                UsePreviousTemplate=True,
                Capabilities=['CAPABILITY_IAM'],
            )
        except Exception as e:
            if 'No updates are to be performed' in e.args[0]:
                self.state.logaction(log.INFO, 'Stack is already at 0 nodes')
                return True
            else:
                print(e.args[0])
                self.state.logaction(log.ERROR, f'An error occurred spinning down to 0 nodes: {e.args[0]}')
                return False
        self.state.logaction(log.INFO, str(update_stack))
        if self.wait_stack_action_complete("UPDATE_IN_PROGRESS"):
            self.state.logaction(log.INFO, "Successfully spun down to 0 nodes")
            return True
        return False

    def wait_stack_action_complete(self, in_progress_state, stack_id=None):
        self.state.logaction(log.INFO, "Waiting for stack action to complete")
        stack_state = self.check_stack_state()
        while stack_state == in_progress_state:
            time.sleep(60)
            stack_state = self.check_stack_state(stack_id if stack_id else self.stack_name)
        if 'ROLLBACK' in stack_state:
            self.state.logaction(log.ERROR,f'Stack action was rolled back: {stack_state}')
            return False
        elif 'FAILED' in stack_state:
            self.state.logaction(log.ERROR,f'Stack action failed: {stack_state}')
            return False
        return True

    def spinup_to_one_appnode(self):
        self.state.logaction(log.INFO, "Spinning stack up to one appnode")
        # for connie 1 app node and 1 synchrony
        cfn = boto3.client('cloudformation', region_name=self.region)
        spinup_parms = self.state.forgestate['stack_parms']
        spinup_parms = self.update_parmlist(spinup_parms, 'ClusterNodeMax', '1')
        spinup_parms = self.update_parmlist(spinup_parms, 'ClusterNodeMin', '1')
        if self.app_type == 'jira':
            spinup_parms = self.update_parmlist(spinup_parms, 'JiraVersion', self.state.forgestate['new_version'])
        elif self.app_type == 'confluence':
            spinup_parms = self.update_parmlist(spinup_parms, 'ConfluenceVersion', self.state.forgestate['new_version'])
            spinup_parms = self.update_parmlist(spinup_parms, 'SynchronyClusterNodeMax', '1')
            spinup_parms = self.update_parmlist(spinup_parms, 'SynchronyClusterNodeMin', '1')
        self.state.logaction(log.INFO, f'Spinup params: {spinup_parms}')
        try:
            update_stack = cfn.update_stack(
                StackName=self.stack_name,
                Parameters=spinup_parms,
                UsePreviousTemplate=True,
                Capabilities=['CAPABILITY_IAM'],
            )
        except botocore.exceptions.ClientError as e:
            self.state.logaction(log.INFO, f'Stack spinup failed: {e.args[0]}')
            return False
        if not self.wait_stack_action_complete("UPDATE_IN_PROGRESS"):
            return False
        self.state.logaction(log.INFO, "Spun up to 1 node, waiting for service to respond")
        self.validate_service_responding()
        self.state.logaction(log.INFO, f'Updated stack: {update_stack}')
        return True

    def validate_service_responding(self):
        self.state.logaction(log.INFO, "Waiting for service to reply RUNNING on /status")
        service_state = self.check_service_status()
        while service_state != '{"state":"RUNNING"}':
            time.sleep(60)
            service_state = self.check_service_status()
        self.state.logaction(log.INFO, f' {self.stack_name} /status now reporting RUNNING')
        return

    def check_service_status(self):
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack_details = cfn.describe_stacks(StackName=self.stack_name)
        except Exception as e:
            print(e.args[0])
            return f'Error checking service status: {e.args[0]}'
        self.state.update('lburl', self.getLburl(stack_details))
        self.state.logaction(log.INFO,
                        f' ==> checking service status at {self.state.forgestate["lburl"]}/status')
        try:
            service_status = requests.get(self.state.forgestate['lburl'] + '/status', timeout=5)
            status = service_status.text if service_status.text else "...?"
            if '<title>' in status:
                status = status[status.index('<title>') + 7 : status.index('</title>')]
            self.state.logaction(log.INFO,
                            f' ==> service status is: {status}')
            return status
        except requests.exceptions.ReadTimeout as e:
            self.state.logaction(log.INFO, f'Node status check timed out')
        return "Timed Out"

    def check_stack_state(self, stack_id=None):
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack_state = cfn.describe_stacks(StackName=stack_id if stack_id else self.stack_name)
        except Exception as e:
            if "does not exist" in e.response['Error']['Message']:
                self.state.logaction(log.INFO, f'Stack {self.stack_name} does not exist')
                return
            print(e.args[0])
            self.state.logaction(log.ERROR, f'Error checking stack state: {e.args[0]}')
            return
        state = stack_state['Stacks'][0]['StackStatus']
        return state

    def check_node_status(self, node_ip):
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack = cfn.describe_stacks(StackName=self.stack_name)
        except Exception as e:
            print(e.args[0])
            return f'Error checking node status: {e.args[0]}'

        context_path = [param['ParameterValue'] for param in stack['Stacks'][0]['Parameters']  if param['ParameterKey'] == 'TomcatContextPath'][0]
        port = [param['ParameterValue'] for param in stack['Stacks'][0]['Parameters'] if param['ParameterKey'] == 'TomcatDefaultConnectorPort'][0]
        self.state.logaction(log.INFO, f' ==> checking node status at {node_ip}:{port}{context_path}/status')
        try:
            node_status = requests.get(f'http://{node_ip}:{port}{context_path}/status', timeout=5)
            self.state.logaction(log.INFO, f' ==> node status is: {node_status.text}')
            return node_status.text
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout) as e:
            self.state.logaction(log.INFO, f'Node status check timed out')
        except Exception as e:
            print('type is:', e.__class__.__name__)
        return "Timed Out"


    def spinup_remaining_nodes(self):
        self.state.logaction(log.INFO, 'Spinning up any remaining nodes in stack')
        cfn = boto3.client('cloudformation', region_name=self.region)
        spinup_parms = self.state.forgestate['stack_parms']
        spinup_parms = self.update_parmlist(spinup_parms, 'ClusterNodeMax', self.state.forgestate['appnodemax'])
        spinup_parms = self.update_parmlist(spinup_parms, 'ClusterNodeMin', self.state.forgestate['appnodemin'])
        if self.app_type == 'jira':
            spinup_parms = self.update_parmlist(spinup_parms, 'JiraVersion', self.state.forgestate['new_version'])
        if self.app_type == 'confluence':
            spinup_parms = self.update_parmlist(spinup_parms, 'ConfluenceVersion', self.state.forgestate['new_version'])
            spinup_parms = self.update_parmlist(spinup_parms, 'SynchronyClusterNodeMax', self.state.forgestate['syncnodemax'])
            spinup_parms = self.update_parmlist(spinup_parms, 'SynchronyClusterNodeMin', self.state.forgestate['syncnodemin'])
        self.state.logaction(log.INFO, f'Spinup params: {spinup_parms}')
        try:
            update_stack = cfn.update_stack(
                StackName=self.stack_name,
                Parameters=spinup_parms,
                UsePreviousTemplate=True,
                Capabilities=['CAPABILITY_IAM'],
            )
        except Exception as e:
            print(e.args[0])
            self.state.logaction(log.ERROR, f'Error occurred spinning up remaining nodes: {e.args[0]}')
            return False
        if self.wait_stack_action_complete("UPDATE_IN_PROGRESS"):
            self.state.logaction(log.INFO, "Stack restored to full node count")
        return True

    def get_stacknodes(self):
        ec2 = boto3.resource('ec2', region_name=self.region)
        filters = [
            {'Name': 'tag:aws:cloudformation:stack-name', 'Values': [self.stack_name]},
            {'Name': 'tag:aws:cloudformation:logical-id', 'Values': ['ClusterNodeGroup']},
            {'Name': 'instance-state-name', 'Values': ['pending', 'running']},
        ]
        self.instancelist = []
        for i in ec2.instances.filter(Filters=filters):
            instancedict = {i.instance_id: i.private_ip_address}
            self.instancelist.append(instancedict)
        return

    def shutdown_app(self, instancelist):
        cmd_id_list = []
        for i in range(0, len(instancelist)):
            for key in instancelist[i]:
                instance = key
                node_ip = instancelist[i][instance]
            self.state.logaction(log.INFO, f'Shutting down {self.app_type} on {instance} ({node_ip})')
            cmd = f'/etc/init.d/{self.app_type} stop'
            cmd_id_list.append(self.ssm_send_command(instance, cmd))
        for cmd_id in cmd_id_list:
            result = self.wait_for_cmd_result(cmd_id)
            if result == 'Failed':
                self.state.logaction(log.ERROR, f'Shutdown result for {cmd_id}: {result}')
            else:
                self.state.logaction(log.INFO, f'Shutdown result for {cmd_id}: {result}')
        return

    def startup_app(self, instancelist):
        for instancedict in instancelist:
            instance = list(instancedict.keys())[0]
            node_ip = list(instancedict.values())[0]
            self.state.logaction(log.INFO, f'Starting up {instance} ({node_ip})')
            cmd = f'/etc/init.d/{self.app_type} start'
            cmd_id = self.ssm_send_command(instance, cmd)
            result = self.wait_for_cmd_result(cmd_id)
            if result == 'Failed':
                self.state.logaction('ERROR', f'Startup result for {cmd_id}: {result}')
            else:
                result = ""
                while result != '{"state":"RUNNING"}':
                    result = self.check_node_status(node_ip)
                    self.state.logaction(log.INFO, f'Startup result for {cmd_id}: {result}')
                    time.sleep(60)
        return

    def run_command(self, instancelist, cmd):
        cmd_id_dict = {}
        for instancedict in instancelist:
            instance = list(instancedict.keys())[0]
            node_ip = list(instancedict.values())[0]
            self.state.logaction(log.INFO, f'Running command {cmd} on {node_ip}')
            cmd_id_dict[self.ssm_send_command(instance, cmd)] = node_ip
        for cmd_id in cmd_id_dict:
            result = self.wait_for_cmd_result(cmd_id)
            if result == 'Failed':
                self.state.logaction(log.ERROR, f'Command result for {cmd_id}: {result}')
                return False
            else:
                self.state.logaction(log.INFO, f'Command result for {cmd_id}: {result}')
        return True

    def wait_for_cmd_result(self, cmd_id):
        result = ""
        while result != 'Success' and result != 'Failed':
            result, cmd_instance = self.ssm_cmd_check(cmd_id)
            time.sleep(10)
        return result

    def get_stack_action_in_progress(self):
        try:
            with open(f'stacks/{self.stack_name}/{self.stack_name}.current-action', 'r') as infile:
                action = infile.read()
                return action
        except FileNotFoundError:
            return False

    def store_current_action(self, action):
        if Path(f'stacks/{self.stack_name}/{self.stack_name}.json').exists():
            os.remove(f'stacks/{self.stack_name}/{self.stack_name}.json')
        self.state.update('action', action)
        with open(f'stacks/{self.stack_name}/{self.stack_name}.current-action', 'w') as outfile:
            outfile.write(action)
        outfile.close()
        return True

    def clear_current_action(self):
        self.state.archive()
        os.remove(f'stacks/{self.stack_name}/{self.stack_name}.current-action')
        self.state.update('action', 'none')
        return True


## Stack - Major Action Methods

    def upgrade(self, new_version):
        self.state.logaction(log.INFO, f'Beginning upgrade for {self.stack_name}')
        self.state.update('new_version', new_version)
        # TODO block traffic at vtm
        # get pre-upgrade state information
        self.get_current_state()
        # # spin stack down to 0 nodes
        if not self.spindown_to_zero_appnodes():
            self.state.logaction(log.INFO, "Upgrade complete - failed")
            return False
        # TODO change template if required
        # spin stack up to 1 node on new release version
        if not self.spinup_to_one_appnode():
            self.state.logaction(log.INFO, "Upgrade complete - failed")
            return False
        # spinup remaining appnodes in stack if needed
        if self.state.forgestate['appnodemin'] != "1":
            self.spinup_remaining_nodes()
        elif 'syncnodemin' in self.state.forgestate.keys() and self.state.forgestate[
            'syncnodemin'] != "1":
            self.spinup_remaining_nodes()
        # TODO wait for remaining nodes to respond ??? ## maybe a LB check for active node count
        # TODO enable traffic at VTM
        self.state.logaction(log.INFO, f'Upgrade successful for {self.stack_name} at {self.env} to version {new_version}')
        self.state.logaction(log.INFO, "Upgrade complete")
        return True


    def destroy(self):
        self.state.logaction(log.INFO, f'Destroying stack {self.stack_name} in {self.env}')
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack_state = cfn.describe_stacks(StackName=self.stack_name)
        except botocore.exceptions.ClientError as e:
            if "does not exist" in e.response['Error']['Message']:
                self.state.logaction(log.INFO, f'Stack {self.stack_name} does not exist')
                return True
        stack_id = stack_state['Stacks'][0]['StackId']
        delete_stack = cfn.delete_stack(StackName=self.stack_name)
        if self.wait_stack_action_complete("DELETE_IN_PROGRESS", stack_id):
            self.state.logaction(log.INFO, f'Destroy successful for stack {self.stack_name}: {delete_stack}')
        self.state.logaction(log.INFO, "Destroy complete")
        return True


    def clone(self, stack_parms):
        self.state.logaction(log.INFO, 'Initiating clone')
        self.writeparms(stack_parms)
        # TODO popup confirming if you want to destroy existing
        if self.destroy():
            if self.create(parms=stack_parms, clone=True):
                if self.run_post_clone_sql():
                    self.full_restart()
        self.state.logaction(log.INFO, "Clone complete")
        return True

    def update(self, stack_parms, template_type):
        self.state.logaction(log.INFO, 'Updating stack with params: ' + str([param for param in stack_parms if 'UsePreviousValue' not in param]))
        template_filename = f'{self.app_type.title()}{template_type}.template.yaml'
        template= f'wpe-aws/{self.app_type}/{template_filename}'
        self.upload_template(template, template_filename)
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            updated_stack = cfn.update_stack(
                StackName=self.stack_name,
                Parameters=stack_parms,
                TemplateURL=f'https://s3.amazonaws.com/wpe-public-software/forge-templates/{template_filename}',
                Capabilities=['CAPABILITY_IAM'],
            )
            stack_details = cfn.describe_stacks(StackName=self.stack_name)
        except Exception as e:
            print(e.args[0])
            self.state.logaction(log.ERROR, f'An error occurred updating stack: {e.args[0]}')
            self.state.logaction(log.INFO, "Update complete - failed")
            return False
        self.state.update('lburl', self.getLburl(stack_details))
        self.state.logaction(log.INFO, f'Stack {self.stack_name} is being updated: {updated_stack}')
        if not self.wait_stack_action_complete("UPDATE_IN_PROGRESS"):
            self.state.logaction(log.INFO, "Update complete - failed")
            return False
        if 'ParameterValue' in [param for param in stack_parms if param['ParameterKey'] == 'ClusterNodeMax'][0] and \
                int([param['ParameterValue'][0] for param in stack_parms if param['ParameterKey'] == 'ClusterNodeMax'][0]) > 0:
            self.state.logaction(log.INFO, 'Waiting for stack to respond')
            self.validate_service_responding()
        self.state.logaction(log.INFO, "Update complete")
        return True


    #  TODO create like
    # def create_like(self, like_stack, changeparms):
    #     # grab stack parms from like stack
    #     # changedParms = param list with changed parms
    #     create(parms=changedParms)


    def create(self, like_stack=None, like_env=None, parms=None, clone=False, template_filename=None, app_type=None):
        if like_stack:
            self.get_current_state(like_stack, like_env)
            stack_parms = self.state.forgestate['stack_parms']
            self.state.logaction(log.INFO, f'Creating stack: {self.stack_name}, like source stack {like_stack}')
        elif parms:
            parms.remove(parms[0])
            stack_parms = parms
            self.state.logaction(log.INFO, f'Creating stack: {self.stack_name}')
        else:
            stack_parms = self.readparms()
            self.state.logaction(log.INFO, f'Creating stack: {self.stack_name}')
        self.state.logaction(log.INFO, f'Creation params: {stack_parms}')
        if not template_filename:
            template_filename = f'{self.app_type.title()}STGorDR.template.yaml'
        template=f'wpe-aws/{app_type if app_type else self.app_type}/{template_filename}'
        self.upload_template(template, template_filename)
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            # TODO spin up to one node first, then spin up remaining nodes
            created_stack = cfn.create_stack(
                StackName=self.stack_name,
                Parameters=stack_parms,
                TemplateURL=f'https://s3.amazonaws.com/wpe-public-software/forge-templates/{template_filename}',
                Capabilities=['CAPABILITY_IAM'],
            )
            time.sleep(5)
            stack_details = cfn.describe_stacks(StackName=self.stack_name)
        except Exception as e:
            print(e.args[0])
            self.state.logaction(log.WARN, f'Error occurred creating stack: {e.args[0]}')
            self.state.logaction(log.INFO, "Create complete - failed")
            return False
        self.state.logaction(log.INFO, f'Create has begun: {created_stack}')
        if not self.wait_stack_action_complete("CREATE_IN_PROGRESS"):
            self.state.logaction(log.INFO, "Create complete - failed")
            return False
        self.state.logaction(log.INFO, f'Stack {self.stack_name} created, waiting on service responding')
        self.validate_service_responding()
        self.state.logaction(log.INFO, "Create complete")
        return True


    def rolling_restart(self):
        self.state.logaction(log.INFO, f'Beginning Rolling Restart for {self.stack_name}')
        self.get_stacknodes()
        self.state.logaction(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        for instance in self.instancelist:
            shutdown = self.shutdown_app([instance])
            self.state.logaction(log.INFO, f'starting application on instance {instance} for {self.stack_name}')
            startup = self.startup_app([instance])
        self.state.logaction(log.INFO, "Rolling restart complete")
        return True


    def full_restart(self):
        self.state.logaction(log.INFO, f'Beginning Full Restart for {self.stack_name}')
        self.get_stacknodes()
        self.state.logaction(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        self.state.logaction(log.INFO, f'Shutting down {self.app_type} on all instances of {self.stack_name}')
        shutdown = self.shutdown_app(self.instancelist)
        for instance in self.instancelist:
            self.state.logaction(log.INFO, f'starting application on {instance} for {self.stack_name}')
            startup = self.startup_app([instance])
        self.state.logaction(log.INFO, "Full restart complete")
        return True


    def thread_dump(self, alsoHeaps=False):
        heaps_to_come_log_line = ''
        if alsoHeaps:
            heaps_to_come_log_line = ', heap dumps to follow'
        self.state.logaction(log.INFO, f'Beginning thread dumps on {self.stack_name}{heaps_to_come_log_line}')
        self.get_stacknodes()
        self.state.logaction(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        self.run_command(self.instancelist, '/usr/local/bin/j2ee_thread_dump')
        self.state.logaction(log.INFO, "Thread dumps complete")
        return True


    def heap_dump(self):
        self.state.logaction(log.INFO, f'Beginning heap dumps on {self.stack_name}')
        self.get_stacknodes()
        self.state.logaction(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        # Wait for each heap dump to finish before starting the next, to avoid downtime
        for instance in self.instancelist:
            self.ssm_send_and_wait_response(list(instance.keys())[0], '/usr/local/bin/j2ee_heap_dump_live')
            time.sleep(30) # give node time to recover and rejoin cluster
        self.state.logaction(log.INFO, "Heap dumps complete")
        return True

    def run_post_clone_sql(self):
        self.state.logaction(log.INFO, f'Running post clone SQL')
        self.get_stacknodes()
        sqlfile = Path(f'stacks/{self.stack_name}/{self.stack_name}.post-clone.sql')
        if sqlfile.is_file():
            with open(sqlfile, 'r') as outfile:
                if self.run_command([self.instancelist[0]], f'echo "{outfile.read()}" > /usr/local/bin/{self.stack_name}.post-clone.sql') :
                    db_conx_string = 'PGPASSWORD=${ATL_JDBC_PASSWORD} /usr/bin/psql -h ${ATL_DB_HOST} -p ${ATL_DB_PORT} -U postgres -w ${ATL_DB_NAME}'
                    if not self.run_command([self.instancelist[0]], f'source /etc/atl; {db_conx_string} -a -f /usr/local/bin/{self.stack_name}.post-clone.sql'):
                        self.state.logaction(log.ERROR, f'Running SQL script failed')
                        return False
                else:
                    self.state.logaction(log.ERROR, f'Dumping SQL file to target machine failed')
                    return False
        else:
            self.state.logaction(log.INFO, f'No post clone SQL file found')
            return False
        self.state.logaction(log.INFO, f'Run SQL complete')
        return True
