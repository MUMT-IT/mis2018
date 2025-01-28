import os
import arrow
import requests
import pandas
from io import BytesIO
from pytz import timezone
from datetime import datetime, date

from app.academic_services.forms import create_request_form, ServiceSampleAppointmentForm
from app.service_admin import service_admin
from app.academic_services.models import *
from flask import render_template, flash, redirect, url_for, request, session, make_response, jsonify, current_app, \
    send_file
from flask_login import current_user, login_required
from sqlalchemy import or_, and_
from app.service_admin.forms import (ServiceCustomerInfoForm, ServiceCustomerAddressForm, ServiceResultForm,
                                     ServiceInvoiceForm)
from app.main import app, get_credential, json_keyfile
from app.main import mail
from flask_mail import Message
from werkzeug.utils import secure_filename
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, TableStyle, Table, Spacer, KeepTogether, PageBreak

localtz = timezone('Asia/Bangkok')

sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
pdfmetrics.registerFont(sarabun_font)
style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))
style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', alignment=TA_CENTER))

gauth = GoogleAuth()
keyfile_dict = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
scopes = ['https://www.googleapis.com/auth/drive']
gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scopes)
drive = GoogleDrive(gauth)

FOLDER_ID = '1832el0EAqQ6NVz2wB7Ade6wRe-PsHQsu'

keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile, scopes)
    return GoogleDrive(gauth)


@service_admin.route('/')
# @login_required
def index():
    return render_template('service_admin/index.html')


@service_admin.route('/customer/view')
@login_required
def view_customer():
    customers = ServiceCustomerInfo.query.all()
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    return render_template('service_admin/view_customer.html', customers=customers, admin=admin)


@service_admin.route('/customer/add', methods=['GET', 'POST'])
@service_admin.route('/customer/edit/<int:customer_id>', methods=['GET', 'POST'])
def create_customer(customer_id=None):
    if customer_id:
        customer = ServiceCustomerInfo.query.get(customer_id)
        form = ServiceCustomerInfoForm(obj=customer)
    else:
        form = ServiceCustomerInfoForm()
    if form.validate_on_submit():
        if customer_id is None:
            customer = ServiceCustomerInfo()
        form.populate_obj(customer)
        if customer_id is None:
            customer.creator_id = current_user.id
            account = ServiceCustomerAccount(email=form.email.data, customer_info=customer)
        else:
            for account in customer.accounts:
                account.email = form.email.data
        db.session.add(account)
        db.session.add(customer)
        db.session.commit()
        if customer_id:
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
        else:
            flash('เพิ่มลูกค้าสำเร็จ', 'success')
        return redirect(url_for('service_admin.view_customer'))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('service_admin/create_customer.html', customer_id=customer_id,
                           form=form)


@service_admin.route('/customer/address/edit/<int:customer_id>', methods=['GET', 'POST'])
def create_address(customer_id=None):
    if customer_id:
        customer = ServiceCustomerInfo.query.get(customer_id)
        form = ServiceCustomerInfoForm(obj=customer)
    else:
        form = ServiceCustomerInfoForm()
    if form.validate_on_submit():
        if customer_id is None:
            customer = ServiceCustomerInfo()
        form.populate_obj(customer)
        if customer_id is None:
            customer.creator_id = current_user.id
        db.session.add(customer)
        db.session.commit()
        if customer_id:
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
        else:
            flash('เพิ่มลูกค้าสำเร็จ', 'success')
        return redirect(url_for('service_admin.view_customer'))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('service_admin/create_customer.html', customer_id=customer_id, form=form)


@service_admin.route('/request/index')
@login_required
def request_index():
    return render_template('service_admin/request_index.html')


@service_admin.route('/api/request/index')
def get_requests():
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    labs = []
    sub_labs = []
    for a in admin:
        if a.lab:
            labs.append(a.lab.code)
        else:
            sub_labs.append(a.sub_lab.code)
    query = ServiceRequest.query.filter(or_(ServiceRequest.admin.has(id=current_user.id), ServiceRequest.lab.in_(labs))) \
        if labs else ServiceRequest.query.filter(or_(ServiceRequest.admin.has(id=current_user.id), ServiceRequest.lab.in_(sub_labs)))
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ServiceRequest.request_no.contains(search))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        data.append(item_data)
    return jsonify({'data': data,
                    'recordFiltered': total_filtered,
                    'recordTotal': records_total,
                    'draw': request.args.get('draw', type=int)
                    })


