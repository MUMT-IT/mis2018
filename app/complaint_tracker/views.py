# -*- coding:utf-8 -*-
from datetime import datetime
import arrow
from flask import render_template, flash, redirect, url_for, request, make_response, jsonify
from flask_login import current_user
from flask_login import login_required
from pytz import timezone

from app.complaint_tracker import complaint_tracker
from app.complaint_tracker.forms import ComplaintRecordForm, ComplaintActionRecordForm, ComplaintInvestigatorForm
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
        record.topic = topic
        record.complainant = current_user
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
    form = ComplaintRecordForm(obj=record)
    form.deadline.data = form.deadline.data.astimezone(localtz) if form.deadline.data else None
    if form.validate_on_submit():
        form.populate_obj(record)
        record.deadline = arrow.get(form.deadline.data, 'Asia/Bangkok').datetime if form.deadline.data else None
        db.session.add(record)
        db.session.commit()
        flash(u'แก้ไขข้อมูลคำร้องเรียบร้อย', 'success')
    return render_template('complaint_tracker/admin_record_form.html', form=form, record=record)


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
@complaint_tracker.route('/issue/comment/edit/<int:action_id>', methods=['GET', 'POST'])
def edit_comment(record_id=None, action_id=None):
    if record_id:
        record = ComplaintRecord.query.get(record_id)
        admin = ComplaintAdmin.query.filter_by(admin=current_user, topic=record.topic).first()
        form = ComplaintActionRecordForm()
    elif action_id:
        action = ComplaintActionRecord.query.get(action_id)
        form = ComplaintActionRecordForm(obj=action)
    if form.validate_on_submit():
        if record_id:
            action = ComplaintActionRecord()
        form.populate_obj(action)
        if record_id:
            action.record_id = record_id
            action.reviewer_id = admin.id
        action.comment_datetime = arrow.now('Asia/Bangkok').datetime
        db.session.add(action)
        db.session.commit()
        flash('Comment Success!', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('complaint_tracker/modal/comment_record_modal.html', record_id=record_id,
                           action_id=action_id, form=form)


@complaint_tracker.route('/issue/comment/delete/<int:action_id>', methods=['GET', 'DELETE'])
def delete_comment(action_id):
    if request.method == 'DELETE':
        action = ComplaintActionRecord.query.get(action_id)
        db.session.delete(action)
        db.session.commit()
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@complaint_tracker.route('/issue/invite/add/<int:record_id>', methods=['GET', 'POST'])
@complaint_tracker.route('/issue/invite/<int:investigator_id>', methods=['GET', 'DELETE'])
def add_invite(record_id=None, investigator_id=None):
    form = ComplaintInvestigatorForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            for admin_id in form.invites.data:
                investigator = ComplaintInvestigator(admin_id=admin_id.id, record_id=record_id)
                db.session.add(investigator)
            db.session.commit()
            resp = make_response()
            resp.headers['HX-Refresh'] = 'true'
            return resp
    elif request.method == 'DELETE':
        investigator = ComplaintInvestigator.query.get(investigator_id)
        db.session.delete(investigator)
        db.session.commit()
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('complaint_tracker/modal/invite_record_modal.html', record_id=record_id,
                           form=form)