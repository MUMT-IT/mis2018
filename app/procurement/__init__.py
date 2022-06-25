from flask import Blueprint

procurementbp = Blueprint('procurement', __name__)

from . import views