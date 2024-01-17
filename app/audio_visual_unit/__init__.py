from flask import Blueprint

audio_visual_unit_bp = Blueprint('audio_visual', __name__)

from . import views