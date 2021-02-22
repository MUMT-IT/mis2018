from flask import render_template

from . import health_service_blueprint as hb

@hb.route('/')
def index():
    return render_template('health_service_scheduler/index.html')