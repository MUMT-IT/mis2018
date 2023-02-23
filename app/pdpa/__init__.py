from flask import Blueprint

pdpa_blueprint = Blueprint('pdpa', __name__)

from . import views