import os
import qrcode
from bahttext import bahttext
from sqlalchemy import or_, case
from datetime import date
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
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, TableStyle, Table, Spacer, KeepTogether, PageBreak, \
    Indenter
from sqlalchemy.orm import make_transient
from wtforms import FormField, FieldList
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
from app.auth.views import line_bot_api
from app.main import app, get_credential, json_keyfile
from app.academic_services import academic_services
from app.academic_services.forms import (ServiceCustomerInfoForm, LoginForm, ForgetPasswordForm, ResetPasswordForm,
                                         ServiceCustomerAccountForm, create_request_form, ServiceCustomerContactForm,
                                         ServiceCustomerAddressForm, ServiceSampleForm, ServicePaymentForm,
                                         ServiceRequestForm)
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

from app.models import Holidays
from app.service_admin.forms import ServiceQuotationForm

localtz = timezone('Asia/Bangkok')

sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
pdfmetrics.registerFont(sarabun_font)
style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))
style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', alignment=TA_CENTER))
style_sheet.add(ParagraphStyle(name='ThaiStyleRight', fontName='Sarabun', alignment=TA_RIGHT))

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

bangkok = pytz.timezone('Asia/Bangkok')
S3_BUCKET_NAME = os.getenv('BUCKETEER_BUCKET_NAME')


def generate_url(file_url):
    url = s3.generate_presigned_url('get_object',
                                    Params={'Bucket': S3_BUCKET_NAME, 'Key': file_url},
                                    ExpiresIn=3600)
    return url


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


def send_mail_for_account(recp, title, message):
    message = Message(subject=title, html=message, recipients=recp, body=None)
    mail.send(message)


def format_data(data):
    if isinstance(data, dict):
        return {k: format_data(v) for k, v in data.items() if k != "csrf_token" and k != 'submit'}
    elif isinstance(data, list):
        return [format_data(item) for item in data]
    elif isinstance(data, (date)):
        return data.isoformat()
    return data


def get_status(s_id):
    statuses = ServiceStatus.query.filter_by(status_id=s_id).first()
    status_id = statuses.id
    return status_id


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


@academic_services.route('/aws-s3/download/<key>', methods=['GET'])
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
                    if user.is_first_login == False:
                        user.is_first_login = True
                        db.session.add(user)
                        db.session.commit()
                    if current_user.customer_info:
                        return redirect(url_for('academic_services.lab_index', menu='new'))
                    else:
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
@login_required
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
            message = 'Click the link below to reset the password.' \
                      ' กรุณาคลิกที่ลิงค์เพื่อทำการตั้งรหัสผ่านใหม่\n\n{}'.format(url)
            try:
                send_mail([form.email.data],
                          title='MUMT-MIS: Password Reset. ตั้งรหัสผ่านใหม่สำหรับระบบ MUMT-MIS',
                          message=message)
            except:
                flash('ระบบไม่สามารถส่งอีเมลได้กรุณาตรวจสอบอีกครั้ง'.format(form.email.data), 'danger')
            else:
                flash('โปรดตรวจสอบอีเมลของท่านเพื่อทำการแก้ไขรหัสผ่านภายใน 20 นาที', 'success')
            return redirect(url_for('academic_services.login'))
        else:
            for er in form.errors:
                flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('academic_services/forget_password.html', form=form)


@academic_services.route('/reset_password', methods=['GET', 'POST'])
@login_required
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
                    if user.is_first_login == False:
                        user.is_first_login = True
                        db.session.add(user)
                        db.session.commit()
                    if current_user.customer_info:
                        return redirect(url_for('academic_services.lab_index', menu='new'))
                    else:
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
@login_required
def detail_lab_index():
    cat = request.args.get('cat')
    code = request.args.get('code')
    labs = ServiceLab.query.filter_by(code=code)
    return render_template('academic_services/detail_lab_index.html', cat=cat, labs=labs, code=code)


@academic_services.route('/page/pdpa')
def pdpa_index():
    return render_template('academic_services/pdpa_page.html')


