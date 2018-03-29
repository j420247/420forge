# imports
from collections import defaultdict
from datetime import datetime, timedelta
from pprint import pprint
from stack import Stack
import boto3
import botocore
from flask import Flask, request, session, redirect, url_for, \
    render_template, flash
from flask_restful import Api, Resource
import flask_saml
from ruamel import yaml
import argparse
import json
from pathlib import Path

# global configuration
SECRET_KEY = 'key_to_the_forge'

# using dict of dicts called forgestate to track state of all actions
forgestate = defaultdict(dict)

# list to hold stacks that have already been initialised
stacks = []

# create and initialize app
app = Flask(__name__)
app.config.from_object(__name__)
api = Api(app)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SAML_METADATA_URL'] = 'https://aas0641.my.centrify.com/saasManage/DownloadSAMLMetadataForApp?appkey=0752aaf3-897c-489c-acbc-5a233ccad705&customerid=AAS0641'
flask_saml.FlaskSAML(app)

parser = argparse.ArgumentParser(description='Forge')
parser.add_argument('--nosaml',
                        action='store_true',
                        help='Start with --nosaml to bypass SAML for local dev')
args = parser.parse_args()

##
#### REST Endpoint classes
##

class doupgrade(Resource):
    def get(self, env, stack_name, new_version):
        mystack = Stack(stack_name, env)
        stacks.append(mystack)
        outcome = mystack.destroy()
        return


class doclone(Resource):
    def get(self, env, stack_name, rdssnap, ebssnap, pg_pass, app_pass, app_type):
        mystack = Stack(stack_name, env)
        stacks.append(mystack)
        try:
            outcome = mystack.destroy()
        except:
            pass
        outcome = mystack.clone(ebssnap, rdssnap, pg_pass, app_pass, app_type)
        return


class dofullrestart(Resource):
    def get(self, env, stack_name):
        mystack = Stack(stack_name, env)
        stacks.append(mystack)
        outcome = mystack.full_restart()
        return


class dorollingrestart(Resource):
    def get(self, env, stack_name):
        mystack = Stack(stack_name, env)
        stacks.append(mystack)
        outcome = mystack.rolling_restart()
        return


class dodestroy(Resource):
    def get(self, env, stack_name):
        mystack = Stack(stack_name, env)
        stacks.append(mystack)
        try:
            outcome = mystack.destroy()
        except:
            pass
        return


class docreate(Resource):
    def get(self, env, stack_name, pg_pass, app_pass, app_type):
        mystack = Stack(stack_name, env)
        stacks.append(mystack)
        try:
            outcome = mystack.destroy()
        except:
            pass
        outcome = mystack.create(pg_pass, app_pass, app_type)
        return


class status(Resource):
    def get(self, stack_name):
        log_json = get_current_log(stack_name)
        return log_json if log_json else f'No current status for {stack_name}'


class serviceStatus(Resource):
    def get(self, env, stack_name):
        return "RUNNING"

        #TODO fix?
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
        for stack in stacks:
            if stack.stack_name == stack_name:
                return stack.check_stack_state()


class stackParams(Resource):
    def get(self, env, stack_name):
        cfn = boto3.client('cloudformation', region_name=getRegion(env))
        try:
            stack_details = cfn.describe_stacks(StackName=stack_name)
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return
        stack_params = stack_details['Stacks'][0]['Parameters']

        def general_constructor(loader, tag_suffix, node):
            return node.value

        #  Determine app type
        for param in stack_params:
            if param['ParameterKey'] == 'ConfluenceVersion':
                app_type = 'Confluence'
                break
            elif param['ParameterKey'] == 'JiraVersion':
                app_type = 'Jira'
                break

        template_type = "STGorDR"
        if env == 'stg':
            template_type = "DataCenter"

        template_file = open(f'wpe-aws/{ app_type.lower() }/{ app_type}{ template_type }.template.yaml', "r")
        yaml.SafeLoader.add_multi_constructor(u'!', general_constructor)
        template_params = yaml.safe_load(template_file)

        # Remove old stack params that are no longer on the template
        # To do this we need to build a new list
        compared_params = []
        for stack_param in stack_params:
            if stack_param['ParameterKey'] in template_params['Parameters']:
                compared_params.append(stack_param)
            else:
                print("Parameter not found: " + stack_param['ParameterKey'])

        # Add new params from the template to the stack params
        for param in template_params['Parameters']:
            if param != 'DBSnapshotName' and param != 'EBSSnapshotId':
                if param not in [stack_param['ParameterKey'] for stack_param in stack_params]:
                    compared_params.append({'ParameterKey': param,
                                            'ParameterValue': template_params['Parameters'][param]['Default'] if 'Default' in template_params['Parameters'][param] else ''})
        return compared_params


