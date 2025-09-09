# -*- coding:utf-8 -*-
import uuid
from collections import defaultdict
from datetime import datetime
from io import BytesIO
import arrow
import gviz_api
import requests
from bahttext import bahttext
from flask import render_template, flash, redirect, url_for, request, make_response, jsonify, current_app, send_file
from flask_login import current_user
from flask_login import login_required
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from sqlalchemy import or_
from app.auth.views import line_bot_api
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive
from app.complaint_tracker import complaint_tracker
from app.complaint_tracker.forms import (create_record_form, ComplaintActionRecordForm, ComplaintInvestigatorForm,
                                         ComplaintPerformanceReportForm, ComplaintCoordinatorForm,
                                         ComplaintRepairApprovalForm, ComplaintCommitteeGroupForm)
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, PageBreak, TableStyle, Table, Spacer, KeepTogether
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.complaint_tracker.models import *
from app.main import mail
from ..main import csrf
from flask_mail import Message

from ..models import Org
from ..procurement.models import ProcurementDetail
from ..roles import admin_permission

sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
pdfmetrics.registerFont(sarabun_font)
pdfmetrics.registerFont(TTFont('SarabunBold', 'app/static/fonts/THSarabunNewBold.ttf'))
pdfmetrics.registerFont(TTFont('DejaVuSans', 'app/static/fonts/DejaVuSans.ttf'))
style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))
style_sheet.add(ParagraphStyle(name='ThaiStyleBold', fontName='SarabunBold'))
style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', alignment=TA_CENTER))

localtz = timezone('Asia/Bangkok')

FOLDER_ID = '1832el0EAqQ6NVz2wB7Ade6wRe-PsHQsu'

json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_url(file_url):
    url = s3.generate_presigned_url('get_object',
                                    Params={'Bucket': S3_BUCKET_NAME, 'Key': file_url},
                                    ExpiresIn=3600)
    return url


def get_fiscal_date(date):
    if date.month >= 10:
        start_fiscal_date = datetime(date.year, 10, 1)
        end_fiscal_date = datetime(date.year + 1, 9, 30, 23, 59, 59, 0)
    else:
        start_fiscal_date = datetime(date.year - 1, 10, 1)
        end_fiscal_date = datetime(date.year, 9, 30, 23, 59, 59, 0)
    return start_fiscal_date, end_fiscal_date


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


def initialize_gdrive():
    try:
        gauth = GoogleAuth()
        scopes = ['https://www.googleapis.com/auth/drive']
        gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scopes)
        return GoogleDrive(gauth)
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการเชื่อมต่อ Google Drive: {e}")
        return None


@complaint_tracker.route('/api/committee/position')
def get_position():
    staff_id = request.args.get('staff_id')
    staff = StaffAccount.query.filter_by(id=staff_id).first()
    position = staff.personal_info.position if staff else ''
    return jsonify({"position": position})


@complaint_tracker.route('/')
def index():
    categories = ComplaintCategory.query.all()
    return render_template('complaint_tracker/index.html', categories=categories)


@complaint_tracker.route('/issue/<int:topic_id>', methods=['GET', 'POST'])
def new_record(topic_id, room=None, procurement=None):
    topic = ComplaintTopic.query.get(topic_id)
    ComplaintRecordForm = create_record_form(record_id=None, topic_id=topic_id)
    form = ComplaintRecordForm()
    room_number = request.args.get('number')
    location = request.args.get('location')
    procurement_no = request.args.get('procurement_no')
    pro_number = request.args.get('pro_number')
    is_admin = False
    if current_user.is_authenticated:
        is_admin = True if ComplaintAdmin.query.filter_by(admin=current_user, topic_id=topic_id).first() else False
    if room_number and location:
        room = RoomResource.query.filter_by(number=room_number, location=location).first()
    elif procurement_no or pro_number:
        procurement = ProcurementDetail.query.filter_by(
            procurement_no=procurement_no if procurement_no else pro_number).first()
    if form.validate_on_submit():
        record = ComplaintRecord()
        form.populate_obj(record)
        file = form.file_upload.data
        record.topic = topic
        record.created_at = arrow.now('Asia/Bangkok').datetime
        if current_user.is_authenticated:
            record.complainant = current_user
        if file and allowed_file(file.filename):
            mime_type = file.mimetype
            file_name = '{}.{}'.format(uuid.uuid4().hex, file.filename.split('.')[-1])
            file_data = file.stream.read()
            response = s3.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=file_name,
                Body=file_data,
                ContentType=mime_type
            )
            record.url = file_name
        if topic.code == 'room' and room:
            record.room = room
        elif topic.code == 'runied' and procurement:
            record.procurements.append(procurement)
        if (((form.is_contact.data and form.fl_name.data and (form.telephone.data or form.email.data)) or
             (not form.is_contact.data and (form.fl_name.data or form.telephone.data or form.email.data))) or
                (
                        not form.is_contact.data and not form.fl_name.data and not form.telephone.data and not form.email.data)):
            db.session.add(record)
            db.session.commit()
            flash('รับเรื่องแจ้งเรียบร้อย', 'success')
            complaint_link = url_for("comp_tracker.edit_record_admin", record_id=record.id, _external=True,
                                     _scheme='https')
            msg = ('มีการแจ้งเรื่องในส่วนของ{} หัวข้อ{}' \
                   '\nเวลาแจ้ง : วันที่ {} เวลา {}' \
                   '\nซึ่งมีรายละเอียด ดังนี้ {}' \
                   '\nคลิกที่ Link เพื่อดำเนินการ {}'.format(topic.category, topic.topic,
                                                             record.created_at.astimezone(localtz).strftime('%d/%m/%Y'),
                                                             record.created_at.astimezone(localtz).strftime('%H:%M'),
                                                             form.desc.data,
                                                             complaint_link)
                   )
            if not current_app.debug:
                for a in topic.admins:
                    if a.is_supervisor == False:
                        try:
                            line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                        except LineBotApiError:
                            pass
            if current_user.is_authenticated:
                return redirect(url_for('comp_tracker.complainant_index'))
            else:
                return redirect(url_for('comp_tracker.closing_page'))
        else:
            flash('กรุณากรอกชื่อ-นามสกุล และเบอร์โทรศัพท์ หรืออีเมล', 'danger')
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('complaint_tracker/record_form.html', form=form, topic=topic, room=room,
                           is_admin=is_admin, procurement=procurement)


@complaint_tracker.route('issue/closing-page')
def closing_page():
    return render_template('complaint_tracker/closing.html')


@complaint_tracker.route('/issue/records/<int:record_id>', methods=['GET', 'POST', 'PATCH'])
@login_required
def edit_record_admin(record_id):
    tab = request.args.get('tab')
    record = ComplaintRecord.query.get(record_id)
    if record:
        admins = True if ComplaintAdmin.query.filter_by(admin=current_user, topic=record.topic).first() else False
        investigators = []
        coordinators = ComplaintCoordinator.query.filter_by(coordinator=current_user, record_id=record_id).first() \
            if ComplaintCoordinator.query.filter_by(coordinator=current_user, record_id=record_id).first() else None
        for i in record.investigators:
            if i.admin.admin == current_user:
                investigators.append(i)
        if record.repair_approvals:
            for repair_approval in record.repair_approvals:
                repair_approval_id = repair_approval.id
        else:
            repair_approval_id = None
        ComplaintRecordForm = create_record_form(record_id=record_id, topic_id=None)
        form = ComplaintRecordForm(obj=record)
        form.deadline.data = form.deadline.data.astimezone(localtz) if form.deadline.data else None
        if record.url and len(record.url) > 0:
            file_url = generate_url(record.url)
        else:
            file_url = None
        if request.method == 'PATCH':
            if record.closed_at is None:
                record.closed_at = arrow.now('Asia/Bangkok').datetime
                flash('ปิดรายการเรียบร้อย', 'success')
            else:
                record.closed_at = None
                flash('เปิดรายการอีกครั้งเรียบร้อย', 'success')
            db.session.add(record)
            db.session.commit()
            resp = make_response()
            resp.headers['HX-Refresh'] = 'true'
            return resp
        if form.validate_on_submit():
            old_priority = record.priority.priority if record.priority else None
            form.populate_obj(record)
            record.deadline = arrow.get(form.deadline.data, 'Asia/Bangkok').datetime if form.deadline.data else None
            db.session.add(record)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            new_priority = record.priority.priority if record.priority else None
            if old_priority != 2 and new_priority == 2:
                if not current_app.debug:
                    complaint_link = url_for("comp_tracker.edit_record_admin", record_id=record_id, _external=True
                                             , _scheme='https')
                    create_at = arrow.get(record.created_at, 'Asia/Bangkok').datetime
                    msg = ('มีการแจ้งเรื่องในส่วนของ{} หัวข้อ{}' \
                           '\nเวลาแจ้ง : วันที่ {} เวลา {}' \
                           '\nซึ่งมีรายละเอียด ดังนี้ {}' \
                           '\nคลิกที่ Link เพื่อดำเนินการ {}'.format(record.topic.category, record.topic,
                                                                     create_at.astimezone(localtz).strftime('%d/%m/%Y'),
                                                                     create_at.astimezone(localtz).strftime('%H:%M'),
                                                                     record.desc, complaint_link)
                           )
                    for a in record.topic.admins:
                        if a.is_supervisor:
                            try:
                                line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                            except LineBotApiError:
                                pass
        return render_template('complaint_tracker/admin_record_form.html', form=form, record=record, tab=tab,
                               file_url=file_url, admins=admins, investigators=investigators, coordinators=coordinators,
                               repair_approval_id=repair_approval_id)
    else:
        return render_template('complaint_tracker/record_cancelled_page.html', record_id=record_id, tab=tab)


