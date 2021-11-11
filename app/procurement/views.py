# -*- coding:utf-8 -*-
from flask import render_template, request, flash, redirect, url_for, session, jsonify, Flask
from flask_login import current_user, login_required
from . import procurementbp as procurement
from .models import ProcurementDetail
from ..main import db
from .forms import *
from datetime import datetime
from pytz import timezone

bangkok = timezone('Asia/Bangkok')


@procurement.route('/add', methods=['GET','POST'])
@login_required
def add_procurement():
    if request.method == 'POST':
        form = request.form
        procurement = ProcurementDetail(
            list=form.get('list'),
            code=form.get('code'),
            available=form.get('available'),
            category_id=form.get('category_id'),
            model=form.get('model'),
            maker=form.get('maker'),
            size=form.get('size'),
            desc=form.get('desc'),
            comment=form.get('comment'),
        )
        db.session.add(procurement)
        db.session.commit()
        return render_template('procurement/index.html')
    return render_template('procurement/new_procurement.html')


@procurement.route('/home')
def index():
    return render_template('procurement/index.html')


@procurement.route('/alldata')
@login_required
def view_procurement():
    procurement_list = []
    procurement_query = ProcurementDetail.query.all()
    for procurement in procurement_query:
        record = {}
        record["id"] = procurement.id
        record["list"] = procurement.list
        record["code"] = procurement.code
        record["available"] = procurement.available
        procurement_list.append(record)
    return render_template('procurement/view_all_data.html', procurement_list=procurement_list)


@procurement.route('/createqrcode', methods=['POST', 'GET'])
@login_required
def create_qrcode():
    qr = None
    if request.method == 'POST':
        qr = request.form['inputtext']
    return render_template('procurement/generate_qrcode.html', qr=qr)


@procurement.route('/explanation')
def explanation():
    return render_template('procurement/explanation.html')

@procurement.route('/edit/<int:procurement_id>', methods=['GET','POST'])
@login_required
def edit_procurement(procurement_id):
    procurement = ProcurementDetail.query.get(procurement_id)
    if request.method == 'POST':
        form = request.form
        procurement.list = form.get('list')
        procurement.type = form.get('type')
        procurement.code = form.get('code')
        procurement.location = form.get('location')
        procurement.available = form.get('available')
        db.session.add(procurement)
        db.session.commit()
        flash(u'แก้ไขข้อมูลเรียบร้อย', 'success')
        return redirect(url_for('procurement.view_procurement'))
    return render_template('procurement/edit_procurement.html', procurement=procurement)


@procurement.route('/viewqrcode/<int:procurement_id>')
@login_required
def view_qrcode(procurement_id):
    item = ProcurementDetail.query.get(procurement_id)
    return render_template('procurement/view_qrcode.html',
                           model=ProcurementRecord,
                           item=item,
                           code=item.code)


@procurement.route('/items/<int:item_id>/records/add', methods=['GET', 'POST'])
@login_required
def add_record(item_id):
    form = ProcurementRecordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_record = ProcurementRecord()
            form.populate_obj(new_record)
            new_record.item_id = item_id
            new_record.staff = current_user
            new_record.updated_at = datetime.now(tz=bangkok)
            db.session.add(new_record)
            db.session.commit()
            flash('New Record Has Been Added.', 'success')
            return redirect(url_for('procurement.view_procurement'))
    return render_template('procurement/record_form.html', form=form)