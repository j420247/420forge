# imports
from collections import defaultdict
from datetime import timedelta
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
from os import path
import log
from flask_sqlalchemy import SQLAlchemy
from flask_sessionstore import Session
from werkzeug.contrib.fixers import ProxyFix
from sys import argv
import configparser

# global configuration
SECRET_KEY = 'key_to_the_forge'
PRODUCTS = ["Jira", "Confluence", "Crowd"]
VALID_STACK_STATUSES = ['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE', 'CREATE_IN_PROGRESS',
                        'DELETE_IN_PROGRESS', 'UPDATE_IN_PROGRESS', 'ROLLBACK_IN_PROGRESS', 'ROLLBACK_COMPLETE',
                        'DELETE_FAILED']

parser = argparse.ArgumentParser(description='Forge')
parser.add_argument('--nosaml',
                        action='store_true',
                        help='Start with --nosaml to bypass SAML for local testing')
parser.add_argument('--prod',
                        action='store_true',
                        help='Start with --prod for SAML production auth. Default (no args) is dev auth')
args = parser.parse_args()

# using dict of dicts called forgestate to track state of all actions
forgestate = defaultdict(dict)

# list to hold stacks that have already been initialised
stacks = []

# create and initialize app
app = Flask(__name__)
app.config.from_object(__name__)
api = Api(app)
app.config['SECRET_KEY'] = SECRET_KEY
if args.prod:
   app.wsgi_app = ProxyFix(app.wsgi_app)
   print("SAML auth set to production - the app can be accessed on https://forge.internal.atlassian.com")
   app.config['SAML_METADATA_URL'] = 'https://aas0641.my.centrify.com/saasManage/DownloadSAMLMetadataForApp?appkey=e17b1c79-2510-4865-bc02-fed7fe9e04bc&customerid=AAS0641'
else:
   print("SAML auth set to dev - the app can be accessed on http://127.0.0.1:8000")
   app.config['SAML_METADATA_URL'] = 'https://aas0641.my.centrify.com/saasManage/DownloadSAMLMetadataForApp?appkey=0752aaf3-897c-489c-acbc-5a233ccad705&customerid=AAS0641'
flask_saml.FlaskSAML(app)
# Create a SQLalchemy db for session and permission storge.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///acforge.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # suppress warning messages
app.config['SESSION_TYPE'] = 'sqlalchemy'
db = SQLAlchemy(app)
session_store = Session(app)
session_store.app.session_interface.db.create_all()

# load permissions file
#TODO think about whether we want to restrict based on environment tags or regions
with open(path.join(path.dirname(__file__), 'permissions.json')) as json_data:
    json_perms = json.load(json_data)

##
#### All actions need to pass through the sub class (RestrictedResource) to control permissions -
#### (doupgrade, doclone, dofullrestart, dorollingrestart, docreate, dodestroy, dothreaddumps, doheapdumps dorunsql, doupdate, status)
##
class RestrictedResource(Resource):
    def dispatch_request(self, *args, **kwargs):
        if '--nosaml' in argv:
            return super().dispatch_request(*args, **kwargs)
        # check permissions before returning super
        for keys in json_perms:
             if json_perms[keys]['group'][0] in session['saml']['attributes']['memberOf']:
                 if session['region'] in json_perms[keys]['region'] or '*' in json_perms[keys]['region']:
                     if request.endpoint in json_perms[keys]['action'] or '*' in json_perms[keys]['action']:
                         if kwargs['stack_name'] in json_perms[keys]['stack'] or '*' in json_perms[keys]['stack']:
                             print(f'User is authorised to perform {request.endpoint} on {kwargs["stack_name"]}')
                             return super().dispatch_request(*args, **kwargs)
        print(f'User is not authorised to perform {request.endpoint} on {kwargs["stack_name"]}')
        return 'Forbidden', 403

