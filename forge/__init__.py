from flask import Flask
import boto3
import botocore
from forge.version import __version__
from forge.config import config
from logging.handlers import RotatingFileHandler
import logging
from dotenv import load_dotenv
import os
from os import getenv

# Import Blueprints
from forge.api import api_blueprint
from forge.aws_cfn_stack import aws_cfn_stack_blueprint
from forge.main import main as main_blueprint
from forge.saml_auth import saml_blueprint, saml_auth

log = logging.getLogger('app_log')


def create_app(config_class):
    # create log directory
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # init loggers
    access_log_handler = RotatingFileHandler(f'{log_dir}/forge_access.log', maxBytes=10000000, backupCount=5)
    access_log_handler.setLevel(logging.INFO)
    access_log = logging.getLogger('werkzeug')
    access_log.addHandler(access_log_handler)

    app_log_handler = RotatingFileHandler(f'{log_dir}/forge.log', maxBytes=10000000, backupCount=5)
    app_log_handler.setLevel(logging.INFO)
    log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s', '%Y-%m-%d %H:%M:%S')
    app_log_handler.setFormatter(log_formatter)
    app_log = logging.getLogger('app_log')
    app_log.addHandler(app_log_handler)

    # load .env file
    load_dotenv()
    # create and initialize app
    log.info(f'Starting Atlassian CloudFormation Forge v{__version__}')
    app = Flask(__name__)
    app.config.from_object(config_class)

    # get current region and create SSM client to read parameter store params
    ssm_client = boto3.client('ssm', region_name=getenv('REGION', 'us-east-1'))
    app.config['SECRET_KEY'] = 'REPLACE_ME'
    try:
        key = ssm_client.get_parameter(Name='atl_forge_secret_key', WithDecryption=True)
        app.config['SECRET_KEY'] = key['Parameter']['Value']
    except botocore.exceptions.NoCredentialsError as e:
        log.error('No credentials - please authenticate with Cloudtoken')
    except Exception:
        log.error('No secret key in parameter store')

    # create SAML URL if saml enabled
    if not getenv('NO_SAML') and not app.config['NO_SAML']:
        saml_auth.configure_saml(ssm_client, app)
    else:
        log.info('SAML auth is not configured')

    # Register Blueprints
    app.register_blueprint(api_blueprint)
    app.register_blueprint(main_blueprint)
    app.register_blueprint(aws_cfn_stack_blueprint)
    app.register_blueprint(saml_blueprint, url_prefix='/saml')

    return app
