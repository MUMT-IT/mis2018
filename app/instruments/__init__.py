from flask import Blueprint

instrumentsbp = Blueprint('instruments', __name__)

from . import views