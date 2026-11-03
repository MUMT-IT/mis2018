from flask import Blueprint

bp = Blueprint('line_mini_app', __name__, url_prefix='/miniapp')

from . import views
