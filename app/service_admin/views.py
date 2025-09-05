import itertools
import re
import uuid
import qrcode
from collections import Counter
import arrow
import pandas
from io import BytesIO
from bahttext import bahttext
from markupsafe import Markup
from pytz import timezone
from datetime import date
from base64 import b64decode
from sqlalchemy.orm import make_transient
from wtforms import FormField, FieldList
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
from app.auth.views import line_bot_api
from app.academic_services.forms import create_request_form, ServicePaymentForm
from app.e_sign_api import e_sign
from app.models import Org
from app.scb_payment_service.views import generate_qrcode
from app.service_admin import service_admin
from app.academic_services.models import *
from flask import render_template, flash, redirect, url_for, request, session, make_response, jsonify, current_app, \
    send_file
from flask_login import current_user, login_required
from sqlalchemy import or_
from app.service_admin.forms import (ServiceCustomerInfoForm, crate_address_form, create_quotation_item_form,
                                     ServiceInvoiceForm, ServiceQuotationForm, ServiceSampleForm,
                                     PasswordOfSignDigitalForm,
                                     ServiceResultForm, ServiceCustomerContactForm)
from app.main import app, get_credential, json_keyfile
from app.main import mail
from flask_mail import Message
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, TableStyle, Table, Spacer, KeepTogether, PageBreak

localtz = timezone('Asia/Bangkok')

sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
pdfmetrics.registerFont(sarabun_font)
pdfmetrics.registerFont(TTFont('SarabunItalic', 'app/static/fonts/THSarabunNewItalic.ttf'))
style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))
style_sheet.add(ParagraphStyle(name='ThaiStyleBold', fontName='SarabunBold'))
style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', alignment=TA_CENTER))
style_sheet.add(ParagraphStyle(name='ThaiStyleRight', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleItalic', fontName='SarabunItalic'))

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_url(file_url):
    url = s3.generate_presigned_url('get_object',
                                    Params={'Bucket': S3_BUCKET_NAME, 'Key': file_url},
                                    ExpiresIn=3600)
    return url


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


def form_data(data):
    if isinstance(data, dict):
        return {k: form_data(v) for k, v in data.items() if k != "csrf_token" and k != 'submit'}
    elif isinstance(data, list):
        return [form_data(item) for item in data]
    elif isinstance(data, (date)):
        return data.isoformat()
    return data


def get_status(s_id):
    statuses = ServiceStatus.query.filter_by(status_id=s_id).first()
    status_id = statuses.id
    return status_id


def sort_quotation_item(items):
    if 'สำเนา' in items.item:
        priority = 2
    elif 'ใบรายงานผล' in items.item:
        priority = 1
    else:
        priority = 0
    return (priority, items.id)


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
                                value = Markup(f"<i>{value}</i>")
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
                    label = field.label.text
                    value = ', '.join(field.data) if field.type == 'CheckboxField' else field.data
                    if label.startswith("เชื้อ"):
                        value = Markup(f"<i>{value}</i>")
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
@login_required
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
    menu = request.args.get('menu')
    admins = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    admin = False
    supervisor = False
    assistant = False

    sub_labs = []
    for a in admins:
        if a.sub_lab.approver:
            assistant = True
        elif a.is_supervisor:
            supervisor = True
        else:
            admin = True
        sub_labs.append(a.sub_lab.code)
    quotation_request_count = len([r for r in ServiceRequest.query.filter(ServiceRequest.status.has(status_id=2),
                                                                          or_(ServiceRequest.admin.has(
                                                                              id=current_user.id),
                                                                              ServiceRequest.lab.in_(sub_labs)))])
    quotation_pending_approval_count = len(
        [r for r in ServiceRequest.query.filter(ServiceRequest.status.has(status_id=5),
                                                or_(ServiceRequest.admin.has(id=current_user.id),
                                                    ServiceRequest.lab.in_(sub_labs)))])
    waiting_sample_count = len([r for r in ServiceRequest.query.filter(ServiceRequest.status.has(status_id=9),
                                                                       or_(ServiceRequest.admin.has(id=current_user.id),
                                                                           ServiceRequest.lab.in_(sub_labs)))])
    testing_count = len([r for r in ServiceRequest.query.filter(ServiceRequest.status.has(status_id=11),
                                                                or_(ServiceRequest.admin.has(id=current_user.id),
                                                                    ServiceRequest.lab.in_(sub_labs)))])
    return render_template('service_admin/request_index.html', menu=menu,
                           quotation_request_count=quotation_request_count,
                           quotation_pending_approval_count=quotation_pending_approval_count,
                           waiting_sample_count=waiting_sample_count,
                           testing_count=testing_count, admin=admin, supervisor=supervisor, assistant=assistant)


@service_admin.route('/api/request/index')
def get_requests():
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    sub_labs = []
    for a in admin:
        sub_labs.append(a.sub_lab.code)
    query = ServiceRequest.query.filter(ServiceRequest.status.has(ServiceStatus.status_id != 1),
                                        or_(ServiceRequest.admin.has(id=current_user.id),
                                            ServiceRequest.lab.in_(sub_labs)))
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
        html_blocks = []
        for result in item.results:
            for i in result.result_items:
                if i.final_file:
                    download_file = url_for('service_admin.download_file', key=i.final_file,
                                            download_filename=f"{i.report_language} (ฉบับจริง).pdf")
                    html = f'''
                            <div class="field has-addons">
                                <div class="control">
                                    <a class="button is-small is-light is-link is-rounded" href="{download_file}">
                                        <span>{i.report_language} (ฉบับจริง)</span>
                                        <span class="icon is-small"><i class="fas fa-download"></i></span>
                                    </a>
                                </div>
                            </div>
                        '''
                elif i.draft_file:
                    download_file = url_for('service_admin.download_file', key=i.draft_file,
                                            download_filename=f"{i.report_language} (ฉบับร่าง).pdf")
                    html = f'''
                                <div class="field has-addons">
                                    <div class="control">
                                        <a class="button is-small is-light is-link is-rounded" href="{download_file}">
                                            <span>{i.report_language} (ฉบับร่าง)</span>
                                                <span class="icon is-small"><i class="fas fa-download"></i></span>
                                            </a>
                                        </div>
                                    </div>
                                '''
                else:
                    html = ''
                html_blocks.append(html)
        item_data['files'] = ''.join(html_blocks) if html_blocks else ''
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
    menu = request.args.get('menu')
    sub_lab = request.args.get('sub_lab')
    service_request = ServiceRequest.query.get(request_id)
    report_languages = ServiceReportLanguage.query.all()
    req_report_language_id = [rl.report_language_id for rl in service_request.report_languages]
    req_report_language = [rl.report_language.language for rl in sorted(service_request.report_languages,
                                                                        key=lambda rl: rl.report_language.no)]
    if request.method == 'POST':
        items = request.form.getlist('check_report_language')
        ServiceReqReportLanguageAssoc.query.filter_by(request_id=request_id).delete()
        for item_id in items:
            assoc = ServiceReqReportLanguageAssoc(
                request_id=request_id,
                report_language_id=int(item_id)
            )
            db.session.add(assoc)
        db.session.commit()
        return redirect(url_for('service_admin.create_customer_detail', request_id=request_id, menu=menu,
                                sub_lab=sub_lab))
    return render_template('service_admin/create_report_language.html', menu=menu, sub_lab=sub_lab,
                           request_id=request_id, report_languages=report_languages,
                           req_report_language=req_report_language,
                           req_report_language_id=req_report_language_id)


@service_admin.route('/request/customer/detail/add/<int:request_id>', methods=['GET', 'POST'])
@login_required
def create_customer_detail(request_id):
    form = None
    menu = request.args.get('menu')
    sub_lab = request.args.get('sub_lab')
    service_request = ServiceRequest.query.get(request_id)
    customer_id = service_request.customer.customer_info_id
    selected_address_id = service_request.quotation_address_id if service_request.quotation_address_id else None
    customer = ServiceCustomerInfo.query.get(service_request.customer.customer_info_id)
    cus_contact = ServiceCustomerContact.query.filter_by(creator_id=customer.id).first()
    if not cus_contact:
        form = ServiceCustomerContactForm()
    if request.method == 'POST':
        if not cus_contact:
            cus_contact = ServiceCustomerContact()
            form.populate_obj(cus_contact)
            cus_contact.creator_id = customer.id
            db.session.add(cus_contact)
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
        else:
            for quotation_address_id in request.form.getlist('quotation_address'):
                service_request.document_address_id = int(quotation_address_id)
                db.session.add(service_request)
                quotation_address = ServiceCustomerAddress.query.get(int(quotation_address_id))
                remark = quotation_address.remark if quotation_address.remark else None
                if current_user.customer_info.addresses:
                    for address in current_user.customer_info.addresses:
                        if customer.has_document_address():
                            if address.address_type == 'document':
                                address.name = quotation_address.name
                                address.address_type = 'document'
                                address.taxpayer_identification_no = quotation_address.taxpayer_identification_no
                                address.province_id = quotation_address.province_id
                                address.district_id = quotation_address.district_id
                                address.subdistrict_id = quotation_address.subdistrict_id
                                address.zipcode = quotation_address.zipcode
                                address.phone_number = quotation_address.phone_number
                                address.remark = remark
                                address.customer_id = customer_id
                        else:
                            address = ServiceCustomerAddress(name=quotation_address.name, address_type='document',
                                                             taxpayer_identification_no=quotation_address.taxpayer_identification_no,
                                                             address=quotation_address.address,
                                                             zipcode=quotation_address.zipcode,
                                                             phone_number=quotation_address.phone_number,
                                                             remark=remark,
                                                             customer_id=customer_id,
                                                             province_id=quotation_address.province_id,
                                                             district_id=quotation_address.district_id,
                                                             subdistrict_id=quotation_address.subdistrict_id)
                else:
                    address = ServiceCustomerAddress(name=quotation_address.name, address_type='document',
                                                     taxpayer_identification_no=quotation_address.taxpayer_identification_no,
                                                     address=quotation_address.address,
                                                     zipcode=quotation_address.zipcode,
                                                     phone_number=quotation_address.phone_number, reamerk=remark,
                                                     customer_id=customer_id,
                                                     province_id=quotation_address.province_id,
                                                     district_id=quotation_address.district_id,
                                                     subdistrict_id=quotation_address.subdistrict_id)
                db.session.add(address)
                db.session.commit()
        status_id = get_status(2)
        service_request.status_id = status_id
        service_request.admin_id = current_user.id
        db.session.commit()
        return redirect(url_for('service_admin.view_request', request_id=request_id, menu=menu))
    return render_template('service_admin/create_customer_detail.html', form=form, customer=customer,
                           request_id=request_id, sub_lab=sub_lab, customer_id=customer_id, menu=menu,
                           selected_address_id=selected_address_id)


@service_admin.route('/request/customer/address/add/<int:customer_id>', methods=['GET', 'POST'])
@service_admin.route('/request/customer/address/edit/<int:address_id>', methods=['GET', 'POST'])
@login_required
def edit_customer_address(customer_id=None, address_id=None):
    type = request.args.get('type')
    customer = ServiceCustomerInfo.query.get(customer_id)
    ServiceCustomerAddressForm = crate_address_form(use_type=False)
    if address_id:
        address = ServiceCustomerAddress.query.get(address_id)
        form = ServiceCustomerAddressForm(obj=address)
    else:
        form = ServiceCustomerAddressForm()
    address_type = address.address_type if address_id else None
    if not form.taxpayer_identification_no.data:
        form.taxpayer_identification_no.data = customer.taxpayer_identification_no
    if form.validate_on_submit():
        if address_id is None:
            address = ServiceCustomerAddress()
        form.populate_obj(address)
        if address_id is None:
            address.customer_id = customer_id
            address.address_type = type
        if address_type == 'document' or type == 'document':
            address.taxpayer_identification_no = None
        db.session.add(address)
        db.session.commit()
        if address_id:
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
        else:
            flash('เพิ่มข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('service_admin/modal/add_customer_address_modal.html', type=type, form=form,
                           customer_id=customer_id, address_id=address_id, customer=customer)


@service_admin.route('/customer/address/submit/<int:address_id>', methods=['GET', 'POST'])
def submit_same_address(address_id):
    customer_id = request.args.get('customer_id')
    if request.method == 'POST':
        address = ServiceCustomerAddress.query.get(address_id)
        db.session.expunge(address)
        make_transient(address)
        address.name = address.name
        address.address_type = 'document'
        address.address = address.address
        address.phone_number = address.phone_number
        address.province_id = address.province_id
        address.district_id = address.district_id
        address.subdistrict_id = address.subdistrict_id
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
    menu = request.args.get('menu')
    return render_template('service_admin/sample_index.html', menu=menu)


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
@login_required
def sample_verification(sample_id):
    menu = request.args.get('menu')
    sample = ServiceSample.query.get(sample_id)
    form = ServiceSampleForm(obj=sample)
    if not sample.received_at:
        if request.method == 'GET':
            form.process()
        if form.validate_on_submit():
            form.populate_obj(sample)
            status_id = get_status(10)
            sample.received_at = arrow.now('Asia/Bangkok').datetime
            sample.receiver_id = current_user.id
            sample.request.status_id = status_id
            db.session.add(sample)
            test_item = ServiceTestItem(request_id=sample.request_id, customer_id=sample.request.customer_id,
                                        sample_id=sample_id, creator_id=current_user.id,
                                        created_at=arrow.now('Asia/Bangkok').datetime)
            db.session.add(test_item)
            db.session.commit()
            scheme = 'http' if current_app.debug else 'https'
            contact_email = sample.request.customer.contact_email if sample.request.customer.contact_email else sample.request.customer.email
            title_prefix = 'คุณ' if sample.request.customer.customer_info.type.type == 'บุคคล' else ''
            link = url_for("academic_services.request_index", menu='request', _external=True, _scheme=scheme)
            title = f'''แจ้งตรวจรับตัวอย่างของใบคำขอรับบริการ [{sample.request.request_no}] – งานบริการตรวจวิเคราะห์ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
            message = f'''เรียน {title_prefix}{sample.request.customer.customer_name}\n\n'''
            message += f'''ตามที่ท่านได้ส่งตัวอย่างเพื่อตรวจวิเคราะห์มายังคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล บัดนี้ทางเจ้าหน้าที่ได้ตรวจรับตัวอย่างของท่านเรียบร้อยแล้ว\n'''
            message += f'''เจ้าหน้าที่จะดำเนินการตรวจวิเคราะห์ตามขั้นตอน และจัดทำรายงานผลการตรวจวิเคราะห์ตามที่ตกลงไว้\n'''
            message += f'''ท่านสามารถติดตามสถานะการตรวจวิเคราะห์ได้ที่ลิงก์ด้านล่างนี้้\n'''
            message += f'''{link}\n\n'''
            message += f'''ขอขอบพระคุณที่ใช้บริการจากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล\n\n'''
            message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
            message += f'''ขอแสดงความนับถือ\n'''
            message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
            message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
            send_mail([contact_email], title, message)
            flash('ผลการตรวจสอบตัวอย่างได้รับการบันทึกเรียบร้อยแล้ว', 'success')
            return redirect(url_for('service_admin.sample_index', menu=menu))
    else:
        return render_template('service_admin/sample_verify_page.html', request_no=sample.request.request_no,
                               menu=menu)
    return render_template('service_admin/sample_verification_form.html', form=form, menu=menu,
                           request_no=sample.request.request_no)


@service_admin.route('/sample/appointment/view/<int:sample_id>')
@login_required
def view_sample_appointment(sample_id):
    menu = request.args.get('menu')
    sample = ServiceSample.query.get(sample_id)
    return render_template('service_admin/view_sample_appointment.html', sample=sample, menu=menu)


@service_admin.route('/test-item/index')
@login_required
def test_item_index():
    menu = request.args.get('menu')
    return render_template('service_admin/test_item_index.html', menu=menu)


@service_admin.route('/api/test-item/index')
def get_test_items():
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    sub_labs = []
    for a in admin:
        sub_labs.append(a.sub_lab.code)
    query = ServiceTestItem.query.filter(ServiceTestItem.request.has(or_(ServiceRequest.admin.has(id=current_user.id),
                                                                         ServiceRequest.lab.in_(sub_labs)
                                                                         )
                                                                     )
                                         )
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(
            or_(
                ServiceTestItem.quotation.has(ServiceQuotation.quotation_no.contains(search)),
                ServiceSample.request.has(ServiceRequest.request_no.contains(search)),
                ServiceSample.customer.has(ServiceCustomerAccount.has(ServiceCustomerInfo.cus_name.contains(search)))
            )
        )
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        html_blocks = []
        item_data = item.to_dict()
        for result in item.request.results:
            for i in result.result_items:
                if i.final_file:
                    download_file = url_for('service_admin.download_file', key=i.final_file,
                                            download_filename=f"{i.report_language} (ฉบับจริง).pdf")
                    html = f'''
                            <div class="field has-addons">
                                <div class="control">
                                    <a class="button is-small is-light is-link is-rounded" href="{download_file}">
                                        <span>{i.report_language} (ฉบับจริง)</span>
                                        <span class="icon is-small"><i class="fas fa-download"></i></span>
                                    </a>
                                </div>
                            </div>
                        '''
                elif i.draft_file:
                    download_file = url_for('service_admin.download_file', key=i.draft_file,
                                            download_filename=f"{i.report_language} (ฉบับร่าง).pdf")
                    html = f'''
                                            <div class="field has-addons">
                                                <div class="control">
                                                    <a class="button is-small is-light is-link is-rounded" href="{download_file}">
                                                        <span>{i.report_language} (ฉบับร่าง)</span>
                                                        <span class="icon is-small"><i class="fas fa-download"></i></span>
                                                    </a>
                                                </div>
                                            </div>
                                        '''
                else:
                    html = ''
                html_blocks.append(html)
        item_data['files'] = ''.join(html_blocks) if html_blocks else '<span class="has-text-grey-light is-italic">ไม่มีไฟล์</span>'
        data.append(item_data)
    return jsonify({'data': data,
                    'recordFiltered': total_filtered,
                    'recordTotal': records_total,
                    'draw': request.args.get('draw', type=int)
                    })


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
    menu = request.args.get('menu')
    service_request = ServiceRequest.query.get(request_id)
    sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab)
    datas = request_data(service_request)
    if service_request.results:
        for result in service_request.results:
            result_id = result.id
    else:
        result_id = None
    return render_template('service_admin/view_request.html', service_request=service_request, menu=menu,
                           sub_lab=sub_lab, datas=datas, result_id=result_id)


def generate_request_pdf(service_request):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 40, 40)
    if service_request.samples:
        sample_id = int(''.join(str(s.id) for s in service_request.samples)) if service_request.samples else None
        qr_buffer = BytesIO()
        qr_img = qrcode.make(url_for('service_admin.sample_verification', sample_id=sample_id, menu='sample',
                                     _external=True))
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        qr_code = Image(qr_buffer, width=80, height=80)
        qr_code.hAlign = 'LEFT'

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
    table_rows = []
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
                            # if f.label.text == 'ปริมาณสารสำคัญที่ออกฤทธ์' or f.label.text == 'สารสำคัญที่ออกฤทธิ์':
                            #     items = [item.strip() for item in str(f.data).split(',')]
                            #     values.append(f"{f.label.text}")
                            #     for item in items:
                            #         values.append(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- {item}")
                            if label.startswith("เชื้อ"):
                                germ = f"<i>{value}</i>"
                                value = re.sub(r'<i>(.*?)</i>', r"<font name='SarabunItalic'>\1</font>", germ)
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
                    label = field.label.text
                    value = ', '.join(field.data) if field.type == 'CheckboxField' else field.data
                    # if field.label.text == 'ปริมาณสารสำคัญที่ออกฤทธ์' or field.label.text == 'สารสำคัญที่ออกฤทธิ์':
                    #     items = [item.strip() for item in str(field.data).split(',')]
                    #     values.append(f"{field.label.text}")
                    #     for item in items:
                    #         values.append(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- {item}")
                    if label.startswith("เชื้อ"):
                        germ = f"<i>{value}</i>"
                        value = re.sub(r'<i>(.*?)</i>', r"<font name='SarabunItalic'>\1</font>", germ)
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

    if service_request.report_languages:
        values.append("ใบรายงานผล : " + ", ".join([rl.report_language.item for rl in service_request.report_languages]))

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
                เลขที่ใบคำขอ &nbsp;  <u>&nbsp;{request_no}&nbsp;&nbsp;</u><br/>
                วันที่รับตัวอย่าง <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u><br/>
                วันที่รายงานผล <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u><br/>
                </font></para>'''.format(request_no=service_request.request_no)

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

    center_style = ParagraphStyle(
        'CenterStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=12,
        leading=25,
        alignment=TA_CENTER
    )

    customer = '''<para>ข้อมูลผู้ประสานงาน<br/>
                                ชื่อ-นามสกุล : {cus_contact}<br/>
                                เลขประจำตัวผู้เสียภาษี : {taxpayer_identification_no}<br/>
                                เบอร์โทรศัพท์ : {phone_number}<br/>
                                อีเมล : {email}
                            </para>
                            '''.format(cus_contact=service_request.customer.customer_name,
                                       taxpayer_identification_no=service_request.customer.customer_info.taxpayer_identification_no,
                                       phone_number=service_request.customer.contact_phone_number,
                                       email=service_request.customer.contact_email)

    customer_table = Table([[Paragraph(customer, style=detail_style)]], colWidths=[530])

    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    district_title = 'เขต' if service_request.document_address.province.name == 'กรุงเทพมหานคร' else 'อำเภอ'
    subdistrict_title = 'แขวง' if service_request.document_address.province.name == 'กรุงเทพมหานคร' else 'ตำบล',
    document_address = '''<para>ข้อมูลที่อยู่จัดส่งเอกสาร<br/>
                                    ถึง : {name}<br/>
                                    ที่อยู่ : {address} {subdistrict_title}{subdistrict} {district_title}{district} จังหวัด{province} {zipcode}<br/>
                                    เบอร์โทรศัพท์ : {phone_number}<br/>
                                    อีเมล : {email}
                                </para>
                                '''.format(name=service_request.document_address.name,
                                           address=service_request.document_address.address,
                                           subdistrict_title=subdistrict_title,
                                           subdistrict=service_request.document_address.subdistrict,
                                           district_title=district_title,
                                           district=service_request.document_address.district,
                                           province=service_request.document_address.province,
                                           zipcode=service_request.document_address.zipcode,
                                           phone_number=service_request.document_address.phone_number,
                                           email=service_request.customer.contact_email)

    document_address_table = Table([[Paragraph(document_address, style=detail_style)]], colWidths=[265])

    district_title = 'เขต' if service_request.quotation_address.province.name == 'กรุงเทพมหานคร' else 'อำเภอ'
    subdistrict_title = 'แขวง' if service_request.quotation_address.province.name == 'กรุงเทพมหานคร' else 'ตำบล',
    quotation_address = '''<para>ข้อมูลที่อยู่ใบเสนอราคา/ใบแจ้งหนี้/ใบกำกับภาษี<br/>
                                        ออกในนาม : {name}<br/>
                                        ที่อยู่ : {address} {subdistrict_title}{subdistrict} {district_title}{district} จังหวัด{province} {zipcode}<br/>
                                        เลขประจำตัวผู้เสียภาษีอากร : {taxpayer_identification_no}<br/>
                                        เบอร์โทรศัพท์ : {phone_number}<br/>
                                        อีเมล : {email}
                                    </para>
                                    '''.format(name=service_request.quotation_address.name,
                                               address=service_request.quotation_address.address,
                                               subdistrict_title=subdistrict_title,
                                               subdistrict=service_request.quotation_address.subdistrict,
                                               district_title=district_title,
                                               district=service_request.quotation_address.district,
                                               province=service_request.quotation_address.province,
                                               zipcode=service_request.quotation_address.zipcode,
                                               taxpayer_identification_no=service_request.quotation_address.taxpayer_identification_no,
                                               phone_number=service_request.quotation_address.phone_number,
                                               email=service_request.customer.contact_email)

    quotation_address_table = Table([[Paragraph(quotation_address, style=detail_style)]], colWidths=[265])

    address_table = Table(
        [[quotation_address_table, document_address_table]],
        colWidths=[265, 265]
    )

    address_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (0, 0), 0.5, colors.grey),
        ('BOX', (1, 0), (1, 0), 0.5, colors.grey),
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
    data.append(KeepTogether(address_table))
    data.append(KeepTogether(customer_table))

    details = 'ข้อมูลผลิตภัณฑ์' + "<br/>" + "<br/>".join(values)
    first_page_limit = 410
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

    first_page = Paragraph("<br/>".join(first_page_lines), style=detail_style)
    first_page_paragraph = [[first_page]]
    first_page_table = Table(first_page_paragraph, colWidths=[530])
    first_page_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('LINEBELOW', (0, 0), (-1, 0), 0, colors.white),
        ('LINEABOVE', (0, 1), (-1, 1), 0, colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    data.append(KeepTogether(first_page_table))

    if remaining_text:
        remaining_page = Paragraph(remaining_text, style=detail_style)
        remaining_page_paragraph = [[remaining_page]]
        data.append(PageBreak())
        remaining_page_table = Table(remaining_page_paragraph, colWidths=[530])
        remaining_page_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('LINEBELOW', (0, 0), (-1, 0), 0, colors.white),
            ('LINEABOVE', (0, 1), (-1, 1), 0, colors.white),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        data.append(KeepTogether(Spacer(20, 20)))
        data.append(KeepTogether(content_header))
        data.append(KeepTogether(Spacer(7, 7)))
        data.append(KeepTogether(remaining_page_table))

    height = 0
    if table_rows:
        height = (len(table_rows) + 1) * detail_style.leading
        header_table = [Paragraph(f"<b>{key}</b>", detail_style) for key in table_keys]
        content_table = [header_table]
        for row in table_rows:
            row_data = [Paragraph(str(row.get(k, '')), detail_style) for k in table_keys]
            content_table.append(row_data)

        germ_table = Table(content_table, colWidths=[530 / len(table_keys)])
        germ_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        total_height = current_length + height
        if total_height > first_page_limit and not remaining_text:
            data.append(PageBreak())
            data.append(Spacer(20, 20))
            data.append(content_header)
            data.append(Spacer(7, 7))
        data.append(germ_table)

    lab_test = '''<para><font size=12>
                    สำหรับเจ้าหน้าที่<br/>
                    Lab No. : _________________________________________________________________________________________________________________<br/>
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
        lab_table_height = detail_style.leading * lab_test.count('<br/>')
        if not remaining_text and (height + lab_table_height > first_page_limit):
            data.append(PageBreak())
            data.append(Spacer(20, 20))
            data.append(content_header)
            data.append(Spacer(7, 7))
        data.append(lab_test_table)

    if service_request.samples:
        sign_table = Table([
            [Paragraph("ผู้ส่งตัวอย่าง/Sent by", center_style), Paragraph('', center_style)],
            [Paragraph("(", center_style), Paragraph(')', center_style)],
            [Paragraph("วันที่/Date", center_style), Paragraph('', center_style)],
            [Spacer(1, 50)],
            [Paragraph("ผู้รับตัวอย่าง/Received by", center_style), Paragraph('', center_style)],
            [Paragraph("(", center_style), Paragraph(')', center_style)],
            [Paragraph("วันที่/Date", center_style), Paragraph('', center_style)]],
            colWidths=[160, 160])

        sign_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 0),
        ]))

        qr_code_label = Paragraph("QR Code สำหรับเจ้าหน้าที่ตรวจรับตัวอย่าง", style=center_style)
        qr_code_table = Table([
            [qr_code_label],
            [qr_code],
        ], colWidths=[180])
        qr_code_table.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (0, 0), 16),
            ('RIGHTPADDING', (0, 1), (0, 1), 0),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        footer_table = Table([
            [qr_code_table, Spacer(10, 0), sign_table]
        ], colWidths=[180, 40, 330])
        footer_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ]))

        data.append(Spacer(1, 50))
        data.append(footer_table)
    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    buffer.seek(0)
    return buffer


@service_admin.route('/request/pdf/<int:request_id>', methods=['GET'])
@login_required
def export_request_pdf(request_id):
    service_request = ServiceRequest.query.get(request_id)
    buffer = generate_request_pdf(service_request)
    return send_file(buffer, download_name='Request_form.pdf', as_attachment=True)


@service_admin.route('/aws-s3/download/<key>', methods=['GET'])
def download_file(key):
    download_filename = request.args.get('download_filename')
    s3_client = boto3.client(
        's3',
        region_name=os.getenv('BUCKETEER_AWS_REGION'),
        aws_access_key_id=os.getenv('BUCKETEER_AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('BUCKETEER_AWS_SECRET_ACCESS_KEY')
    )
    outfile = BytesIO()
    s3_client.download_fileobj(os.getenv('BUCKETEER_BUCKET_NAME'), key, outfile)
    outfile.seek(0)
    return send_file(outfile, download_name=download_filename, as_attachment=True)


@service_admin.route('/result/index')
@login_required
def result_index():
    menu = request.args.get('menu')
    return render_template('service_admin/result_index.html', menu=menu)


@service_admin.route('/api/result/index')
def get_results():
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    sub_labs = []
    for a in admin:
        sub_labs.append(a.sub_lab.code)
    query = ServiceResult.query.filter(or_(ServiceResult.creator_id == current_user.id,
                                           ServiceResult.request.has(ServiceRequest.lab.in_(sub_labs)
                                                                     )
                                           )
                                       )
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ServiceResult.request.has(ServiceRequest.request_no).contains(search))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        html_blocks = []
        for i in item.result_items:
            if i.final_file:
                download_file = url_for('service_admin.download_file', key=i.final_file,
                                        download_filename=f"{i.report_language} (ฉบับจริง).pdf")
                html = f'''
                    <div class="field has-addons">
                        <div class="control">
                            <a class="button is-small is-light is-link is-rounded" href="{download_file}">
                                <span>{i.report_language} (ฉบับจริง)</span>
                                <span class="icon is-small"><i class="fas fa-download"></i></span>
                            </a>
                        </div>
                    </div>
                '''
            elif i.draft_file:
                download_file = url_for('service_admin.download_file', key=i.draft_file,
                                        download_filename=f"{i.report_language} (ฉบับร่าง).pdf")
                html = f'''
                                    <div class="field has-addons">
                                        <div class="control">
                                            <a class="button is-small is-light is-link is-rounded" href="{download_file}">
                                                <span>{i.report_language} (ฉบับร่าง)</span>
                                                <span class="icon is-small"><i class="fas fa-download"></i></span>
                                            </a>
                                        </div>
                                    </div>
                                '''
            else:
                html = ''
            html_blocks.append(html)
        item_data['files'] = ''.join(
            html_blocks) if html_blocks else '<span class="has-text-grey-light is-italic">ไม่มีไฟล์</span>'
        data.append(item_data)
    return jsonify({'data': data,
                    'recordFiltered': total_filtered,
                    'recordTotal': records_total,
                    'draw': request.args.get('draw', type=int)
                    })


@service_admin.route('/result/add', methods=['GET', 'POST'])
@service_admin.route('/result/edit/<int:result_id>', methods=['GET', 'POST'])
@login_required
def create_result(result_id=None):
    menu = request.args.get('menu')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    if not result_id:
        result = ServiceResult.query.filter_by(request_id=request_id).first()
        if not result:
            if request.method == 'GET':
                result_list = ServiceResult(request_id=request_id, released_at=arrow.now('Asia/Bangkok').datetime,
                                            creator_id=current_user.id)
                db.session.add(result_list)
                if service_request.report_languages:
                    for rl in service_request.report_languages:
                        result_item = ServiceResultItem(report_language=rl.report_language.item, result=result_list,
                                                        released_at=arrow.now('Asia/Bangkok').datetime,
                                                        creator_id=current_user.id)
                        db.session.add(result_item)
                        db.session.commit()
                result = ServiceResult.query.get(result_list.id)
            else:
                result = ServiceResult.query.filter_by(request_id=request_id).first()
    else:
        result = ServiceResult.query.get(result_id)
    if request.method == 'POST':
        for item in result.result_items:
            file = request.files.get(f'file_{item.id}')
            if file and allowed_file(file.filename):
                mime_type = file.mimetype
                file_name = '{}.{}'.format(item.report_language,
                                           file.filename.split('.')[-1])
                file_data = file.stream.read()
                response = s3.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=file_name,
                    Body=file_data,
                    ContentType=mime_type
                )
                item.url = file_name
                if result_id:
                    item.modified_at = arrow.now('Asia/Bangkok').datetime
                    item.result.modified_at = arrow.now('Asia/Bangkok').datetime
                db.session.add(item)
                db.session.commit()
        uploaded_all = all(item.url for item in result.result_items)
        if uploaded_all:
            status_id = get_status(12)
            result.status_id = status_id
            service_request.status_id = status_id
            scheme = 'http' if current_app.debug else 'https'
            if not result.is_sent_email:
                customer_name = result.request.customer.customer_name.replace(' ', '_')
                contact_email = result.request.customer.contact_email if result.request.customer.contact_email else result.request.customer.email
                title_prefix = 'คุณ' if result.request.customer.customer_info.type.type == 'บุคคล' else ''
                title = f'''แจ้งออกร่างรายงานผลการทดสอบของใบคำขอรับบริการ [{result.request.request_no}] – งานบริการตรวจวิเคราะห์ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
                message = f'''เรียน {title_prefix}{customer_name}\n\n'''
                message += f'''ตามที่ท่านได้ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล ใบคำขอบริการเลขที่ {result.request.request_no}'''
                message += f''' ขณะนี้ได้จัดทำร่างรายงานผลการทดสอบแล้ว และได้แนบไฟล์ร่างรายงานมาพร้อมกับอีเมลฉบับนี้'''
                message += f''' กรุณาตรวจสอบความถูกต้องของข้อมูลในร่างรายงาน และดำเนินการยืนยันตามลิงก์ด้านล่าง\n\n'''
                message += f'''ท่านสามารถยืนยันได้ที่ลิงก์ด้านล่าง'''
                message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
                message += f'''ขอแสดงความนับถือ\n'''
                message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
                message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
                send_mail([contact_email], title, message)
            result.is_sent_email = True
        else:
            status_id = get_status(11)
            result.status_id = status_id
            service_request.status_id = status_id
        db.session.add(result)
        db.session.add(service_request)
        db.session.commit()
        flash("บันทึกไฟล์เรียบร้อยแล้ว", "success")
        return redirect(url_for('service_admin.test_item_index', menu='test_item'))
    return render_template('service_admin/create_result.html', result_id=result_id, menu=menu,
                           result=result)


@service_admin.route('/result/delete/<int:item_id>', methods=['GET', 'POST'])
def delete_result_file(item_id):
    status_id = get_status(11)
    item = ServiceResultItem.query.get(item_id)
    item.url = None
    item.modified_at = arrow.now('Asia/Bangkok').datetime
    item.result.status_id = status_id
    item.result.modified_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(item)
    db.session.commit()
    flash("ลบไฟล์เรียบร้อยแล้ว", "success")
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@service_admin.route('/result/tracking_number/add/<int:result_id>', methods=['GET', 'POST'])
def add_tracking_number(result_id):
    menu = request.args.get('menu')
    result = ServiceResult.query.get(result_id)
    form = ServiceResultForm(obj=result)
    if form.validate_on_submit():
        form.populate_obj(result)
        db.session.add(result)
        db.session.commit()
        flash('อัพเดตข้อมูลสำเร็จ', 'success')
        return redirect(url_for('service_admin.result_index', menu=menu))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('service_admin/add_tracking_number_for_result.html', form=form, menu=menu,
                           result_id=result_id)


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
                address.address_type = 'document'
                address.taxpayer_identification_no = None
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
@login_required
def address_index(customer_id):
    customer = ServiceCustomerInfo.query.get(customer_id)
    addresses = ServiceCustomerAddress.query.filter_by(customer_id=customer_id)
    return render_template('service_admin/address_index.html', addresses=addresses, customer_id=customer_id,
                           customer=customer)


@service_admin.route('/invoice/index')
@login_required
def invoice_index():
    menu = request.args.get('menu')
    is_central_admin = ServiceAdmin.query.filter_by(admin_id=current_user.id, is_central_admin=True).first()
    return render_template('service_admin/invoice_index.html', menu=menu,
                           is_central_admin=is_central_admin)


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
        if item.payments:
            for payment in item.payments:
                if payment.slip:
                    item_data['slip'] = generate_url(payment.slip)
                else:
                    item_data['slip'] = None
        data.append(item_data)
    return jsonify({'data': data,
                    'recordFiltered': total_filtered,
                    'recordTotal': records_total,
                    'draw': request.args.get('draw', type=int)
                    })


@service_admin.route('/invoice/add/<int:quotation_id>', methods=['GET', 'POST'])
@login_required
def create_invoice(quotation_id):
    menu = request.args.get('menu')
    quotation = ServiceQuotation.query.get(quotation_id)
    sub_lab = ServiceSubLab.query.filter_by(code=quotation.request.lab).first()
    if not quotation.invoices:
        invoice_no = ServiceNumberID.get_number('IV', db, lab=sub_lab.lab.code if sub_lab and sub_lab.lab.code == 'protein' \
            else quotation.request.lab)
        invoice = ServiceInvoice(invoice_no=invoice_no.number, quotation_id=quotation_id, name=quotation.name,
                                 address=quotation.address, taxpayer_identification_no=quotation.taxpayer_identification_no,
                                 created_at=arrow.now('Asia/Bangkok').datetime,
                                 creator_id=current_user.id)
        invoice_no.count += 1
        db.session.add(invoice)
        for quotation_item in quotation.quotation_items:
            invoice_item = ServiceInvoiceItem(sequence=quotation_item.sequence, discount_type=quotation_item.discount_type,
                                              invoice_id=invoice.id, item=quotation_item.item,
                                              quantity=quotation_item.quantity,
                                              unit_price=quotation_item.unit_price, total_price=quotation_item.total_price,
                                              discount=quotation_item.discount)
            db.session.add(invoice_item)
            db.session.commit()
        db.session.commit()
        status_id = get_status(16)
        invoice.quotation.request.status_id = status_id
        db.session.add(invoice)
        db.session.commit()
        flash('สร้างใบแจ้งหนี้สำเร็จ', 'success')
        return redirect(url_for('service_admin.view_invoice', invoice_id=invoice.id, menu=menu))
    else:
        return render_template('service_admin/invoice_created_confirmation_page.html', menu=menu,
                               invoice_id=[invoice.id for invoice in quotation.invoices])


@service_admin.route('/invoice/approve/<int:invoice_id>', methods=['GET', 'POST'])
def approve_invoice(invoice_id):
    menu = request.args.get('menu')
    admin = request.args.get('admin')
    invoice = ServiceInvoice.query.get(invoice_id)
    scheme = 'http' if current_app.debug else 'https'
    admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=invoice.quotation.request.lab)).all()
    sub_lab = ServiceSubLab.query.filter_by(code=invoice.quotation.request.lab).first()
    invoice_url = url_for("service_admin.view_invoice", invoice_id=invoice.id, menu=menu, _external=True,
                          _scheme=scheme)
    customer_name = invoice.customer_name.replace(' ', '_')
    title_prefix = 'คุณ' if invoice.quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
    if admin == 'assistant':
        status_id = get_status(19)
        invoice.quotation.request.status_id = status_id
        invoice.assistant_approved_at = arrow.now('Asia/Bangkok').datetime
        invoice.assistant_id = current_user.id
        db.session.add(invoice)
        db.session.commit()
        if admins:
            email = [a.admin.email + '@mahidol.ac.th' for a in admins if a.is_central_admin]
            if email:
                # invoice_file_url = url_for('service_admin.export_invoice_pdf', invoice_id=invoice.id, _external=True,
                #               _scheme=scheme)
                title = f'[{invoice.invoice_no}] ใบแจ้งหนี้ - {title_prefix}{customer_name} ({invoice.name}) | แจ้งดำเนินการพิมพ์และนำเข้าใบแจ้งหนี้'
                message = f'''เรียน แอดมินส่วนกลาง\n\n'''
                message += f'''ตามที่มีการออกใบแจ้งหนี้เลขที่ : {invoice.invoice_no}\n'''
                message += f'''ลูกค้า : {invoice.customer_name}\n'''
                message += f'''ในนาม : {invoice.name}\n'''
                message += f'''อ้างอิงจาก : \n'''
                message += f'''- ใบคำขอรับบริการเลขที่ : {invoice.quotation.request.request_no}\n'''
                message += f'''- ใบเสนอราคาเลขที ่: {invoice.quotation.quotation_no}\n\n'''
                message += f'''กรุณาดำเนินการพิมพ์และนำเข้าใบแจ้งหนี้ดังกล่าวเข้าสู่ระบบ e-Office เพื่อให้คณบดีลงนามและออกเลข อว. ต่อไป '''
                message += f'''หลังจากดำเนินการแล้ว กรุณาอัปโหลดไฟล์ใบแจ้งหนี้กลับเข้าสู่ระบบบริการวิชาการ\n'''
                message += f'''สามารถพิมพ์ใบแจ้งหนี้ได้ที่ลิงก์ด้านล่าง\n'''
                message += f'''{invoice_url}\n\n'''
                message += f'''ผู้ประสานงาน\n'''
                message += f'''{invoice.customer_name}\n'''
                message += f'''เบอร์โทร {invoice.contact_phone_number}\n'''
                message += f'''ระบบบริการวิชาการ'''
                send_mail(email, title, message)
                if not current_app.debug:
                    msg = (
                        'แจ้งแอดมินส่วนกลางดำเนินการพิมพ์และนำเข้าใบแจ้งหนี้เลขที่ {}\n\n'
                        'เรียน แอดมินส่วนกลาง\n\n'
                        'ตามที่มีการออกใบแจ้งหนี้เลขที่ : {}\n'

                        'ลูกค้า : {}\n'
                        'ในนาม : {}\n'
                        'อ้างอิงจาก : \n'
                        '- ใบคำขอรับบริการเลขที่ : {}\n'
                        '- ใบเสนอราคาเลขที่ : {}\n\n'
                        'กรุณาดำเนินการพิมพ์และนำเข้าใบแจ้งหนี้ดังกล่าวเข้าสู่ระบบ e-Office เพื่อให้คณบดีลงนามและออกเลข อว. ต่อไป'
                        'หลังจากดำเนินการแล้ว กรุณาอัปโหลดไฟล์ใบแจ้งหนี้กลับเข้าสู่ระบบบริการวิชาการ\n\n'
                        'สามารถพิมพ์ใบแจ้งหนี้ได้ที่ลิงก์ด้านล่าง\n'
                        '{}\n\n'
                        '\ู้ประสานงาน\n'
                        '{}\n'
                        'เบอร์โทร {}\n'
                        'ระบบงานบริการวิชาการ'.format(invoice.invoice_no, invoice.invoice_no,
                                                      invoice.quotation.request.request_no,
                                                      invoice.quotation.quotation_no, invoice.customer_name,
                                                      invoice.name,
                                                      invoice_url, invoice.customer_name, invoice.contact_phone_number))
                    for a in admins:
                        if a.is_central_admin:
                            try:
                                line_bot_api.push_message(to=sub_lab.approver.line_id,
                                                          messages=TextSendMessage(text=msg))
                            except LineBotApiError:
                                pass
    elif admin == 'supervisor':
        status_id = get_status(18)
        invoice.quotation.request.status_id = status_id
        invoice.head_approved_at = arrow.now('Asia/Bangkok').datetime
        invoice.head_id = current_user.id
        if sub_lab.approver:
            title = f'[{invoice.invoice_no}] ใบแจ้งหนี้ - {title_prefix}{customer_name} ({invoice.name}) | แจ้งอนุมัติใบแจ้งหนี้'
            message = f'''เรียน ผู้ช่วยคณบดีฝ่ายบริการวิชาการ\n\n'''
            message += f'''ใบแจ้งหนี้เลขที่ : {invoice.invoice_no}\n'''
            message += f'''ลูกค้า : {invoice.customer_name}\n'''
            message += f'''ในนาม : {invoice.name}\n'''
            message += f'''อ้างอิงจาก : \n'''
            message += f'''- ใบคำขอรับบริการเลขที่ : {invoice.quotation.request.request_no}\n'''
            message += f'''- ใบเสนอราคาเลขที ่: {invoice.quotation.quotation_no}\n\n'''
            message += f'''ที่รอดำเนินการอนุมัติใบแจ้งหนี้\n'''
            message += f'''กรุณาตรวจสอบและดำเนินการได้ที่ลิงก์ด้านล่าง\n'''
            message += f'''{invoice_url}\n\n'''
            message += f'''ผู้ประสานงาน\n'''
            message += f'''{invoice.customer_name}\n'''
            message += f'''เบอร์โทร {invoice.contact_phone_number}\n'''
            message += f'''ระบบบริการวิชาการ'''
            send_mail([sub_lab.approver.email + '@mahidol.ac.th'], title, message)
        if not current_app.debug:
            msg = ('แจ้งขออนุมัติใบแจ้งหนี้เลขที่ {}' \
                   '\n\nเรียน ผู้ช่วยคณบดีฝ่ายบริการวิชาการ' \
                   '\n\nใบแจ้งหนี้เลขที่ : {}' \
                   '\nลูกค้า : {}' \
                   '\nในนาม : {}' \
                   '\nอ้างอิงจาก : ' \
                   '\n- ใบคำขอรับบริการเลขที่ : {}'
                   '\n- ใบเสนอราคาเลขที่ : {}'
                   '\n\nที่รอดำเนินการอนุมัติใบแจ้งหนี้' \
                   '\nกรุณาตรวจสอบและดำเนินการได้ที่ลิงก์ด้านล่าง' \
                   '\n{}' \
                   '\n\nผู้ประสานงาน' \
                   '\n{}' \
                   '\nเบอร์โทร {}' \
                   '\nระบบงานบริการวิชาการ'.format(invoice.invoice_no, invoice.invoice_no,
                                                   invoice.quotation.request.request_no,
                                                   invoice.quotation.quotation_no, invoice.customer_name,
                                                   invoice.name, invoice_url, invoice.customer_name,
                                                   invoice.contact_phone_number))
            try:
                line_bot_api.push_message(to=sub_lab.approver.line_id, messages=TextSendMessage(text=msg))
            except LineBotApiError:
                pass
    else:
        status_id = get_status(17)
        invoice.sent_at = arrow.now('Asia/Bangkok').datetime
        invoice.sender_id = current_user.id
        invoice.quotation.request.status_id = status_id
        if admins:
            email = [a.admin.email + '@mahidol.ac.th' for a in admins if a.is_supervisor]
            if email:
                title = f'[{invoice.invoice_no}] ใบแจ้งหนี้ - {title_prefix}{customer_name} ({invoice.name}) | แจ้งอนุมัติใบแจ้งหนี้'
                message = f'''เรียน หัวหน้าห้องปฏิบัติการ\n\n'''
                message += f'''ใบแจ้งหนี้เลขที่ : {invoice.invoice_no}\n'''
                message += f'''ลูกค้า : {invoice.customer_name}\n'''
                message += f'''ในนาม : {invoice.name}\n'''
                message += f'''อ้างอิงจาก : \n'''
                message += f'''- ใบคำขอรับบริการเลขที่ : {invoice.quotation.request.request_no}\n'''
                message += f'''- ใบเสนอราคาเลขที ่: {invoice.quotation.quotation_no}\n\n'''
                message += f'''ที่รอดำเนินการอนุมัติใบแจ้งหนี้\n'''
                message += f'''กรุณาตรวจสอบและดำเนินการได้ที่ลิงก์ด้านล่าง\n'''
                message += f'''{invoice_url}\n\n'''
                message += f'''ผู้ประสานงาน\n'''
                message += f'''{invoice.customer_name}\n'''
                message += f'''เบอร์โทร {invoice.contact_phone_number}\n'''
                message += f'''ระบบบริการวิชาการ'''
                send_mail(email, title, message)
                if not current_app.debug:
                    msg = ('แจ้งขออนุมัติใบแจ้งหนี้เลขที่ {}' \
                           '\n\nเรียน หัวหน้าห้องปฏิบัติการ' \
                           '\n\nใบแจ้งหนี้เลขที่ : {}' \
                           '\nลูกค้า : {}' \
                           '\nในนาม : {}' \
                           '\nอ้างอิงจาก : ' \
                           '\n- ใบคำขอรับบริการเลขที่ : {}'
                           '\n- ใบเสนอราคาเลขที่ : {}'
                           '\n\nที่รอดำเนินการอนุมัติใบแจ้งหนี้' \
                           '\nกรุณาตรวจสอบและดำเนินการได้ที่ลิงก์ด้านล่าง' \
                           '\n{}' \
                           '\n\nผู้ประสานงาน' \
                           '\n{}' \
                           '\nเบอร์โทร {}' \
                           '\nระบบงานบริการวิชาการ'.format(invoice.invoice_no, invoice.invoice_no,
                                                           invoice.quotation.request.request_no,
                                                           invoice.quotation.quotation_no, invoice.customer_name,
                                                           invoice.name, invoice_url, invoice.customer_name,
                                                           invoice.contact_phone_number))
                    for a in admins:
                        if a.is_supervisor:
                            try:
                                line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                            except LineBotApiError:
                                pass
    db.session.add(invoice)
    db.session.commit()
    flash('อนุมัติใบแจ้งหนี้สำเร็จ', 'success')
    return render_template('service_admin/invoice_index.html', menu=menu)