@service_admin.route('/request/add/<int:customer_id>', methods=['GET'])
@service_admin.route('/request/edit/<int:request_id>', methods=['GET'])
@login_required
def create_request(request_id=None, customer_id=None):
    code = request.args.get('code')
    return render_template('service_admin/create_request.html', code=code, request_id=request_id, customer_id=customer_id)


@service_admin.route('/api/request/form', methods=['GET'])
def get_request_form():
    code = request.args.get('code')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    lab = ServiceLab.query.filter_by(code=code).first() if code else ServiceLab.query.filter_by(code=service_request.lab).first()
    sub_lab = ServiceSubLab.query.filter_by(code=code).first() if code else ServiceSubLab.query.filter_by(code=service_request.lab).first()
    sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    if sub_lab:
        sheet = wks.worksheet(sub_lab.sheet)
    else:
        sheet = wks.worksheet(lab.sheet)
    df = pandas.DataFrame(sheet.get_all_records())
    if request_id:
        data = service_request.data
        form = create_request_form(df)(**data)
    else:
        form = create_request_form(df)()
    template = ''
    for f in form:
        template += str(f)
    return template


def form_data(data):
    if isinstance(data, dict):
        return {k: form_data(v) for k, v in data.items() if k != "csrf_token" and k != 'submit'}
    elif isinstance(data, list):
        return [form_data(item) for item in data]
    elif isinstance(data, (date)):
        return data.isoformat()
    return data


@service_admin.route('/submit-request/add/<int:customer_id>', methods=['POST'])
@service_admin.route('/submit-request/edit/<int:request_id>', methods=['POST'])
def submit_request(request_id=None, customer_id=None):
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        lab = ServiceLab.query.filter_by(code=service_request.lab).first()
        sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab).first()
    else:
        code = request.args.get('code')
        lab = ServiceLab.query.filter_by(code=code).first()
        sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    if sub_lab:
        sheet = wks.worksheet(sub_lab.sheet)
    else:
        sheet = wks.worksheet(lab.sheet)
    df = pandas.DataFrame(sheet.get_all_records())
    form = create_request_form(df)(request.form)
    if request_id:
        service_request.data = form_data(form.data)
        service_request.modified_at = arrow.now('Asia/Bangkok').datetime
    else:
        service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id,
                                         created_at=arrow.now('Asia/Bangkok').datetime, lab=sub_lab.code if sub_lab
            else lab.code, data=form_data(form.data))
    db.session.add(service_request)
    db.session.commit()
    if not request_id:
        service_request.request_no = f'RQ{service_request.id}'
        db.session.add(service_request)
        db.session.commit()
    return redirect(url_for('service_admin.view_request', request_id=service_request.id))


@service_admin.route('/request/test/process/<int:request_id>', methods=['GET'])
def process_test(request_id):
    service_request = ServiceRequest.query.get(request_id)
    service_request.status = 'กำลังดำเนินการทดสอบ'
    db.session.add(service_request)
    db.session.commit()
    flash('อัพเดตสถานะสำเร็จ', 'success')
    return redirect(url_for('service_admin.request_index'))


@service_admin.route('/request/test/confirm/<int:request_id>', methods=['GET'])
def confirm_test(request_id):
    service_request = ServiceRequest.query.get(request_id)
    service_request.status = 'ดำเนินการทดสอบเสร็จสิ้น'
    db.session.add(service_request)
    db.session.commit()
    flash('อัพเดตสถานะสำเร็จ', 'success')
    return redirect(url_for('service_admin.request_index'))


@service_admin.route('/request/view/<int:request_id>')
@login_required
def view_request(request_id=None):
    service_request = ServiceRequest.query.get(request_id)
    return render_template('service_admin/view_request.html', service_request=service_request)