##
#### REST Endpoint classes
##
class doupgrade(RestrictedResource):
    def get(self, region, stack_name, new_version):
        mystack = Stack(stack_name, region)
        stacks.append(mystack)
        if not mystack.store_current_action('upgrade'):
            return False
        try:
            outcome = mystack.upgrade(new_version)
        except Exception as e:
            print(e.args[0])
            mystack.state.logaction(log.ERROR, f'Error occurred upgrading stack: {e.args[0]}')
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class doclone(RestrictedResource):
    def get(self, region, stack_name, rdssnap, ebssnap, pg_pass, app_pass, app_type):
        mystack = Stack(stack_name, region)
        stacks.append(mystack)
        if not mystack.store_current_action('clone'):
            return False
        try:
            outcome = mystack.destroy()
            outcome = mystack.clone(ebssnap, rdssnap, pg_pass, app_pass, app_type)
        except Exception as e:
            print(e.args[0])
            mystack.state.logaction(log.ERROR, f'Error occurred cloning stack: {e.args[0]}')
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


#TODO see if def post() in class doclone() will work here
@app.route('/doclone', methods = ['POST'])
def cloneJson():
    content = request.get_json()[0]
    app_type = '' #TODO is there a better way to do this?

    for param in content:
        if param['ParameterKey'] == 'StackName':
            stack_name = param['ParameterValue']
        if param['ParameterKey'] == 'Region':
            region = param['ParameterValue']
        elif param['ParameterKey'] == 'ConfluenceVersion':
            app_type = 'confluence'
        elif param['ParameterKey'] == 'JiraVersion':
            app_type = 'jira'
        elif param['ParameterKey'] == 'CrowdVersion':
            app_type = 'crowd'
        elif param['ParameterKey'] == 'EBSSnapshotId':
            param['ParameterValue'] = param['ParameterValue'].split(' ')[1]
        elif param['ParameterKey'] == 'DBSnapshotName':
            param['ParameterValue'] = param['ParameterValue'].split(' ')[1]

    content.remove(next(param for param in content if param['ParameterKey'] == 'Region'))

    mystack = Stack(stack_name, region, app_type)
    if not mystack.store_current_action('clone'):
        return False
    stacks.append(mystack)
    outcome = mystack.clone(content)
    mystack.clear_current_action()
    return outcome


