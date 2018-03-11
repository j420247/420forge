from collections import defaultdict
from forgestate import Forgestate
import boto3
import botocore
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

## Stack - helper methods

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

    def get_current_state(self):
        self.state.logaction('INFO', f'Getting pre-upgrade stack state for {self.stack_name}')

        # store outcome in forgestate[stack_name]
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
        #self.state.write()
        return

## Stack - Major Actions

    def upgrade(self, env, new_version):
        self.state.logaction('INFO', f'Beginning upgrade for {self.stack_name}')

        self.state.update('action', 'upgrade')
        self.state.update('environment', env)
        self.state.update('new_version', new_version)
        self.state.update('region', self.setRegion(env))

        # block traffic at vtm
        # get pre-upgrade state information
        self.get_current_state()
        # # spin stack down to 0 nodes
        spindown_to_zero_appnodes()
        # # change template if required
        # # spin stack up to 1 node on new release version
        # spinup_to_one_appnode()
        # # spinup remaining appnodes in stack if needed
        # if forgestate[stack_name]['appnodemin'] != "1":
        #     spinup_remaining_nodes()
        # elif 'syncnodemin' in forgestate[stack_name].keys() and forgestate[stack_name][
        #     'syncnodemin'] != "1":
        #     spinup_remaining_nodes()
        # # wait for remaining nodes to respond ???
        # # enable traffic at VTM
        # last_action_log(forgestate, stack_name, INFO,
        #                 "Completed upgrade for " + stack_name + " at " + env + " to version " + new_version)
        # last_action_log(forgestate, stack_name, INFO, "Final state")
        # return forgestate[stack_name]['last_action_log']
        return
