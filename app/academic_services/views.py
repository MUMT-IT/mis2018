import os
from datetime import date
from bahttext import bahttext
from sqlalchemy import or_
import arrow
import pandas
from io import BytesIO
import pytz
import requests
from pytz import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, TableStyle, Table, Spacer, KeepTogether, PageBreak
from sqlalchemy.orm import make_transient
from wtforms import FormField, FieldList

from app.main import app, get_credential, json_keyfile
from app.academic_services import academic_services
from app.academic_services.forms import (ServiceCustomerInfoForm, LoginForm, ForgetPasswordForm, ResetPasswordForm,
                                         ServiceCustomerAccountForm, create_request_form, ServiceCustomerContactForm,
                                         ServiceCustomerAddressForm, ServiceSampleForm, ServicePaymentForm)
from app.academic_services.models import *
from flask import render_template, flash, redirect, url_for, request, current_app, abort, session, make_response, \
    jsonify, send_file
from flask_login import login_user, current_user, logout_user, login_required
from flask_principal import Identity, identity_changed, AnonymousIdentity
from flask_admin.helpers import is_safe_url
from itsdangerous.url_safe import URLSafeTimedSerializer as TimedJSONWebSignatureSerializer
from app.main import mail
from flask_mail import Message
from werkzeug.utils import secure_filename
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive

localtz = timezone('Asia/Bangkok')

sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
pdfmetrics.registerFont(sarabun_font)
style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))
style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', alignment=TA_CENTER))

gauth = GoogleAuth()
scopes = ['https://www.googleapis.com/auth/drive']
keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile, scopes)
drive = GoogleDrive(gauth)

FOLDER_ID = '1832el0EAqQ6NVz2wB7Ade6wRe-PsHQsu'

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

bangkok = pytz.timezone('Asia/Bangkok')


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile, scopes)
    return GoogleDrive(gauth)


def format_data(data):
    if isinstance(data, dict):
        return {k: format_data(v) for k, v in data.items() if k != "csrf_token" and k != 'submit'}
    elif isinstance(data, list):
        return [format_data(item) for item in data]
    elif isinstance(data, (date)):
        return data.isoformat()
    return data


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


@academic_services.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        next_url = request.args.get('next', url_for('academic_services.customer_account'))
        if is_safe_url(next_url):
            return redirect(next_url)
        else:
            return abort(400)
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(ServiceCustomerAccount).filter_by(email=form.email.data).first()
        if user:
            pwd = form.password.data
            if user.verify_password(pwd):
                login_user(user)
                identity_changed.send(current_app._get_current_object(), identity=Identity(user.id))
                next_url = request.args.get('next', url_for('index'))
                if not is_safe_url(next_url):
                    return abort(400)
                else:
                    flash('ลงทะเบียนเข้าใช้งานสำเร็จ', 'success')
                    if user.is_first_login == True :
                        return redirect(url_for('academic_services.lab_index', menu='new'))
                    else:
                        user.is_first_login = True
                        db.session.add(user)
                        db.session.commit()
                        return redirect(url_for('academic_services.customer_account', menu='view'))
            else:
                flash('รหัสผ่านไม่ถูกต้อง กรุณาลองอีกครั้ง', 'danger')
                return redirect(url_for('academic_services.customer_index'))
        else:
            flash('ไม่พบบัญชีผู้ใช้งาน', 'danger')
            return redirect(url_for('academic_services.customer_index'))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('academic_services/login.html', form=form)


@academic_services.route('/logout')
@login_required
def logout():
    logout_user()
    identity_changed.send(current_app._get_current_object(), identity=AnonymousIdentity())
    flash('ออกจากระบบเรียบร้อย', 'success')
    return redirect(url_for('academic_services.customer_index'))


@academic_services.route('/forget_password', methods=['GET', 'POST'])
def forget_password():
    if current_user.is_authenticated:
        return redirect('academic_services.customer_account')
    form = ForgetPasswordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            user = ServiceCustomerAccount.query.filter_by(email=form.email.data).first()
            if not user:
                flash('ไม่พบบัญชีผู้ใช้งาน', 'warning')
                return render_template('academic_services/forget_password.html', form=form, errors=form.errors)
            serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'))
            token = serializer.dumps({'email': form.email.data})
            url = url_for('academic_services.reset_password', token=token, _external=True)
            message = 'Click the link below to reset the password.'\
                      ' กรุณาคลิกที่ลิงค์เพื่อทำการตั้งรหัสผ่านใหม่\n\n{}'.format(url)
            try:
                send_mail([form.email.data],
                          title='MUMT-MIS: Password Reset. ตั้งรหัสผ่านใหม่สำหรับระบบ MUMT-MIS',
                          message=message)
            except:
                flash('ระบบไม่สามารถส่งอีเมลได้กรุณาตรวจสอบอีกครั้ง'.format(form.email.data),'danger')
            else:
                flash('โปรดตรวจสอบอีเมลของท่านเพื่อทำการแก้ไขรหัสผ่านภายใน 20 นาที', 'success')
            return redirect(url_for('academic_services.login'))
        else:
            for er in form.errors:
                flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('academic_services/forget_password.html', form=form)


