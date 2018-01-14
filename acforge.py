# imports
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, jsonify, make_response
from flask_restful import reqparse, abort, Api, Resource
from datetime import datetime
import requests
import os
import json
import time
import boto3
from pprint import pprint

# configuration
# DATABASE = 'acforge.db'
# DEBUG = True
SECRET_KEY = 'key_to_the_forge'
# USERNAME = 'admin'
# PASSWORD = 'admin'

# create and initialize app
app = Flask(__name__)
app.config.from_object(__name__)
api = Api(app)

##
#### Endpoint classes
##

class hello(Resource):
    def get(self):
        return {'hello': 'world'}

class testing(Resource):
    def get(self, env, stack, newversion):
        session['progress_log'] = "beginning testing " + str(datetime.now())
        session['action'] = "status"
        session['environment'] = env
        session['stack'] = stack
        session['newversion'] = newversion
        if env == 'prod':
            session['region'] = 'us-west-2'
        else:
            session['region'] = 'us-east-1'
        get_stack_current_state()
        spinup_to_one_appnode()
        # dummy up the numbers
        session['appnodemin'] = '2'
        session['appnodemax'] = '6'
        session['syncnodemin'] = '2'
        session['syncnodemax'] = '6'
        pprint(session)
        #        if originial stack had more than one node spin up to same as before
        if session['appnodemin'] != "1":
            spinup_remaining_nodes()
        elif 'syncnodemin' in session.keys() and session['syncnodemin'] != "1":
            spinup_remaining_nodes()
        # validate_service_responding()
        print("final state")
        spl = session['progress_log']
        print(spl)
        return(session['progress_log'])

class clear(Resource):
    def get(self):
        session.clear()
        session['progress_log'] = str ( "log cleared " + str(datetime.now()))
        return "session cleared"

class upgrade(Resource):
    def get(self, env, stack, newversion):
        session['progress_log'] = ("beginning upgrade " + str(datetime.now()))
        session['action'] = "upgrade"
        session['environment'] = env
        session['stack'] = stack
        session['newversion'] = newversion
        if env == 'prod':
            session['region'] = 'us-west-2'
        else:
            session['region'] = 'us-east-1'
        # block traffic at vtm
        # get pre-upgrade state information
        get_stack_current_state()
        # spin stack down to 0 nodes
        spindown_to_zero_appnodes()
        # spin stack up to 1 node on new release version
        spinup_to_one_appnode()
        # spinup remaining appnodes in stack if needed
        if session['appnodemin'] != "1":
            spinup_remaining_nodes()
        elif 'syncnodemin' in session.keys() and session['syncnodemin'] != "1" :
            spinup_remaining_nodes()
        # wait for remaining nodes to respond ???
        # enable traffic at VTM
        progress_log([ "completed upgrade for " + stack +" at " + env + " to version " + newversion])
        print("final state")
        spl = session['progress_log']
        print(spl)
        return(session['progress_log'])
    def put(self, env, stack):
        return {env: stack}

class status(Resource):
    def get(self):
        return(session['progress_log'])


api.add_resource(hello, '/hello')
api.add_resource(testing, '/test/<string:env>/<string:stack>/<string:newversion>')
api.add_resource(clear, '/clear')
api.add_resource(upgrade, '/upgrade/<string:env>/<string:stack>/<string:newversion>')
api.add_resource(status, '/status')

##
#### stack action functions
##