@complaint_tracker.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_index():
    tab = request.args.get('tab')
    admins = ComplaintAdmin.query.filter_by(admin=current_user)
    coordinators = ComplaintCoordinator.query.filter_by(coordinator=current_user)
    records = []

    for admin in admins:
        if admin.investigators:
            for investigator in admin.investigators:
                if tab == 'new' and investigator.record.status is None:
                    records.append(investigator.record)
                else:
                    rec = investigator.get_record_by_status(tab)
                    if rec:
                        records.append(rec)

        if admin.topic.records:
            for record in admin.topic.records:
                if tab == 'new' and record.status is None:
                    records.append(record)
                else:
                    rec = record.get_record_by_status(tab)
                    if rec:
                        records.append(rec)
    for c in coordinators:
        if tab == 'new' and c.record.status is None:
            records.append(c.record)
        else:
            rec = c.get_record_by_status(tab)
            if rec:
                records.append(rec)

    def all_page_setup(canvas, doc):
        canvas.saveState()
        canvas.restoreState()

    if request.method == "POST":
        doc = SimpleDocTemplate('app/complaint.pdf',
                                pagesize=A4,
                                rightMargin=30,
                                leftMargin=30,
                                topMargin=20,
                                bottomMargin=30
                                )
        data = []

        header_style = ParagraphStyle(
            name="Header",
            parent=style_sheet['ThaiStyleBold'],
            fontSize=20,
            alignment=1,
            spaceAfter=12
        )

        label_style = ParagraphStyle(
            name="Label",
            parent=style_sheet['ThaiStyleBold'],
            fontSize=16
        )

        value_style = ParagraphStyle(
            name="Value",
            parent=style_sheet['ThaiStyle'],
            fontSize=16
        )

        for item_id in request.form.getlist('selected_items'):
            item = ComplaintRecord.query.get(int(item_id))
            name = item.complainant.fullname if item.complainant else item.fl_name if item.fl_name else '-'
            if item.rooms or item.room:
                title = 'ห้อง :'
                if item.room:
                    if item.room.desc:
                        room = f'''{item.room.number} {item.room.location} ({item.room.desc})'''
                    else:
                        room = f'''{item.room.number} {item.room.location}'''
                else:
                    for r in item.rooms:
                        if r.desc:
                            room = f'''{r.number} {r.location} ({r.desc})'''
                        else:
                            room = f'''{r.number} {r.location}'''
                col_Widths = [55, 445]
            elif item.procurement_location:
                title = 'สถานที่ตั้งครุภัณฑ์ปัจจุบัน :'
                if item.procurement_location.desc:
                    room = f'''{item.procurement_location.number} {item.procurement_location.location} ({item.procurement_location.desc})'''
                else:
                    room = f'''{item.procurement_location.number} {item.procurement_location.location}'''
                col_Widths = [140, 360]
            else:
                room = '-'
                col_Widths = [55, 445]
            header = [
                [Paragraph('รายละเอียดหมวดหมู่', style=label_style)],
                [Paragraph("หมวด :", style=label_style), Paragraph(item.topic.category.category, style=value_style)],
                [Paragraph("หัวข้อ :", style=label_style), Paragraph(item.topic.topic, style=value_style)],
                [Paragraph(title, style=label_style), Paragraph(room, style=value_style)],
            ]

            header_table = Table(header, colWidths=col_Widths)
            header_table.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('BOX', (0, 0), (-1, -1), 1.2, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, -1), (-1, -1), 15)
            ]))

            data.append(KeepTogether(Paragraph("ใบแจ้งปัญหา / COMPLAINT FORM", style=header_style)))
            data.append(KeepTogether(Spacer(1, 8)))
            data.append(KeepTogether(header_table))

            if item.procurements:
                for p in item.procurements:
                    for r in p.records:
                        if r.location:
                            if r.location.desc:
                                location = f'''{r.location.number} {r.location.location} ({r.location.desc})'''
                            else:
                                location = f'''{r.location.number} {r.location.location}'''
                        else:
                            location = '-'
                    procurement = [
                        [Paragraph('รายละเอียดครุภัณฑ์', style=label_style)],
                        [Paragraph("ชื่อครุภัณฑ์ :", style=label_style), Paragraph(p.name, style=value_style)],
                        [Paragraph("หมวดหมู่/ประเภท :", style=label_style),
                         Paragraph(p.category.category, style=value_style)],
                        [Paragraph("สถานที่ติดตั้ง :", style=label_style), Paragraph(location, style=value_style)],
                        [Paragraph("เลขครุภัณฑ์ :", style=label_style), Paragraph(p.procurement_no, style=value_style)],
                        [Paragraph("ภาควิชา/หน่วยงาน :", style=label_style), Paragraph(p.org.name, style=value_style)],
                    ]

                    procurement_table = Table(procurement, colWidths=[115, 385])
                    procurement_table.setStyle(TableStyle([
                        ('BOX', (0, 0), (-1, -1), 1.2, colors.black),
                        ('SPAN', (0, 0), (1, 0)),
                        ('LEFTPADDING', (0, 0), (-1, -1), 10),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, -1), (-1, -1), 15)
                    ]))

                    data.append(KeepTogether(procurement_table))

            created_at = arrow.get(item.created_at.astimezone(localtz)).format(fmt='วันที่ DD MMMM YYYY เวลา HH:mm',
                                                                               locale='th-th')

            complainant = [
                [Paragraph('รายละเอียดผู้แจ้ง', style=label_style)],
                [Paragraph("ผู้แจ้ง :", style=label_style), Paragraph(name, style=value_style)],
                [Paragraph("วันที่แจ้ง :", style=label_style), Paragraph(created_at, style=value_style)]
            ]

            complainant_table = Table(complainant, colWidths=[65, 435])
            complainant_table.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('BOX', (0, 0), (-1, -1), 1.2, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, -1), (-1, -1), 15)
            ]))

            desc_title = Paragraph("รายละเอียดปัญหา", style=label_style)
            desc_text = Paragraph(item.desc or "-", style=value_style)

            desc_table = Table([[desc_title], [desc_text]], colWidths=[500])
            desc_table.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 1.2, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ]))

            status = [
                [Paragraph('สถานะ', style=label_style)],
                [Paragraph('☐ รับเรื่อง/รอดำเนินการ', style=value_style)],
                [Paragraph('☐ อยู่ระหว่างดำเนินการ', style=value_style)],
                [Paragraph('☐ ดำเนินการเสร็จสิ้น', style=value_style)]
            ]

            status_table = Table(status, colWidths=[500])
            status_table.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 1.2, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, -1), (-1, -1), 15)
            ]))

            report = [
                [Paragraph('รายงานผลการดำเนินงาน', style=label_style)],
                [Paragraph("." * 185, style=value_style) for _ in range(3)]
            ]
            report_table = Table([[r] for r in report], colWidths=[500])
            report_table.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 1.2, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, -1), (-1, -1), 15)
            ]))

            data.append(KeepTogether(complainant_table))
            data.append(KeepTogether(desc_table))
            data.append(KeepTogether(status_table))
            data.append(KeepTogether(report_table))
            data.append(PageBreak())
        doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
        return send_file('complaint.pdf')
    return render_template('complaint_tracker/admin_index.html', records=records, tab=tab)


@complaint_tracker.route('/topics/<code>')
def scan_qr_code_room(code):
    topic = ComplaintTopic.query.filter_by(code=code).first()
    return redirect(url_for('comp_tracker.new_record', topic_id=topic.id, **request.args))


