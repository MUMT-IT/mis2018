from flask import render_template
from . import comhealth
from .models import ComHealthService

@comhealth.route('/')
def index():
    services = ComHealthService.query.order_by('date desc').all()
    return render_template('comhealth/index.html',
                           services=services)