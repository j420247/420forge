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
import os
from version import __version__
import glob

# global configuration
PRODUCTS = ["Jira", "Confluence", "Crowd"]
VALID_STACK_STATUSES = ['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE', 'CREATE_IN_PROGRESS',
                        'DELETE_IN_PROGRESS', 'UPDATE_IN_PROGRESS', 'ROLLBACK_IN_PROGRESS', 'ROLLBACK_COMPLETE', 'ROLLBACK_FAILED',
                        'DELETE_FAILED', 'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS', 'UPDATE_ROLLBACK_IN_PROGRESS']

parser = argparse.ArgumentParser(description='Forge')
parser.add_argument('--nosaml',
                        action='store_true',
                        help='Start with --nosaml to bypass SAML for local testing')
parser.add_argument('--region',
                        nargs='?',
                        default='us-east-1',
                        help='The AWS region that Forge is operating in')
args = parser.parse_args()

# using dict of dicts called stackstate to track state of a stack's actions
stackstate = defaultdict(dict)

# list to hold stacks that have already been initialised
stacks = []

# create and initialize app
print(f'Starting Atlassian CloudFormation Forge v{__version__}')
app = Flask(__name__)
app.config.from_object(__name__)
api = Api(app)
# get current region and create SSM client to read parameter store params
ssm_client = boto3.client('ssm', region_name=args.region)
app.config['SECRET_KEY'] = 'REPLACE_ME'
try:
    key = ssm_client.get_parameter(
        Name='atl_forge_secret_key',
        WithDecryption=True
    )
    app.config['SECRET_KEY'] = key['Parameter']['Value']
except botocore.exceptions.NoCredentialsError as e:
    print('No credentials - please authenticate with Cloudtoken')
    raise
except Exception:
    print('No secret key in parameter store')
# create SAML URL if saml enabled
if not args.nosaml:
    app.wsgi_app = ProxyFix(app.wsgi_app)
    print('SAML auth configured')
    try:
        saml_protocol = ssm_client.get_parameter(
            Name='atl_forge_saml_metadata_protocol',
            WithDecryption=True
        )
        saml_url = ssm_client.get_parameter(
            Name='atl_forge_saml_metadata_url',
            WithDecryption=True
        )
        app.config['SAML_METADATA_URL'] = f"{saml_protocol['Parameter']['Value']}://{saml_url['Parameter']['Value']}"
    except Exception:
        print('SAML is configured but there is no SAML metadata URL in the parameter store - exiting')
        raise
    flask_saml.FlaskSAML(app)
else:
    print('SAML auth is not configured')
# Create a SQLalchemy db for session and permission storge.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///acforge.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # suppress warning messages
app.config['SESSION_TYPE'] = 'sqlalchemy'
db = SQLAlchemy(app)
session_store = Session(app)
session_store.app.session_interface.db.create_all()
# is analytics enabled
config_props = configparser.ConfigParser()
config_props.read(path.join(path.dirname(__file__), 'forge.properties'))
if config_props['analytics']['enabled'] == 'true':
    app.config['ANALYTICS'] = 'true'

# load permissions file
#TODO think about whether we want to restrict based on environment tags or regions
try:
    with open(path.join(path.dirname(__file__), 'permissions.json')) as json_data:
        json_perms = json.load(json_data)
except Exception:
    print('could not open permissions.json; SAML auth will not work!')

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
                        if request.endpoint == 'docreate':
                            # do not check stack_name on stack creation
                            print(f'User is authorised to perform {request.endpoint}')
                            return super().dispatch_request(*args, **kwargs)
                        elif kwargs['stack_name'] in json_perms[keys]['stack'] or '*' in json_perms[keys]['stack']:
                            print(f'User is authorised to perform {request.endpoint} on {kwargs["stack_name"]}')
                            return super().dispatch_request(*args, **kwargs)
        print(f'User is not authorised to perform {request.endpoint} on {kwargs["stack_name"]}')
        return 'Forbidden', 403

