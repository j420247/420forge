import argparse
import os
import re
from pathlib import Path

import boto3
import botocore
import forge_const
from ruamel import yaml

from lib import forge_const


class ForgeConfig:
    """configuration management class for Forge"""
    def __init__(self):

        # load config files
        local_config_file = Path('config.yml')
        if local_config_file.is_file():
            with open(local_config_file) as config_file:
                config_file = yaml.safe_load(config_file)
        else:
            s3 = boto3.client('s3')
            try:
                config_file = s3.get_object(Bucket=forge_const.S3_BUCKETS['config'], Key='config.yml')
                config_file = yaml.safe_load(config_file['Body'].read())
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    print(f"no config file found in bucket: ${forge_const.S3_BUCKETS['config']}")
                    print(f'no regions or SAML auth permissions will be loaded')
                else:
                    raise e

        # load regions
        try:
            self.regions = config_file['regions']
        except Exception:
            print(f'no configured regions found; using default us-east-1')
            self.regions = {"us-east-1": "US East 1"}

        # load saml auth permissions
        try:
            self.permissions = config_file['permissions']
        except Exception:
            print(f'no configured saml auth permissions found; saml auth will not be available if enabled')

        # grab environment variables
        self.flask_secret = os.environ.get('ATL_FORGE_SECRET', 'key_to_the_forge')
        self.saml_metadata_url = os.environ.get('ATL_FORGE_SAML_METADATA_URL')
        self.port = os.environ.get('ATL_FORGE_PORT', 8000)

        # empty vars for user args
        self.dev = False
        self.saml = False

        # pull in our constants
        for k in vars(forge_const).keys():
            if re.match(r"^[A-Z0-9]+[A-Z0-9_]+$", k):
                setattr(self, k, getattr(forge_const, k))

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Atlassian CloudFormation Forge')
        parser.add_argument('--saml', action='store_true', help='Use SAML auth')
        parser.add_argument('--dev', action='store_true', help='Run flask app in debug mode for local development')
        user_args = parser.parse_args()
        self.dev = user_args.dev
        self.saml = user_args.saml
