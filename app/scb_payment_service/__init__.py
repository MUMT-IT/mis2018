from flask import Blueprint

scb_payment = Blueprint('scb_payment', __name__, url_prefix='/scb_payment')

from . import views