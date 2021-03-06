import inspect
import os
from pathlib import Path
from unittest.mock import MagicMock

import boto3
import mock
import moto
import moto_overrides
from flask import Flask
from forge.aws_cfn_stack import stack as aws_stack


# Environment setup
CONF_STACKNAME = 'my-confluence'
CONF_CLONE_STACKNAME = 'my-cloned-confluence'

DUMMY_FILE = Path(f'{Path(inspect.getfile(inspect.currentframe())).parent}/dummy.file')
TEMPLATE_FILE = Path(f'{Path(inspect.getfile(inspect.currentframe())).parent}/func-test-confluence.template.yaml')
TEMPLATE_FILE_CLONE = Path(f'{Path(inspect.getfile(inspect.currentframe())).parent}/func-test-confluence-clone.template.yaml')
REGION = 'us-east-1'

# Configure app
app = Flask(__name__)
app.config['S3_BUCKET'] = 'mock_bucket'
app.config['SNS_REGION'] = 'us-east-1'
app.config['TESTING'] = True
app.config['ACTION_TIMEOUTS'] = {
    'node_registration_deregistration': 3600,
    'validate_node_responding': 3600,
    'validate_service_responding': 3600,
}

# override buggy moto functions
moto.cloudformation.parsing.parse_condition = moto_overrides.parse_condition
moto.cloudformation.responses.CloudFormationResponse.create_change_set = moto_overrides.create_change_set
moto.elbv2.models.ELBv2Backend.create_target_group = moto_overrides.create_target_group


