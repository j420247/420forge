# imports
import json
import time
from collections import defaultdict
from datetime import datetime
from pprint import pprint
from stack import Stack
import boto3
import botocore
import requests
from flask import Flask, request, session, redirect, url_for, \
    render_template, flash
from flask_restful import Api, Resource
from ruamel import yaml

# global configuration

SECRET_KEY = 'key_to_the_forge'
INFO = "INFO"
ERROR = "ERROR"

# using dict of dicts called forgestate to track state of all actions
forgestate = defaultdict(dict)

# create and initialize app
app = Flask(__name__)
app.config.from_object(__name__)
api = Api(app)

##
#### REST Endpoint classes
##

class hello(Resource):
    def get(self):
        return {'hello': 'world'}

class test(Resource):
    def get(self, env, stack_name, new_version):
        # use this endpoint to test new functionality without impacting existing endpoints
        forgestate = defaultdict(dict)
        forgestate = forgestate_update(forgestate, stack_name, 'action', 'test')
        forgestate = forgestate_update(forgestate, stack_name, 'environment', env)
        forgestate = forgestate_update(forgestate, stack_name, 'stack_name', stack_name)
        forgestate = forgestate_update(forgestate, stack_name, 'new_version', new_version)
        if env == 'prod':
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-west-2')
        else:
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-east-1')
        forgestate = get_stack_current_state(forgestate, stack_name)
        forgestate[stack_name]['appnodemax'] = '4'
        forgestate[stack_name]['appnodemin'] = '4'
        forgestate[stack_name]['syncnodemin'] = '2'
        forgestate[stack_name]['syncnodemax'] = '2'
        spinup_remaining_nodes(forgestate, stack_name)
        last_action_log(forgestate, stack_name, "Final state")
        return forgestate[stack_name]['last_action_log']


class clear(Resource):
    def get(self, stack_name):
        forgestate_clear(forgestate, stack_name)
        last_action_log(forgestate, stack_name, INFO, "Log cleared")
        return "forgestate[stack_name] cleared"


class upgrade(Resource):
    def get(self, env, stack_name, new_version):
        mystack = Stack(stack_name, env)
        outcome = mystack.destroy()
        return


class clone(Resource):
    def get(self, env, stack_name, rdssnap, ebssnap, pg_pass, app_pass, app_type):
        mystack = Stack(stack_name, env)
        try:
            outcome = mystack.destroy()
        except:
            pass
        outcome = mystack.clone(ebssnap, rdssnap, pg_pass, app_pass, app_type)
        return


class fullrestart(Resource):
    def get(self, env, stack_name):
        forgestate = defaultdict(dict)
        forgestate_clear(forgestate, stack_name)
        last_action_log(forgestate, stack_name, INFO, "Beginning full restart")
        if env == 'prod':
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-west-2')
        else:
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-east-1')
        forgestate,instancelist = get_nodes_in_stack(forgestate, stack_name)
        shutdown_all_apps = shutdown_node_app(forgestate, stack_name, instancelist)
        for instance in instancelist:
            startup = start_node_app(forgestate, stack_name, [instance])
        last_action_log(forgestate, stack_name, INFO, "Final state")
        return(forgestate[stack_name]['last_action_log'])


class rollingrestart(Resource):
    def get(self, env, stack_name):
        forgestate = defaultdict(dict)
        forgestate_clear(forgestate, stack_name)
        last_action_log(forgestate, stack_name, INFO, "Beginning rolling restart")

        if env == 'prod':
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-west-2')
        else:
            forgestate = forgestate_update(forgestate, stack_name, 'region', 'us-east-1')
        forgestate,instancelist = get_nodes_in_stack(forgestate, stack_name)
        for instance in instancelist:
            shutdown = shutdown_node_app(forgestate, stack_name, [instance])
            startup = start_node_app(forgestate, stack_name, [instance])
        last_action_log(forgestate, stack_name, INFO, "Final state")
        return(forgestate[stack_name]['last_action_log'])


class destroy(Resource):
    def get(self, env, stack_name):
        mystack = Stack(stack_name, env)
        try:
            outcome = mystack.destroy()
        except:
            pass
        return


class create(Resource):
    def get(self, env, stack_name, pg_pass, app_pass, app_type):
        mystack = Stack(stack_name, env)
        try:
            outcome = mystack.destroy()
        except:
            pass
        outcome = mystack.create(pg_pass, app_pass, app_type)
        return


