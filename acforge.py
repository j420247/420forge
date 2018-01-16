# imports
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, jsonify, make_response
from flask_restful import reqparse, abort, Api, Resource
from datetime import datetime
from collections import defaultdict

import requests
import os
import json
import time
import boto3
from pprint import pprint

# configuration
# DATABASE = 'acforge.db'
# DEBUG = True
# USERNAME = 'admin'
# PASSWORD = 'admin'
SECRET_KEY = 'key_to_the_forge'
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
        # using dict of dicts called forgestate to track state of all actions
        forgestate = defaultdict(dict)
        # initialise log for stack
        forgestate[stack_name]['last_action_log'] = []

        last_action_log(forgestate, stack_name, "beginning testing " + str(datetime.now()))
        forgestate = forgestate_update(forgestate, stack_name, 'action', 'test')
        forgestate = forgestate_update(forgestate, stack_name, 'environment', env)
        forgestate = forgestate_update(forgestate, stack_name, 'stack_name', stack_name)
        forgestate = forgestate_update(forgestate, stack_name, 'new_version', new_version)
        if env == 'prod':
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-west-2')
        else:
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-east-1')
        forgestate = get_stack_current_state(forgestate, stack_name)

       # spinup_to_one_appnode(forgestate, stack_name)

        # forgestate[stack_name]['appnodemax'] = '4'
        # forgestate[stack_name]['appnodemin'] = '4'
        # forgestate[stack_name]['syncnodemin'] = '2'
        # forgestate[stack_name]['syncnodemax'] = '2'
        # forgestate[stack_name]['stack_parms'] = update_parm(forgestate[stack_name]['stack_parms'], 'ClusterNodeMax', '4')
        # forgestate[stack_name]['stack_parms'] = update_parm(forgestate[stack_name]['stack_parms'], 'ClusterNodeMin', '4')
        # forgestate[stack_name]['stack_parms'] = update_parm(forgestate[stack_name]['stack_parms'], 'SynchronyClusterNodeMax', '2')
        # forgestate[stack_name]['stack_parms'] = update_parm(forgestate[stack_name]['stack_parms'], 'SynchronyClusterNodeMin', '2')
        # spinup_remaining_nodes(forgestate, stack_name)
        # spinup_to_one_appnode(forgestate, stack_name)
        # # dummy up the numbers
        # forgestate[stack_name]['appnodemin'] = '2'
        # forgestate[stack_name]['appnodemax'] = '6'
        # forgestate[stack_name]['syncnodemin'] = '2'
        # forgestate[stack_name]['syncnodemax'] = '6'
        # pprint(forgestate[stack_name])
        # #        if originial stack had more than one node spin up to same as before
        # if forgestate[stack_name]['appnodemin'] != "1":
        #     spinup_remaining_nodes(forgestate, stack_name)
        # elif 'syncnodemin' in forgestate[stack_name].keys() and forgestate[stack_name]['syncnodemin'] != "1":
        #     spinup_remaining_nodes(forgestate, stack_name)
        # validate_service_responding(forgestate, stack_name)
        # print("final state")
        # spl = forgestate[stack_name]['last_action_log']
        #print(spl)
        last_action_log(forgestate, stack_name, "final state")
        return(forgestate[stack_name]['last_action_log'])

class clear(Resource):
    def get(self, stack_name):
        forgestate[stack_name].clear()
        last_action_log(forgestate, stack_name, "log cleared "+ str(datetime.now()))
        return "forgestate[stack_name] cleared"

class upgrade(Resource):
    def get(self, env, stack_name, new_version):
        forgestate = defaultdict(dict)
        last_action_log(forgestate, stack_name, "beginning upgrade " + str(datetime.now()))
        forgestate = forgestate_update(forgestate, stack_name, 'action', 'upgrade')
        forgestate = forgestate_update(forgestate, stack_name, 'environment', env)
        forgestate = forgestate_update(forgestate, stack_name, 'stack_name', stack_name)
        forgestate = forgestate_update(forgestate, stack_name, 'new_version', new_version)
        if env == 'prod':
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-west-2')
        else:
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-east-1')

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
        elif 'syncnodemin' in forgestate[stack_name].keys() and forgestate[stack_name]['syncnodemin'] != "1":
            spinup_remaining_nodes(forgestate, stack_name)
        # wait for remaining nodes to respond ???
        # enable traffic at VTM
        last_action_log(forgestate, stack_name, "completed upgrade for " + stack_name +" at " + env + " to version " + new_version)
        last_action_log(forgestate, stack_name, "final state")
        return(forgestate[stack_name]['last_action_log'])

