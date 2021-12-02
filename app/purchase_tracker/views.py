# -*- coding:utf-8 -*-
from flask import render_template, request, flash, redirect, url_for, session, jsonify, Flask
from flask_login import current_user, login_required
from . import purchase_tracker_bp as purchase_tracker
from ..main import db
from .forms import *
from datetime import datetime
from pytz import timezone

from .models import PurchaseTrackerAccount


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
            purchase_tracker.creation_date = bangkok.localize(datetime.now())
            purchase_tracker.staff = current_user
            db.session.add(purchase_tracker)
            db.session.commit()
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return render_template('purchase_tracker/index.html')
    return render_template('purchase_tracker/create_account.html', form=form)


@purchase_tracker.route('/track')
def track():
    return render_template('purchase_tracker/tracking.html')


@purchase_tracker.route('/supplies')
def supplies():
    purchase_tracker_list = []
    purchase_tracker_query = PurchaseTrackerAccount.query.all()
    for purchase_tracker in purchase_tracker_query:
        record = {}
        record["id"] = purchase_tracker.id
        record["subject"] = purchase_tracker.subject
        record["number"] = purchase_tracker.number
        purchase_tracker_list.append(record)
    return render_template('purchase_tracker/procedure_supplies.html', purchase_tracker_list=purchase_tracker_list)


@purchase_tracker.route('/description')
def description():
    return render_template('purchase_tracker/description.html')


@purchase_tracker.route('/contact')
def contact():
    return render_template('purchase_tracker/contact_us.html')

@purchase_tracker.route('/items/<int:item_id>/records/update', methods=['GET', 'POST'])
def update_items(item_id):
    form = RegisterAccountForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        else:
            new_record = RegisterAccountForm()
            form.populate_obj(new_record)
            new_record.item_id = item_id
            new_record.staff = current_user
            new_record.creation_date = bangkok.localize(datetime.now())
            new_record.status_date = bangkok.localize(datetime.now())
            db.session.add(new_record)
            db.session.commit()
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return redirect(url_for('purchase_tracker.supplies'))
    return render_template('purchase_tracker/update_record.html', form=form)


@purchase_tracker.route('/update/<int:purchase_tracker_id>', methods=['GET', 'POST'])
@login_required
def update_status(purchase_tracker_id):
    purchase_tracker = PurchaseTrackerAccount.query.get(purchase_tracker_id)
    form = RegisterAccountForm(obj=purchase_tracker)
    if request.method == 'POST':
        pur_edit = PurchaseTrackerAccount()
        form.populate_obj(pur_edit)
        db.session.add(pur_edit)
        db.session.commit()
        flash(u'แก้ไขข้อมูลเรียบร้อย', 'success')
        return redirect(url_for('purchase_tracker.update'))
    return render_template('purchase_tracker/update_record.html', form=form, purchase_tracker=purchase_tracker)


@purchase_tracker.route('/choice')
def choice():
    return render_template('purchase_tracker/choice_fiscal.html')