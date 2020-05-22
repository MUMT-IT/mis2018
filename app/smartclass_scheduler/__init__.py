from flask import Blueprint


smartclass_scheduler_blueprint = Blueprint('smartclass_scheduler', __name__)

from . import views