def get_stack_current_state():
    progress_log("getting pre-upgrade stack state")
    # store outcome in session
    cfn = boto3.client('cloudformation', region_name=session['region'])
    stack_details = cfn.describe_stacks( StackName=session['stack'] )

    session['appnodemax'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'ClusterNodeMax' ][0]
    session['appnodemin'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'ClusterNodeMin'][0]
    session['lburl'] = [p['OutputValue'] for p in stack_details['Stacks'][0]['Outputs'] if p['OutputKey'] == 'LoadBalancerURL'][0]

    # all the following parms are dependent on stack type and will fail list index out of range when not matching so wrap in try by apptype
    # versions in different parms relative to products - we should probably abstract the product

    #connie
    try:
        session['preupgrade_confluence_version'] = \
        [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
         p['ParameterKey'] == 'ConfluenceVersion'][0]
        # synchrony only exists for connie
        session['syncnodemax'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                               p['ParameterKey'] == 'SynchronyClusterNodeMax'][0]
        session['syncnodemin'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if
                               p['ParameterKey'] == 'SynchronyClusterNodeMin'][0]
    except:
        progress_log("not confluence")

    #jira
    try:
        session['preupgrade_jira_version'] = \
        [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'JiraVersion'][0]
    except:
        progress_log("not jira")
    progress_log(str(session))
    return

def spindown_to_zero_appnodes():
    progress_log("spinning stack down to 0 nodes")
    cfn = boto3.client('cloudformation', region_name=session['region'])
    spindown_parms = [
        { 'ParameterKey': 'ClusterNodeMax', 'ParameterValue': '0' },
        { 'ParameterKey': 'ClusterNodeMin', 'ParameterValue': '0' },
        { 'ParameterKey': 'CustomDnsName', 'UsePreviousValue': True },
    ]
    if 'preupgrade_confluence_version' in session:
        spindown_parms.append({ 'ParameterKey': 'SynchronyClusterNodeMax', 'ParameterValue': '0' })
        spindown_parms.append({ 'ParameterKey': 'SynchronyClusterNodeMin', 'ParameterValue': '0' })

    progress_log(str(spindown_parms))

    update_stack = cfn.update_stack(
        StackName=session['stack'],
        Parameters=spindown_parms,
        UsePreviousTemplate=True,
        Capabilities=[ 'CAPABILITY_IAM' ],
    )
    progress_log(str(update_stack))
    wait_stackupdate_complete()
    return

def spinup_to_one_appnode():
    progress_log("spinning stack up to one appnode")
    # for connie 1 app node and 1 synchrony
    cfn = boto3.client('cloudformation', region_name=session['region'])
    spinup_parms = [
        { 'ParameterKey': 'ClusterNodeMax', 'ParameterValue': '1' },
        { 'ParameterKey': 'ClusterNodeMin', 'ParameterValue': '1' },
        { 'ParameterKey': 'CustomDnsName', 'UsePreviousValue': True },
    ]
    if 'preupgrade_jira_version' in session:
        spinup_parms.append({'ParameterKey': 'JiraVersion', 'ParameterValue': session['newversion']})
    if 'preupgrade_confluence_version' in session:
        spinup_parms.append({ 'ParameterKey': 'ConfluenceVersion', 'ParameterValue': session['newversion']})
        spinup_parms.append({ 'ParameterKey': 'SynchronyClusterNodeMax', 'ParameterValue': '1' })
        spinup_parms.append({ 'ParameterKey': 'SynchronyClusterNodeMin', 'ParameterValue': '1' })

    progress_log(str(spinup_parms))

    update_stack = cfn.update_stack(
        StackName=session['stack'],
        Parameters=spinup_parms,
        UsePreviousTemplate=True,
        Capabilities=[ 'CAPABILITY_IAM' ],
    )
    wait_stackupdate_complete()
    validate_service_responding()
    progress_log(str(update_stack))
    return

##
#### Common functions
##
def progress_log(log_this):
    print(str(log_this))
    session['progress_log'] = "\n".join([str(log_this), str(session['progress_log'])])
    return

def check_stack_state():
    progress_log(" ==> checking stack state ")
    cfn = boto3.client('cloudformation', region_name=session['region'])
    stack_state = cfn.describe_stacks(StackName=session['stack'])
    return(stack_state['Stacks'][0]['StackStatus'])

def wait_stackupdate_complete():
    progress_log("waiting for stack update to complete")
    stack_state = check_stack_state()
    while stack_state == "UPDATE_IN_PROGRESS":
        progress_log(str("====> stack_state is: " + stack_state + " waiting .... " + str(datetime.now())))
        time.sleep(30)
        stack_state = check_stack_state()
    return