class actionReadyToStart(Resource):
    def get(self):
        return actionReadyToStartRenderTemplate()


class getEbsSnapshots(Resource):
    def get(self, stack_name):
        ec2 = boto3.client('ec2', region_name=getRegion('stg'))
        try:
            snapshots = ec2.describe_snapshots(Filters=[
                {
                    'Name': 'description',
                    'Values': [
                        f'dr-{stack_name}-snap-*',
                    ]
                },
            ],)
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return

        snapshotIds = []
        for snap in snapshots['Snapshots']:
            snapshotIds.append(str(snap['StartTime']).split(' ').__getitem__(0) + ": " + snap['SnapshotId'])
        snapshotIds.sort(reverse=True)
        return snapshotIds


class getRdsSnapshots(Resource):
    def get(self, stack_name):
        rds = boto3.client('rds', region_name=getRegion('stg'))
        try:
            snapshots = rds.describe_db_snapshots(DBInstanceIdentifier=stack_name)
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return

        snapshotIds = []
        for snap in snapshots['DBSnapshots']:
            snapshotIds.append(str(snap['SnapshotCreateTime']).split(' ').__getitem__(0) + ": " + snap['DBSnapshotIdentifier'])
        snapshotIds.sort(reverse=True)
        return snapshotIds


# Action UI pages
@app.route('/upgrade', methods = ['GET'])
def upgrade():
        return render_template('upgrade.html')

@app.route('/clone', methods = ['GET'])
def clone():
    return render_template("clone.html")

@app.route('/fullrestart', methods = ['GET'])
def fullrestart():
    return render_template('fullrestart.html')

@app.route('/rollingrestart', methods = ['GET'])
def rollingrestart():
    return render_template('rollingrestart.html')

@app.route('/create', methods = ['GET'])
def create():
    return render_template('create.html')

@app.route('/destroy', methods = ['GET'])
def destroy():
    return render_template('destroy.html')

@app.route('/viewlog', methods = ['GET'])
def viewlog():
    return render_template('viewlog.html')


# Actions
api.add_resource(doupgrade, '/doupgrade/<env>/<stack_name>/<new_version>')
api.add_resource(doclone, '/doclone/<app_type>/<stack_name>/<ebssnap>/<rdssnap>')
api.add_resource(dofullrestart, '/dofullrestart/<env>/<stack_name>')
api.add_resource(dorollingrestart, '/dorollingrestart/<env>/<stack_name>')
api.add_resource(docreate, '/docreate/<app_type>/<env>/<stack_name>/<ebssnap>/<rdssnap>')
api.add_resource(dodestroy, '/dodestroy/<env>/<stack_name>')

# Stack info
api.add_resource(status, '/status/<stack_name>')
api.add_resource(serviceStatus, '/serviceStatus/<env>/<stack_name>')
api.add_resource(stackState, '/stackState/<env>/<stack_name>')
api.add_resource(stackParams, '/stackParams/<env>/<stack_name>')

# Helpers
api.add_resource(actionReadyToStart, '/actionReadyToStart')
api.add_resource(getEbsSnapshots, '/getEbsSnapshots/<stack_name>')
api.add_resource(getRdsSnapshots, '/getRdsSnapshots/<stack_name>')


def app_active_in_lb(forgestate, node):
    return(forgestate)

##
#### Common functions
##


def getRegion(env):
    if env == 'prod':
        return 'us-west-2'
    else:
        return 'us-east-1'


def get_cfn_stacks_for_environment(region=None):
    cfn = boto3.client('cloudformation', region if region else session['region'])
    stack_name_list = []
    stack_list = cfn.list_stacks(
        StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE']
    )
    for stack in stack_list['StackSummaries']:
        stack_name_list.append(stack['StackName'])
    #TODO fix or remove
    #  last_action_log(forgestate, 'general', log.INFO, f'Stack names: {stack_name_list}')
    return stack_name_list


