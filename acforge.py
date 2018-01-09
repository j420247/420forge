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
