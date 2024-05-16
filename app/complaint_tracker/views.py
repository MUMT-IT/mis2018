# -*- coding:utf-8 -*-
from datetime import datetime
import os
import arrow
import requests
from flask import render_template, flash, redirect, url_for, request, make_response, jsonify, current_app
from flask_login import current_user
from flask_login import login_required
from pytz import timezone
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
from app.auth.views import line_bot_api
from werkzeug.utils import secure_filename
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive
from app.complaint_tracker import complaint_tracker
from app.complaint_tracker.forms import ComplaintRecordForm, ComplaintActionRecordForm, ComplaintInvestigatorForm
from app.complaint_tracker.models import *
from app.main import mail
from ..main import csrf
from flask_mail import Message

from ..procurement.models import ProcurementDetail

gauth = GoogleAuth()
keyfile_dict = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
scopes = ['https://www.googleapis.com/auth/drive']
gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scopes)
drive = GoogleDrive(gauth)

localtz = timezone('Asia/Bangkok')

FOLDER_ID = '1832el0EAqQ6NVz2wB7Ade6wRe-PsHQsu'

json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scopes)
    return GoogleDrive(gauth)


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
        file = form.file_upload.data
        record.topic = topic
        if current_user.is_authenticated:
            record.complainant = current_user
        drive = initialize_gdrive()
        if file:
            file_name = secure_filename(file.filename)
            file.save(file_name)
            file_drive = drive.CreateFile({'title': file_name,
                                           'parents': [{'id': FOLDER_ID, "kind": "drive#fileLink"}]})
            file_drive.SetContentFile(file_name)
            file_drive.Upload()
            permission = file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
            record.url = file_drive['id']
            record.file_name = file_name
        if topic.code == 'room' and room:
            record.rooms.append(room)
            db.session.add(record)
        if topic.code == 'runied' and procurement:
            record.procurements.append(procurement)
            db.session.add(record)
        if (((form.is_contact.data and form.fl_name.data and (form.telephone.data or form.email.data)) or
            (not form.is_contact.data and (form.fl_name.data or form.telephone.data or form.email.data))) or
                (not form.is_contact.data and not form.fl_name.data and not form.telephone.data and not form.email.data)):
            db.session.add(record)
            db.session.commit()
            flash('รับเรื่องแจ้งเรียบร้อย', 'success')
            create_at = arrow.get(record.created_at, 'Asia/Bangkok').datetime
            msg = 'มีการแจ้งเรื่องเกี่ยวกับการ{} โดยเกี่ยวข้องในส่วนของ{} หัวข้อ{}' \
                  '\nเวลาแจ้ง : วันที่ {} เวลา {}' \
                  '\nซึ่งมีรายละเอียด ดังนี้ {}'.format(form.question_type.data, topic.category, topic.topic,
                                                        create_at.astimezone(localtz).strftime('%d/%m/%Y'),
                                                        create_at.astimezone(localtz).strftime('%H:%M'),
                                                        form.desc.data)
            if not current_app.debug:
                try:
                    line_bot_api.push_message(to=[a.admin.line_id for a in topic.admins], messages=TextSendMessage(text=msg))
                except LineBotApiError:
                    pass
            if current_user.is_authenticated:
                return redirect(url_for('comp_tracker.complainant_index'))
            else:
                return redirect(url_for('comp_tracker.closing_page'))
        else:
            flash('กรุณากรอกชื่อ-นามสกุล และเบอร์โทรศัพท์ หรืออีเมล', 'warning')
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('complaint_tracker/record_form.html', form=form, topic=topic, room=room,
                           procurement=procurement)


@complaint_tracker.route('issue/closing-page')
def closing_page():
    return render_template('complaint_tracker/closing.html')


