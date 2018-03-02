# imports
import json
import time
from collections import defaultdict
from datetime import datetime
from pprint import pprint

import boto3
import botocore
import requests
from flask import Flask, request, session, redirect, url_for, \
    render_template, flash
from flask_restful import Api, Resource

# global configuration

SECRET_KEY = 'key_to_the_forge'
INFO = "INFO"
ERROR = "ERROR"

# using dict of dicts called forgestate to track state of all actions
forgestate = defaultdict(dict)

# create and initialize app
app = Flask(__name__)
app.config.from_object(__name__)
api = Api(app)

##
#### REST Endpoint classes
##

class hello(Resource):
    def get(self):
        return {'hello': 'world'}

class test(Resource):
    def get(self, env, stack_name, new_version):
        # use this endpoint to test new functionality without impacting existing endpoints
        forgestate = defaultdict(dict)
        forgestate = forgestate_update(forgestate, stack_name, 'action', 'test')
        forgestate = forgestate_update(forgestate, stack_name, 'environment', env)
        forgestate = forgestate_update(forgestate, stack_name, 'stack_name', stack_name)
        forgestate = forgestate_update(forgestate, stack_name, 'new_version', new_version)
        if env == 'prod':
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-west-2')
        else:
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-east-1')
        forgestate = get_stack_current_state(forgestate, stack_name)
        forgestate[stack_name]['appnodemax'] = '4'
        forgestate[stack_name]['appnodemin'] = '4'
        forgestate[stack_name]['syncnodemin'] = '2'
        forgestate[stack_name]['syncnodemax'] = '2'
        spinup_remaining_nodes(forgestate, stack_name)
        last_action_log(forgestate, stack_name, "Final state")
        return forgestate[stack_name]['last_action_log']


class clear(Resource):
    def get(self, stack_name):
        forgestate_clear(forgestate, stack_name)
        last_action_log(forgestate, stack_name, INFO, "Log cleared")
        return "forgestate[stack_name] cleared"


class upgrade(Resource):
    def get(self, env, stack_name, new_version):
        forgestate = defaultdict(dict)
        forgestate_clear(forgestate, stack_name)
        last_action_log(forgestate, stack_name, INFO, "Beginning upgrade")
        forgestate = forgestate_update(forgestate, stack_name, 'action', 'upgrade')
        forgestate = forgestate_update(forgestate, stack_name, 'environment', env)
        forgestate = forgestate_update(forgestate, stack_name, 'stack_name', stack_name)
        forgestate = forgestate_update(forgestate, stack_name, 'new_version', new_version)
        forgestate = forgestate_update(forgestate, stack_name, 'region', getRegion(env))

        # block traffic at vtm
        # get pre-upgrade state information
        get_stack_current_state(forgestate, stack_name)
        # spin stack down to 0 nodes
        spindown_to_zero_appnodes(forgestate, stack_name)
        # change template if required
        # spin stack up to 1 node on new release version
        spinup_to_one_appnode(forgestate, stack_name)
        # spinup remaining appnodes in stack if needed
        if forgestate[stack_name]['appnodemin'] != "1":
            spinup_remaining_nodes(forgestate, stack_name)
        elif 'syncnodemin' in forgestate[stack_name].keys() and forgestate[stack_name][
            'syncnodemin'] != "1":
            spinup_remaining_nodes(forgestate, stack_name)
        # wait for remaining nodes to respond ???
        # enable traffic at VTM
        last_action_log(forgestate, stack_name, INFO,
                        "Completed upgrade for " + stack_name + " at " + env + " to version " + new_version)
        last_action_log(forgestate, stack_name, INFO, "Final state")
        return forgestate[stack_name]['last_action_log']


class clone(Resource):
    def get(self, app_type, stack_name, rdssnap, ebssnap):
        forgestate[stack_name]['environment'] = 'stg'
        forgestate[stack_name]['region'] = getRegion('stg')

        if app_type.lower == 'jira':
            set_clone_params_jira(forgestate, ebssnap, rdssnap, stack_name)
        if app_type.lower == 'confluence':
            set_clone_params_confluence(forgestate, ebssnap, rdssnap, stack_name)

        create(forgestate, stack_name)
        return forgestate[stack_name]['last_action_log']


