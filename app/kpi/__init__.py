from flask import Blueprint

kpibp = Blueprint('kpi', __name__)

from . import views