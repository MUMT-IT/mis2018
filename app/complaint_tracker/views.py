# -*- coding:utf-8 -*-
from datetime import datetime
import arrow
from flask import render_template, flash, redirect, url_for, request, make_response
from flask_login import current_user
from flask_login import login_required
from pytz import timezone

from app.complaint_tracker import complaint_tracker
from app.complaint_tracker.forms import ComplaintRecordForm, ComplaintActionRecordForm
from app.complaint_tracker.models import *
from app.main import mail
from ..main import csrf
from flask_mail import Message

from ..procurement.models import ProcurementDetail

localtz = timezone('Asia/Bangkok')


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


@complaint_tracker.route('/')
def index():
    categories = ComplaintCategory.query.all()
    return render_template('complaint_tracker/index.html', categories=categories)


@complaint_tracker.route('/issue/<int:topic_id>', methods=['GET', 'POST'])
def new_record(topic_id, room=None, procurement=None):
    topic = ComplaintTopic.query.get(topic_id)
    form = ComplaintRecordForm()
    room_number = request.args.get('number')
    location = request.args.get('location')
    procurement_no = request.args.get('procurement_no')
    if room_number and location:
        room = RoomResource.query.filter_by(number=room_number, location=location).first()
    if procurement_no:
        procurement = ProcurementDetail.query.filter_by(procurement_no=procurement_no).first()
    if form.validate_on_submit():
        record = ComplaintRecord()
        form.populate_obj(record)
        if topic.code == 'room' and room:
            record.rooms.append(room)
        if topic.code == 'runied' and procurement:
            record.procurements.append(procurement)
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
    return render_template('complaint_tracker/record_form.html', form=form, topic=topic, room=room,
                           procurement=procurement)


@complaint_tracker.route('/issue/records/<int:record_id>', methods=['GET', 'POST'])
def edit_record_admin(record_id):
    record = ComplaintRecord.query.get(record_id)
    action = ComplaintActionRecord.query.filter_by(record_id=record_id).first()
    forward = request.args.get('forward', 'false')
    form = ComplaintRecordForm(obj=record)
    deadline = form.deadline.data.astimezone(localtz) if form.deadline.data else None
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
            record.deadline = arrow.get(form.deadline.data, 'Asia/Bangkok').datetime if form.deadline.data else None
            admin = ComplaintAdmin.query.filter_by(admin=current_user, topic=record.topic).first()
            for action in record.actions:
                action.reviewer_id = admin.id
            db.session.add(record)
            db.session.commit()
            flash(u'แก้ไขข้อมูลคำร้องเรียบร้อย', 'success')
    return render_template('complaint_tracker/admin_record_form.html', form=form, record=record,
                           forward=forward, action=action, deadline=deadline)


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


@complaint_tracker.route('/scan-qrcode/complaint/<code>')
@csrf.exempt
def scan_qr_code_complaint(code):
    topic = ComplaintTopic.query.filter_by(code=code).first()
    return render_template('complaint_tracker/qr_code_scan_to_complaint.html', topic=topic.id)


@complaint_tracker.route('/issue/comment/add/<int:record_id>', methods=['GET', 'POST'])
def add_comment_record(record_id):
    form = ComplaintActionRecordForm()
    if form.validate_on_submit():
        action = ComplaintActionRecord()
        form.populate_obj(action)
        action.record_id = record_id
        action.reviewer_id = current_user.id
        db.session.add(action)
        db.session.commit()
        flash('เพิ่มความคิดเห็นสำเร็จ!', 'success')
        return redirect(url_for('comp_tracker.edit_record_admin', record_id=record_id))
    return render_template('complaint_tracker/add_comment_record.html', record_id=record_id, form=form)