def generate_request_pdf(service_request, sign=False, cancel=False):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 40, 40)

    sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    lab = ServiceLab.query.filter_by(code=service_request.lab).first()
    sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab).first()
    if sub_lab:
        sheet = wks.worksheet(sub_lab.sheet)
    else:
        sheet = wks.worksheet(lab.sheet)
    df = pandas.DataFrame(sheet.get_all_records())
    data = service_request.data
    form = create_request_form(df)(**data)
    values = []
    set_fields = set()
    for fn in df.fieldGroup:
        for field in getattr(form, fn):
            if field.type == 'FieldList':
                for fd in field:
                    for f in fd:
                        if f.data != None and f.data != '' and f.data != [] and f.label not in set_fields:
                            set_fields.add(f.label)
                            if f.type == 'CheckboxField':
                                values.append(f"{f. label.text} : {', '.join(f.data)}")
                            else:
                                values.append(f"{f.label.text} : {f.data}")
            else:
                if field.data != None and field.data != '' and field.data != [] and field.label not in set_fields:
                    set_fields.add(field.label)
                    if field.type == 'CheckboxField':
                        values.append(f"{field.label.text} : {', '.join(field.data)}")
                    else:
                        values.append(f"{field.label.text} : {field.data}")

    def all_page_setup(canvas, doc):
        canvas.saveState()
        canvas.setFont("Sarabun", 12)
        page_number = canvas.getPageNumber()
        canvas.drawString(530, 30, f"Page {page_number}")
        canvas.restoreState()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer,
                            rightMargin=20,
                            leftMargin=20,
                            topMargin=10,
                            bottomMargin=10
                            )

    data = []

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=15,
        alignment=TA_CENTER,
    )

    header = Table([[Paragraph('<b>ใบขอรับบริการ / Request</b>', style=header_style)]], colWidths=[530],
                   rowHeights=[25])

    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    lab_address = '''<para><font size=12>
                    {address}
                    </font></para>'''.format(address=lab.address if lab else sub_lab.address)

    lab_table = Table([[logo, Paragraph(lab_address, style=style_sheet['ThaiStyle'])]], colWidths=[45, 330])

    lab_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))

    staff_only = '''<para><font size=12>
                สำหรับเจ้าหน้าที่ / Staff only<br/>
                เลขที่ใบคำขอ &nbsp;&nbsp;_____________<br/>
                วันที่รับตัวอย่าง _____________<br/>
                วันที่รายงานผล _____________<br/>
                </font></para>'''

    staff_table = Table([[Paragraph(staff_only, style=style_sheet['ThaiStyle'])]], colWidths=[150])

    staff_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))

    content_header = Table([[Paragraph('<b>รายละเอียด / Detail</b>', style=header_style)]], colWidths=[530],
                           rowHeights=[25])

    content_header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    detail_style = ParagraphStyle(
        'ThaiStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=12,
        leading=18
    )

    customer = '''<para>ข้อมูลผู้ส่งตรวจ<br/>
                        ผู้ส่ง : {customer}<br/>
                        เบอร์โทรศัพท์ : {phone_number}<br/>
                        ที่อยู่ : {address}<br/>
                        อีเมล : {email}
                    </para>
                    '''.format(customer=service_request.customer.customer_info.cus_name,
                               address=', '.join([address.address for address in service_request.customer.customer_info.addresses if address.address_type == 'customer']),
                               phone_number=service_request.customer.customer_info.phone_number,
                               email=service_request.customer.customer_info.email)

    customer_table = Table([[Paragraph(customer, style=detail_style)]], colWidths=[530])

    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    data.append(KeepTogether(Spacer(7, 7)))
    data.append(KeepTogether(Paragraph('<para align=center><font size=18>ใบขอรับบริการ / REQUEST<br/><br/></font></para>',
                                       style=style_sheet['ThaiStyle'])))
    data.append(KeepTogether(header))
    data.append(KeepTogether(Spacer(3, 3)))
    data.append(KeepTogether(Table([[lab_table, staff_table]], colWidths=[378, 163])))
    data.append(KeepTogether(Spacer(3, 3)))
    data.append(KeepTogether(content_header))
    data.append(KeepTogether(Spacer(7, 7)))
    data.append(KeepTogether(customer_table))

    details = 'ข้อมูลผลิตภัณฑ์' + "<br/>" + "<br/>".join(values)
    first_page_limit = 500
    remaining_text = ""
    current_length = 0

    lines = details.split("<br/>")
    first_page_lines = []
    for line in lines:
        if current_length + detail_style.leading <= first_page_limit:
            first_page_lines.append(line)
            current_length += detail_style.leading
        else:
            remaining_text += line + "<br/>"

    first_page_text = "<br/>".join(first_page_lines)
    first_page_paragraph = Paragraph(first_page_text, style=detail_style)

    if remaining_text:
        remaining_paragraph = Paragraph(remaining_text, style=detail_style)

    first_page_table = [[first_page_paragraph]]
    first_page_table = Table(first_page_table, colWidths=[530])
    first_page_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    data.append(KeepTogether(first_page_table))

    if remaining_text:
        data.append(PageBreak())
        remaining_table = [[remaining_paragraph]]
        remaining_table = Table(remaining_table, colWidths=[530])
        remaining_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        data.append(KeepTogether(Spacer(20, 20)))
        data.append(KeepTogether(content_header))
        data.append(KeepTogether(Spacer(7, 7)))
        data.append(KeepTogether(remaining_table))
    lab_test = '''<para><font size=12>
                    สำหรับเจ้าหน้าที่<br/>
                    Lab No. : __________________________________<br/>
                    สภาพตัวอย่าง : O ปกติ<br/>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; O ไม่ปกติ<br/>
                    </font></para>'''

    lab_test_table = Table([[Paragraph(lab_test, style=detail_style)]], colWidths=[530])

    lab_test_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    if service_request.lab == 'bacteria' or service_request.lab == 'virology':
        if remaining_text:
            data.append(KeepTogether(lab_test_table))
        else:
            data.append(KeepTogether(lab_test_table))

    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    buffer.seek(0)
    return buffer


