from flask import Blueprint

academic_service_payment = Blueprint('academic_service_payment', __name__, url_prefix='/academic_service_payment')

from . import views