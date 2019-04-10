import argparse
from flask import Flask
import boto3
import botocore
from forge.version import __version__
from forge.config import config

# Import Blueprints
from forge.api import api_blueprint
from forge.aws_cfn_stack import aws_cfn_stack_blueprint
from forge.main import main as main_blueprint
from forge.saml_auth import saml_blueprint, saml_auth
from dotenv import load_dotenv
from os import getenv


def create_app(config_class):

    # load .env file
    load_dotenv()
    # create and initialize app
    print(f'Starting Atlassian CloudFormation Forge v{__version__}')
    app = Flask(__name__)
    app.config.from_object(config_class)

    # get current region and create SSM client to read parameter store params
    ssm_client = boto3.client('ssm', region_name=getenv('REGION', 'us-east-1'))
    app.config['SECRET_KEY'] = 'REPLACE_ME'
    try:
        key = ssm_client.get_parameter(Name='atl_forge_secret_key', WithDecryption=True)
        app.config['SECRET_KEY'] = key['Parameter']['Value']
    except botocore.exceptions.NoCredentialsError as e:
        print('No credentials - please authenticate with Cloudtoken')
    except Exception:
        print('No secret key in parameter store')

    # create SAML URL if saml enabled
    if not getenv('NO_SAML'):
        saml_auth.configure_saml(ssm_client, app)
    else:
        print('SAML auth is not configured')

    # Register Blueprints
    app.register_blueprint(api_blueprint)
    app.register_blueprint(main_blueprint)
    app.register_blueprint(aws_cfn_stack_blueprint)
    app.register_blueprint(saml_blueprint, url_prefix='/saml')

    return app