def set_clone_params_jira(forgestate, rdssnap, ebssnap, stack_name):
    parameters = [
        {'ParameterKey': 'BusinessUnit', 'ParameterValue': 'Workplace-Technology'},
        {'ParameterKey': 'TomcatEnableLookups', 'ParameterValue': 'false'},
        {'ParameterKey': 'DBIops', 'ParameterValue': '1000'},
        {'ParameterKey': 'ExternalSubnets', 'ParameterValue': 'subnet-df0c3597,subnet-f1fb87ab'},
        {'ParameterKey': 'JiraProduct', 'ParameterValue': 'All'},
        {'ParameterKey': 'TomcatMinSpareThreads', 'ParameterValue': '10'},
        {'ParameterKey': 'DBMaxWaitMillis', 'ParameterValue': '10000'},
        {'ParameterKey': 'InternalSubnets', 'ParameterValue': 'subnet-df0c3597,subnet-f1fb87ab'},
        {'ParameterKey': 'ClusterNodeSize', 'ParameterValue': '50'},
        {'ParameterKey': 'DBTestOnBorrow', 'ParameterValue': 'false'},
        {'ParameterKey': 'DBMultiAZ', 'ParameterValue': 'true'},
        {'ParameterKey': 'JiraVersion', 'ParameterValue': '7.7.0'},
        {'ParameterKey': 'JvmHeapOverride', 'ParameterValue': ''},
        {'ParameterKey': 'DBRemoveAbandoned', 'ParameterValue': 'true'},
        {'ParameterKey': 'DBInstanceClass', 'ParameterValue': 'db.t2.medium'},
        {'ParameterKey': 'DBMasterUserPassword', 'ParameterValue': 'password1234'},
        {'ParameterKey': 'TomcatProxyPort', 'ParameterValue': '443'},
        {'ParameterKey': 'ClusterNodeInstanceType', 'ParameterValue': 't2.medium'},
        {'ParameterKey': 'DBMinIdle', 'ParameterValue': '10'},
        {'ParameterKey': 'DBPassword', 'ParameterValue': 'G49uTtAEBmtU'},
        {'ParameterKey': 'TomcatScheme', 'ParameterValue': 'https'},
        {'ParameterKey': 'ClusterNodeMin', 'ParameterValue': '1'},
        {'ParameterKey': 'SSLCertificateName', 'ParameterValue': ''},
        {'ParameterKey': 'DBStorage', 'ParameterValue': '200'},
        {'ParameterKey': 'TomcatMaxThreads', 'ParameterValue': '200'},
        {'ParameterKey': 'ClusterNodeMax', 'ParameterValue': '1'},
        {'ParameterKey': 'DBMaxIdle', 'ParameterValue': '20'},
        {'ParameterKey': 'EBSSnapshotId', 'ParameterValue': ebssnap},
        {'ParameterKey': 'TomcatAcceptCount', 'ParameterValue': '10'},
        {'ParameterKey': 'DBStorageType', 'ParameterValue': 'General Purpose (SSD)'},
        {'ParameterKey': 'VPC', 'ParameterValue': 'vpc-320c1355'},
        {'ParameterKey': 'CidrBlock', 'ParameterValue': '0.0.0.0/0'},
        {'ParameterKey': 'TomcatSecure', 'ParameterValue': 'true'},
        {'ParameterKey': 'DBMinEvictableIdleTimeMillis', 'ParameterValue': '180000'},
        {'ParameterKey': 'StartCollectd', 'ParameterValue': 'true'},
        {'ParameterKey': 'TomcatRedirectPort', 'ParameterValue': '8443'},
        {'ParameterKey': 'JiraDownloadUrl', 'ParameterValue': ''},
        {'ParameterKey': 'DBTestWhileIdle', 'ParameterValue': 'true'},
        {'ParameterKey': 'HostedZone', 'ParameterValue': 'wpt.atlassian.com.'},
        {'ParameterKey': 'CatalinaOpts', 'ParameterValue': '-Datlassian.mail.senddisabled=true -Datlassian.mail.fetchdisabled=true -Datlassian.mail.popdisabled=true'},
        {'ParameterKey': 'CustomDnsName', 'ParameterValue': 'hr-jira.stg.internal.atlassian.com'},
        {'ParameterKey': 'TomcatContextPath', 'ParameterValue': '/jira'},
        {'ParameterKey': 'DBRemoveAbandonedTimeout', 'ParameterValue': '60'},
        {'ParameterKey': 'AssociatePublicIpAddress', 'ParameterValue': 'false'},
        {'ParameterKey': 'DBPoolMinSize', 'ParameterValue': '20'},
        {'ParameterKey': 'DBTimeBetweenEvictionRunsMillis', 'ParameterValue': '60000'},
        {'ParameterKey': 'KeyName', 'ParameterValue': 'WPE-GenericKeyPair-20161102'},
        {'ParameterKey': 'DBPoolMaxSize', 'ParameterValue': '20'},
        {'ParameterKey': 'TomcatProtocol', 'ParameterValue': 'HTTP/1.1'},
        {'ParameterKey': 'TomcatConnectionTimeout', 'ParameterValue': '20000'},
        {'ParameterKey': 'DBSnapshotName', 'ParameterValue': rdssnap}]

    forgestate[stack_name]['stack_parms'] = parameters


