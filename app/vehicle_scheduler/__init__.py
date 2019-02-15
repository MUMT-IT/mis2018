from flask import Blueprint

vehiclebp = Blueprint('vehicle', __name__)

from . import views
