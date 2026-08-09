from flask import Blueprint

maintenancebp = Blueprint('maintenance', __name__)

from app.maintenance import models
from app.maintenance import views