@academic_services.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    token = request.args.get('token')
    serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'))
    try:
        token_data = serializer.loads(token, max_age=72000)
    except:
        return 'รหัสสำหรับทำการตั้งค่า password หมดอายุหรือไม่ถูกต้อง'
    user = ServiceCustomerAccount.query.filter_by(email=token_data.get('email')).first()
    if not user:
        flash('ไม่พบชื่อบัญชีในฐานข้อมูล')
        return redirect(url_for('academic_services.customer_index'))

    form = ResetPasswordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            user.password = form.new_password.data
            db.session.add(user)
            db.session.commit()
            flash('ตั้งรหัสผ่านใหม่เรียบร้อย', 'success')
            return redirect(url_for('academic_services.customer_index'))
        else:
            for er in form.errors:
                flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('academic_services/reset_password.html', form=form)


@academic_services.route('/customer/index', methods=['GET', 'POST'])
def customer_index():
    labs = ServiceLab.query.all()
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(ServiceCustomerAccount).filter_by(email=form.email.data).first()
        if user:
            pwd = form.password.data
            if user.verify_password(pwd):
                login_user(user)
                identity_changed.send(current_app._get_current_object(), identity=Identity(user.id))
                next_url = request.args.get('next', url_for('academic_services.customer_index'))
                if not is_safe_url(next_url):
                    return abort(400)
                else:
                    flash('ลงทะเบียนเข้าใช้งานสำเร็จ', 'success')
                    if user.is_first_login == True :
                        return redirect(url_for('academic_services.lab_index', menu='new'))
                    else:
                        user.is_first_login = True
                        db.session.add(user)
                        db.session.commit()
                        return redirect(url_for('academic_services.customer_account', menu='view'))
            else:
                flash('รหัสผ่านไม่ถูกต้อง กรุณาลองอีกครั้ง', 'danger')
                return redirect(url_for('academic_services.customer_index'))
        else:
            flash('ไม่พบบัญชีผู้ใช้งาน', 'danger')
            return redirect(url_for('academic_services.customer_index'))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('academic_services/customer_index.html', form=form, labs=labs)


@academic_services.route('/customer/lab/index')
@login_required
def lab_index():
    menu = request.args.get('menu')
    labs = ServiceLab.query.all()
    return render_template('academic_services/lab_index.html', menu=menu, labs=labs)


@academic_services.route('/customer/lab/detail', methods=['GET', 'POST'])
def detail_lab_index():
    cat = request.args.get('cat')
    code = request.args.get('code')
    labs = ServiceLab.query.filter_by(code=code)
    return render_template('academic_services/detail_lab_index.html', cat=cat, labs=labs, code=code)


@academic_services.route('/page/pdpd')
def pdpa_index():
    return render_template('academic_services/pdpa_page.html')


@academic_services.route('/accept-policy', methods=['POST'])
def accept_policy():
    session['policy_accepted'] = True
    return redirect(url_for('academic_services.create_customer_account'))


@academic_services.route('/customer/account', methods=['GET', 'POST'])
def account():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if new_password and confirm_password:
            if new_password == confirm_password:
                current_user.password = new_password
                db.session.add(current_user)
                db.session.commit()
                flash('รหัสผ่านแก้ไขแล้ว', 'success')
            else:
                flash('รหัสผ่านไม่ตรงกัน', 'danger')
        else:
            flash('กรุณากรอกรหัสใหม่', 'danger')
    return render_template('academic_services/account.html')


@academic_services.route('/customer/view', methods=['GET', 'POST'])
def customer_account():
    menu = request.args.get('menu')
    return render_template('academic_services/customer_account.html', menu=menu)


@academic_services.route('/customer/account/add', methods=['GET', 'POST'])
def create_customer_account(customer_id=None):
    if session.get('policy_accepted'):
        menu = request.args.get('menu')
        form = ServiceCustomerAccountForm()
        if form.validate_on_submit():
            account = ServiceCustomerAccount()
            form.populate_obj(account)
            db.session.add(account)
            db.session.commit()
            serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'))
            token = serializer.dumps({'email': form.email.data})
            scheme = 'http' if current_app.debug else 'https'
            url = url_for('academic_services.verify_email', token=token, _external=True, _scheme=scheme)
            message = 'Click the link below to confirm.' \
                        ' กรุณาคลิกที่ลิงค์เพื่อทำการยืนยันการสมัครบัญชีระบบ MUMT-MIS\n\n{}'.format(url)
            send_mail([form.email.data], title='ยืนยันการสมัครบัญชีระบบ MUMT-MIS', message=message)
            return redirect(url_for('academic_services.verify_email_page'))
        else:
            for er in form.errors:
                flash("{} {}".format(er, form.errors[er]), 'danger')
    else:
        return redirect(url_for('academic_services.accept_policy'))
    return render_template('academic_services/create_customer.html', form=form, customer_id=customer_id,
                           menu=menu)


@academic_services.route('/page/verify')
def verify_email_page():
    return  render_template('academic_services/verify_email_page.html')


