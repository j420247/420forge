# imports
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, jsonify, make_response
from flask_restful import reqparse, abort, Api, Resource
#from flask_bootstrap import Bootstrap
import os
import json
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

class hello(Resource):
    def get(self):
        return {'hello': 'world'}

class testing(Resource):
    def get(self):
        return "testing something"

class upgrade(Resource):
    def get(self, env, stack, newversion):
        session['action'] = "upgrade"
        session['environment'] = env
        session['stack'] = stack
        session['newversion'] = newversion
        if env == 'prod':
            session['region'] = 'us-west-2'
        else:
            session['region'] = 'us-east-1'
        # get pre-upgrade state information
        get_stack_current_state()
        # spin stack down to 0 nodes
 #       spindown_to_zero_appnodes()
        # spin stack up to 1 node on new release version
        spinup_to_one_appnode()
        # wait for
        return [ "starting upgrade for " + stack +" at " + env + " to version " + newversion ]
    def put(self, env, stack):
        return {env: stack}

class status(Resource):
    def get(self):
        return "something is happening"


api.add_resource(hello, '/hello')
api.add_resource(testing, '/test')
api.add_resource(upgrade, '/upgrade/<string:env>/<string:stack>/<string:newversion>')
api.add_resource(status, '/upgrade/status<string:env>/<string:stack>')

def get_stack_current_state():
    # store outcome in session
    cfn = boto3.client('cloudformation', region_name=session['region'])
    stack_details = cfn.describe_stacks( StackName=session['stack'] )

    session['appnodemax'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'ClusterNodeMax' ][0]
    session['appnodemin'] = [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'ClusterNodeMin'][0]

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
        print("not confluence")

    #jira
    try:
        session['preupgrade_jira_version'] = \
        [p['ParameterValue'] for p in stack_details['Stacks'][0]['Parameters'] if p['ParameterKey'] == 'JiraVersion'][0]
    except:
        print("not jira")
    pprint(session)
    return

def spindown_to_zero_appnodes():
    cfn = boto3.client('cloudformation', region_name=session['region'])
    spindown_parms = [
        { 'ParameterKey': 'ClusterNodeMax', 'ParameterValue': '0' },
        { 'ParameterKey': 'ClusterNodeMin', 'ParameterValue': '0' },
        { 'ParameterKey': 'CustomDnsName', 'UsePreviousValue': True },
    ]
    if 'preupgrade_confluence_version' in session:
        spindown_parms.append({ 'ParameterKey': 'SynchronyClusterNodeMax', 'ParameterValue': '0' })
        spindown_parms.append({ 'ParameterKey': 'SynchronyClusterNodeMin', 'ParameterValue': '0' })

    pprint(spindown_parms)

    update_stack = cfn.update_stack(
        StackName=session['stack'],
        Parameters=spindown_parms,
        UsePreviousTemplate=True,
        Capabilities=[ 'CAPABILITY_IAM' ],
    )
    pprint(update_stack)
    wait_stackupdate_complete()
    return

def spinup_to_one_appnode():
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

    pprint(spinup_parms)

    update_stack = cfn.update_stack(
        StackName=session['stack'],
        Parameters=spinup_parms,
        UsePreviousTemplate=True,
        Capabilities=[ 'CAPABILITY_IAM' ],
    )
    wait_stackupdate_complete()
    pprint(update_stack)
    return

def wait_stackupdate_complete():
    return

def validate_service_responding():
    return

def spinup_remaining_nodes():
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
        print(stack['StackName'])
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
    app.run(debug=True)
