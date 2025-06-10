from flask import Blueprint

service_admin = Blueprint('service_admin', __name__, url_prefix='/service_admin')

from . import views