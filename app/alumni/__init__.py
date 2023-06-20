from flask import Blueprint

alumnibp = Blueprint('alumni', __name__)

from . import views