##
#### REST Endpoint classes
##
class doupgrade(RestrictedResource):
    def get(self, region, stack_name, new_version):
        mystack = get_or_create_stack_obj(region, stack_name)
        if not mystack.store_current_action('upgrade', stack_locking_enabled()):
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
        mystack = get_or_create_stack_obj(region, stack_name)
        creator = session['saml']['subject'] if 'saml' in session else 'unknown'
        if not mystack.store_current_action('clone', stack_locking_enabled()):
            return False
        try:
            outcome = mystack.destroy()
            outcome = mystack.clone(ebssnap, rdssnap, pg_pass, app_pass, app_type, creator)
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
    instance_type = 'DataCenter' #TODO support server

    for param in content:
        if param['ParameterKey'] == 'TemplateName':
            template_name = param['ParameterValue']
        if param['ParameterKey'] == 'StackName':
            stack_name = param['ParameterValue']
        if param['ParameterKey'] == 'Region':
            region = param['ParameterValue']
        elif param['ParameterKey'] == 'ConfluenceVersion':
            app_type = 'Confluence'
        elif param['ParameterKey'] == 'JiraVersion':
            app_type = 'Jira'
        elif param['ParameterKey'] == 'CrowdVersion':
            app_type = 'Crowd'
        elif param['ParameterKey'] == 'EBSSnapshotId':
            param['ParameterValue'] = param['ParameterValue'].split(' ')[1]
        elif param['ParameterKey'] == 'DBSnapshotName':
            param['ParameterValue'] = param['ParameterValue'].split(' ')[1]

    #remove region and templateName from params to send
    content.remove(next(param for param in content if param['ParameterKey'] == 'Region'))
    content.remove(next(param for param in content if param['ParameterKey'] == 'TemplateName'))

    # remove any params that are not in the Clone template
    if template_name:
        template_file = get_template_file(template_name)
    else:
        template_file = f'atlassian-aws-deployment/templates/{app_type}{instance_type}Clone.template.yaml'
    yaml.SafeLoader.add_multi_constructor(u'!', general_constructor)
    template_params = yaml.safe_load(open(template_file, 'r'))['Parameters']
    params_to_send = []
    for param in content:
        if param['ParameterKey'] == 'StackName' or next((template_param for template_param in template_params if template_param == param['ParameterKey']), None):
            params_to_send.append(param)

    mystack = get_or_create_stack_obj(region, stack_name)
    if not mystack.store_current_action('clone', stack_locking_enabled()):
        return False
    creator = session['saml']['subject'] if 'saml' in session else 'unknown'
    outcome = mystack.clone(params_to_send, template_file=template_file, app_type=app_type.lower(), instance_type=instance_type, region=region, creator=creator)
    mystack.clear_current_action()
    return outcome


class dofullrestart(RestrictedResource):
    def get(self, region, stack_name, threads, heaps):
        mystack = get_or_create_stack_obj(region, stack_name)
        if not mystack.store_current_action('fullrestart', stack_locking_enabled()):
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
        mystack = get_or_create_stack_obj(region, stack_name)
        if not mystack.store_current_action('rollingrestart', stack_locking_enabled()):
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
        mystack = get_or_create_stack_obj(region, stack_name)
        if not mystack.store_current_action('destroy', stack_locking_enabled()):
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
        mystack = get_or_create_stack_obj(region, stack_name)
        if not mystack.store_current_action('diagnostics', stack_locking_enabled()):
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
        mystack = get_or_create_stack_obj(region, stack_name)
        if not mystack.store_current_action('diagnostics', stack_locking_enabled()):
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
        mystack = get_or_create_stack_obj(region, stack_name)
        if not mystack.store_current_action('runsql', stack_locking_enabled()):
            return False
        try:
            outcome = mystack.run_post_clone_sql()
        except Exception as e:
            print(e.args[0])
            mystack.state.logaction(log.ERROR, f'Error occurred running SQL: {e.args[0]}')
            mystack.clear_current_action()
        mystack.clear_current_action()
        return outcome

class dotag(RestrictedResource):
    def post(self, region, stack_name):
        tags = request.get_json()
        mystack = get_or_create_stack_obj(region, stack_name)
        if not mystack.store_current_action('tag', stack_locking_enabled()):
            return False
        try:
            outcome = mystack.tag(tags)
        except Exception as e:
            print(e.args[0])
            mystack.state.logaction(log.ERROR, f'Error occurred tagging stack: {e.args[0]}')
            mystack.clear_current_action()
        mystack.clear_current_action()
        return outcome

class docreate(RestrictedResource):
    def post(self):
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

        mystack = get_or_create_stack_obj(session['region'], stack_name)
        if not mystack.store_current_action('create', stack_locking_enabled()):
            return False
        params_for_create = [param for param in content if param['ParameterKey'] != 'StackName' and param['ParameterKey'] != 'TemplateName']
        creator = session['saml']['subject'] if 'saml' in session else 'unknown'
        outcome = mystack.create(parms=params_for_create, template_file=get_template_file(template_name), app_type=app_type, creator=creator, region=session['region'])
        session['stacks'] = sorted(get_cfn_stacks_for_region())
        mystack.clear_current_action()
        return outcome