def set_clone_params_confluence(forgestate, rdssnap, ebssnap, stack_name):

    parameters=[
        ('AssociatePublicIpAddress', 'false'),
        ('AutologinCookieAge', '604800'),
        ('BastionAMIOS', 'Amazon-Linux-HVM'),
        ('BastionBanner', 'https://s3.amazonaws.com/quickstart-reference/linux/bastion/latest/scripts/banner_message.txt'),
        ('BastionInstanceType', 't2.micro'),
        ('CatalinaOpts', '-Datlassian.mail.senddisabled=true -Datlassian.mail.fetchdisabled=true -Datlassian.mail.popdisabled=true -Dconfluence.disable.mailpolling=true'),
        ('CidrBlock', '0.0.0.0/0'),
        ('ClusterNodeInstanceType', 'c5.xlarge'),
        ('ClusterNodeMax', '1'),
        ('ClusterNodeMin', '1'),
        ('ClusterNodeSize', '200'),
        ('ConfluenceDownloadUrl', ''),
        ('ConfluenceVersion', '6.8.0-m44'),
        ('CustomDnsName', 'extranet.stg.internal.atlassian.com'),
        ('DBAcquireIncrement', '3'),
        ('DBIdleTestPeriod', '0'),
        ('DBInstanceClass', 'db.t2.medium'),
        ('DBIops', '1000'),
        ('DBMasterUserPassword', 'password1234'),
        ('DBMaxStatements', '0'),
        ('DBMultiAZ', 'false'),
        ('DBPassword', 'password1234'),
        ('DBPoolMaxSize', '60'),
        ('DBPoolMinSize', '10'),
        ('DBPreferredTestQuery', ''),
        ('DBSnapshotId', ''),
        ('DBSnapshotName', rdssnap),
        ('DBStorage', '200'),
        ('DBStorageType', 'General Purpose (SSD'),
        ('DBTimeout', '0'),
        ('DBValidate', 'false'),
        ('EBSSnapshotId', ebssnap),
        ('EnableBanner', 'false'),
        ('EnableTCPForwarding', 'false'),
        ('EnableX11Forwarding', 'false'),
        ('ExternalSubnets', 'subnet-df0c3597,subnet-f1fb87ab'),
        ('HostedZone', 'wpt.atlassian.com.'),
        ('InternalSubnets', 'subnet-df0c3597,subnet-f1fb87ab'),
        ('JvmHeapOverride', ''),
        ('KeyName', 'WPE-GenericKeyPair-20161102'),
        ('NumBastionHosts', '1'),
        ('SSLCertificateName', ''),
        ('StartCollectd', 'true'),
        ('SubDomainName', 'false'),
        ('SynchronyClusterNodeMax', '1'),
        ('SynchronyClusterNodeMin', '1'),
        ('SynchronyNodeInstanceType', 't2.medium'),
        ('TomcatAcceptCount', '10'),
        ('TomcatConnectionTimeout', '20000'),
        ('TomcatContextPath', ''),
        ('TomcatDefaultConnectorPort', '8080'),
        ('TomcatEnableLookups', 'false'),
        ('TomcatMaxThreads', '48'),
        ('TomcatMinSpareThreads', '10'),
        ('TomcatProtocol', 'HTTP/1.1'),
        ('TomcatProxyPort', '443'),
        ('TomcatRedirectPort', '8443'),
        ('TomcatScheme', 'https'),
        ('TomcatSecure', 'true'),
        ('VPC', 'vpc-320c1355'),
     ],

    forgestate[stack_name]['stack_parms'] = parameters

class fullrestart(Resource):
    def get(self, env, stack_name):
        forgestate = defaultdict(dict)
        forgestate_clear(forgestate, stack_name)
        last_action_log(forgestate, stack_name, INFO, "Beginning full restart")
        if env == 'prod':
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-west-2')
        else:
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-east-1')
        forgestate,instancelist = get_nodes_in_stack(forgestate, stack_name)
        shutdown_all_apps = shutdown_node_app(forgestate, stack_name, instancelist)
        for instance in instancelist:
            startup = start_node_app(forgestate, stack_name, [instance])
        last_action_log(forgestate, stack_name, INFO, "Final state")
        return(forgestate[stack_name]['last_action_log'])


class rollingrestart(Resource):
    def get(self, env, stack_name):
        forgestate = defaultdict(dict)
        forgestate_clear(forgestate, stack_name)
        last_action_log(forgestate, stack_name, INFO, "Beginning rolling restart")

        if env == 'prod':
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-west-2')
        else:
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-east-1')
        forgestate,instancelist = get_nodes_in_stack(forgestate, stack_name)
        for instance in instancelist:
            shutdown = shutdown_node_app(forgestate, stack_name, [instance])
            startup = start_node_app(forgestate, stack_name, [instance])
        last_action_log(forgestate, stack_name, INFO, "Final state")
        return(forgestate[stack_name]['last_action_log'])


