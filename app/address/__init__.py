from flask import Blueprint

address = Blueprint('address', __name__, url_prefix='/address')

from . import views