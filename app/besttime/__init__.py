from flask import Blueprint

besttime_bp = Blueprint('besttime', __name__, url_prefix='/besttime')

from . import views