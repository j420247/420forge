import os
import boto3

# define the Atlassian products that Forge supports
PRODUCTS = [
    'Confluence',
    'Crowd',
    'Jira'
]

# define the valid states of a Cloudformation stack
VALID_STACK_STATUSES = [
    'CREATE_COMPLETE',
    'CREATE_IN_PROGRESS',
    'DELETE_FAILED',
    'DELETE_IN_PROGRESS',
    'ROLLBACK_COMPLETE',
    'ROLLBACK_IN_PROGRESS',
    'UPDATE_COMPLETE',
    'UPDATE_IN_PROGRESS',
    'UPDATE_ROLLBACK_COMPLETE',
    'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS',
    'UPDATE_ROLLBACK_IN_PROGRESS'
]

# grab AWS account ID for S3 bucket fallback names
_AWS_ACCOUNT_ID = boto3.client('sts').get_caller_identity().get('Account')

# set names for S3 buckets from env vars or use defaults
S3_BUCKETS = {
    'config':      os.environ.get('ATL_FORGE_S3_CONFIG', f'atl-forge-config-{_AWS_ACCOUNT_ID}'),
    'templates':   os.environ.get('ATL_FORGE_S3_TEMPLATES', f'atl-forge-templates-{_AWS_ACCOUNT_ID}'),
    'stacklogs':   os.environ.get('ATL_FORGE_S3_STACKLOGS', f'atl-forge-stacklogs-{_AWS_ACCOUNT_ID}')
    # not used by forge yet
    # 'diagnostics': os.environ.get('ATL_FORGE_S3_DIAGNOSTICS', f'atl-forge-diagnostics-{_AWS_ACCOUNT_ID}')
}
