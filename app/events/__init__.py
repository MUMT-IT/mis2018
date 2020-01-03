from flask import Blueprint

event_bp = Blueprint('event', __name__)

from . import views