class clone(Resource):
    def get(self, stack_name, rdssnap, ebssnap):
        forgestate[stack_name]['environment'] = 'stg'
        forgestate[stack_name]['region'] = 'us-east-1'

        forgestate[stack_name]['stack_parms'] = update_parm(forgestate[stack_name]['stack_parms'], 'DBSnapshotName', rdssnap)
        forgestate[stack_name]['stack_parms'] = update_parm(forgestate[stack_name]['stack_parms'], 'EBSSnapshotId', ebssnap)

        spinup_to_one_appnode(forgestate, stack_name)

        return(forgestate[stack_name]['last_action_log'])

class status(Resource):
    def get(self, stack_name):
        forgestate = defaultdict(dict)
        forgestate[stack_name] = forgestate_read(stack_name)
        return(forgestate[stack_name]['last_action_log'])


api.add_resource(hello, '/hello')
api.add_resource(test, '/test/<string:env>/<string:stack_name>/<string:new_version>')
api.add_resource(clear, '/clear/<string:stack_name>')
api.add_resource(upgrade, '/upgrade/<string:env>/<string:stack_name>/<string:new_version>')
api.add_resource(clone, '/clone/<app_type>/<string:stack_name>/<string:rdssnap>/<string:ebssnap>')
api.add_resource(status, '/status/<string:stack_name>')

##
#### stack action functions
##

def get_stack_current_state(forgestate, stack_name):
    last_action_log(forgestate, stack_name, "getting pre-upgrade stack state")

    # store outcome in forgestate[stack_name]
    cfn = boto3.client('cloudformation', region_name=forgestate[stack_name]['region'])
    stack_details = cfn.describe_stacks( StackName=stack_name )
    # lets store the parms (list of dicts) if they havnt been already stored

    if forgestate[stack_name].get('stack_parms'):
        print("stack parms already stored")
    else:
        forgestate[stack_name]['stack_parms'] = stack_details['Stacks'][0]['Parameters']

    forgestate[stack_name]['appnodemax'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'ClusterNodeMax' ][0]
    forgestate[stack_name]['appnodemin'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'ClusterNodeMin'][0]
    forgestate[stack_name]['lburl'] = [p['OutputValue'] for p in stack_details['Stacks'][0]['Outputs'] if p['OutputKey'] == 'LoadBalancerURL'][0]

    # all the following parms are dependent on stack type and will fail list index out of range when not matching so wrap in try by apptype
    # versions in different parms relative to products - we should probably abstract the product

    #connie
    try:
        forgestate[stack_name]['preupgrade_confluence_version'] = \
        [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
         p['ParameterKey'] == 'ConfluenceVersion'][0]
        # synchrony only exists for connie
        forgestate[stack_name]['syncnodemax'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                               p['ParameterKey'] == 'SynchronyClusterNodeMax'][0]
        forgestate[stack_name]['syncnodemin'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                               p['ParameterKey'] == 'SynchronyClusterNodeMin'][0]
    except:
        last_action_log(forgestate, stack_name, "not confluence")

    #jira
    try:
        forgestate[stack_name]['preupgrade_jira_version'] = \
        [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'JiraVersion'][0]
    except:
        last_action_log(forgestate, stack_name, "not jira")

    last_action_log(forgestate, stack_name, "end of testing")
    return(forgestate)