@complaint_tracker.route('/scan-qrcode/complaint/<code>', methods=['GET', 'POST'])
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
        if record_id:
            flash('เพิ่มความคิดเห็น/ข้อเสนอแนะสำเร็จ', 'success')
            resp = make_response(render_template('complaint_tracker/comment_template.html', action=action))
            resp.headers['HX-Trigger'] = 'closeModal'
        else:
            flash('แก้ไขความคิดเห็น/ข้อเสนอแนะสำเร็จ', 'success')
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
        flash('ลบความคิดเห็น/ข้อเสนอแนะสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@complaint_tracker.route('/issue/invited/add/<int:record_id>', methods=['GET', 'POST'])
@complaint_tracker.route('/issue/invited/delete/<int:investigator_id>', methods=['GET', 'DELETE'])
@complaint_tracker.route('/issue/coordinators/delete/<int:coordinator_id>', methods=['GET', 'DELETE'])
def edit_invited(record_id=None, investigator_id=None, coordinator_id=None):
    form = ComplaintInvestigatorForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            invites = []
            coordinators = []
            for admin_id in form.invites.data:
                admin = ComplaintAdmin.query.filter_by(staff_account=admin_id.id).first()
                if admin:
                    investigator = ComplaintInvestigator(inviter_id=current_user.id, admin_id=admin.id,
                                                         record_id=record_id)
                    db.session.add(investigator)
                    invites.append(investigator)
                else:
                    coordinator = ComplaintCoordinator(coordinator_id=admin_id.id, record_id=record_id,
                                                       recorder_id=current_user.id)
                    db.session.add(coordinator)
                    coordinators.append(coordinator)
            db.session.commit()
            record = ComplaintRecord.query.get(record_id)
            create_at = arrow.get(record.created_at, 'Asia/Bangkok').datetime
            complaint_link = url_for('comp_tracker.edit_record_admin', record_id=record_id, _external=True
                                     , _scheme='https')
            msg = ('มีการแจ้งเรื่องในส่วนของ{} หัวข้อ{}' \
                   '\nเวลาแจ้ง : วันที่ {} เวลา {}' \
                   '\nซึ่งมีรายละเอียด ดังนี้ {}'
                   '\nคลิกที่ Link เพื่อดำเนินการ {}'.format(record.topic.category, record.topic.topic,
                                                             create_at.astimezone(localtz).strftime('%d/%m/%Y'),
                                                             create_at.astimezone(localtz).strftime('%H:%M'),
                                                             record.desc, complaint_link))
            title = f'''แจ้งปัญหาในส่วนของ{record.topic.category}'''
            message = f'''มีการแจ้งปัญหามาในเรื่องของ{record.topic} โดยมีรายละเอียดปัญหาที่พบ ได้แก่ {record.desc}\n\n'''
            message += f'''กรุณาดำเนินการแก้ไขปัญหาตามที่ได้รับแจ้งจากผู้ใช้งาน\n\n\n'''
            message += f'''ลิงค์สำหรับดำเนินการแก้ไขปัญหา : {complaint_link}'''
            if invites:
                invited = [invite.admin.admin.email + '@mahidol.ac.th' for invite in invites]
                send_mail(invited, title, message)
            if coordinators:
                cor = [coordinator.coordinator.email + '@mahidol.ac.th' for coordinator in coordinators]
                send_mail(cor, title, message)
            if not current_app.debug:
                for invite in invites:
                    try:
                        line_bot_api.push_message(to=invite.admin.admin.line_id, messages=TextSendMessage(text=msg))
                    except LineBotApiError:
                        pass
            flash('เพิ่มรายชื่อผู้เกี่ยวข้องสำเร็จ', 'success')
            resp = make_response(render_template('complaint_tracker/invite_template.html',
                                                 invites=invites, coordinators=coordinators))
            resp.headers['HX-Trigger'] = 'closePopup'
            return resp
    elif request.method == 'DELETE':
        if investigator_id:
            investigator = ComplaintInvestigator.query.get(investigator_id)
            db.session.delete(investigator)
            title = f'''แจ้งยกเลิกการเป็นผู้เกี่ยวข้องการดำเนินการแก้ไขปัญหา'''
            message = f'''ท่านได้ถูกยกเลิกในการเป็นผู้เกี่ยวข้องการดำเนินการแก้ไขปัญหาในหัวข้อ{investigator.record.topic} โดยมีรายละเอียดปัญหา ดังนี้ {investigator.record.desc}\n\n'''
            send_mail([investigator.admin.admin.email + '@mahidol.ac.th'], title, message)
        else:
            coordinator = ComplaintCoordinator.query.get(coordinator_id)
            db.session.delete(coordinator)
            title = f'''แจ้งยกเลิกการเป็นผู้เกี่ยวข้องการดำเนินการแก้ไขปัญหา'''
            message = f'''ท่านได้ถูกยกเลิกในการเป็นผู้เกี่ยวข้องการดำเนินการแก้ไขปัญหาในหัวข้อ{coordinator.record.topic} โดยมีรายละเอียดปัญหา ดังนี้ {coordinator.record.desc}\n\n'''
            send_mail([coordinator.coordinator.email + '@mahidol.ac.th'], title, message)
        db.session.commit()
        flash('ลบรายชื่อผู้เกี่ยวข้องสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('complaint_tracker/modal/invite_record_modal.html', record_id=record_id,
                           form=form)


@complaint_tracker.route('/complaint/user', methods=['GET'])
@login_required
def complainant_index():
    records = ComplaintRecord.query.filter_by(complainant=current_user)
    is_admin = True if ComplaintAdmin.query.filter_by(admin=current_user).first() else False
    return render_template('complaint_tracker/complainant_index.html', records=records, is_admin=is_admin)


@complaint_tracker.route('/api/priority')
@login_required
def check_priority():
    priority_id = request.args.get('priorityID')
    priority = ComplaintPriority.query.get(priority_id)
    template = f'<span class="tag is-light">{priority.priority_detail}</span>'
    template += f'<span id="priority" class="tags"></span>'
    resp = make_response(template)
    return resp


@complaint_tracker.route('/issue/report/add/<int:record_id>', methods=['GET', 'POST'])
@complaint_tracker.route('/issue/report/edit/<int:report_id>', methods=['GET', 'POST'])
def create_report(record_id=None, report_id=None):
    if record_id:
        record = ComplaintRecord.query.get(record_id)
        admin = ComplaintAdmin.query.filter_by(admin=current_user, topic=record.topic).first()
        if not admin:
            misc_topic = ComplaintTopic.query.filter_by(code='misc').first()
            admin = ComplaintAdmin.query.filter_by(admin=current_user, topic=misc_topic).first()
        form = ComplaintPerformanceReportForm()
    elif report_id:
        report = ComplaintPerformanceReport.query.get(report_id)
        form = ComplaintPerformanceReportForm(obj=report)
    if form.validate_on_submit():
        if record_id:
            report = ComplaintPerformanceReport()
        form.populate_obj(report)
        if record_id:
            report.record_id = record_id
            report.reporter_id = admin.id
        report.report_datetime = arrow.now('Asia/Bangkok').datetime
        db.session.add(report)
        db.session.commit()
        if record_id:
            flash('เพิ่มรายงานผลการดำเนินงานสำเร็จ', 'success')
            resp = make_response(render_template('complaint_tracker/performance_report_template.html',
                                                 report=report))
            resp.headers['HX-Trigger'] = 'closeReport'
        else:
            flash('แก้ไขรายงานผลการดำเนินงานสำเร็จ', 'success')
            resp = make_response()
            resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('complaint_tracker/modal/performance_report_modal.html', record_id=record_id,
                           report_id=report_id, form=form)


@complaint_tracker.route('/issue/report/delete/<int:report_id>', methods=['GET', 'DELETE'])
def delete_report(report_id):
    if request.method == 'DELETE':
        report = ComplaintPerformanceReport.query.get(report_id)
        db.session.delete(report)
        db.session.commit()
        flash('ลบรายงานผลการดำเนินงานสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@complaint_tracker.route('/issue/record/coordinator/complaint-acknowledgment/<int:coordinator_id>',
                         methods=['GET', 'POST'])
def acknowledge_complaint(coordinator_id):
    if request.method == 'POST':
        coordinator = ComplaintCoordinator.query.get(coordinator_id)
        coordinator.received_datetime = arrow.now('Asia/Bangkok').datetime
        db.session.add(coordinator)
        db.session.commit()
        flash('ยืนยันเรียบร้อย', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@complaint_tracker.route('/issue/record/coordinator/note/add/<int:coordinator_id>', methods=['GET', 'POST'])
@login_required
def edit_note(coordinator_id):
    coordinator = ComplaintCoordinator.query.get(coordinator_id)
    form = ComplaintCoordinatorForm(obj=coordinator)
    if request.method == 'GET':
        template = '''
            <tr>
                <td style="width: 100%;">
                    <label class="label">รายงานผลการดำเนินงาน</label>{}
                </td>
                <td>
                    <a class="button is-success is-outlined"
                        hx-post="{}" hx-include="closest tr">
                        <span class="icon"><i class="fas fa-save"></i></span>
                        <span class="has-text-success">บันทึก</span>
                    </a>
                </td>
            </tr>
            '''.format(form.note(class_="textarea"),
                       url_for('comp_tracker.edit_note', coordinator_id=coordinator.id)
                       )
    if request.method == 'POST':
        coordinator.note = request.form.get('note')
        db.session.add(coordinator)
        db.session.commit()
        flash('บันทึกรายงานผลการดำเนินงานสำเร็จ', 'success')
        template = '''
            <tr>
                <td style="width: 100%;">
                    <label class="label">รายงานผลการดำเนินงาน</label>
                    <p class="notification">{}</p>
                </td>
                <td>
                    <div class="field has-addons">
                        <div class="control">
                            <a class="button is-light is-outlined"
                               hx-get="{}">
                                <span class="icon">
                                   <i class="fas fa-pencil has-text-dark"></i>
                                </span>
                                <span class="has-text-dark">ร่าง</span>
                            </a>
                        </div>
                        <div class="control">
                            <a class="button is-light is-outlined"
                                style="width: 5em"
                                hx-patch="{}"
                                hx-confirm="ท่านต้องการส่งรายงานผลการดำเนินงานหรือไม่">
                                <span class="icon">
                                    <i class="fas fa-paper-plane has-text-info"></i>
                                </span>
                                <span class="has-text-info">ส่ง</span>
                            </a>
                        </div>
                    </div>
                </td>
            </tr>
            '''.format(coordinator.note, url_for('comp_tracker.edit_note', coordinator_id=coordinator.id),
                       url_for('comp_tracker.submit_note', coordinator_id=coordinator.id))
    resp = make_response(template)
    return resp


@complaint_tracker.route('/issue/record/coordinator/note/note-submission/<int:coordinator_id>',
                         methods=['GET', 'PATCH'])
@login_required
def submit_note(coordinator_id):
    coordinator = ComplaintCoordinator.query.get(coordinator_id)
    if request.method == 'PATCH':
        coordinator.submitted_datetime = arrow.now('Asia/Bangkok').datetime
        flash('ปิดรายงานผลการดำเนินงานเรียบร้อย', 'success')
        db.session.add(coordinator)
        db.session.commit()
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@complaint_tracker.route('/issue/complainant/email-sending/<int:record_id>', methods=['GET', 'POST'])
def send_email(record_id):
    record = ComplaintRecord.query.get(record_id)
    form = request.form
    if request.method == 'POST':
        title = f'''{form.get('title')}'''
        message = f'''{form.get('detail')}'''
        send_mail([record.email], title, message)
        flash('ส่งอีเมลเรียบร้อย', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('complaint_tracker/modal/send_email_modal.html', record_id=record_id)


@complaint_tracker.route('/issue/report/assignee/add/<int:record_id>/<int:assignee_id>',
                         methods=['GET', 'POST', 'DELETE'])
def edit_assignee(record_id, assignee_id):
    if request.method == 'POST':
        assignees = ComplaintAssignee(assignee_id=assignee_id, record_id=record_id,
                                      assignee_datetime=arrow.now('Asia/Bangkok').datetime)
        db.session.add(assignees)
        db.session.commit()
        flash('มอบหมายงานสำเร็จ', 'success')
        complaint_link = url_for('comp_tracker.edit_record_admin', record_id=record_id, _external=True, _scheme='https')
        msg = ('ท่านได้รับมอบหมายให้ดำเนินการแก้ไขปัญหา'
               '\nกรุณาคลิกที่ Link เพื่อดำเนินการ {}'.format(complaint_link))
        if not current_app.debug:
            try:
                line_bot_api.push_message(to=assignees.assignee.admin.line_id, messages=TextSendMessage(text=msg))
            except LineBotApiError:
                pass
    elif request.method == 'DELETE':
        assignee = ComplaintAssignee.query.filter_by(assignee_id=assignee_id, record_id=record_id).first()
        db.session.delete(assignee)
        db.session.commit()
        flash('ยกเลิกการมอบหมายงานสำเร็จ', 'success')
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@complaint_tracker.route('/issue/report/hendler/add/<int:record_id>', methods=['GET', 'POST'])
def add_handler(record_id):
    ComplaintHandler.query.filter_by(record_id=record_id).delete()
    for h_id in request.form.getlist('handlers'):
        handlers = ComplaintHandler(record_id=record_id, handler_id=h_id, handled_at=arrow.now('Asia/Bangkok').datetime)
        db.session.add(handlers)
        db.session.commit()
    flash('บันทึกผู้ดำเนินการเรียบร้อยแล้ว', 'success')
    record = ComplaintRecord.query.get(record_id)
    return render_template('complaint_tracker/handler_template.html', record=record)


@complaint_tracker.route('/complaint/user/view/<int:record_id>', methods=['GET'])
def view_record_complaint(record_id):
    record = ComplaintRecord.query.get(record_id)
    if record.url and len(record.url) > 0:
        file_url = generate_url(record.url)
    else:
        file_url = None
    return render_template('complaint_tracker/view_record_complaint.html', record=record, file_url=file_url)


@complaint_tracker.route('/complaint/report/view/<int:record_id>')
@login_required
def view_performance_report(record_id):
    record = ComplaintRecord.query.get(record_id)
    return render_template('complaint_tracker/modal/view_performance_report_modal.html', record=record)


@complaint_tracker.route('/complaint/user/delete/<int:record_id>', methods=['DELETE'])
def delete_complaint(record_id):
    if record_id:
        record = ComplaintRecord.query.get(record_id)
        db.session.delete(record)
        db.session.commit()
        flash('ลบรายการแจ้งปัญหาสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@complaint_tracker.route('/admin/complaint/index')
@admin_permission.require()
@login_required
def admin_record_complaint_index():
    menu = request.args.get('menu')
    topics = ComplaintTopic.query.all()
    grouped_topics = defaultdict(list)
    for topic in topics:
        if topic.code != 'misc':
            grouped_topics[topic.category].append(topic)
    return render_template('complaint_tracker/admin_record_complaint_index.html', menu=menu,
                           grouped_topics=grouped_topics)


@complaint_tracker.route('/api/records')
@login_required
def get_records():
    menu = request.args.get('menu')
    query = ComplaintRecord.query.filter(
        ComplaintRecord.topic.has(code=menu)) if menu != 'all' else ComplaintRecord.query
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ComplaintRecord.desc.contains(search))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': records_total,
                    'draw': request.args.get('draw', type=int),
                    })


@complaint_tracker.route('/admin/complaint/view/<int:record_id>')
def view_record_complaint_for_admin(record_id):
    menu = request.args.get('menu')
    record = ComplaintRecord.query.get(record_id)
    if record.url and len(record.url) > 0:
        file_url = generate_url(record.url)
    else:
        file_url = None
    return render_template('complaint_tracker/view_record_complaint_for_admin.html', file_url=file_url,
                           record=record, menu=menu)


@complaint_tracker.route('/add-procurement-number/complaint/<code>', methods=['GET', 'POST'])
def add_procurement_number(code):
    topic = ComplaintTopic.query.filter_by(code=code).first()
    if request.method == 'POST':
        pro_number = request.form.get('pro_number')
        return redirect(url_for('comp_tracker.new_record', topic_id=topic.id, pro_number=pro_number))
    return render_template('complaint_tracker/add_procurement_number.html', code=code, topic_id=topic.id)


@complaint_tracker.route('/admin/record-complaint-summary')
@login_required
def admin_record_complaint_summary():
    menu = request.args.get('menu')
    topics = ComplaintTopic.query.filter(ComplaintTopic.code != 'misc')
    code = []
    topic = []
    for t in topics:
        if menu == t.code:
            topic.append(t.topic)
            code.append(t.code)
    return render_template('complaint_tracker/admin_record_complaint_summary.html', menu=menu, code=' '.join(code),
                           topic=' '.join(topic), topics=topics)


@complaint_tracker.route('/admin/repair-approval/add/<int:record_id>', methods=['GET', 'POST'])
@complaint_tracker.route('/admin/repair-approval/edit/<int:record_id>/<int:repair_approval_id>', methods=['GET', 'POST'])
def repair_approval(record_id, repair_approval_id=None):
    record = ComplaintRecord.query.get(record_id)
    if repair_approval_id:
        rep_approval = ComplaintRepairApproval.query.get(repair_approval_id)
        form = ComplaintRepairApprovalForm(obj=rep_approval)
    else:
        form = ComplaintRepairApprovalForm()
    org = Org.query.filter_by(name=current_user.personal_info.org.name).first()
    staff = StaffAccount.query.filter_by(email=org.head).first()
    form.name.data = staff.fullname
    form.position.data = f"หัวหน้า{staff.personal_info.org.name}"
    if staff.personal_info.org.parent and staff.personal_info.org.parent.parent:
        form.organization.data = f'{staff.personal_info.org.name} {staff.personal_info.org.parent} {staff.personal_info.org.parent.parent}'
    elif staff.personal_info.org.parent and not staff.personal_info.org.parent.parent:
        form.organization.data = f'{staff.personal_info.org.name} {staff.personal_info.org.parent}'
    else:
        form.organization.data = staff.personal_info.org.name
    if record.procurements:
        for procurement in record.procurements:
            form.item.data = f'{procurement.procurement_no} {procurement.name}'
    if form.validate_on_submit():
        if not repair_approval_id:
            rep_approval = ComplaintRepairApproval()
        form.populate_obj(rep_approval)
        rep_approval.receipt_date = arrow.get(form.receipt_date.data,
                                              'Asia/Bangkok').date() if form.receipt_date.data else None
        if not repair_approval_id:
            rep_approval.record_id = record_id
            rep_approval.created_at = arrow.now('Asia/Bangkok').datetime
            rep_approval.creator_id = current_user.id
        if form.repair_type.data != 'เร่งด่วน':
            rep_approval.name = None
            rep_approval.position = None
        db.session.add(rep_approval)
        db.session.commit()
        if rep_approval.repair_type == 'เร่งด่วน':
            flash('บันทึกข้อมูลสำเร็จ', 'success')
            return redirect(url_for('comp_tracker.edit_record_admin', record_id=record_id))
        else:
            return redirect(url_for('comp_tracker.edit_committee', repair_approval_id=rep_approval.id))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('complaint_tracker/repair_approval_form.html', form=form, record_id=record_id)


@complaint_tracker.route('/admin/repair-approval/committee/add/<int:repair_approval_id>', methods=['GET', 'POST'])
def edit_committee(repair_approval_id):
    rep_approval = ComplaintRepairApproval.query.get(repair_approval_id)
    committees = ComplaintCommittee.query.filter_by(repair_approval_id=repair_approval_id).all()
    if rep_approval.price > 500000 and rep_approval.repair_type == 'ไม่เร่งด่วน (จ้าง/ซ่อม)':
        min_entries = 9
        default_positions = ['ประธาน', 'กรรมการ', 'กรรมการ', 'ประธาน', 'กรรมการ', 'กรรมการ', 'ประธาน', 'กรรมการ',
                             'กรรมการ']
    elif ((
                  rep_approval.price > 30000 and rep_approval.price <= 500000 and rep_approval.repair_type == 'ไม่เร่งด่วน (จ้าง/ซ่อม)')
          or (rep_approval.price > 30000 and rep_approval.repair_type == 'ไม่เร่งด่วน (จ้างซ่อม)')):
        min_entries = 3
        default_positions = ['ประธาน', 'กรรมการ', 'กรรมการ']
    else:
        min_entries = 1
        default_positions = ['ผู้ตรวจรับพัสดุ']
    form = ComplaintCommitteeGroupForm(obj=committees)
    if request.method == 'GET':
        current_count = len(committees)
        if committees:
            for committee in committees:
                c_form = form.committees.append_entry()
                c_form.form.id.data = committee.id
                c_form.form.staff.data = committee.staff
                c_form.form.position.data = committee.position
                c_form.form.committee_position.data = committee.committee_position
            for i in range(min_entries - current_count):
                c_form = form.committees.append_entry()
                if i < len(default_positions):
                    c_form.form.committee_position.data = default_positions[i]
        else:
            for i in range(min_entries):
                c_form = form.committees.append_entry()
                if i < len(default_positions):
                    c_form.form.committee_position.data = default_positions[i]
    if form.validate_on_submit():
        ComplaintCommittee.query.filter_by(repair_approval_id=rep_approval.id).delete()
        for i, c_form in enumerate(form.committees.entries):
            if not c_form.form.staff.data:
                continue
            committee = ComplaintCommittee(
                staff=c_form.form.staff.data,
                position=c_form.form.position.data,
                committee_position=c_form.form.committee_position.data,
                repair_approval_id=rep_approval.id,
                committee_name=request.form.get(f'committee_name_{i // 3}', 'ผู้ตรวจรับพัสดุ')
            )
            db.session.add(committee)
            db.session.commit()
        flash('บันทึกข้อมูลสำเร็จ', 'success')
        return redirect(url_for('comp_tracker.edit_record_admin', record_id=rep_approval.record_id))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('complaint_tracker/committee_form.html', form=form, rep_approval=rep_approval)


def generate_repair_approval_pdf(repair_approval):
    def all_page_setup(canvas, doc):
        canvas.saveState()
        canvas.restoreState()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer,
                            pagesize=A4,
                            rightMargin=38,
                            leftMargin=38,
                            topMargin=38,
                            bottomMargin=38
                            )

    data = []

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=16,
        leading=20,
        alignment=TA_RIGHT
    )
    header_right_style = ParagraphStyle(
        'HeaderRightStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=16,
        leading=20,
        alignment=TA_RIGHT,
    )
    content_style = ParagraphStyle(
        'ContentStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=16,
        leading=20,
    )
    bold_style = ParagraphStyle(
        'BoldStyle',
        parent=style_sheet['ThaiStyleBold'],
        fontSize=16,
        leading=20,
        alignment=TA_CENTER
    )
    approver_style = ParagraphStyle(
        'ApproverStyle',
        parent=style_sheet['ThaiStyleBold'],
        fontSize=16,
        leading=50,
        alignment=TA_CENTER
    )
    center_style = ParagraphStyle(
        'CenterStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=16,
        leading=20,
        alignment=TA_CENTER
    )
    item_style = ParagraphStyle(
        'ItemStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=16,
        leading=20,
        firstLineIndent=-37,
        leftIndent=37,
        alignment=TA_LEFT
    )
    item_detail_style = ParagraphStyle(
        'ItemDetailStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=16,
        leading=20,
        firstLineIndent=35,
        leftIndent=0,
    )

    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 60, 60)

    if current_user.personal_info.org.name == 'หน่วยข้อมูลและสารสนเทศ':
        organization = 'หน่วยข้อมูลและสารสนเทศ งานยุทธศาสตร์ และการบริหารพัฒนาทรัพยากร สังกัดสำนักงานคณบดี'
        organization_text = "หน่วยข้อมูลและสารสนเทศ<br/>งานยุทธศาสตร\u00A0และการบริหารพัฒนาทรัพยากร\u00A0สำนักงานคณบดี<br/>โทร 02-4414371-7 ต่อ 2320"
        organization_info = Paragraph(organization_text, style=header_right_style)
        person = Table([
            [Paragraph('ลงชื่อ', center_style), Paragraph('ผู้ขออนุมัติ', center_style)],
            [Paragraph('(นายอดิศักดิ์ นันท์นฤมิตร)', center_style), ''],
            ['', ''],
            ['', ''],
            ['', ''],
            [Paragraph('ลงชื่อ', center_style), Paragraph('หัวหน้าภาค / ศูนย์ฯ', center_style)],
            [Paragraph('(ผู้ช่วยศาสตราจารย์ ดร.ลิขิต ปรียานนท์)', center_style), ''],
        ], colWidths=[160, 160])
        person.setStyle(TableStyle([
            ('SPAN', (0, 1), (1, 1)),
            ('SPAN', (0, 6), (1, 6)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        organization = 'หน่วยซ่อมบำรุง งานบริหารจัดการทั่วไป สังกัดสำนักงานคณบดี'
        organization_text = "หน่วยซ่อมบำรุง<br/>งานบริหารจัดการทั่วไป\u00A0สำนักงานคณบดี<br/>โทร 02-4414371-9 ต่อ 2115"
        organization_info = Paragraph(organization_text, style=header_right_style)
        person = Table([
            ['', ''],
            ['', ''],
            ['', ''],
            [Paragraph('(นายธนพัฒน์ นพโสภณ)', center_style), Paragraph('', center_style)],
            [Paragraph('ตำแหน่งหัวหน้าหน่วยซ่อมบำรุง', center_style), Paragraph('', center_style)],
            ['', ''],
            ['', ''],
            ['', ''],
            ['', ''],
            ['', ''],
            ['', ''],
            [Paragraph('(รองศาสตราจารย์ ดร.กลมรัตน์ โพธิ์ปิ่น)', center_style), Paragraph('', center_style)],
            [Paragraph('ผู้ช่วยรองคณบดีฝ่ายบริหาร', center_style), Paragraph('', center_style)],
        ], colWidths=[160, 160])
        person.setStyle(TableStyle([
            ('SPAN', (0, 3), (1, 3)),
            ('SPAN', (0, 4), (1, 4)),
            ('SPAN', (0, 11), (1, 11)),
            ('SPAN', (0, 12), (1, 12)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

    purchase_type = f'<font name="DejaVuSans">☑</font> รายได้ส่วนงาน <font name="DejaVuSans">☐</font> เงินงบประมาณแผ่นดิน' if repair_approval.purchase_type == 'รายได้ส่วนงาน' else \
        f'<font name="DejaVuSans">☐</font> รายได้ส่วนงาน <font name="DejaVuSans">☑</font> เงินงบประมาณแผ่นดิน'

    price_thai = bahttext(repair_approval.price)

    formatted_price = f"{int(repair_approval.price):,}" if repair_approval.price == int(repair_approval.price) \
        else f"{repair_approval.price:,.2f}"

    mhesi_no = '''<font name="SarabunBold">ที่</font>&nbsp;&nbsp;&nbsp;&nbsp;{mhesi_no}'''.format(
        mhesi_no=repair_approval.mhesi_no)

    mhesi_no_date = arrow.get(repair_approval.mhesi_no_date).format(fmt='DD MMMM YYYY', locale='th-th')
    mhesi_no_date_info = '''<font name="SarabunBold">วันที่</font>&nbsp;&nbsp;&nbsp;&nbsp;{mhesi_no_date}'''.format(
        mhesi_no_date=mhesi_no_date)

    if repair_approval.repair_type == 'เร่งด่วน':
        indent = 47
        text_style = item_detail_style

        form_code = Table(
            [[Paragraph("MTPC-001", style=bold_style)]],
            colWidths=[70],
            rowHeights=[30]
        )
        form_code.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        item = (
            '<font name="SarabunBold">เรื่อง</font>&nbsp;&nbsp;&nbsp;&nbsp;รายงานขออนุมัติซื้อ {item} กรณีจำเป็นเร่งด่วน ไม่คาดหมายไว้ก่อน ซึ่งไม่อาจดำเนินการตามปกติได้ทัน'
            .format(item=repair_approval.item))

        org = Org.query.filter_by(head=repair_approval.creator.email).first()
        if org:
            position = 'หัวหน้า' + org.name
        else:
            position = current_user.personal_info.position

        item_detail = '''ด้วย ข้าพเจ้า {creator} ตำแหน่ง {position} สังกัด {org} ซึ่งเป็นผู้รับผิดชอบในการซื้อ {item} ไปก่อนแล้ว จึงขอรายงานเหตุ
                        ผลและความจำเป็น กรณีเร่งด่วน โดยมีรายละเอียด ดังนี้'''.format(
            creator=repair_approval.creator.fullname,
            item=repair_approval.item,
            position=position,
            org=organization)

        reason_title = '<para leftIndent=35><font name="SarabunBold">1. เหตุผลและความจำเป็นเร่งด่วนที่ต้องซื้อหรือจ้าง</font></para>'

        detail_title = '<para leftIndent=35><font name="SarabunBold">2. รายละเอียดของพัสดุที่ซื้อหรือจ้าง</font></para>'

        receipt_date = arrow.get(repair_approval.receipt_date).format(fmt='DD MMMM YYYY', locale='th-th')
        price = (
            '<font name="SarabunBold">3. วงเงินที่ซื้อหรือจ้างในครั้งนี้เป็นเงิน</font> {price} บาท ({price_thai}) จาก {budget_source} ตามใบส่งของ/ใบเสร็จรับเงิน '
            'เล่มที่ {book_number} เลขที่ {receipt_number} วันที่ {receipt_date} ทั้งนี้ ข้าพเจ้าพร้อมหัวหน้าหน่วยงานได้ลงนามรับรองในใบส่ง'
            'ของหรือใบเสร็จรับเงินว่า “ได้ตรวจรับพัสดุไว้ถูกต้องครบถ้วนแล้ว”'
            .format(price=formatted_price, price_thai=price_thai, budget_source=repair_approval.budget_source,
                    book_number=repair_approval.book_number, receipt_number=repair_approval.receipt_number,
                    receipt_date=receipt_date))

        receipt = (
            '<para leftIndent=35><font name="SarabunBold">4. โดยขอเบิกจ่ายจากเงิน</font> {purchase_type} ประจำปีงบประมาณ {budget_year} </para>'
            .format(purchase_type=purchase_type, budget_year=repair_approval.budget_year))

        remark = (
            '<font name="SarabunBold">5. ขออนุมัติขยายระยะเวลาเบิกจ่ายเงินเกิน 30 วัน</font> ไม่เป็นไปตามข้อบังคับมหาวิทยาลัยมหิดล ว่าด้วยการ'
            'บริหารงบประมาณและการเงิน (ฉบับที่ 2) พ.ศ.2556 ข้อ 32 เนื่องจาก {remark}'
            .format(remark=repair_approval.remark))
        if repair_approval.remark:
            description = (
                '<para leftIndent=55>จึงเรียนมาเพื่อโปรดพิจารณา <font name="SarabunBold">หากเห็นชอบโปรด</font><br/>'
                '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">1. อนุมัติซื้อหรือจ้างตามรายการข้างต้น</font><br/>'
                '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">2. ทราบผลการตรวจรับพัสดุ และอนุมัติเบิกจ่ายเงิน</font> '
                'ให้แก่ {requester}<br/>'
                '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;เป็นเงินทั้งสิ้น {price} บาท ({price_thai})) '
                'โดยส่งใช้เงินยืมทดรองจ่ายในนาม<br/>'
                '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"{borrower}"'
                '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">และให้ถือว่ารายงานฉบับนี้'
                'เป็นหลักฐานการตรวจรับโดยอนุโลม</font><br/>'
                '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">3. อนุมัติขยายระยะเวลาเบิกจ่ายเงิน</font>  '
                '(ใช้กรณีขยายระยะเวลาเบิกจ่ายเงินเกิน 30 วัน หากไม่มีให้ลบออก)'
                '</para>').format(requester=repair_approval.borrower,
                                  price=formatted_price, price_thai=price_thai,
                                  borrower=repair_approval.borrower)
        else:
            description = ('<para leftIndent=55>จึงเรียนมาเพื่อโปรดพิจารณา หากเห็นชอบโปรด<br/>'
                           '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">1. อนุมัติซื้อหรือจ้างตามรายการข้างต้น</font><br/>'
                           '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">2. ทราบผลการตรวจรับพัสดุ และอนุมัติเบิกจ่ายเงิน</font> '
                           'ให้แก่ {requester}<br/>'
                           '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;เป็นเงินทั้งสิ้น {price} บาท ({price_thai})) โดยส่ง'
                           'ใช้เงินยืมทดรองจ่ายในนาม<br/>'
                           '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"{borrower}"<br/>'
                           '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">และให้ถือว่ารายงานฉบับนี้'
                           'เป็นหลักฐานการตรวจรับโดยอนุโลม</font>'
                           '</para>').format(requester=repair_approval.borrower,
                                             price=formatted_price, price_thai=price_thai,
                                             borrower=repair_approval.borrower)
    elif repair_approval.repair_type == 'ไม่เร่งด่วน (จ้าง/ซ่อม)':
        indent = 14
        text_style = content_style
        if repair_approval.price <= 30000:
            mtpc = 'MTPC-002'
        elif repair_approval.price > 30000 and repair_approval.price <= 500000:
            mtpc = 'MTPC-003'
        else:
            mtpc = 'MTPC-004'
        form_code = Table(
            [[Paragraph(mtpc, style=bold_style)]],
            colWidths=[70],
            rowHeights=[30]
        )
        form_code.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        checkbox = f'<font name="DejaVuSans">☑</font> ซื้อ <font name="DejaVuSans">☐</font> จ้าง' if repair_approval.principle_approval_type == 'ซื้อ' else \
            f'<font name="DejaVuSans">☐</font> ซื้อ <font name="DejaVuSans">☑</font> จ้าง'
        item = (
            '''<font name="SarabunBold">เรื่อง</font>&nbsp;&nbsp;&nbsp;&nbsp;ขออนุมัติในหลักการ {checkbox} รายการ {item}'''
            .format(checkbox=checkbox, item=repair_approval.item))

        item_detail = '''ด้วย {org} มีความประสงค์จะจัดซื้อหรือจ้าง {purpose} รายละเอียดดังนี้'''.format(org=organization,
                                                                                        purpose=repair_approval.purpose)

        reason_title = '<font name="SarabunBold">1. เหตุผลและความจำเป็นต้องซื้อ</font>'

        detail_title = '<font name="SarabunBold">2. รายละเอียดคุณลักษณะเฉพาะของพัสดุที่ซื้อหรือจ้าง</font>'

        price = ('<font name="SarabunBold">3. วงเงินที่ซื้อหรือจ้างในครั้งนี้เป็นเงิน</font> {price} บาท ({price_thai})'
                 .format(price=formatted_price, price_thai=price_thai))

        receipt = (
            '<font name="SarabunBold">4. โดยขอเบิกจ่ายจากเงิน</font> {purchase_type} ประจำปีงบประมาณ {budget_year}'
            .format(purchase_type=purchase_type, budget_year=repair_approval.budget_year))

        remark = (
            '<font name="SarabunBold">6. ตามแนวทางปฏิบัติตามกฎกระทรวงกำหนดพัสดุและวิธีการจัดซื้อจัดจ้างพัสดุที่รัฐต้องการส่งเสริมหรือสนับสนุน '
            '(ฉบับที่ 2) พ.ศ. 2563</font><br/>'
            '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
            '☐ มีความจำเป็นจะต้องมีการใช้พัสดุที่ผลิตจากต่างประเทศหรือนำเข้าพัสดุจากต่างประเทศ เนื่องจาก {remark}'
            .format(remark=repair_approval.remark if repair_approval.remark else
            '<br/>(กรณีไม่สามารถใช้สินค้าจาก SME หรือ Made In Thailand ได้)'))

        description = (
            '<para leftIndent=45>จึงเรียนมาเพื่อโปรดพิจารณา <font name="SarabunBold">หากเห็นชอบโปรด</font><br/>'
            '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">1. อนุมัติในหลักการซื้อหรือจ้างตามรายการข้างต้น</font><br/>'
            '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">2. อนุมัติตามข้อ 6</font> กรณีที่มีความจำเป็นต้องมีการใช้พัสดุที่ผลิตจากต่างประเทศหรือนำเข้าพัสดุจาก<br/>ต่างประเทศเท่านั้น<br/>'
            '</para>')
    else:
        indent = 14
        text_style = content_style

        form_code = Table(
            [[Paragraph("MTPC-007", style=bold_style)]],
            colWidths=[70],
            rowHeights=[30]
        )
        form_code.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        item = '''<font name="SarabunBold">เรื่อง</font>&nbsp;&nbsp;&nbsp;&nbsp;ขออนุมัติในหลักการ <font name="DejaVuSans">☑</font> 
                    จ้างซ่อม ครุภัณฑ์ {item}'''.format(item=repair_approval.item)

        item_detail = ('''ด้วย {org} มีความประสงค์จะจ้างซ่อมครุภัณฑ์ {item} {procurement_no} รายละเอียดดังนี้'''
                       .format(org=organization, item=repair_approval.item,
                               procurement_no=repair_approval.procurement_no))

        reason_title = '<font name="SarabunBold">1. เหตุผลและความจำเป็นต้องจ้างซ่อม</font>'

        detail_title = '<font name="SarabunBold">2. รายละเอียดการซ่อม</font>'

        price = ('<font name="SarabunBold">3. วงเงินที่ซ่อมในครั้งนี้เป็นเงิน</font> {price} บาท ({price_thai})'
                 .format(price=repair_approval.price, price_thai=price_thai))

        receipt = (
            '<font name="SarabunBold">4. โดยขอเบิกจ่ายจากเงิน</font> {purchase_type} ประจำปีงบประมาณ {budget_year}'
            .format(purchase_type=purchase_type, budget_year=repair_approval.budget_year))

        remark = (
            '<font name="SarabunBold">6. ตามแนวทางปฏิบัติตามกฎกระทรวงกำหนดพัสดุและวิธีการจัดซื้อจัดจ้างพัสดุที่รัฐต้องการส่งเสริมหรือสนับสนุน '
            '(ฉบับที่ 2) พ.ศ. 2563</font><br/>'
            '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
            '☐ มีความจำเป็นจะต้องมีการใช้พัสดุที่ผลิตจากต่างประเทศหรือนำเข้าพัสดุจากต่างประเทศ เนื่องจาก {remark}'
            .format(remark=repair_approval.remark if repair_approval.remark else
            '<br/>(กรณีไม่สามารถใช้สินค้าจาก SME หรือ Made In Thailand ได้)'))

        description = (
            '<para leftIndent=45>จึงเรียนมาเพื่อโปรดพิจารณา <font name="SarabunBold">หากเห็นชอบโปรด</font><br/>'
            '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">1. อนุมัติในหลักการซื้อหรือจ้างตามรายการข้างต้น</font><br/>'
            '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">2. อนุมัติตามข้อ 6</font> กรณีที่มีความจำเป็นต้องมีการใช้พัสดุที่ผลิตจากต่างประเทศหรือนำเข้าพัสดุจาก<br/>ต่างประเทศเท่านั้น<br/>'
            '</para>')
    if repair_approval.repair_type == 'ไม่เร่งด่วน (จ้าง/ซ่อม)' and repair_approval.price <= 30000:
        code_detail = ('รหัสศูนย์ต้นทุน {cost_center} รหัสใบสั่งงานภายใน {io_code}'
                       .format(cost_center=repair_approval.cost_center, io_code=repair_approval.io_code.id))
    else:
        code_detail = ('รหัสศูนย์ต้นทุน {cost_center} รหัสใบสั่งงานภายใน {io_code} ผลผลิต {product_code}'
                       .format(cost_center=repair_approval.cost_center, io_code=repair_approval.io_code.id,
                               product_code=repair_approval.product_code))
    logo_cell = [[logo]]
    logo_table = Table(logo_cell, colWidths=[60])
    logo_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('VALIGN', (0, 0), (0, 0), 'TOP'),
    ]))

    header_right_table = Table([
        [form_code],
        [organization_info]
    ])
    header_right_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    header_table = Table([
        [Spacer(1, 1), logo_table, header_right_table]
    ], colWidths=[160, 180, 200])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
    ]))

    approval = Table([
        [Paragraph('อนุมัติ', style=approver_style)],
        [Paragraph('(ผู้ช่วยศาสตราจารย์ ดร.โชติรส พลับพลึง)<br/>คณบดีคณะเทคนิคการแพทย์', style=center_style)]
    ], colWidths=195)

    approval.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))

    footer_table = Table([
        [approval, Spacer(10, 0), person]
    ], colWidths=[180, 10, 330])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
    ]))

    data.append(header_table)
    data.append(Spacer(1, 12))
    data.append(Paragraph(mhesi_no, style=content_style))
    data.append(Paragraph(mhesi_no_date_info, style=content_style))
    data.append(Paragraph(item, style=item_style))
    data.append(Paragraph(f'<font name="SarabunBold">เรียน</font>&nbsp;&nbsp;&nbsp;&nbsp;คณบดีคณะเทคนิคการแพทย์',
                          style=content_style))
    data.append(Paragraph(item_detail, style=item_detail_style))
    data.append(Paragraph(reason_title, style=content_style))
    data.append(Paragraph(f'<para leftIndent={indent}>{repair_approval.reason}</para>', style=content_style))
    data.append(Paragraph(detail_title, style=content_style))
    data.append(Paragraph(f'<para leftIndent={indent}>{repair_approval.detail}</para>', style=content_style))
    data.append(Paragraph(price, style=text_style))
    data.append(Paragraph(receipt, style=content_style))
    data.append(Paragraph(code_detail, style=content_style))
    if repair_approval.repair_type == 'ไม่เร่งด่วน (จ้าง/ซ่อม)':
        if repair_approval.price > 500000:
            committee_title = '5. ขอแต่งตั้งผู้มีรายนามต่อไปนี้ เป็นผู้ตรวจรับพัสดุ'
            data.append(Paragraph(committee_title, style=content_style))
            ordered_committee_names = [
                'คณะกรรมการกำหนดรายละเอียดคุณลักษณะเฉพาะ',
                'คณะกรรมการพิจารณาผลการประกวดราคาอิเล็กทรอนิกส์',
                'คณะกรรมการตรวจรับพัสดุ'
            ]

            for committee_name in ordered_committee_names:
                committee_members = [
                    c for c in repair_approval.committees
                    if c.committee_name.strip() == committee_name
                ]

                if committee_members:
                    data.append(Paragraph(committee_name, style=content_style))
                    count = 2
                    for c in committee_members:
                        if c.committee_position == "ประธาน":
                            para = f'<para leftIndent=35>1) {c.staff.fullname} ตำแหน่ง {c.position} {c.committee_position}</para>'
                            data.append(Paragraph(para, style=content_style))
                    for c in committee_members:
                        if c.committee_position == "กรรมการ":
                            para = f'<para leftIndent=35>{count}) {c.staff.fullname} ตำแหน่ง {c.position} {c.committee_position}</para>'
                            data.append(Paragraph(para, style=content_style))
                            count += 1
        elif repair_approval.price > 30000 and repair_approval.price <= 500000:
            committee_title = '5. ขอแต่งตั้งผู้มีรายนามต่อไปนี้ เป็นคณะกรรมการตรวจรับพัสดุ'
            data.append(Paragraph(committee_title, style=content_style))
            count = 2
            for c in repair_approval.committees:
                if c.committee_position == "ประธาน":
                    committee = ('<para leftIndent=35>5.1 {committee} ตำแหน่ง {position} {committee_position}</para>'
                                 .format(committee=c.staff.fullname, position=c.position,
                                         committee_position=c.committee_position))
                elif c.committee_position == "กรรมการ":
                    committee = (
                        '<para leftIndent=35>5.{num} {committee} ตำแหน่ง {position} {committee_position}</para>'
                        .format(num=count, committee=c.staff.fullname, position=c.position,
                                committee_position=c.committee_position))
                    count += 1
                else:
                    committee = ('<para leftIndent=35>5.1 {committee} ตำแหน่ง {position} {committee_position}</para>'
                                 .format(committee=c.staff.fullname, position=c.position,
                                         committee_position=c.committee_position))
                data.append(Paragraph(committee, style=content_style))
        else:
            committee_title = '5. ขอแต่งตั้งผู้มีรายนามต่อไปนี้ เป็นผู้ตรวจรับพัสดุ'
            data.append(Paragraph(committee_title, style=content_style))
            for c in repair_approval.committees:
                committee = ('<para leftIndent=35>5.1 {committee} ตำแหน่ง {position} {committee_position}</para>'
                             .format(committee=c.staff.fullname, position=c.position,
                                     committee_position=c.committee_position))
                data.append(Paragraph(committee, style=content_style))
    elif repair_approval.repair_type == 'ไม่เร่งด่วน (จ้างซ่อม)':
        if repair_approval.price > 30000:
            committee_title = '5. ขอแต่งตั้งผู้มีรายนามต่อไปนี้ เป็นผู้ตรวจรับพัสดุ'
        else:
            committee_title = '5. ขอแต่งตั้งผู้มีรายนามต่อไปนี้ เป็นคณะกรรมการตรวจรับพัสดุ'
        data.append(Paragraph(committee_title, style=content_style))
        count = 2
        for c in repair_approval.committees:
            if c.committee_position == "ประธาน":
                committee = ('<para leftIndent=35>5.1 {committee} ตำแหน่ง {position} {committee_position}</para>'
                             .format(committee=c.staff.fullname, position=c.position,
                                     committee_position=c.committee_position))
            elif c.committee_position == "กรรมการ":
                committee = ('<para leftIndent=35>5.{num} {committee} ตำแหน่ง {position} {committee_position}</para>'
                             .format(num=count, committee=c.staff.fullname, position=c.position,
                                     committee_position=c.committee_position))
                count += 1
            else:
                committee = ('<para leftIndent=35>5.1 {committee} ตำแหน่ง {position} {committee_position}</para>'
                             .format(committee=c.staff.fullname, position=c.position,
                                     committee_position=c.committee_position))
            data.append(Paragraph(committee, style=content_style))
    if (repair_approval.repair_type == 'เร่งด่วน' and repair_approval.remark) or repair_approval.repair_type == 'ไม่เร่งด่วน (จ้าง/ซ่อม)' \
            or repair_approval.repair_type == 'ไม่เร่งด่วน (จ้างซ่อม)':
        data.append(Paragraph(remark, style=text_style))
    data.append(Paragraph(description, style=content_style))
    data.append(Spacer(1, 12))
    data.append(footer_table)
    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    buffer.seek(0)
    return buffer


