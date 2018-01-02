# imports
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, jsonify, make_response
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
app.config.from_object(__name__)

def get_saved_data():
    try:
        saved_data = json.loads(request.cookies.get('forgedata'))
    except TypeError:
        saved_data = { }
    return saved_data

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html', saves=get_saved_data())

@app.route('/settype', methods=['POST'])
def settype():
    response = make_response(redirect(url_for('index')))
    saved_data = get_saved_data()
    saved_data.update(dict(request.form.items()))
    response.set_cookie('forgedata', json.dumps(saved_data))
    return response


if __name__ == '__main__':
    app.run(debug=True)
