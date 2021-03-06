class BaseConfig(object):
    ########
    ## Defaults
    DEBUG = False
    TESTING = False
    PRODUCTS = ["Jira", "Confluence", "Crowd"]
    VALID_STACK_STATUSES = [
        'CREATE_COMPLETE',
        'UPDATE_COMPLETE',
        'UPDATE_ROLLBACK_COMPLETE',
        'CREATE_IN_PROGRESS',
        'DELETE_IN_PROGRESS',
        'UPDATE_IN_PROGRESS',
        'ROLLBACK_IN_PROGRESS',
        'ROLLBACK_COMPLETE',
        'ROLLBACK_FAILED',
        'DELETE_FAILED',
        'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS',
        'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
        'UPDATE_ROLLBACK_IN_PROGRESS',
    ]
    ########
    ## User configuration properties
    REGIONS = [('us-east-1', 'N.Virginia'), ('us-west-2', 'Oregon'), ('ap-southeast-2', 'Sydney')]
    ANALYTICS = True
    S3_BUCKET = 'atl-cfn-forge-515798882395'

    ##
    ## Configurable timeouts for actions (in seconds)
    ACTION_TIMEOUTS = {
        'approve_zdu_upgrade': 3600,
        'cancel_zdu_mode': 300,
        'enable_zdu_mode': 300,
        'node_initialisation': 3600,
        'node_registration_deregistration': 3600,
        'validate_node_responding': 3600,
        'validate_service_responding': 3600,
        'zdu_ready_to_run_upgrade_tasks': 600,
        'zdu_upgrade_tasks_complete': 3600,
    }

    ########
    ## User default settings
    # These values can be used to automatically populate template parameters
    # This means you don't have to always copy/paste VPCs, subnets, hostedzones or ssh keys into the fields

    ## VPCs
    # format vpc-56abc789
    DEFAULT_VPCS = {'us-east-1': 'vpc-320c1355', 'us-west-2': 'vpc-dd8dc7ba', 'lab': 'vpc-ff1b9284'}
    ## Default subnets for each VPC
    # format 'vpc-56abc789': {'internal': 'subnet-12abc345,subnet-12abc346', 'external': 'subnet-12abc345,subnet-12abc346'}'
    DEFAULT_SUBNETS = {
        'vpc-320c1355': {'internal': 'subnet-df0c3597,subnet-f1fb87ab', 'external': 'subnet-df0c3597,subnet-f1fb87ab'},
        'vpc-dd8dc7ba': {'internal': 'subnet-eb952fa2,subnet-f2bddd95', 'external': 'subnet-eb952fa2,subnet-f2bddd95'},
        'vpc-ff1b9284': {'internal': 'subnet-d9162484,subnet-158d4b5f', 'external': 'subnet-782f5f32,subnet-afc26ff3'},
    }
    ## Hosted Zone
    # format 'myteam.example.com.'
    HOSTED_ZONE = 'wpt.atlassian.com.'
    ## SSH Key
    SSH_KEY_NAME = 'WPE-GenericKeyPair-20161102'

    ## Default parameters for cloning a stack
    # Enter defaults for desired parameters to be applied to all stacks
    # fmt: off
    CLONE_DEFAULTS = {
        'all': {
            'ClusterNodeCount': '1',
            'CustomDnsName': '',
            'DBMultiAZ': 'false',
            'DeployEnvironment': 'stg',
            'MailEnabled': 'false',
            'Monitoring': 'false',
            'TomcatScheme': 'http'
        },
        'foj-stg': {
            'ClusterNodeCount': '4',
            'CustomDnsName': 'mystack.mycompany.com'
        },
        # To create stack specific defaults, add a param with the stackname, as below
        # When cloning a stack of this name, these defaults will be applied over the top of the parameters above
        # 'mystack' = {
        #     'ClusterNodeMin': '2',
        #     'ClusterNodeMax': '2',
        #     'CustomDnsName': 'mystack.mycompany.com'
        # },
    }
    # fmt: on

    # Default URL for gravatar
    # To use a custom URL, specify the username, md5_of_email, email_address parameter in {}s for it to be injected for the user, eg
    # https://mycompany.com/avatars/{username}?size=Small
    AVATAR_URL = 'https://www.gravatar.com/avatar/{md5_of_email}.jpg?s=80&d=mp'

    ## Stack locking
    # Lock stack actions so only one can be performed at a time
    STACK_LOCKING = False

    # disable SAML by default
    NO_SAML = True

    # Default SNS region
    SNS_REGION = 'us-east-1'


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = True


class TestingConfig(BaseConfig):
    DEBUG = False
    TESTING = True
