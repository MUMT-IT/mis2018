from flask import Blueprint

staffbp = Blueprint('staff', __name__)

from . import views