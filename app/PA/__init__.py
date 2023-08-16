from flask import Blueprint

pa_blueprint = Blueprint('pa', __name__, url_prefix='/pa')

from . import views