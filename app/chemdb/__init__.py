from flask import Blueprint

chemdbbp = Blueprint('chemdb', __name__)

from . import views