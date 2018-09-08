from flask import Blueprint

researchbp = Blueprint('research', __name__)

from . import views