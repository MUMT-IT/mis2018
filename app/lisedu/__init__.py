from flask import Blueprint

lisedu = Blueprint('lisedu', __name__)

from . import views