@complaint_tracker.route('/admin/repair-approval/pdf/<int:repair_approval_id>', methods=['GET'])
def export_repair_approval_pdf(repair_approval_id):
    repair_approval = ComplaintRepairApproval.query.get(repair_approval_id)
    buffer = generate_repair_approval_pdf(repair_approval)
    return send_file(buffer, download_name='Repair_approval_form.pdf', as_attachment=True)


@complaint_tracker.route('/api/admin/new-record-complaint')
@login_required
def get_new_record_complaint():
    code = request.args.get('code')
    description = {'date': ('date', 'Day'), 'heads': ('number', 'heads')}
    data = defaultdict(int)
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    if code != 'null':
        records = ComplaintRecord.query.filter(ComplaintRecord.created_at.between(START_FISCAL_DATE, END_FISCAL_DATE),
                                               ComplaintRecord.topic.has(code=code))
    else:
        records = ComplaintRecord.query.filter(ComplaintRecord.created_at.between(START_FISCAL_DATE, END_FISCAL_DATE))
    for record in records:
        if not record.status:
            data[record.created_at.date()] += 1
    count_data = []
    for date, heads in data.items():
        count_data.append({
            'date': date,
            'heads': heads
        })
    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon(columns_order=('date', 'heads'))


@complaint_tracker.route('/api/admin/pending-record-complaint')
@login_required
def get_pending_record_complaint():
    code = request.args.get('code')
    description = {'date': ("date", "Day"), 'heads': ("number", "heads")}
    data = defaultdict(int)
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    if code != 'null':
        records = ComplaintRecord.query.filter(ComplaintRecord.created_at.between(START_FISCAL_DATE, END_FISCAL_DATE),
                                               ComplaintRecord.topic.has(code=code))
    else:
        records = ComplaintRecord.query.filter(ComplaintRecord.created_at.between(START_FISCAL_DATE, END_FISCAL_DATE))
    for record in records:
        if record.status is not None and (record.status.code == 'pending'):
            data[record.created_at.date()] += 1
    count_data = []
    for date, heads in data.items():
        count_data.append({
            'date': date,
            'heads': heads
        })
    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon(columns_order=('date', 'heads'))


