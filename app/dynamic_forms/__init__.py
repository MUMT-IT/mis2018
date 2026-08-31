from flask import Blueprint

dynamic_forms_bp = Blueprint('dynamic_forms', __name__)

from . import views  # noqa: E402,F401
