from flask import Blueprint

user_eval = Blueprint('user_eval', __name__, url_prefix='/user_eval')

from . import views