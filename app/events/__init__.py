from flask import Blueprint

event_bp = Blueprint('event_bp', __name__)

from . import views