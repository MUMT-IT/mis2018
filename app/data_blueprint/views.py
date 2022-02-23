# -*- coding:utf-8 -*-

from . import data_bp
from app.main import db
from forms import *
from models import CoreService
from flask import url_for, render_template, redirect, flash, request
from flask_login import current_user, login_required


@data_bp.route('/')
def index():
    data = Data.query.all()
    core_services = CoreService.query.all()
    processes = Process.query.all()
    return render_template('data_blueprint/index.html',
                                core_services=core_services,
                                data=data,
                                processes=processes)


@data_bp.route('/core-services/new', methods=['GET', 'POST'])
@data_bp.route('/core-services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
def core_service_form(service_id=None):
    if service_id:
        service_ = CoreService.query.get(service_id)
        form = CoreServiceForm(obj=service_)
    else:
        form = CoreServiceForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            if not service_id:
                new_service = CoreService()
                form.populate_obj(new_service)
                new_service.creator_id = current_user.id
                db.session.add(new_service)
            else:
                form.populate_obj(service_)
                db.session.add(service_)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
            return redirect(url_for('data_bp.index'))
    return render_template('data_blueprint/core_services.html', form=form)


@data_bp.route('/data/new', methods=['GET', 'POST'])
@data_bp.route('/data/<int:data_id>/edit', methods=['GET', 'POST'])
@login_required
def data_form(data_id=None):
    if data_id:
        data_ = Data.query.get(data_id)
        form = DataForm(obj=data_)
    else:
        form = DataForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            if not data_id:
                new_data = Data()
                form.populate_obj(new_data)
                new_data.creator_id = current_user.id
                db.session.add(new_data)
            else:
                form.populate_obj(data_)
                db.session.add(data_)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
            return redirect(url_for('data_bp.index'))
    return render_template('data_blueprint/data_form.html', form=form)


@data_bp.route('/process/new', methods=['GET', 'POST'])
@data_bp.route('/process/<int:process_id>/edit', methods=['GET', 'POST'])
@login_required
def process_form(process_id=None):
    if process_id:
        data_ = Process.query.get(process_id)
        form = ProcessForm(obj=data_)
    else:
        form = ProcessForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            if not process_id:
                new_data = Process()
                form.populate_obj(new_data)
                new_data.creator_id = current_user.id
                db.session.add(new_data)
            else:
                form.populate_obj(data_)
                db.session.add(data_)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
            return redirect(url_for('data_bp.index'))
    return render_template('data_blueprint/process_form.html', form=form)
