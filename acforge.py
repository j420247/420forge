# imports
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, jsonify, make_response
from flask_bootstrap import Bootstrap
import os
import json
import boto3

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

def get_cfn_stacks_for_environment(env):
    if env == 'prod':
        region = 'us-west-2'
    else:
        region = 'us-east-1'
    cfn = boto3.resource('cloudformation', region_name=region)
    stack_list = cfn.stacks.all()
    return stack_list


def get_saved_data():
    try:
        saved_data = json.loads(request.cookies.get('forgedata'))
    except TypeError:
        saved_data = { }
    return saved_data

@app.route('/', methods=['GET', 'POST'])
def index():
    response = make_response(redirect(url_for('upgrade')))
    # set defaults
    response.set_cookie('forgetype', 'upgrade')
    response.set_cookie('environment', 'stg')
    return render_template('index.html', saves=get_saved_data())

@app.route('/upgrade.html', methods=['GET', 'POST'])
def upgrade():
    response = make_response(redirect(url_for('upgrade')))
    response.set_cookie('forgetype', 'upgrade')
    return render_template('upgrade.html', saves=get_saved_data())

@app.route('/clone.html', methods=['GET', 'POST'])
def clone():
    response = make_response(redirect(url_for('clone')))
    response.set_cookie('forgetype', 'clone')
    return render_template('clone.html', saves=get_saved_data())

@app.route('/restart.html', methods=['GET', 'POST'])
def restart():
    response = make_response(redirect(url_for('restart')))
    response.set_cookie('forgetype', 'restart')
    return render_template('restart.html', saves=get_saved_data())

@app.route('/stg.html', methods=['GET', 'POST'])
def stg():
    get_cfn_stacks_for_environment('stg')
    response = make_response(redirect(url_for('stg')))
    response.set_cookie('environment', 'stg')
    return render_template('stg.html', saves=get_saved_data())

@app.route('/prod.html', methods=['GET', 'POST'])
def prod():
    response = make_response(redirect(url_for('prod')))
    response.set_cookie('environment', 'prod')
    return render_template('stg.html', saves=get_saved_data())

@app.route('/settype', methods=['POST'])
def settype():
    response = make_response(redirect(url_for('index')))
    saved_data = get_saved_data()
    saved_data.update(dict(request.form.items()))
    response.set_cookie('forgedata', json.dumps(saved_data))
    return response


if __name__ == '__main__':
    app.run(debug=True)
