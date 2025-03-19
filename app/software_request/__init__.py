from flask import Blueprint

software_request = Blueprint('software_request', __name__, url_prefix='/software_request')

from . import views