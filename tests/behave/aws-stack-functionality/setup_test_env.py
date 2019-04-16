import boto3
from flask import current_app
from moto import mock_cloudformation, mock_ec2, mock_s3, mock_route53

REGION = 'us-east-1'
CONF_STACKNAME = 'my-confluence'
S3_BUCKET='mock_bucket'


@mock_s3
@mock_ec2
@mock_route53
@mock_cloudformation
def setup_env_resources():
    # create S3 bucket
    s3 = boto3.resource('s3', region_name=REGION)
    s3.create_bucket(Bucket=S3_BUCKET)

    # create VPC and subnets
    ec2 = boto3.resource('ec2', region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock='10.0.0.0/24')
    subnet_1 = vpc.create_subnet(CidrBlock='10.0.0.0/25')
    subnet_2 = vpc.create_subnet(CidrBlock='10.0.0.0/26')

    # create hosted zone
    r53 = boto3.client('route53')
    hosted_zone = r53.create_hosted_zone(
        Name='wpt.atlassian.com.',
        VPC={
            'VPCRegion': REGION,
            'VPCId': vpc.vpc_id
        },
        CallerReference='caller_ref',
        HostedZoneConfig={
            'Comment': 'string',
            'PrivateZone': True
        },
        DelegationSetId='string'
    )
    resources = {}
    resources['vpc_id'] = vpc.vpc_id
    resources['subnet_1_id'] = subnet_1.subnet_id
    resources['subnet_2_id'] = subnet_2.subnet_id
    resources['hosted_zone'] = hosted_zone

    current_app.config['RESOURCES'] = resources