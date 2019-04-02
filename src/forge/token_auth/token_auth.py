from flask import session, request, Blueprint, current_app, Flask, abort, request, jsonify, g, url_for
from forge.saml_auth.saml_auth import RestrictedResource
from .models import *


token_blueprint = Blueprint('token_auth', __name__)


class DoCreateToken(RestrictedResource):
    def post(self):
        User.init_db(self)
        content = request.get_json()
        user = User(username=content['username'], token=User.generate_auth_token(self))
        db.session.add(user)
        db.session.commit()
        return user.token.decode("utf-8")

    @staticmethod
    def get_auth_token(self):
        token = g.DoCreateToken.generate_auth_token(600)
        return jsonify({'token': token.decode('ascii'), 'duration': 600})
