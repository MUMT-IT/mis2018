import itertools
import os
from collections import Counter

import arrow
import requests
import pandas
from io import BytesIO

from _decimal import Decimal
from bahttext import bahttext
from pytz import timezone
from datetime import datetime, date

from sqlalchemy.orm import make_transient
from wtforms import FormField, FieldList
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
from app.auth.views import line_bot_api
from app.academic_services.forms import create_request_form, ServiceRequestForm
from app.models import Org
from app.service_admin import service_admin
from app.academic_services.models import *
from flask import render_template, flash, redirect, url_for, request, session, make_response, jsonify, current_app, \
    send_file
from flask_login import current_user, login_required
from sqlalchemy import or_, and_
from app.service_admin.forms import (ServiceCustomerInfoForm, crate_address_form, create_result_form,
                                     create_quotation_item_form, ServiceInvoiceForm, ServiceQuotationForm,
                                     ServiceSampleForm)
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
style_sheet.add(ParagraphStyle(name='ThaiStyleRight', fontName='Sarabun', alignment=TA_RIGHT))

gauth = GoogleAuth()
keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
scopes = ['https://www.googleapis.com/auth/drive']
gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile, scopes)
drive = GoogleDrive(gauth)

FOLDER_ID = '1832el0EAqQ6NVz2wB7Ade6wRe-PsHQsu'

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile, scopes)
    return GoogleDrive(gauth)


def form_data(data):
    if isinstance(data, dict):
        return {k: form_data(v) for k, v in data.items() if k != "csrf_token" and k != 'submit'}
    elif isinstance(data, list):
        return [form_data(item) for item in data]
    elif isinstance(data, (date)):
        return data.isoformat()
    return data


def request_data(service_request):
    sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab).first()
    sheet = wks.worksheet(sub_lab.sheet)
    df = pandas.DataFrame(sheet.get_all_records())
    data = service_request.data
    form = create_request_form(df)(**data)
    values = []
    table_rows = []
    set_fields = set()
    current_row = {}
    for fn in df.fieldGroup:
        for field in getattr(form, fn):
            if field.type == 'FieldList':
                for fd in field:
                    for f in fd:
                        if f.data != None and f.data != '' and f.data != [] and f.label not in set_fields:
                            set_fields.add(f.label)
                            label = f.label.text
                            value = ', '.join(f.data) if f.type == 'CheckboxField' else f.data
                            if label.startswith("เชื้อ"):
                                if current_row:
                                    table_rows.append(current_row)
                                    current_row = {}
                                current_row["เชื้อ"] = value
                            elif "อัตราส่วน" in label:
                                current_row["อัตราส่วนเจือจาง"] = value
                            elif "ระยะห่าง" in label:
                                current_row["ระยะห่างในการฉีดพ่น"] = value
                            elif "ระยะเวลาในการฉีดพ่น" in label or "ระยะเวลาฉีดพ่น" in label:
                                current_row["ระยะเวลาฉีดพ่น"] = value
                            elif "สัมผัสกับเชื้อ" in label:
                                current_row["ระยะเวลาสัมผัสเชื้อ"] = value
                            else:
                                values.append(f"{label} : {value}")
            else:
                if field.data != None and field.data != '' and field.data != [] and field.label not in set_fields:
                    set_fields.add(field.label)
                    set_fields.add(field.label)
                    label = field.label.text
                    value = ', '.join(field.data) if field.type == 'CheckboxField' else field.data
                    if label.startswith("เชื้อ"):
                        if current_row:
                            table_rows.append(current_row)
                            current_row = {}
                        current_row["เชื้อ"] = value
                    elif "อัตราส่วน" in label:
                        current_row["อัตราส่วนเจือจาง"] = value
                    elif "ระยะห่าง" in label:
                        current_row["ระยะห่างในการฉีดพ่น"] = value
                    elif "ระยะเวลาในการฉีดพ่น" in label or "ระยะเวลาฉีดพ่น" in label:
                        current_row["ระยะเวลาฉีดพ่น"] = value
                    elif "สัมผัสกับเชื้อ" in label:
                        current_row["ระยะเวลาสัมผัสเชื้อ"] = value
                    else:
                        values.append(f"{label} : {value}")
    if current_row:
        table_rows.append(current_row)
    table_keys = []
    for row in table_rows:
        for key in row:
            if key not in table_keys:
                table_keys.append(key)

    return {
        "value": values,
        "table_rows": table_rows,
        "table_keys": table_keys
    }


def walk_form_fields(field, quote_column_names, cols=set(), keys=[], values='', depth=''):
    field_name = field.name.split('-')[-1]
    cols.add(field_name)
    if isinstance(field, FormField) or isinstance(field, FieldList):
        for f in field:
            field_name = f.name.split('-')[-1]
            cols.add(field_name)
            if field_name == 'csrf_token' or field_name == 'submit':
                continue
            if isinstance(f, FormField) or isinstance(f, FieldList):
                walk_form_fields(f, quote_column_names, cols, keys, values, depth + '-')
            else:
                if field_name in quote_column_names:
                    if isinstance(f.data, list):
                        for item in f.data:
                            keys.append((field_name, values + str(item)))
                    else:
                        keys.append((field_name, values + str(f.data)))
    else:
        if field.name in quote_column_names:
            if field.name != 'csrf_token' or field.name != 'submit':
                if isinstance(field.data, list):
                    for item in field.data:
                        keys.append((field.name, values + str(item)))
                else:
                    keys.append((field.name, values + str(field.data)))
    return keys


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


@service_admin.route('/request/index')
@login_required
def request_index():
    return render_template('service_admin/request_index.html')


@service_admin.route('/api/request/index')
def get_requests():
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    sub_labs = []
    for a in admin:
        sub_labs.append(a.sub_lab.code)
    query = ServiceRequest.query.filter(
        or_(ServiceRequest.admin.has(id=current_user.id), ServiceRequest.lab.in_(sub_labs)))
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
    sub_lab = ServiceSubLab.query.filter_by(code=code)
    return render_template('service_admin/create_request.html', code=code, request_id=request_id,
                           customer_id=customer_id, sub_lab=sub_lab)


@service_admin.route('/api/request/form', methods=['GET'])
def get_request_form():
    code = request.args.get('code')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    sub_lab = ServiceSubLab.query.filter_by(code=code).first() if code else ServiceSubLab.query.filter_by(
        code=service_request.lab).first()
    sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet(sub_lab.sheet)
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


@service_admin.route('/submit-request/add/<int:customer_id>', methods=['POST'])
@service_admin.route('/submit-request/edit/<int:request_id>', methods=['POST'])
def submit_request(request_id=None, customer_id=None):
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab).first()
    else:
        code = request.args.get('code')
        sub_lab = ServiceSubLab.query.filter_by(code=code).first()
        request_no = ServiceNumberID.get_number('RQ', db,
                                                lab=sub_lab.lab.code if sub_lab and sub_lab.lab.code == 'protein' else code)
    sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet(sub_lab.sheet)
    df = pandas.DataFrame(sheet.get_all_records())
    form = create_request_form(df)(request.form)
    products = []
    for _, values in form.data.items():
        if isinstance(values, dict):
            if 'product_name' in values:
                products.append(values['product_name'])
            elif 'ware_name' in values:
                products.append(values['ware_name'])
            elif 'sample_name' in values:
                products.append(values['sample_name'])
            elif 'รายการ' in values:
                for v in values['รายการ']:
                    if 'sample_name' in v:
                        products.append(v['sample_name'])
            elif 'test_sample_of_trace' in values:
                products.append(values['test_sample_of_trace'])
            elif 'test_sample_of_heavy' in values:
                products.append(values['test_sample_of_heavy'])
    if request_id:
        service_request.data = form_data(form.data)
        service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        service_request.product = products
    else:
        service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id,
                                         created_at=arrow.now('Asia/Bangkok').datetime, lab=code,
                                         request_no=request_no.number,
                                         product=products, data=form_data(form.data))
        request_no.count += 1
    db.session.add(service_request)
    db.session.commit()
    return redirect(url_for('service_admin.create_report_language', request_id=service_request.id,
                            sub_lab=sub_lab.sub_lab))


