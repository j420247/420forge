# imports
from collections import defaultdict
from pprint import pprint
from stack import Stack
import boto3
import botocore
from flask import Flask, request, session, redirect, url_for, \
    render_template, flash
from flask_restful import Api, Resource
from ruamel import yaml
import log

# global configuration
SECRET_KEY = 'key_to_the_forge'

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
        forgestate = self.state.forgestate_update(forgestate, stack_name, 'action', 'test')
        forgestate = self.state.forgestate_update(forgestate, stack_name, 'environment', env)
        forgestate = self.state.forgestate_update(forgestate, stack_name, 'stack_name', stack_name)
        forgestate = self.state.forgestate_update(forgestate, stack_name, 'new_version', new_version)
        if env == 'prod':
            forgestate = self.state.forgestate_update(forgestate, stack_name, 'region', 'us-west-2')
        else:
            forgestate = self.state.forgestate_update(forgestate, stack_name, 'region', 'us-east-1')
        forgestate = self.state.get_stack_current_state(forgestate, stack_name)
        forgestate[stack_name]['appnodemax'] = '4'
        forgestate[stack_name]['appnodemin'] = '4'
        forgestate[stack_name]['syncnodemin'] = '2'
        forgestate[stack_name]['syncnodemax'] = '2'
        self.state.spinup_remaining_nodes(forgestate, stack_name)
        self.state.last_action_log(forgestate, stack_name, "Final state")
        return forgestate[stack_name]['last_action_log']


class clear(Resource):
    def get(self, stack_name):
        self.state.forgestate_clear(forgestate, stack_name)
        self.state.last_action_log(forgestate, stack_name, log.INFO, "Log cleared")
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
        mystack = Stack(stack_name, env)
        outcome = mystack.full_restart()
        return


class rollingrestart(Resource):
    def get(self, env, stack_name):
        mystack = Stack(stack_name, env)
        outcome = mystack.rolling_restart()
        return


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
    def get(self, env, stack_name, app_type):
        #TODO remove env and app_type
        mystack = Stack(stack_name, env, app_type)
        outcome = mystack.print_action_log()
        return outcome


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
        forgestate = defaultdict(dict)
        forgestate[stack_name] = self.state.forgestate_read(stack_name)
        forgestate[stack_name]['region'] = getRegion(env)
        return self.state.check_stack_state(forgestate, stack_name)


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
api.add_resource(status, '/status/<env>/<stack_name>/<app_type>')
api.add_resource(serviceStatus, '/serviceStatus/<env>/<stack_name>')
api.add_resource(stackState, '/stackState/<env>/<stack_name>')
api.add_resource(stackParams, '/stackParams/<env>/<stack_name>')
api.add_resource(actionReadyToStart, '/actionReadyToStart')
api.add_resource(viewLog, '/viewlog')
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


@app.route('/')
def index():
    #TODO remove?
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

        file = open("wpe-aws/confluence/ConfluenceSTGorDR.template.yaml", "r")
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

    mystack = Stack(stack_name, 'stg', app_type)
    outcome = mystack.clone(content)
    return outcome


if __name__ == '__main__':
    app.run(threaded=True, debug=True, host='0.0.0.0')
