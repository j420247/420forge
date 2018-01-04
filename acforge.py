# imports
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, jsonify, make_response
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
#bootstrap = Bootstrap(app)
app.config.from_object(__name__)
# # set defaults to 'upgrade' and 'stg'
# saved_data = {'environment': 'stg', 'forgetype': 'upgrade'}

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

#@app.route('/stg')
#@app.route('/prod')
@app.route('/<environment>')
def one_parm(environment):
    session['environment'] = environment
    print('env only environment = ', session['environment'])
    return render_template(session['environment'] + '.html')

#@app.route('/stg/upgrade')
@app.route('/<string:environment>/<string:action>')
def two_parms(environment, action):
    session['action'] = action

    print('2parm environment = ', session['environment'])
    print('2parm action = ', session['action'])
    action_path = session['environment'] + '/' + session['action']
    return redirect(url_for('show_stacks'))

@app.route('/show_stacks')
def show_stacks():
    stack_name_list = get_cfn_stacks_for_environment(session['environment'])
    return render_template('show_stacks.html', stack_name_list=stack_name_list)

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