class destroy(Resource):
    def get(self, env, stack_name):
        forgestate = defaultdict(dict)
        forgestate_clear(forgestate, stack_name)

        if env == 'prod':
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-west-2')
        else:
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-east-1')

        destroy_stack(forgestate, stack_name)

        last_action_log(forgestate, stack_name, INFO, "Final state")
        return(forgestate[stack_name]['last_action_log'])

class create(Resource):
    def get(self, env, stack_name, rdssnap, ebssnap):
        forgestate = defaultdict(dict)
        forgestate_clear(forgestate, stack_name)

        cfn = boto3.client('cloudformation', region_name='us-east-1')
        try:
            stack_details = cfn.describe_stacks(StackName='eacj-stg')
        except botocore.exceptions.ClientError as e:
            print(e.args[0])

        if env == 'prod':
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-west-2')
        else:
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-east-1')

        forgestate[stack_name]['stack_parms'] = defaultdict(dict)

        set_clone_params_jira(forgestate, rdssnap, ebssnap, stack_name)
        create_stack(forgestate, stack_name)

        last_action_log(forgestate, stack_name, INFO, "Final state")
        return(forgestate[stack_name]['last_action_log'])


class status(Resource):
    def get(self, stack_name):
        forgestate = defaultdict(dict)
        forgestate[stack_name] = forgestate_read(stack_name)
        return forgestate[stack_name]['last_action_log']


class serviceStatus(Resource):
    def get(self, env, stack_name):
        return "RUNNING"

        # forgestate = defaultdict(dict)
        # forgestate[stack_name] = forgestate_read(stack_name)
        # forgestate[stack_name]['region'] = getRegion(env)
        # cfn = boto3.client('cloudformation', region_name=forgestate[stack_name]['region'])
        # # forgestate[stack_name]['tomcatcontextpath'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'TomcatContextPath'][0]
        #
        # try:
        #     stack_details = cfn.describe_stacks(StackName=stack_name)
        # except botocore.exceptions.ClientError as e:
        #     print(e.args[0])
        #     return
        # forgestate[stack_name]['lburl'] = getLburl(stack_details, stack_name)
        #
        # return check_service_status(forgestate, stack_name)


class stackState(Resource):
    def get(self, env, stack_name):
        forgestate = defaultdict(dict)
        forgestate[stack_name] = forgestate_read(stack_name)
        forgestate[stack_name]['region'] = getRegion(env)
        return check_stack_state(forgestate, stack_name)


class actionReadyToStart(Resource):
    def get(self):
        return actionReadyToStartRenderTemplate()


api.add_resource(hello, '/hello')
api.add_resource(test, '/test/<env>/<stack_name>/<new_version>')
api.add_resource(clear, '/clear/<stack_name>')
api.add_resource(upgrade, '/upgrade/<env>/<stack_name>/<new_version>')
api.add_resource(clone, '/clone/<app_type>/<stack_name>/<rdssnap>/<ebssnap>')
api.add_resource(fullrestart, '/fullrestart/<env>/<stack_name>')
api.add_resource(rollingrestart, '/rollingrestart/<env>/<stack_name>')
api.add_resource(create, '/create/<env>/<stack_name>/<rdssnap>/<ebssnap>')
api.add_resource(destroy, '/destroy/<env>/<stack_name>')
api.add_resource(status, '/status/<stack_name>')
api.add_resource(serviceStatus, '/serviceStatus/<env>/<stack_name>')
api.add_resource(stackState, '/stackState/<env>/<stack_name>')
api.add_resource(actionReadyToStart, '/actionReadyToStart')

##
#### stack action functions
##


def get_stack_current_state(forgestate, stack_name):
    last_action_log(forgestate, stack_name, INFO, "Getting pre-upgrade stack state")
    # store outcome in forgestate[stack_name]
    cfn = boto3.client('cloudformation', region_name=forgestate[stack_name]['region'])
    try:
        stack_details = cfn.describe_stacks(StackName=stack_name)
    except botocore.exceptions.ClientError as e:
        print(e.args[0])
        return
    # let's store the parms (list of dicts) if they haven't been already stored
    if forgestate[stack_name].get('stack_parms'):
        print("stack parms already stored")
    else:
        forgestate[stack_name]['stack_parms'] = stack_details['Stacks'][0]['Parameters']
    forgestate[stack_name]['appnodemax'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'ClusterNodeMax' ][0]
    forgestate[stack_name]['appnodemin'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'ClusterNodeMin'][0]
    forgestate[stack_name]['tomcatcontextpath'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'TomcatContextPath'][0]
    # force lburl to always be http as we offoad SSL at the VTM before traffic hits ELB/ALB
    forgestate[stack_name]['lburl'] = getLburl(forgestate, stack_details, stack_name)

    # all the following parms are dependent on stack type and will fail list index out of range when not matching so wrap in try by apptype
    # versions in different parms relative to products - we should probably abstract the product
    # connie
    try:
        forgestate[stack_name]['preupgrade_confluence_version'] = \
            [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
             p['ParameterKey'] == 'ConfluenceVersion'][0]
        # synchrony only exists for connie
        forgestate[stack_name]['syncnodemax'] = \
            [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
             p['ParameterKey'] == 'SynchronyClusterNodeMax'][0]
        forgestate[stack_name]['syncnodemin'] = \
            [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
             p['ParameterKey'] == 'SynchronyClusterNodeMin'][0]
    except:
        last_action_log(forgestate, stack_name, INFO, "Not confluence")
    # jira
    try:
        forgestate[stack_name]['preupgrade_jira_version'] = \
            [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
             p['ParameterKey'] == 'JiraVersion'][0]
    except:
        last_action_log(forgestate, stack_name, INFO, "Not jira")

    last_action_log(forgestate, stack_name, INFO, "End of testing")
    return forgestate


