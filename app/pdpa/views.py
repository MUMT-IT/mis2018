# -*- coding:utf-8 -*-
from flask import render_template, flash, redirect, url_for
from flask_mail import Message
from sqlalchemy import or_

from . import pdpa_blueprint as pdpa
from app.models import Dataset
from app.main import mail
from .models import *
from .forms import *


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


@pdpa.route('/')
def index():
    services = set()
    for dataset in Dataset.query.filter(or_(Dataset.personal==True, Dataset.sensitive==True)):
        for process in dataset.data.core_services:
            services.add(process)
    return render_template('pdpa/index.html', services=services)


@pdpa.route('services/<int:service_id>/requests')
def request_index(service_id):
    request_types = PDPARequestType.query.all()
    return render_template('pdpa/comhealth/requests.html', request_types=request_types, service_id=service_id)


@pdpa.route('services/<int:service_id>/requests/<int:request_type_id>', methods=['GET', 'POST'])
def request_form(service_id, request_type_id):
    req_type = PDPARequestType.query.get(request_type_id)
    service = CoreService.query.get(service_id)
    MyPDPARequestForm = request_form_factory(service)
    form = MyPDPARequestForm()
    if form.validate_on_submit():
        req = PDPARequest()
        form.populate_obj(req)
        req.service = service
        req.request_type_id = request_type_id
        db.session.add(req)
        db.session.commit()
        title = req_type.name
        message = u'Request: {}\n'.format(req_type.name)
        message += u'Service: {}\n'.format(service.service)
        message += u'Name: {}\n'.format(req.requester_name)
        message += u'E-mail: {}\n'.format(req.requester_email)
        message += u'Phone: {}\n'.format(req.requester_phone)
        message += u'Created at: {}'.format(req.created_at.strftime('%Y-%m-%d %H:%M'))
        send_mail([u'{}@mahidol.ac.th'.format(s.email) for s in service.pdpa_coordinators], title, message)
        flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
        return redirect(url_for('pdpa.confirm_submission', request_id=req.id))
    if form.errors:
        for field, errs in form.errors.items():
            flash(', '.join(errs), 'danger')
    return render_template('pdpa/request_form.html', form=form, req_type=req_type)


@pdpa.route('requests/<int:request_id>/submission')
def confirm_submission(request_id):
    return render_template('pdpa/submission.html')