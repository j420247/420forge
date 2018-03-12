from collections import defaultdict
from forgestate import Forgestate
import boto3
import botocore
import time
import requests
from pprint import pprint
from datetime import datetime
import json
from pprint import pprint

class Stack:
    """An object describing an instance of an aws cloudformation stack:

    Attributes:
        forgestate: A dict of dicts containing all state information.
        stack_name: The name of the stack we are keeping state for
    """

    def __init__(self, stack_name):
        self.state = Forgestate(stack_name)
        self.state.logaction('INFO', f'Initialising stack object for {stack_name}')
        self.stack_name = stack_name

## Stack - micro function methods

    def print_action_log(self):
        self.state.read()
        return self.state.forgestate['action_log']

    def debug_forgestate(self):
        self.state.read()
        pprint(self.state.forgestate)
        return

    def setRegion(self, env):
        if env == 'prod':
            return 'us-west-2'
        else:
            return 'us-east-1'

    def getLburl(self, stack_details):
        rawlburl = [p['OutputValue'] for p in stack_details['Stacks'][0]['Outputs'] if
                    p['OutputKey'] == 'LoadBalancerURL'][0] + self.state.forgestate['tomcatcontextpath']
        return rawlburl.replace("https", "http")

    def update_parm(self, parmlist, parmkey, parmvalue):
        for dict in parmlist:
            for k, v in dict.items():
                if v == parmkey:
                    dict['ParameterValue'] = parmvalue
                if v == 'DBMasterUserPassword' or v == 'DBPassword':
                    try:
                        del dict['ParameterValue']
                    except:
                        pass
                    dict['UsePreviousValue'] = True
        return parmlist