def getRegion(env):
    if env == 'prod':
        return 'us-west-2'
    else:
        return 'us-east-1'


def getLburl(forgestate, stack_details, stack_name):
    rawlburl = [p['OutputValue'] for p in stack_details['Stacks'][0]['Outputs'] if
                p['OutputKey'] == 'LoadBalancerURL'][0] + forgestate[stack_name][
                   'tomcatcontextpath']
    return rawlburl.replace("https", "http")


def spindown_to_zero_appnodes(forgestate, stack_name):
    last_action_log(forgestate, stack_name, INFO, "Spinning stack down to 0 nodes")
    cfn = boto3.client('cloudformation', region_name=forgestate[stack_name]['region'])
    spindown_parms = forgestate[stack_name]['stack_parms']
    spindown_parms = update_parm(spindown_parms, 'ClusterNodeMax', '0')
    spindown_parms = update_parm(spindown_parms, 'ClusterNodeMin', '0')
    if 'preupgrade_confluence_version' in forgestate[stack_name]:
        spindown_parms = update_parm(spindown_parms, 'SynchronyClusterNodeMax', '0')
        spindown_parms = update_parm(spindown_parms, 'SynchronyClusterNodeMin', '0')
    last_action_log(forgestate, stack_name, INFO, f'Spindown params: {spindown_parms}')
    update_stack = cfn.update_stack(
        StackName=stack_name,
        Parameters=spindown_parms,
        UsePreviousTemplate=True,
        Capabilities=['CAPABILITY_IAM'],
    )
    last_action_log(forgestate, stack_name, INFO, str(update_stack))
    wait_stackupdate_complete(forgestate, stack_name)
    return forgestate


def spinup_to_one_appnode(forgestate, stack_name):
    last_action_log(forgestate, stack_name, INFO, "Spinning stack up to one appnode")
    # for connie 1 app node and 1 synchrony
    cfn = boto3.client('cloudformation', region_name=forgestate[stack_name]['region'])
    spinup_parms = forgestate[stack_name]['stack_parms']
    spinup_parms = update_parm(spinup_parms, 'ClusterNodeMax', '1')
    spinup_parms = update_parm(spinup_parms, 'ClusterNodeMin', '1')
    if 'preupgrade_jira_version' in forgestate[stack_name]:
        spinup_parms = update_parm(spinup_parms, 'JiraVersion', forgestate[stack_name]['new_version'])
    if 'preupgrade_confluence_version' in forgestate[stack_name]:
        spinup_parms = update_parm(spinup_parms, 'ConfluenceVersion', forgestate[stack_name]['new_version'])
        spinup_parms = update_parm(spinup_parms, 'SynchronyClusterNodeMax', '1')
        spinup_parms = update_parm(spinup_parms, 'SynchronyClusterNodeMin', '1')
    last_action_log(forgestate, stack_name, INFO, f'Spinup params: {spinup_parms}')
    update_stack = cfn.update_stack(
        StackName=stack_name,
        Parameters=spinup_parms,
        UsePreviousTemplate=True,
        Capabilities=['CAPABILITY_IAM'],
    )
    wait_stackupdate_complete(forgestate, stack_name)
    validate_service_responding(forgestate, stack_name)
    last_action_log(forgestate, stack_name, INFO, f'Update stack: {update_stack}')
    return forgestate