def spindown_to_zero_appnodes(forgestate, stack_name):

    last_action_log(forgestate, stack_name, "spinning stack down to 0 nodes")
    cfn = boto3.client('cloudformation', region_name=forgestate[stack_name]['region'])
    spindown_parms = forgestate[stack_name]['stack_parms']
    spindown_parms = update_parm(spindown_parms, 'ClusterNodeMax', '0')
    spindown_parms = update_parm(spindown_parms, 'ClusterNodeMin', '0')

    if 'preupgrade_confluence_version' in forgestate[stack_name]:
        spindown_parms = update_parm(spindown_parms, 'SynchronyClusterNodeMax', '0')
        spindown_parms = update_parm(spindown_parms, 'SynchronyClusterNodeMin', '0')

    last_action_log(forgestate, stack_name, str(spindown_parms))

    update_stack = cfn.update_stack(
        StackName=stack_name,
        Parameters=spindown_parms,
        UsePreviousTemplate=True,
        Capabilities=[ 'CAPABILITY_IAM' ],
    )
    last_action_log(forgestate, stack_name, str(update_stack))

    wait_stackupdate_complete(forgestate, stack_name)
    return(forgestate)

def spinup_to_one_appnode(forgestate, stack_name):
    last_action_log(forgestate, stack_name, "spinning stack up to one appnode")

    # for connie 1 app node and 1 synchrony
    cfn = boto3.client('cloudformation', region_name=forgestate[stack_name]['region'])
    spinup_parms = forgestate[stack_name]['stack_parms']
    spinup_parms = update_parm(spinup_parms, 'ClusterNodeMax', '1')
    spinup_parms = update_parm(spinup_parms, 'ClusterNodeMin', '1')

    if 'preupgrade_jira_version' in forgestate[stack_name]:
        spinup_parms = update_parm(spinup_parms, 'JiraVersion', forgestate[stack_name]['newversion'])
        #spinup_parms.append({'ParameterKey': 'JiraVersion', 'ParameterValue': forgestate[stack_name]['newversion']})
    if 'preupgrade_confluence_version' in forgestate[stack_name]:
        spinup_parms = update_parm(spinup_parms, 'ConfluenceVersion', forgestate[stack_name]['newversion'])
        spinup_parms = update_parm(spinup_parms, 'SynchronyClusterNodeMax', '1')
        spinup_parms = update_parm(spinup_parms, 'SynchronyClusterNodeMin', '1')
        # spinup_parms.append({ 'ParameterKey': 'ConfluenceVersion', 'ParameterValue': forgestate[stack_name]['newversion']})
        # spinup_parms.append({ 'ParameterKey': 'SynchronyClusterNodeMax', 'ParameterValue': '1' })
        # spinup_parms.append({ 'ParameterKey': 'SynchronyClusterNodeMin', 'ParameterValue': '1' })

    last_action_log(forgestate, stack_name, str(spinup_parms))

    update_stack = cfn.update_stack(
        StackName=stack_name,
        Parameters=spinup_parms,
        UsePreviousTemplate=True,
        Capabilities=[ 'CAPABILITY_IAM' ],
    )
    wait_stackupdate_complete()
    validate_service_responding()
    last_action_log(forgestate, stack_name, str(update_stack))
    return(forgestate)