@complaint_tracker.route('/api/admin/progress-record-complaint')
@login_required
def get_progress_record_complaint():
    code = request.args.get('code')
    description = {'date': ("date", "Day"), 'heads': ("number", "heads")}
    data = defaultdict(int)
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    if code != 'null':
        records = ComplaintRecord.query.filter(ComplaintRecord.created_at.between(START_FISCAL_DATE, END_FISCAL_DATE),
                                               ComplaintRecord.topic.has(code=code))
    else:
        records = ComplaintRecord.query.filter(ComplaintRecord.created_at.between(START_FISCAL_DATE, END_FISCAL_DATE))
    for record in records:
        if record.status is not None and record.status.code == 'progress':
            data[record.created_at.date()] += 1
    count_data = []
    for date, heads in data.items():
        count_data.append({
            'date': date,
            'heads': heads
        })
    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon(columns_order=('date', 'heads'))


@complaint_tracker.route('/api/admin/success-record-complaint')
@login_required
def get_success_record_complaint():
    code = request.args.get('code')
    description = {'date': ("date", "Day"), 'heads': ("number", "heads")}
    data = defaultdict(int)
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    if code != 'null':
        records = ComplaintRecord.query.filter(ComplaintRecord.closed_at.between(START_FISCAL_DATE, END_FISCAL_DATE),
                                               ComplaintRecord.topic.has(code=code))
    else:
        records = ComplaintRecord.query.filter(ComplaintRecord.closed_at.between(START_FISCAL_DATE, END_FISCAL_DATE))
    for record in records:
        if record.status is not None and record.status.code == 'completed':
            data[record.closed_at.date()] += 1
    count_data = []
    for date, heads in data.items():
        count_data.append({
            'date': date,
            'heads': heads
        })
    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon(columns_order=('date', 'heads'))


@complaint_tracker.route('/api/admin/pie-chart')
@login_required
def get_pie_chart_for_record_complaint():
    code = request.args.get('code')
    description = {'status': ("string", "Status"), 'heads': ("number", "heads")}
    data = defaultdict(int)
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    if code != 'null':
        records = ComplaintRecord.query.filter(
            or_(ComplaintRecord.closed_at.between(START_FISCAL_DATE, END_FISCAL_DATE),
                ComplaintRecord.created_at.between(START_FISCAL_DATE, END_FISCAL_DATE)),
            ComplaintRecord.topic.has(code=code))
    else:
        records = ComplaintRecord.query.filter(
            or_(ComplaintRecord.closed_at.between(START_FISCAL_DATE, END_FISCAL_DATE),
                ComplaintRecord.created_at.between(START_FISCAL_DATE, END_FISCAL_DATE)))
    for record in records:
        if record.status is None:
            data['ยังไม่ดำเนินการ'] += 1
        else:
            data[record.status] += 1
    count_data = []
    for status, heads in data.items():
        count_data.append({
            'status': status,
            'heads': heads
        })
    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon(columns_order=('status', 'heads'))


@complaint_tracker.route('/api/admin/bar-chart')
@login_required
def get_bar_chart_for_record_complaint():
    code = request.args.get('code')
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())

    if code != 'null':
        records = ComplaintRecord.query.filter(
            or_(
                ComplaintRecord.closed_at.between(START_FISCAL_DATE, END_FISCAL_DATE),
                ComplaintRecord.created_at.between(START_FISCAL_DATE, END_FISCAL_DATE)
            ),
            ComplaintRecord.topic.has(code=code)
        )
    else:
        records = ComplaintRecord.query.filter(
            or_(
                ComplaintRecord.closed_at.between(START_FISCAL_DATE, END_FISCAL_DATE),
                ComplaintRecord.created_at.between(START_FISCAL_DATE, END_FISCAL_DATE)
            )
        )

    status_data = set()
    data = defaultdict(lambda: defaultdict(int))
    for record in records:
        month = record.created_at.strftime('%B %Y')
        status = record.status.status if record.status else 'ยังไม่ดำเนินการ'
        status_data.add(status)
        data[month][status] += 1
    statuses = list(status_data)
    description = {'month': ('string', 'Month')}
    for status in statuses:
        description[status] = ('number', status)

    count_data = []
    for month in sorted(data.keys(), key=lambda x: datetime.strptime(x, '%B %Y').month):
        row = {'month': month}
        for status in statuses:
            row[status] = data[month].get(status, 0)
        count_data.append(row)
    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon(columns_order=['month'] + statuses)


@complaint_tracker.route('/api/admin/tag-bar-chart')
@login_required
def get_tag_bar_chart_for_record_complaint():
    description = {'tag': ("string", "Tag"), 'amount': ("number", "amount")}
    count_data = []
    for tag in ComplaintTag.query.all():
        amount = len(tag.records)
        count_data.append({
            'tag': tag.tag,
            'amount': amount
        })
    sort_data = sorted(count_data, key=lambda x: x['amount'], reverse=True)
    count_sort_data = sort_data[:10]
    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_sort_data)
    return data_table.ToJSon(columns_order=('tag', 'amount'))
