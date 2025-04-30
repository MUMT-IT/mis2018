from flask import Blueprint

academic_services = Blueprint('academic_services', __name__, url_prefix='/academic_services')

from . import views