def spinup_remaining_nodes(forgestate, stack_name):
    last_action_log(forgestate, stack_name, "spinning up any remaining nodes in stack")

    # for connie 1 app node and 1 synchrony
    cfn = boto3.client('cloudformation', region_name=forgestate[stack_name]['region'])
    spinup_parms = forgestate[stack_name]['stack_parms']
    spinup_parms = update_parm(spinup_parms, 'ClusterNodeMax', forgestate[stack_name]['appnodemax'])
    spinup_parms = update_parm(spinup_parms, 'ClusterNodeMin', forgestate[stack_name]['appnodemin'])
    # spinup_parms = [
    #     { 'ParameterKey': 'ClusterNodeMax', 'ParameterValue': forgestate[stack_name]['appnodemax'] },
    #     { 'ParameterKey': 'ClusterNodeMin', 'ParameterValue': forgestate[stack_name]['appnodemin'] },
    #     { 'ParameterKey': 'CustomDnsName', 'UsePreviousValue': True },
    # ]
    if 'preupgrade_jira_version' in forgestate[stack_name]:
        spinup_parms = update_parm(spinup_parms, 'JiraVersion', forgestate[stack_name]['newversion'])
        # spinup_parms.append({'ParameterKey': 'JiraVersion', 'ParameterValue': forgestate[stack_name]['newversion']})
    if 'preupgrade_confluence_version' in forgestate[stack_name]:
        spinup_parms = update_parm(spinup_parms, 'ConfluenceVersion', forgestate[stack_name]['newversion'])
        spinup_parms = update_parm(spinup_parms, 'SynchronyClusterNodeMax', forgestate[stack_name]['syncnodemax'])
        spinup_parms = update_parm(spinup_parms, 'SynchronyClusterNodeMin', forgestate[stack_name]['syncnodemin'])
        # spinup_parms.append({ 'ParameterKey': 'ConfluenceVersion', 'ParameterValue': forgestate[stack_name]['newversion']})
        # spinup_parms.append({ 'ParameterKey': 'SynchronyClusterNodeMax', 'ParameterValue': forgestate[stack_name]['syncnodemax'] })
        # spinup_parms.append({ 'ParameterKey': 'SynchronyClusterNodeMin', 'ParameterValue': forgestate[stack_name]['syncnodemin'] })

    last_action_log(forgestate, stack_name, str(spinup_parms))

    update_stack = cfn.update_stack(
        StackName=forgestate[stack_name]['stack'],
        Parameters=spinup_parms,
        UsePreviousTemplate=True,
        Capabilities=[ 'CAPABILITY_IAM' ],
    )
    wait_stackupdate_complete()
    last_action_log(forgestate, stack_name, "stack restored to full node count")

    return(forgestate)

##
#### Common functions
##
def forgestate_write(stack_state, stack_name):
    with open(stack_name+'.json', 'w') as outfile:
        json.dumps(stack_state, outfile)
    outfile.close()
    return

def forgestate_read(stack_name):
    try:
        with open(stack_name+'.json', 'r') as infile:
            stack_state = json.loads(stack_name, infile)
            return (stack_state)
    except Exception as e:
        print('type is:', e.__class__.__name__)
        pprint(e)
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
    return(forgestate)

def forgestate_clear(forgestate, stack_name):
    forgestate.pop(stack_name)
    return(forgestate)

def last_action_log(forgestate, stack_name, log_this):
    print(str(log_this))
    last_action_log = forgestate[stack_name]['last_action_log']
    last_action_log.insert(0,log_this)
    forgestate = forgestate_update(forgestate, stack_name, 'last_action_log', last_action_log)
    #forgestate[stack_name]['last_action_log'] = "\n".join([str(log_this), str(forgestate[stack_name]['last_action_log'])])
    return(forgestate)

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
#        dict.update((dict['ParameterValue'] = parmvalue) for k, v in dict.items() if v == parmkey)
    return(parmlist)

def check_stack_state(forgestate, stack_name):
    last_action_log(forgestate, stack_name, " ==> checking stack state ")
    cfn = boto3.client('cloudformation', region_name=forgestate[stack_name]['region'])
    stack_state = cfn.describe_stacks(StackName=forgestate[stack_name]['stack'])
    return(stack_state['Stacks'][0]['StackStatus'])

def wait_stackupdate_complete(forgestate, stack_name):
    last_action_log(forgestate, stack_name, "waiting for stack update to complete")
    stack_state = check_stack_state()
    while stack_state == "UPDATE_IN_PROGRESS":
        last_action_log(forgestate, stack_name, "====> stack_state is: " + stack_state + " waiting .... " + str(datetime.now()))
        time.sleep(30)
        stack_state = check_stack_state()
    return

def check_service_status(forgestate, stack_name):
    last_action_log(str(" ==> checking service status at " + forgestate[stack_name]['lburl'] + "/status"))
    service_status = requests.get(forgestate[stack_name]['lburl'] + '/status')
    return(service_status.text)