def spinup_remaining_nodes(forgestate, stack_name):
    last_action_log(forgestate, stack_name, INFO, "Spinning up any remaining nodes in stack")
    cfn = boto3.client('cloudformation', region_name=forgestate[stack_name]['region'])
    spinup_parms = forgestate[stack_name]['stack_parms']
    spinup_parms = update_parm(spinup_parms, 'ClusterNodeMax', forgestate[stack_name]['appnodemax'])
    spinup_parms = update_parm(spinup_parms, 'ClusterNodeMin', forgestate[stack_name]['appnodemin'])
    if 'preupgrade_jira_version' in forgestate[stack_name]:
        spinup_parms = update_parm(spinup_parms, 'JiraVersion', forgestate[stack_name]['new_version'])
    if 'preupgrade_confluence_version' in forgestate[stack_name]:
        spinup_parms = update_parm(spinup_parms, 'ConfluenceVersion', forgestate[stack_name]['new_version'])
        spinup_parms = update_parm(spinup_parms, 'SynchronyClusterNodeMax', forgestate[stack_name]['syncnodemax'])
        spinup_parms = update_parm(spinup_parms, 'SynchronyClusterNodeMin', forgestate[stack_name]['syncnodemin'])
    last_action_log(forgestate, stack_name, INFO, f'Spinup params: {spinup_parms}')
    update_stack = cfn.update_stack(
        StackName=stack_name,
        Parameters=spinup_parms,
        UsePreviousTemplate=True,
        Capabilities=['CAPABILITY_IAM'],
    )
    wait_stackupdate_complete(forgestate, stack_name)
    last_action_log(forgestate, stack_name, INFO, "Stack restored to full node count")
    return forgestate


def destroy_stack(forgestate, stack_name):
    last_action_log(forgestate, stack_name, INFO, f'Destroying stack {stack_name}')
    cfn = boto3.client('cloudformation', region_name=forgestate[stack_name]['region'])
    stack_state = cfn.describe_stacks(StackName=stack_name)

    stack_id = stack_state['Stacks'][0]['StackId']
    delete_stack = cfn.delete_stack(
        StackName=stack_name,
    )
    wait_stackdestroy_complete(forgestate, stack_name, stack_id) # id must be used to check deletion
    last_action_log(forgestate, stack_name, INFO, f'Destroyed stack: {delete_stack}')
    return forgestate


def create_stack(forgestate, stack_name):
    last_action_log(forgestate, stack_name, INFO, f'Creating stack: {stack_name}')
    cfn = boto3.client('cloudformation', region_name=forgestate[stack_name]['region'])
    stack_parms = forgestate[stack_name]['stack_parms']
    last_action_log(forgestate, stack_name, INFO, f'Spinup params: {stack_parms}')
    create_stack = cfn.create_stack(
        StackName=stack_name,
        Parameters=stack_parms,
        # TemplateBody='',
        TemplateURL='https://s3.amazonaws.com/wpe-public-software/JiraSTGorDR.template.yaml',
        Capabilities=['CAPABILITY_IAM'],
    )
    wait_stackcreate_complete(forgestate, stack_name)

    last_action_log(forgestate, stack_name, INFO, f'Create has begun: {create_stack}')
    return forgestate


def get_nodes_in_stack(forgestate, stack_name):
    ec2 = boto3.resource('ec2', region_name=forgestate[stack_name]['region'])
    filters = [
        {'Name': 'tag:aws:cloudformation:stack-name', 'Values': [stack_name]},
        {'Name': 'tag:aws:cloudformation:logical-id', 'Values': ['ClusterNodeGroup']},
        {'Name': 'instance-state-name', 'Values': ['pending', 'running']},
    ]
    instancelist = []
    for i in ec2.instances.filter(Filters=filters):
        instancedict = { i.instance_id: i.private_ip_address }
        instancelist.append(instancedict)
    return(forgestate, instancelist)


def shutdown_node_app(forgestate, stack_name, instancelist):
    cmd_id_list = []
    for instance in [list(d.keys())[0] for d in instancelist]:
        last_action_log(forgestate, stack_name, INFO, f'Shutting down {instance}')
        cmd = "/etc/init.d/confluence stop"
        cmd_id_list.append(ssm_send_command(forgestate, stack_name, instance, cmd))
    for cmd_id in cmd_id_list:
        result = ""
        while result != 'Success' and result != 'Failed':
            result, cmd_instance = ssm_cmd_check(forgestate, stack_name, cmd_id)
            time.sleep(5)
        if result == 'Failed':
            last_action_log(forgestate, stack_name, ERROR, f'Shutdown result for {cmd_instance}: {result}')
        else:
            last_action_log(forgestate, stack_name, INFO, f'Shutdown result for {cmd_instance}: {result}')
    return(forgestate)


def start_node_app(forgestate, stack_name, instancelist):
    cmd_id_list = []
    #for instance in [d.keys() for d in instancelist]:
    for instancedict in instancelist:
        instance = list(instancedict.keys())[0]
        node_ip = list(instancedict.values())[0]
        last_action_log(forgestate, stack_name, INFO, f'Starting up {instance}')
        cmd = "/etc/init.d/confluence start"
        cmd_id = ssm_send_command(forgestate, stack_name, instance, cmd)
        result = ""
        while result != 'Success' and result != 'Failed':
            result, cmd_instance = ssm_cmd_check(forgestate, stack_name, cmd_id)
            time.sleep(5)
        if result == 'Failed':
            last_action_log(forgestate, stack_name, ERROR, f'Startup result for {cmd_instance}: {result}')
        else:
            result = ""
            while result != '{"state":"RUNNING"}':
                result = check_node_status(forgestate, stack_name, node_ip)
                last_action_log(forgestate, stack_name, INFO, f'Startup result for {cmd_instance}: {result}')
                time.sleep(30)
    return(forgestate)


