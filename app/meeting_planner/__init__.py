from flask import Blueprint

meeting_planner = Blueprint('meeting_planner', __name__, url_prefix='/meeting_planner')

from . import views