def get_current_log(stack_name):
    statefile = Path(stack_name + '.json')
    if statefile.is_file():
        with open(statefile, 'r') as stack_state:
            return json.load(stack_state)['action_log']


# This checks for SAML auth and sets a session timeout.
@app.before_request
def check_loggedin():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=60)
    if args.nosaml:
        print("Bypassing SAML auth because --nosaml has been set - the app can be accessed on 127.0.0.1")
        return
    if not request.path.startswith("/saml") and not session.get('saml'):
        login_url = url_for('login', next=request.url)
        return redirect(login_url)


@app.route('/')
def index():
    #TODO remove?
    # saved_data = get_saved_data()
    # if 'forgetype' in forgestate[stack_name] and 'environment' in forgestate[stack_name]:
    #     gtg_flag = True
    #     stack_name_list = get_cfn_stacks_for_environment(forgestate[stack_name]['environment'])

    # use stg if no env selected (eg first load)
    if 'region' not in session:
        session['region'] = getRegion('stg')
        session['env'] = 'stg'
        session['stacks'] = sorted(get_cfn_stacks_for_environment(getRegion('stg')))
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
    return render_template('actionprogress.html')


# Either stg or prod
@app.route('/setenv/<env>')
def setenv(env):
    session['region'] = getRegion(env)
    session['env'] = env
    session['stacks'] = sorted(get_cfn_stacks_for_environment(getRegion(env)))
    flash(f'Environment selected: {env}', 'success')
    return redirect(url_for('index'))


# Ex. action could equal upgrade, rollingrestart, etc.
@app.route('/setaction/<action>')
def setaction(action):
    session['action'] = action
    return redirect(url_for(action))


#@app.route('/getparms/upgrade')
@app.route('/getparms/<action>')
def getparms(action):
    return sorted(get_cfn_stacks_for_environment())


# @app.route('/go/stg/upgradeProgress/<stack_name>')
#TODO fix or remove, this doesn't seem to be used
@app.route('/go/<environment>/<action>Progress/<stack_name>')
def progress(environment, action, stack_name):
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


# @app.route('/stg/upgrade/<stack_name>')
#TODO Remove this? It was broken so I have added stack_name so it compiles at least
@app.route('/<env>/<action>/<stack_name>', methods=['POST'])
def envact(env, action, stack_name):
    print('after stack selection')
    for key in request.form:
        forgestate[stack_name]['selected_stack'] = key.split("_")[1]
    pprint(forgestate[stack_name])
    return render_template(action + 'Options.html')


@app.route('/clone', methods = ['POST'])
def cloneJson():
    print(request.is_json)
    content = request.get_json()
    print(content)

    app_type = "";

    for param in content:
        if param['ParameterKey'] == 'StackName':
            stack_name = param['ParameterValue']
        elif param['ParameterKey'] == 'ConfluenceVersion':
            app_type = 'confluence'
        elif param['ParameterKey'] == 'JiraVersion':
            app_type = 'jira'
        elif param['ParameterKey'] == 'EBSSnapshotId':
            param['ParameterValue'] = param['ParameterValue'].split(' ')[1]
        elif param['ParameterKey'] == 'DBSnapshotName':
            param['ParameterValue'] = param['ParameterValue'].split(' ')[1]
        # Hackity hack, I know, it's just for now
        elif param['ParameterKey'] == 'ExternalSubnets':
            param['ParameterValue'] = 'subnet-df0c3597,subnet-f1fb87ab'
        elif param['ParameterKey'] == 'InternalSubnets':
            param['ParameterValue']  = 'subnet-df0c3597,subnet-f1fb87ab'
        elif param['ParameterKey'] == 'VPC':
            param['ParameterValue'] = 'vpc-320c1355'

    mystack = Stack(stack_name, 'stg', app_type)
    stacks.append(mystack)
    outcome = mystack.clone(content)
    return outcome


if __name__ == '__main__':
    app.run(threaded=True, debug=True, host='0.0.0.0', port=8000)
