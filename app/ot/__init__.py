from flask import Blueprint

otbp = Blueprint('ot', __name__)

from . import views