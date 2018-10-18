from flask import Blueprint

roombp = Blueprint('room', __name__)

from . import views
