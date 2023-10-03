from flask import Blueprint

esign = Blueprint('e_sign', __name__, url_prefix='/e-sign')

from .views import *