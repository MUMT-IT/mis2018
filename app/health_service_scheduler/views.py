from flask import render_template, request, flash, redirect, url_for
from models import *
from forms import *

from . import health_service_blueprint as hs


@hs.route('/')
def index():
    return render_template('health_service_scheduler/index.html')


@hs.route('/sites/add', methods=['GET', 'POST'])
def add_site():
    form = ServiceSiteForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            site = HealthServiceSite()
            form.populate_obj(site)
            db.session.add(site)
            db.session.commit()
            flash(u'New site has been added.', 'success')
            return redirect(url_for('health_service_scheduler.get_sites'))
        else:
            for field, err in form.errors:
                flash(u'{}:{}'.format(field, err), 'danger')
    return render_template('health_service_scheduler/site_form.html', form=form)


@hs.route('/sites')
def get_sites():
    sites = HealthServiceSite.query.all()
    return render_template('health_service_scheduler/sites.html', sites=sites)


@hs.route('/services')
def get_services():
    services = HealthServiceService.query.all()
    return render_template('health_service_scheduler/services.html', services=services)


@hs.route('/services/add', methods=['GET', 'POST'])
def add_service():
    form = ServiceForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            service = HealthServiceService()
            form.populate_obj(service)
            db.session.add(service)
            db.session.commit()
            flash(u'New service has been added.', 'success')
            return redirect(url_for('health_service_scheduler.get_services'))
        else:
            for field, err in form.errors:
                flash(u'{}:{}'.format(field, err), 'danger')
    return render_template('health_service_scheduler/service_form.html', form=form)
