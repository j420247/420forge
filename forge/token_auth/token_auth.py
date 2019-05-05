from flask import Blueprint, request, jsonify, g, session
from forge.saml_auth.saml_auth import RestrictedResource
from .models import *
from datetime import datetime


token_blueprint = Blueprint('token_auth', __name__)


class DoCreateToken(RestrictedResource):
    def post(self, stack_name):
        User.init_db(self)
        try:
            content = request.get_json()
            expiry = content['expiry']
        except:
            expiry = 600
        user = User(
            username=session['saml']['subject'],
            token=User.generate_auth_token(self, expiration=expiry),
            granted=datetime.now(),
            email=session['saml']['attributes']['User.Email'][0],
            expiry=expiry,
            memberOf=f"{session['saml']['attributes']['memberOf']}",
        )
        db.session.add(user)
        db.session.commit()
        token = user.token.decode("utf-8")
        return token

    @staticmethod
    def get_auth_token(self):
        token = g.DoCreateToken.generate_auth_token(600)
        return jsonify({'token': token.decode('ascii'), 'duration': 600})
