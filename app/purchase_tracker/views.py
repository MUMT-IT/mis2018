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
    return render_template('purchase_tracker/tracking.html')

@purchase_tracker.route('/supplies')
def supplies():
    return render_template('purchase_tracker/procedure_supplies.html')