@service_admin.route('/request/pdf/<int:request_id>', methods=['GET'])
def export_request_pdf(request_id):
    service_request = ServiceRequest.query.get(request_id)
    buffer = generate_request_pdf(service_request)
    return send_file(buffer, download_name='Request_form.pdf', as_attachment=True)


@service_admin.route('/result/index')
@login_required
def result_index():
    return render_template('service_admin/result_index.html')


@service_admin.route('/api/result/index')
def get_results():
    query = ServiceResult.query.filter_by(admin_id=current_user.id)
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ServiceResult.lab_no.contains(search))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        if item.file_result:
            file_upload = drive.CreateFile({'id': item.url})
            file_upload.FetchMetadata()
            item_data['file'] = file_upload.get('embedLink')
        else:
            item_data['file'] = None
        data.append(item_data)
    return jsonify({'data': data,
                    'recordFiltered': total_filtered,
                    'recordTotal': records_total,
                    'draw': request.args.get('draw', type=int)
                    })


@service_admin.route('/result/add', methods=['GET', 'POST'])
@service_admin.route('/result/edit/<int:result_id>', methods=['GET', 'POST'])
def create_result(result_id=None):
    if result_id:
        result = ServiceResult.query.get(result_id)
        form = ServiceResultForm(obj=result)
    else:
        form = ServiceResultForm()
    if form.validate_on_submit():
        if result_id is None:
            result = ServiceResult()
        form.populate_obj(result)
        file = form.file_upload.data
        result.admin_id = current_user.id
        if result_id:
            result.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            result.released_at = arrow.now('Asia/Bangkok').datetime
        result.status = 'รอรับทราบใบรายงานผล'
        result.request.status = 'รอรับทราบใบรายงานผล'
        drive = initialize_gdrive()
        if file:
            file_name = secure_filename(file.filename)
            file.save(file_name)
            file_drive = drive.CreateFile({'title': file_name,
                                           'parents': [{'id': FOLDER_ID, "kind": "drive#fileLink"}]})
            file_drive.SetContentFile(file_name)
            file_drive.Upload()
            permission = file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
            result.url = file_drive['id']
            result.file_result = file_name
        db.session.add(result)
        db.session.commit()
        scheme = 'http' if current_app.debug else 'https'
        service_request = ServiceRequest.query.get(result.request_id)
        customer_email = service_request.customer_account.customer_info.email
        result_link = url_for('academic_services.result_index', _external=True, _scheme=scheme)
        if result_id:
            title = 'แจ้งแก้ไขและออกใบรายงานผลการทดสอบใหม่'
            message = f'''ทางหน่วยงานได้แก้ไขและทำการออกใบรายงานผลการทดสอบใหม่เป็นที่เรียบร้อยแล้ว ท่านสามมารถตรวจสอบได้ที่ลิ้งค์ข้างล่างนี้\n'''
            message += f'''{result_link}'''
            send_mail([customer_email], title, message)
            flash('แก้ไขรายงานผลการทดสอบเรียบร้อย', 'success')
        else:
            title = 'แจ้งออกใบรายงานผลการทดสอบ'
            message = f'''ทางหน่วยงานได้ทำการออกใบรายงานผลการทดสอบเป็นที่เรียบร้อยแล้ว ท่านสามมารถตรวจสอบได้ที่ลิ้งค์ข้างล่างนี้\n'''
            message += f'''{result_link}'''
            send_mail([customer_email], title, message)
            flash('สร้างรายงานผลการทดสอบเรียบร้อย', 'success')
        return redirect(url_for('service_admin.result_index'))
    return render_template('service_admin/create_result.html', form=form, result_id=result_id)


