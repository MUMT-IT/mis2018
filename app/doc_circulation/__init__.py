from flask import Blueprint

docbp = Blueprint('doc', __name__)

from . import views