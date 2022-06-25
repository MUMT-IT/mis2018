from flask import Blueprint

purchase_tracker_bp = Blueprint('purchase_tracker', __name__)

from . import views