def app_active_in_lb(forgestate, node):
    return(forgestate)

##
#### Common functions
##
def ssm_send_command(forgestate, stack_name, instance, cmd):
    ssm = boto3.client('ssm', region_name=forgestate[stack_name]['region'])
    ssm_command = ssm.send_command(
        InstanceIds=[instance],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [cmd], 'executionTimeout': ["900"]},
        OutputS3BucketName='wpe-logs',
        OutputS3KeyPrefix='run-command-logs'
    )
    print("for command: ", cmd, " command_Id is: ", ssm_command['Command']['CommandId'])
    if ssm_command['ResponseMetadata']['HTTPStatusCode'] == 200:
        return (ssm_command['Command']['CommandId'])


def ssm_cmd_check(forgestate, stack_name, cmd_id):
    ssm = boto3.client('ssm', region_name=forgestate[stack_name]['region'])
    list_command = ssm.list_commands(CommandId=cmd_id)
    cmd_status = list_command[u'Commands'][0][u'Status']
    instance = list_command[u'Commands'][0][u'InstanceIds'][0]
    # result = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=instance)
    # if status == 'Success':
    #     pprint.pprint(result[u'StandardOutputContent'])
    return (cmd_status, instance)


def forgestate_write(stack_state, stack_name):
    with open(stack_name + '.json', 'w') as outfile:
        json.dump(stack_state, outfile)
    outfile.close()
    return


def forgestate_read(stack_name):
    try:
        with open(stack_name + '.json', 'r') as infile:
            stack_state = json.load(infile)
            return stack_state
    except FileNotFoundError:
        stack_state = {'last_action_log': []}
        pass
    except Exception as e:
        print('type is:', e.__class__.__name__)
        print(e.strerror)
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        message = template.format(type(e).__name__, e.args)
        return ('failed')
    # except FileNotFoundError:
    #     pass
    return(stack_state)


def forgestate_update(forgestate, stack_name, update_key, update_value):
    if not stack_name in forgestate:
        forgestate[stack_name] = forgestate_read(stack_name)
    forgestate[stack_name][update_key] = update_value
    forgestate_write(forgestate[stack_name], stack_name)
    return (forgestate)


def forgestate_clear(forgestate, stack_name):
    if stack_name in forgestate:
        forgestate.pop(stack_name)
    forgestate[stack_name]['last_action_log'] = []
    return (forgestate)


def last_action_log(forgestate, stack_name, level, log_this):
    print(f'{datetime.now()} {level} {log_this}')

    try:
        last_action_log = forgestate[stack_name]['last_action_log']
    except KeyError:
        last_action_log = []
    last_action_log.insert(0, f'{datetime.now()} {level} {log_this}')
    forgestate = forgestate_update(forgestate, stack_name, 'last_action_log', last_action_log)
    return (forgestate)


def update_parm(parmlist, parmkey, parmvalue):
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


def check_stack_state(forgestate, stack_name, stack_id):
    last_action_log(forgestate, stack_name, INFO, " ==> checking stack state")
    cfn = boto3.client('cloudformation', region_name=forgestate[stack_name]['region'])
    stack_state = cfn.describe_stacks(StackName=stack_id if stack_id else stack_name)
    return stack_state['Stacks'][0]['StackStatus']


def wait_stackupdate_complete(forgestate, stack_name):
    wait_stack_action_complete(forgestate, stack_name, "UPDATE_IN_PROGRESS")
    return


def wait_stackdestroy_complete(forgestate, stack_name, stack_id):
    wait_stack_action_complete(forgestate, stack_name, "DELETE_IN_PROGRESS", stack_id)
    return


def wait_stackcreate_complete(forgestate, stack_name):
    wait_stack_action_complete(forgestate, stack_name, "CREATE_IN_PROGRESS")
    return


def wait_stack_action_complete(forgestate, stack_name, in_progress_state, stack_id):
    last_action_log(forgestate, stack_name, INFO, "Waiting for stack action to complete")
    stack_state = check_stack_state(forgestate, stack_name)
    while stack_state == in_progress_state:
        last_action_log(forgestate, stack_name, INFO,
                        "====> stack_state is: " + stack_state)
        time.sleep(30)
        stack_state = check_stack_state(forgestate, stack_id if stack_id else stack_name)
    return

