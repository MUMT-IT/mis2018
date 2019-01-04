from flask import Blueprint

assetbp = Blueprint('asset', __name__)

from . import views
