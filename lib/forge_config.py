import argparse
import os
from pathlib import Path

import boto3
import botocore
from ruamel import yaml

from lib import forge_const


class ForgeConfig:
    """configuration management class for Forge"""
    def __init__(self):

        print('Initializing...')

        # empty vars for user args
        self.dev = False
        self.saml = False

        # parse user args
        self._parse_args()

        config_file = None

        # load config file
        config_file_path = Path('config.yml')
        if config_file_path.is_file():
            with open(config_file_path) as config_file:
                config_file = yaml.safe_load(config_file)
        else:
            s3 = boto3.client('s3')
            try:
                config_file = s3.get_object(Bucket=forge_const.S3_BUCKETS['config'], Key='config.yml')
                config_file = yaml.safe_load(config_file['Body'].read())
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    print(f"no config file found in bucket: {forge_const.S3_BUCKETS['config']}")
                    print(f'no regions or SAML auth permissions will be loaded')
                elif e.response['Error']['Code'] == 'NoSuchBucket':
                    print(f"S3 bucket for configuration ({forge_const.S3_BUCKETS['config']}) not found")
                    print(f'no regions or SAML auth permissions will be loaded')
                else:
                    raise e

        # load aws_defaults; provide us-east-1 as fallback region
        self.aws_defaults = {}
        self.aws_defaults['regions'] = {"us-east-1": "US East 1"}
        self._load_from_config(config_file, 'aws_defaults', 'no aws configuration found; using default us-east-1 region')

        # load saml auth permissions
        self._load_from_config(config_file, 'permissions', 'no configured saml auth permissions found; saml auth will not be available if enabled')

        # grab environment variables
        self.analytics_ua = os.environ.get('ATL_FORGE_ANALYTICS_UA')
        self.flask_secret = os.environ.get('ATL_FORGE_FLASK_SECRET', os.urandom(24))
        self.saml_metadata_url = os.environ.get('ATL_FORGE_SAML_METADATA_URL')
        self.port = os.environ.get('ATL_FORGE_PORT', 8000)

    def _load_from_config(self, config, key, err_msg):
        try:
            setattr(self, key, config[key])
        except Exception:
            print(err_msg)

    def _parse_args(self):
        parser = argparse.ArgumentParser(description='Atlassian CloudFormation Forge')
        parser.add_argument('--saml', action='store_true', help='Use SAML auth')
        parser.add_argument('--dev', action='store_true', help='Run flask app in debug mode for local development')
        user_args = parser.parse_args()
        self.dev = user_args.dev
        self.saml = user_args.saml


FORGE_CONFIG = ForgeConfig()