@service_admin.route('/invoice/file/add/<int:invoice_id>', methods=['GET', 'POST'])
def upload_invoice_file(invoice_id):
    menu = request.args.get('menu')
    invoice = ServiceInvoice.query.get(invoice_id)
    form = ServiceInvoiceForm(obj=invoice)
    if form.validate_on_submit():
        form.populate_obj(invoice)
        status_id = get_status(20)
        file = form.file_upload.data
        invoice.quotation.request.status_id = status_id
        invoice.file_attached_id = current_user.id
        invoice.file_attached_at = arrow.now('Asia/Bangkok').datetime
        invoice.due_date = arrow.get(invoice.file_attached_at).shift(days=+30).datetime
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
            invoice.file = file_name
            db.session.add(invoice)
            db.session.commit()
            scheme = 'http' if current_app.debug else 'https'
            title_prefix = 'คุณ' if invoice.quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
            contact_email = invoice.quotation.request.customer.contact_email if invoice.quotation.request.customer.contact_email else invoice.quotation.request.customer.email
            org = Org.query.filter_by(name='หน่วยการเงินและบัญชี').first()
            staff = StaffAccount.get_account_by_email(org.head)
            sub_lab = ServiceSubLab.query.filter_by(code=invoice.quotation.request.lab).first()
            invoice_url = url_for("academic_services.view_invoice", invoice_id=invoice.id, menu='invoice',
                                  _external=True,
                                  _scheme=scheme)
            msg = (f'แจ้งออกใบแจ้งหนี้เลขที่ {invoice.invoice_no}\n\n'
                   f'เรียน ฝ่ายการเงิน\n\n'
                   f'หน่วยงาน {sub_lab.sub_lab} ได้ดำเนินการออกใบแจ้งหนี้เลขที่ {invoice.invoice_no} เรียบร้อยแล้ว\n'
                   f'วันที่ออก : {invoice.file_attached_at.strftime("%d/%m/%Y")}\n'
                   f'จำนวนเงิน : {invoice.grand_total():,.2f} บาท\n'
                   f'กรุณาดำเนินการตรวจสอบและเตรียมออกใบเสร็จรับเงินเมื่อได้รับการชำระเงินจากลูกค้าตามขั้นตอนที่กำหนด\n\n'
                   f'ขอบคุณค่ะ\n'
                   f'ระบบงานบริการวิชาการ'
                   )
            title = f'''แจ้งออกใบแจ้งหนี้ [{invoice.invoice_no}] – งานบริการตรวจวิเคราะห์ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
            message = f'''เรียน {title_prefix}{invoice.customer_name}\n\n'''
            message += f'''ตามที่ท่านใช้บริการจากหน่วยงานตรวจวิเคราะห์ของคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล ทางเจ้าหน้าที่ได้ดำเนินการออกใบแจ้งหนี้เลขที่ {invoice.invoice_no}'''
            message += f''' ของใบคำขอรับบริการเลขที่ {invoice.quotation.request.request_no} และของใบเสนอราคาเลขที่ {invoice.quotation.quotation_no} เรียบร้อยแล้ว กรุณาดำเนินการชำระเงินภายใน 30 วันนับจากวันที่ออกใบแจ้งหนี้\n'''
            message += f'''ท่านสามารถตรวจสอบรายละเอียดใบแจ้งหนี้ได้จากลิงก์ด้านล่าง\n'''
            message += f'''{invoice_url}\n\n'''
            message += f'''ขอขอบพระคุณที่ใช้บริการจากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล\n\n'''
            message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
            message += f'''ขอแสดงความนับถือ\n'''
            message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
            message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
            send_mail([contact_email], title, message)
            if not current_app.debug:
                try:
                    line_bot_api.push_message(to=staff.line_id, messages=TextSendMessage(text=msg))
                except LineBotApiError:
                    pass
            flash('บันทึกข้อมูลสำเร็จ', 'success')
            return redirect(url_for('service_admin.invoice_index', menu=menu))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('service_admin/upload_invoice_file.html', form=form, invoice_id=invoice_id,
                           menu=menu, invoice=invoice)


@service_admin.route('/invoice/view/<int:invoice_id>', methods=['GET'])
@login_required
def view_invoice(invoice_id):
    menu = request.args.get('menu')
    invoice = ServiceInvoice.query.get(invoice_id)
    sub_lab = ServiceSubLab.query.filter_by(code=invoice.quotation.request.lab).first()
    admin_lab = ServiceAdmin.query.filter(ServiceAdmin.admin_id == current_user.id,
                                          ServiceAdmin.sub_lab.has(ServiceSubLab.code == sub_lab.code))
    admin = any(a for a in admin_lab if not a.is_supervisor)
    supervisor = any(a.is_supervisor for a in admin_lab)
    assistant = sub_lab.approver if sub_lab.approver_id == current_user.id else None
    dean = sub_lab.signer if sub_lab.signer_id == current_user.id else None
    central_admin = any(a.is_central_admin for a in admin_lab)
    return render_template('service_admin/view_invoice.html', invoice=invoice, admin=admin,
                           supervisor=supervisor, assistant=assistant, dean=dean, sub_lab=sub_lab,
                           central_admin=central_admin, menu=menu)


def generate_invoice_pdf(invoice, qr_image_base64=None):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 70, 70)

    lab = ServiceLab.query.filter_by(code=invoice.quotation.request.lab).first()
    sub_lab = ServiceSubLab.query.filter_by(code=invoice.quotation.request.lab).first()

    def all_page_setup(canvas, doc):
        canvas.saveState()
        # logo_image = ImageReader('app/static/img/mu-watermark.png')
        # canvas.drawImage(logo_image, 140, 265, mask='auto')
        canvas.restoreState()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer,
                            rightMargin=20,
                            leftMargin=20,
                            topMargin=10,
                            bottomMargin=10,
                            )
    data = []

    bold_style = ParagraphStyle(
        'BoldStyle',
        parent=style_sheet['ThaiStyleBold'],
        leading=15,
        alignment=TA_RIGHT
    )

    affiliation = '''<para><font size=12>
                           คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>
                           999 ต.ศาลายา อ.พุทธมณฑล จ.นครปฐม 73170<br/>
                           โทร 0-2441-4371-9 ต่อ 2820 2830<br/>
                           เลขประจำตัวผู้เสียภาษี 0994000158378
                           </font></para>
                           '''

    lab_address = '''<para><font size=13>
                        {address}
                        </font></para>'''.format(address=lab.address if lab else sub_lab.address)

    invoice_no = '''<br/><font size=12>
                    เลขที่/No. {invoice_no}
                    </font>
                    '''.format(invoice_no=invoice.invoice_no)

    header_content_ori = [[[],
                           [logo],
                           [],
                           [Paragraph(affiliation, style=bold_style),
                            Paragraph(invoice_no, style=style_sheet['ThaiStyleRight'])]]]

    header_styles = TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
    ])

    header_ori = Table(header_content_ori, colWidths=[180, 200, 0, 180])

    header_ori.hAlign = 'CENTER'
    header_ori.setStyle(header_styles)

    detail_style = ParagraphStyle(
        'DetailStyle',
        parent=style_sheet['ThaiStyle'],
        leading=17
    )

    customer = '''<para><font size=14>
                    ที่ อว. {mhesi_no}<br/>
                    วันที่ <br/>
                    เรื่อง ใบแจ้งหนี้ค่าบริการตรวจวิเคราะห์ทางห้องปฏิบัติการ<br/>
                    เรียน {customer}<br/>
                    ที่อยู่ {address}<br/>
                    เลขประจำตัวผู้เสียภาษี {taxpayer_identification_no}
                    </font></para>
                    '''.format(mhesi_no='78.04/',
                               customer=invoice.name,
                               address=invoice.address,
                               taxpayer_identification_no=invoice.taxpayer_identification_no)

    customer_table = Table([[Paragraph(customer, style=detail_style)]], colWidths=[540, 280])

    customer_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP')]))

    label_style = ParagraphStyle(
        'LabelStyle',
        parent=style_sheet['ThaiStyleBold'],
        alignment=TA_CENTER
    )
    items = [[Paragraph('<font size=13>ลำดับ<br/>No</font>', style=label_style),
              Paragraph('<font size=13>รายการ<br/>Description</font>', style=label_style),
              Paragraph('<font size=13>จำนวน<br/>Quantity</font>', style=label_style),
              Paragraph('<font size=13>ราคา<br/>Unit Price</font>', style=label_style),
              Paragraph('<font size=13>จำนวนเงิน<br/>Amount</font>', style=label_style),
              ]]

    for n, item in enumerate(sorted(invoice.invoice_items, key=lambda x: x.sequence), start=1):
        lab_item = re.sub(r'<i>(.*?)</i>', r"<font name='SarabunItalic'>\1</font>", item.item)
        item_record = [Paragraph('<font size=12>{}</font>'.format(n), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{}</font>'.format(lab_item), style=style_sheet['ThaiStyle']),
                       Paragraph('<font size=12>{}</font>'.format(item.quantity), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.unit_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.total_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       ]
        items.append(item_record)

    items.append([
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>รวมเป็นเงิน</font>', style=style_sheet['ThaiStyleBold']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(invoice.subtotal()), style=bold_style),
    ])

    items.append([
        Paragraph('<font size=13>รวมเป็นเงินทั้งสิ้น/Grand Total ({})</font>'.format(bahttext(invoice.grand_total())),
                  style=label_style),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>ส่วนลด</font>', style=style_sheet['ThaiStyleBold']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(invoice.discount()), style=bold_style),
    ])

    items.append([
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>รวมเป็นเงินทั้งสิ้น/Grand Total</font>', style=style_sheet['ThaiStyleBold']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(invoice.grand_total()), style=bold_style),
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
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (0, -1), 6),
    ]))

    head_remark_style = ParagraphStyle(
        'HeadRemarkStyle',
        parent=style_sheet['ThaiStyleBold'],
        leading=17
    )
    remark_table = Table([
        [Paragraph("<font size=14>หมายเหตุ/Remark<br/></font>", style=head_remark_style)],
        [Paragraph(
            "<font size=12>1. โปรดโอนเงินเข้าบัญชีออมทรัพย์ ในนาม <u>คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล ธนาคารไทยพาณิชย์ จำกัด (มหาชน) "
            "สาขาศิริราช เลขที่บัญชี 016-433468-4</u> หรือ บัญชีกระแสรายวัน <u>เลขที่บัญชี 016-300-325-6</u> ชื่อบัญชี <u>มหาวิทยาลัยมหิดล</u> "
            "หรือ<u> Scan QR Code ด้านล่าง</u> หรือ <u>โปรดสั่งจ่ายเช็คในนาม มหาวิทยาลัยมหิดล</u><br/></font>",
            style=detail_style)],
        [Paragraph(
            "<font size=12>2. จัดส่งหลักฐานการชำระเงินทาง E-mail : <u>mumtfinance@gmail.com</u> หรือ แจ้งผ่านโดยการ <u>Scan QR Code</u> "
            "ด้านล่าง<br/></font>", style=detail_style)],
        [Paragraph(
            "<font size=12>3. โปรดชำระค่าบริการตรวจวิเคราะห์ทางห้องปฏิบัติการ <u><b>ภายใน 30 วัน</b></u> นับถัดจากวันที่ลงนามใน"
            "หนังสือแจ้งชำระค่าบริการฉบับนี้<br/></font>", style=detail_style)],
        [Paragraph(
            "<font size=12>4. โปรดตรวจสอบรายละเอียดข้อมูลการชำระเงิน หากพบข้อมูลไม่ถูกต้อง โปรดทำหนังสือแจ้งกลับมายัง <u><b>หน่วย"
            "การเงินและบัญชี งานคลังและพัสดุ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล</b></u><br/></font>",
            style=detail_style)],
        [Paragraph("<font size=12>5. <u>หากชำระเงินแล้วจะไม่สามารถขอเงินคืนได้</u><br/></font>",
                   style=detail_style)],
    ],
        colWidths=[500]
    )
    remark_table.hAlign = 'LEFT'
    remark_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 1), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 0),
    ]))

    qr_code_img = None
    if qr_image_base64:
        qr_bytes = b64decode(qr_image_base64)
        qr_buffer = BytesIO(qr_bytes)
        qr_code_img = Image(qr_buffer, width=90, height=90)

    sign_style = ParagraphStyle(
        'SignStyle',
        parent=style_sheet['ThaiStyleCenter'],
        fontSize=17,
        leading=20,
    )

    sign = [
        [Paragraph('<font size=12>ขอแสดงความนับถือ<br/></font>', style=sign_style)],
        [Paragraph(f'<font size=12><br/></font>', style=sign_style)],
        [Paragraph(f'<font size=12><br/></font>', style=sign_style)],
        [Paragraph(f'<font size=12><br/></font>', style=sign_style)],
        [Paragraph(f'<font size=12><br/></font>', style=sign_style)],
        [Paragraph(f'<font size=12><br/></font>', style=sign_style)],
        [Paragraph(f'<font size=12><br/></font>', style=sign_style)],
        [Paragraph(f'<font size=12>(ผู้ช่วยศาสตราจารย์ ดร.โชติรส พลับพลึง)<br/></font>', style=sign_style)],
        [Paragraph('<font size=12>คณบดีคณะเทคนิคการแพทย์</font>', style=sign_style)]
    ]
    sign_table = Table(sign, colWidths=[200])
    sign_table.hAlign = 'RIGHT'
    sign_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 50),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    data.append(KeepTogether(Spacer(7, 7)))
    data.append(KeepTogether(header_ori))
    data.append(KeepTogether(Spacer(1, 12)))
    data.append(KeepTogether(customer_table))
    data.append(KeepTogether(Spacer(1, 16)))
    data.append(KeepTogether(item_table))
    data.append(KeepTogether(Spacer(1, 16)))
    data.append(KeepTogether(remark_table))
    if qr_code_img:
        qr_code_text = Paragraph("QR Code<br/>ชำระเงิน", style=style_sheet['ThaiStyleCenter'])
        qr_code_table = Table([[qr_code_img], [qr_code_text]], colWidths=[150])
        qr_code_table.hAlign = 'LEFT'

        qr_code_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))

        combined_table = Table(
            [[qr_code_table, sign_table]],
            colWidths=[50, 450]
        )
        combined_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (0, 0), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('VALIGN', (1, 0), (1, 0), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT')
        ]))

        data.append(Spacer(1, 16))
        data.append(KeepTogether(combined_table))
    else:
        data.append(KeepTogether(Spacer(1, 16)))
        data.append(KeepTogether(sign_table))

    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    buffer.seek(0)
    return buffer


@service_admin.route('/invoice/pdf/<int:invoice_id>', methods=['GET'])
@login_required
def export_invoice_pdf(invoice_id):
    invoice = ServiceInvoice.query.get(invoice_id)
    sub_lab = ServiceSubLab.query.filter_by(code=invoice.quotation.request.lab).first()
    ref1 = re.sub(r'[^A-Z0-9]', '', invoice.invoice_no.upper())
    ref2 = re.sub(r'[^A-Z0-9]', '', sub_lab.sub_lab.upper())
    qrcode_data = generate_qrcode(amount=invoice.grand_total(), ref1=ref1, ref2=ref2, ref3=None)
    if qrcode_data:
        qr_image_base64 = qrcode_data['qrImage']
    else:
        qr_image_base64 = None
    buffer = generate_invoice_pdf(invoice, qr_image_base64=qr_image_base64)
    return send_file(buffer, download_name='Invoice.pdf', as_attachment=True)


@service_admin.route('/payment/add', methods=['GET', 'POST'])
def add_payment():
    menu = request.args.get('menu')
    invoice_id = request.args.get('invoice_id')
    invoice = ServiceInvoice.query.get(invoice_id)
    form = ServicePaymentForm()
    if form.validate_on_submit():
        payment = ServicePayment()
        form.populate_obj(payment)
        status_id = get_status(21)
        file = form.file_upload.data
        payment.invoice_id = invoice_id
        payment.created_at = arrow.now('Asia/Bangkok').datetime
        payment.customer_id = invoice.quotation.request.customer_id
        payment.admin_id = current_user.id
        payment.paid_at = arrow.get(form.paid_at.data, 'Asia/Bangkok').datetime
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
            payment.slip = file_name
            db.session.add(payment)
            invoice.paid_at = arrow.now('Asia/Bangkok').datetime
            invoice.quotation.request.status_id = status_id
            db.session.add(invoice)
            result = ServiceResult.query.filter_by(request_id=invoice.quotation.request_id).first()
            result.status_id = status_id
            db.session.add(result)
            db.session.commit()
            scheme = 'http' if current_app.debug else 'https'
            org = Org.query.filter_by(name='หน่วยการเงินและบัญชี').first()
            staff = StaffAccount.get_account_by_email(org.head)
            title_prefix = 'คุณ' if current_user.customer_info.type.type == 'บุคคล' else ''
            link = url_for("academic_service_payment.invoice_payment_index", _external=True, _scheme=scheme)
            customer_name = invoice.customer_name.replace(' ', '_')
            title = f'''[{invoice.invoice_no}] ใบแจ้งหนี้ - {title_prefix}{customer_name} ({invoice.name}) | แจ้งอัปเดตการชำระเงิน'''
            message = f'''เรียน เจ้าหน้าที่การเงิน\n\n'''
            message += f'''ใบแจ้งหนี้เลขที่ : {invoice.invoice_no}\n'''
            message += f'''ลูกค้า : {invoice.customer_name}\n'''
            message += f'''ในนาม : {invoice.name}\n'''
            message += f'''ขอแจ้งให้ทราบว่า ได้มีการอัปเดตข้อมูลการชำระเงินเรียบร้อยแล้ว\n'''
            message += f'''กรุณาตรวจสอบรายละเอียดการชำระเงินได้ที่ลิงก์ด้านล่าง\n'''
            message += f'''{link}\n\n'''
            message += f'''ผู้ประสานงาน\n'''
            message += f'''{invoice.customer_name}\n'''
            message += f'''เบอร์โทร {invoice.contact_phone_number}\n\n'''
            message += f'''ระบบงานบริการวิชาการ'''
            send_mail([staff.email + '@mahidol.ac.th'], title, message)
            msg = ('แจ้งอัปเดตการชำระเงิน' \
                   '\n\nเรียน เจ้าหน้าที่การเงิน'
                   '\n\nใบแจ้งหนี้เลขที่ {}' \
                   '\nลูกค้า : {}' \
                   '\nในนาม : {}' \
                   '\nขอแจ้งให้ทราบว่า ได้มีการอัปเดตข้อมูลการชำระเงินเรียบร้อยแล้ว' \
                   '\nกรุณาตรวจสอบรายละเอียดการชำระเงินได้ที่ลิงก์ด้านล่าง' \
                   '\n{}' \
                   '\n\nผู้ประสานงาน' \
                   '\n{}' \
                   '\nเบอร์โทร {}' \
                   '\n\nระบบงานบริการวิชาการ'.format(invoice.invoice_no, invoice.customer_name, invoice.name, link,
                                                     invoice.customer_name, invoice.contact_phone_number)
                   )
            if not current_app.debug:
                try:
                    line_bot_api.push_message(to=staff.line_id, messages=TextSendMessage(text=msg))
                except LineBotApiError:
                    pass
        flash('อัพเดตสลิปสำเร็จ', 'success')
        return redirect(url_for('service_admin.invoice_index', menu=menu))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
        return render_template('service_admin/add_payment.html', menu=menu, form=form, invoice=invoice)


@service_admin.route('/quotation/index')
@login_required
def quotation_index():
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    is_admin = any(a for a in admin if not a.is_supervisor)
    is_supervisor = any(a.is_supervisor for a in admin)
    return render_template('service_admin/quotation_index.html', tab=tab, menu=menu,
                           is_supervisor=is_supervisor, is_admin=is_admin)


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
        query = query.filter(ServiceQuotation.sent_at == None, ServiceQuotation.approved_at == None,
                             ServiceQuotation.confirmed_at == None,
                             ServiceQuotation.cancelled_at == None)
    elif tab == 'pending_supervisor_approval' or tab == 'pending_approval':
        query = query.filter(ServiceQuotation.sent_at != None, ServiceQuotation.approved_at == None,
                             ServiceQuotation.confirmed_at == None,
                             ServiceQuotation.cancelled_at == None)
    elif tab == 'awaiting_customer':
        query = query.filter(ServiceQuotation.sent_at != None, ServiceQuotation.approved_at != None,
                             ServiceQuotation.confirmed_at == None,
                             ServiceQuotation.cancelled_at == None)
    elif tab == 'confirmed':
        query = query.filter(ServiceQuotation.sent_at != None, ServiceQuotation.approved_at != None,
                             ServiceQuotation.confirmed_at != None,
                             ServiceQuotation.cancelled_at == None)
    elif tab == 'reject':
        query = query.filter(ServiceQuotation.sent_at != None, ServiceQuotation.approved_at != None,
                             ServiceQuotation.confirmed_at == None,
                             ServiceQuotation.cancelled_at != None)
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
    menu = request.args.get('menu')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab).first()
    quotation = ServiceQuotation.query.filter_by(request_id=request_id).first()
    if not quotation:
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
        for field in request_form:
            if field.name not in quote_column_names:
                continue
            keys = []
            keys = walk_form_fields(field, quote_column_names[field.name], keys=keys)
            for r in range(1, len(quote_column_names[field.name]) + 1):
                for key in itertools.combinations(keys, r):
                    sorted_key_ = sorted(''.join([k[1] for k in key]))
                    p_key = ''.join(sorted_key_).replace(' ', '')
                    values = ', '.join(
                        [f"<i>{k[1]}</i>" if "germ" in k[0] and k[1] != "None" else k[1] for k in key]
                    )
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
                                quote_details[p_key] = {"value": values, "price": price, "quantity": quantities}
                    else:
                        if p_key in quote_prices:
                            prices = quote_prices[p_key]
                            quote_details[p_key] = {"value": values, "price": prices, "quantity": quantities}
        quotation_no = ServiceNumberID.get_number('QT', db,
                                                  lab=sub_lab.lab.code if sub_lab and sub_lab.lab.code == 'protein' \
                                                      else service_request.lab)
        district_title = 'เขต' if service_request.quotation_address.province.name == 'กรุงเทพมหานคร' else 'อำเภอ'
        subdistrict_title = 'แขวง' if service_request.quotation_address.province.name == 'กรุงเทพมหานคร' else 'ตำบล'
        quotation = ServiceQuotation(quotation_no=quotation_no.number, request_id=request_id,
                                     name=service_request.quotation_address.name,
                                     address=(
                                         f"{service_request.quotation_address.address} "
                                         f"{subdistrict_title}{service_request.quotation_address.subdistrict} "
                                         f"{district_title}{service_request.quotation_address.district} "
                                         f"จังหวัด{service_request.quotation_address.province} "
                                         f"{service_request.quotation_address.zipcode}"
                                     ),
                                     taxpayer_identification_no=service_request.quotation_address.taxpayer_identification_no,
                                     creator=current_user, created_at=arrow.now('Asia/Bangkok').datetime)
        db.session.add(quotation)
        quotation_no.count += 1
        status_id = get_status(3)
        service_request.status_id = status_id
        db.session.add(service_request)
        db.session.commit()
        sequence_no = ServiceSequenceQuotationID.get_number('QT', db, quotation='quotation_' + str(quotation.id))
        for _, (_, item) in enumerate(quote_details.items()):
            quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                  item=item['value'],
                                                  quantity=item['quantity'],
                                                  unit_price=item['price'],
                                                  total_price=int(item['quantity']) * item['price'])
            sequence_no.count += 1
            db.session.add(quotation_item)
            db.session.commit()
        if service_request.report_languages:
            for rl in service_request.report_languages:
                if rl.report_language.price != 0:
                    quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                          item=rl.report_language.item,
                                                          quantity=1,
                                                          unit_price=rl.report_language.price,
                                                          total_price=rl.report_language.price)
                    sequence_no.count += 1
                    db.session.add(quotation_item)
                    db.session.commit()
        return redirect(
            url_for('service_admin.create_quotation_for_admin', quotation_id=quotation.id, tab='draft', menu=menu))
    else:
        return render_template('service_admin/quotation_created_confirmation_page.html',
                               quotation_id=quotation.id, request_no=service_request.request_no, menu=menu)


@service_admin.route('/admin/quotation/add/<int:quotation_id>', methods=['GET', 'POST', 'PATCH'])
@login_required
def create_quotation_for_admin(quotation_id):
    menu = request.args.get('menu')
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
            status_id = get_status(4)
            quotation.sent_at = arrow.now('Asia/Bangkok').datetime
            quotation.request.status_id = status_id
            db.session.add(quotation)
            db.session.commit()
            customer_name = quotation.customer_name.replace(' ', '_')
            title_prefix = 'คุณ' if quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
            admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=quotation.request.lab)).all()
            quotation_link = url_for("service_admin.approval_quotation_for_supervisor", quotation_id=quotation_id,
                                     tab='pending_approval', _external=True, _scheme=scheme, menu=menu)
            if admins:
                email = [a.admin.email + '@mahidol.ac.th' for a in admins if a.is_supervisor]
                if email:
                    title = f'''[{quotation.quotation_no}] ใบเสนอราคา - {title_prefix}{customer_name} ({quotation.name}) | แจ้งขออนุมัติใบเสนอราคา'''
                    message = f'''เรียน หัวหน้าห้องปฏิบัติการ\n\n'''
                    message += f'''ใบเสนอราคาเลขที่ : {quotation.quotation_no}\n'''
                    message += f'''ลูกค้า : {quotation.customer_name}\n'''
                    message += f'''ในนาม : {quotation.name}\n'''
                    message += f'''อ้างอิงจากใบคำขอรับบริการเลขที่ : {quotation.request.request_no}'''
                    message += f'''ที่รอการอนุมัติใบเสนอราคา\n'''
                    message += f'''กรุณาตรวจสอบและดำเนินการได้ที่ลิงก์ด้านล่าง\n'''
                    message += f'''{quotation_link}\n\n'''
                    message += f'''เจ้าหน้าที่ Admin\n'''
                    message += f'''{quotation.creator.fullname}\n'''
                    message += f'''ระบบงานบริการวิชาการ'''
                    send_mail(email, title, message)
                    msg = ('แจ้งขออนุมัติใบเสนอราคาเลขที่ {}' \
                           '\n\nเรียน หัวหน้าห้องปฏิบัติการ'
                           '\n\nใบเสนอราคาเลขที่ {}' \
                           '\nลูกค้า : {}' \
                           '\nในนาม : {}' \
                           '\nอ้างอิงจากใบคำขอรับบริการเลขที่ : {}'
                           '\nที่รอการอนุมัติใบเสนอราคา' \
                           '\nกรุณาตรวจสอบและดำเนินการได้ที่ลิงก์ด้านล่าง' \
                           '\n{}' \
                           '\nเจ้าหน้าที่ Admin' \
                           '\n\n{}' \
                           '\nระบบงานบริการวิชาการ'
                           .format(quotation.quotation_no, quotation.quotation_no,
                                   quotation.request.customer.customer_info.cus_name,
                                   quotation.name, quotation.request.request_no, quotation_link,
                                   quotation.creator.fullname)
                           )
                    if not current_app.debug:
                        for a in admins:
                            if a.is_supervisor:
                                try:
                                    line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                                except LineBotApiError:
                                    pass
            flash('ส่งข้อมูลให้หัวหน้าอนุมัติเรียบร้อยแล้ว กรุณารอดำเนินการ', 'success')
            return redirect(url_for('service_admin.quotation_index', tab='pending_supervisor_approval', menu=menu))
        else:
            flash('บันทึกข้อมูลแบบร่างเรียบร้อยแล้ว', 'success')
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('service_admin/create_quotation_for_admin.html', quotation=quotation, menu=menu,
                           tab=tab, form=form, datas=datas, sub_lab=sub_lab)


@service_admin.route('/quotation/supervisor/approve/<int:quotation_id>', methods=['GET', 'POST'])
@login_required
def approval_quotation_for_supervisor(quotation_id):
    menu = request.args.get('menu')
    tab = request.args.get('tab')
    quotation = ServiceQuotation.query.get(quotation_id)
    sub_lab = ServiceSubLab.query.filter_by(code=quotation.request.lab).first()
    scheme = 'http' if current_app.debug else 'https'
    if not quotation.approved_at:
        if request.method == 'POST':
            status_id = get_status(5)
            password = request.form.get('password')
            quotation.approver_id = current_user.id
            quotation.approved_at = arrow.now('Asia/Bangkok').datetime
            quotation.request.status_id = status_id
            db.session.add(quotation)
            if quotation.digital_signature is None:
                buffer = generate_quotation_pdf(quotation, sign=True)
                try:
                    sign_pdf = e_sign(buffer, password, include_image=False)
                except (ValueError, AttributeError):
                    flash("ไม่สามารถลงนามดิจิทัลได้ โปรดตรวจสอบรหัสผ่าน", "danger")
                    return redirect(
                        url_for('service_admin.approval_quotation_for_supervisor', quotation_id=quotation.id,
                                tab='awaiting_customer'))
                else:
                    quotation.digital_signature = sign_pdf.read()
                    sign_pdf.seek(0)
                    db.session.add(quotation)
                    db.session.commit()
                    contact_email = quotation.request.customer.contact_email if quotation.request.customer.contact_email else quotation.request.customer.email
                    quotation_link = url_for("academic_services.view_quotation", quotation_id=quotation_id, menu=menu,
                                             _external=True, _scheme=scheme)
                    total_items = len(quotation.quotation_items)
                    title_prefix = 'คุณ' if quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
                    title = f'''โปรดยืนยันใบเสนอราคา [{quotation.quotation_no}] – งานบริการตรวจวิเคราะห์ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
                    customer_name = quotation.customer_name.replace(' ', '_')
                    message = f'''เรียน {title_prefix}{customer_name}\n\n'''
                    message += f'''ตามที่ท่านได้แจ้งความประสงค์ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล ใบเสนอราคาหมายเลข {quotation.quotation_no}'''
                    message += f''' ได้รับการอนุมัติเรียบร้อยแล้ว และขณะนี้รอการยืนยันจากท่านเพื่อดำเนินการขั้นตอนต่อไป\n\n'''
                    message += f'''รายละเอียดข้อมูล\n'''
                    message += f'''วันที่อนุมัติ : {quotation.approved_at.astimezone(localtz).strftime('%d/%m/%Y')}\n'''
                    message += f'''จำนวนรายการ : {total_items} รายการ\n'''
                    message += f'''ราคา : {"{:,.2f}".format(quotation.grand_total())} บาท\n'''
                    message += f'''อ้างอิงจากใบคำขอรับบริการเลขที่ : {quotation.request.request_no}\n\n'''
                    message += f'''กรุณาดำเนินการยืนยันใบเสนอราคาภายใน 7 วัน ผ่านลิงก์ด้านล่าง\n'''
                    message += f'''{quotation_link}\n\n'''
                    message += f'''หากไม่ยืนยันภายในกำหนด ใบเสนอราคาอาจถูกยกเลิกและราคาอาจเปลี่ยนแปลงได้\n\n'''
                    message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
                    message += f'''ขอแสดงความนับถือ\n'''
                    message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
                    message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
                    send_mail([contact_email], title, message)
                    quotation_link_for_assistant = url_for("service_admin.view_quotation", quotation_id=quotation_id,
                                                           tab='awaiting_customer', menu=menu, _external=True,
                                                           _scheme=scheme)
                    if sub_lab.approver:
                        title_for_assistant = f'''รายการอนุมัติใบเสนอราคาเลขที่ {quotation.quotation_no} อนุมัติโดย คุณ{quotation.approver.fullname}'''
                        message_for_assistant = f'''เรียน ผู้ช่วยคณบดีฝ่ายบริการวิชาการ\n\n'''
                        message_for_assistant += f'''แจ้งรายการอนุมัติใบเสนอราคาเลขที่ {quotation.quotation_no}\n'''
                        message_for_assistant += f'''ในนามลูกค้า {title_prefix}{customer_name}\n'''
                        message_for_assistant += f'''รายละเอียดดังต่อไปนี้\n'''
                        message_for_assistant += f'''วันที่อนุมัติ : {quotation.approved_at.astimezone(localtz).strftime('%d/%m/%Y')}\n'''
                        message_for_assistant += f'''จำนวนรายการ : {total_items} รายการ\n'''
                        message_for_assistant += f'''ราคา : {"{:,.2f}".format(quotation.grand_total())} บาท\n'''
                        message_for_assistant += f'''อ้างอิงจากใบคำขอรับบริการเลขที่ : {quotation.request.request_no}\n'''
                        message_for_assistant += f'''อนุมัติโดย คุณ{quotation.approver.fullname}\n\n'''
                        message_for_assistant += f'''โดยสามารถดูรายละเอียดใบเสนอราคาเพิ่มเติมได้ที่ลิงก์ด้านล่าง\n'''
                        message_for_assistant += f'''{quotation_link_for_assistant}\n\n'''
                        message += f'''หัวหน้าห้องปฏิบัติการ\n'''
                        message += f'''{quotation.approver.fullname}\n'''
                        message += f'''ระบบงานบริการวิชาการ'''
                        send_mail([sub_lab.approver.email + '@mahidol.ac.th'], title_for_assistant,
                                  message_for_assistant)
                    flash(f'อนุมัติใบเสนอราคาเลขที่ {quotation.quotation_no} สำเร็จ กรุณารอลูกค้ายืนยันใบเสนอราคา',
                          'success')
                    return redirect(
                        url_for('service_admin.quotation_index', quotation_id=quotation.id, tab='awaiting_customer'))
        return render_template('service_admin/approval_quotation_for_supervisor.html', quotation=quotation,
                               tab=tab, quotation_id=quotation_id, sub_lab=sub_lab, menu=menu)
    else:
        return render_template('service_admin/quotation_approved_page.html', quotation_id=quotation.id,
                               quotaiton_no=quotation.quotation_no, menu=menu, tab='all')