@service_admin.route('/request/report_language/add/<int:request_id>', methods=['GET', 'POST'])
@login_required
def create_report_language(request_id):
    sub_lab = request.args.get('sub_lab')
    service_request = ServiceRequest.query.get(request_id)
    form = ServiceRequestForm(obj=service_request)
    if request.method == 'GET':
        if sub_lab == 'บริการตรวจวิเคราะห์ผลิตภัณฑ์ในการฆ่าเชื้อไวรัส':
            form.eng_language.data = True
        else:
            form.thai_language.data = True
    if form.validate_on_submit():
        form.populate_obj(service_request)
        service_request.status = 'อยู่ระหว่างการจัดทำใบเสนอราคา'
        db.session.add(service_request)
        db.session.commit()
        return redirect(url_for('service_admin.create_customer_detail', request_id=request_id, sub_lab=sub_lab))
    return render_template('service_admin/create_report_language.html', form=form, sub_lab=sub_lab,
                           request_id=request_id)


@service_admin.route('/request/customer/detail/add/<int:request_id>', methods=['GET', 'POST'])
@login_required
def create_customer_detail(request_id):
    sub_lab = request.args.get('sub_lab')
    service_request = ServiceRequest.query.get(request_id)
    customer_id = service_request.customer.customer_info_id
    if customer_id:
        customer = ServiceCustomerInfo.query.get(customer_id)
        form = ServiceCustomerInfoForm(obj=customer)
    if form.validate_on_submit():
        form.populate_obj(customer)
        db.session.add(customer)
        if request.form.getlist('quotation_address'):
            for quotation_address_id in request.form.getlist('quotation_address'):
                service_request.quotation_address_id = int(quotation_address_id)
                db.session.add(service_request)
                db.session.commit()
        if request.form.getlist('document_address'):
            for document_address_id in request.form.getlist('document_address'):
                service_request.document_address_id = int(document_address_id)
                db.session.add(service_request)
                db.session.commit()
        service_request.status = 'รอลูกค้าส่งคำขอใบเสนอราคา'
        db.session.add(service_request)
        db.session.commit()
        return redirect(url_for('service_admin.view_request', request_id=request_id))
    return render_template('service_admin/create_customer_detail.html', form=form, customer=customer,
                           request_id=request_id, sub_lab=sub_lab, customer_id=customer_id)


@service_admin.route('/request/customer/address/add/<int:customer_id>', methods=['GET', 'POST'])
def add_customer_address(customer_id):
    type = request.args.get('type')
    customer = ServiceCustomerInfo.query.get(customer_id)
    ServiceCustomerAddressForm = crate_address_form(use_type=False)
    form = ServiceCustomerAddressForm()
    if not form.taxpayer_identification_no.data:
        form.taxpayer_identification_no.data = customer.taxpayer_identification_no
    if form.validate_on_submit():
        address = ServiceCustomerAddress()
        form.populate_obj(address)
        address.customer_id = customer_id
        address.address_type = type
        db.session.add(address)
        db.session.commit()
        flash('เพิ่มข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('service_admin/modal/add_customer_address_modal.html', type=type, form=form,
                           customer_id=customer_id, customer=customer)


@service_admin.route('/customer/address/submit/<int:address_id>', methods=['GET', 'POST'])
def submit_same_address(address_id):
    customer_id = request.args.get('customer_id')
    if request.method == 'POST':
        address = ServiceCustomerAddress.query.get(address_id)
        db.session.expunge(address)
        make_transient(address)
        address.name = address.name
        address.address_type = 'document'
        address.taxpayer_identification_no = address.taxpayer_identification_no if address.taxpayer_identification_no else None
        address.address = address.address
        address.phone_number = address.phone_number
        address.province_id = address.province_id
        address.district_id = address.district_id
        address.subdistrict_id =address.subdistrict_id
        address.zipcode = address.zipcode
        address.remark = address.remark if address.remark else None
        address.customer_id = customer_id
        address.id = None
        db.session.add(address)
        db.session.commit()
        flash('บันทึกข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@service_admin.route('/sample/index')
@login_required
def sample_index():
    tab = request.args.get('tab')
    return render_template('service_admin/sample_index.html', tab=tab)


@service_admin.route('/api/sample/index')
def get_samples():
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    sub_labs = []
    for a in admin:
        sub_labs.append(a.sub_lab.code)
    query = ServiceSample.query.filter(ServiceSample.request.has(or_(ServiceRequest.admin.has(id=current_user.id),
                                                                     ServiceRequest.lab.in_(sub_labs)
                                                                     )
                                                                 )
                                       )
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ServiceSample.location.contains(search))
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


@service_admin.route('/sample/verification/add/<int:sample_id>', methods=['GET', 'POST'])
def sample_verification(sample_id):
    tab = request.args.get('tab')
    sample = ServiceSample.query.get(sample_id)
    form = ServiceSampleForm(obj=sample)
    if form.validate_on_submit():
        form.populate_obj(sample)
        sample.received_at = arrow.now('Asia/Bangkok').datetime
        sample.receiver_id = current_user.id
        sample.request.status = 'ได้รับตัวอย่าง'
        db.session.add(sample)
        db.session.commit()
        flash('บันทึกข้อมูลสำเร็จ', 'success')
        return redirect(url_for('service_admin.sample_index', tab=tab))
    return render_template('service_admin/sample_verification_form.html', form=form, tab=tab)


@service_admin.route('/sample/process/<int:sample_id>', methods=['GET'])
def process_sample(sample_id):
    tab = request.args.get('tab')
    sample = ServiceSample.query.get(sample_id)
    sample.started_at = arrow.now('Asia/Bangkok').datetime
    sample.starter_id = current_user.id
    sample.request.status = 'กำลังดำเนินการทดสอบ'
    db.session.add(sample)
    db.session.commit()
    flash('อัพเดตสถานะสำเร็จ', 'success')
    return redirect(url_for('service_admin.sample_index', tab=tab))


@service_admin.route('/sample/confirm/<int:sample_id>', methods=['GET'])
def confirm_sample(sample_id):
    tab = request.args.get('tab')
    sample = ServiceSample.query.get(sample_id)
    sample.finished_at = arrow.now('Asia/Bangkok').datetime
    sample.finish_id = current_user.id
    sample.request.status = 'ดำเนินการทดสอบเสร็จสิ้น'
    db.session.add(sample)
    db.session.commit()
    flash('อัพเดตสถานะสำเร็จ', 'success')
    return redirect(url_for('service_admin.sample_index', tab=tab))


@service_admin.route('/request/view/<int:request_id>')
@login_required
def view_request(request_id=None):
    service_request = ServiceRequest.query.get(request_id)
    sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab)
    datas = request_data(service_request)
    return render_template('service_admin/view_request.html', service_request=service_request,
                           sub_lab=sub_lab, datas=datas)