class status(Resource):
    def get(self, stack_name):
        forgestate = defaultdict(dict)
        forgestate[stack_name] = forgestate_read(stack_name)
        return forgestate[stack_name]['last_action_log']


class stackParams(Resource):
    def get(self, env, stack_name):
        cfn = boto3.client('cloudformation', region_name=getRegion(env))
        try:
            stack_details = cfn.describe_stacks(StackName=stack_name)
            template = cfn.get_template(StackName=stack_name)
        except botocore.exceptions.ClientError as e:
            print(e.args[0])
            return

        return stack_details['Stacks'][0]['Parameters']


class actionReadyToStart(Resource):
    def get(self):
        return actionReadyToStartRenderTemplate()


class viewLog(Resource):
    def get(self):
        return viewLogRenderTemplate()


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
            snapshotIds.append(snap['Description'])
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
            snapshotIds.append(snap['DBSnapshotIdentifier'])
        return snapshotIds


api.add_resource(hello, '/hello')
api.add_resource(test, '/test/<env>/<stack_name>/<new_version>')
api.add_resource(clear, '/clear/<stack_name>')
api.add_resource(upgrade, '/upgrade/<env>/<stack_name>/<new_version>')
api.add_resource(clone, '/clone/<app_type>/<stack_name>/<ebssnap>/<rdssnap>')
api.add_resource(fullrestart, '/fullrestart/<env>/<stack_name>')
api.add_resource(rollingrestart, '/rollingrestart/<env>/<stack_name>')
api.add_resource(create, '/create/<app_type>/<env>/<stack_name>/<ebssnap>/<rdssnap>')
api.add_resource(destroy, '/destroy/<env>/<stack_name>')
api.add_resource(status, '/status/<stack_name>')
api.add_resource(serviceStatus, '/serviceStatus/<env>/<stack_name>')
api.add_resource(stackState, '/stackState/<env>/<stack_name>')
api.add_resource(stackParams, '/stackParams/<env>/<stack_name>')
api.add_resource(actionReadyToStart, '/actionReadyToStart')
api.add_resource(viewLog, '/viewlog')
api.add_resource(getEbsSnapshots, '/getEbsSnapshots/<stack_name>')
api.add_resource(getRdsSnapshots, '/getRdsSnapshots/<stack_name>')


def get_nodes_in_stack(forgestate, stack_name):
    ec2 = boto3.resource('ec2', region_name=forgestate[stack_name]['region'])
    filters = [
        {'Name': 'tag:aws:cloudformation:stack-name', 'Values': [stack_name]},
        {'Name': 'tag:aws:cloudformation:logical-id', 'Values': ['ClusterNodeGroup']},
        {'Name': 'instance-state-name', 'Values': ['pending', 'running']},
    ]
    instancelist = []
    for i in ec2.instances.filter(Filters=filters):
        instancedict = { i.instance_id: i.private_ip_address }
        instancelist.append(instancedict)
    return(forgestate, instancelist)


def shutdown_node_app(forgestate, stack_name, instancelist):
    cmd_id_list = []
    for i in range(0, len(instancelist)) :
        for key in instancelist[i] :
            instance = key
            node_ip = instancelist[i][instance]
        last_action_log(forgestate, stack_name, INFO, f'Shutting down {instance} ({node_ip})')
        cmd = "/etc/init.d/confluence stop"
        cmd_id_list.append(ssm_send_command(forgestate, stack_name, instance, cmd))
    for cmd_id in cmd_id_list:
        result = ""
        while result != 'Success' and result != 'Failed':
            result, cmd_instance = ssm_cmd_check(forgestate, stack_name, cmd_id)
            time.sleep(5)
        if result == 'Failed':
            last_action_log(forgestate, stack_name, ERROR, f'Shutdown result for {cmd_instance}: {result}')
        else:
            last_action_log(forgestate, stack_name, INFO, f'Shutdown result for {cmd_instance}: {result}')
    return(forgestate)


def start_node_app(forgestate, stack_name, instancelist):
    cmd_id_list = []
    #for instance in [d.keys() for d in instancelist]:
    for instancedict in instancelist:
        instance = list(instancedict.keys())[0]
        node_ip = list(instancedict.values())[0]
        last_action_log(forgestate, stack_name, INFO, f'Starting up {instance} ({node_ip})')
        cmd = "/etc/init.d/confluence start"
        cmd_id = ssm_send_command(forgestate, stack_name, instance, cmd)
        result = ""
        while result != 'Success' and result != 'Failed':
            result, cmd_instance = ssm_cmd_check(forgestate, stack_name, cmd_id)
            time.sleep(5)
        if result == 'Failed':
            last_action_log(forgestate, stack_name, ERROR, f'Startup result for {cmd_instance}: {result}')
        else:
            result = ""
            while result != '{"state":"RUNNING"}':
                result = check_node_status(forgestate, stack_name, node_ip)
                last_action_log(forgestate, stack_name, INFO, f'Startup result for {cmd_instance}: {result}')
                time.sleep(30)
    return(forgestate)