@academic_services.route('/accept-policy', methods=['GET', 'POST'])
def accept_policy():
    session['policy_accepted'] = True
    return redirect(url_for('academic_services.create_customer_account'))


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
            message = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>ยืนยันบัญชีระบบงานบริการตรวจวิเคราะห์ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        background-color: #f4f4f4;
                        margin: 0;
                        padding: 20px;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                    }}
                    .container {{
                        background-color: #ffffff;
                        border: 1px solid #e0e0e0;
                        border-radius: 5px;
                        max-width: 600px;
                        width: 100%;
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                        text-align: center;
                        padding: 40px;
                        box-sizing: border-box;
                    }}
                    .header {{
                        margin-bottom: 30px;
                    }}
                    .header h1 {{
                        font-size: 2.5em;
                        color: #444;
                        margin: 0;
                    }}
                    .header p {{
                        font-size: 1.2em;
                        color: #666;
                        margin-top: 5px;
                    }}
                    .content {{
                        margin-bottom: 30px;
                        color: #555;
                        line-height: 1.6;
                    }}
                    .content h3 {{
                        text-align: left;
                    }}
                    .content p {{
                        margin: 0 0 15px 0;
                        font-size: 1.1em;
                        text-align: left;
                    }}
                    .confirm-button {{
                        display: inline-block;
                        background-color: #008000; 
                        padding: 15px 30px;
                        text-decoration: none; 
                        border-radius: 5px;
                        font-size: 1.2em;
                        font-weight: bold;
                        margin-bottom: 20px;
                        transition: background-color 0.3s ease, transform 0.2s ease;
                        color: #ffffff !important;
                    }}
                    .link-validity {{
                        margin-top: 35px;
                        font-size: 0.9em;
                        color: #888;
                        text-align: left;
                    }}
                    .footer {{
                        margin-top: 40px;
                        font-size: 0.8em;
                        color: #aaa;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>ระบบงานบริการตรวจวิเคราะห์</h1>
                        <p>ยืนยันบัญชี</p>
                    </div>
                    <hr style="border: 0; border-top: 1px solid #e0e0e0; margin: 20px 0;">
                    <div class="content">
                        <h3>เรียน ผู้ใช้บริการ</h3>
                        <p>
                            ขอบคุณสำหรับการลงทะเบียนใช้งานระบบงานบริการตรวจวิเคราะห์<br>
                            กรุณาคลิกที่ปุ่มด้านล่างเพื่อยืนยันบัญชีอีเมลของท่านเพื่อดำเนินการต่อ
                        </p>
                        <a href="{url}" class="confirm-button">ยืนยันบัญชีอีเมล</a>
                        <p class="link-validity" >ลิงก์นี้จะสามารถใช้งานได้ภายใน 20 นาทีหลังจากที่อีเมลนี้ถูกส่งไป</p>
                    </div>
                    <div class="footer">
                        <p>Copyright &copy; คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล ระบบงานบริการตรวจวิเคราะห์</p>
                    </div>
                </div>
            </body>
            </html>
            """
            send_mail_for_account([form.email.data],
                                  title='ยืนยันบัญชีระบบงานบริการตรวจวิเคราะห์ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล',
                                  message=message)
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
    return render_template('academic_services/verify_email_page.html')


@academic_services.route('/page/confirm')
def confirm_email_page():
    return render_template('academic_services/confirm_email_page.html')


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
        return redirect(url_for('academic_services.customer_index'))
    elif user.verify_datetime:
        flash('ได้รับการยืนยันอีเมลแล้ว', 'info')
        return redirect(url_for('academic_services.customer_index'))
    else:
        user.verify_datetime = arrow.now('Asia/Bangkok').datetime
        db.session.add(user)
        db.session.commit()
        flash('ยืนยันอีเมลเรียบร้อยแล้ว', 'success')
        return redirect(url_for('academic_services.confirm_email_page'))


@academic_services.route('/customer/account', methods=['GET', 'POST'])
@login_required
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
@login_required
def customer_account():
    menu = request.args.get('menu')
    account = ServiceCustomerAccount.query.get(current_user.id)
    if current_user.customer_info:
        customer = ServiceCustomerInfo.query.get(current_user.customer_info_id)
        form = ServiceCustomerInfoForm(obj=customer)
    else:
        form = ServiceCustomerInfoForm()
    if form.validate_on_submit():
        if not current_user.customer_info:
            customer = ServiceCustomerInfo()
        form.populate_obj(customer)
        if not current_user.customer_info:
            account.customer_info = customer
            db.session.add(account)
        db.session.add(customer)
        db.session.commit()
        flash('บันทึกข้อมูลสำเร็จ', 'customer_updated')
        return redirect(url_for('academic_services.lab_index', menu='new'))
    if not current_user.customer_info:
        flash('กรุณากรอกข้อมูลลูกค้าและข้อมูลผู้ประสานงานให้ครบถ้วนก่อนดำเนินการต่อ', 'warning')
    return render_template('academic_services/customer_account.html', menu=menu, form=form)


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
        if customer.type and customer.type.type == 'บุคคล' and customer_id is None:
            contact = ServiceCustomerContact(contact_name=customer.cus_name, phone_number=customer.phone_number,
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
@login_required
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
    sub_lab = ServiceSubLab.query.filter_by(code=code)
    return render_template('academic_services/request_form.html', code=code, sub_lab=sub_lab)


@academic_services.route('/submit-request/add', methods=['POST', 'GET'])
@academic_services.route('/submit-request/edit/<int:request_id>', methods=['GET', 'POST'])
def submit_request(request_id=None):
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
    return redirect(url_for('academic_services.create_report_language', request_id=req.id, menu='request',
                            sub_lab=sub_lab.sub_lab))


@academic_services.route('/customer/report_language/add/<int:request_id>', methods=['GET', 'POST'])
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
        return redirect(url_for('academic_services.create_customer_detail', request_id=request_id, menu=menu,
                                sub_lab=sub_lab))
    return render_template('academic_services/create_report_language.html', menu=menu, sub_lab=sub_lab,
                           request_id=request_id, report_languages=report_languages,
                           req_report_language=req_report_language,
                           req_report_language_id=req_report_language_id)


@academic_services.route('/customer/detail/add/<int:request_id>', methods=['GET', 'POST'])
@login_required
def create_customer_detail(request_id):
    form = None
    menu = request.args.get('menu')
    sub_lab = request.args.get('sub_lab')
    service_request = ServiceRequest.query.get(request_id)
    selected_address_id = service_request.quotation_address_id if service_request.quotation_address_id else None
    customer = ServiceCustomerInfo.query.get(current_user.customer_info_id)
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
                                address.customer_id = current_user.customer_info_id
                        else:
                            address = ServiceCustomerAddress(name=quotation_address.name, address_type='document',
                                                             taxpayer_identification_no=quotation_address.taxpayer_identification_no,
                                                             address=quotation_address.address,
                                                             zipcode=quotation_address.zipcode,
                                                             phone_number=quotation_address.phone_number,
                                                             remark=remark,
                                                             customer_id=current_user.customer_info_id,
                                                             province_id=quotation_address.province_id,
                                                             district_id=quotation_address.district_id,
                                                             subdistrict_id=quotation_address.subdistrict_id)
                else:
                    address = ServiceCustomerAddress(name=quotation_address.name, address_type='document',
                                                  taxpayer_identification_no=quotation_address.taxpayer_identification_no,
                                                  address=quotation_address.address, zipcode=quotation_address.zipcode,
                                                  phone_number=quotation_address.phone_number, reamerk=remark,
                                                  customer_id=current_user.customer_info_id,
                                                  province_id=quotation_address.province_id,
                                                  district_id=quotation_address.district_id,
                                                  subdistrict_id=quotation_address.subdistrict_id)
                db.session.add(address)
                db.session.commit()
        status_id = get_status(1)
        service_request.status_id = status_id
        db.session.add(service_request)
        db.session.commit()
        return redirect(url_for('academic_services.view_request', request_id=request_id, menu=menu))
    return render_template('academic_services/create_customer_detail.html', menu=menu,
                           customer=customer, request_id=request_id, sub_lab=sub_lab, form=form,
                           selected_address_id=selected_address_id)


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
    sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab)
    datas = request_data(service_request)
    return render_template('academic_services/view_request.html', service_request=service_request, menu=menu,
                           datas=datas, sub_lab=sub_lab)


def generate_request_pdf(service_request):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 40, 40)
    if service_request.samples:
        sample_id = int(''.join(str(s.id) for s in service_request.samples))
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

    center_style = ParagraphStyle(
        'CenterStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=12,
        leading=25,
        alignment=TA_CENTER
    )

    customer = '''<para>ข้อมูลผู้ประสานงาน<br/>
                            ผู้ประสานงาน : {cus_contact}<br/>
                            เลขประจำตัวผู้เสียภาษี : {taxpayer_identification_no}<br/>
                            เบอร์โทรศัพท์ : {phone_number}<br/>
                            อีเมล : {email}
                        </para>
                        '''.format(cus_contact=', '.join(contact.contact_name for contact in service_request.customer.customer_info.customer_contacts),
                                   taxpayer_identification_no=service_request.customer.customer_info.taxpayer_identification_no,
                                   phone_number=service_request.customer.customer_info.phone_number,
                                   email=service_request.customer.email)

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
                                ออกในนาม : {name}<br/>
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
                                       phone_number=service_request.customer.customer_info.phone_number,
                                       email=service_request.customer.email)

    document_address_table = Table([[Paragraph(document_address, style=detail_style)]], colWidths=[265])

    district_title = 'เขต' if service_request.quotation_address.province.name == 'กรุงเทพมหานคร' else 'อำเภอ'
    subdistrict_title = 'แขวง' if service_request.quotation_address.province.name == 'กรุงเทพมหานคร' else 'ตำบล',
    quotation_address = '''<para>ข้อมูลที่อยู่จัดส่งเอกสาร<br/>
                                    ออกในนาม : {name}<br/>
                                    ที่อยู่ : {address} {subdistrict_title}{subdistrict} {district_title}{district} จังหวัด{province} {zipcode}<br/>
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
                                           phone_number=service_request.customer.customer_info.phone_number,
                                           email=service_request.customer.email)

    quotation_address_table = Table([[Paragraph(quotation_address, style=detail_style)]], colWidths=[265])

    address_table = Table(
        [[document_address_table, quotation_address_table]],
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
    data.append(KeepTogether(customer_table))
    data.append(KeepTogether(address_table))


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

        if total_height > first_page_limit and remaining_text:
                data.append(PageBreak())
                data.append(KeepTogether(Spacer(20, 20)))
                data.append(KeepTogether(content_header))
                data.append(KeepTogether(Spacer(7, 7)))
        data.append(KeepTogether(germ_table))

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
        total_height = total_height + current_length
        if not remaining_text and total_height > first_page_limit:
            data.append(PageBreak())
            data.append(KeepTogether(Spacer(20, 20)))
            data.append(KeepTogether(content_header))
            data.append(KeepTogether(Spacer(7, 7)))
        data.append(KeepTogether(lab_test_table))

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

        qr_code_label = Paragraph("QR Code สำหรับการตรวจสอบตัวอย่าง", style=center_style)
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
    addresses = ServiceCustomerAddress.query.filter_by(address_type='quotation',
                                                       customer_id=current_user.customer_info.id)
    if search:
        addresses = [address for address in addresses if search.lower() in address.address.lower()]
    for address in addresses:
        results.append({
            "id": address.id,
            "text": f'{address.name}: {address.taxpayer_identification_no}: {address.address}: {address.phone_number}'
        })
    return jsonify({'results': results})


@academic_services.route('/customer/quotation/address/add/<int:request_id>', methods=['GET', 'POST'])
def request_quotation(request_id):
    menu = request.args.get('menu')
    status_id = get_status(2)
    service_request = ServiceRequest.query.get(request_id)
    service_request.status_id = status_id
    db.session.add(service_request)
    db.session.commit()
    scheme = 'http' if current_app.debug else 'https'
    admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=service_request.lab)).all()
    title_prefix = 'คุณ' if current_user.customer_info.type.type == 'บุคคล' else ''
    link = url_for("service_admin.generate_quotation", request_id=request_id, menu='quotation',
                   _external=True, _scheme=scheme)
    customer_name = service_request.customer.customer_name.replace(' ', '_')
    sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab).first()
    title = f'''[{service_request.request_no}] ใบคำขอรับบริการ - {title_prefix}{customer_name} ({service_request.quotation_address.name}) | แจ้งขอใบเสนอราคา'''
    message = f'''เรียน เจ้าหน้าที่{sub_lab.sub_lab}่\n\n'''
    message += f'''ใบคำขอบริการเลขที่ : {service_request.request_no}\n'''
    message += f'''ลูกค้า : {customer_name}\n'''
    message += f'''ในนาม : {service_request.customer.customer_name}\n'''
    message += f'''ที่รอการดำเนินการจัดทำใบเสนอราคา\n'''
    message += f'''กรุณาตรวจสอบและดำเนินการได้ที่ลิงก์ด้านล่าง\n'''
    message += f'''{link}\n\n'''
    message += f'''ขอบคุณค่ะ\n'''
    message += f'''ระบบงานบริการวิชาการ\n\n'''
    message += f'''{service_request.customer.customer_name}\n'''
    message += f'''ผู้ประสานงาน\n'''
    message += f'''เบอร์โทร {service_request.customer.customer_info.phone_number}'''
    send_mail([a.admin.email + '@mahidol.ac.th' for a in admins if not a.is_supervisor], title, message)
    request_link = url_for("academic_services.view_request", request_id=request_id, menu='request',
                           _external=True, _scheme=scheme)
    title_for_customer = f'''แจ้งรับใบคำขอรับบริการ [{service_request.request_no}] – คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
    message_for_customer = f'''เรียน {title_prefix}{current_user.customer_info.cus_name}\n\n'''
    message_for_customer += f'''ตามที่ท่านได้แจ้งความประสงค์ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล ขณะนี้ทางเจ้าหน้าที่ได้รับข้อมูลคำขอรับบริการเป็นที่เรียบร้อยแล้ว\n'''
    message_for_customer += f'''ทางเจ้าหน้าที่จะพิจารณารายละเอียดและจัดทำใบเสนอราคาอย่างเป็นทางการต่อไป เมื่อใบเสนอราคาออกเรียบร้อยแล้ว ท่านจะได้รับอีเมลแจ้งอีกครั้งหนึ่ง พร้อมลิงก์สำหรับตรวจสอบและยืนยันใบเสนอราคา\n'''
    message_for_customer += f'''ท่านสามารถดูรายละเอียดใบคำขอรับบริการได้ที่ลิงก์ด้างล่างนี้\n'''
    message_for_customer += f'''{request_link}\n'''
    message_for_customer += f'''ขอขอบพระคุณที่ใช้บริการจากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล\n\n'''
    message_for_customer += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
    message_for_customer += f'''ขอแสดงความนับถือ\n'''
    message_for_customer += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
    message_for_customer += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
    send_mail([current_user.email], title_for_customer, message_for_customer)
    msg = ('แจ้งขอใบเสนอราคา' \
           '\n\nเรียน เจ้าหน้าที{}'
           '\n\nใบคำขอบริการเลขที่ {}' \
           '\nลูกค้า : {}'\
           '\nในนาม : {}'\
           '\nที่รอการดำเนินการออกใบเสนอราคา'\
           '\nกรุณาตรวจสอบและดำเนินการได้ที่ลิงก์ด้านล่าง' \
           '\n{}' \
           '\n\nขอบคุณค่ะ' \
           '\nระบบงานบริการวิชาการ'\
           '\n\n{}'\
           '\nผู้ประสานงาน'\
           '\nเบอร์โทร {}'.format(sub_lab.sub_lab, service_request.request_no, service_request.customer.customer_info.cus_name,
                                   service_request.quotation_address.name, link, service_request.customer.customer_info.cus_name,
                                   service_request.customer.customer_info.phone_number)
           )
    if not current_app.debug:
        for a in admins:
            if not a.is_supervisor:
                try:
                    line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                except LineBotApiError:
                    pass
    flash('ส่งใบคำขอรับบริการสำเร็จ', 'send_request')
    return redirect(url_for('academic_services.request_index', menu=menu))


@academic_services.route('/customer/quotation/index')
@login_required
def quotation_index():
    menu = request.args.get('menu')
    return render_template('academic_services/quotation_index.html', menu=menu)


@academic_services.route('/api/quotation/index')
def get_quotations():
    query = ServiceQuotation.query.filter(ServiceQuotation.request.has(customer_id=current_user.id),
                                          or_(ServiceQuotation.approved_at!=None))
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
    sub_lab = ServiceSubLab.query.filter_by(code=quotation.request.lab).all()
    return render_template('academic_services/view_quotation.html', quotation_id=quotation_id, menu=menu,
                           quotation=quotation, sub_lab=sub_lab)


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
    customer = '''<para><font size=11>
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
        item_record = [Paragraph('<font size=12>{}</font>'.format(n), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{}</font>'.format(item.item), style=style_sheet['ThaiStyle']),
                       Paragraph('<font size=12>{}</font>'.format(item.quantity), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.unit_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.total_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       ]
        items.append(item_record)

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
    data.append(KeepTogether(sign_table))

    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    buffer.seek(0)
    return buffer


@academic_services.route('/quotation/pdf/<int:quotation_id>', methods=['GET'])
def export_quotation_pdf(quotation_id):
    quotation = ServiceQuotation.query.get(quotation_id)
    buffer = generate_quotation_pdf(quotation)
    return send_file(buffer, download_name='Quotation.pdf', as_attachment=True)


@academic_services.route('/customer/quotation/confirm/<int:quotation_id>', methods=['GET', 'POST'])
def confirm_quotation(quotation_id):
    menu = request.args.get('menu')
    status_id = get_status(6)
    scheme = 'http' if current_app.debug else 'https'
    quotation = ServiceQuotation.query.get(quotation_id)
    quotation.confirmed_at = arrow.now('Asia/Bangkok').datetime
    quotation.confirmer_id = current_user.id
    quotation.request.status_id = status_id
    db.session.add(quotation)
    sample = ServiceSample(request_id=quotation.request_id)
    db.session.add(sample)
    db.session.commit()
    flash('ยืนยันใบเสนอราคาสำเร็จ กรุณาดำเนินการนัดหมายส่งตัวอย่าง', 'success')
    sub_lab = ServiceSubLab.query.filter_by(code=quotation.request.lab).first()
    admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=quotation.request.lab)).all()
    link = url_for('service_admin.view_quotation', menu='quotation', tab='all', quotation_id=quotation_id,
                   _external=True, _scheme=scheme)
    title_prefix = 'คุณ' if quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
    customer_name = quotation.customer_name.replace(' ', '_')
    title = f'''[{quotation.quotation_no}] ใบเสนอราคา - {title_prefix}{customer_name} ({quotation.name}) | แจ้งยืนยันใบเสนอราคา'''
    message = f'''เรียน เจ้าหน้าที่{sub_lab.sub_lab}่\n\n'''
    message += f'''ใบเสนอราคาเลขที่ {quotation.quotation_no}\n'''
    message += f'''ลูกค้า : {quotation.customer_name}\n'''
    message += f'''ในนาม : {quotation.name}\n'''
    message += f'''ได้รับการยืนยันจากลูกค้าแล้ว\n'''
    message += f'''ท่านสามารถดูรายละเอียดได้ที่ลิงก์ด้านล่าง\n'''
    message += f'''{link}\n\n'''
    message += f'''ขอบคุณค่ะ\n'''
    message += f'''ระบบบริการวิชาการ\n\n'''
    message += f'''{quotation.customer_name}\n'''
    message += f'''ผู้ประสานงาน\n'''
    message += f'''เบอร์โทร {quotation.request.customer.customer_info.phone_number}'''
    send_mail([a.admin.email + '@mahidol.ac.th' for a in admins], title, message)
    return redirect(url_for('academic_services.confirm_quotation_page', menu=menu, sample_id=sample.id))


@academic_services.route('/customer/quotation/confirm/page/<int:sample_id>', methods=['GET', 'POST'])
def confirm_quotation_page(sample_id):
    menu = request.args.get('menu')
    return render_template('academic_services/confirm_quotation_page.html', sample_id=sample_id, menu=menu)


@academic_services.route('/customer/quotation/reject/<int:quotation_id>', methods=['GET', 'POST'])
def reject_quotation(quotation_id):
    menu = request.args.get('menu')
    quotation = ServiceQuotation.query.get(quotation_id)
    form = ServiceQuotationForm(obj=quotation)
    if form.validate_on_submit():
        form.populate_obj(quotation)
        status_id = get_status(7)
        quotation.canceller_id = current_user.id
        quotation.cancelled_at = arrow.now('Asia/Bangkok').datetime
        quotation.request.status = status_id
        db.session.add(quotation)
        db.session.commit()
        flash('ยกเลิกใบเสนอราคาสำเร็จ', 'success')
        sub_lab = ServiceSubLab.query.filter_by(code=quotation.request.lab).first()
        admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=quotation.request.lab)).all()
        title_prefix = 'คุณ' if quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
        customer_name = quotation.customer_name.replace(' ', '_')
        title = f'''[{quotation.quotation_no}] ใบเสนอราคา - {title_prefix}{customer_name} ({quotation.name}) | แจ้งปฏิเสธใบเสนอราคา'''
        message = f'''เรียน เจ้าหน้าที่{sub_lab.sub_lab}่\n\n'''
        message += f'''ใบเสนอราคาเลขที่ {quotation.quotation_no}\n'''
        message += f'''ลูกค้า : {quotation.customer_name}\n'''
        message += f'''ในนาม : {quotation.name}\n'''
        message += f'''เหตุผลที่ยกเลิก : {quotation.note or ''}'''
        message += f'''ได้รับการปฏิเสธจากลูกค้า\n'''
        message += f'''กรุณาตรวจสอบและดำเนินขั้นตอนที่เหมาะสมต่อไป\n\n'''
        message += f'''ขอบคุณค่ะ\n'''
        message += f'''ระบบบริการวิชาการ\n\n'''
        message += f'''{quotation.customer_name}\n'''
        message += f'''ผู้ประสานงาน\n'''
        message += f'''เบอร์โทร {quotation.request.customer.customer_info.phone_number}'''
        send_mail([a.admin.email + '@mahidol.ac.th' for a in admins], title, message)
        resp = make_response()
        resp.headers['HX-Redirect'] = url_for('academic_services.quotation_index', menu=menu)
        return resp
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('academic_services/modal/reject_quotation_modal.html', form=form,
                           quotation_id=quotation_id, menu=menu)


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
@login_required
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
@login_required
def address_index():
    menu = request.args.get('menu')
    addresses = ServiceCustomerAddress.query.filter_by(customer_id=current_user.customer_info.id).all()
    return render_template('academic_services/address_index.html', addresses=addresses, menu=menu)


@academic_services.route('/customer/address/add', methods=['GET', 'POST'])
@academic_services.route('/customer/address/edit/<int:address_id>', methods=['GET', 'POST'])
@login_required
def create_address(address_id=None):
    menu = request.args.get('menu')
    type = request.args.get('type')
    if address_id:
        address = ServiceCustomerAddress.query.get(address_id)
        form = ServiceCustomerAddressForm(obj=address)
    else:
        form = ServiceCustomerAddressForm()
        address = ServiceCustomerAddress.query.all()
    if not form.taxpayer_identification_no.data:
        form.taxpayer_identification_no.data = current_user.customer_info.taxpayer_identification_no
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


@academic_services.route('/api/get_districts')
def get_districts():
    province_id = request.args.get('province_id')
    districts = District.query.filter_by(province_id=province_id).all()
    result = [{"id": d.id, "name": d.name} for d in districts]
    return jsonify(result)


@academic_services.route('/api/get_subdistricts')
def get_subdistricts():
    district_id = request.args.get('district_id')
    subdistricts = Subdistrict.query.filter_by(district_id=district_id).all()
    result = [{"id": s.id, "name": s.name} for s in subdistricts]
    return jsonify(result)


@academic_services.route('/api/get_zipcode')
def get_zipcode():
    subdistrict_id = request.args.get('subdistrict_id')
    subdistrict = Subdistrict.query.filter_by(id=subdistrict_id).first()
    zipcode = subdistrict.zip_code.zip_code if subdistrict else ''
    return jsonify({"zipcode": zipcode})


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
        address.address_type = 'document'
        address.taxpayer_identification_no = address.taxpayer_identification_no if address.taxpayer_identification_no else None
        address.address = address.address
        address.phone_number = address.phone_number
        address.province_id = address.province_id
        address.district_id = address.district_id
        address.subdistrict_id = address.subdistrict_id
        address.zipcode = address.zipcode
        address.remark = address.remark if address.remark else None
        address.customer_id = current_user.customer_info.id
        address.id = None
        db.session.add(address)
        db.session.commit()
        flash('ยืนยันสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@academic_services.route('/customer/sample/index')
@login_required
def sample_index():
    menu = request.args.get('menu')
    samples = ServiceSample.query.filter(ServiceSample.request.has(customer_id=current_user.id))
    request_id = None
    if samples:
        for sample in samples:
            request_id = sample.request_id
    else:
        request_id = None
    return render_template('academic_services/sample_index.html', samples=samples, menu=menu,
                           request_id=request_id)


@academic_services.route('/customer/sample/add/<int:sample_id>', methods=['GET', 'POST'])
@login_required
def create_sample_appointment(sample_id):
    menu = request.args.get('menu')
    sample = ServiceSample.query.get(sample_id)
    service_request = ServiceRequest.query.get(sample.request_id)
    datas = request_data(service_request)
    sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab).all()
    form = ServiceSampleForm(obj=sample)
    admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=sample.request.lab)).all()
    appointment_date = form.appointment_date.data.astimezone(localtz) if form.appointment_date.data else None
    holidays = Holidays.query.all()
    if form.validate_on_submit():
        form.populate_obj(sample)
        if form.ship_type.data == 'ส่งด้วยตนเอง':
            sample.appointment_date = arrow.get(form.appointment_date.data, 'Asia/Bangkok').datetime
        else:
            sample.appointment_date = None
        db.session.add(sample)
        db.session.commit()
        scheme = 'http' if current_app.debug else 'https'
        sub_lab = ServiceSubLab.query.filter_by(code=service_request.lab).first()
        title_prefix = 'คุณ' if service_request.customer.customer_info.type.type == 'บุคคล' else ''
        link = url_for("service_admin.sample_verification", sample_id=sample.id, menu=menu, _external=True,
                       _scheme=scheme)
        customer_name = service_request.customer.customer_info.cus_name.replace(' ', '_')
        if service_request.status == 'กำลังดำเนินการส่งตัวอย่าง':
            title = f'''[{service_request.request_no}] นัดหมายส่งตัวอย่าง - {title_prefix}{customer_name} ({service_request.quotation_address.name}) | (แจ้งแก้ไขนัดหมายส่งตัวอย่าง)'''
            message = f'''เรียน เจ้าหน้าที่{sub_lab.sub_lab}\n\n'''
            message += f'''ใบคำขอรับบริการเลขที่ {service_request.request_no}'''
            message += f'''ลูกค้า : {service_request.customer.customer_info.cus_name}\n'''
            message += f'''ในนาม : {service_request.quotation_address.name}\n'''
            message += f'''ได้ดำเนินการแก้ไขข้อมูลการนัดหมายส่งตัวอย่าง โดยมีรายละเอียดดังนี้\n'''
            message += f'''ใบเสนอราคา : {' , '.join(quotation.quotation_no for quotation in service_request.quotations)}\n'''
            if sample.appointment_date:
                message += f'''วันที่นัดหมาย : {sample.appointment_date.astimezone(localtz).strftime('%d/%m/%Y')}\n'''
                message += f'''เวลานัดหมาย : {sample.appointment_date.astimezone(localtz).strftime('%H:%M')}\n'''
            message += f'''สถานที่นัดหมาย : {sample.location}\n'''
            message += f'''รายละเอียดสถานที่ : {' , '.join(s_lab.short_address for s_lab in sub_lab)}\n'''
            message += f'''รูปแบบการจัดส่งตัวอย่าง : {sample.ship_type}\n\n'''
            message += f'''กรุณาตรวจสอบและดำเนินการได้ที่ลิงค์ด้านล่าง\n'''
            message += f'''{link}\n\n'''
            message += f'''ขอบคุณค่ะ\n'''
            message += f'''ระบบงานบริการวิชาการ\n\n'''
            message += f'''{service_request.customer.customer_info.cus_name}\n'''
            message += f'''ผู้ประสานงาน\n'''
            message += f'''เบอร์โทร {service_request.customer.customer_info.phone_number}'''
        else:
            title = f'''[{service_request.request_no}] นัดหมายส่งตัวอย่าง - {title_prefix}{customer_name} ({service_request.quotation_address.name}) | (แจ้งนัดหมายส่งตัวอย่าง)'''
            message = f'''เรียน เจ้าหน้าที่{sub_lab.sub_lab}\n\n'''
            message += f'''ใบคำขอรับบริการเลขที่ {service_request.request_no}'''
            message += f'''ลูกค้า : {service_request.customer.customer_info.cus_name}\n'''
            message += f'''ในนาม : {service_request.quotation_address.name}\n'''
            message += f'''ได้ดำเนินการนัดหมายส่งตัวอย่าง โดยมีรายละเอียดดังนี้\n'''
            message += f'''ใบเสนอราคา : {' , '.join(quotation.quotation_no for quotation in service_request.quotations)}\n'''
            if sample.appointment_date:
                message += f'''วันที่นัดหมาย : {sample.appointment_date.astimezone(localtz).strftime('%d/%m/%Y')}\n'''
                message += f'''เวลานัดหมาย : {sample.appointment_date.astimezone(localtz).strftime('%H:%M')}\n'''
            message += f'''สถานที่นัดหมาย : {sample.location}\n'''
            message += f'''รูปแบบการจัดส่งตัวอย่าง : {sample.ship_type}\n'''
            message += f'''รายละเอียดสถานที่ : {' , '.join(s_lab.short_address for s_lab in sub_lab)}\n'''
            message += f'''กรุณาตรวจสอบและดำเนินการได้ที่ลิงค์ด้านล่าง\n'''
            message += f'''{link}\n\n'''
            message += f'''ขอบคุณค่ะ\n'''
            message += f'''ระบบงานบริการวิชาการ\n\n'''
            message += f'''{service_request.customer.customer_info.cus_name}\n'''
            message += f'''ผู้ประสานงาน\n'''
            message += f'''เบอร์โทร {service_request.customer.customer_info.phone_number}'''
        send_mail([a.admin.email + '@mahidol.ac.th' for a in admins], title, message)
        if service_request.status == 'ยืนยันใบเสนอราคาเรียบร้อยแล้ว':
            service_request.status == 'กำลังดำเนินการส่งตัวอย่าง'
            db.session.add(service_request)
            db.session.commit()
        flash('อัพเดตข้อมูลสำเร็จ', 'success')
        return redirect(url_for('academic_services.confirm_sample_appointment_page', menu=menu,
                                request_id=sample.request_id))
    return render_template('academic_services/create_sample_appointment.html', form=form,
                           sample=sample, menu=menu, sample_id=sample_id, sub_lab=sub_lab, datas=datas,
                           appointment_date=appointment_date, service_request=service_request, holidays=holidays)


@academic_services.route('/customer/sample-appointment/confirm/page/<int:request_id>', methods=['GET', 'POST'])
def confirm_sample_appointment_page(request_id):
    menu = request.args.get('menu')
    return render_template('academic_services/confirm_sample_appointment_page.html', request_id=request_id,
                           menu=menu)


@academic_services.route('/customer/sample/tracking_number/add/<int:sample_id>', methods=['GET', 'POST'])
def add_tracking_number(sample_id):
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
    return render_template('academic_services/modal/add_tracking_number_modal.html', form=form, menu=menu,
                           sample_id=sample_id)


@academic_services.route('/customer/sample/appointment/view/<int:sample_id>')
@login_required
def view_sample_appointment(sample_id):
    menu = request.args.get('menu')
    sample = ServiceSample.query.get(sample_id)
    return render_template('academic_services/view_sample_appointment.html', sample=sample, menu=menu)


@academic_services.route('/customer/sample/test/view/<int:sample_id>')
@login_required
def view_test_sample(sample_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    sample = ServiceSample.query.get(sample_id)
    return render_template('academic_services/view_test_sample.html', sample=sample, tab=tab, menu=menu)


@academic_services.route('/customer/test-item/index')
@login_required
def test_item_index():
    menu = request.args.get('menu')
    return render_template('academic_services/test_item_index.html', menu=menu)


@academic_services.route('/api/test-item/index')
def get_test_items():
    query = ServiceTestItem.query.filter(ServiceTestItem.request.has(ServiceRequest.customer_id == current_user.id))
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
        item_data = item.to_dict()
        data.append(item_data)
    return jsonify({'data': data,
                    'recordFiltered': total_filtered,
                    'recordTotal': records_total,
                    'draw': request.args.get('draw', type=int)
                    })


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
@login_required
def result_index():
    menu = request.args.get('menu')
    results = ServiceResult.query.filter(ServiceResult.request.has(customer_id=current_user.id))
    return render_template('academic_services/result_index.html', results=results, menu=menu)


@academic_services.route('/customer/invoice/index')
@login_required
def invoice_index():
    menu = request.args.get('menu')
    return render_template('academic_services/invoice_index.html', menu=menu)


@academic_services.route('/api/invoice/index')
def get_invoices():
    query = ServiceInvoice.query.filter(ServiceInvoice.status == 'ออกใบแจ้งหนี้เรียบร้อยแล้ว',
                                        ServiceInvoice.quotation.has(
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
    invoice = ServiceInvoice.query.get(invoice_id)
    sub_lab = ServiceSubLab.query.filter_by(code=invoice.quotation.request.lab).first()
    return render_template('academic_services/view_invoice.html', invoice_id=invoice_id, menu=menu,
                           sub_lab=sub_lab, invoice=invoice)


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

    issued_date = arrow.get(invoice.approved_at.astimezone(localtz)).format(fmt='DD MMMM YYYY', locale='th-th')
    customer = '''<para><font size=11>
                        ที่ อว. {mhesi_no}<br/>
                        วันที่ {issued_date}<br/>
                        เรื่อง ใบแจ้งหนี้ค่าบริการตรวจวิเคราะห์ทางห้องปฏิบัติการ<br/>
                        เรียน {customer}<br/>
                        ที่อยู่ {address}<br/>
                        เลขประจำตัวผู้เสียภาษี {taxpayer_identification_no}
                        </font></para>
                        '''.format(mhesi_no=invoice.mhesi_no if invoice.mhesi_no else '',
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

    for n, item in enumerate(sorted(invoice.invoice_items, key=lambda x: x.sequence), start=1):
        item_record = [Paragraph('<font size=12>{}</font>'.format(n), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{}</font>'.format(item.item), style=style_sheet['ThaiStyle']),
                       Paragraph('<font size=12>{}</font>'.format(item.quantity), style=style_sheet['ThaiStyleCenter']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.unit_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       Paragraph('<font size=12>{:,.2f}</font>'.format(item.total_price),
                                 style=style_sheet['ThaiStyleNumber']),
                       ]
        items.append(item_record)

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
        Paragraph('<font size=12>{:,.2f}</font>'.format(invoice.subtotal()), style=style_sheet['ThaiStyleNumber']),
    ])

    items.append([
        Paragraph('<font size=12>{}</font>'.format(bahttext(invoice.grand_total())),
                  style=style_sheet['ThaiStyleCenter']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>ส่วนลด</font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(invoice.discount()), style=style_sheet['ThaiStyleNumber']),
    ])

    items.append([
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>รวมเป็นเงินทั้งสิ้น/Grand Total</font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(invoice.grand_total()), style=style_sheet['ThaiStyleNumber']),
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
    code = request.args.get('code')
    sub_lab = ServiceSubLab.query.filter_by(code=code)
    return render_template('academic_services/edit_request.html', request_id=request_id, sub_lab=sub_lab)


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
        result.status = 'รับทราบผลการทดสอบแล้ว'
        result.approver_id = current_user.id
        result.request.status = 'รับทราบผลการทดสอบแล้ว'
        db.session.add(result)
        db.session.commit()
        flash('รับทราบผลเรียบร้อยแล้ว', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@academic_services.route('/customer/payment/view/<int:payment_id>')
@login_required
def view_payment(payment_id):
    menu = request.args.get('menu')
    payment = ServicePayment.query.get(payment_id)
    return render_template('academic_services/view_payment.html', payment=payment, menu=menu)


@academic_services.route('/customer/receipt/index', methods=['GET'])
@login_required
def receipt_index():
    menu = request.args.get('menu')
    return render_template('academic_services/receipt_index.html', menu=menu)