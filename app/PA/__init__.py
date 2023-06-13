from flask import Blueprint

pa_blueprint = Blueprint('pa', __name__, '/pa')

from . import views