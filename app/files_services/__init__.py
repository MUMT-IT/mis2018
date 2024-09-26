from flask import Blueprint

files_services = Blueprint('files_services', __name__,url_prefix='/files_services')

from . import views