class dofullrestart(RestrictedResource):
    def get(self, region, stack_name, threads, heaps):
        mystack = Stack(stack_name, region)
        stacks.append(mystack)
        if not mystack.store_current_action('fullrestart'):
            return False
        try:
            if threads == 'true':
                mystack.thread_dump(alsoHeaps=heaps)
            if heaps == 'true':
                mystack.heap_dump()
            mystack.full_restart()
        except Exception as e:
            print(e.args[0])
            mystack.state.logaction(log.ERROR, f'Error occurred doing full restart: {e.args[0]}')
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class dorollingrestart(RestrictedResource):
    def get(self, region, stack_name, threads, heaps):
        mystack = Stack(stack_name, region)
        stacks.append(mystack)
        if not mystack.store_current_action('rollingrestart'):
            return False
        try:
            if threads == 'true':
                mystack.thread_dump(alsoHeaps=heaps)
            if heaps == 'true':
                mystack.heap_dump()
            mystack.rolling_restart()
        except Exception as e:
            print(e.args[0])
            mystack.state.logaction(log.ERROR, f'Error occurred doing rolling restart: {e.args[0]}')
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class dodestroy(RestrictedResource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        stacks.append(mystack)
        if not mystack.store_current_action('destroy'):
            return False
        try:
            outcome = mystack.destroy()
        except Exception as e:
            print(e.args[0])
            mystack.state.logaction(log.ERROR, f'Error occurred destroying stack: {e.args[0]}')
            mystack.clear_current_action()
        session['stacks'] = sorted(get_cfn_stacks_for_region())
        mystack.clear_current_action()
        return


class dothreaddumps(RestrictedResource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        stacks.append(mystack)
        if not mystack.store_current_action('diagnostics'):
            return False
        try:
            outcome = mystack.thread_dump()
        except Exception as e:
            print(e.args[0])
            mystack.state.logaction(log.ERROR, f'Error occurred taking thread dumps: {e.args[0]}')
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class doheapdumps(RestrictedResource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        stacks.append(mystack)
        if not mystack.store_current_action('diagnostics'):
            return False
        try:
            outcome = mystack.heap_dump()
        except Exception as e:
            print(e.args[0])
            mystack.state.logaction(log.ERROR, f'Error occurred taking heap dumps: {e.args[0]}')
            mystack.clear_current_action()
        mystack.clear_current_action()
        return


class dorunsql(RestrictedResource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        stacks.append(mystack)
        if not mystack.store_current_action('runsql'):
            return False
        try:
            outcome = mystack.run_post_clone_sql()
        except Exception as e:
            print(e.args[0])
            mystack.state.logaction(log.ERROR, f'Error occurred running SQL: {e.args[0]}')
            mystack.clear_current_action()
        mystack.clear_current_action()
        return outcome


class docreate(RestrictedResource):
    def get(self, region, stack_name, pg_pass, app_pass, app_type):
        mystack = Stack(stack_name, region, app_type)
        stacks.append(mystack)
        if not mystack.store_current_action('create'):
            return False
        try:
            outcome = mystack.create(pg_pass, app_pass, app_type)
        except Exception as e:
            print(e.args[0])
            mystack.state.logaction(log.ERROR, f'Error occurred creating stack: {e.args[0]}')
            mystack.clear_current_action()
        session['stacks'] = sorted(get_cfn_stacks_for_region())
        mystack.clear_current_action()
        return outcome


@app.route('/docreate', methods = ['POST'])
def createJson():
    content = request.get_json()[0]

    for param in content:
        if param['ParameterKey'] == 'StackName':
            stack_name = param['ParameterValue']
            continue
        elif param['ParameterKey'] == 'TemplateName':
            template_name = param['ParameterValue']
            continue
        elif param['ParameterKey'] == 'ConfluenceVersion':
            app_type = 'confluence'
        elif param['ParameterKey'] == 'JiraVersion':
            app_type = 'jira'
        elif param['ParameterKey'] == 'CrowdVersion':
            app_type = 'crowd'

    mystack = Stack(stack_name, session['region'], app_type)
    if not mystack.store_current_action('create'):
        return False
    stacks.append(mystack)
    mystack.writeparms(content)

    params_for_create = [param for param in content if param['ParameterKey'] != 'StackName' and param['ParameterKey'] != 'TemplateName']
    outcome = mystack.create(parms=params_for_create, template_filename=template_name, app_type=app_type)
    session['stacks'] = sorted(get_cfn_stacks_for_region())
    mystack.clear_current_action()
    return outcome


@app.route('/doupdate', methods = ['POST'])
def updateJson():
    content = request.get_json()
    new_params = content[0]
    orig_params = content[1]

    stack_name = next(param for param in new_params if param['ParameterKey'] == 'StackName')['ParameterValue']
    mystack = Stack(stack_name, session['region'])
    if not mystack.store_current_action('update'):
        return False
    stacks.append(mystack)
    mystack.writeparms(new_params)

    for param in new_params:
        if param['ParameterKey'] != 'StackName' \
                and param['ParameterValue'] == next(orig_param for orig_param in orig_params if orig_param['ParameterKey'] == param['ParameterKey'])['ParameterValue']:
            del param['ParameterValue']
            param['UsePreviousValue'] = True

    params_for_update = [param for param in new_params if param['ParameterKey'] != 'StackName']

    cfn = boto3.client('cloudformation', region_name=session['region'])
    try:
        stack_details = cfn.describe_stacks(StackName=stack_name)
    except Exception as e:
        if e.response and "does not exist" in e.response['Error']['Message']:
            print(f'Stack {stack_name} does not exist')
            return f'Stack {stack_name} does not exist'
        print(e.args[0])

    # default to DataCenter template
    template_type = "DataCenter"

    env = next(tag for tag in stack_details['Stacks'][0]['Tags'] if tag['Key'] == 'environment')['Value']
    if env == 'stg':
        params_for_update.append({'ParameterKey': 'EBSSnapshotId', 'UsePreviousValue': True})
        params_for_update.append({'ParameterKey': 'DBSnapshotName', 'UsePreviousValue': True})
        template_type = 'STGorDR'

    outcome = mystack.update(params_for_update, template_type)
    mystack.clear_current_action()
    return outcome


class status(RestrictedResource):
    def get(self, stack_name):
        log_json = get_current_log(stack_name)
        return log_json if log_json else f'No current status for {stack_name}'


class serviceStatus(Resource):
    def get(self, region, stack_name):
        return "RUNNING"

        #TODO fix?
        # forgestate = defaultdict(dict)
        # forgestate[stack_name] = forgestate_read(stack_name)
        # forgestate[stack_name]['region'] = region
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
    def get(self, region, stack_name):
        for stack in stacks:
            if stack.stack_name == stack_name:
                return stack.check_stack_state()
        cfn = boto3.client('cloudformation', region_name=region)
        try:
            stack_state = cfn.describe_stacks(StackName=stack_name)
        except Exception as e:
            if e.response and "does not exist" in e.response['Error']['Message']:
                print(f'Stack {stack_name} does not exist')
                return f'Stack {stack_name} does not exist'
            print(e.args[0])
            return f'Error checking stack state: {e.args[0]}'
        return stack_state['Stacks'][0]['StackStatus']

class templateParams(Resource):
    def get(self, template_name):
        app_type = 'confluence' # default for lab
        for product in PRODUCTS:
            if product.lower() in template_name.lower():
                app_type = product.lower()
                break
        template_file = open(f'wpe-aws/{app_type}/{template_name}', "r")
        yaml.SafeLoader.add_multi_constructor(u'!', general_constructor)
        template_params = yaml.safe_load(template_file)['Parameters']

        params_to_send = []
        for param in template_params:
            params_to_send.append({'ParameterKey': param,
                                    'ParameterValue': template_params[param]['Default'] if 'Default' in template_params[param] else ''})
            if 'AllowedValues' in template_params[param]:
                next(param_to_send for param_to_send in params_to_send if param_to_send['ParameterKey'] == param)['AllowedValues'] = \
                    template_params[param]['AllowedValues']
        return params_to_send


class templateParamsForStack(Resource):
    def get(self, region, stack_name):
        cfn = boto3.client('cloudformation', region_name=region)
        try:
            stack_details = cfn.describe_stacks(StackName=stack_name)
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return
        stack_params = stack_details['Stacks'][0]['Parameters']

        # default to Stg template
        template_type = 'STGorDR'
        if len(stack_details['Stacks'][0]['Tags']) > 0:
            product_tag = next(tag for tag in stack_details['Stacks'][0]['Tags'] if tag['Key'] == 'product')
            if product_tag:
                app_type = product_tag['Value']
            else:
                flash(f'Stack {stack_name} is not tagged with product, cannot determine template to use', 'error')
                return False
            env_tag = next(tag for tag in stack_details['Stacks'][0]['Tags'] if tag['Key'] == 'environment')
            if env_tag:
                env = env_tag['Value']
            else:
                flash(f'Stack {stack_name} is not tagged with environment, cannot determine template to use', 'error')
                return False
        else:
            flash(f'Stack {stack_name} is not tagged, cannot determine template to use', 'error')
            return False

        if env == 'prod':
            template_type = 'DataCenter'

        template_file = open(f'wpe-aws/{app_type.lower()}/{app_type}{template_type}.template.yaml', "r")
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
                if 'AllowedValues' in template_params['Parameters'][param]:
                    next(compared_param for compared_param in compared_params if compared_param['ParameterKey'] == param)['AllowedValues'] = \
                        template_params['Parameters'][param]['AllowedValues']
                    next(compared_param for compared_param in compared_params if compared_param['ParameterKey'] == param)['Default'] = \
                        template_params['Parameters'][param]['Default'] if 'Default' in template_params['Parameters'][param] else ''
        return compared_params


class getSql(Resource):
    def get(self, stack_name):
        if Path(f'stacks/{stack_name}/{stack_name}.post-clone.sql').is_file():
            sql_file = open(f'stacks/{stack_name}/{stack_name}.post-clone.sql', "r")
            sql_to_run = 'SQL to be run:<br /><br />' + sql_file.read()
        else:
            sql_to_run = 'No SQL script exists for this stack'
        return sql_to_run


class getStackActionInProgress(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        action = mystack.get_stack_action_in_progress()
        if action:
            flash(f'{stack_name} is already being operated on: {action}', 'error')
            return action
        return False


class clearStackActionInProgress(Resource):
    def get(self, region, stack_name):
        mystack = Stack(stack_name, region)
        mystack.clear_current_action()
        return True


class actionReadyToStart(Resource):
    def get(self):
        return actionReadyToStartRenderTemplate()


class getEbsSnapshots(Resource):
    def get(self, region, stack_name):
        ec2 = boto3.client('ec2', region_name=region)
        snap_name_format = f'{stack_name}_ebs_snap_*'
        if region == 'us-east-1':
            snap_name_format = f'dr_{snap_name_format}'
        try:
            snapshots = ec2.describe_snapshots(Filters=[
                {
                    'Name': 'tag-value',
                    'Values': [
                        snap_name_format,
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
    def get(self, region, stack_name):
        rds = boto3.client('rds', region_name=region)
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


class getTemplates(Resource):
    def get(self, product):
        templates = []
        template_folder = Path(f'wpe-aws/{product.lower()}')
        templates.extend([file.name for file in list(template_folder.glob('**/*.yaml'))])
        templates.sort()
        return templates


class getVpcs(Resource):
    def get(self, region):
        ec2 = boto3.client('ec2', region_name=region)
        try:
            vpcs = ec2.describe_vpcs()
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return

        vpc_ids = []
        for vpc in vpcs['Vpcs']:
            vpc_ids.append(vpc['VpcId'])
        return vpc_ids


# Action UI pages
@app.route('/upgrade', methods = ['GET'])
def upgrade():
        return render_template('upgrade.html')

@app.route('/clone', methods = ['GET'])
def clone():
    return render_template('clone.html')

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

@app.route('/update', methods = ['GET'])
def update():
    return render_template('update.html')

@app.route('/viewlog', methods = ['GET'])
def viewlog():
    return render_template('viewlog.html')

@app.route('/diagnostics', methods = ['GET'])
def diagnostics():
    return render_template('diagnostics.html')

@app.route('/runsql', methods = ['GET'])
def runsql():
    return render_template('runsql.html')

@app.route('/admin', methods = ['GET'])
def admin():
    return render_template('admin.html')


# Actions
api.add_resource(doupgrade, '/doupgrade/<region>/<stack_name>/<new_version>')
api.add_resource(doclone, '/doclone/<app_type>/<stack_name>/<ebssnap>/<rdssnap>')
api.add_resource(dofullrestart, '/dofullrestart/<region>/<stack_name>/<threads>/<heaps>')
api.add_resource(dorollingrestart, '/dorollingrestart/<region>/<stack_name>/<threads>/<heaps>')
api.add_resource(docreate, '/docreate/<app_type>/<region>/<stack_name>/<ebssnap>/<rdssnap>')
api.add_resource(dodestroy, '/dodestroy/<region>/<stack_name>')
api.add_resource(dothreaddumps, '/dothreaddumps/<region>/<stack_name>')
api.add_resource(doheapdumps, '/doheapdumps/<region>/<stack_name>')
api.add_resource(dorunsql, '/dorunsql/<region>/<stack_name>')

# Stack info
api.add_resource(status, '/status/<stack_name>')
api.add_resource(serviceStatus, '/serviceStatus/<region>/<stack_name>')
api.add_resource(stackState, '/stackState/<region>/<stack_name>')
api.add_resource(templateParamsForStack, '/stackParams/<region>/<stack_name>')
api.add_resource(templateParams, '/templateParams/<template_name>')
api.add_resource(getSql, '/getsql/<stack_name>')
api.add_resource(getStackActionInProgress, '/getActionInProgress/<region>/<stack_name>')
api.add_resource(clearStackActionInProgress, '/clearActionInProgress/<region>/<stack_name>')

# Helpers
api.add_resource(actionReadyToStart, '/actionReadyToStart')
api.add_resource(getEbsSnapshots, '/getEbsSnapshots/<region>/<stack_name>')
api.add_resource(getRdsSnapshots, '/getRdsSnapshots/<region>/<stack_name>')
api.add_resource(getTemplates, '/getTemplates/<product>')
api.add_resource(getVpcs, '/getVpcs/<region>')


def app_active_in_lb(forgestate, node):
    return(forgestate)


##
#### Common functions
##

def get_cfn_stacks_for_region(region=None):
    cfn = boto3.client('cloudformation', region if region else session['region'])
    stack_name_list = []
    try:
        stack_list = cfn.list_stacks(
            StackStatusFilter=VALID_STACK_STATUSES)
        for stack in stack_list['StackSummaries']:
            stack_name_list.append(stack['StackName'])
    except (KeyError, botocore.exceptions.NoCredentialsError):
        flash(f'Cannot query AWS - please authenticate with Cloudtoken', 'error')
    return stack_name_list


def get_current_log(stack_name):
    statefile = Path(f'stacks/{stack_name}/{stack_name}.json')
    if statefile.is_file() and path.getsize(statefile) > 0:
        with open(statefile, 'r') as stack_state:
            try:
                json_state = json.load(stack_state)
                if 'action_log' in json_state:
                    return json_state['action_log']
            except Exception as e:
                print(e.args[0])
    return False


# This checks for SAML auth and sets a session timeout.
@app.before_request
def check_loggedin():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=60)
    if args.nosaml:
        return
    if not request.path.startswith("/saml") and not session.get('saml'):
        login_url = url_for('login', next=request.url)
        return redirect(login_url)


def general_constructor(loader, tag_suffix, node):
    return node.value

@app.route('/error/<error>')
def error(error):
    return render_template('error.html', code=error), error


def use_east1_if_no_region_selected():
    # use first region in forge.properties if no region selected (eg first load)
    if 'region' not in session:
        session['region'] = get_regions()[0][0]
        session['stacks'] = sorted(get_cfn_stacks_for_region(session['region']))


def get_regions():
    config = configparser.ConfigParser()
    config.read('forge.properties')
    return config.items('regions')


@app.route('/')
def index():
    use_east1_if_no_region_selected()
    session['products'] = PRODUCTS
    session['action'] = 'none'
    session['regions'] = get_regions()
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


@app.route('/setregion/<region>')
def setregion(region):
    session['region'] = region
    session['stacks'] = sorted(get_cfn_stacks_for_region(region))
    session['stack_name'] = 'none'
    session['version'] = 'none'
    flash(f'Region selected: {region}', 'success')
    return redirect(url_for('index'))


# Ex. action could equal upgrade, rollingrestart, etc.
@app.route('/setaction/<action>')
def setaction(action):
    use_east1_if_no_region_selected()
    session['action'] = action
    session['stack_name'] = 'none'
    session['version'] = 'none'
    session['stacks'] = sorted(get_cfn_stacks_for_region(session['region']))
    return redirect(url_for(action))


#@app.route('/getparms/upgrade')
@app.route('/getparms/<action>')
def getparms(action):
    return sorted(get_cfn_stacks_for_region())


@app.route('/show_stacks')
def show_stacks():
    stack_name_list = sorted(get_cfn_stacks_for_region())
    return render_template('stack_selection.html', stack_name_list=stack_name_list)


if __name__ == '__main__':
    app.run(threaded=True, debug=True, host='0.0.0.0', port=8000)