def get_stack_params():
    return [
        {'ParameterKey': 'AutologinCookieAge', 'ParameterValue': ''},
        {'ParameterKey': 'CatalinaOpts', 'ParameterValue': ''},
        {'ParameterKey': 'CidrBlock', 'ParameterValue': '0.0.0.0/0'},
        {'ParameterKey': 'ClusterNodeInstanceType', 'ParameterValue': 't2.medium'},
        {'ParameterKey': 'ClusterNodeMax', 'ParameterValue': '2'},
        {'ParameterKey': 'ClusterNodeMin', 'ParameterValue': '2'},
        {'ParameterKey': 'ClusterNodeVolumeSize', 'ParameterValue': '50'},
        {'ParameterKey': 'CollaborativeEditingMode', 'ParameterValue': 'synchrony-local'},
        {'ParameterKey': 'ConfluenceDownloadUrl', 'ParameterValue': ''},
        {'ParameterKey': 'ConfluenceVersion', 'ParameterValue': '6.11.0'},
        {'ParameterKey': 'CustomDnsName', 'ParameterValue': ''},
        {'ParameterKey': 'DBAcquireIncrement', 'ParameterValue': '3'},
        {'ParameterKey': 'DBIdleTestPeriod', 'ParameterValue': '0'},
        {'ParameterKey': 'DBInstanceClass', 'ParameterValue': 'db.t2.medium'},
        {'ParameterKey': 'DBIops', 'ParameterValue': '1000'},
        {'ParameterKey': 'DBMasterUserPassword', 'ParameterValue': 'changeme'},
        {'ParameterKey': 'DBMaxStatements', 'ParameterValue': '0'},
        {'ParameterKey': 'DBMultiAZ', 'ParameterValue': 'true'},
        {'ParameterKey': 'DBPassword', 'ParameterValue': 'changeme'},
        {'ParameterKey': 'DBPoolMaxSize', 'ParameterValue': '60'},
        {'ParameterKey': 'DBPoolMinSize', 'ParameterValue': '10'},
        {'ParameterKey': 'DBPreferredTestQuery', 'ParameterValue': ''},
        {'ParameterKey': 'DBReadReplicaInstanceClass', 'ParameterValue': ''},
        {'ParameterKey': 'DBSnapshotId', 'ParameterValue': ''},
        {'ParameterKey': 'DBStorage', 'ParameterValue': '10'},
        {'ParameterKey': 'DBStorageType', 'ParameterValue': 'General Purpose (SSD)'},
        {'ParameterKey': 'DBTimeout', 'ParameterValue': '0'},
        {'ParameterKey': 'DBValidate', 'ParameterValue': 'false'},
        {'ParameterKey': 'DeployEnvironment', 'ParameterValue': 'prod'},
        {'ParameterKey': 'ElasticFileSystem', 'ParameterValue': 'EFS'},
        {'ParameterKey': 'ExternalSubnets', 'ParameterValue': f"{app.config['RESOURCES']['subnet_1_id']},{app.config['RESOURCES']['subnet_2_id']}"},
        {'ParameterKey': 'HostedZone', 'ParameterValue': 'wpt.atlassian.com.'},
        {'ParameterKey': 'InternalSubnets', 'ParameterValue': f"{app.config['RESOURCES']['subnet_1_id']},{app.config['RESOURCES']['subnet_2_id']}"},
        {'ParameterKey': 'JvmHeapOverride', 'ParameterValue': ''},
        {'ParameterKey': 'JvmHeapOverrideSynchrony', 'ParameterValue': ''},
        {'ParameterKey': 'KeyPairName', 'ParameterValue': 'WPE-GenericKeyPair-20161102'},
        {'ParameterKey': 'KmsKeyArn', 'ParameterValue': ''},
        {'ParameterKey': 'LoadBalancerScheme', 'ParameterValue': 'internal'},
        {'ParameterKey': 'LocalAnsibleGitRepo', 'ParameterValue': ''},
        {'ParameterKey': 'LocalAnsibleGitSshKeyName', 'ParameterValue': ''},
        {'ParameterKey': 'MailEnabled', 'ParameterValue': 'false'},
        {'ParameterKey': 'SSLCertificateARN', 'ParameterValue': ''},
        {'ParameterKey': 'StartCollectd', 'ParameterValue': 'true'},
        {'ParameterKey': 'SubDomainName', 'ParameterValue': ''},
        {'ParameterKey': 'SynchronyClusterNodeMax', 'ParameterValue': '1'},
        {'ParameterKey': 'SynchronyClusterNodeMin', 'ParameterValue': '1'},
        {'ParameterKey': 'SynchronyNodeInstanceType', 'ParameterValue': 't2.medium'},
        {'ParameterKey': 'TomcatAcceptCount', 'ParameterValue': '10'},
        {'ParameterKey': 'TomcatConnectionTimeout', 'ParameterValue': '20000'},
        {'ParameterKey': 'TomcatContextPath', 'ParameterValue': ''},
        {'ParameterKey': 'TomcatDefaultConnectorPort', 'ParameterValue': '8080'},
        {'ParameterKey': 'TomcatEnableLookups', 'ParameterValue': 'false'},
        {'ParameterKey': 'TomcatMaxThreads', 'ParameterValue': '48'},
        {'ParameterKey': 'TomcatMinSpareThreads', 'ParameterValue': '10'},
        {'ParameterKey': 'TomcatProtocol', 'ParameterValue': 'HTTP/1.1'},
        {'ParameterKey': 'TomcatProxyPort', 'ParameterValue': '80'},
        {'ParameterKey': 'TomcatRedirectPort', 'ParameterValue': '8443'},
        {'ParameterKey': 'TomcatScheme', 'ParameterValue': 'http'},
        {'ParameterKey': 'TomcatSecure', 'ParameterValue': 'false'},
        {'ParameterKey': 'VPC', 'ParameterValue': f"{app.config['RESOURCES']['vpc_id']}"},
    ]


def setup_stack():
    # not using pytest.setup_class or a fixture here as the moto environment does not persist - it tears itself down
    # each test must call this at the start
    with app.app_context():
        setup_env_resources()
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        # setup mocks
        mystack.validate_service_responding = MagicMock(return_value=True)
        mystack.wait_stack_action_complete = MagicMock(return_value=True)
        # create stack
        outcome = mystack.create(get_stack_params(), TEMPLATE_FILE, 'confluence', 'true', 'test_user', REGION, cloned_from=False)
        assert outcome