def check_node_status(forgestate, stack_name, node_ip):
    last_action_log(forgestate, stack_name, INFO,
                    f' ==> checking node status at {node_ip}/status')
    try:
        node_status = requests.get(f'http://{node_ip}:8080/status', timeout=5)
        last_action_log(forgestate, stack_name, INFO,
                        f' ==> node status is: {node_status.text}')
        return node_status.text
    except requests.exceptions.ReadTimeout as e:
        return "Timed Out"


def check_service_status(forgestate, stack_name):
    last_action_log(forgestate, stack_name, INFO,
                    " ==> checking service status at " + forgestate[stack_name][
                        'lburl'] + "/status")
    try:
        service_status = requests.get(forgestate[stack_name]['lburl'] + '/status', timeout=5)
        status = service_status.text if service_status.text else "...?"
        last_action_log(forgestate, stack_name, INFO,
                        f' ==> service status is: {status}')
        return service_status.text
    except requests.exceptions.ReadTimeout as e:
        last_action_log(forgestate, stack_name, INFO, f'Node status check timed out: {e.errno}, {e.strerror}')
    return "Timed Out"


def validate_service_responding(forgestate, stack_name):
    last_action_log(forgestate, stack_name, INFO, "Waiting for service to reply RUNNING on /status")
    service_state = check_service_status(forgestate, stack_name)
    while service_state != '{"state":"RUNNING"}':
        last_action_log(forgestate, stack_name, INFO,
                        "====> health check reports: " + service_state + " waiting for RUNNING " + str(
                            datetime.now()))
        time.sleep(60)
        service_state = check_service_status(forgestate, stack_name)
    last_action_log(forgestate, stack_name, INFO, stack_name + "/status now reporting RUNNING")
    return


def get_cfn_stacks_for_environment():
    cfn = boto3.client('cloudformation', region_name=session['region'])
    stack_name_list = []
    stack_list = cfn.list_stacks(
        StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE']
    )
    for stack in stack_list['StackSummaries']:
        stack_name_list.append(stack['StackName'])
    last_action_log(forgestate, 'general', INFO, f'Stack names: {stack_name_list}')
    return stack_name_list


@app.route('/')
def index():
    # saved_data = get_saved_data()
    # if 'forgetype' in forgestate[stack_name] and 'environment' in forgestate[stack_name]:
    #     gtg_flag = True
    #     stack_name_list = get_cfn_stacks_for_environment(forgestate[stack_name]['environment'])

    # use stg if no env selected
    if 'region' not in session:
        session['region'] = getRegion('stg')
        session['env'] = 'stg'
    session['action'] = 'none'
    return render_template('index.html')


@app.route('/upgrade')
def upgradeSetParams():
    return render_template('upgrade.html', stacks=getparms('upgrade'))


@app.route('/actionreadytostart')
def actionReadyToStartRenderTemplate():
    return render_template('actionreadytostart.html')


@app.route('/actionprogress/<action>/<stack_name>')
def actionprogress(action, stack_name):
    session['stack_name'] = stack_name
    flash(f'Action \'{action}\' on {stack_name} has begun', 'success')
    return render_template("actionprogress.html")


# Either stg or prod
@app.route('/setenv/<env>')
def env(env):
    session['region'] = getRegion(env)
    session['env'] = env
    flash(f'Environment selected: {env}', 'success')
    return redirect(url_for('index'))


# Ex. action could equal upgrade, rollingrestart, etc.
@app.route('/setaction/<action>')
def setaction(action):
    session['action'] = action
    envstacks=sorted(get_cfn_stacks_for_environment())
    return render_template(action + ".html", stacks=envstacks)


#@app.route('/getparms/upgrade')
@app.route('/getparms/<action>')
def getparms(action):
    return sorted(get_cfn_stacks_for_environment())


# @app.route('/go/stg/upgradeProgress')
@app.route('/go/<environment>/<action>Progress')
def progress(environment, action):
    print("in progress")
    print('env =', forgestate[stack_name]['environment'])
    print('action = ', forgestate[stack_name]['action'])
    if 'action' in forgestate[stack_name] and 'environment' in forgestate[stack_name]:
        return redirect(url_for('show_stacks'))
    else:
        return redirect(url_for('index'))


@app.route('/show_stacks')
def show_stacks():
    stack_name_list = sorted(get_cfn_stacks_for_environment())
    return render_template('stack_selection.html', stack_name_list=stack_name_list)


# @app.route('/stg/upgrade')
@app.route('/<env>/<action>', methods=['POST'])
def envact(env, action):
    print('after stack selection')
    for key in request.form:
        forgestate[stack_name]['selected_stack'] = key.split("_")[1]
    pprint(forgestate[stack_name])
    return render_template(action + 'Options.html')


if __name__ == '__main__':
    app.run(threaded=True, debug=True, host='0.0.0.0')