@service_admin.route('/payment/index')
@login_required
def payment_index():
    return render_template('service_admin/payment_index.html')


@service_admin.route('/api/payment/index')
def get_payments():
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    labs = []
    sub_labs = []
    for a in admin:
        if a.lab:
            labs.append(a.lab.code)
        else:
            sub_labs.append(a.sub_lab.code)
    query = ServiceRequest.query.filter(
        and_(
            or_(ServiceRequest.admin.has(id=current_user.id),ServiceRequest.lab.in_(labs))),
        or_(
            ServiceRequest.status == 'ยังไม่ชำระเงิน',
            ServiceRequest.status == 'รอเจ้าหน้าที่ตรวจสอบการชำระเงิน',
            ServiceRequest.status == 'ชำระเงินไม่สำเร็จ',
            ServiceRequest.status == 'ชำระเงินสำเร็จ'
        )
    ) \
        if labs else ServiceRequest.query.filter(
        and_(
            or_(ServiceRequest.admin.has(id=current_user.id), ServiceRequest.lab.in_(sub_labs))),
        or_(
            ServiceRequest.status == 'ยังไม่ชำระเงิน',
            ServiceRequest.status == 'รอเจ้าหน้าที่ตรวจสอบการชำระเงิน',
            ServiceRequest.status == 'ชำระเงินไม่สำเร็จ',
            ServiceRequest.status == 'ชำระเงินสำเร็จ'
        )
    )
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ServiceRequest.request_no.contains(search))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        if item.payment and item.payment.url:
            file_upload = drive.CreateFile({'id': item.payment.url})
            file_upload.FetchMetadata()
            item_data['file'] = f"https://drive.google.com/uc?export=download&id={item.payment.url}"
        else:
            item_data['file'] = None
        data.append(item_data)
    return jsonify({'data': data,
                    'recordFiltered': total_filtered,
                    'recordTotal': records_total,
                    'draw': request.args.get('draw', type=int)
                    })


@service_admin.route('/payment/confirm/<int:request_id>', methods=['GET'])
def confirm_payment(request_id):
    service_request = ServiceRequest.query.get(request_id)
    service_request.status = 'ชำระเงินสำเร็จ'
    service_request.payment.status = 'ชำระเงินสำเร็จ'
    service_request.payment.admin_id = current_user.id
    db.session.add(service_request)
    db.session.commit()
    flash('อัพเดตสถานะสำเร็จ', 'success')
    return redirect(url_for('service_admin.payment_index'))


@service_admin.route('/payment/cancel/<int:request_id>', methods=['GET'])
def cancel_payment(request_id):
    service_request = ServiceRequest.query.get(request_id)
    service_request.status = 'ชำระเงินไม่สำเร็จ'
    service_request.payment.bill = None
    service_request.payment.url = None
    service_request.payment.status = 'ชำระเงินไม่สำเร็จ'
    service_request.payment.admin_id = current_user.id
    db.session.add(service_request)
    db.session.commit()
    flash('อัพเดตสถานะสำเร็จ', 'success')
    return redirect(url_for('service_admin.payment_index'))


