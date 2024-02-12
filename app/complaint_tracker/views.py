# -*- coding:utf-8 -*-
from datetime import datetime

from flask import render_template, flash, redirect, url_for, request
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
    if topic.code == 'general':
        form = ComplaintRecordForm()
    else:
        form = ComplaintRecordForm()
    if form.validate_on_submit():
        record = ComplaintRecord()
        form.populate_obj(record)
        if topic.code == 'room':
            room_number = request.args.get('number')
            location = request.args.get('location')
            room = RoomResource.query.filter_by(number=room_number, location=location).first()
            record.rooms.append(room)
        if topic.code == 'general':
            record.subtopic = form.subtopic.data
        record.topic = topic
        db.session.add(record)
        db.session.commit()
        flash(u'ส่งคำร้องเรียบร้อย', 'success')
        return redirect(url_for('comp_tracker.index'))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('complaint_tracker/record_form.html', form=form, topic=topic)


@complaint_tracker.route('/issue/records/<int:record_id>', methods=['GET', 'POST'])
def edit_record_admin(record_id):
    record = ComplaintRecord.query.get(record_id)
    forward = request.args.get('forward', 'false')
    form = ComplaintRecordForm(obj=record)
    if form.validate_on_submit():
        if forward == 'true':
            new_record = ComplaintRecord()
            del form.actions
            form.populate_obj(new_record)
            new_record.origin_id = record.id
            db.session.add(new_record)
            db.session.commit()
            flash('Forwarded successfully', 'success')
            return redirect(url_for('comp_tracker.edit_record_admin', record_id=record.id))
        else:
            form.populate_obj(record)
            for action in record.actions:
                if action.deadline:
                    action.deadline = localtz.localize(action.deadline)
            db.session.add(record)
            db.session.commit()
            flash(u'แก้ไขข้อมูลคำร้องเรียบร้อย', 'success')
    return render_template('complaint_tracker/admin_record_form.html', form=form, record=record, forward=forward)


@complaint_tracker.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_index():
    admin_list = ComplaintAdmin.query.filter_by(admin=current_user)
    return render_template('complaint_tracker/admin_index.html', admin_list=admin_list)


@complaint_tracker.route('/record/view/<int:record_id>')
def view_record_admin(record_id):
    record = ComplaintRecord.query.get(record_id)
    return render_template('complaint_tracker/view_record_admin.html', record=record)


@complaint_tracker.route('/topics/<code>')
def scan_qr_code_room(code):
    topic = ComplaintTopic.query.filter_by(code=code).first()
    return redirect(url_for('comp_tracker.new_record', topic_id=topic.id, **request.args))