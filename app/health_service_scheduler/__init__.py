from flask import Blueprint

health_service_blueprint = Blueprint('health_service_scheduler', __name__)

from . import views
from . import apis