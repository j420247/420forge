import sys
sys.path.append('../../src')

import boto3
import unittest
import forge.aws_cfn_stack.stack as aws_stack
from moto import mock_cloudformation, mock_ec2, mock_s3, mock_route53, mock_ssm
from setup_test_env import setup_env_resources, REGION, CONF_STACKNAME, S3_BUCKET
from pathlib import Path

from flask import Flask, current_app


class test_aws_stacks(unittest.TestCase):
    TEMPLATE_FILE = Path('../../src/forge/cfn-templates/UnitTest-Confluence.template.yaml')
    def get_stack_params(self):
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
        {'ParameterKey': 'ExternalSubnets', 'ParameterValue': f"{current_app.config['RESOURCES']['subnet_1_id']},{current_app.config['RESOURCES']['subnet_2_id']}"},
        {'ParameterKey': 'HostedZone', 'ParameterValue': 'wpt.atlassian.com.'},
        {'ParameterKey': 'InternalSubnets', 'ParameterValue': f"{current_app.config['RESOURCES']['subnet_1_id']},{current_app.config['RESOURCES']['subnet_2_id']}"},
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
        {'ParameterKey': 'VPC', 'ParameterValue':  f"{current_app.config['RESOURCES']['vpc_id']}"}
    ]

    @mock_ec2
    @mock_s3
    @mock_route53
    @mock_cloudformation
    def setup(self):
        # not using unittest.setUp/setUpClass here as the created stack does not persist in the moto environment
        # each test must call this at the start
        setup_env_resources()
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        mystack.create(self.get_stack_params(), self.TEMPLATE_FILE,
                       'confluence', 'true', 'test_user', REGION, cloned_from=False)

    @mock_cloudformation
    def test_create(self):
        # the stack is created by setup() so we just test it exists here
        self.setup()
        stacks = boto3.client('cloudformation', REGION).describe_stacks(StackName=CONF_STACKNAME)
        self.assertEqual(stacks['Stacks'][0]['StackName'], CONF_STACKNAME)

    @mock_cloudformation
    def test_destroy(self):
        self.setup()
        cfn = boto3.client('cloudformation', REGION)
        stacks = cfn.describe_stacks()
        self.assertEqual(len(stacks['Stacks']), 1)
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        mystack.destroy()
        stacks = cfn.describe_stacks()
        self.assertEqual(len(stacks['Stacks']), 0)

    @mock_s3
    @mock_cloudformation
    def test_update(self):
        self.setup()
        cfn = boto3.client('cloudformation', REGION)
        stacks = cfn.describe_stacks(StackName=CONF_STACKNAME)
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        params_for_update = self.get_stack_params()
        for param in params_for_update:
            if param['ParameterKey'] == 'TomcatConnectionTimeout':
                param['ParameterValue'] = '20001'
            # for other params, delete the value and set UsePreviousValue to true
            else:
                del param['ParameterValue']
                param['UsePreviousValue'] = True
        result = mystack.update(params_for_update, self.TEMPLATE_FILE)
        cfn = boto3.client('cloudformation', REGION)
        stacks = cfn.describe_stacks(StackName=CONF_STACKNAME)
        self.assertEqual([param for param in stacks['Stacks'][0]['Parameters'] if param['ParameterKey'] == 'TomcatConnectionTimeout'][0]['ParameterValue'], '20001')

    @mock_cloudformation
    def test_tagging(self):
        self.setup()
        mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
        tags_to_add = [
            {'Key': 'Tag1', 'Value': 'Value1'},
            {'Key': 'Tag2', 'Value': 'Value2'}
        ]
        tagged = mystack.tag(tags_to_add)
        self.assertTrue(tagged)
        tags = mystack.get_tags()
        self.assertEqual(tags, tags_to_add)

    @mock_ec2
    @mock_ssm
    @mock_cloudformation
    def test_restarts(self):
            self.setup()
            mystack = aws_stack.Stack(CONF_STACKNAME, REGION)
            rolling_result = mystack.rolling_restart()
            self.assertTrue(rolling_result)
            full_result = mystack.full_restart()
            self.assertTrue(full_result)


if __name__ == '__main__':
    app = Flask(__name__)
    app.config['S3_BUCKET'] = 'mock_bucket'
    app.config['TESTING'] = True
    with app.app_context():
        unittest.main()