@service_admin.route('/quotation/item/add/<int:quotation_id>', methods=['GET', 'POST'])
def add_quotation_item(quotation_id):
    menu = request.args.get('menu')
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
                           menu=menu, quotation_id=quotation_id)


@service_admin.route('/quotation/item/delete/<int:quotation_item_id>', methods=['GET', 'DELETE'])
def delete_quotation_item(quotation_item_id):
    menu = request.args.get('menu')
    tab = request.args.get('tab')
    quotation_item = ServiceQuotationItem.query.get(quotation_item_id)
    quotation_id = quotation_item.quotation_id
    db.session.delete(quotation_item)
    db.session.commit()
    items = ServiceQuotationItem.query.filter_by(quotation_id=quotation_id).all()
    sorted_items = sorted(items, key=sort_quotation_item)
    for index, item in enumerate(sorted_items, start=1):
        item.sequence = index
    db.session.commit()
    seq_code = f"quotation_{quotation_id}"
    seq = ServiceSequenceQuotationID.query.filter_by(quotation=seq_code).first()
    if seq and seq.count > 0:
        seq.count -= 1
        db.session.commit()
    flash('ลบรายการสำเร็จ', 'success')
    return redirect(url_for('service_admin.create_quotation_for_admin', menu=menu, tab=tab, quotation_id=quotation_id))


