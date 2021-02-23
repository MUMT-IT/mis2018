from flask import render_template
from forms import *

from . import health_service_blueprint as hs


@hs.route('/')
def index():
    return render_template('health_service_scheduler/index.html')


@hs.route('/sites/add')
def add_site():
    form = ServiceSiteForm()
    return render_template('health_service_scheduler/site_form.html', form=form)


@hs.route('/sites')
def get_sites():
    sites = HealthServiceSite.query.all()
    return render_template('health_service_scheduler/sites.html', sites=sites)
