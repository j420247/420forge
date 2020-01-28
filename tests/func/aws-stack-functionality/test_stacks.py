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


CONF_STACKNAME = 'my-confluence'
REGION = 'us-east-1'

app = Flask(__name__)
app.config['S3_BUCKET'] = 'mock_bucket'
app.config['TESTING'] = True
app.config['ACTION_TIMEOUTS'] = {
    'validate_node_responding': 3600,
    'validate_service_responding': 3600,
}

# override buggy moto functions
moto.cloudformation.parsing.parse_condition = moto_overrides.parse_condition
moto.cloudformation.responses.CloudFormationResponse.create_change_set = moto_overrides.create_change_set
moto.elbv2.models.ELBv2Backend.create_target_group = moto_overrides.create_target_group

TEMPLATE_FILE = Path(f'{Path(inspect.getfile(inspect.currentframe())).parent}/func-test-confluence.template.yaml')


def get_stack_params():
    return [
        {'ParameterKey': 'AssociatePublicIpAddress', 'ParameterValue': 'false'},
        {'ParameterKey': 'AutologinCookieAge', 'ParameterValue': ''},
        {'ParameterKey': 'CatalinaOpts', 'ParameterValue': ''},
        {'ParameterKey': 'CidrBlock', 'ParameterValue': '0.0.0.0/0'},
        {'ParameterKey': 'ClusterNodeInstanceType', 'ParameterValue': 't2.medium'},
        {'ParameterKey': 'ClusterNodeMax', 'ParameterValue': '2'},
        {'ParameterKey': 'ClusterNodeMin', 'ParameterValue': '2'},
        {'ParameterKey': 'ClusterNodeVolumeSize', 'ParameterValue': '50'},
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
        {'ParameterKey': 'DBSnapshotId', 'ParameterValue': ''},
        {'ParameterKey': 'DBStorage', 'ParameterValue': '10'},
        {'ParameterKey': 'DBStorageType', 'ParameterValue': 'General Purpose (SSD)'},
        {'ParameterKey': 'DBTimeout', 'ParameterValue': '0'},
        {'ParameterKey': 'DBValidate', 'ParameterValue': 'false'},
        {'ParameterKey': 'DeployEnvironment', 'ParameterValue': 'prod'},
        {'ParameterKey': 'ExternalSubnets', 'ParameterValue': f"{app.config['RESOURCES']['subnet_1_id']},{app.config['RESOURCES']['subnet_2_id']}"},
        {'ParameterKey': 'HostedZone', 'ParameterValue': 'wpt.atlassian.com.'},
        {'ParameterKey': 'InternalSubnets', 'ParameterValue': f"{app.config['RESOURCES']['subnet_1_id']},{app.config['RESOURCES']['subnet_2_id']}"},
        {'ParameterKey': 'JvmHeapOverride', 'ParameterValue': ''},
        {'ParameterKey': 'JvmHeapOverrideSynchrony', 'ParameterValue': ''},
        {'ParameterKey': 'KeyName', 'ParameterValue': 'WPE-GenericKeyPair-20161102'},
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


@mock.patch.dict(os.environ, {'AWS_ACCESS_KEY_ID': 'AWS_ACCESS_KEY_ID'})
@mock.patch.dict(os.environ, {'AWS_SECRET_ACCESS_KEY': 'AWS_SECRET_ACCESS_KEY'})
class TestAwsStacks:
    @moto.mock_ec2
    @moto.mock_s3
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_create(self):
        setup_stack()
        stacks = boto3.client('cloudformation', REGION).describe_stacks(StackName=CONF_STACKNAME)
        assert stacks['Stacks'][0]['StackName'] == CONF_STACKNAME

    @moto.mock_ec2
    @moto.mock_s3
    @moto.mock_route53
    @moto.mock_cloudformation
    def test_destroy(self):
        setup_stack()
        cfn = boto3.client('cloudformation', REGION)
        stacks = cfn.describe_stacks()
        assert len(stacks['Stacks']) == 1
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        mystack.destroy()
        stacks = cfn.describe_stacks()
        assert len(stacks['Stacks']) == 0

    @moto.mock_ec2
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
    @moto.mock_s3
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

        with app.app_context():
            # perform restarts
            # expect failures as node count is 0
            rolling_result = mystack.rolling_restart()
            assert rolling_result is False
            full_result = mystack.full_restart()
            assert full_result is False

            # mock nodes
            mystack.get_stacknodes = MagicMock(return_value=[{'i-0bcf57c789637b10f': '10.111.22.333'}, {'i-0fdacb1ab66016786': '10.111.22.444'}])

            # expect restarts to pass
            rolling_result = mystack.rolling_restart()
            assert rolling_result is True
            full_result = mystack.full_restart()
            assert full_result is True

    @moto.mock_ec2
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