@academic_services.route('/email-verification', methods=['GET', 'POST'])
def verify_email():
    token = request.args.get('token')
    serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'))
    try:
        token_data = serializer.loads(token, max_age=72000)
    except:
        return 'รหัสสำหรับทำการสมัครบัญชีหมดอายุหรือไม่ถูกต้อง'
    user = ServiceCustomerAccount.query.filter_by(email=token_data.get('email')).first()
    if not user:
        flash('ไม่พบชื่อบัญชีผู้ใช้งาน กรุณาลงทะเบียนใหม่อีกครั้ง', 'danger')
    elif user.verify_datetime:
        flash('ได้รับการยืนยันอีเมลแล้ว', 'info')
    else:
        user.verify_datetime = arrow.now('Asia/Bangkok').datetime
        db.session.add(user)
        db.session.commit()
        flash('ยืนยันอีเมลเรียบร้อยแล้ว', 'success')
    return redirect(url_for('academic_services.customer_index'))


@academic_services.route('/customer/add', methods=['GET', 'POST'])
@academic_services.route('/customer/edit/<int:customer_id>', methods=['GET', 'POST'])
def edit_customer_account(customer_id=None):
    menu = request.args.get('menu')
    account = ServiceCustomerAccount.query.get(current_user.id)
    if customer_id:
        customer = ServiceCustomerInfo.query.get(customer_id)
        form = ServiceCustomerInfoForm(obj=customer)
    else:
        form = ServiceCustomerInfoForm()
        customer = ServiceCustomerInfo.query.all()
    if form.validate_on_submit():
        if customer_id is None:
            customer = ServiceCustomerInfo()
        form.populate_obj(customer)
        if customer_id is None:
            account.customer_info = customer
            db.session.add(account)
        db.session.add(customer)
        if customer.type.type == 'บุคคล' and customer_id is None:
            contact = ServiceCustomerContact(name=customer.cus_name, phone_number=customer.phone_number,
                                             email=current_user.email, adder_id=current_user.id)
            db.session.add(contact)
        db.session.commit()
        flash('บันทึกข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('academic_services/modal/edit_customer_modal.html', form=form, menu=menu,
                           customer_id=customer_id, customer=customer)


@academic_services.route('/edit_password', methods=['GET', 'POST'])
def edit_password():
    menu = request.args.get('menu')
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if new_password and confirm_password:
            if new_password == confirm_password:
                current_user.password = new_password
                db.session.add(current_user)
                db.session.commit()
                flash('รหัสผ่านแก้ไขแล้ว', 'success')
            else:
                flash('รหัสผ่านไม่ตรงกัน', 'danger')
        else:
            flash('กรุณากรอกรหัสใหม่', 'danger')
    return render_template('academic_services/edit_password.html', menu=menu)


@academic_services.route('/academic-service-form', methods=['GET'])
def get_request_form():
    code = request.args.get('code')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet(sub_lab.sheet)
    df = pandas.DataFrame(sheet.get_all_records())
    form = create_request_form(df)()
    template = ''
    for f in form:
        template += str(f)
    return template


@academic_services.route('/academic-service-request', methods=['GET'])
@login_required
def create_service_request():
    code = request.args.get('code')
    return render_template('academic_services/request_form.html', code=code)


@academic_services.route('/submit-request', methods=['POST'])
@academic_services.route('/submit-request/<int:request_id>', methods=['POST'])
def submit_request(request_id=None):
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab).first()
    else:
        code = request.args.get('code')
        sub_lab = ServiceSubLab.query.filter_by(code=code).first()
        request_no = ServiceNumberID.get_number('RQ', db, lab=sub_lab.lab.code if sub_lab and sub_lab.lab.code=='protein' else code)
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
        req = ServiceRequest.query.get(request_id)
        req.data = format_data(form.data)
        req.modified_at = arrow.now('Asia/Bangkok').datetime
        req.product = products
    else:
        req = ServiceRequest(customer_id=current_user.id, created_at=arrow.now('Asia/Bangkok').datetime, lab=code,
                             request_no=request_no.number, product=products, data=format_data(form.data))
        request_no.count += 1
    db.session.add(req)
    db.session.commit()
    return redirect(url_for('academic_services.view_request', request_id=req.id, menu='request'))


@academic_services.route('/customer/request/index')
@login_required
def request_index():
    menu = request.args.get('menu')
    return render_template('academic_services/request_index.html', menu=menu)


@academic_services.route('/api/request/index')
def get_requests():
    query = ServiceRequest.query.filter_by(customer_id=current_user.id)
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ServiceRequest.created_at.contains(search))
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