@complaint_tracker.route('/issue/records/<int:record_id>', methods=['GET', 'POST'])
def edit_record_admin(record_id):
    record = ComplaintRecord.query.get(record_id)
    form = ComplaintRecordForm(obj=record)
    form.deadline.data = form.deadline.data.astimezone(localtz) if form.deadline.data else None
    file_url = None
    if record.url:
        file_upload = drive.CreateFile({'id': record.url})
        file_upload.FetchMetadata()
        file_url = file_upload.get('embedLink')
    if form.validate_on_submit():
        form.populate_obj(record)
        record.deadline = arrow.get(form.deadline.data, 'Asia/Bangkok').datetime if form.deadline.data else None
        db.session.add(record)
        db.session.commit()
        flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
    return render_template('complaint_tracker/admin_record_form.html', form=form, record=record,
                           file_url=file_url)


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
        if not admin:
            misc_topic = ComplaintTopic.query.filter_by(code='misc').first()
            admin = ComplaintAdmin.query.filter_by(admin=current_user, topic=misc_topic).first()
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
        flash('เพิ่มความคิดเห็น/ข้อเสนอแนะสำเร็จ', 'success')
        if record_id:
            resp = make_response(render_template('complaint_tracker/comment_template.html', action=action))
            resp.headers['HX-Trigger'] = 'closeModal'
        else:
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
                investigator = ComplaintInvestigator(inviter_id=current_user.id, admin_id=admin_id.id, record_id=record_id)
                db.session.add(investigator)
                investigators = ComplaintInvestigator.query.filter_by(admin_id=admin_id.id, record_id=record_id)
                record = ComplaintRecord.query.get(record_id)
                create_at = arrow.get(record.created_at, 'Asia/Bangkok').datetime
                complaint_link = url_for('comp_tracker.edit_record_admin', record_id=record_id, _external=True)
                msg = 'มีการแจ้งเรื่องเกี่ยวกับการ{} โดยเกี่ยวข้องในส่วนของ{} หัวข้อ{}' \
                      '\nเวลาแจ้ง : วันที่ {} เวลา {}' \
                      '\nซึ่งมีรายละเอียด ดังนี้ {}'.format(record.question_type, record.topic.category,
                                                            record.topic.topic,
                                                            create_at.astimezone(localtz).strftime('%d/%m/%Y'),
                                                            create_at.astimezone(localtz).strftime('%H:%M'),
                                                            record.desc)
                if not current_app.debug:
                    try:
                        line_bot_api.push_message(to=[i.admin.admin.line_id for i in investigators],
                                                  messages=TextSendMessage(text=msg))
                    except LineBotApiError:
                        pass
                title = f'''แจ้งปัญหาร้องเรียนในส่วนของ{record.topic.category}'''
                message = f'''มีการแจ้งปัญหาร้องเรียนมาในเรื่องของ{record.topic} โดยมีรายละเอียดปัญหาที่พบ ได้แก่ {record.desc}\n\n'''
                message += f'''กรุณาดำเนินการแก้ไขปัญหาตามที่ได้รับแจ้งจากผู้ใช้งาน\n\n\n'''
                message += f'''ลิงค์สำหรับจัดการข้อร้องเรียน : {complaint_link}'''
                send_mail([i.admin.admin.email + '@mahidol.ac.th' for i in investigators], title, message)
            db.session.commit()
            flash('เพิ่มรายชื่อผู้เกี่ยวข้องสำเร็จ', 'success')
            resp = make_response(render_template('complaint_tracker/invite_template.html',
                                                 investigator=investigator))
            resp.headers['HX-Trigger'] = 'closePopup'
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


@complaint_tracker.route('/complaint/user', methods=['GET'])
@login_required
def complainant_index():
    record_list = []
    records = ComplaintRecord.query.filter_by(complainant=current_user).all()
    for record in records:
        if record.url:
            file_upload = drive.CreateFile({'id': record.url})
            file_upload.FetchMetadata()
            record.url = file_upload.get('embedLink')
        else:
            record.url = None
        record_list.append(record)
    return render_template('complaint_tracker/complainant_index.html', record_list=record_list)


@complaint_tracker.route('/api/priority')
@login_required
def check_priority():
    priority_id = request.args.get('priorityID')
    priority = ComplaintPriority.query.get(priority_id)
    template = f'<span class="tag is-light">{priority.priority_detail}</span>'
    template += f'<span id="priority" class="tags"></span>'
    resp = make_response(template)
    return resp