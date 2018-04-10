from forgestate import Forgestate
import boto3
import botocore
import time
import requests
import json
import sys
from datetime import datetime
from pprint import pprint
import log

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
            except Exception as e:
                print(e.args[0])
                self.state.logaction(log.WARN, f'An error occurred getting stack details from AWS (stack may not exist yet): {e.args[0]}')
        self.state.logaction(log.INFO, f'{stack_name} is a {app_type}')
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
        with open(self.stack_name + '.parms.json', 'w') as outfile:
            json.dump(parms, outfile)
        outfile.close()
        return (self)

    def readparms(self):
        try:
            with open(self.stack_name + '.parms.json', 'r') as infile:
                parms = json.load(infile)
                return parms
        except FileNotFoundError:
            self.state.logaction(log.ERROR, f'can not load parms, {self.stack_name}.parms.json does not exist')
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
        sys.exit()

    def ssm_cmd_check(self, cmd_id):
        ssm = boto3.client('ssm', region_name=self.region)
        list_command = ssm.list_commands(CommandId=cmd_id)
        cmd_status = list_command[u'Commands'][0][u'Status']
        instance = list_command[u'Commands'][0][u'InstanceIds'][0]
        self.state.logaction(log.INFO, f'result of ssm command {cmd_id} on instance {instance} is {cmd_status}')
        return (cmd_status, instance)


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
        # lets write out the most recent parms to a file
        self.writeparms(stack_details['Stacks'][0]['Parameters'])
        # let's store the parms (list of dicts) if they haven't been already stored
        if "stack_parms" in self.state.forgestate:
            print("stack parms already stored")
        else:
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
        update_stack = cfn.update_stack(
            StackName=self.stack_name,
            Parameters=spindown_parms,
            UsePreviousTemplate=True,
            Capabilities=['CAPABILITY_IAM'],
        )
        self.state.logaction(log.INFO, str(update_stack))
        self.wait_stack_action_complete("UPDATE_IN_PROGRESS")
        return

    def wait_stack_action_complete(self, in_progress_state, stack_id=None):
        self.state.logaction(log.INFO, "Waiting for stack action to complete")
        stack_state = self.check_stack_state()
        while stack_state == in_progress_state:
            self.state.logaction(log.INFO, "====> stack_state is: " + stack_state)
            time.sleep(60)
            stack_state = self.check_stack_state(stack_id if stack_id else self.stack_name)
        return

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
            self.state.logaction(log.INFO, f'stack spinup failed {e.args[0]}')
            sys.exit()
        self.wait_stack_action_complete("UPDATE_IN_PROGRESS")
        self.validate_service_responding()
        self.state.logaction(log.INFO, f'Update stack: {update_stack}')
        return

    def validate_service_responding(self):
        self.state.logaction(log.INFO, "Waiting for service to reply RUNNING on /status")
        service_state = self.check_service_status()
        while service_state != '{"state":"RUNNING"}':
            self.state.logaction(log.INFO,
                f'====> health check reports: {service_state} waiting for RUNNING " {str(datetime.now())}')
            time.sleep(60)
            service_state = self.check_service_status()
        self.state.logaction(log.INFO, f' {self.stack_name} /status now reporting RUNNING')
        return

    def check_service_status(self):
        self.state.logaction(log.INFO,
                        f' ==> checking service status at {self.state.forgestate["lburl"]} /status')
        try:
            service_status = requests.get(self.state.forgestate['lburl'] + '/status', timeout=5)
            status = service_status.text if service_status.text else "...?"
            self.state.logaction(log.INFO,
                            f' ==> service status is: {status}')
            return service_status.text
        except requests.exceptions.ReadTimeout as e:
            self.state.logaction(log.INFO, f'Node status check timed out: {e.errno}, {e.strerror}')
        return "Timed Out"

    def check_stack_state(self, stack_id=None):
        self.state.logaction(log.INFO, " ==> checking stack state")
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
        return stack_state['Stacks'][0]['StackStatus']

    def check_node_status(self, node_ip):
        self.state.logaction(log.INFO, f' ==> checking node status at {node_ip}/status')
        try:
            node_status = requests.get(f'http://{node_ip}:8080/status', timeout=5)
            self.state.logaction(log.INFO, f' ==> node status is: {node_status.text}')
            return node_status.text
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout) as e:
            self.state.logaction(log.INFO, f'Node status check timed out: {e.errno}, {e.strerror}')
        except Exception as e:
            print('type is:', e.__class__.__name__)
        return "Timed Out"

    def spinup_remaining_nodes(self):
        self.state.logaction(log.INFO, "Spinning up any remaining nodes in stack")
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
        update_stack = cfn.update_stack(
            StackName=self.stack_name,
            Parameters=spinup_parms,
            UsePreviousTemplate=True,
            Capabilities=['CAPABILITY_IAM'],
        )
        self.wait_stack_action_complete("UPDATE_IN_PROGRESS")
        self.state.logaction(log.INFO, "Stack restored to full node count")
        return

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
            self.state.logaction(log.INFO, f'Shutting down {instance} ({node_ip})')
            cmd = f'/etc/init.d/{self.app_type} stop'
            cmd_id_list.append(self.ssm_send_command(instance, cmd))
        for cmd_id in cmd_id_list:
            result = ""
            while result != 'Success' and result != 'Failed':
                result, cmd_instance = self.ssm_cmd_check(cmd_id)
                time.sleep(10)
            if result == 'Failed':
                self.state.logaction(log.ERROR, f'Shutdown result for {cmd_instance}: {result}')
            else:
                self.state.logaction(log.INFO, f'Shutdown result for {cmd_instance}: {result}')
        return

    def startup_app(self, instancelist):
        for instancedict in instancelist:
            instance = list(instancedict.keys())[0]
            node_ip = list(instancedict.values())[0]
            self.state.logaction(log.INFO, f'Starting up {instance} ({node_ip})')
            cmd = f'/etc/init.d/{self.app_type} start'
            cmd_id = self.ssm_send_command(instance, cmd)
            result = ""
            while result != 'Success' and result != 'Failed':
                result, cmd_instance = self.ssm_cmd_check(cmd_id)
                time.sleep(10)
            if result == 'Failed':
                self.state.logaction('ERROR', f'Startup result for {cmd_instance}: {result}')
            else:
                result = ""
                while result != '{"state":"RUNNING"}':
                    result = self.check_node_status(node_ip)
                    self.state.logaction(log.INFO, f'Startup result for {cmd_instance}: {result}')
                    time.sleep(30)
        return

    def run_command(self, instancelist, cmd):
        cmd_id_dict = {}
        for instancedict in instancelist:
            instance = list(instancedict.keys())[0]
            node_ip = list(instancedict.values())[0]
            self.state.logaction(log.INFO, f'Running command {cmd} on ({node_ip})')
            cmd_id_dict[self.ssm_send_command(instance, cmd)] = node_ip
        for cmd_id in cmd_id_dict:
            result = ""
            while result != 'Success' and result != 'Failed':
                result, cmd_instance = self.ssm_cmd_check(cmd_id)
                time.sleep(10)
            if result == 'Failed':
                self.state.logaction(log.ERROR, f'Command result for {cmd_instance}: {result}')
            else:
                self.state.logaction(log.INFO, f'Command result for {cmd_instance}: {result}')
        return

