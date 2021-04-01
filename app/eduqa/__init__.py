from flask import Blueprint

eduqa_bp = Blueprint('eduqa', __name__)


from . import views