## Stack - helper methods

    def get_current_state(self):
        self.state.logaction('INFO', f'Getting pre-upgrade stack state for {self.stack_name}')
        cfn = boto3.client('cloudformation', region_name=self.state.forgestate['region'])
        try:
            stack_details = cfn.describe_stacks(StackName=self.stack_name)
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return
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
        try:
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
        except:
            self.state.logaction('INFO', f'{self.stack_name} is NOT confluence')
        # jira
        try:
            self.state.update('preupgrade_jira_version',
                [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                 p['ParameterKey'] == 'JiraVersion'][0])
        except:
            self.state.logaction('INFO', f'{self.stack_name} is NOT jira')
        self.state.logaction('INFO', f'finished getting stack_state for {self.stack_name}')
        return

    def spindown_to_zero_appnodes(self):
        self.state.logaction('INFO', f'Spinning {self.stack_name} stack down to 0 nodes')
        cfn = boto3.client('cloudformation', region_name=self.state.forgestate['region'])
        spindown_parms = self.state.forgestate['stack_parms']
        spindown_parms = self.update_parm(spindown_parms, 'ClusterNodeMax', '0')
        spindown_parms = self.update_parm(spindown_parms, 'ClusterNodeMin', '0')
        if 'preupgrade_confluence_version' in self.state.forgestate:
            spindown_parms = self.update_parm(spindown_parms, 'SynchronyClusterNodeMax', '0')
            spindown_parms = self.update_parm(spindown_parms, 'SynchronyClusterNodeMin', '0')
        self.state.logaction('INFO', f'Spindown params: {spindown_parms}')
        update_stack = cfn.update_stack(
            StackName=self.stack_name,
            Parameters=spindown_parms,
            UsePreviousTemplate=True,
            Capabilities=['CAPABILITY_IAM'],
        )
        self.state.logaction('INFO', str(update_stack))
        self.wait_stack_action_complete("UPDATE_IN_PROGRESS")
        return

    def wait_stack_action_complete(self, in_progress_state, stack_id=None):
        self.state.logaction('INFO', "Waiting for stack action to complete")
        stack_state = self.check_stack_state()
        while stack_state == in_progress_state:
            self.state.logaction('INFO', "====> stack_state is: " + stack_state)
            time.sleep(60)
            stack_state = self.check_stack_state(stack_id if stack_id else self.stack_name)
        return

    def spinup_to_one_appnode(self):
        self.state.logaction('INFO', "Spinning stack up to one appnode")
        # for connie 1 app node and 1 synchrony
        cfn = boto3.client('cloudformation', region_name=self.state.forgestate['region'])
        spinup_parms = self.state.forgestate['stack_parms']
        spinup_parms = self.update_parm(spinup_parms, 'ClusterNodeMax', '1')
        spinup_parms = self.update_parm(spinup_parms, 'ClusterNodeMin', '1')
        if 'preupgrade_jira_version' in self.state.forgestate:
            spinup_parms = self.update_parm(spinup_parms, 'JiraVersion', self.state.forgestate['new_version'])
        if 'preupgrade_confluence_version' in self.state.forgestate:
            spinup_parms = self.update_parm(spinup_parms, 'ConfluenceVersion', self.state.forgestate['new_version'])
            spinup_parms = self.update_parm(spinup_parms, 'SynchronyClusterNodeMax', '1')
            spinup_parms = self.update_parm(spinup_parms, 'SynchronyClusterNodeMin', '1')
        self.state.logaction('INFO', f'Spinup params: {spinup_parms}')
        update_stack = cfn.update_stack(
            StackName=self.stack_name,
            Parameters=spinup_parms,
            UsePreviousTemplate=True,
            Capabilities=['CAPABILITY_IAM'],
        )
        self.wait_stack_action_complete("UPDATE_IN_PROGRESS")
        self.validate_service_responding()
        self.state.logaction('INFO', f'Update stack: {update_stack}')
        return

    def validate_service_responding(self):
        self.state.logaction('INFO', "Waiting for service to reply RUNNING on /status")
        service_state = self.check_service_status()
        while service_state != '{"state":"RUNNING"}':
            self.state.logaction('INFO',
                f'====> health check reports: {service_state} waiting for RUNNING " {str(datetime.now())}')
            time.sleep(60)
            service_state = self.check_service_status()
        self.state.logaction('INFO', f' {self.stack_name} /status now reporting RUNNING')
        return

    def check_service_status(self):
        self.state.logaction('INFO',
                        f' ==> checking service status at {self.state.forgestate["lburl"]} /status')
        try:
            service_status = requests.get(self.state.forgestate['lburl'] + '/status', timeout=5)
            status = service_status.text if service_status.text else "...?"
            self.state.logaction('INFO',
                            f' ==> service status is: {status}')
            return service_status.text
        except requests.exceptions.ReadTimeout as e:
            self.state.logaction('INFO', f'Node status check timed out: {e.errno}, {e.strerror}')
        return "Timed Out"

    def check_stack_state(self, stack_id=None):
        self.state.logaction('INFO', " ==> checking stack state")
        cfn = boto3.client('cloudformation', region_name=self.state.forgestate['region'])
        try:
            stack_state = cfn.describe_stacks(StackName=stack_id if stack_id else self.stack_name)
        except botocore.exceptions.ClientError as e:
            if "does not exist" in e.response['Error']['Message']:
                self.state.logaction('INFO', f'Stack {self.stack_name} does not exist')
                return
        return stack_state['Stacks'][0]['StackStatus']

    def spinup_remaining_nodes(self):
        self.state.logaction('INFO', "Spinning up any remaining nodes in stack")
        cfn = boto3.client('cloudformation', region_name=self.state.forgestate['region'])
        spinup_parms = self.state.forgestate['stack_parms']
        spinup_parms = self.update_parm(spinup_parms, 'ClusterNodeMax', self.state.forgestate['appnodemax'])
        spinup_parms = self.update_parm(spinup_parms, 'ClusterNodeMin', self.state.forgestate['appnodemin'])
        if 'preupgrade_jira_version' in self.state.forgestate:
            spinup_parms = self.update_parm(spinup_parms, 'JiraVersion', self.state.forgestate['new_version'])
        if 'preupgrade_confluence_version' in self.state.forgestate:
            spinup_parms = self.update_parm(spinup_parms, 'ConfluenceVersion', self.state.forgestate['new_version'])
            spinup_parms = self.update_parm(spinup_parms, 'SynchronyClusterNodeMax', self.state.forgestate['syncnodemax'])
            spinup_parms = self.update_parm(spinup_parms, 'SynchronyClusterNodeMin', self.state.forgestate['syncnodemin'])
        self.state.logaction('INFO', f'Spinup params: {spinup_parms}')
        update_stack = cfn.update_stack(
            StackName=self.stack_name,
            Parameters=spinup_parms,
            UsePreviousTemplate=True,
            Capabilities=['CAPABILITY_IAM'],
        )
        self.wait_stack_action_complete("UPDATE_IN_PROGRESS")
        self.state.logaction('INFO', "Stack restored to full node count")
        return

## Stack - Major Action Methods

    def upgrade(self, env, new_version):
        self.state.logaction('INFO', f'Beginning upgrade for {self.stack_name}')
        self.state.update('action', 'upgrade')
        self.state.update('environment', env)
        self.state.update('new_version', new_version)
        self.state.update('region', self.setRegion(env))
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
        self.state.logaction('INFO', f'Completed upgrade for {self.stack_name} at {env} to version {new_version}')
        self.state.logaction('INFO', "Final state")
        self.state.archive()
        # return forgestate[stack_name]['last_action_log']
        return

    def destroy(self, env):
        self.state.logaction('INFO', f'Destroying stack {self.stack_name} in {env}')
        self.state.update('action', 'destroy')
        self.state.update('environment', env)
        self.state.update('region', self.setRegion(env))
        cfn = boto3.client('cloudformation', region_name=self.state.forgestate['region'])
        try:
            stack_state = cfn.describe_stacks(StackName=self.stack_name)
        except botocore.exceptions.ClientError as e:
            if "does not exist" in e.response['Error']['Message']:
                self.state.logaction('INFO', f'Stack {stack_name} does not exist')
                return
        stack_id = stack_state['Stacks'][0]['StackId']
        delete_stack = cfn.delete_stack(StackName=self.stack_name)
        self.wait_stack_action_complete("DELETE_IN_PROGRESS", stack_id)
        self.state.logaction('INFO', f'Destroy complete for stack {self.stack_name}: {delete_stack}')
        self.state.logaction('INFO', "Final state")
        self.state.archive()
        return