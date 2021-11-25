# -*- coding:utf-8 -*-
from flask import render_template, request, flash, redirect, url_for, session, jsonify, Flask
from flask_login import current_user, login_required
from . import purchase_tracker_bp as purchase_tracker
from ..main import db
from .forms import *
from datetime import datetime
from pytz import timezone

from .models import PurchaseTrackerAccount, PurchaseTrackerRecord

bangkok = timezone('Asia/Bangkok')

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

@purchase_tracker.route('/home')
def index():
    return render_template('purchase_tracker/index.html')

@purchase_tracker.route('/create', methods=['GET', 'POST'])
def add_account():
    form = RegisterAccountForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        else:
            purchase_tracker = PurchaseTrackerAccount()
            form.populate_obj(purchase_tracker)
            db.session.add(purchase_tracker)
            db.session.commit()
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return render_template('purchase_tracker/index.html')
    return render_template('purchase_tracker/create_account.html', form=form)

@purchase_tracker.route('/track')
def track():
    return render_template('purchase_tracker/tracking.html')

@purchase_tracker.route('/finance')
def finance():
    return render_template('purchase_tracker/finance_record.html')

@purchase_tracker.route('/supplies')
def supplies():
    return render_template('purchase_tracker/procedure_supplies.html')

@purchase_tracker.route('/description')
def description():
    return render_template('purchase_tracker/description.html')

@purchase_tracker.route('/receive', methods=['GET', 'POST'])
def receive():
    form = DeliveryForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        else:
            purchase_record = PurchaseTrackerRecord()
            purchase_record.staff = current_user
            form.populate_obj(purchase_record)
            db.session.add(purchase_record)
            db.session.commit()
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return render_template('purchase_tracker/procedure_supplies.html')
    return render_template('purchase_tracker/receive_record.html', form=form)

@purchase_tracker.route('/sender', methods=['GET', 'POST'])
def sender():
    form = DeliveryForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        else:
            purchase_record = PurchaseTrackerRecord()
            purchase_record.staff = current_user
            form.populate_obj(purchase_record)
            db.session.add(purchase_record)
            db.session.commit()
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return render_template('purchase_tracker/procedure_supplies.html')
    return render_template('purchase_tracker/sender_record.html', form=form)

@purchase_tracker.route('/arrive', methods=['GET', 'POST'])
def arrive():
    form = DeliveryForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        else:
            purchase_record = PurchaseTrackerRecord()
            purchase_record.staff = current_user
            form.populate_obj(purchase_record)
            db.session.add(purchase_record)
            db.session.commit()
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return render_template('purchase_tracker/procedure_supplies.html')
    return render_template('purchase_tracker/arrive_at_record.html', form=form)

@purchase_tracker.route('/back', methods=['GET', 'POST'])
def deliver_back():
    form = DeliveryForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        else:
            purchase_record = PurchaseTrackerRecord()
            purchase_record.staff = current_user
            form.populate_obj(purchase_record)
            db.session.add(purchase_record)
            db.session.commit()
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return render_template('purchase_tracker/procedure_supplies.html')
    return render_template('purchase_tracker/deliver_back_record.html', form=form)

@purchase_tracker.route('/problem', methods=['GET', 'POST'])
def problem():
    form = DeliveryForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        else:
            purchase_record = PurchaseTrackerRecord()
            purchase_record.staff = current_user
            form.populate_obj(purchase_record)
            db.session.add(purchase_record)
            db.session.commit()
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return render_template('purchase_tracker/procedure_supplies.html')
    return render_template('purchase_tracker/problem_record.html', form=form)

@purchase_tracker.route('/remain', methods=['GET', 'POST'])
def remain():
    form = DeliveryForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        else:
            purchase_record = PurchaseTrackerRecord()
            purchase_record.staff = current_user
            form.populate_obj(purchase_record)
            db.session.add(purchase_record)
            db.session.commit()
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return render_template('purchase_tracker/procedure_supplies.html')
    return render_template('purchase_tracker/remain_record.html', form=form)