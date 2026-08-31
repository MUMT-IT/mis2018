from flask import Blueprint


shorturl = Blueprint('shorturl', __name__, url_prefix='/shorturl')

from .models import ShortUrlMapping
from . import views