@app.route('/doupdate', methods = ['POST'])
def updateJson():
    content = request.get_json()
    new_params = content[0]
    orig_params = content[1]

    stack_name = next(param for param in new_params if param['ParameterKey'] == 'StackName')['ParameterValue']
    mystack = get_or_create_stack_obj(session['region'], stack_name)
    if not mystack.store_current_action('update', stack_locking_enabled()):
        return False

    cfn_client = boto3.client('cloudformation', region_name=session['region'])
    cfn_resource = boto3.resource('cloudformation', region_name=session['region'])
    try:
        stack_details = cfn_client.describe_stacks(StackName=stack_name)
        existing_template_params = cfn_resource.Stack(stack_name).parameters
    except Exception as e:
        if e.response and "does not exist" in e.response['Error']['Message']:
            print(f'Stack {stack_name} does not exist')
            return f'Stack {stack_name} does not exist'
        print(e.args[0])

    template_name = next(param for param in new_params if param['ParameterKey'] == 'TemplateName')['ParameterValue']

    for param in new_params:
        # if param was not in previous template, always pass it in the change set
        if not next((existing_param for existing_param in existing_template_params if existing_param['ParameterKey'] == param['ParameterKey']), None):
            continue
        # if param has not changed from previous, delete the value and set UsePreviousValue to true
        if param['ParameterValue'] == next(orig_param for orig_param in orig_params if orig_param['ParameterKey'] == param['ParameterKey'])['ParameterValue']:
            del param['ParameterValue']
            param['UsePreviousValue'] = True

    params_for_update = [param for param in new_params if (param['ParameterKey'] != 'StackName' and param['ParameterKey'] != 'TemplateName')]

    env = next(tag for tag in stack_details['Stacks'][0]['Tags'] if tag['Key'] == 'environment')['Value']
    if env == 'stg' or env == 'dr':
        if not next((parm for parm in params_for_update if parm['ParameterKey'] == 'EBSSnapshotId'), None):
            params_for_update.append({'ParameterKey': 'EBSSnapshotId', 'UsePreviousValue': True})
        if not next((parm for parm in params_for_update if parm['ParameterKey'] == 'DBSnapshotName'), None):
            params_for_update.append({'ParameterKey': 'DBSnapshotName', 'UsePreviousValue': True})

    outcome = mystack.update(params_for_update, get_template_file(template_name))
    mystack.clear_current_action()
    return outcome


class status(Resource):
    def get(self, stack_name):
        log_json = get_current_log(stack_name)
        return log_json if log_json else f'No current status for {stack_name}'


class serviceStatus(Resource):
    def get(self, region, stack_name):
        mystack = get_or_create_stack_obj(region, stack_name)
        return mystack.check_service_status(logMsgs=False)


class stackState(Resource):
    def get(self, region, stack_name):
        mystack = get_or_create_stack_obj(region, stack_name)
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
    def get(self, repo_name, template_name):
        if 'atlassian-aws-deployment' in repo_name:
            template_file = open(f"atlassian-aws-deployment/templates/{template_name}", "r")
        else:
            for file in glob.glob(f'../custom-templates/{repo_name}/**/*.yaml'):
                if template_name in file:
                    template_file = open(file, "r")
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
    def get(self, region, stack_name, template_name):
        cfn = boto3.client('cloudformation', region_name=region)
        try:
            stack_details = cfn.describe_stacks(StackName=stack_name)
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return
        stack_params = stack_details['Stacks'][0]['Parameters']

        if len(stack_details['Stacks'][0]['Tags']) > 0:
            product_tag = next((tag for tag in stack_details['Stacks'][0]['Tags'] if tag['Key'] == 'product'), None)
            if product_tag:
                app_type = product_tag['Value']
            else:
                return 'tag-error'
            env_tag = next((tag for tag in stack_details['Stacks'][0]['Tags'] if tag['Key'] == 'environment'), None)
            if env_tag:
                env = env_tag['Value']
            else:
                return 'tag-error'
        else:
            return 'tag-error'

        template_file = open(get_template_file(template_name), "r")
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
        mystack = get_or_create_stack_obj(region, stack_name)
        action = mystack.get_stack_action_in_progress()
        if action:
            return action
        return 'None'


class clearStackActionInProgress(Resource):
    def get(self, region, stack_name):
        mystack = get_or_create_stack_obj(region, stack_name)
        mystack.clear_current_action()
        return True


