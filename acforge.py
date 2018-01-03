# imports
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, jsonify, make_response
from flask_bootstrap import Bootstrap
import os
import json
import boto3
from pprint import pprint

# configuration
DATABASE = 'acforge.db'
DEBUG = True
SECRET_KEY = 'key_to_the_forge'
USERNAME = 'admin'
PASSWORD = 'admin'

# create and initialize app
app = Flask(__name__)
bootstrap = Bootstrap(app)
app.config.from_object(__name__)
# set defaults to 'upgrade' and 'stg'
saved_data = {'environment': 'stg', 'forgetype': 'upgrade'}

def get_cfn_stacks_for_environment(env):
    if env == 'prod':
        region = 'us-west-2'
    else:
        region = 'us-east-1'
    cfn = boto3.resource('cloudformation', region_name=region)
    stack_list = cfn.stacks.all()
    return stack_list

def put_saved_data(ckey,cvalue):
    response = make_response(redirect(url_for('index')))
    saved_data = get_saved_data()
    saved_data[ckey] = cvalue
    response.set_cookie('forgedata', json.dumps(saved_data))
    return response

def get_saved_data():
    try:
        saved_data = json.loads(request.cookies.get('forgedata'))
    except TypeError:
        saved_data = { }
    pprint(saved_data)
    return saved_data

@app.route('/', methods=['GET', 'POST'])
def index():
    get_cfn_stacks_for_environment('stg')
    return render_template('index.html', saves=get_saved_data())

@app.route('/upgrade.html', methods=['GET', 'POST'])
def upgrade():
    response = put_saved_data('forgetype', 'upgrade')
    return response

@app.route('/clone.html', methods=['GET', 'POST'])
def clone():

    response = put_saved_data('forgetype', 'clone')
    return response

@app.route('/restart.html', methods=['GET', 'POST'])
def restart():
    response = put_saved_data('forgetype', 'restart')
    return response

@app.route('/stg.html', methods=['GET', 'POST'])
def stg():
    response = put_saved_data('environment', 'stg')
    return response

@app.route('/prod.html', methods=['GET', 'POST'])
def prod():
    response = put_saved_data('environment', 'prod')
    return response

if __name__ == '__main__':
    app.run(debug=True)
