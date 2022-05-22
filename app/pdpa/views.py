# -*- coding:utf-8 -*-
from flask import render_template, flash, redirect, url_for
from sqlalchemy import or_

from . import pdpa_blueprint as pdpa
from app.models import Dataset
from .models import *
from .forms import *


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
        flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
        return redirect(url_for('pdpa.confirm_submission', request_id=req.id))
    if form.errors:
        flash(form.errors, 'is-danger')
    return render_template('pdpa/request_form.html', form=form, req_type=req_type)


@pdpa.route('requests/<int:request_id>/submission')
def confirm_submission(request_id):
    return render_template('pdpa/submission.html')