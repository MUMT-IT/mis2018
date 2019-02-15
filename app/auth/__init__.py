from flask import Blueprint

authbp = Blueprint('auth', __name__)

from . import views