def setup_env_resources():
    # create S3 bucket
    s3 = boto3.resource('s3', region_name=REGION)
    s3.create_bucket(Bucket=app.config['S3_BUCKET'])
    # create VPC and subnets
    ec2 = boto3.resource('ec2', region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock='10.0.0.0/22')
    subnet_1 = vpc.create_subnet(CidrBlock='10.0.0.0/24')
    subnet_2 = vpc.create_subnet(CidrBlock='10.0.1.0/24')
    # create hosted zone
    r53 = boto3.client('route53')
    hosted_zone = r53.create_hosted_zone(
        Name='wpt.atlassian.com.',
        VPC={'VPCRegion': REGION, 'VPCId': vpc.vpc_id},
        CallerReference='caller_ref',
        HostedZoneConfig={'Comment': 'string', 'PrivateZone': True},
        DelegationSetId='string',
    )
    resources = {}
    resources['vpc_id'] = vpc.vpc_id
    resources['subnet_1_id'] = subnet_1.subnet_id
    resources['subnet_2_id'] = subnet_2.subnet_id
    resources['hosted_zone'] = hosted_zone
    app.config['RESOURCES'] = resources


# Tests
@mock.patch.dict(os.environ, {'AWS_ACCESS_KEY_ID': 'AWS_ACCESS_KEY_ID'})
@mock.patch.dict(os.environ, {'AWS_SECRET_ACCESS_KEY': 'AWS_SECRET_ACCESS_KEY'})
class TestAwsStacks:
    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_create(self):
        setup_stack()
        stacks = boto3.client('cloudformation', REGION).describe_stacks(StackName=CONF_STACKNAME)
        assert stacks['Stacks'][0]['StackName'] == CONF_STACKNAME

    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_create_changeset(self):
        setup_stack()
        cfn = boto3.client('cloudformation', REGION)
        stack = cfn.describe_stacks(StackName=CONF_STACKNAME)
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        params_for_update = stack['Stacks'][0]['Parameters']
        for param in params_for_update:
            if param['ParameterKey'] == 'TomcatConnectionTimeout':
                param['ParameterValue'] = '20001'
            # for other params, delete the value and set UsePreviousValue to true
            else:
                del param['ParameterValue']
                param['UsePreviousValue'] = True
        with app.app_context():
            result = mystack.create_change_set(params_for_update, TEMPLATE_FILE)
            assert result['ResponseMetadata']['HTTPStatusCode'] == 200
            cfn = boto3.client('cloudformation', REGION)
            change_set = cfn.describe_change_set(ChangeSetName=result['Id'], StackName=CONF_STACKNAME)
            assert [param for param in change_set['Parameters'] if param['ParameterKey'] == 'TomcatConnectionTimeout'][0]['ParameterValue'] == '20001'

    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_ssm
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_clone(self):
        setup_stack()
        clone_stack = aws_stack.Stack(CONF_CLONE_STACKNAME, REGION)
        clone_params = get_stack_params()
        clone_params.append({'ParameterKey': 'StackName', 'ParameterValue': CONF_CLONE_STACKNAME})
        # setup mocks
        clone_stack.full_restart = MagicMock(return_value=True)
        clone_stack.get_stacknodes = MagicMock(return_value=[{'i-0bcf57c789637b10f': '10.111.22.333'}, {'i-0fdacb1ab66016786': '10.111.22.444'}])
        clone_stack.get_sql = MagicMock(return_value='Select * from cwd_user limit 1;')
        clone_stack.validate_service_responding = MagicMock(return_value=True)
        clone_stack.wait_stack_action_complete = MagicMock(return_value=True)
        with app.app_context():
            outcome = clone_stack.clone(
                stack_params=clone_params,
                template_file=TEMPLATE_FILE_CLONE,
                app_type='confluence',
                clustered='true',
                creator='test-user',
                region=REGION,
                cloned_from=CONF_STACKNAME,
            )
            assert outcome
            stacks = boto3.client('cloudformation', REGION).describe_stacks(StackName=CONF_CLONE_STACKNAME)
            assert stacks['Stacks'][0]['StackName'] == CONF_CLONE_STACKNAME

    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_ssm
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_clone_destroy_failed(self):
        setup_stack()
        clone_stack = aws_stack.Stack(CONF_CLONE_STACKNAME, REGION)
        clone_params = get_stack_params()
        clone_params.append({'ParameterKey': 'StackName', 'ParameterValue': CONF_CLONE_STACKNAME})
        # setup mocks
        clone_stack.wait_stack_action_complete = MagicMock(return_value=False)
        clone_stack.create = MagicMock(return_value=True)
        with app.app_context():
            outcome = clone_stack.clone(
                stack_params=clone_params,
                template_file=TEMPLATE_FILE_CLONE,
                app_type='confluence',
                clustered='true',
                creator='test-user',
                region=REGION,
                cloned_from=CONF_STACKNAME,
            )
            assert not outcome
            clone_stack.create.assert_not_called()

    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_destroy(self):
        setup_stack()
        s3_bucket = app.config['S3_BUCKET']
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        with app.app_context():
            # upload a changelog and thread dump
            s3 = boto3.client('s3')
            s3.upload_file(os.path.relpath(DUMMY_FILE), s3_bucket, f'changelogs/{mystack.stack_name}')
            s3.upload_file(os.path.relpath(DUMMY_FILE), s3_bucket, f'changelogs/{mystack.stack_name}/changelog.log')
            s3.upload_file(os.path.relpath(DUMMY_FILE), s3_bucket, f'diagnostics/{mystack.stack_name}')
            s3.upload_file(os.path.relpath(DUMMY_FILE), s3_bucket, f'diagnostics/{mystack.stack_name}/threaddump.zip')
            # confirm files exist
            changelogs = s3.list_objects_v2(Bucket=s3_bucket, Prefix=f'changelogs/{mystack.stack_name}/')
            assert len(changelogs['Contents']) == 1
            diagnostics = s3.list_objects_v2(Bucket=s3_bucket, Prefix=f'diagnostics/{mystack.stack_name}/')
            assert len(diagnostics['Contents']) == 1
            # confirm stack exists
            cfn = boto3.client('cloudformation', REGION)
            stacks = cfn.describe_stacks()
            assert len(stacks['Stacks']) == 1
            # confirm stack has been deleted
            mystack.destroy(delete_changelogs=True, delete_threaddumps=True)
            stacks = cfn.describe_stacks()
            assert len(stacks['Stacks']) == 0
            # confirm changelogs have been deleted
            changelogs = s3.list_objects_v2(Bucket=s3_bucket, Prefix=f'changelogs/{mystack.stack_name}/')
            assert 'Contents' not in changelogs
            # confirm threaddumps have been deleted
            diagnostics = s3.list_objects_v2(Bucket=s3_bucket, Prefix=f'diagnostics/{mystack.stack_name}/')
            assert 'Contents' not in diagnostics

    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_dr_clone(self):
        setup_stack()
        dr_stack = aws_stack.Stack(CONF_CLONE_STACKNAME, REGION)
        clone_params = get_stack_params()
        next(param for param in clone_params if param['ParameterKey'] == 'DeployEnvironment')['ParameterValue'] = 'dr'
        clone_params.append({'ParameterKey': 'StackName', 'ParameterValue': CONF_CLONE_STACKNAME})
        # setup mocks
        dr_stack.run_sql = MagicMock(return_value=False)
        dr_stack.validate_service_responding = MagicMock(return_value=True)
        dr_stack.wait_stack_action_complete = MagicMock(return_value=True)
        with app.app_context():
            outcome = dr_stack.clone(
                stack_params=clone_params,
                template_file=TEMPLATE_FILE_CLONE,
                app_type='confluence',
                clustered='true',
                creator='test-user',
                region=REGION,
                cloned_from=CONF_STACKNAME,
            )
            assert outcome
            dr_stack.run_sql.assert_not_called()

    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_execute_changeset(self):
        setup_stack()
        cfn = boto3.client('cloudformation', REGION)
        stack = cfn.describe_stacks(StackName=CONF_STACKNAME)
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        params_for_update = stack['Stacks'][0]['Parameters']
        for param in params_for_update:
            if param['ParameterKey'] == 'TomcatConnectionTimeout':
                param['ParameterValue'] = '20001'
            # for other params, delete the value and set UsePreviousValue to true
            else:
                del param['ParameterValue']
                param['UsePreviousValue'] = True
        with app.app_context():
            change_set = mystack.create_change_set(params_for_update, TEMPLATE_FILE)
            change_set_name = change_set['Id']
            mystack.validate_service_responding = MagicMock(return_value=True)
            result = mystack.execute_change_set(change_set_name)
            assert result is True
            cfn = boto3.client('cloudformation', REGION)
            stacks = cfn.describe_stacks(StackName=CONF_STACKNAME)
            assert [param for param in stacks['Stacks'][0]['Parameters'] if param['ParameterKey'] == 'TomcatConnectionTimeout'][0]['ParameterValue'] == '20001'

    @moto.mock_ec2
    @moto.mock_cloudwatch
    @moto.mock_s3
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_node_cpu(self):
        setup_stack()
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        mystack.get_stacknodes = MagicMock(return_value=[{'i-0bcf57c789637b10f': '10.111.22.333'}, {'i-0fdacb1ab66016786': '10.111.22.444'}])
        result = mystack.get_node_cpu('10.111.22.333')
        # moto returns no metrics, but this proves that the function completed successfully
        assert result == {}

    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_sns
    @moto.mock_ssm
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_restarts(self):
        setup_stack()
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        # setup mocks
        mystack.check_service_status = MagicMock(return_value='RUNNING')
        mystack.check_node_status = MagicMock(return_value='RUNNING')
        mystack.get_tag = MagicMock(return_value='Confluence')
        mystack.is_app_clustered = MagicMock(return_value=True)
        drain_target_states = ['healthy', 'draining', 'notregistered', 'initial', 'initial', 'healthy', 'healthy', 'draining', 'notregistered', 'initial', 'initial', 'healthy']
        no_drain_target_states = ['initial', 'initial', 'healthy', 'initial', 'initial', 'healthy']
        with app.app_context():
            # perform restarts
            # expect failures as node count is 0
            rolling_result = mystack.rolling_restart(False)
            assert rolling_result is False
            full_result = mystack.full_restart()
            assert full_result is False
            # mock nodes and target states
            mystack.get_stacknodes = MagicMock(return_value=[{'i-0bcf57c789637b10f': '10.111.22.333'}, {'i-0fdacb1ab66016786': '10.111.22.444'}])
            mystack.get_target_state = MagicMock(side_effect=no_drain_target_states)
            # test rolling restart with and without draining
            rolling_result = mystack.rolling_restart(False)
            assert rolling_result is True
            mystack.get_target_state = MagicMock(side_effect=drain_target_states)
            rolling_drain_result = mystack.rolling_restart(True)
            assert rolling_drain_result is True
            # test full restart
            full_result = mystack.full_restart()
            assert full_result is True
            # test node restart with and without draining
            mystack.get_target_state = MagicMock(side_effect=no_drain_target_states)
            restart_node_result = mystack.restart_node('10.111.22.333', False)
            assert restart_node_result is True
            mystack.get_target_state = MagicMock(side_effect=drain_target_states)
            restart_node_drain_result = mystack.restart_node('10.111.22.444', True)
            assert restart_node_drain_result is True

    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_sns
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_sns(self):
        setup_stack()
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        action_msg = 'test msg'
        with app.test_request_context(''):
            session = {'saml': {'subject': 'UserA'}}
            topic_arn = mystack.get_sns_topic_arn()
            # confirm there is no topic for forge msgs
            assert topic_arn is None
            # send a msg
            published_msg = mystack.send_sns_msg(action_msg)
            topic_arn = mystack.get_sns_topic_arn()
            # confirm a topic has been created for forge msgs
            assert topic_arn is not None
            # confirm the message was sent successfully
            assert published_msg is not None
            assert published_msg['MessageId'] is not None

    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_tagging(self):
        setup_stack()
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        tags_to_add = [{'Key': 'Tag1', 'Value': 'Value1'}, {'Key': 'Tag2', 'Value': 'Value2'}]
        tagged = mystack.tag(tags_to_add)
        assert tagged
        tags = mystack.get_tags()
        assert tags == tags_to_add

    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_ssm
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_thread_and_heap_dumps(self):
        setup_stack()
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        # setup mocks
        mystack.get_stacknodes = MagicMock(return_value=[{'i-0bcf57c789637b10f': '10.111.22.333'}, {'i-0fdacb1ab66016786': '10.111.22.444'}])
        with app.app_context():
            # test thread dumps
            thread_result = mystack.thread_dump(alsoHeaps=False)
            assert thread_result is True
            single_node_thread_result = mystack.thread_dump(node='10.111.22.333', alsoHeaps=False)
            assert single_node_thread_result is True
            # test heap dumps
            heap_result = mystack.heap_dump()
            assert heap_result is True
            single_node_heap_result = mystack.heap_dump(node='10.111.22.333')
            assert single_node_heap_result is True

    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_ssm
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_thread_dump_links(self):
        setup_stack()
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        # upload a dummy thread dump
        s3 = boto3.client('s3')
        s3.upload_file(os.path.relpath(DUMMY_FILE), app.config['S3_BUCKET'], f'diagnostics/{mystack.stack_name}/threaddump.zip')
        with app.app_context():
            thread_dump_links = mystack.get_thread_dump_links()
            assert len(thread_dump_links) > 0

    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_sns
    @moto.mock_ssm
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_toggle_node(self):
        setup_stack()
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        # setup mocks
        mystack.check_service_status = MagicMock(return_value='RUNNING')
        mystack.check_node_status = MagicMock(return_value='RUNNING')
        mystack.get_tag = MagicMock(return_value='Confluence')
        mystack.is_app_clustered = MagicMock(return_value=True)
        deregister_target_states = ['healthy', 'healthy', 'draining', 'draining', 'notregistered']
        register_target_states = ['notregistered', 'notregistered', 'initial', 'initial', 'healthy']
        with app.app_context():
            with app.test_request_context(''):
                session = {'saml': {'subject': 'UserA'}}
                # mock nodes
                mystack.get_stacknodes = MagicMock(return_value=[{'i-0bcf57c789637b10f': '10.111.22.333'}, {'i-0fdacb1ab66016786': '10.111.22.444'}])
                # register node initially
                mystack.get_target_state = MagicMock(side_effect=register_target_states)
                register_result = mystack.toggle_node_registration(node='10.111.22.333')
                assert register_result is True
                # deregister node
                mystack.get_target_state = MagicMock(side_effect=deregister_target_states)
                deregister_result = mystack.toggle_node_registration(node='10.111.22.333')
                assert deregister_result is True
                # re-register node
                mystack.get_target_state = MagicMock(side_effect=register_target_states)
                register_result = mystack.toggle_node_registration(node='10.111.22.333')
                assert register_result is True
                # confirm a draining node re-registers
                mystack.get_target_state = MagicMock(side_effect=['draining'])
                mystack.wait_node_registered = MagicMock(return_value=True)
                mystack.toggle_node_registration(node='10.111.22.333')
                assert mystack.wait_node_registered.called

    @moto.mock_ec2
    @moto.mock_elbv2
    @moto.mock_s3
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_upgrade(self):
        setup_stack()
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        assert mystack.get_param_value('ProductVersion') == '6.11.0'
        # mock status
        mystack.check_service_status = MagicMock(return_value='RUNNING')
        # upgrade
        with app.app_context():
            mystack.upgrade('6.11.1')
        assert mystack.get_param_value('ProductVersion') == '6.11.1'
