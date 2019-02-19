from flask import session, request, Blueprint
from flask_restful import Resource, current_app
import flask_saml
from werkzeug.contrib.fixers import ProxyFix
import sys
from flask_sqlalchemy import SQLAlchemy
from flask_sessionstore import Session
from os import path
import json
from sys import argv

saml_blueprint = Blueprint('saml_auth', __name__)

def configure_saml(ssm_client):
    # Create a SQLalchemy db for session and permission storge.
    current_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///acforge.db'
    current_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # suppress warning messages
    current_app.config['SESSION_TYPE'] = 'sqlalchemy'
    db = SQLAlchemy(current_app)
    session_store = Session(current_app)
    session_store.app.session_interface.db.create_all()

    # load permissions file
    #TODO think about whether we want to restrict based on environment tags or regions
    try:
        with open(path.join(path.dirname(__file__), 'permissions.json')) as json_data:
            current_app.json_perms = json.load(json_data)
    except Exception:
        print('could not open permissions.json; SAML auth will not work!')

    current_app.wsgi_app = ProxyFix(current_app.wsgi_app)
    print('SAML auth configured')
    try:
        saml_protocol = ssm_client.get_parameter(
            Name='atl_forge_saml_metadata_protocol',
            WithDecryption=True
        )
        saml_url = ssm_client.get_parameter(
            Name='atl_forge_saml_metadata_url',
            WithDecryption=True
        )
        current_app.config['SAML_METADATA_URL'] = f"{saml_protocol['Parameter']['Value']}://{saml_url['Parameter']['Value']}"
    except Exception:
        print('SAML is configured but there is no SAML metadata URL in the parameter store - exiting')
        sys.exit(1)
    flask_saml.FlaskSAML(current_app)


##
#### All actions need to pass through the sub class (RestrictedResource) to control permissions -
#### (doupgrade, doclone, dofullrestart, dorollingrestart, dorollingrebuild, docreate, dodestroy, dothreaddumps, doheapdumps dorunsql, doupdate, status)
##
class RestrictedResource(Resource):
    def dispatch_request(self, *args, **kwargs):
        if '--nosaml' in argv:
            return super().dispatch_request(*args, **kwargs)
        # check permissions before returning super
        for keys in current_app.json_perms:
            if current_app.json_perms[keys]['group'][0] in session['saml']['attributes']['memberOf']:
                if session['region'] in current_app.json_perms[keys]['region'] or '*' in current_app.json_perms[keys]['region']:
                    if request.endpoint in current_app.json_perms[keys]['action'] or '*' in current_app.json_perms[keys]['action']:
                        if request.endpoint in ('docreate', 'doclone'):
                            # do not check stack_name on stack creation/clone
                            print(f'User is authorised to perform {request.endpoint}')
                            return super().dispatch_request(*args, **kwargs)
                        elif kwargs['stack_name'] in current_app.json_perms[keys]['stack'] or '*' in current_app.json_perms[keys]['stack']:
                            print(f'User is authorised to perform {request.endpoint} on {kwargs["stack_name"]}')
                            return super().dispatch_request(*args, **kwargs)
        print(f'User is not authorised to perform {request.endpoint} on {kwargs["stack_name"]}')
        return 'Forbidden', 403