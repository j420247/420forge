class BaseConfig(object):
    # Defaults
    DEBUG = False
    TESTING = False
    PRODUCTS = ["Jira", "Confluence", "Crowd"]
    VALID_STACK_STATUSES = ['CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE', 'CREATE_IN_PROGRESS',
                            'DELETE_IN_PROGRESS', 'UPDATE_IN_PROGRESS', 'ROLLBACK_IN_PROGRESS', 'ROLLBACK_COMPLETE', 'ROLLBACK_FAILED',
                            'DELETE_FAILED', 'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS', 'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS', 'UPDATE_ROLLBACK_IN_PROGRESS']

    # User configuration properties
    REGIONS = [
        ('us-east-1', 'N.Virginia'),
        ('us-west-2', 'Oregon'),
        ('ap-southeast-2', 'Sydney'),
    ]
    ANALYTICS = 'true'
    S3_BUCKET = 'atl-cfn-forge-515798882395'

    # User default settings
    # These values can be used to automatically populate template parameters
    # This means you don't have to always copy/paste VPCs, subnets, hostedzones or ssh keys into the fields

    # VPCs
    # format vpc-56abc789
    DEFAULT_VPCS = {
        'us-east-1': 'vpc-320c1355',
        'us-west-2': 'vpc-dd8dc7ba',
        'lab': 'vpc-ff1b9284',
    }

    # Subnets
    # format 'subnet-12abc345,subnet-12abc346'
    DEFAULT_SUBNETS = {
        'vpc-320c1355': 'subnet-df0c3597,subnet-f1fb87ab',
        'vpc-dd8dc7ba': 'subnet-eb952fa2,subnet-f2bddd95',
        'vpc-ff1b9284': { 'dmz': 'subnet-a2b3a3c6,subnet-a9b08f86', 'external': 'subnet-d9162484,subnet-158d4b5f'} ,
    }

    # Hosted Zone
    # format 'myteam.example.com.'
    HOSTED_ZONE = 'wpt.atlassian.com.'

    # SSH Key
    SSH_KEY_NAME = 'WPE-GenericKeyPair-20161102'


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = True


class TestingConfig(BaseConfig):
    DEBUG = False
    TESTING = True