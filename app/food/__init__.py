from flask import Blueprint

foodbp = Blueprint('food', __name__)

from . import views
