from flask import Blueprint

linebot_bp = Blueprint('linebot_bp', __name__)

from . import views