def app_active_in_lb(forgestate, node):
    return(forgestate)

##
#### Common functions
##
def ssm_send_command(forgestate, stack_name, instance, cmd):
    ssm = boto3.client('ssm', region_name=forgestate[stack_name]['region'])
    ssm_command = ssm.send_command(
        InstanceIds=[instance],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': [cmd], 'executionTimeout': ["900"]},
        OutputS3BucketName='wpe-logs',
        OutputS3KeyPrefix='run-command-logs'
    )
    print("for command: ", cmd, " command_Id is: ", ssm_command['Command']['CommandId'])
    if ssm_command['ResponseMetadata']['HTTPStatusCode'] == 200:
        return (ssm_command['Command']['CommandId'])


def ssm_cmd_check(forgestate, stack_name, cmd_id):
    ssm = boto3.client('ssm', region_name=forgestate[stack_name]['region'])
    list_command = ssm.list_commands(CommandId=cmd_id)
    cmd_status = list_command[u'Commands'][0][u'Status']
    instance = list_command[u'Commands'][0][u'InstanceIds'][0]
    # result = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=instance)
    # if status == 'Success':
    #     pprint.pprint(result[u'StandardOutputContent'])
    return (cmd_status, instance)


def get_cfn_stacks_for_environment(region=None):
    cfn = boto3.client('cloudformation', region if region else session['region'])
    stack_name_list = []
    stack_list = cfn.list_stacks(
        StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE']
    )
    for stack in stack_list['StackSummaries']:
        stack_name_list.append(stack['StackName'])
    last_action_log(forgestate, 'general', INFO, f'Stack names: {stack_name_list}')
    return stack_name_list


@app.route('/')
def index():
    # saved_data = get_saved_data()
    # if 'forgetype' in forgestate[stack_name] and 'environment' in forgestate[stack_name]:
    #     gtg_flag = True
    #     stack_name_list = get_cfn_stacks_for_environment(forgestate[stack_name]['environment'])

    # use stg if no env selected
    if 'region' not in session:
        session['region'] = getRegion('stg')
        session['env'] = 'stg'
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
    return render_template("actionprogress.html")


@app.route('/viewlog')
def viewLogRenderTemplate():
    return render_template('viewlog.html')


# Either stg or prod
@app.route('/setenv/<env>')
def setenv(env):
    session['region'] = getRegion(env)
    session['env'] = env
    flash(f'Environment selected: {env}', 'success')
    return redirect(url_for('index'))


# Ex. action could equal upgrade, rollingrestart, etc.
@app.route('/setaction/<action>')
def setaction(action):
    session['action'] = action
    if action == "clone" or "create":
        envstacks=sorted(get_cfn_stacks_for_environment(getRegion('prod')))

        def general_constructor(loader, tag_suffix, node):
            return node.value

        file = open("cfn-templates/ConfluenceSTGorDR.template.yaml", "r")
        yaml.SafeLoader.add_multi_constructor(u'!', general_constructor)
        templateParams = yaml.safe_load(file)
        return render_template(action + ".html", stacks=envstacks, templateParams=templateParams)
    else:
        envstacks=sorted(get_cfn_stacks_for_environment())
        return render_template(action + ".html", stacks=envstacks)


#@app.route('/getparms/upgrade')
@app.route('/getparms/<action>')
def getparms(action):
    return sorted(get_cfn_stacks_for_environment())


# @app.route('/go/stg/upgradeProgress')
@app.route('/go/<environment>/<action>Progress')
def progress(environment, action):
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


# @app.route('/stg/upgrade')
@app.route('/<env>/<action>', methods=['POST'])
def envact(env, action):
    print('after stack selection')
    for key in request.form:
        forgestate[stack_name]['selected_stack'] = key.split("_")[1]
    pprint(forgestate[stack_name])
    return render_template(action + 'Options.html')


if __name__ == '__main__':
    app.run(threaded=True, debug=True, host='0.0.0.0')
