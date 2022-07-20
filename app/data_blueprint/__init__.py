from flask import Blueprint

data_bp = Blueprint('data_bp', __name__)

from . import views