def generate_request_pdf(service_request, sign=False, cancel=False):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 40, 40)

    sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab).first()
    sheet = wks.worksheet(sub_lab.sheet)
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
                                values.append(f"{f.label.text} : {', '.join(f.data)}")
                            elif f.label.text == 'ปริมาณสารสำคัญที่ออกฤทธ์' or f.label.text == 'สารสำคัญที่ออกฤทธิ์':
                                items = [item.strip() for item in str(f.data).split(',')]
                                values.append(f"{f.label.text}")
                                for item in items:
                                    values.append(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- {item}")
                            else:
                                values.append(f"{f.label.text} : {f.data}")
            else:
                if field.data != None and field.data != '' and field.data != [] and field.label not in set_fields:
                    set_fields.add(field.label)
                    if field.type == 'CheckboxField':
                        values.append(f"{field.label.text} : {', '.join(field.data)}")
                    elif field.label.text == 'ปริมาณสารสำคัญที่ออกฤทธ์' or field.label.text == 'สารสำคัญที่ออกฤทธิ์':
                        items = [item.strip() for item in str(field.data).split(',')]
                        values.append(f"{field.label.text}")
                        for item in items:
                            values.append(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- {item}")
                    else:
                        values.append(f"{field.label.text} : {field.data}")
    reports = []
    if service_request.thai_language:
        reports.append("ใบรายงานผลภาษาไทย")
    if service_request.thai_copy_language:
        reports.append("สำเนาใบรายงานผลภาษาไทย")
    if service_request.eng_language:
        reports.append("ใบรายงานผลภาษาอังกฤษ")
    if service_request.eng_copy_language:
        reports.append("สำเนาใบรายงานผลภาษาอังกฤษ")
    if reports:
        values.append("ใบรายงานผล : " + ", ".join(reports))
        
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
                    </font></para>'''.format(address=sub_lab.address)

    lab_table = Table([[logo, Paragraph(lab_address, style=style_sheet['ThaiStyle'])]], colWidths=[45, 330])

    lab_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    staff_only = '''<para><font size=12>
                สำหรับเจ้าหน้าที่ / Staff only<br/>
                เลขที่ใบคำขอ &nbsp;&nbsp;_____________<br/>
                วันที่รับตัวอย่าง _____________<br/>
                วันที่รายงานผล _____________<br/>
                </font></para>'''

    staff_table = Table([[Paragraph(staff_only, style=style_sheet['ThaiStyle'])]], colWidths=[150])

    combined_table = Table(
        [[lab_table, staff_table]],
        colWidths=[370, 159]
    )

    combined_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (0, 0), 0.5, colors.grey),
        ('BOX', (1, 0), (1, 0), 0.5, colors.grey),
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

    district_title = 'เขต' if service_request.document_address.province.name == 'กรุงเทพมหานคร' else 'อำเภอ'
    subdistrict_title = 'แขวง' if service_request.document_address.province.name == 'กรุงเทพมหานคร' else 'ตำบล'
    customer = '''<para>ข้อมูลผู้ส่งตรวจ<br/>
                        ผู้ส่ง : {customer}<br/>
                        ที่อยู่ : {address} {subdistrict_title}{subdistrict} {district_title}{district} จังหวัด{province} {zipcode}<br/>
                        เบอร์โทรศัพท์ : {phone_number}<br/>
                        อีเมล : {email}
                    </para>
                    '''.format(customer=service_request.customer.customer_info.cus_name,
                               address=service_request.document_address.address,
                               subdistrict_title=subdistrict_title,
                               subdistrict=service_request.document_address.subdistrict,
                               district_title=district_title,
                               district=service_request.document_address.district,
                               province=service_request.document_address.province,
                               zipcode=service_request.document_address.zipcode,
                               phone_number=service_request.customer.customer_info.phone_number,
                               email=service_request.customer.email)

    customer_table = Table([[Paragraph(customer, style=detail_style)]], colWidths=[530])

    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    data.append(KeepTogether(Spacer(7, 7)))
    data.append(
        KeepTogether(Paragraph('<para align=center><font size=18>ใบขอรับบริการ / REQUEST<br/><br/></font></para>',
                               style=style_sheet['ThaiStyle'])))
    data.append(KeepTogether(header))
    data.append(KeepTogether(Spacer(3, 3)))
    data.append(KeepTogether(combined_table))
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
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    sub_labs = []
    for a in admin:
        sub_labs.append(a.sub_lab.code)
    query = ServiceResult.query.filter(or_(ServiceResult.creator_id == current_user.id,
                                           ServiceResult.request.has(ServiceRequest.lab.in_(sub_labs))))
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
    request_id = request.args.get('request_id')
    ServiceResultForm = create_result_form(has_file=True)
    if result_id:
        result = ServiceResult.query.get(result_id)
        form = ServiceResultForm(obj=result)
    else:
        form = ServiceResultForm()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        form.request.data = service_request
    if form.validate_on_submit():
        if result_id is None:
            result = ServiceResult()
        form.populate_obj(result)
        file = form.file_upload.data
        result.creator_id = current_user.id
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
        customer_email = [customer_contact.email for customer_contact in service_request.customer.customer_contacts]
        result_link = url_for('academic_services.result_index', _external=True, _scheme=scheme)
        if result_id:
            title = 'แจ้งแก้ไขและออกใบรายงานผลการทดสอบใหม่'
            message = f'''เรียนท่านผู้ใช้บริการ\n\n'''
            message += f'''ทางหน่วยงานได้ดำเนินการแก้ไขและออกใบรายงานผลการทดสอบฉบับใหม่เรียบร้อยแล้ว ท่านสามารถตรวจสอบเอกสารฉบับล่าสุดได้จากลิงก์ด้านล่างนี้\n'''
            message += f'''{result_link}\n\n'''
            message += f'''หากมีข้อสอบถามหรือต้องการข้อมูลเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ที่ดูแล\n\n'''
            message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
            message += f'''ขอแสดงความนับถือ'''
            send_mail(customer_email, title, message)
            flash('ได้ทำการแก้ไขและออกใบรายงานผลใหม่เรียบร้อยแล้ว', 'success')
        else:
            title = 'แจ้งออกใบรายงานผลการทดสอบ'
            message = f'''เรียนท่านผู้ใช้บริการ\n\n'''
            message += f'''ทางหน่วยงานได้ดำเนินการออกใบรายงานผลการทดสอบเรียบร้อยแล้ว ท่านสามารถเข้าดูรายละเอียดได้จากลิงก์ด้านล่างนี้้\n'''
            message += f'''{result_link}\n\n'''
            message += f'''หากมีข้อสอบถามหรือต้องการข้อมูลเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ที่ดูแล\n\n'''
            message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
            message += f'''ขอแสดงความนับถือ'''
            send_mail(customer_email, title, message)
            flash('ดำเนินการออกใบรายงานผลการทดสอบเรียบร้อยแล้ว', 'success')
        return redirect(url_for('service_admin.result_index'))
    return render_template('service_admin/create_result.html', form=form, result_id=result_id)


@service_admin.route('/result/tracking_number/add/<int:result_id>', methods=['GET', 'POST'])
def add_tracking_number(result_id):
    result = ServiceResult.query.get(result_id)
    ServiceResultForm = create_result_form(has_file=None)
    form = ServiceResultForm(obj=result)
    if form.validate_on_submit():
        form.populate_obj(result)
        db.session.add(result)
        db.session.commit()
        flash('อัพเดตข้อมูลสำเร็จ', 'success')
        return redirect(url_for('service_admin.result_index'))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('service_admin/add_tracking_number_for_result.html', form=form, result_id=result_id)


@service_admin.route('/payment/index')
@login_required
def payment_index():
    return render_template('service_admin/payment_index.html')


@service_admin.route('/api/payment/index')
def get_payments():
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    sub_labs = []
    for a in admin:
        sub_labs.append(a.sub_lab.code)
    query = ServicePayment.query.filter(
        ServicePayment.invoice.has(
            ServiceInvoice.quotation.has(
                ServiceQuotation.request.has(
                    or_(
                        ServiceRequest.admin.has(id=current_user.id),
                        ServiceRequest.lab.in_(sub_labs)
                    )
                )
            )
        )
    )
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ServicePayment.status.contains(search))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        if item.url:
            file_upload = drive.CreateFile({'id': item.url})
            file_upload.FetchMetadata()
            item_data['file'] = f"https://drive.google.com/uc?export=download&id={item.url}"
        else:
            item_data['file'] = None
        data.append(item_data)
    return jsonify({'data': data,
                    'recordFiltered': total_filtered,
                    'recordTotal': records_total,
                    'draw': request.args.get('draw', type=int)
                    })


@service_admin.route('/payment/confirm/<int:payment_id>', methods=['GET'])
def confirm_payment(payment_id):
    payment = ServicePayment.query.get(payment_id)
    payment.status = 'ชำระเงินสำเร็จ'
    payment.invoice.quotation.request.status = 'ชำระเงินสำเร็จ'
    payment.invoice.quotation.request.is_paid = True
    payment.verifier_id = current_user.id
    db.session.add(payment)
    db.session.commit()
    flash('อัพเดตสถานะสำเร็จ', 'success')
    return redirect(url_for('service_admin.payment_index'))


@service_admin.route('/payment/cancel/<int:payment_id>', methods=['GET'])
def cancel_payment(payment_id):
    payment = ServicePayment.query.get(payment_id)
    payment.bill = None
    payment.url = None
    payment.status = 'ชำระเงินไม่สำเร็จ'
    payment.invoice.quotation.request.status = 'ชำระเงินไม่สำเร็จ'
    payment.verifier_id = current_user.id
    db.session.add(payment)
    db.session.commit()
    flash('อัพเดตสถานะสำเร็จ', 'success')
    return redirect(url_for('service_admin.payment_index'))


@service_admin.route('/lab/index/<int:customer_id>')
@login_required
def lab_index(customer_id):
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id)
    return render_template('service_admin/lab_index.html', customer_id=customer_id,
                           admin=admin)


@service_admin.route('/customer/address/add/<int:customer_id>', methods=['GET', 'POST'])
@service_admin.route('/customer/address/edit/<int:customer_id>/<int:address_id>', methods=['GET', 'POST'])
def create_customer_address(customer_id=None, address_id=None):
    customer = ServiceCustomerInfo.query.get(customer_id)
    if address_id:
        address = ServiceCustomerAddress.query.get(address_id)
        ServiceCustomerAddressForm = crate_address_form(use_type=True)
        form = ServiceCustomerAddressForm(obj=address)
        form.address_type.data = 'ที่อยู่จัดส่งเอกสาร' if address.address_type == 'document' else 'ที่อยู่ใบเสนอราคา/ใบแจ้งหนี้/ใบกำกับภาษี'
    else:
        ServiceCustomerAddressForm = crate_address_form(use_type=True)
        form = ServiceCustomerAddressForm()
        address = ServiceCustomerAddress.query.all()
    if not form.taxpayer_identification_no.data:
        form.taxpayer_identification_no.data = customer.taxpayer_identification_no
    if form.validate_on_submit():
        if address_id is None:
            address = ServiceCustomerAddress()
        form.populate_obj(address)
        if address_id is None:
            address.customer_id = customer_id
        if form.address_type.data:
            if form.address_type.data == 'ที่อยู่จัดส่งเอกสาร':
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
    sub_lab = ServiceSubLab.query.filter(
        or_(
            ServiceSubLab.approver_id == current_user.id,
            ServiceSubLab.signer_id == current_user.id,
            ServiceSubLab.admins.any(ServiceAdmin.admin_id == current_user.id)
        )
    )
    sub_labs = []
    for s in sub_lab:
        sub_labs.append(s.code)
    query = ServiceInvoice.query.filter(or_(ServiceInvoice.creator_id == current_user.id,
                                            ServiceInvoice.quotation.has(ServiceQuotation.request.has(
                                                ServiceRequest.lab.in_(sub_labs)))))
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


@service_admin.route('/invoice/add/<int:quotation_id>', methods=['GET', 'POST'])
def create_invoice(quotation_id):
    quotation = ServiceQuotation.query.get(quotation_id)
    sub_lab = ServiceSubLab.query.filter_by(code=quotation.request.lab).first()
    invoice_no = ServiceNumberID.get_number('IV', db, lab=sub_lab.lab.code if sub_lab and sub_lab.lab.code == 'protein' \
        else quotation.request.lab)
    invoice = ServiceInvoice(invoice_no=invoice_no.number, quotation_id=quotation_id, name=quotation.name,
                             address=quotation.address, taxpayer_identification_no=quotation.taxpayer_identification_no,
                             total_price=quotation.total_price, created_at=arrow.now('Asia/Bangkok').datetime, creator_id=current_user.id,
                             status='รอเจ้าหน้าที่ออกใบแจ้งหนี้')
    invoice_no.count += 1
    db.session.add(invoice)
    for quotation_item in quotation.quotation_items:
        invoice_item = ServiceInvoiceItem(invoice_id=invoice.id, item=quotation_item.item,
                                          quantity=quotation_item.quantity,
                                          unit_price=quotation_item.unit_price, total_price=quotation_item.total_price,
                                          discount=quotation_item.discount)
        db.session.add(invoice_item)
        db.session.commit()
    invoice.status = 'รอหัวหน้าห้องปฏิบัติการอนุมัติใบแจ้งหนี้'
    invoice.quotation.request.status = 'รอหัวหน้าห้องปฏิบัติการอนุมัติใบแจ้งหนี้'
    db.session.add(invoice)
    db.session.commit()
    scheme = 'http' if current_app.debug else 'https'
    admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=quotation.request.lab)).all()
    invoice_url = url_for("service_admin.view_invoice", invoice_id=invoice.id, _external=True, _scheme=scheme)
    title = 'แจ้งขออนุมัติใบแจ้งหนี้'
    message = f'''เรียนหัวหน้าห้องปฏิบัติการ\n\n'''
    message += f'''ใบแจ้งหนี้เลขที่ {invoice.invoice_no} ได้รับการตรวจสอบและอนุมัติโดยเจ้าหน้าที่เรียบร้อยแล้ว\n\n'''
    message += f'''กรุณาตรวจสอบและดำเนินการอนุมัติใบแจ้งหนี้ดังกล่าว\n\n'''
    message += f'''วันที่ออกใบแจ้งหนี้ : {invoice.created_at.astimezone(localtz).strftime('%d/%m/%Y')}\n\n'''
    message += f'''เวลาออกใบแจ้งหนี้ : {invoice.created_at.astimezone(localtz).strftime('%H:%M')}\n\n'''
    message += f'''ดูรายละเอียดเพิ่มเติมได้ที่ : {invoice_url}'''
    send_mail([admin.email for admin in admins if admin.is_supervisor], title, message)
    if not current_app.debug:
        msg = ('แจ้งขออนุมัติใบแจ้งหนี้เลขที่ {}' \
               '\nกรุณาตรวจสอบและดำเนินการอนุมัติใบแจ้งหนี้'.format(invoice.invoice_no))
        for a in admins:
            if a.is_supervisor:
                try:
                    line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                except LineBotApiError:
                    pass
    flash('สร้างใบแจ้งหนี้เรียบร้อย', 'success')
    return redirect(url_for('service_admin.view_invoice', invoice_id=invoice.id))


@service_admin.route('/invoice/view/<int:invoice_id>', methods=['GET'])
@login_required
def view_invoice(invoice_id):
    invoice = ServiceInvoice.query.get(invoice_id)
    sub_lab = ServiceSubLab.query.filter_by(code=invoice.quotation.request.lab).first()
    admin_lab = ServiceAdmin.query.filter(ServiceAdmin.admin_id == current_user.id,
                                          ServiceAdmin.sub_lab.has(ServiceSubLab.code == sub_lab.code))
    supervisor = any(a.is_supervisor for a in admin_lab)
    approver = sub_lab.approver if sub_lab.approver_id == current_user.id else None
    signer = sub_lab.signer if sub_lab.signer_id == current_user.id else None
    central_admin = any(a.is_central_admin for a in admin_lab)
    return render_template('service_admin/view_invoice.html', invoice=invoice, supervisor=supervisor,
                           approver=approver, signer=signer, sub_lab=sub_lab, central_admin=central_admin)


def generate_invoice_pdf(invoice, sign=False, cancel=False):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 60, 60)

    lab = ServiceLab.query.filter_by(code=invoice.quotation.request.lab).first()
    sub_lab = ServiceSubLab.query.filter_by(code=invoice.quotation.request.lab).first()

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

    affiliation = '''<para><font size=10>
                           คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>
                           999 ต.ศาลายา อ.พุทธมณฑล จ.นครปฐม 73170<br/>
                           โทร 0-2441-4371-9 ต่อ 2820 2830<br/>
                           เลขประจำตัวผู้เสียภาษี 0994000158378
                           </font></para>
                           '''

    lab_address = '''<para><font size=12>
                        {address}
                        </font></para>'''.format(address=lab.address if lab else sub_lab.address)

    invoice_no = '''<br/><br/><font size=10>
                    เลขที่/No. {invoice_no}<br/>
                    </font>
                    '''.format(invoice_no=invoice.invoice_no)

    header_content_ori = [[[],
                           [logo],
                           [],
                           [Paragraph(affiliation, style=style_sheet['ThaiStyleRight']),
                            Paragraph(invoice_no, style=style_sheet['ThaiStyleRight'])]]]

    header_styles = TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
    ])

    header_ori = Table(header_content_ori, colWidths=[150, 200, 0, 150])

    header_ori.hAlign = 'CENTER'
    header_ori.setStyle(header_styles)

    issued_date = arrow.get(invoice.created_at.astimezone(localtz)).format(fmt='DD MMMM YYYY', locale='th-th')
    customer = '''<para><font size=11>
                    ที่ อว. {mhesi_no}<br/>
                    วันที่ {issued_date}<br/>
                    เรื่อง ใบแจ้งหนี้ค่าบริการตรวจวิเคราะห์ทางห้องปฏิบัติการ<br/>
                    เรียน {customer}<br/>
                    ที่อยู่ {address}<br/>
                    เลขประจำตัวผู้เสียภาษี {taxpayer_identification_no}
                    </font></para>
                    '''.format(mhesi_no = invoice.mhesi_no if invoice.mhesi_no else '',
                               issued_date=issued_date,
                               customer=invoice.name,
                               address=invoice.address,
                               taxpayer_identification_no=invoice.taxpayer_identification_no)

    customer_table = Table([[Paragraph(customer, style=style_sheet['ThaiStyle'])]], colWidths=[540, 280])

    customer_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP')]))

    items = [[Paragraph('<font size=10>ลำดับ / No.</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>รายการ / Description</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>จำนวน / Quantity</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>ราคา / Unit Price</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>จำนวนเงิน / Amount</font>', style=style_sheet['ThaiStyleCenter']),
              ]]

    discount = 0

    for n, item in enumerate(invoice.invoice_items, start=1):
        if item.discount:
            if item.discount_type == 'เปอร์เซ็นต์':
                amount = item.total_price * (float(item.discount) / 100)
                discount += amount
            else:
                discount += float(item.discount)
        item_record = [Paragraph('<font size=12>{}</font>'.format(n), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{}</font>'.format(item.item), style=style_sheet['ThaiStyle']),
                       Paragraph('<font size=12>{}</font>'.format(item.quantity), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.unit_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.total_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       ]
        items.append(item_record)

    net_price = invoice.total_price - discount
    n = len(items)

    for i in range(18 - n):
        items.append([
            Paragraph('<font size=12>&nbsp; </font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
        ])

    items.append([
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>รวมเป็นเงิน</font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(invoice.total_price), style=style_sheet['ThaiStyleNumber']),
    ])

    items.append([
        Paragraph('<font size=12>{}</font>'.format(bahttext(net_price)), style=style_sheet['ThaiStyleCenter']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>ส่วนลด</font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(discount), style=style_sheet['ThaiStyleNumber']),
    ])

    items.append([
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>รวมเป็นเงินทั้งสิ้น/Grand Total</font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(net_price), style=style_sheet['ThaiStyleNumber']),
    ])

    item_table = Table(items, colWidths=[50, 250, 75, 75])
    item_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, 0), 0.25, colors.black),
        ('BOX', (0, 0), (0, -1), 0.25, colors.black),
        ('BOX', (1, 0), (1, -1), 0.25, colors.black),
        ('BOX', (2, 0), (2, -1), 0.25, colors.black),
        ('BOX', (3, 0), (3, -1), 0.25, colors.black),
        ('BOX', (4, 0), (4, -1), 0.25, colors.black),
        ('LINEABOVE', (0, -3), (-1, -3), 0.25, colors.black),
        ('BOX', (2, -3), (-1, -3), 0.25, colors.black),
        ('BOX', (2, -2), (-1, -2), 0.25, colors.black),
        ('BOX', (2, -1), (-1, -1), 0.25, colors.black),
        ('SPAN', (0, -3), (1, -3)),
        ('SPAN', (2, -3), (3, -3)),
        ('SPAN', (0, -2), (1, -2)),
        ('SPAN', (2, -2), (3, -2)),
        ('SPAN', (0, -1), (1, -1)),
        ('SPAN', (2, -1), (3, -1)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))

    text_info = Paragraph('<br/><font size=12>ขอแสดงความนับถือ<br/></font>', style=style_sheet['ThaiStyle'])
    text = [[text_info, Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
    text_table = Table(text, colWidths=[0, 155, 155])
    text_table.hAlign = 'RIGHT'
    sign_info = Paragraph('<font size=12>(ผู้ช่วยศาตราจารย์ ดร.โชติรส พลับพลึง)</font>', style=style_sheet['ThaiStyle'])
    sign = [[sign_info, Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
    sign_table = Table(sign, colWidths=[0, 185, 185])
    sign_table.hAlign = 'RIGHT'
    position_info = Paragraph('<font size=12>คณบดีคณะเทคนิคการแพทย์</font>', style=style_sheet['ThaiStyle'])
    position = [[position_info, Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
    position_table = Table(position, colWidths=[0, 168, 168])
    position_table.hAlign = 'RIGHT'

    data.append(KeepTogether(Spacer(7, 7)))
    data.append(KeepTogether(header_ori))
    data.append(KeepTogether(Spacer(1, 12)))
    data.append(KeepTogether(customer_table))
    data.append(KeepTogether(Spacer(1, 16)))
    data.append(KeepTogether(item_table))
    data.append(KeepTogether(Spacer(1, 16)))
    data.append(KeepTogether(text_table))
    data.append(KeepTogether(Spacer(1, 25)))
    data.append(KeepTogether(sign_table))
    data.append(KeepTogether(position_table))

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
    scheme = 'http' if current_app.debug else 'https'
    admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=invoice.quotation.request.lab)).all()
    sub_lab = ServiceSubLab.query.filter_by(code=invoice.quotation.request.lab).first()
    invoice_url = url_for("service_admin.view_invoice", invoice_id=invoice.id, _external=True, _scheme=scheme)
    if admin == 'dean':
        invoice.approved_at = arrow.now('Asia/Bangkok').datetime
        invoice.status = 'รอเจ้าหน้าทีออกเลข อว.'
        invoice.quotation.request.status = 'รอเจ้าหน้าทีออกเลข อว.'
        db.session.add(invoice)
        db.session.commit()
        msg = ('แจ้งออกเลข อว. ใบแจ้งหนี้เลขที่ {}' \
               '\nกรุณาดำเนินการออกเลข อว. ตามขั้นตอน.'.format(invoice.invoice_no))
        title = 'แจ้งอนุมัติใบแจ้งหนี้และขอออกเลข อว.'
        message = f'''ใบแจ้งหนี้เลขที่ {invoice.invoice_no} ได้รับการอนุมัติจากคณบดีและลงนามเรียบร้อยแล้ว\n\n'''
        message += f'''กรุณาดำเนินการออกเลข อว. ให้เรียบร้อยตามขั้นตอนที่กำหนด\n\n'''
        message += f'''ดูรายละเอียดเพิ่มเติมได้ที่ : {invoice_url}'''
        send_mail([a.admin.email for a in admins if a.is_central_admin], title, message)
        if not current_app.debug:
            for a in admins:
                if a.is_central_admin:
                    try:
                        line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                    except LineBotApiError:
                        pass
    elif admin == 'assistant':
        invoice.status = 'รอคณบดีอนุมัติใบแจ้งหนี้'
        invoice.quotation.request.status = 'รอคณบดีอนุมัติใบแจ้งหนี้'
        db.session.add(invoice)
        db.session.commit()
        msg = ('แจ้งขออนุมัติใบแจ้งหนี้เลขที่ {}' \
               '\nกรุณาตรวจสอบและดำเนินการอนุมัติใบแจ้งหนี้'.format(invoice.invoice_no))
        title = 'แจ้งขออนุมัติใบแจ้งหนี้้'
        message = f'''เรียนคณบดี\n\n'''
        message = f'''ใบแจ้งหนี้เลขที่ {invoice.invoice_no} ได้รับการตรวจสอบและอนุมัติโดยผู้ช่วยคณบดีเรียบร้อยแล้ว\n\n'''
        message += f'''กรุณาตรวจสอบและดำเนินการอนุมัติใบแจ้งหนี้ดังกล่าว\n\n'''
        message += f'''วันที่ออกใบแจ้งหนี้ : {invoice.created_at.astimezone(localtz).strftime('%d/%m/%Y')}\n\n'''
        message += f'''เวลาออกใบแจ้งหนี้ : {invoice.created_at.astimezone(localtz).strftime('%H:%M')}\n\n'''
        message += f'''ดูรายละเอียดเพิ่มเติมได้ที่ : {invoice_url}'''
        send_mail([sub_lab.signer.email + '@mahidol.ac.th'], title, message)
        if not current_app.debug:
            try:
                line_bot_api.push_message(to=sub_lab.approver.line_id, messages=TextSendMessage(text=msg))
            except LineBotApiError:
                pass
    elif admin == 'supervisor':
        invoice.status = 'รอผู้ช่วยคณบดีอนุมัติใบแจ้งหนี้'
        invoice.quotation.request.status = 'รอผู้ช่วยคณบดีอนุมัติใบแจ้งหนี้'
        db.session.add(invoice)
        db.session.commit()
        msg = ('แจ้งขออนุมัติใบแจ้งหนี้เลขที่ {}' \
               '\nกรุณาตรวจสอบและดำเนินการอนุมัติใบแจ้งหนี้'.format(invoice.invoice_no))
        title = 'แจ้งขออนุมัติใบแจ้งหนี้'
        message = f'''เรียนผู้ช่วยคณบดี\n\n'''
        message += f'''ใบแจ้งหนี้เลขที่ {invoice.invoice_no} ได้รับการตรวจสอบและอนุมัติโดยหัวหน้าห้องปฏิบัติการเรียบร้อยแล้ว\n\n'''
        message += f'''กรุณาตรวจสอบและดำเนินการอนุมัติใบแจ้งหนี้ดังกล่าว\n\n'''
        message += f'''วันที่ออกใบแจ้งหนี้ : {invoice.created_at.astimezone(localtz).strftime('%d/%m/%Y')}\n\n'''
        message += f'''เวลาออกใบแจ้งหนี้ : {invoice.created_at.astimezone(localtz).strftime('%H:%M')}\n\n'''
        message += f'''ดูรายละเอียดเพิ่มเติมได้ที่ : {invoice_url}'''
        send_mail([sub_lab.approver.email + '@mahidol.ac.th'], title, message)
        if not current_app.debug:
            try:
                line_bot_api.push_message(to=sub_lab.approver.line_id, messages=TextSendMessage(text=msg))
            except LineBotApiError:
                pass
    flash('อัพเดตสถานะสำเร็จ', 'success')
    return render_template('service_admin/invoice_index.html')


@service_admin.route('/invoice/number/add/<int:invoice_id>', methods=['GET', 'POST'])
def add_mhesi_number(invoice_id):
    invoice = ServiceInvoice.query.get(invoice_id)
    form = ServiceInvoiceForm(obj=invoice)
    if form.validate_on_submit():
        form.populate_obj(invoice)
        invoice.status = 'ออกใบแจ้งหนี้เรียบร้อยแล้ว'
        invoice.quotation.request.status = 'ยังไม่ชำระเงิน'
        payment = ServicePayment(invoice_id=invoice_id, amount_due=invoice.total_price)
        db.session.add(invoice)
        db.session.add(payment)
        db.session.commit()
        scheme = 'http' if current_app.debug else 'https'
        org = Org.query.filter_by(name='หน่วยการเงินและบัญชี').first()
        staff = StaffAccount.get_account_by_email(org.head)
        sub_lab = ServiceSubLab.query.filter_by(code=invoice.quotation.request.lab).first()
        invoice_url = url_for("academic_services.view_invoice", invoice_id=invoice.id, menu='invoice', _external=True,
                              _scheme=scheme)
        msg = ('หน่วย{} ได้ดำเนินการออกใบแจ้งหนี้เลขที่่ {} เรียบร้อยแล้ว' \
               '\nกรุณาดำเนินการเตรียมออกใบเสร็จรับเงินเมื่อลูกค้าชำระเงิน'.format(sub_lab.sub_lab, invoice.invoice_no))
        title = 'แจ้งออกใบแจ้งหนี้'
        message = f'''เรียนผู้ใช้บริการ\n\n'''
        message += f'''ทางหน่วยงานได้ดำเนินการออกใบแจ้งหนี้เลขที่ {invoice.invoice_no} เรียบร้อยแล้ว กรุณาดำเนินการชำระเงินภายใน 30 วันนับจากวันที่ออกใบแจ้งหนี้\n\n'''
        message += f'''ท่านสามารถตรวจสอบรายละเอียดใบแจ้งหนี้ได้จากลิงก์ด้านล่าง\n\n'''
        message += f'''{invoice_url}\n\n'''
        message += f'''หากมีข้อสงสัยหรือสอบถามเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ตามช่องทางที่ให้ไว้\n\n'''
        message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
        message += f'''ขอขอบคุณที่ใช้บริการ'''
        send_mail([customer_contact.email for customer_contact in invoice.quotation.request.customer.customer_contacts],
                  title,
                  message)
        if not current_app.debug:
            try:
                line_bot_api.push_message(to=staff.line_id, messages=TextSendMessage(text=msg))
            except LineBotApiError:
                pass
        flash('บันทึกข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('service_admin/modal/add_mhesi_number_modal.html', form=form, invoice_id=invoice_id)


@service_admin.route('/quotation/index')
@login_required
def quotation_index():
    tab = request.args.get('tab')
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    is_supervisor = any(a.is_supervisor for a in admin)
    return render_template('service_admin/quotation_index.html', tab=tab, is_supervisor=is_supervisor)


@service_admin.route('/api/quotation/index')
def get_quotations():
    tab = request.args.get('tab')
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    sub_labs = []
    for a in admin:
        sub_labs.append(a.sub_lab.code)

    query = ServiceQuotation.query.filter(
        or_(ServiceQuotation.creator_id == current_user.id,
            ServiceQuotation.request.has(ServiceRequest.lab.in_(sub_labs))))
    if tab == 'draft':
        query = query.filter_by(status='อยู่ระหว่างการจัดทำใบเสนอราคา')
    elif tab == 'pending_supervisor_approval' or tab == 'pending_approval':
        query = query.filter_by(status='รออนุมัติใบเสนอราคาโดยหัวหน้าห้องปฏิบัติการ')
    elif tab == 'awaiting_customer':
        query = query.filter_by(status='รอยืนยันใบเสนอราคาจากลูกค้า')
    elif tab == 'confirmed':
        query = query.filter_by(status='ยืนยันใบเสนอราคาเรียบร้อยแล้ว')
    elif tab == 'reject':
        query = query.filter_by(status='ลูกค้าไม่อนุมัติใบเสนอราคา')
    else:
        query = query
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ServiceQuotation.quotation_no.contains(search))
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


@service_admin.route('/quotation/generate', methods=['GET', 'POST'])
@login_required
def generate_quotation():
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab).first()
    sheet_price_id = '1hX0WT27oRlGnQm997EV1yasxlRoBSnhw3xit1OljQ5g'
    gc = get_credential(json_keyfile)
    wksp = gc.open_by_key(sheet_price_id)
    sheet_price = wksp.worksheet(sub_lab.code)
    df_price = pandas.DataFrame(sheet_price.get_all_records())
    quote_column_names = {}
    quote_details = {}
    quote_prices = {}
    count_value = Counter()
    for _, row in df_price.iterrows():
        if sub_lab and sub_lab.code == 'quantitative':
            quote_column_names[row['field_group']] = set(row['field_name'].split(', '))
        else:
            if row['field_group'] not in quote_column_names:
                quote_column_names[row['field_group']] = set()
            for field_name in row['field_name'].split(','):
                quote_column_names[row['field_group']].add(field_name.strip())
        key = ''.join(sorted(row[4:].str.cat())).replace(' ', '')
        if service_request.customer.customer_info.type.type == 'หน่วยงานรัฐ':
            quote_prices[key] = row['government_price']
        else:
            quote_prices[key] = row['other_price']
    sheet_request_id = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
    wksr = gc.open_by_key(sheet_request_id)
    sheet_request = wksr.worksheet(sub_lab.sheet)
    df_request = pandas.DataFrame(sheet_request.get_all_records())
    data = service_request.data
    request_form = create_request_form(df_request)(**data)
    total_price = 0
    for field in request_form:
        if field.name not in quote_column_names:
            continue
        keys = []
        keys = walk_form_fields(field, quote_column_names[field.name], keys=keys)
        for r in range(1, len(quote_column_names[field.name]) + 1):
            for key in itertools.combinations(keys, r):
                sorted_key_ = sorted(''.join([k[1] for k in key]))
                p_key = ''.join(sorted_key_).replace(' ', '')
                values = ', '.join([k[1] for k in key])
                count_value.update(values.split(', '))
                quantities = (
                    ', '.join(str(count_value[v]) for v in values.split(', '))
                    if ((sub_lab and sub_lab.lab.code not in ['bacteria', 'virology']))
                    else 1
                )
                if sub_lab and sub_lab.lab.code == 'endotoxin':
                    for k in key:
                        if not k[1]:
                            break
                        for price in quote_prices.values():
                            total_price += price
                            quote_details[p_key] = {"value": values, "price": price, "quantity": quantities}
                else:
                    if p_key in quote_prices:
                        prices = quote_prices[p_key]
                        total_price += prices
                        quote_details[p_key] = {"value": values, "price": prices, "quantity": quantities}
    quotation_no = ServiceNumberID.get_number('QT', db,
                                              lab=sub_lab.lab.code if sub_lab and sub_lab.lab.code == 'protein' \
                                                  else service_request.lab)
    district_title = 'เขต' if service_request.document_address.province.name == 'กรุงเทพมหานคร' else 'อำเภอ'
    subdistrict_title = 'แขวง' if service_request.document_address.province.name == 'กรุงเทพมหานคร' else 'ตำบล'
    quotation = ServiceQuotation(quotation_no=quotation_no.number, total_price=total_price, request_id=request_id,
                                 name=service_request.quotation_address.name,
                                 address=f'{service_request.quotation_address.address} '
                                         f'{subdistrict_title}{service_request.quotation_address.subdistrict}'
                                         f'{district_title}{service_request.quotation_address.district}'
                                         f'{service_request.quotation_address.province}'
                                         f'{service_request.quotation_address.zipcode}',
                                 taxpayer_identification_no=service_request.quotation_address.taxpayer_identification_no,
                                 creator=current_user, created_at=arrow.now('Asia/Bangkok').datetime,
                                 status='อยู่ระหว่างการจัดทำใบเสนอราคา')
    db.session.add(quotation)
    quotation_no.count += 1
    db.session.commit()
    for _, (_, item) in enumerate(quote_details.items()):
        sequence_no = ServiceSequenceQuotationID.get_number('QT', db, quotation='quotation_' + str(quotation.id))
        quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                              item=item['value'],
                                              quantity=item['quantity'],
                                              unit_price=item['price'],
                                              total_price=int(item['quantity']) * item['price'])
        sequence_no.count += 1
        db.session.add(quotation_item)
        if service_request.eng_language:
            quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                  item='ใบรายงานผลภาษาอังกฤษ',
                                                  quantity=1,
                                                  unit_price=300,
                                                  total_price=1 * 300)
            sequence_no.count += 1
            db.session.add(quotation_item)
        if service_request.thai_copy_language:
            quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                  item='สำเนาใบรายงานผลภาษาไทย',
                                                  quantity=1,
                                                  unit_price=300,
                                                  total_price=1 * 300)
            sequence_no.count += 1
            db.session.add(quotation_item)
        if service_request.eng_copy_language:
            quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                  item='สำเนาใบรายงานผลภาษาอังกฤษ',
                                                  quantity=1,
                                                  unit_price=300,
                                                  total_price=1 * 300)
            sequence_no.count += 1
            db.session.add(quotation_item)
        db.session.commit()
    return redirect(url_for('service_admin.create_quotation_for_admin', quotation_id=quotation.id, tab='draft'))


@service_admin.route('/admin/quotation/add/<int:quotation_id>', methods=['GET', 'POST', 'PATCH'])
def create_quotation_for_admin(quotation_id):
    tab = request.args.get('tab')
    action = request.form.get('action')
    quotation = ServiceQuotation.query.get(quotation_id)
    sub_lab = ServiceSubLab.query.filter_by(code=quotation.request.lab)
    datas = request_data(quotation.request)
    quotation.quotation_items = sorted(quotation.quotation_items, key=lambda x: x.sequence)
    form = ServiceQuotationForm(obj=quotation)
    if form.validate_on_submit():
        form.populate_obj(quotation)
        db.session.add(quotation)
        db.session.commit()
        if action == 'approve':
            scheme = 'http' if current_app.debug else 'https'
            quotation.status = 'รออนุมัติใบเสนอราคาโดยหัวหน้าห้องปฏิบัติการ'
            quotation.request.status = 'รออนุมัติใบเสนอราคาโดยหัวหน้าห้องปฏิบัติการ'
            db.session.add(quotation)
            db.session.commit()
            title_prefix = 'คุณ' if quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
            admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=quotation.request.lab)).all()
            quotation_link = url_for("service_admin.approval_quotation_for_supervisor", quotation_id=quotation_id,
                                     tab='pending_approval', _external=True, _scheme=scheme)
            title = f'''[{quotation.quotation_no} ใบเสนอราคา - {title_prefix}{quotation.request.customer.customer_info.cus_name}]'''
            message = f'''เรียน หัวหน้าห้องปฏิบัติการ\n\n'''
            message += f'''กรุณาตรวจสอบและดำเนิการได้ที่ลิงก์ด้านล่าง\n'''
            message += f'''มีใบเสนอราคาเลขที่ {quotation.quotation_no} จาก {title_prefix}{quotation.request.customer.customer_info.cus_name} ที่รอการอนุมัติใบเสนอราคา\n'''
            message += f'''{quotation_link}\n\n'''
            message += f'''ขอบคุณค่ะ\n'''
            message += f'''ระบบงานบริการวิชาการ'''
            send_mail([a.admin.email + '@mahidol.ac.th' for a in admins if a.is_supervisor], title, message)
            msg = ('แจ้งขออนุมัติใบเสนอราคาเลขที่ {}' \
                   '\n\nเรียน หัวหน้าห้องปฏิบัติการ'
                   '\n\nมีใบเสนอราคาเลขที่ {} จาก {}{} ที่รอการอนุมัติใบเสนอราคา' \
                   '\nกรุณาตรวจสอบและดำเนิการได้ที่ลิงก์ด้านล่าง' \
                   '\n{}' \
                   '\n\nขอบคุณค่ะ' \
                   '\nระบบงานบริการวิชาการ'.format(quotation.request.request_no, quotation.request.request_no,
                                                   title_prefix, quotation.request.customer.customer_info.cus_name,
                                                   quotation_link)
                   )
            if not current_app.debug:
                for a in admins:
                    if a.is_supervisor:
                        try:
                            line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                        except LineBotApiError:
                            pass
            flash('สร้างใบเสนอราคาสำเร็จ', 'success')
            return redirect(url_for('service_admin.quotation_index', tab=tab))
        else:
            flash('บันทึกข้อมูลสำเร็จ', 'success')
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('service_admin/create_quotation_for_admin.html', quotation=quotation,
                           tab=tab, form=form, datas=datas, sub_lab=sub_lab)


@service_admin.route('/quotation/item/add/<int:quotation_id>', methods=['GET', 'POST'])
def add_quotation_item(quotation_id):
    tab = request.args.get('tab')
    ServiceQuotationItemForm = create_quotation_item_form(is_form=True)
    quotation = ServiceQuotation.query.get(quotation_id)
    form = ServiceQuotationItemForm()
    if form.validate_on_submit():
        sequence_no = ServiceSequenceQuotationID.get_number('QT', db, quotation='quotation_' + str(quotation_id))
        quotation_item = ServiceQuotationItem()
        form.populate_obj(quotation_item)
        quotation_item.sequence = sequence_no.number
        quotation_item.quotation_id = quotation_id
        quotation_item.total_price = form.quantity.data * form.unit_price.data
        db.session.add(quotation_item)
        quotation.total_price = quotation.total_price + (form.unit_price.data * form.quantity.data)
        sequence_no.count += 1
        db.session.add(quotation)
        db.session.commit()
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('service_admin/modal/add_quotation_item_modal.html', form=form, tab=tab,
                           quotation_id=quotation_id)


@service_admin.route('/quotation/supervisor/approve/<int:quotation_id>', methods=['GET', 'POST'])
def approval_quotation_for_supervisor(quotation_id):
    tab = request.args.get('tab')
    quotation = ServiceQuotation.query.get(quotation_id)
    sub_lab = ServiceSubLab.query.filter_by(code=quotation.request.lab).all()
    scheme = 'http' if current_app.debug else 'https'
    if request.method == 'POST':
        quotation.approver_id = current_user.id
        quotation.approved_at = arrow.now('Asia/Bangkok').datetime
        quotation.status = 'รอยืนยันใบเสนอราคาจากลูกค้า'
        quotation.request.status = 'รอยืนยันใบเสนอราคาจากลูกค้า'
        db.session.add(quotation)
        db.session.commit()
        quotation_link = url_for("academic_services.view_quotation", quotation_id=quotation_id,
                                 menu='quotation', _external=True, _scheme=scheme)
        total_items = len(quotation.quotation_items)
        title_prefix = 'คุณ' if quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
        title = f'''โปรดยืนยันใบเสนอราคา ({quotation.quotation_no}) – งานบริการตรวจวิเคราะห์ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
        message = f'''เรียน {title_prefix}{quotation.request.customer.customer_info.cus_name}\n\n'''
        message += f'''ตามที่ท่านได้แจ้งความประสงค์ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล ใบเสนอราคาหมายเลข {quotation.quotation_no}'''
        message += f''' ได้รับการอนุมัติเรียบร้อยแล้ว และขณะนี้รอการยืนยันจากท่านเพื่อดำเนินการขั้นตอนต่อไป\n\n'''
        message += f'''รายละเอียดข้อมูล\n'''
        message += f'''วันที่อนุมัติ : {quotation.approved_at.astimezone(localtz).strftime('%d/%m/%Y')}\n'''
        message += f'''จำนวนรายการ : {total_items} รายการ\n'''
        message += f'''ราคารวม : {quotation.sum_price()} บาท\n\n'''
        message += f'''กรุณาดำเนินการยืนยันใบเสนอราคาภายใน 7 วัน ผ่านลิงก์ด้านล่าง\n'''
        message += f'''{quotation_link}\n\n'''
        message += f'''หากไม่ยืนยันภายในกำหนด ใบเสนอราคาอาจถูกยกเลิกและราคาอาจเปลี่ยนแปลงได้\n\n'''
        message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
        message += f'''ขอแสดงความนับถือ\n'''
        message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
        message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
        send_mail([quotation.request.customer.email], title, message)
        quotation_link_for_assistant = url_for("service_admin.view_quotation", quotation_id=quotation_id,
                                               tab='awaiting_customer', _external=True, _scheme=scheme)

        title_for_assistant = f'''[{quotation.quotation_no}] ใบเสนอราคา - {title_prefix}{quotation.request.customer.customer_info.cus_name} (แจ้งอนุมัติใบเสนอราคา)'''
        message_for_assistant = f'''เรียน ผู้ช่วยคณบดีฝ่ายบริการวิชาการ\n\n'''
        message_for_assistant += f'''มีใบเสนอราคาเลขที่ {quotation.quotation_no} จาก {title_prefix}{quotation.request.customer.customer_info.cus_name} ได้ดำเนินการอนุมัติใบเสนอราคาเป็นที่เรียบร้อยแล้ว\n'''
        message_for_assistant += f'''ท่านสามารถเข้าดูรายละเอียดของใบเสนอราคาได้ที่ลิงก์ด้านล่าง\n'''
        message_for_assistant += f'''{quotation_link_for_assistant}\n\n'''
        message += f'''ขอบคุณค่ะ\n'''
        message += f'''ระบบงานบริกาวิชาการ\n'''
        send_mail([s.approver.email + '@mahidol.ac.th' for s in sub_lab], title_for_assistant, message_for_assistant)
        flash(f'อนุมัติใบเสนอราคาเลขที่ {quotation.quotation_no} สำเร็จ', 'success')
        return redirect(url_for('service_admin.quotation_index', quotation_id=quotation.id, tab='awaiting_customer'))
    return render_template('service_admin/approval_quotation_for_supervisor.html', quotation=quotation,
                           tab=tab, quotation_id=quotation_id, sub_lab=sub_lab)


@service_admin.route('/quotation/view/<int:quotation_id>')
@login_required
def view_quotation(quotation_id):
    tab = request.args.get('tab')
    quotation = ServiceQuotation.query.get(quotation_id)
    sub_lab = ServiceSubLab.query.filter_by(code=quotation.request.lab).all()
    return render_template('service_admin/view_quotation.html', quotation_id=quotation_id, tab=tab,
                           quotation=quotation, sub_lab=sub_lab)


def generate_quotation_pdf(quotation):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 60, 60)

    lab = ServiceLab.query.filter_by(code=quotation.request.lab).first()
    sub_lab = ServiceSubLab.query.filter_by(code=quotation.request.lab).first()

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

    affiliation = '''<para><font size=10>
                   คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>
                   999 ต.ศาลายา อ.พุทธมณฑล จ.นครปฐม 73170<br/>
                   โทร 0-2441-4371-9 ต่อ 2820 2830<br/>
                   เลขประจำตัวผู้เสียภาษี 0994000158378
                   </font></para>
                   '''

    lab_address = '''<para><font size=12>
                        {address}
                        </font></para>'''.format(address=lab.address if lab else sub_lab.address)

    quotation_no = '''<br/><br/><font size=10>
                เลขที่/No. {quotation_no}<br/>
                </font>
                '''.format(quotation_no = quotation.quotation_no)

    header_content_ori = [[[],
                           [logo],
                           [],
                           [Paragraph(affiliation, style=style_sheet['ThaiStyleRight']),
                           Paragraph(quotation_no, style=style_sheet['ThaiStyleRight'])]]]

    header_styles = TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
    ])

    header_ori = Table(header_content_ori, colWidths=[150, 200, 0, 150])

    header_ori.hAlign = 'CENTER'
    header_ori.setStyle(header_styles)

    issued_date = arrow.get(quotation.created_at.astimezone(localtz)).format(fmt='DD MMMM YYYY', locale='th-th')
    customer = '''<para><font size=12>
                วันที่ {issued_date}<br/>
                เรื่อง ใบเสนอราคาค่าบิรการตรวจวิเคราะห์ทางห้องปฏิบัติการ<br/>
                เรียน {customer}<br/>
                ที่อยู่ {address}<br/>
                เลขประจำตัวผู้เสียภาษี {taxpayer_identification_no}
                </font></para>
                '''.format(issued_date=issued_date, customer=quotation.name, address=quotation.address,
                           taxpayer_identification_no=quotation.taxpayer_identification_no if quotation.taxpayer_identification_no else '-')

    customer_table = Table([[Paragraph(customer, style=style_sheet['ThaiStyle'])]], colWidths=[540, 280])
    customer_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP')]))

    items = [[Paragraph('<font size=10>ลำดับ / No.</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>รายการ / Description</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>จำนวน / Quantity</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>ราคา / Unit Price</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>จำนวนเงิน / Amount</font>', style=style_sheet['ThaiStyleCenter']),
              ]]

    discount = 0

    for n, item in enumerate(quotation.quotation_items, start=1):
        if item.discount:
            if item.discount_type == 'เปอร์เซ็นต์':
                amount = item.total_price * (float(item.discount) / 100)
                discount += amount
            else:
                discount += float(item.discount)
        item_record = [Paragraph('<font size=12>{}</font>'.format(n), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{}</font>'.format(item.item), style=style_sheet['ThaiStyle']),
                       Paragraph('<font size=12>{}</font>'.format(item.quantity), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.unit_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.total_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       ]
        items.append(item_record)

    net_price = quotation.total_price - discount
    n = len(items)

    for i in range(18 - n):
        items.append([
            Paragraph('<font size=12>&nbsp; </font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
        ])

    items.append([
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>รวมเป็นเงิน</font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(quotation.total_price), style=style_sheet['ThaiStyleNumber']),
    ])

    items.append([
        Paragraph('<font size=12>{}</font>'.format(bahttext(net_price)), style=style_sheet['ThaiStyleCenter']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>ส่วนลด</font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(discount), style=style_sheet['ThaiStyleNumber']),
    ])

    items.append([
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>รวมเป็นเงินทั้งสิ้น/Grand Total</font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(net_price), style=style_sheet['ThaiStyleNumber']),
    ])

    item_table = Table(items, colWidths=[50, 250, 75, 75])
    item_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, 0), 0.25, colors.black),
        ('BOX', (0, 0), (0, -1), 0.25, colors.black),
        ('BOX', (1, 0), (1, -1), 0.25, colors.black),
        ('BOX', (2, 0), (2, -1), 0.25, colors.black),
        ('BOX', (3, 0), (3, -1), 0.25, colors.black),
        ('BOX', (4, 0), (4, -1), 0.25, colors.black),
        ('LINEABOVE', (0, -3), (-1, -3), 0.25, colors.black),
        ('BOX', (2, -3), (-1, -3), 0.25, colors.black),
        ('BOX', (2, -2), (-1, -2), 0.25, colors.black),
        ('BOX', (2, -1), (-1, -1), 0.25, colors.black),
        ('SPAN', (0, -3), (1, -3)),
        ('SPAN', (2, -3), (3, -3)),
        ('SPAN', (0, -2), (1, -2)),
        ('SPAN', (2, -2), (3, -2)),
        ('SPAN', (0, -1), (1, -1)),
        ('SPAN', (2, -1), (3, -1)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))

    text_info = Paragraph('<br/><font size=12>ขอแสดงความนับถือ<br/></font>', style=style_sheet['ThaiStyle'])
    text = [[text_info, Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
    text_table = Table(text, colWidths=[0, 140, 140])
    text_table.hAlign = 'RIGHT'

    sign_info = Paragraph(
        '<font size=12>(&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)</font>',
        style=style_sheet['ThaiStyle'])
    sign = [[sign_info, Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
    sign_table = Table(sign, colWidths=[0, 185, 185])
    sign_table.hAlign = 'RIGHT'

    position_info = Paragraph('<font size=12>หัวหน้าห้องปฏิบัติการ</font>', style=style_sheet['ThaiStyle'])
    position = [[position_info, Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
    position_table = Table(position, colWidths=[0, 143, 143])
    position_table.hAlign = 'RIGHT'

    data.append(KeepTogether(Spacer(7, 7)))
    data.append(KeepTogether(header_ori))
    data.append(KeepTogether(Spacer(1, 12)))
    data.append(KeepTogether(customer_table))
    data.append(KeepTogether(Spacer(1, 16)))
    data.append(KeepTogether(item_table))
    data.append(KeepTogether(Spacer(1, 5)))
    data.append(KeepTogether(text_table))
    data.append(KeepTogether(Spacer(1, 25)))
    data.append(KeepTogether(sign_table))
    data.append(KeepTogether(Spacer(1, 2)))
    data.append(KeepTogether(position_table))

    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    buffer.seek(0)
    return buffer


@service_admin.route('/quotation/pdf/<int:quotation_id>', methods=['GET'])
def export_quotation_pdf(quotation_id):
    quotation = ServiceQuotation.query.get(quotation_id)
    buffer = generate_quotation_pdf(quotation)
    return send_file(buffer, download_name='Quotation.pdf', as_attachment=True)
