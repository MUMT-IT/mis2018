# -*- coding:utf-8 -*-

from . import data_bp
from app.main import db
from app.models import CoreService, Process, Data, KPI
from forms import *
from flask import url_for, render_template, redirect, flash, request
from flask_login import current_user, login_required


@data_bp.route('/')
def index():
    data = Data.query.all()
    core_services = CoreService.query.all()
    back_office_processes = Process.query.filter_by(category='back_office').all()
    crm_processes = Process.query.filter_by(category='crm').all()
    performance_processes = Process.query.filter_by(category='performance').all()
    regulation_processes = Process.query.filter_by(category='regulation').all()
    return render_template('data_blueprint/index.html',
                                core_services=core_services,
                                data=data,
                                back_office_processes=back_office_processes,
                                crm_processes=crm_processes,
                                performance_processes=performance_processes,
                                regulation_processes=regulation_processes,
                                )


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


@data_bp.route('/kpi/new', methods=['GET', 'POST'])
@data_bp.route('/kpi/<int:kpi_id>/edit', methods=['GET', 'POST'])
@login_required
def kpi_form(kpi_id=None):
    if kpi_id:
        data_ = KPI.query.get(kpi_id)
        form = KPIForm(obj=data_)
    else:
        form = KPIForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            if not kpi_id:
                new_data = KPI()
                form.populate_obj(new_data)
                new_data.creator_id = current_user.id
                db.session.add(new_data)
            else:
                form.populate_obj(data_)
                db.session.add(data_)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
            return redirect(url_for('data_bp.index'))
    return render_template('data_blueprint/kpi_form.html', form=form)


@data_bp.route('/data/<int:data_id>', methods=['GET'])
@login_required
def data_detail(data_id):
    data = Data.query.get(data_id)
    return render_template('data_blueprint/data_detail.html', data=data)


@data_bp.route('/data/<int:data_id>/datasets/<int:dataset_id>/edit', methods=['GET', 'POST'])
@data_bp.route('/data/<int:data_id>/datasets/form', methods=['GET', 'POST'])
@login_required
def dataset_form(data_id, dataset_id=None):
    if dataset_id:
        dataset = Dataset.query.get(dataset_id)
        form = createDatasetForm(data_id=data_id)(obj=dataset)
    else:
        form = createDatasetForm(data_id=data_id)()
    if request.method == 'POST':
        if form.validate_on_submit():
            if not dataset_id:
                new_dataset = Dataset()
                form.populate_obj(new_dataset)
                new_dataset.creator_id = current_user.id
                new_dataset.data_id = data_id
                db.session.add(new_dataset)
            else:
                form.populate_obj(dataset)
                db.session.add(dataset)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
            return redirect(url_for('data_bp.data_detail', data_id=data_id))
    return render_template('data_blueprint/dataset_form.html', form=form)


@data_bp.route('/datasets/<int:dataset_id>', methods=['GET'])
@login_required
def dataset_detail(dataset_id):
    ds = Dataset.query.get(dataset_id)
    return render_template('data_blueprint/data_detail.html', data=ds)
