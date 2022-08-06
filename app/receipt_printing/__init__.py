from flask import Blueprint

receipt_printing_bp = Blueprint('receipt_printing', __name__)

from . import views