class getVersion(Resource):
    def get(self, region, stack_name):
        cfn = boto3.client('cloudformation', region_name=region)
        try:
            stack_details = cfn.describe_stacks(StackName=stack_name)
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return 'Error'
        version_param = next((param for param in stack_details['Stacks'][0]['Parameters'] if 'Version' in param['ParameterKey']), None)
        if version_param:
            version_number = version_param['ParameterValue']
            return version_number
        else:
            return ''


class getNodes(Resource):
    def get(self, region, stack_name):
        mystack = get_or_create_stack_obj(region, stack_name)
        mystack.get_stacknodes()
        nodes = []
        for instance in mystack.instancelist:
            node = {}
            node_ip = list(instance.values())[0]
            node['ip'] = node_ip
            node['status'] = mystack.check_node_status(node_ip, False)
            nodes.append(node)
        return nodes


class getTags(Resource):
    def get(self, region, stack_name):
        mystack = get_or_create_stack_obj(region, stack_name)
        tags = mystack.get_tags()
        return tags


def get_or_create_stack_obj(region, stack_name):
    if len(stacks) > 0:
        mystack = next((stack for stack in stacks if stack.stack_name == stack_name), None)
        if not mystack:
            mystack = Stack(stack_name, region)
            stacks.append(mystack)
    else:
        mystack = Stack(stack_name, region)
        stacks.append(mystack)
    return mystack


class actionReadyToStart(Resource):
    def get(self):
        return actionReadyToStartRenderTemplate()


class getEbsSnapshots(Resource):
    def get(self, region, stack_name):
        ec2 = boto3.client('ec2', region_name=region)
        snap_name_format = f'{stack_name}_ebs_snap_*'
        if region != session['region']:
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
    def get(self, template_type):
        templates = []
        template_folder = Path('atlassian-aws-deployment/templates')
        custom_template_folder = Path('../custom-templates')
        # get default templates
        if template_type == 'all':
            default_templates = list(template_folder.glob(f"**/*.yaml"))
        else:
            default_templates = list(template_folder.glob(f"**/*{template_type}*.yaml"))
        for file in default_templates:
            # TODO support Server and Bitbucket
            if 'Server' in file.name:
                continue
            templates.append(('atlassian-aws-deployment', file.name))
        # get custom templates
        if custom_template_folder.exists():
            if template_type == 'all':
                custom_templates = list(custom_template_folder.glob(f"**/*/*/*.yaml"))
            else:
                custom_templates = list(custom_template_folder.glob(f"**/*/*/*{template_type}*.yaml"))
            for file in custom_templates:
                if 'Server' in file.name:
                    continue
                templates.append((file.parent.parent.name, file.name))
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


class getLockedStacks(Resource):
    def get(self):
        locked_stacks = [dir.name for dir in os.scandir(f'locks/') if dir.is_dir()]
        locked_stacks.sort()
        return locked_stacks


class setStackLocking(Resource):
    def post(self, lock):
        lockfile = Path(f'locks/locking')
        with open(lockfile, 'w') as lock_state:
            lock_state.write(lock)
            session['stack_locking'] = lock
            return lock

class forgeStatus(Resource):
    def get(self):
        return {'state': 'RUNNING'}

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

@app.route('/tag', methods = ['GET'])
def tag():
    return render_template('tag.html')

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

@app.route('/admin/<stack_name>', methods = ['GET'])
def admin_stack(stack_name):
    return render_template('admin.html', stackToAdmin=stack_name)


# Actions
api.add_resource(doupgrade, '/doupgrade/<region>/<stack_name>/<new_version>')
api.add_resource(doclone, '/doclone/<app_type>/<stack_name>/<ebssnap>/<rdssnap>')
api.add_resource(dofullrestart, '/dofullrestart/<region>/<stack_name>/<threads>/<heaps>')
api.add_resource(dorollingrestart, '/dorollingrestart/<region>/<stack_name>/<threads>/<heaps>')
api.add_resource(docreate, '/docreate')
api.add_resource(dodestroy, '/dodestroy/<region>/<stack_name>')
api.add_resource(dothreaddumps, '/dothreaddumps/<region>/<stack_name>')
api.add_resource(doheapdumps, '/doheapdumps/<region>/<stack_name>')
api.add_resource(dorunsql, '/dorunsql/<region>/<stack_name>')
api.add_resource(dotag, '/dotag/<region>/<stack_name>')