## Stack - Major Action Methods

    def upgrade(self, new_version):
        self.state.logaction(log.INFO, f'Beginning upgrade for {self.stack_name}')
        self.state.update('action', 'upgrade')
        self.state.update('new_version', new_version)
        # TODO block traffic at vtm
        # get pre-upgrade state information
        self.get_current_state()
        # # spin stack down to 0 nodes
        self.spindown_to_zero_appnodes()
        # TODO change template if required
        # spin stack up to 1 node on new release version
        self.spinup_to_one_appnode()
        # spinup remaining appnodes in stack if needed
        if self.state.forgestate['appnodemin'] != "1":
            self.spinup_remaining_nodes()
        elif 'syncnodemin' in self.state.forgestate.keys() and self.state.forgestate[
            'syncnodemin'] != "1":
            self.spinup_remaining_nodes()
        # TODO wait for remaining nodes to respond ??? ## maybe a LB check for active node count
        # TODO enable traffic at VTM
        self.state.logaction(log.INFO, f'Completed upgrade for {self.stack_name} at {self.env} to version {new_version}')
        self.state.logaction(log.INFO, "Final state")
        self.state.archive()
        # return forgestate[stack_name]['last_action_log']
        return


    def destroy(self):
        self.state.logaction(log.INFO, f'Destroying stack {self.stack_name} in {self.env}')
        self.state.update('action', 'destroy')
        cfn = boto3.client('cloudformation', region_name=self.region)
        try:
            stack_state = cfn.describe_stacks(StackName=self.stack_name)
        except botocore.exceptions.ClientError as e:
            if "does not exist" in e.response['Error']['Message']:
                self.state.logaction(log.INFO, f'Stack {self.stack_name} does not exist')
                return
        stack_id = stack_state['Stacks'][0]['StackId']
        delete_stack = cfn.delete_stack(StackName=self.stack_name)
        self.wait_stack_action_complete("DELETE_IN_PROGRESS", stack_id)
        self.state.logaction(log.INFO, f'Destroy complete for stack {self.stack_name}: {delete_stack}')
        self.state.logaction(log.INFO, "Final state")
        self.state.archive()
        return


    def clone(self, stack_parms):
        self.state.update('action', 'clone')
        self.writeparms(stack_parms)
        # TODO popup confirming if you want to destroy existing
        self.destroy()
        self.create(parms=stack_parms, clone=True)
        return

    def update(self, stack_parms, template_type):
        self.state.update('action', 'update')
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
            self.state.logaction(log.ERROR, f'An error occurred: {e.args[0]}')
            return
        self.state.update('lburl', self.getLburl(stack_details))
        self.state.logaction(log.INFO, f'Stack {self.stack_name} is being updated: {updated_stack}')
        self.wait_stack_action_complete("UPDATE_IN_PROGRESS")
        if len([param for param in stack_parms if param['ParameterKey'] == 'ClusterNodeMax']) > 0 \
                and [param for param in stack_parms if 'ParameterValue' in param and param['ParameterKey'] == 'ClusterNodeMax'][0]['ParameterValue'] != 0:
            self.state.logaction(log.INFO, 'Waiting for stack to respond')
            self.validate_service_responding()
        self.state.logaction(log.INFO, "Final state")
        self.state.archive()
        return


    #  TODO create like
    # def create_like(self, like_stack, changeparms):
    #     # grab stack parms from like stack
    #     # changedParms = param list with changed parms
    #     create(parms=changedParms)


    def create(self, like_stack=None, like_env=None, parms=None, clone=False, template_filename=None, app_type=None):
        # create uses an existing stack as a cookie cutter for the template and its parms, but is empty of data
        # probably need to force mail disable catalina opts for safety (note from Denise: this is done in the JS in the front end so it can be modified)
        self.state.update('action', 'create')
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
            stack_details = cfn.describe_stacks(StackName=self.stack_name)
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return
        self.state.update('lburl', self.getLburl(stack_details))
        self.state.logaction(log.INFO, f'Create has begun: {created_stack}')
        self.wait_stack_action_complete("CREATE_IN_PROGRESS")
        self.state.logaction(log.INFO, f'Stack {self.stack_name} created, waiting on service responding')
        self.validate_service_responding()
        self.state.logaction(log.INFO, "Final state")
        self.state.archive()
        return


    def rolling_restart(self):
        self.state.logaction(log.INFO, f'Beginning Rolling Restart for {self.stack_name}')
        self.get_stacknodes()
        self.state.logaction(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        for instance in self.instancelist:
            self.state.logaction(log.INFO, f'shutting down application on instance {instance} for {self.stack_name}')
            shutdown = self.shutdown_app([instance])
            self.state.logaction(log.INFO, f'starting application on instance {instance} for {self.stack_name}')
            startup = self.startup_app([instance])
        self.state.logaction(log.INFO, "Final state")
        return


    def full_restart(self):
        self.state.logaction(log.INFO, f'Beginning Full Restart for {self.stack_name}')
        self.get_stacknodes()
        self.state.logaction(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        self.state.logaction(log.INFO, f'shutting down application on all instances of {self.stack_name}')
        shutdown = self.shutdown_app(self.instancelist)
        for instance in self.instancelist:
            self.state.logaction(log.INFO, f'starting application on {instance} for {self.stack_name}')
            startup = self.startup_app([instance])
        self.state.logaction(log.INFO, "Final state")
        return


    def thread_dump(self):
        self.state.logaction(log.INFO, f'Beginning thread dumps on {self.stack_name}')
        self.get_stacknodes()
        self.state.logaction(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        self.run_command(self.instancelist, '/usr/local/bin/j2ee_thread_dump')
        self.state.logaction(log.INFO, "Final state")
        return


    def heap_dump(self):
        self.state.logaction(log.INFO, f'Beginning heap dumps on {self.stack_name}')
        self.get_stacknodes()
        self.state.logaction(log.INFO, f'{self.stack_name} nodes are {self.instancelist}')
        self.run_command(self.instancelist, '/usr/local/bin/j2ee_heap_dump_live')
        self.state.logaction(log.INFO, "Final state")
        return
