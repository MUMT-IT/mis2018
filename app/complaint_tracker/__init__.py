from flask import Blueprint

complaint_tracker = Blueprint('comp_tracker', __name__, url_prefix='/complaint-tracker')

from . import views