# Stack info
api.add_resource(status, '/status/<stack_name>')
api.add_resource(serviceStatus, '/serviceStatus/<region>/<stack_name>')
api.add_resource(stackState, '/stackState/<region>/<stack_name>')
api.add_resource(templateParamsForStack, '/stackParams/<region>/<stack_name>/<template_name>')
api.add_resource(templateParams, '/templateParams/<repo_name>/<template_name>')
api.add_resource(getSql, '/getsql/<stack_name>')
api.add_resource(getStackActionInProgress, '/getActionInProgress/<region>/<stack_name>')
api.add_resource(clearStackActionInProgress, '/clearActionInProgress/<region>/<stack_name>')
api.add_resource(getVersion, '/getVersion/<region>/<stack_name>')
api.add_resource(getNodes, '/getNodes/<region>/<stack_name>')
api.add_resource(getTags, '/getTags/<region>/<stack_name>')

# Helpers
api.add_resource(actionReadyToStart, '/actionReadyToStart')
api.add_resource(getEbsSnapshots, '/getEbsSnapshots/<region>/<stack_name>')
api.add_resource(getRdsSnapshots, '/getRdsSnapshots/<region>/<stack_name>')
api.add_resource(getTemplates, '/getTemplates/<template_type>')
api.add_resource(getVpcs, '/getVpcs/<region>')
api.add_resource(getLockedStacks, '/getLockedStacks')
api.add_resource(setStackLocking, '/setStackLocking/<lock>')

# Status endpoint
api.add_resource(forgeStatus, '/status')


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
    if not request.path.startswith("/saml") and not request.path.startswith("/status") and not session.get('saml'):
        login_url = url_for('login', next=request.url)
        return redirect(login_url)


def general_constructor(loader, tag_suffix, node):
    return node.value


def get_template_file(template_name):
    if 'atlassian-aws-deployment' in template_name:
        template_folder = Path('atlassian-aws-deployment/templates')
    else:
        template_folder = Path('../custom-templates')
    return list(template_folder.glob(f"**/{template_name.split(': ')[1]}"))[0]


def get_regions():
    config = get_config_properties()
    return config.items('regions')


def get_dr_region():
    config = get_config_properties()
    return config['dr']['dr-region']


def get_config_properties():
    config_props = configparser.ConfigParser()
    config_props.read(path.join(path.dirname(__file__), 'forge.properties'))
    return config_props


def get_nice_action_name(action):
    switcher = {
        'admin': 'Admin',
        'backup': 'Backup stack',
        'clone': 'Clone stack',
        'create': 'Create stack',
        'destroy': 'Destroy stack',
        'diagnostics': 'Diagnostics',
        'fullrestart': 'Full restart',
        'rollingrestart': 'Rolling restart',
        'runsql': 'Run SQL',
        'viewlog': 'Stack logs',
        'tag': 'Tag stack',
        'update': 'Update stack',
        'upgrade': 'Upgrade',
    }
    return switcher.get(action, '')


def stack_locking_enabled():
    lockfile = Path(f'locks/locking')
    with open(lockfile, 'r') as lock_state:
        try:
            return lock_state.read() == 'true'
        except Exception as e:
            print(e.args[0])


def get_forge_settings():
    # use first region in forge.properties if no region selected (eg first load)
    if 'region' not in session:
        session['region'] = get_regions()[0][0]
        session['stacks'] = sorted(get_cfn_stacks_for_region(session['region']))
    session['products'] = PRODUCTS
    session['regions'] = get_regions()
    session['stack_locking'] = stack_locking_enabled()
    session['forge_version'] = __version__


@app.route('/error/<error>')
def error(error):
    return render_template('error.html', code=error), error


@app.route('/')
def index():
    get_forge_settings()
    session['nice_action_name'] = ''
    return render_template('index.html')


@app.route('/upgrade')
def upgradeSetParams():
    return render_template('upgrade.html', stacks=getparms('upgrade'))


@app.route('/actionreadytostart')
def actionReadyToStartRenderTemplate():
    return render_template('actionreadytostart.html')


@app.route('/actionprogress/<action>')
def actionprogress(action):
    flash(f"Action '{action}' on {request.args.get('stack')} has begun", 'success')
    return render_template('actionprogress.html')


@app.route('/setregion/<region>')
def setregion(region):
    session['region'] = region
    session['stacks'] = sorted(get_cfn_stacks_for_region(region))
    flash(f'Region selected: {region}', 'success')
    return redirect(request.referrer)


# Ex. action could equal upgrade, rollingrestart, etc.
@app.route('/setaction/<action>')
def setaction(action):
    get_forge_settings()
    session['nice_action_name'] = get_nice_action_name(action)
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
