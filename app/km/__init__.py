from flask import Blueprint

km_bp = Blueprint('km', __name__)

from . import views