@service_admin.route('/quotation/password/enter/<int:quotation_id>', methods=['GET', 'POST'])
@login_required
def enter_password_for_sign_digital(quotation_id):
    form = PasswordOfSignDigitalForm()
    return render_template('service_admin/modal/password_modal.html', form=form, quotation_id=quotation_id)


@service_admin.route('/quotation/view/<int:quotation_id>')
@login_required
def view_quotation(quotation_id):
    menu = request.args.get('menu')
    tab = request.args.get('tab')
    quotation = ServiceQuotation.query.get(quotation_id)
    sub_lab = ServiceSubLab.query.filter_by(code=quotation.request.lab).all()
    return render_template('service_admin/view_quotation.html', quotation_id=quotation_id, tab=tab,
                           quotation=quotation, sub_lab=sub_lab, menu=menu)


def generate_quotation_pdf(quotation, sign=False):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 60, 60)
    approver = quotation.approver.fullname if sign else ''
    digital_sign = 'ลายมือชื่อดิจิทัล/Digital Signature' if sign else (
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;')
    lab = ServiceLab.query.filter_by(code=quotation.request.lab).first()
    sub_lab = ServiceSubLab.query.filter_by(code=quotation.request.lab).first()

    def all_page_setup(canvas, doc):
        canvas.saveState()
        # logo_image = ImageReader('app/static/img/mu-watermark.png')
        # canvas.drawImage()
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
                '''.format(quotation_no=quotation.quotation_no)

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

    issued_date = arrow.get(quotation.approved_at.astimezone(localtz)).format(fmt='DD MMMM YYYY',
                                                                              locale='th-th') if sign else ''
    customer = '''<para><font size=12>
                วันที่ {issued_date}<br/>
                เรื่อง ใบเสนอราคาค่าบริการตรวจวิเคราะห์ทางห้องปฏิบัติการ<br/>
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

    for n, item in enumerate(sorted(quotation.quotation_items, key=lambda x: x.sequence), start=1):
        lab_item = re.sub(r'<i>(.*?)</i>', r"<font name='SarabunItalic'>\1</font>", item.item)
        item_record = [Paragraph('<font size=12>{}</font>'.format(n), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{}</font>'.format(lab_item), style=style_sheet['ThaiStyle']),
                       Paragraph('<font size=12>{}</font>'.format(item.quantity), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.unit_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.total_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       ]
        items.append(item_record)

    for i in range(n):
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
        Paragraph('<font size=12>{:,.2f}</font>'.format(quotation.subtotal()), style=style_sheet['ThaiStyleNumber']),
    ])

    items.append([
        Paragraph('<font size=12>{}</font>'.format(bahttext(quotation.grand_total())),
                  style=style_sheet['ThaiStyleCenter']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>ส่วนลด</font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(quotation.discount()), style=style_sheet['ThaiStyleNumber']),
    ])

    items.append([
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>รวมเป็นเงินทั้งสิ้น/Grand Total</font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(quotation.grand_total()), style=style_sheet['ThaiStyleNumber']),
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

    sign_style = ParagraphStyle(
        'SignStyle',
        parent=style_sheet['ThaiStyleCenter'],
        fontSize=16,
        leading=20,
    )

    district_title = 'เขต' if quotation.request.quotation_address.province.name == 'กรุงเทพมหานคร' else 'อำเภอ'
    subdistrict_title = 'แขวง' if quotation.request.quotation_address.province.name == 'กรุงเทพมหานคร' else 'ตำบล',

    document_address = '''<para><font size=12>ที่อยู่สำหรับจัดส่งเอกสาร<br/>
                ถึง {name}<br/>
                ที่อยู่ {address} {subdistrict_title}{subdistrict} {district_title}{district} จังหวัด{province} {zipcode}<br/>
                เบอร์โทรศัพท์ : {phone_number}<br/>
                อีเมล : {email}
                </font></para>
                '''.format(name=quotation.request.document_address.name,
                           address=quotation.request.document_address.address,
                           subdistrict_title=subdistrict_title,
                           subdistrict=quotation.request.document_address.subdistrict,
                           district_title=district_title,
                           district=quotation.request.document_address.district,
                           province=quotation.request.document_address.province,
                           zipcode=quotation.request.document_address.zipcode,
                           phone_number=quotation.request.document_address.phone_number,
                           email=quotation.request.customer.contact_email
                           )
    document_address_table = Table([[Paragraph(document_address, style=style_sheet['ThaiStyle'])]], colWidths=[200])
    document_address_table.hAlign = 'LEFT'

    sign = [
        [Paragraph('<font size=12>ขอแสดงความนับถือ<br/></font>', style=sign_style)],
        [Paragraph(f'<font size=12>{approver}<br/></font>', style=sign_style)],
        [Paragraph(f'<font size=12>({digital_sign})<br/></font>', style=sign_style)],
        [Paragraph('<font size=12>หัวหน้าห้องปฏิบัติการ</font>', style=sign_style)]
    ]
    sign_table = Table(sign, colWidths=[200])
    sign_table.hAlign = 'RIGHT'
    sign_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 50),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    data.append(KeepTogether(Spacer(7, 7)))
    data.append(KeepTogether(header_ori))
    data.append(KeepTogether(Spacer(1, 12)))
    data.append(KeepTogether(customer_table))
    data.append(KeepTogether(Spacer(1, 16)))
    data.append(KeepTogether(item_table))
    data.append(KeepTogether(Spacer(1, 15)))
    data.append(KeepTogether(document_address_table))
    data.append(KeepTogether(Spacer(1, 5)))
    data.append(KeepTogether(sign_table))

    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    buffer.seek(0)
    return buffer


@service_admin.route('/quotation/pdf/<int:quotation_id>', methods=['GET'])
def export_quotation_pdf(quotation_id):
    quotation = ServiceQuotation.query.get(quotation_id)
    if quotation.digital_signature:
        return send_file(BytesIO(quotation.digital_signature), download_name=f'{quotation.quotation_no}.pdf',
                         as_attachment=True)
    buffer = generate_quotation_pdf(quotation)
    return send_file(buffer, download_name=f'{quotation.quotation_no}.pdf', as_attachment=True)


@service_admin.route('/procurement/meeting/add', methods=['GET'])
def add_meeting():
    return render_template('procurement/add_meeting.html')


@service_admin.route('/receipt/index', methods=['GET'])
@login_required
def receipt_index():
    menu = request.args.get('menu')
    return render_template('service_admin/receipt_index.html', menu=menu)


@service_admin.route('/api/receipt/index')
def get_receipts():
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
    query = ServiceInvoice.query.filter(ServiceInvoice.receipts!=None, or_(ServiceInvoice.creator_id == current_user.id,
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


@service_admin.route('/result/draft/add', methods=['GET', 'POST'])
@service_admin.route('/result/draft/edit/<int:result_id>', methods=['GET', 'POST'])
@login_required
def create_draft_result(result_id=None):
    menu = request.args.get('menu')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    if not result_id:
        result = ServiceResult.query.filter_by(request_id=request_id).first()
        if not result:
            if request.method == 'GET':
                result_list = ServiceResult(request_id=request_id, released_at=arrow.now('Asia/Bangkok').datetime,
                                            creator_id=current_user.id)
                db.session.add(result_list)
                if service_request.report_languages:
                    for rl in service_request.report_languages:
                        result_item = ServiceResultItem(report_language=rl.report_language.item, result=result_list,
                                                        released_at=arrow.now('Asia/Bangkok').datetime,
                                                        creator_id=current_user.id)
                        db.session.add(result_item)
                        db.session.commit()
                result = ServiceResult.query.get(result_list.id)
            else:
                result = ServiceResult.query.filter_by(request_id=request_id).first()
    else:
        result = ServiceResult.query.get(result_id)
    if request.method == 'POST':
        for item in result.result_items:
            file = request.files.get(f'file_{item.id}')
            if file and allowed_file(file.filename):
                mime_type = file.mimetype
                file_name = '{}.{}'.format(item.report_language,
                                           file.filename.split('.')[-1])
                file_data = file.stream.read()
                response = s3.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=file_name,
                    Body=file_data,
                    ContentType=mime_type
                )
                item.draft_file = file_name
                if result_id:
                    item.modified_at = arrow.now('Asia/Bangkok').datetime
                    item.result.modified_at = arrow.now('Asia/Bangkok').datetime
                db.session.add(item)
                db.session.commit()
        uploaded_all = all(item.draft_file for item in result.result_items)
        if uploaded_all:
            if result.request.status.status_id == 14:
                result.status_note = True
            else:
                result.status_note = False
            status_id = get_status(12)
            result.status_id = status_id
            service_request.status_id = status_id
            scheme = 'http' if current_app.debug else 'https'
            if not result.is_sent_email:
                result_url = url_for('academic_services.result_index', menu='report', _external=True, _scheme=scheme)
                customer_name = result.request.customer.customer_name.replace(' ', '_')
                contact_email = result.request.customer.contact_email if result.request.customer.contact_email else result.request.customer.email
                title_prefix = 'คุณ' if result.request.customer.customer_info.type.type == 'บุคคล' else ''
                title = f'''แจ้งออกรายงานผลการทดสอบฉบับร่างของใบคำขอรับบริการ [{result.request.request_no}] – งานบริการตรวจวิเคราะห์ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
                message = f'''เรียน {title_prefix}{customer_name}\n\n'''
                message += f'''ตามที่ท่านได้ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล ใบคำขอบริการเลขที่ {result.request.request_no}'''
                message += f''' ขณะนี้ได้จัดทำรายงานผลการทดสอบฉบับร่างเรียบร้อยแล้ว'''
                message += f''' กรุณาตรวจสอบความถูกต้องของข้อมูลในรายงานผลการทดสอบฉบับร่าง และดำเนินการยืนยันตามลิงก์ด้านล่าง\n'''
                message += f'''ท่านสามารถยืนยันได้ที่ลิงก์ด้านล่าง'''
                message += f'''{result_url}'''
                message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
                message += f'''ขอแสดงความนับถือ\n'''
                message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
                message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
                send_mail([contact_email], title, message)
            elif result.result_edit_at and not result.approved_at:
                result_url = url_for('academic_services.result_index', menu='report', _external=True, _scheme=scheme)
                customer_name = result.request.customer.customer_name.replace(' ', '_')
                contact_email = result.request.customer.contact_email if result.request.customer.contact_email else result.request.customer.email
                title_prefix = 'คุณ' if result.request.customer.customer_info.type.type == 'บุคคล' else ''
                title = f'''แจ้งแก้ไขรายงานผลการทดสอบฉบับร่างของใบคำขอรับบริการ [{result.request.request_no}] – งานบริการตรวจวิเคราะห์ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
                message = f'''เรียน {title_prefix}{customer_name}\n\n'''
                message += f'''ตามที่ท่านได้ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล ใบคำขอบริการเลขที่ {result.request.request_no}'''
                message += f''' ขณะนี้ได้แก้ไขทำรายงานผลการทดสอบฉบับร่างเรียบร้อยแล้ว'''
                message += f''' กรุณาตรวจสอบความถูกต้องของข้อมูลในรายงานผลการทดสอบฉบับร่าง และดำเนินการยืนยันตามลิงก์ด้านล่าง\n'''
                message += f'''ท่านสามารถยืนยันได้ที่ลิงก์ด้านล่าง'''
                message += f'''{result_url}'''
                message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
                message += f'''ขอแสดงความนับถือ\n'''
                message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
                message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
                send_mail([contact_email], title, message)
            result.is_sent_email = True
        else:
            status_id = get_status(11)
            result.status_id = status_id
            service_request.status_id = status_id
        db.session.add(result)
        db.session.add(service_request)
        db.session.commit()
        flash("บันทึกไฟล์เรียบร้อยแล้ว", "success")
        return redirect(url_for('service_admin.test_item_index', menu='test_item'))
    return render_template('service_admin/create_draft_result.html', result_id=result_id, menu=menu,
                           result=result)


@service_admin.route('/result/draft/delete/<int:item_id>', methods=['GET', 'POST'])
def delete_draft_result(item_id):
    status_id = get_status(11)
    item = ServiceResultItem.query.get(item_id)
    item.draft_file = None
    item.modified_at = arrow.now('Asia/Bangkok').datetime
    item.result.status_id = status_id
    item.result.modified_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(item)
    db.session.commit()
    flash("ลบไฟล์เรียบร้อยแล้ว", "success")
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@service_admin.route('/result/final/edit/<int:result_id>', methods=['GET', 'POST'])
@login_required
def create_final_result(result_id=None):
    menu = request.args.get('menu')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    result = ServiceResult.query.get(result_id)
    if request.method == 'POST':
        for item in result.result_items:
            file = request.files.get(f'file_{item.id}')
            if file and allowed_file(file.filename):
                mime_type = file.mimetype
                file_name = '{}.{}'.format(item.report_language,
                                           file.filename.split('.')[-1])
                file_data = file.stream.read()
                response = s3.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=file_name,
                    Body=file_data,
                    ContentType=mime_type
                )
                item.final_file = file_name
                item.modified_at = arrow.now('Asia/Bangkok').datetime
                item.result.modified_at = arrow.now('Asia/Bangkok').datetime
                db.session.add(item)
                db.session.commit()
                scheme = 'http' if current_app.debug else 'https'
                result_url = url_for('academic_services.result_index', menu='report', _external=True, _scheme=scheme)
                customer_name = result.request.customer.customer_name.replace(' ', '_')
                contact_email = result.request.customer.contact_email if result.request.customer.contact_email else result.request.customer.email
                title_prefix = 'คุณ' if result.request.customer.customer_info.type.type == 'บุคคล' else ''
                title = f'''แจ้งออกรายงานผลการทดสอบฉบับร่างจริงของใบคำขอรับบริการ [{result.request.request_no}] – งานบริการตรวจวิเคราะห์ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
                message = f'''เรียน {title_prefix}{customer_name}\n\n'''
                message += f'''ตามที่ท่านได้ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล ใบคำขอบริการเลขที่ {result.request.request_no}'''
                message += f''' ขณะนี้ได้ดำเนินการออกรายงานผลการทดสอบฉบับจริงเรียบร้อยแล้ว'''
                message += f'''ท่านสามารถดูรายละเอียดรายงานผลการทดสอบได้จากลิงก์ด้านล่าง'''
                message += f'''{result_url}'''
                message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
                message += f'''ขอแสดงความนับถือ\n'''
                message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
                message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
                send_mail([contact_email], title, message)
                db.session.add(result)
                db.session.add(service_request)
                db.session.commit()
                flash("บันทึกไฟล์เรียบร้อยแล้ว", "success")
                return redirect(url_for('service_admin.test_item_index', menu='test_item'))
    return render_template('service_admin/create_final_result.html', result_id=result_id, menu=menu, result=result)


@service_admin.route('/result/final/delete/<int:item_id>', methods=['GET', 'POST'])
def delete_final_result(item_id):
    item = ServiceResultItem.query.get(item_id)
    item.final_file = None
    item.modified_at = arrow.now('Asia/Bangkok').datetime
    item.result.modified_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(item)
    db.session.commit()
    flash("ลบไฟล์เรียบร้อยแล้ว", "success")
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp
