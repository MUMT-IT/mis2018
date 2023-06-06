# -*- coding:utf-8 -*-
from datetime import datetime

from flask import render_template, flash, redirect, url_for
from flask_login import current_user
from flask_login import login_required
from pytz import timezone

from app.complaint_tracker import complaint_tracker
from app.complaint_tracker.forms import ComplaintRecordForm, ComplaitActionRecordForm
from app.complaint_tracker.models import *

localtz = timezone('Asia/Bangkok')


@complaint_tracker.route('/')
def index():
    categories = ComplaintCategory.query.all()
    return render_template('complaint_tracker/index.html', categories=categories)


@complaint_tracker.route('/issue/<int:topic_id>', methods=['GET', 'POST'])
def new_record(topic_id):
    topic = ComplaintTopic.query.get(topic_id)
    form = ComplaintRecordForm()
    if form.validate_on_submit():
        record = ComplaintRecord()
        form.populate_obj(record)
        record.topic = topic
        db.session.add(record)
        db.session.commit()
        flash(u'ส่งคำร้องเรียบร้อย', 'success')
        return redirect(url_for('comp_tracker.index'))
    return render_template('complaint_tracker/record_form.html', form=form, topic=topic)


@complaint_tracker.route('/issue/records/<int:record_id>', methods=['GET', 'POST'])
def edit_record_admin(record_id):
    record = ComplaintRecord.query.get(record_id)
    form = ComplaintRecordForm(obj=record)
    if form.validate_on_submit():
        form.populate_obj(record)
        for action in record.actions:
            if action.deadline:
                action.deadline = localtz.localize(action.deadline)
        db.session.add(record)
        db.session.commit()
        flash(u'แก้ไขข้อมูลคำร้องเรียบร้อย', 'success')
    return render_template('complaint_tracker/admin_record_form.html', form=form, record=record)


@complaint_tracker.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_index():
    admin_list = ComplaintAdmin.query.filter_by(admin=current_user) \
        .filter_by(is_supervisor=False)
    return render_template('complaint_tracker/admin_index.html', admin_list=admin_list)
