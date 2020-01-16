from flask import Blueprint

kpibp = Blueprint('kpi_blueprint', __name__)

from . import views
