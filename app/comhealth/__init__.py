from flask import Blueprint

comhealth = Blueprint('comhealth', __name__)

from . import views