def check_service_status():
    progress_log(str(" ==> checking service status at " + session['lburl'] + "/status"))
    service_status = requests.get(session['lburl'] + '/status')
    return(service_status.text)

def validate_service_responding():
    progress_log("waiting for service to reply RUNNING on /status")
    service_state = check_service_status()
    while service_state != '{"state":"RUNNING"}' :
        progress_log(str("====> health check reports: " + service_state + " waiting for RUNNING " + str(datetime.now())))
        time.sleep(60)
        service_state = check_service_status()
    return

def spinup_remaining_nodes():
    progress_log("spinning up any remaining nodes in stack")
    # for connie 1 app node and 1 synchrony
    cfn = boto3.client('cloudformation', region_name=session['region'])
    spinup_parms = [
        { 'ParameterKey': 'ClusterNodeMax', 'ParameterValue': session['appnodemax'] },
        { 'ParameterKey': 'ClusterNodeMin', 'ParameterValue': session['appnodemin'] },
        { 'ParameterKey': 'CustomDnsName', 'UsePreviousValue': True },
    ]
    if 'preupgrade_jira_version' in session:
        spinup_parms.append({'ParameterKey': 'JiraVersion', 'ParameterValue': session['newversion']})
    if 'preupgrade_confluence_version' in session:
        spinup_parms.append({ 'ParameterKey': 'ConfluenceVersion', 'ParameterValue': session['newversion']})
        spinup_parms.append({ 'ParameterKey': 'SynchronyClusterNodeMax', 'ParameterValue': session['syncnodemax'] })
        spinup_parms.append({ 'ParameterKey': 'SynchronyClusterNodeMin', 'ParameterValue': session['syncnodemin'] })

    progress_log(str(spinup_parms))

    update_stack = cfn.update_stack(
        StackName=session['stack'],
        Parameters=spinup_parms,
        UsePreviousTemplate=True,
        Capabilities=[ 'CAPABILITY_IAM' ],
    )
    wait_stackupdate_complete()
    progress_log("stack restored to full node count")
    return

def get_cfn_stacks_for_environment(env):
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
        progress_log(stack['StackName'])
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
    if 'forgetype' in session and 'environment' in session:
        gtg_flag = True
        stack_name_list = get_cfn_stacks_for_environment(session['environment'])
    return render_template('index.html')

#@app.route('/setenv/stg')
#@app.route('/setenv/prod')
@app.route('/setenv/<environment>')
def env(environment):
    session['environment'] = environment
    print('env = ', session['environment'])
    if 'action' in session and 'environment' in session:
        return redirect(url_for('show_stacks'))
    else:
        return redirect(url_for('index'))

#@app.route('/setaction/upgrade')
@app.route('/setaction/<string:action>')
def action(action):
    session['action'] = action
    print('action = ', session['action'])
    if 'action' in session and 'environment' in session:
        return redirect(url_for('show_stacks'))
    else:
        return redirect(url_for('index'))

#@app.route('/go/stg/upgradeProgress')
@app.route('/go/<environment>/<string:action>Progress')
def progress(environment, action):
    print("in progress")
    print('env =', session['environment'])
    print('action = ', session['action'])

    if 'action' in session and 'environment' in session:
        return redirect(url_for('show_stacks'))
    else:
        return redirect(url_for('index'))

@app.route('/show_stacks')
def show_stacks():
    stack_name_list = sorted(get_cfn_stacks_for_environment(session['environment']))
#    selected_stack = request.form['stack_selection']
#    print("selcted stack is ", selected_stack)
    return render_template('stack_selection.html', stack_name_list=stack_name_list)

#@app.route('/stg/upgrade')
@app.route('/<string:env>/<string:action>', methods=['POST'])
def envact(env, action):
    print('after stack selection')
    for key in request.form:
        session['selected_stack'] = key.split("_")[1]
    pprint(session)
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