@academic_services.route('/request/view/<int:request_id>')
@login_required
def view_request(request_id=None):
    menu = request.args.get('menu')
    service_request = ServiceRequest.query.get(request_id)
    addresses = ServiceCustomerAddress.query.filter_by(address_type='quotation',
                                                       customer_id=current_user.customer_info.id)
    address_count = addresses.count()
    return render_template('academic_services/view_request.html', service_request=service_request, menu=menu,
                           address_count=address_count)


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
                                values.append(f"{f. label.text} : {', '.join(f.data)}")
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
                        ที่อยู่ : {address}<br/>
                        เบอร์โทรศัพท์ : {phone_number}<br/>
                        อีเมล : {email}
                    </para>
                    '''.format(customer=current_user.customer_info.cus_name,
                               address=', '.join([address.address for address in current_user.customer_info.addresses if address.address_type == 'customer']),
                               phone_number=current_user.customer_info.phone_number,
                               email=current_user.customer_info.email)

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


@academic_services.route('/request/pdf/<int:request_id>', methods=['GET'])
def export_request_pdf(request_id):
    service_request = ServiceRequest.query.get(request_id)
    buffer = generate_request_pdf(service_request)
    return send_file(buffer, download_name='Request_form.pdf', as_attachment=True)


@academic_services.route('/api/quotation/address', methods=['GET'])
@login_required
def get_quotation_addresses():
    results = []
    search = request.args.get('term', '')
    addresses = ServiceCustomerAddress.query.filter_by(address_type='quotation', customer_id=current_user.customer_info.id)
    if search:
        addresses = [address for address in addresses if search.lower() in address.address.lower()]
    for address in addresses:
        results.append({
            "id": address.id,
            "text": f'{address.name}: {address.taxpayer_identification_no}: {address.address}: {address.phone_number}'
        })
    return jsonify({'results': results})


@academic_services.route('/customer/quotation/address/add/<int:request_id>', methods=['GET', 'POST'])
def add_quotation_address(request_id):
    menu = request.args.get('menu')
    service_request = ServiceRequest.query.get(request_id)
    addresses = ServiceCustomerAddress.query.filter_by(address_type='quotation', customer_id=current_user.customer_info.id)
    address_count = addresses.count()
    if request.method == 'POST':
        if address_count > 1:
            for address in addresses:
                if address.is_used:
                    address.is_used = False
                    db.session.add(address)
            for item_id in request.form.getlist('quotation_address'):
                address = ServiceCustomerAddress.query.get(int(item_id))
                address.is_used = True
                db.session.add(address)
        else:
            for address in addresses:
                address.is_used = True
                db.session.add(address)
        service_request.status = 'รอเจ้าหน้าที่ออกใบเสนอราคา'
        db.session.add(service_request)
        db.session.commit()
        flash('อัพเดตข้อมูลสำเร็จ', 'success')
        if address_count > 1:
            resp = make_response()
            resp.headers['HX-Redirect'] = url_for('academic_services.request_index', menu=menu)
            return resp
        else:
            return redirect(url_for('academic_services.request_index', menu=menu))
    return render_template('academic_services/modal/add_quotation_address_modal.html', menu=menu,
                           request_id=request_id)


@academic_services.route('/customer/quotation/index')
@login_required
def quotation_index():
    menu = request.args.get('menu')
    return render_template('academic_services/quotation_index.html', menu=menu)


@academic_services.route('/api/quotation/index')
def get_quotations():
    query = ServiceQuotation.query.filter(ServiceQuotation.request.has(customer_id=current_user.id))
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


@academic_services.route('/quotation/view/<int:quotation_id>')
@login_required
def view_quotation(quotation_id):
    menu = request.args.get('menu')
    quotation = ServiceQuotation.query.get(quotation_id)
    return render_template('academic_services/view_quotation.html', quotation_id=quotation_id, menu=menu,
                           quotation=quotation)


def generate_quotation_pdf(quotation, sign=False, cancel=False):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 60, 60)

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

    affiliation = '''<para align=center><font size=10>
                   คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>
                   FACULTY OF MEDICAL TECHNOLOGY, MAHIDOL UNIVERSITY
                   </font></para>
                   '''

    lab_address = '''<para><font size=12>
                        {address}
                        </font></para>'''.format(address=sub_lab.address)

    quotation_info = '''<br/><br/><font size=10>
                เลขที่/No. {quotation_no}<br/>
                วันที่/Date {issued_date}
                </font>
                '''

    quotation_no = quotation.quotation_no
    issued_date = arrow.get(quotation.created_at.astimezone(bangkok)).format(fmt='DD MMMM YYYY', locale='th-th')
    quotation_info_ori = quotation_info.format(quotation_no=quotation_no,
                                                   issued_date=issued_date
                                                   )

    header_content_ori = [[Paragraph(lab_address, style=style_sheet['ThaiStyle']),
                           [logo, Paragraph(affiliation, style=style_sheet['ThaiStyle'])],
                           [],
                           Paragraph(quotation_info_ori, style=style_sheet['ThaiStyle'])]]

    header_styles = TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ])

    header_ori = Table(header_content_ori, colWidths=[150, 200, 50, 100])

    header_ori.hAlign = 'CENTER'
    header_ori.setStyle(header_styles)

    customer = '''<para><font size=11>
                    ลูกค้า/Customer {customer}<br/>
                    ที่อยู่/Address {address}<br/>
                    เลขประจำตัวผู้เสียภาษี/Taxpayer identification no {taxpayer_identification_no}
                    </font></para>
                    '''.format(customer=quotation.address.name,
                               address=quotation.address.address,
                               phone_number=quotation.address.phone_number,
                               taxpayer_identification_no=quotation.request.customer.customer_info.taxpayer_identification_no)

    customer_table = Table([[Paragraph(customer, style=style_sheet['ThaiStyle'])]], colWidths=[540, 280])
    customer_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                  ('VALIGN', (0, 0), (-1, -1), 'TOP')]))

    items = [[Paragraph('<font size=10>ลำดับ / No.</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>รายการ / Description</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>จำนวน / Quantity</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>ราคาหน่วย(บาท) / Unit Price</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>ราคารวม(บาท) / Total</font>', style=style_sheet['ThaiStyleCenter']),
              ]]
    discount = 0

    for n, item in enumerate(quotation.quotation_items, start=1):
        if item.discount:
            discount += item.discount
        item_record = [Paragraph('<font size=12>{}</font>'.format(n), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{}</font>'.format(item.item), style=style_sheet['ThaiStyle']),
                       Paragraph('<font size=12>{}</font>'.format(item.quantity), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.unit_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.total_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       ]
        items.append(item_record)
    if discount > 0:
        discount_record = [Paragraph('<font size=12>{}</font>'.format(n + 1), style=style_sheet['ThaiStyleCenter']),
                           Paragraph('<font size=12>ส่วนลด</font>', style=style_sheet['ThaiStyle']),
                           Paragraph('<font size=12>1</font>', style=style_sheet['ThaiStyleCenter']),
                           Paragraph('<font size=12>{:,.2f}</font>'.format(discount),
                                     style=style_sheet['ThaiStyleNumber']),
                           Paragraph('<font size=12>{:,.2f}</font>'.format(discount),
                                     style=style_sheet['ThaiStyleNumber']),
                           ]
        items.append(discount_record)

    net_price = quotation.total_price - discount
    n = len(items)

    for i in range(18-n):
        items.append([
            Paragraph('<font size=12>&nbsp; </font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
            Paragraph('<font size=12></font>', style=style_sheet['ThaiStyleNumber']),
        ])

    items.append([
        Paragraph('<font size=12>{}</font>'.format(bahttext(net_price)), style=style_sheet['ThaiStyleCenter']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>รวมทั้งสิ้น</font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(net_price), style=style_sheet['ThaiStyleNumber'])
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

    remark = [[Paragraph('<font size=14>หมายเหตุ : กำหนดยื่นเสนอราคา 90 วัน</font>', style=style_sheet['ThaiStyle'])]]
    remark_table = Table(remark, colWidths=[537, 150, 50])

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
    data.append(KeepTogether(Paragraph('<para align=center><font size=16>ใบเสนอราคา / QUOTATION<br/><br/></font></para>',
                                       style=style_sheet['ThaiStyle'])))
    data.append(KeepTogether(Spacer(1, 12)))
    data.append(KeepTogether(customer_table))
    data.append(KeepTogether(Spacer(1, 16)))
    data.append(KeepTogether(item_table))
    data.append(KeepTogether(Spacer(1, 5)))
    data.append(KeepTogether(remark_table))
    data.append(KeepTogether(Spacer(1, 10)))
    data.append(KeepTogether(text_table))
    data.append(KeepTogether(Spacer(1, 25)))
    data.append(KeepTogether(sign_table))

    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    buffer.seek(0)
    return buffer


@academic_services.route('/quotation/pdf/<int:quotation_id>', methods=['GET'])
def export_quotation_pdf(quotation_id):
    quotation = ServiceQuotation.query.get(quotation_id)
    buffer = generate_quotation_pdf(quotation)
    return send_file(buffer, download_name='Quotation.pdf', as_attachment=True)


@academic_services.route('/customer/request/issue/<int:request_id>', methods=['GET', 'POST'])
def issue_quotation(request_id):
    menu = request.args.get('menu')
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        service_request.status = 'รอออกใบเสนอราคา'
        db.session.add(service_request)
        db.session.commit()
        scheme = 'http' if current_app.debug else 'https'
        admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=service_request.lab)).all()
        link = url_for("service_admin.view_request", request_id=request_id, _external=True, _scheme=scheme)
        title = 'แจ้งการขอใบเสนอราคา'
        message = f'''มีการขอใบเสนอราคาของใบคำร้องขอ {service_request.request_no} กรุณาดำเนินการออกใบเสนอราคา\n\n'''
        message += f'''ลิ้งค์สำหรับออกใบเสนอราคา : {link}'''
        send_mail([a.admin.email + '@mahidol.ac.th' for a in admins if not a.is_supervisor], title, message)
        flash('ขอใบเสนอราคาสำเร็จ', 'success')
        return redirect(url_for('academic_services.request_index', menu=menu))


@academic_services.route('/customer/quotation/confirm/<int:quotation_id>', methods=['GET', 'POST'])
def confirm_quotation(quotation_id):
    menu = request.args.get('menu')
    quotation = ServiceQuotation.query.get(quotation_id)
    quotation.status = 'ยืนยันใบเสนอราคา'
    quotation.request.status = 'ยืนยันใบเสนอราคา'
    db.session.add(quotation)
    sample = ServiceSample(request_id=quotation.request_id)
    db.session.add(sample)
    db.session.commit()
    flash('ยืนยันสำเร็จ', 'success')
    return redirect(url_for('academic_services.sample_index', menu=menu, tab='appointment'))


@academic_services.route('/customer/quotation/cancel/<int:quotation_id>', methods=['GET', 'POST'])
def cancel_quotation(quotation_id):
    menu = request.args.get('menu')
    quotation = ServiceQuotation.query.get(quotation_id)
    quotation.status = 'ยกเลิกใบเสนอราคา'
    quotation.request.status = 'ยกเลิกใบเสนอราคา'
    db.session.add(quotation)
    db.session.commit()
    flash('ยกเลิกใบเสนอราคาสำเร็จ', 'success')
    return redirect(url_for('academic_services.quotation_index', menu=menu))


@academic_services.route('/customer/contact/index')
@login_required
def customer_contact_index():
    menu = request.args.get('menu')
    contacts = ServiceCustomerContact.query.filter_by(adder_id=current_user.id)
    return render_template('academic_services/customer_contact_index.html', contacts=contacts, menu=menu,
                           adder_id=current_user.id)


@academic_services.route('/api/contact/index')
def get_customer_contacts():
    adder_id = request.args.get('adder_id')
    query = ServiceCustomerContact.query.filter_by(adder_id=adder_id)
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ServiceCustomerContact.name.contains(search))
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


@academic_services.route('/customer/contact/add', methods=['GET', 'POST'])
@academic_services.route('/customer/contact/edit/<int:contact_id>', methods=['GET', 'POST'])
def create_customer_contact(contact_id=None):
    menu = request.args.get('menu')
    if contact_id:
        contact = ServiceCustomerContact.query.get(contact_id)
        form = ServiceCustomerContactForm(obj=contact)
    else:
        form = ServiceCustomerContactForm()
        contact = ServiceCustomerContact.query.all()
    if form.validate_on_submit():
        if contact_id is None:
            contact = ServiceCustomerContact()
        form.populate_obj(contact)
        if contact_id is None:
            contact.adder_id = current_user.id
        db.session.add(contact)
        db.session.commit()
        if contact_id:
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
        else:
            flash('เพิ่มข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('academic_services/modal/create_customer_contact_modal.html', form=form,
                           menu=menu, contact_id=contact_id, )


@academic_services.route('/customer/contact/delete/<int:contact_id>', methods=['GET', 'DELETE'])
def delete_customer_contact(contact_id):
    if contact_id:
        contact = ServiceCustomerContact.query.get(contact_id)
        db.session.delete(contact)
        db.session.commit()
        flash('ลบข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@academic_services.route('/customer/address/index')
def address_index():
    menu = request.args.get('menu')
    addresses = ServiceCustomerAddress.query.filter_by(customer_id=current_user.customer_info.id).all()
    return render_template('academic_services/address_index.html', addresses=addresses, menu=menu)


@academic_services.route('/customer/address/add', methods=['GET', 'POST'])
@academic_services.route('/customer/address/edit/<int:address_id>', methods=['GET', 'POST'])
def create_address(address_id=None):
    menu = request.args.get('menu')
    type = request.args.get('type')
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
            address.customer_id = current_user.customer_info.id
            address.address_type = type
        db.session.add(address)
        db.session.commit()
        if address_id:
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
        else:
            flash('เพิ่มข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('academic_services/modal/create_address_modal.html', address_id=address_id,
                           type=type, form=form, menu=menu)


@academic_services.route('/customer/address/delete/<int:address_id>', methods=['GET', 'DELETE'])
def delete_address(address_id):
    address = ServiceCustomerAddress.query.get(address_id)
    db.session.delete(address)
    db.session.commit()
    flash('ลบข้อมูลสำเร็จ', 'success')
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@academic_services.route('/customer/address/submit/<int:address_id>', methods=['GET', 'POST'])
def submit_same_address(address_id):
    if request.method == 'POST':
        address = ServiceCustomerAddress.query.get(address_id)
        db.session.expunge(address)
        make_transient(address)
        address.name = address.name
        address.address_type = 'customer'
        address.address = address.address
        address.phone_number = address.phone_number
        address.remark = None
        address.customer_account_id = current_user.id
        address.id = None
        db.session.add(address)
        db.session.commit()
        flash('ยืนยันสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@academic_services.route('/customer/sample/index')
def sample_index():
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    samples = ServiceSample.query.filter(ServiceSample.request.has(customer_id=current_user.id))
    return render_template('academic_services/sample_index.html', samples=samples, menu=menu, tab=tab)


@academic_services.route('/customer/sample/add/<int:sample_id>', methods=['GET', 'POST'])
def create_sample_appointment(sample_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    sample = ServiceSample.query.get(sample_id)
    service_request = ServiceRequest.query.get(sample.request_id)
    form = ServiceSampleForm(obj=sample)
    admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=sample.request.lab)).all()
    appointment_date = form.appointment_date.data.astimezone(localtz) if form.appointment_date.data else None
    if form.validate_on_submit():
        form.populate_obj(sample)
        if form.ship_type.data == 'ส่งด้วยตนเอง':
            sample.appointment_date = arrow.get(form.appointment_date.data, 'Asia/Bangkok').datetime
        else:
            sample.appointment_date = None
        db.session.add(sample)
        db.session.commit()
        if service_request.status == 'รอรับตัวอย่าง':
            title = 'แจ้งแก้ไขนัดหมายส่งตัวอย่างการทดสอบ'
            message = f'''มีการแจ้งแก้ไขนัดหมายส่งตัวอย่างการทดสอบของใบคำร้องขอ {sample.request.request_no} เป็น\n\n'''
            if sample.appointment_date:
                message += f'''วันที่ : {sample.appointment_date.astimezone(localtz).strftime('%d/%m/%Y')}\n\n'''
                message += f'''เวลา : {sample.appointment_date.astimezone(localtz).strftime('%H:%M')}\n\n'''
            message += f'''สภานที่ : {sample.location}\n\n'''
            message += f'''การส่งตัวอย่าง : {sample.ship_type}\n\n'''
            message += f'''ขออภัยในความไม่สะดวก'''
        else:
            title = 'แจ้งนัดหมายส่งตัวอย่างการทดสอบ'
            message = f'''มีการแจ้งนัดหมายส่งตัวอย่างการทดสอบของใบคำร้องขอ {sample.request.request_no} เป็น\n\n'''
            if sample.appointment_date:
                message += f'''วันที่ : {sample.appointment_date.astimezone(localtz).strftime('%d/%m/%Y')}\n\n'''
                message += f'''เวลา : {sample.appointment_date.astimezone(localtz).strftime('%H:%M')}\n\n'''
            message += f'''สภานที่ : {sample.location}\n\n'''
            message += f'''การส่งตัวอย่าง : {sample.ship_type}\n\n'''
        send_mail([a.admin.email + '@mahidol.ac.th' for a in admins], title, message)
        if service_request.status == 'ยืนยันใบเสนอราคา':
            service_request.status == 'รอรับตัวอย่าง'
            db.session.add(service_request)
            db.session.commit()
        flash('อัพเดตข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('academic_services/modal/create_sample_appointment_modal.html', form=form,
                           tab=tab, menu=menu, sample_id=sample_id, appointment_date=appointment_date)


@academic_services.route('/customer/sample/tracking_number/add/<int:sample_id>', methods=['GET', 'POST'])
def add_tracking_number(sample_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    sample = ServiceSample.query.get(sample_id)
    form = ServiceSampleForm(obj=sample)
    if form.validate_on_submit():
        form.populate_obj(sample)
        sample.request.status = 'รอรับตัวอย่าง'
        db.session.add(sample)
        db.session.commit()
        flash('อัพเดตข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('academic_services/modal/add_tracking_number_modal.html', form=form, tab=tab,
                           menu=menu, sample_id=sample_id)


@academic_services.route('/customer/sample/appointment/view/<int:sample_id>')
@login_required
def view_sample_appointment(sample_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    sample = ServiceSample.query.get(sample_id)
    return render_template('academic_services/view_sample_appointment.html', sample=sample, tab=tab, menu=menu)


@academic_services.route('/customer/sample/test/view/<int:sample_id>')
@login_required
def view_test_sample(sample_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    sample = ServiceSample.query.get(sample_id)
    return render_template('academic_services/view_test_sample.html', sample=sample, tab=tab, menu=menu)


@academic_services.route('/customer/payment/index')
@login_required
def payment_index():
    menu = request.args.get('menu')
    return render_template('academic_services/payment_index.html', menu=menu)


@academic_services.route('/api/payment/index')
def get_payments():
    query = ServicePayment.query.filter(ServicePayment.invoice.has(
        ServiceInvoice.quotation.has(
            ServiceQuotation.request.has(customer_id=current_user.id))))
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ServicePayment.invoice_no.contains(search))
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


@academic_services.route('/customer/payment/add/<int:payment_id>', methods=['GET', 'POST'])
def add_payment(payment_id):
    menu = request.args.get('menu')
    payment = ServicePayment.query.get(payment_id)
    form = ServicePaymentForm(obj=payment)
    if form.validate_on_submit():
        form.populate_obj(payment)
        file = form.file_upload.data
        payment.paid_at = arrow.now('Asia/Bangkok').datetime
        payment.sender_id = current_user.id
        payment.status = 'รอเจ้าหน้าที่ตรวจสอบการชำระเงิน'
        payment.invoice.quotation.request.status = 'รอเจ้าหน้าที่ตรวจสอบการชำระเงิน'
        drive = initialize_gdrive()
        if file:
            file_name = secure_filename(file.filename)
            file.save(file_name)
            file_drive = drive.CreateFile({'title': file_name,
                                           'parents': [{'id': FOLDER_ID, "kind": "drive#fileLink"}]})
            file_drive.SetContentFile(file_name)
            file_drive.Upload()
            permission = file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
            payment.url = file_drive['id']
            payment.bill = file_name
        db.session.add(payment)
        db.session.commit()
        flash('อัพเดตสลิปสำเร็จ', 'success')
        return redirect(url_for('academic_services.payment_index', menu=menu))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('academic_services/add_payment.html', payment_id=payment_id, payment=payment,
                           menu=menu, form=form)


@academic_services.route('/customer/result/index')
def result_index():
    menu = request.args.get('menu')
    results = ServiceResult.query.filter(ServiceResult.request.has(customer_id=current_user.id))
    for result in results:
        if result.url:
            file_upload = drive.CreateFile({'id': result.url})
            file_upload.FetchMetadata()
            result.file_url = f"https://drive.google.com/uc?export=download&id={result.url}"
        else:
            result.file_url = None
    return render_template('academic_services/result_index.html', results=results, menu=menu)


@academic_services.route('/customer/invoice/index')
@login_required
def invoice_index():
    menu = request.args.get('menu')
    return render_template('academic_services/invoice_index.html', menu=menu)


@academic_services.route('/api/invoice/index')
def get_invoices():
    query = ServiceInvoice.query.filter(ServiceInvoice.status=='ออกใบแจ้งหนี้', ServiceInvoice.quotation.has(
        ServiceQuotation.request.has(customer_id=current_user.id)
    ))
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


@academic_services.route('/invoice/view/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    menu = request.args.get('menu')
    return render_template('academic_services/view_invoice.html', invoice_id=invoice_id, menu=menu)


def generate_invoice_pdf(invoice, sign=False, cancel=False):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 60, 60)

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

    affiliation = '''<para align=center><font size=10>
                คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>
                FACULTY OF MEDICAL TECHNOLOGY, MAHIDOL UNIVERSITY
                </font></para>
                '''

    lab_address = '''<para><font size=12>
                        {address}
                        </font></para>'''.format(address=sub_lab.address)

    invoice_info = '''<br/><br/><font size=10>
                เลขที่/No. {invoice_no}<br/>
                วันที่/Date {issued_date}
                </font>
                '''

    invoice_no = invoice.invoice_no
    issued_date = arrow.get(invoice.created_at.astimezone(bangkok)).format(fmt='DD MMMM YYYY', locale='th-th')
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

    customer = '''<para><font size=11>
                ลูกค้า/Customer {customer}<br/>
                ที่อยู่/Address {address}<br/>
                เลขประจำตัวผู้เสียภาษี/Taxpayer identification no {taxpayer_identification_no}
                </font></para>
                '''.format(customer=invoice.quotation.address.name,
                                   address=invoice.quotation.address.address,
                                   phone_number=invoice.quotation.address.phone_number,
                                   taxpayer_identification_no=invoice.quotation.request.customer.customer_info.taxpayer_identification_no)

    customer_table = Table([[Paragraph(customer, style=style_sheet['ThaiStyle'])]], colWidths=[540, 280])

    customer_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP')]))

    items = [[Paragraph('<font size=10>ลำดับ / No.</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>รายการ / Description</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>จำนวน / Quantity</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>ราคาหน่วย(บาท) / Unit Price</font>', style=style_sheet['ThaiStyleCenter']),
              Paragraph('<font size=10>ราคารวม(บาท) / Total</font>', style=style_sheet['ThaiStyleCenter']),
              ]]
    discount = 0

    for n, item in enumerate(invoice.invoice_items, start=1):
        if item.discount:
            discount += item.discount
        item_record = [Paragraph('<font size=12>{}</font>'.format(n), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{}</font>'.format(item.item), style=style_sheet['ThaiStyle']),
                       Paragraph('<font size=12>{}</font>'.format(item.quantity), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.unit_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.total_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       ]
        items.append(item_record)

    if discount > 0:
        discount_record = [Paragraph('<font size=12>{}</font>'.format(n + 1), style=style_sheet['ThaiStyleCenter']),
                           Paragraph('<font size=12>ส่วนลด</font>', style=style_sheet['ThaiStyle']),
                           Paragraph('<font size=12>1</font>', style=style_sheet['ThaiStyleCenter']),
                           Paragraph('<font size=12>{:,.2f}</font>'.format(discount),
                                     style=style_sheet['ThaiStyleNumber']),
                           Paragraph('<font size=12>{:,.2f}</font>'.format(discount),
                                     style=style_sheet['ThaiStyleNumber']),
                           ]
        items.append(discount_record)

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


@academic_services.route('/invoice/pdf/<int:invoice_id>', methods=['GET'])
def export_invoice_pdf(invoice_id):
    invoice = ServiceInvoice.query.get(invoice_id)
    buffer = generate_invoice_pdf(invoice)
    return send_file(buffer, download_name='Invoice.pdf', as_attachment=True)


@academic_services.route('/customer/request/cancel/<int:request_id>', methods=['GET'])
def cancel_request(request_id):
    menu = request.args.get('menu')
    service_request = ServiceRequest.query.get(request_id)
    service_request.status = 'ยกเลิกใบคำขอรับบริการ'
    db.session.add(service_request)
    db.session.commit()
    flash('ยกเลิกคำขอรับบริการสำเร็จ', 'success')
    return redirect(url_for('academic_services.request_index', menu=menu))


@academic_services.route('/edit/academic-service-form', methods=['GET'])
def edit_request_form():
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab).first()
    sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet(sub_lab.sheet)
    df = pandas.DataFrame(sheet.get_all_records())
    data = service_request.data
    form = create_request_form(df)(**data)
    template = ''
    for f in form:
        template += str(f)
    return template


@academic_services.route('/academic-service-request/<int:request_id>', methods=['GET'])
@login_required
def edit_service_request(request_id):
    return render_template('academic_services/edit_request.html', request_id=request_id)


@academic_services.route('/customer/result/edit/<int:result_id>', methods=['GET', 'POST'])
def edit_result(result_id):
    if result_id:
        result = ServiceResult.query.get(result_id)
        result.status = 'ขอแก้ไขรายงานผล'
        result.file_result = None
        result.url = None
        result.approver_id = current_user.id
        result.request.status = 'ขอแก้ไขรายงานผล'
        db.session.add(result)
        db.session.commit()
        flash('ดำเนินการขอแก้ไขแล้ว', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@academic_services.route('/customer/result/acknowledge/<int:result_id>', methods=['GET', 'POST'])
def acknowledge_result(result_id):
    if result_id:
        result = ServiceResult.query.get(result_id)
        result.status = 'รับทราบผลการทดสอบ'
        result.approver_id = current_user.id
        result.request.status = 'รับทราบผลการทดสอบ'
        db.session.add(result)
        db.session.commit()
        flash('รับทราบผลเรียบร้อยแล้ว', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@academic_services.route('/customer/payment/view/<int:payment_id>')
def view_payment(payment_id):
    menu = request.args.get('menu')
    payment = ServicePayment.query.get(payment_id)
    return render_template('academic_services/view_payment.html', payment=payment, menu=menu)