@service_admin.route('/payment/view/<int:payment_id>')
def view_payment(payment_id):
    payment = ServicePayment.query.get(payment_id)
    return render_template('service_admin/view_payment.html', payment=payment)


@service_admin.route('/lab/index/<int:customer_id>')
@login_required
def lab_index(customer_id):
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id)
    return  render_template('service_admin/lab_index.html', customer_id=customer_id,
                            admin=admin)


@service_admin.route('/sample/add/<int:request_id>', methods=['GET', 'POST'])
def confirm_receipt_of_sample(request_id):
    service_request = ServiceRequest.query.get(request_id)
    sample = ServiceSampleAppointment.query.get(service_request.appointment_id)
    form = ServiceSampleAppointmentForm(obj=sample)
    if form.validate_on_submit():
        form.populate_obj(sample)
        sample.received_date = arrow.get(form.received_date.data, 'Asia/Bangkok').datetime
        sample.recipient_id = current_user.id
        service_request.status = 'ได้รับตัวอย่าง/รอดำเนินการทดสอบ'
        db.session.add(sample)
        db.session.commit()
        flash('ยืนยันสำเร็จ', 'success')
        return redirect(url_for('service_admin.request_index'))
    return render_template('service_admin/confirm_receipt_of_sample.html', form=form)


@service_admin.route('/customer/address/add/<int:customer_id>', methods=['GET', 'POST'])
@service_admin.route('/customer/address/edit/<int:customer_id>/<int:address_id>', methods=['GET', 'POST'])
def create_customer_address(customer_id=None, address_id=None):
    if address_id:
        address = ServiceCustomerAddress.query.get(address_id)
        form = ServiceCustomerAddressForm(obj=address)
    else:
        form = ServiceCustomerAddressForm()
        address = ServiceCustomerAddress.query.all()
    if form.validate_on_submit():
        if address_id is None:
            address = ServiceCustomerAddress()
        form.populate_obj(address)
        if address_id is None:
            address.customer_id = customer_id
        print('f', not form.type.data)
        if form.type.data:
            if form.type.data == 'ที่อยู่จัดส่งเอกสาร':
                address.address_type = 'customer'
            else:
                address.address_type = 'quotation'
            db.session.add(address)
            db.session.commit()
            flash('บันทึกข้อมูลสำเร็จ', 'success')
            return redirect(url_for('service_admin.address_index', customer_id=customer_id))
        elif form.type.data == False:
            flash('กรุณาเลือกประเภทที่อยู่', 'danger')
    return render_template('service_admin/create_customer_address.html', form=form, customer_id=customer_id,
                           address_id=address_id)


@service_admin.route('/customer/adress/delete/<int:address_id>', methods=['GET', 'DELETE'])
def delete_customer_address(address_id):
    customer_id = request.args.get('customer_id')
    address = ServiceCustomerAddress.query.get(address_id)
    db.session.delete(address)
    db.session.commit()
    return redirect(url_for('service_admin.address_index', customer_id=customer_id))


@service_admin.route('/customer/address/index/<int:customer_id>')
def address_index(customer_id):
    customer = ServiceCustomerInfo.query.get(customer_id)
    addresses = ServiceCustomerAddress.query.filter_by(customer_id=customer_id)
    return render_template('service_admin/address_index.html', addresses=addresses, customer_id=customer_id,
                           customer=customer)


@service_admin.route('/invoice/index')
@login_required
def invoice_index():
    return render_template('service_admin/invoice_index.html')


@service_admin.route('/api/invoice/index')
def get_invoices():
    query = ServiceInvoice.query.filter_by(admin_id=current_user.id)
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ServiceInvoice.invoice_no.contains(search))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        data.append(item_data)
    return jsonify({'data': data,
                    'recordFiltered': total_filtered,
                    'recordTotal': records_total,
                    'draw': request.args.get('draw', type=int)
                    })


@service_admin.route('/invoice/add', methods=['GET', 'POST'])
@service_admin.route('/invoice/edit/<int:invoice_id>', methods=['GET', 'POST'])
def create_invoice(invoice_id=None):
    if invoice_id:
        invoice = ServiceInvoice.query.get(invoice_id)
        form = ServiceInvoiceForm(obj=invoice)
    else:
        form = ServiceInvoiceForm()
    if form.validate_on_submit():
        if invoice_id is None:
            invoice = ServiceInvoice()
        form.populate_obj(invoice)
        if invoice_id is None:
            invoice.admin_id = current_user.id
        invoice.created_at = arrow.now('Asia/Bangkok').datetime
        invoice.status = 'รอเจ้าหน้าที่อนุมัติใบแจ้งหนี้'
        invoice.request.status = 'รอเจ้าหน้าที่อนุมัติใบแจ้งหนี้'
        db.session.add(invoice)
        db.session.commit()
        flash('สร้างใบแจ้งหนี้เรียบร้อย', 'success')
        return redirect(url_for('service_admin.invoice_index'))
    return render_template('service_admin/create_invoice.html', form=form, invoice_id=invoice_id)


@service_admin.route('/invoice/view/<int:invoice_id>', methods=['GET'])
@login_required
def view_invoice(invoice_id):
    invoice = ServiceInvoice.query.get(invoice_id)
    admin_lab = ServiceAdmin.query.filter_by(admin_id=current_user.id)
    admin = any(a.is_supervisor for a in admin_lab)
    return render_template('service_admin/view_invoice.html', invoice=invoice, admin=admin)


def generate_invoice_pdf(invoice, sign=False, cancel=False):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 60, 60)

    sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    lab = ServiceLab.query.filter_by(code=invoice.request.lab).first()
    sub_lab = ServiceSubLab.query.filter_by(code=invoice.request.lab).first()
    if sub_lab:
        sheet = wks.worksheet(sub_lab.sheet)
    else:
        sheet = wks.worksheet(lab.sheet)
    df = pandas.DataFrame(sheet.get_all_records())
    data = invoice.request.data
    form = create_request_form(df)(**data)

    def all_page_setup(canvas, doc):
        canvas.saveState()
        logo_image = ImageReader('app/static/img/mu-watermark.png')
        canvas.drawImage(logo_image, 140, 265, mask='auto')
        canvas.restoreState()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer,
                            rightMargin=20,
                            leftMargin=20,
                            topMargin=10,
                            bottomMargin=10,
                            )
    data = []

    affiliation = '''<para align=center><font size=10>
                คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>
                FACULTY OF MEDICAL TECHNOLOGY, MAHIDOL UNIVERSITY
                </font></para>
                '''

    lab_address = '''<para><font size=12>
                        {address}
                        </font></para>'''.format(address=lab.address if lab else sub_lab.address)

    invoice_info = '''<br/><br/><font size=10>
                เลขที่/No. {invoice_no}<br/>
                วันที่/Date {issued_date}
                </font>
                '''

    invoice_no = invoice.invoice_no
    issued_date = arrow.get(invoice.created_at.astimezone(localtz)).format(fmt='DD MMMM YYYY', locale='th-th')
    invoice_info_ori = invoice_info.format(invoice_no=invoice_no,
                                           issued_date=issued_date
                                           )

    header_content_ori = [[Paragraph(lab_address, style=style_sheet['ThaiStyle']),
                           [logo, Paragraph(affiliation, style=style_sheet['ThaiStyle'])],
                           [],
                           Paragraph(invoice_info_ori, style=style_sheet['ThaiStyle'])]]

    header_styles = TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ])

    header_ori = Table(header_content_ori, colWidths=[150, 200, 50, 100])

    header_ori.hAlign = 'CENTER'
    header_ori.setStyle(header_styles)
    for address in invoice.request.customer.customer_info.addresses:
        if address.address_type == 'quotation':
            customer = '''<para><font size=11>
                        ลูกค้า/Customer {customer}<br/>
                        ที่อยู่/Address {address}<br/>
                        เลขประจำตัวผู้เสียภาษี/Taxpayer identification no {taxpayer_identification_no}
                        </font></para>
                        '''.format(customer=address.name,
                                   address=address.address,
                                   phone_number=address.phone_number,
                                   taxpayer_identification_no=invoice.request.customer.customer_info.taxpayer_identification_no)

    customer_table = Table([[Paragraph(customer, style=style_sheet['ThaiStyle'])]], colWidths=[540, 280])

    customer_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP')]))

    items = [[Paragraph('<font size=10>ลำดับ / No.</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>รายการ / Description</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>จำนวน / Quality</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>ราคาหน่วย(บาท) / Unit Price</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>ราคารวม(บาท) / Total</font>', style=style_sheet['ThaiStyleCenter']),
              ]]

    n = len(items)
    for i in range(18 - n):
        items.append([
            Paragraph('<font size=12>&nbsp; </font>', style=style_sheet['ThaiStyle']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
        ])
    items.append([
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>รวมทั้งสิ้น</font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber'])
    ])
    item_table = Table(items, colWidths=[50, 250, 75, 75])
    item_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, 0), 0.25, colors.black),
        ('BOX', (0, -1), (-1, -1), 0.25, colors.black),
        ('BOX', (0, 0), (0, -1), 0.25, colors.black),
        ('BOX', (1, 0), (1, -1), 0.25, colors.black),
        ('BOX', (2, 0), (2, -1), 0.25, colors.black),
        ('BOX', (3, 0), (3, -1), 0.25, colors.black),
        ('BOX', (4, 0), (4, -1), 0.25, colors.black),
        ('SPAN', (0, -1), (1, -1)),
        ('SPAN', (2, -1), (3, -1)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, -2), (-1, -2), 10),
    ]))

    text_info = Paragraph('<br/><font size=12>ขอแสดงความนับถือ<br/></font>',style=style_sheet['ThaiStyle'])
    text = [[text_info, Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
    text_table = Table(text, colWidths=[0, 155, 155])
    text_table.hAlign = 'RIGHT'
    sign_info = Paragraph('<font size=12>(&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
                          '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
                          '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
                          '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)</font>', style=style_sheet['ThaiStyle'])
    sign = [[sign_info, Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
    sign_table = Table(sign, colWidths=[0, 200, 200])
    sign_table.hAlign = 'RIGHT'

    data.append(KeepTogether(Spacer(7, 7)))
    data.append(KeepTogether(header_ori))
    data.append(KeepTogether(Paragraph('<para align=center><font size=16>ใบแจ้งหนี้ / INVOICE<br/><br/></font></para>',
                                       style=style_sheet['ThaiStyle'])))
    data.append(KeepTogether(Spacer(1, 12)))
    data.append(KeepTogether(customer_table))
    data.append(KeepTogether(Spacer(1, 16)))
    data.append(KeepTogether(item_table))
    data.append(KeepTogether(Spacer(1, 16)))
    data.append(KeepTogether(text_table))
    data.append(KeepTogether(Spacer(1, 25)))
    data.append(KeepTogether(sign_table))

    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    buffer.seek(0)
    return buffer


@service_admin.route('/invoice/pdf/<int:invoice_id>', methods=['GET'])
def export_invoice_pdf(invoice_id):
    invoice = ServiceInvoice.query.get(invoice_id)
    buffer = generate_invoice_pdf(invoice)
    return send_file(buffer, download_name='Invoice.pdf', as_attachment=True)


@service_admin.route('/invoice/approve/<int:invoice_id>', methods=['GET', 'POST'])
def approve_invoice(invoice_id):
    admin = request.args.get('admin')
    invoice = ServiceInvoice.query.get(invoice_id)
    if admin:
        invoice.status = 'ยังไม่ชำระเงิน'
        invoice.request.status = 'ยังไม่ชำระเงิน'
        payment = ServicePayment(amount_paid=invoice.amount_due)
        db.session.add(payment)
    else:
        invoice.status = 'รอหัวหน้าห้องปฏิบัติการอนุมัติใบแจ้งหนี้'
        invoice.request.status = 'รอหัวหน้าห้องปฏิบัติการอนุมัติใบแจ้งหนี้'
    db.session.add(invoice)
    db.session.commit()
    return render_template('service_admin/invoice_index.html')