def validate_service_responding(forgestate, stack_name):
    last_action_log(forgestate, stack_name, "waiting for service to reply RUNNING on /status")
    service_state = check_service_status()
    while service_state != '{"state":"RUNNING"}' :
        last_action_log(forgestate, stack_name, "====> health check reports: " + service_state + " waiting for RUNNING " + str(datetime.now()))
        time.sleep(60)
        service_state = check_service_status()
    return

def get_cfn_stacks_for_environment(forgestate, stack_name, env):
    if env == 'prod':
        region = 'us-west-2'
    else:
        region = 'us-east-1'
    cfn = boto3.client('cloudformation', region_name=region)
    stack_list = cfn.list_stacks(
        StackStatusFilter=[ 'CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE' ]
    )
    stack_name_list = []
    for stack in stack_list['StackSummaries']:
        last_action_log(forgestate, stack_name, stack['StackName'])
        stack_name_list.append(stack['StackName'])
    return stack_name_list

# def put_saved_data(ckey,cvalue):
#     response = make_response(redirect(url_for('index')))
#     saved_data = get_saved_data()
#     saved_data[ckey] = cvalue
#     response.set_cookie('forgedata', json.dumps(saved_data))
#     return response

# def get_saved_data():
#     try:
#         saved_data = json.loads(request.cookies.get('forgedata'))
#     except TypeError:
#         saved_data = { }
#     pprint(saved_data)
#     return saved_data

@app.route('/')
def index():
    # saved_data = get_saved_data()
    if 'forgetype' in forgestate[stack_name] and 'environment' in forgestate[stack_name]:
        gtg_flag = True
        stack_name_list = get_cfn_stacks_for_environment(forgestate[stack_name]['environment'])
    return render_template('index.html')

#@app.route('/setenv/stg')
#@app.route('/setenv/prod')
@app.route('/setenv/<environment>')
def env(environment):
    forgestate[stack_name]['environment'] = environment
    print('env = ', forgestate[stack_name]['environment'])
    if 'action' in forgestate[stack_name] and 'environment' in forgestate[stack_name]:
        return redirect(url_for('show_stacks'))
    else:
        return redirect(url_for('index'))

#@app.route('/setaction/upgrade')
@app.route('/setaction/<string:action>')
def action(action):
    forgestate[stack_name]['action'] = action
    print('action = ', forgestate[stack_name]['action'])
    if 'action' in forgestate[stack_name] and 'environment' in forgestate[stack_name]:
        return redirect(url_for('show_stacks'))
    else:
        return redirect(url_for('index'))

#@app.route('/go/stg/upgradeProgress')
@app.route('/go/<environment>/<string:action>Progress')
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
    stack_name_list = sorted(get_cfn_stacks_for_environment(forgestate[stack_name]['environment']))
#    selected_stack = request.form['stack_selection']
#    print("selcted stack is ", selected_stack)
    return render_template('stack_selection.html', stack_name_list=stack_name_list)

#@app.route('/stg/upgrade')
@app.route('/<string:env>/<string:action>', methods=['POST'])
def envact(env, action):
    print('after stack selection')
    for key in request.form:
        forgestate[stack_name]['selected_stack'] = key.split("_")[1]
    pprint(forgestate[stack_name])
    return render_template(action + 'Options.html')

# @app.route('/upgrade.html', methods=['GET', 'POST'])
# def upgrade():
#     response = put_saved_data('forgetype', 'upgrade')
#     return response
#
# @app.route('/clone.html', methods=['GET', 'POST'])
# def clone():
#
#     response = put_saved_data('forgetype', 'clone')
#     return response
#
# @app.route('/restart.html', methods=['GET', 'POST'])
# def restart():
#     response = put_saved_data('forgetype', 'restart')
#     return response
#
# @app.route('/stg.html', methods=['GET', 'POST'])
# def stg():
#     response = put_saved_data('environment', 'stg')
#     return response
#
# @app.route('/prod.html', methods=['GET', 'POST'])
# def prod():
#     response = put_saved_data('environment', 'prod')
#     return response

if __name__ == '__main__':
    app.run(threaded=True, debug=True)
