import re
import uuid
import qrcode
from bahttext import bahttext
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from sqlalchemy import or_, update, and_, exists
from datetime import date, datetime
import arrow
import pandas
from io import BytesIO
import pytz
from pytz import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, TableStyle, Table, Spacer, KeepTogether, \
    PageBreak
from sqlalchemy.orm import make_transient
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
from app.auth.views import line_bot_api
from app.main import app, get_credential, json_keyfile
from app.academic_services import academic_services
from app.academic_services.forms import *
from app.academic_services.models import *
from flask import render_template, flash, redirect, url_for, request, current_app, abort, session, make_response, \
    jsonify, send_file
from flask_login import login_user, current_user, logout_user, login_required
from flask_principal import Identity, identity_changed, AnonymousIdentity
from flask_admin.helpers import is_safe_url
from itsdangerous.url_safe import URLSafeTimedSerializer as TimedJSONWebSignatureSerializer
from app.main import mail
from flask_mail import Message
from app.models import Holidays, Org
from app.service_admin.forms import ServiceResultForm

localtz = timezone('Asia/Bangkok')

sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
pdfmetrics.registerFont(sarabun_font)
pdfmetrics.registerFont(TTFont('SarabunItalic', 'app/static/fonts/THSarabunNewItalic.ttf'))
style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))
style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', alignment=TA_CENTER))
style_sheet.add(ParagraphStyle(name='ThaiStyleRight', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleItalic', fontName='SarabunItalic'))

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

bangkok = pytz.timezone('Asia/Bangkok')
S3_BUCKET_NAME = os.getenv('BUCKETEER_BUCKET_NAME')


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


def tab_of_invoice(tab, query):
    if tab == 'pending':
        query = query.join(ServicePayment).filter(
            ServicePayment.paid_at == None,
            today <= ServiceInvoice.due_date, ServicePayment.cancelled_at == None
        )
    elif tab == 'verify':
        query = query.join(ServicePayment).filter(ServicePayment.paid_at != None, ServicePayment.verified_at == None,
                                                  ServicePayment.cancelled_at == None)
    elif tab == 'payment':
        query = query.join(ServicePayment).filter(ServicePayment.verified_at != None,
                                                  ServicePayment.cancelled_at == None)
    elif tab == 'overdue':
        query = query.join(ServicePayment).filter(today > ServiceInvoice.due_date, ServicePayment.paid_at == None,
                                                  ServicePayment.cancelled_at == None)
    else:
        query = query
    return query
# def request_data(service_request):
#     sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
#     gc = get_credential(json_keyfile)
#     wks = gc.open_by_key(sheetid)
#     sheet = wks.worksheet(service_request.sub_lab.sheet)
#     df = pandas.DataFrame(sheet.get_all_records())
#     data = service_request.data
#     form = create_request_form(df)(**data)
#     values = []
#     table_rows = []
#     set_fields = set()
#     current_row = {}
#     for fn in df.fieldGroup:
#         for field in getattr(form, fn):
#             if field.type == 'FieldList':
#                 for fd in field:
#                     for f in fd:
#                         if f.data != None and f.data != '' and f.data != [] and f.label not in set_fields:
#                             set_fields.add(f.label)
#                             label = f.label.text
#                             value = ', '.join(f.data) if f.type == 'CheckboxField' else f.data
#                             if label.startswith("เชื้อ"):
#                                 value = Markup(f"<i>{value}</i>")
#                                 if current_row:
#                                     table_rows.append(current_row)
#                                     current_row = {}
#                                 current_row["เชื้อ"] = value
#                             elif "อัตราส่วน" in label:
#                                 current_row["อัตราส่วนเจือจาง"] = value
#                             elif "ระยะห่าง" in label:
#                                 current_row["ระยะห่างในการฉีดพ่น"] = value
#                             elif "ระยะเวลาในการฉีดพ่น" in label or "ระยะเวลาฉีดพ่น" in label:
#                                 current_row["ระยะเวลาฉีดพ่น"] = value
#                             elif "สัมผัสกับเชื้อ" in label:
#                                 current_row["ระยะเวลาสัมผัสเชื้อ"] = value
#                             else:
#                                 values.append(f"{label} : {value}")
#             else:
#                 if field.data != None and field.data != '' and field.data != [] and field.label not in set_fields:
#                     set_fields.add(field.label)
#                     label = field.label.text
#                     value = ', '.join(field.data) if field.type == 'CheckboxField' else field.data
#                     if label.startswith("เชื้อ"):
#                         value = Markup(f"<i>{value}</i>")
#                         if current_row:
#                             table_rows.append(current_row)
#                             current_row = {}
#                         current_row["เชื้อ"] = value
#                     elif "อัตราส่วน" in label:
#                         current_row["อัตราส่วนเจือจาง"] = value
#                     elif "ระยะห่าง" in label:
#                         current_row["ระยะห่างในการฉีดพ่น"] = value
#                     elif "ระยะเวลาในการฉีดพ่น" in label or "ระยะเวลาฉีดพ่น" in label:
#                         current_row["ระยะเวลาฉีดพ่น"] = value
#                     elif "สัมผัสกับเชื้อ" in label:
#                         current_row["ระยะเวลาสัมผัสเชื้อ"] = value
#                     else:
#                         values.append(f"{label} : {value}")
#     if current_row:
#         table_rows.append(current_row)
#     table_keys = []
#     for row in table_rows:
#         for key in row:
#             if key not in table_keys:
#                 table_keys.append(key)
#
#     return {
#         "value": values,
#         "table_rows": table_rows,
#         "table_keys": table_keys
#     }

def request_data(service_request, type):
    data = service_request.data
    if service_request.sub_lab.code == 'bacteria':
        form = BacteriaRequestForm(data=data)
    elif service_request.sub_lab.code == 'disinfection':
        form = VirusDisinfectionRequestForm(data=data)
    elif service_request.sub_lab.code == 'air_disinfection':
        form = VirusAirDisinfectionRequestForm(data=data)
    else:
        form = ''
    values = []
    set_fields = set()
    product_header = False
    test_header = False
    for field in form:
        if field.type == 'FormField':
            if not test_header:
                values.append({'type': 'header', 'data': 'รายการทดสอบ'})
                test_header = True
            if not any([f.data for f in field._fields.values() if f.type != 'HiddenField' and f.type != 'FieldList']):
                continue
            for fname, fn in field._fields.items():
                if fn.type == 'FieldList':
                    rows = []
                    for entry in fn.entries:
                        row = {}
                        for f_name, f in entry._fields.items():
                            if f.data and f.label not in set_fields:
                                set_fields.add(f.label)
                                label = f.label.text
                                if label.startswith("เชื้อ"):
                                    data = ', '.join(f.data) if isinstance(f.data, list) else str(f.data or '')
                                    if type == 'form':
                                        row[label] = f"<i>{data}</i>"
                                    else:
                                        row[label] = f"<font name='SarabunItalic'>{data}</font>"
                                else:
                                    row[label] = f.data
                        if row:
                            rows.append(row)
                    if rows:
                        values.append({'type': 'table', 'data': rows})
                else:
                    if fn.data and fn.label not in set_fields:
                        set_fields.add(fn.label)
                        label = fn.label.text
                        value = ', '.join(fn.data) if fn.type == 'CheckboxField' else fn.data
                        if fn.type == 'HiddenField':
                            values.append({'type': 'content_header', 'data': f"{value}"})
                        else:
                            values.append({'type': 'text', 'data': f"{label} : {value}"})
        else:
            if not product_header:
                values.append({'type': 'header', 'data': 'ข้อมูลผลิตภัณฑ์'})
                product_header = True
            if field.data and field.label not in set_fields:
                set_fields.add(field.label)
                label = field.label.text
                value = ', '.join(f.data) if field.type == 'CheckboxField' else field.data
                values.append({'type': 'text', 'data': f"{label} : {value}"})
    return values


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
    result_item = ServiceResultItem.query.filter_by(final_file=key).first()
    if result_item:
        req = result_item.result.request
        if req.is_downloaded == None:
            req.is_downloaded = True
            db.session.add(req)
            db.session.commit()
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


@academic_services.context_processor
def menu():
    request_count = None
    quotation_count = None
    sample_count = None
    invoice_count = None
    report_count = None

    if current_user.is_authenticated:
        request_count = ServiceRequest.query.filter(ServiceRequest.customer_id == current_user.id,
                                                    ServiceRequest.is_downloaded == None, ServiceRequest.status.has(
                ServiceStatus.status_id.in_([1, 2]))).count()
        quotation_count = ServiceRequest.query.filter(ServiceRequest.customer_id == current_user.id,
                                                      ServiceRequest.status.has(
                                                          ServiceStatus.status_id.in_([5]))).count()
        sample_count = ServiceRequest.query.filter(ServiceRequest.customer_id == current_user.id,
                                                   ServiceRequest.status.has(
                                                       ServiceStatus.status_id.in_([6, 8, 9]))).count()
        invoice_count = ServiceRequest.query.filter(ServiceRequest.customer_id == current_user.id,
                                                    ServiceRequest.status.has(
                                                        ServiceStatus.status_id.in_([20, 21]))).count()
        report_count = ServiceResult.query.join(ServiceResult.request).filter(
            ServiceRequest.customer_id == current_user.id,
            ServiceResult.approved_at == None).count()
    return dict(request_count=request_count, quotation_count=quotation_count, sample_count=sample_count,
                invoice_count=invoice_count, report_count=report_count)


# @academic_services.route('index')
# def index():
#     today = arrow.now().date()
#     thirty_days = arrow.now().shift(days=+30).date()
#     request_count = ServiceRequest.query.filter(ServiceRequest.customer_id==current_user.id,
#                                                 ServiceRequest.status.has(ServiceStatus.status_id == 1)
#                                                 ).count()
#     quotation_count = ServiceQuotation.query.filter(ServiceQuotation.request.has(customer_id=current_user.id),
#                                                     ServiceQuotation.approved_at != None,
#                                                     ServiceQuotation.confirmed_at == None).count()
#     sample_count = ServiceSample.query.filter(ServiceSample.request.has(customer_id=current_user.id),
#                                               ServiceSample.received_at == None).count()
#     test_item_count = ServiceRequest.query.filter(ServiceRequest.customer_id==current_user.id,
#                                                 ServiceRequest.status.has(or_(ServiceStatus.status_id == 10,
#                                                                               ServiceStatus.status_id == 11))
#                                                 ).count()
#     report_count = ServiceResultItem.query.filter(ServiceResultItem.result.has(
#                     ServiceResult.request.has(customer_id=current_user.id)),
#                     ServiceResultItem.approved_at == None).count()
#     invoice_count = ServiceInvoice.query.filter(ServiceInvoice.file_attached_at != None, ServiceInvoice.paid_at == None,
#                                                 ServiceInvoice.quotation.has(
#                                                     ServiceQuotation.request.has(customer_id=current_user.id))).count()
#     service_requests = (ServiceRequest.query.filter(ServiceRequest.customer_id==current_user.id)
#                          .order_by(ServiceRequest.created_at.desc()).limit(5))
#     samples = ServiceSample.query.filter(ServiceSample.request.has(customer_id=current_user.id),
#                                               ServiceSample.received_at == None ,
#                                         or_(ServiceSample.appointment_date) <= thirty_days,
#                                         ServiceSample.ship_type == 'ส่งทางไปรษณีย์')
#     invoices = ServiceInvoice.query.filter(ServiceInvoice.file_attached_at != None, ServiceInvoice.paid_at == None,
#                                                 ServiceInvoice.due_date < today, ServiceInvoice.quotation.has(
#                                                     ServiceQuotation.request.has(customer_id=current_user.id)))
#     return render_template('academic_services/index.html', request_count=request_count, quotation_count=quotation_count,
#                            sample_count=sample_count, test_item_count=test_item_count, report_count=report_count,
#                            invoice_count=invoice_count, service_reqeusts=service_requests, samples=samples,
#                            invoices=invoices)


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
    user_agent = request.headers.get('User-Agent')
    is_mobile = False
    mobile_agents = ['Mobile', 'Android', 'iPhone', 'iPad']
    for m in mobile_agents:
        if m in user_agent:
            is_mobile = True
            break
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
    return render_template('academic_services/customer_index.html', form=form, labs=labs,
                           is_mobile=is_mobile)


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
        sub_lab = ServiceSubLab.query.filter_by(code=service_request.sub_lab.code).first()
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
        req = ServiceRequest(customer_id=current_user.id, created_at=arrow.now('Asia/Bangkok').datetime,
                             sub_lab=sub_lab,
                             request_no=request_no.number, product=products, data=format_data(form.data))
        request_no.count += 1
    db.session.add(req)
    db.session.commit()
    return redirect(url_for('academic_services.create_report_language', request_id=req.id, menu='request',
                            code=req.sub_lab.code))


@academic_services.route('/portal/request')
def create_request():
    menu = request.args.get('menu')
    code = request.args.get('code')
    request_id = request.args.get('request_id')
    request_paths = {'bacteria': 'academic_services.create_bacteria_request',
                     'disinfection': 'academic_services.create_virus_disinfection_request',
                     'air_disinfection': 'academic_services.create_virus_air_disinfection_request',
                     'heavymetal': 'academic_services.create_heavy_metal_request',
                     'foodsafety': 'academic_services.create_food_safety_request',
                     'protein_identification': 'academic_services.create_protein_identification_request',
                     'sds_page': 'academic_services.create_sds_page_request',
                     'quantitative': 'academic_services.create_quantitative_request',
                     'metabolomics': 'academic_services.create_metabolomic_request',
                     'endotoxin': 'academic_services.create_endotoxin_request',
                     }
    return redirect(url_for(request_paths[code], code=code, menu=menu, request_id=request_id))


@academic_services.route('/request/bacteria/add', methods=['GET', 'POST'])
@academic_services.route('/request/bacteria/edit/<int:request_id>', methods=['GET', 'POST'])
def create_bacteria_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = BacteriaRequestForm(data=data)
    else:
        form = BacteriaRequestForm()
    for n, org in enumerate(bacteria_liquid_organisms):
        liquid_entry = form.liquid_condition_field.liquid_organism_fields[n]
        liquid_entry.liquid_organism.choices = [(org, org)]
    for n, org in enumerate(bacteria_liquid_organisms):
        spray_entry = form.spray_condition_field.spray_organism_fields[n]
        spray_entry.spray_organism.choices = [(org, org)]
    for n, org in enumerate(bacteria_liquid_organisms):
        sheet_entry = form.sheet_condition_field.sheet_organism_fields[n]
        sheet_entry.sheet_organism.choices = [(org, org)]
    for n, org in enumerate(bacteria_wash_organisms):
        after_wash_entry = form.after_wash_condition_field.after_wash_organism_fields[n]
        after_wash_entry.after_wash_organism.choices = [(org, org)]
    for n, org in enumerate(bacteria_wash_organisms):
        in_wash_entry = form.in_wash_condition_field.in_wash_organism_fields[n]
        in_wash_entry.in_wash_organism.choices = [(org, org)]
    if request.method == 'POST':
        for n, org in enumerate(bacteria_liquid_organisms):
            liquid_entry = form.liquid_condition_field.liquid_organism_fields[n]
            print('label', liquid_entry.liquid_organism.label, 'choice', liquid_entry.liquid_organism.choices, 'data',
                  liquid_entry.liquid_organism.data)
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(1)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(customer_id=current_user.id, created_at=arrow.now('Asia/Bangkok').datetime,
                                             sub_lab=sub_lab, request_no=request_no.number, data=format_data(form.data),
                                             status_id=status_id)
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('academic_services.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('academic_services/forms/bacteria_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@academic_services.route("/request/collect_sample_during_testing")
def get_collect_sample_during_testing():
    request_id = request.args.get("request_id")
    collect_sample_during_testing = request.args.get("collect_sample_during_testing")
    label = 'ระบุ'

    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        if service_request and service_request.data:
            data = service_request.data
            collect_sample_during_testing_other = data.get('collect_sample_during_testing_other', '')
        else:
            collect_sample_during_testing_other = ''
    else:
        collect_sample_during_testing_other = ''
    if collect_sample_during_testing == 'อื่นๆ โปรดระบุ':
        html = f'''
            <div class="field">
                <label class="label">
                    {label}
                    <span class="has-text-danger">*</span>
                </label>
                <div class="control">
                    <input name="collect_sample_during_testing_other" class="input" value="{collect_sample_during_testing_other}" required
                    oninvalid="this.setCustomValidity('กรุณาเลือกการเก็บตัวอย่างระหว่างรอทดสอบ')" oninput="this.setCustomValidity('')">
                </div>
            </div>
        '''
    else:
        html = '<input type="hidden" name="collect_sample_during_testing_other" class="input" value="">'
    resp = make_response(html)
    return resp


@academic_services.route('/request/bacteria/condition')
def get_bacteria_condition_form():
    product_type = request.args.get("product_type")
    if not product_type:
        return ''
    form = BacteriaRequestForm()
    for n, org in enumerate(bacteria_liquid_organisms):
        liquid_entry = form.liquid_condition_field.liquid_organism_fields[n]
        liquid_entry.liquid_organism.choices = [(org, org)]
    for n, org in enumerate(bacteria_liquid_organisms):
        spray_entry = form.spray_condition_field.spray_organism_fields[n]
        spray_entry.spray_organism.choices = [(org, org)]
    for n, org in enumerate(bacteria_liquid_organisms):
        sheet_entry = form.sheet_condition_field.sheet_organism_fields[n]
        sheet_entry.sheet_organism.choices = [(org, org)]
    for n, org in enumerate(bacteria_wash_organisms):
        after_wash_entry = form.after_wash_condition_field.after_wash_organism_fields[n]
        after_wash_entry.after_wash_organism.choices = [(org, org)]
    for n, org in enumerate(bacteria_wash_organisms):
        in_wash_entry = form.in_wash_condition_field.in_wash_organism_fields[n]
        in_wash_entry.in_wash_organism.choices = [(org, org)]
    field_name = f"{product_type}_condition_field"
    fields = getattr(form, field_name)
    return render_template('academic_services/partials/bacteria_request_condition_form.html', fields=fields)


@academic_services.route('/request/virus_disinfection/add', methods=['GET', 'POST'])
@academic_services.route('/request/virus_disinfection/edit/<int:request_id>', methods=['GET', 'POST'])
def create_virus_disinfection_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = VirusDisinfectionRequestForm(data=data)
    else:
        form = VirusDisinfectionRequestForm()
    for n, org in enumerate(virus_liquid_organisms):
        liquid_entry = form.liquid_condition_field.liquid_organism_fields[n]
        liquid_entry.liquid_organism.choices = [(org, org)]
    for n, org in enumerate(virus_liquid_organisms):
        spray_entry = form.spray_condition_field.spray_organism_fields[n]
        spray_entry.spray_organism.choices = [(org, org)]
    for n, org in enumerate(virus_liquid_organisms):
        coat_entry = form.coat_condition_field.coat_organism_fields[n]
        coat_entry.coat_organism.choices = [(org, org)]
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(1)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(customer_id=current_user.id, created_at=arrow.now('Asia/Bangkok').datetime,
                                             sub_lab=sub_lab, request_no=request_no.number, data=format_data(form.data),
                                             status_id=status_id)
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('academic_services.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('academic_services/forms/virus_disinfection_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@academic_services.route("/request/product_storage")
def get_product_storage():
    request_id = request.args.get("request_id")
    product_storage = request.args.get("product_storage")
    label = 'ระบุ'
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        if service_request and service_request.data:
            data = service_request.data
            product_storage_other = data.get('product_storage_other', '')
        else:
            product_storage_other = ''
    else:
        product_storage_other = ''
    if product_storage == 'อื่นๆ โปรดระบุ':
        html = f'''
            <div class="field">
                <label class="label">
                    {label}
                    <span class="has-text-danger">*</span>
                </label>
                <div class="control">
                    <input name="product_storage_other" class="input" value="{product_storage_other}" required 
                    oninvalid="this.setCustomValidity('กรุณาเลือกการเก็บรักษาผลิตภัณฑ์')" oninput="this.setCustomValidity('')">
                </div>
            </div>
        '''
    else:
        html = '<input type="hidden" name="product_storage_other" class="input" value="">'
    resp = make_response(html)
    return resp


@academic_services.route('/request/virus_disinfection/condition')
def get_virus_disinfection_condition_form():
    product_type = request.args.get("product_type")
    if not product_type:
        return ''
    form = VirusDisinfectionRequestForm()
    for n, org in enumerate(virus_liquid_organisms):
        liquid_entry = form.liquid_condition_field.liquid_organism_fields[n]
        liquid_entry.liquid_organism.choices = [(org, org)]
    for n, org in enumerate(virus_liquid_organisms):
        spray_entry = form.spray_condition_field.spray_organism_fields[n]
        spray_entry.spray_organism.choices = [(org, org)]
    for n, org in enumerate(virus_liquid_organisms):
        coat_entry = form.coat_condition_field.coat_organism_fields[n]
        coat_entry.coat_organism.choices = [(org, org)]
    field_name = f"{product_type}_condition_field"
    fields = getattr(form, field_name)
    return render_template('academic_services/partials/virus_disinfection_request_condition_form.html',
                           fields=fields, product_type=product_type)


@academic_services.route('/request/virus_air_disinfection/add', methods=['GET', 'POST'])
@academic_services.route('/request/virus_air_disinfection/edit/<int:request_id>', methods=['GET', 'POST'])
def create_virus_air_disinfection_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = VirusAirDisinfectionRequestForm(data=data)
    else:
        form = VirusAirDisinfectionRequestForm()
    for n, org in enumerate(virus_liquid_organisms):
        surface_entry = form.surface_condition_field.surface_disinfection_organism_fields[n]
        surface_entry.surface_disinfection_organism.choices = [(org, org)]
    for n, org in enumerate(virus_airborne_organisms):
        airborne_entry = form.airborne_condition_field.airborne_disinfection_organism_fields[n]
        airborne_entry.airborne_disinfection_organism.choices = [(org, org)]
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(1)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(customer_id=current_user.id, created_at=arrow.now('Asia/Bangkok').datetime,
                                             sub_lab=sub_lab, request_no=request_no.number, data=format_data(form.data),
                                             status_id=status_id)
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('academic_services.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('academic_services/forms/virus_air_disinfection_request_form.html', code=code,
                           sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@academic_services.route('/request/virus_air_disinfection/condition')
def get_virus_air_disinfection_condition_form():
    product_type = request.args.get("product_type")
    if not product_type:
        return ''
    form = VirusAirDisinfectionRequestForm()
    for n, org in enumerate(virus_liquid_organisms):
        surface_entry = form.surface_condition_field.surface_disinfection_organism_fields[n]
        surface_entry.surface_disinfection_organism.choices = [(org, org)]
    for n, org in enumerate(virus_airborne_organisms):
        airborne_entry = form.airborne_condition_field.airborne_disinfection_organism_fields[n]
        airborne_entry.airborne_disinfection_organism.choices = [(org, org)]
    field_name = f"{product_type}_condition_field"
    fields = getattr(form, field_name)
    return render_template('academic_services/partials/virus_air_disinfection_request_condition_form.html',
                           fields=fields)


@academic_services.route('/request/condition/remove', methods=['GET', 'POST'])
def remove_condition_form():
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    field = request.form.get("field")
    data = service_request.data or {}
    if field in data:
        del data[field]
        db.session.execute(
            update(ServiceRequest)
            .where(ServiceRequest.id == request_id)
            .values(data=data)
        )
        db.session.commit()
    return ""


@academic_services.route('/request/heavy_metal/add', methods=['GET', 'POST'])
@academic_services.route('/request/heavy_metal/edit/<int:request_id>', methods=['GET', 'POST'])
def create_heavy_metal_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = HeavyMetalRequestForm(data=data)
    else:
        form = HeavyMetalRequestForm()
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(1)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(customer_id=current_user.id, created_at=arrow.now('Asia/Bangkok').datetime,
                                             sub_lab=sub_lab, request_no=request_no.number, data=format_data(form.data),
                                             status_id=status_id)
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('academic_services.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('academic_services/forms/heavy_metal_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@academic_services.route('/api/request/heavy_metal/item/add', methods=['POST'])
def add_heavy_metal_condition_item():
    form = HeavyMetalRequestForm()
    form.heavy_metal_condition_field.append_entry()
    item_form = form.heavy_metal_condition_field[-1]
    index = len(form.heavy_metal_condition_field)
    template = """
        <div id="{}">
            <hr style="background-color: #F3F3F3">
            <p><strong>รายการที่ {}</strong></p>
            <table class="table is-fullwidth ">
                <thead>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                </thead>
                <tbody>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">
                        {}
                        <div class="mt-2 ml-4">
                            <label class="label">{}</label>
                            {}
                        </div>
                    </td>
                </tbody>
            </table>
        </div>
    """
    resp = template.format(item_form.id,
                           index,
                           item_form.no.label,
                           item_form.sample_name.label,
                           item_form.quantity.label,
                           item_form.parameter_test.label,
                           item_form.no(class_='input'),
                           item_form.sample_name(class_='input'),
                           item_form.quantity(class_='input'),
                           item_form.parameter_test(),
                           item_form.parameter_test_other.label,
                           item_form.parameter_test_other(class_='input')
                           )
    resp = make_response(resp)
    return resp


@academic_services.route('/api/request/heavy_metal/item/remove', methods=['DELETE'])
def remove_heavy_metal_condition_item():
    form = HeavyMetalRequestForm()
    form.heavy_metal_condition_field.pop_entry()
    resp = ''
    for i, item_form in enumerate(form.quantitative_condition_field, start=1):
        hr = '<hr style="background-color: #F3F3F3">' if i > 1 else ''
        template = """
            <div id="{}">
                {}  
                <p><strong>รายการที่ {}</strong></p>
                <table class="table is-fullwidth ">
                    <thead>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                    </thead>
                    <tbody>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">
                            {}
                            <div class="mt-2 ml-4">
                                <label class="label">{}</label>
                                    {}
                                </div>
                        </td>
                    </tbody>
                </table>
            </div>
        """
        resp += template.format(item_form.id,
                                hr,
                                i,
                                item_form.no.label,
                                item_form.sample_name.label,
                                item_form.quantity.label,
                                item_form.parameter_test.label,
                                item_form.no(class_='input'),
                                item_form.sample_name(class_='input'),
                                item_form.quantity(class_='input'),
                                item_form.parameter_test(),
                                item_form.parameter_test_other.label,
                                item_form.parameter_test_other(class_='input')
                                )
    resp = make_response(resp)
    return resp


@academic_services.route('/request/food_safety/add', methods=['GET', 'POST'])
@academic_services.route('/request/food_safety/edit/<int:request_id>', methods=['GET', 'POST'])
def create_food_safety_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = FoodSafetyRequestForm(data=data)
    else:
        form = FoodSafetyRequestForm()
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(1)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(customer_id=current_user.id, created_at=arrow.now('Asia/Bangkok').datetime,
                                             sub_lab=sub_lab, request_no=request_no.number, data=format_data(form.data),
                                             status_id=status_id)
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('academic_services.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('academic_services/forms/food_safety_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@academic_services.route('/api/request/food_safety/item/add', methods=['POST'])
def add_food_safety_condition_item():
    form = FoodSafetyRequestForm()
    form.food_safety_condition_field.append_entry()
    item_form = form.food_safety_condition_field[-1]
    index = len(form.food_safety_condition_field)
    template = """
        <div id="{}">
            <hr style="background-color: #F3F3F3">
            <p><strong>รายการที่ {}</strong></p>
            <table class="table is-fullwidth ">
                <thead>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                </thead>
                <tbody>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">
                        {}
                        <div class="mt-2 ml-4">
                            <label class="label">{}</label>
                            {}
                        </div>
                    </td>
                </tbody>
            </table>
        </div>
    """
    resp = template.format(item_form.id,
                           index,
                           item_form.no.label,
                           item_form.sample_name.label,
                           item_form.quantity.label,
                           item_form.parameter_test.label,
                           item_form.no(class_='input'),
                           item_form.sample_name(class_='input'),
                           item_form.quantity(class_='input'),
                           item_form.parameter_test(),
                           item_form.parameter_test_other.label,
                           item_form.parameter_test_other(class_='input')
                           )
    resp = make_response(resp)
    return resp


@academic_services.route('/api/request/food_safety/item/remove', methods=['DELETE'])
def remove_food_safety_condition_item():
    form = FoodSafetyRequestForm()
    form.food_safety_condition_field.pop_entry()
    resp = ''
    for i, item_form in enumerate(form.quantitative_condition_field, start=1):
        hr = '<hr style="background-color: #F3F3F3">' if i > 1 else ''
        template = """
            <div id="{}">
                {}  
                <p><strong>รายการที่ {}</strong></p>
                <table class="table is-fullwidth ">
                    <thead>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                    </thead>
                    <tbody>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">
                            {}
                            <div class="mt-2 ml-4">
                                <label class="label">{}</label>
                                    {}
                                </div>
                        </td>
                    </tbody>
                </table>
            </div>
        """
        resp += template.format(item_form.id,
                                hr,
                                i,
                                item_form.no.label,
                                item_form.sample_name.label,
                                item_form.quantity.label,
                                item_form.parameter_test.label,
                                item_form.no(class_='input'),
                                item_form.sample_name(class_='input'),
                                item_form.quantity(class_='input'),
                                item_form.parameter_test(),
                                item_form.parameter_test_other.label,
                                item_form.parameter_test_other(class_='input')
                                )
    resp = make_response(resp)
    return resp


@academic_services.route("/request/objective")
def get_objective():
    request_id = request.args.get("request_id")
    objective = request.args.get("objective")
    label = 'ระบุ'
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        if service_request and service_request.data:
            data = service_request.data
            objective_other = data.get('objective_other', '')
        else:
            objective_other = ''
    else:
        objective_other = ''
    if objective == 'อื่นๆ/Other':
        html = f'''
            <div class="field ml-4 mb-4">
                <label class="label">
                    {label}
                    <span class="has-text-danger">*</span>
                </label>
                <div class="control">
                    <input name="objective_other" class="input" value="{objective_other}" required 
                    oninvalid="this.setCustomValidity('กรุณากรอกข้อมูล')" oninput="this.setCustomValidity('')">
                </div>
            </div>
        '''
    else:
        html = '<input type="hidden" name="objective_other" class="input" value="">'
    resp = make_response(html)
    return resp


@academic_services.route("/request/standard_limitation")
def get_standard_limitation():
    request_id = request.args.get("request_id")
    standard_limitation = request.args.get("standard_limitation")
    label = 'ระบุ'
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        if service_request and service_request.data:
            data = service_request.data
            standard_limitation_other = data.get('standard_limitation_other', '')
        else:
            standard_limitation_other = ''
    else:
        standard_limitation_other = ''
    if standard_limitation == 'Other':
        html = f'''
            <div class="field ml-4 mb-4">
                <label class="label">
                    {label}
                    <span class="has-text-danger">*</span>
                </label>
                <div class="control">
                    <input name="standard_limitation_other" class="input" value="{standard_limitation_other}" required 
                    oninvalid="this.setCustomValidity('กรุณากรอกข้อมูล')" oninput="this.setCustomValidity('')">
                </div>
            </div>
        '''
    else:
        html = '<input type="hidden" name="standard_limitation_other" class="input" value="">'
    resp = make_response(html)
    return resp


@academic_services.route("/request/other_service")
def get_other_service():
    request_id = request.args.get("request_id")
    other_service = request.args.get("other_service")
    label = 'ระบุ'
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        if service_request and service_request.data:
            data = service_request.data
            other_service_note = data.get('other_service_note', '')
        else:
            other_service_note = ''
    else:
        other_service_note = ''
    if other_service == 'Other':
        html = f'''
            <div class="field ml-4 mb-4">
                <label class="label">
                    {label}
                    <span class="has-text-danger">*</span>
                </label>
                <div class="control">
                    <input name="other_service_note" class="input" value="{other_service_note}" required 
                    oninvalid="this.setCustomValidity('กรุณากรอกข้อมูล')" oninput="this.setCustomValidity('')">
                </div>
            </div>
        '''
    else:
        html = '<input type="hidden" name="other_service_note" class="input" value="">'
    resp = make_response(html)
    return resp


@academic_services.route('/request/protein_identification/add', methods=['GET', 'POST'])
@academic_services.route('/request/protein_identification/edit/<int:request_id>', methods=['GET', 'POST'])
def create_protein_identification_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = ProteinIdentificationRequestForm(data=data)
    else:
        form = ProteinIdentificationRequestForm()
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(1)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(customer_id=current_user.id, created_at=arrow.now('Asia/Bangkok').datetime,
                                             sub_lab=sub_lab, request_no=request_no.number, data=format_data(form.data),
                                             status_id=status_id)
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('academic_services.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('academic_services/forms/protein_identification_request_form.html', code=code,
                           sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@academic_services.route('/api/request/protein_identification/item/add', methods=['POST'])
def add_protein_identification_condition_item():
    form = ProteinIdentificationRequestForm()
    form.protein_identification_condition_field.append_entry()
    item_form = form.protein_identification_condition_field[-1]
    index = len(form.protein_identification_condition_field)
    template = """
        <div id="{}">
            <hr style="background-color: #F3F3F3">
            <p><strong>รายการที่ {}</strong></p>
            <table class="table is-fullwidth ">
                <thead>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                </thead>
                <tbody>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                </tbody>
            </table>
        </div>
    """
    resp = template.format(item_form.id,
                           index,
                           item_form.sample_name.label,
                           item_form.clean_up.label,
                           item_form.protein_identification.label,
                           item_form.sample_name(class_='input'),
                           item_form.clean_up(),
                           item_form.protein_identification()
                           )
    resp = make_response(resp)
    return resp


@academic_services.route('/api/request/protein_identification/item/remove', methods=['DELETE'])
def remove_protein_identification_condition_item():
    form = ProteinIdentificationRequestForm()
    form.protein_identification_condition_field.pop_entry()
    resp = ''
    for i, item_form in enumerate(form.quantitative_condition_field, start=1):
        hr = '<hr style="background-color: #F3F3F3">' if i > 1 else ''
        template = """
            <div id="{}">
                {}  
                <p><strong>รายการที่ {}</strong></p>
                <table class="table is-fullwidth ">
                    <thead>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                    </thead>
                    <tbody>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                    </tbody>
                </table>
            </div>
        """
        resp += template.format(item_form.id,
                                hr,
                                i,
                                item_form.sample_name.label,
                                item_form.clean_up.label,
                                item_form.protein_identification.label,
                                item_form.sample_name(class_='input'),
                                item_form.clean_up(),
                                item_form.protein_identification()
                                )
    resp = make_response(resp)
    return resp


@academic_services.route('/request/sds_page/add', methods=['GET', 'POST'])
@academic_services.route('/request/sds_page/edit/<int:request_id>', methods=['GET', 'POST'])
def create_sds_page_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = SDSPageRequestForm(data=data)
    else:
        form = SDSPageRequestForm()
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(1)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(customer_id=current_user.id, created_at=arrow.now('Asia/Bangkok').datetime,
                                             sub_lab=sub_lab, request_no=request_no.number, data=format_data(form.data),
                                             status_id=status_id)
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('academic_services.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('academic_services/forms/sds_page_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@academic_services.route('/api/request/sds_page/item/add', methods=['POST'])
def add_sds_page_condition_item():
    form = SDSPageRequestForm()
    form.sds_page_condition_field.append_entry()
    item_form = form.sds_page_condition_field[-1]
    index = len(form.sds_page_condition_field)
    template = """
        <div id="{}">
            <hr style="background-color: #F3F3F3">
            <p><strong>รายการที่ {}</strong></p>
            <table class="table is-fullwidth ">
                <thead>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                </thead>
                <tbody>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                </tbody>
            </table>
        </div>
    """
    resp = template.format(item_form.id,
                           index,
                           item_form.sample_name.label,
                           item_form.clean_up.label,
                           item_form.staining.label,
                           item_form.sample_name(class_='input'),
                           item_form.clean_up(),
                           item_form.staining()
                           )
    resp = make_response(resp)
    return resp


@academic_services.route('/api/request/sds_page/item/remove', methods=['DELETE'])
def remove_sds_page_condition_item():
    form = SDSPageRequestForm()
    form.sds_page_condition_field.pop_entry()
    resp = ''
    for i, item_form in enumerate(form.quantitative_condition_field, start=1):
        hr = '<hr style="background-color: #F3F3F3">' if i > 1 else ''
        template = """
            <div id="{}">
                {}   
                <p><strong>รายการที่ {}</strong></p>
                <table class="table is-fullwidth ">
                    <thead>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                    </thead>
                    <tbody>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                    </tbody>
                </table>
            </div>
        """
        resp += template.format(item_form.id,
                                hr,
                                i,
                                item_form.sample_name.label,
                                item_form.clean_up.label,
                                item_form.staining.label,
                                item_form.sample_name(class_='input'),
                                item_form.clean_up(),
                                item_form.staining()
                                )
    resp = make_response(resp)
    return resp


@academic_services.route('/request/quantitative/add', methods=['GET', 'POST'])
@academic_services.route('/request/quantitative/edit/<int:request_id>', methods=['GET', 'POST'])
def create_quantitative_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = QuantitativeRequestForm(data=data)
    else:
        form = QuantitativeRequestForm()
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(1)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(customer_id=current_user.id, created_at=arrow.now('Asia/Bangkok').datetime,
                                             sub_lab=sub_lab, request_no=request_no.number, data=format_data(form.data),
                                             status_id=status_id)
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('academic_services.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('academic_services/forms/quantitative_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@academic_services.route('/api/request/quantitative/item/add', methods=['POST'])
def add_quantitative_condition_item():
    form = QuantitativeRequestForm()
    form.quantitative_condition_field.append_entry()
    item_form = form.quantitative_condition_field[-1]
    index = len(form.quantitative_condition_field)
    template = """
        <div id="{}">
            <hr style="background-color: #F3F3F3">
            <p><strong>รายการที่ {}</strong></p>
            <table class="table is-fullwidth ">
                <thead>
                    <th style="border: none">
                        {}
                        <span class="has-text-danger">*</span>
                    </th>
                    <th style="border: none">
                        {}
                        <span class="has-text-danger">*</span>
                    </th>
                    <th style="border: none">
                        {}
                        <span class="has-text-danger">*</span>
                    </th>
                </thead>
                <tbody>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                </tbody>
            </table>
        </div>
    """
    resp = template.format(item_form.id,
                           index,
                           item_form.sample_name.label,
                           item_form.protein_concentration.label,
                           item_form.quantitative_method.label,
                           item_form.sample_name(class_='input'),
                           item_form.protein_concentration(class_='input'),
                           item_form.quantitative_method()
                           )
    resp = make_response(resp)
    return resp


@academic_services.route('/api/request/quantitative/item/remove', methods=['DELETE'])
def remove_quantitative_condition_item():
    form = QuantitativeRequestForm()
    form.quantitative_condition_field.pop_entry()
    resp = ''
    for i, item_form in enumerate(form.quantitative_condition_field, start=1):
        hr = '<hr style="background-color: #F3F3F3">' if i > 1 else ''
        template = """
            <div id="{}">
                {}
                <p><strong>รายการที่ {}</strong></p>
                <table class="table is-fullwidth ">
                    <thead>
                        <th style="border: none">
                            {}
                            <span class="has-text-danger">*</span>
                        </th>
                        <th style="border: none">
                            {}
                            <span class="has-text-danger">*</span>
                        </th>
                        <th style="border: none">
                            {}
                            <span class="has-text-danger">*</span>
                        </th>
                    </thead>
                    <tbody>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                    </tbody>
                </table>
            </div>
        """
        resp += template.format(item_form.id,
                                hr,
                                i,
                                item_form.sample_name.label,
                                item_form.protein_concentration.label,
                                item_form.quantitative_method.label,
                                item_form.sample_name(class_='input'),
                                item_form.protein_concentration(class_='input'),
                                item_form.quantitative_method()
                                )
    resp = make_response(resp)
    return resp


@academic_services.route('/request/metabolomic/add', methods=['GET', 'POST'])
@academic_services.route('/request/metabolomic/edit/<int:request_id>', methods=['GET', 'POST'])
def create_metabolomic_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = MetabolomicRequestForm(data=data)
    else:
        form = MetabolomicRequestForm()
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(1)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(customer_id=current_user.id, created_at=arrow.now('Asia/Bangkok').datetime,
                                             sub_lab=sub_lab, request_no=request_no.number, data=format_data(form.data),
                                             status_id=status_id)
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('academic_services.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('academic_services/forms/metabolomic_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@academic_services.route('/api/request/metabolomic/item/add', methods=['POST'])
def add_metabolomic_condition_item():
    form = MetabolomicRequestForm()
    form.metabolomic_condition_field.append_entry()
    item_form = form.metabolomic_condition_field[-1]
    index = len(form.metabolomic_condition_field)
    template = """
        <div id="{}">
            <hr style="background-color: #F3F3F3">
            <p><strong>รายการที่ {}</strong></p>
            <table class="table is-fullwidth ">
                <thead>
                    <th style="border: none">{}<span class="has-text-danger">*</span></th>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                </thead>
                <tbody>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                </tbody>
            </table>
        </div>
    """
    resp = template.format(item_form.id,
                           index,
                           item_form.sample_name.label,
                           item_form.clean_up.label,
                           item_form.untargeted_metabolomic.label,
                           item_form.quantitative_metabolomic.label,
                           item_form.sample_name(class_='input'),
                           item_form.clean_up(),
                           item_form.untargeted_metabolomic(),
                           item_form.quantitative_metabolomic()
                           )
    resp = make_response(resp)
    return resp


@academic_services.route('/api/request/metabolomic/item/remove', methods=['DELETE'])
def remove_metabolomic_condition_item():
    form = MetabolomicRequestForm()
    form.metabolomic_condition_field.pop_entry()
    resp = ''
    for i, item_form in enumerate(form.metabolomic_condition_field, start=1):
        hr = '<hr style="background-color: #F3F3F3">' if i > 1 else ''
        template = """
            <div id="{}">
                {}
                <p><strong>รายการที่ {}</strong></p>
                <table class="table is-fullwidth ">
                    <thead>
                        <th style="border: none">{}<span class="has-text-danger">*</span></th>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                    </thead>
                    <tbody>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                    </tbody>
                </table>
            </div>
        """
        resp += template.format(item_form.id,
                                hr,
                                i,
                                item_form.sample_name.label,
                                item_form.clean_up.label,
                                item_form.untargeted_metabolomic.label,
                                item_form.quantitative_metabolomic.label,
                                item_form.sample_name(class_='input'),
                                item_form.clean_up(),
                                item_form.untargeted_metabolomic(),
                                item_form.quantitative_metabolomic()
                                )
    resp = make_response(resp)
    return resp


@academic_services.route("/request/sample_species_other")
def get_sample_species_other():
    request_id = request.args.get("request_id")
    sample_species = request.args.getlist("sample_species")
    label = 'Comment'
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        if service_request and service_request.data:
            data = service_request.data
            sample_species_other = data.get('sample_species_other', '')
        else:
            sample_species_other = ''
    else:
        sample_species_other = ''
    if "Others" in sample_species:
        html = f'''
            <div class="field ml-4 mb-4">
                <label class="label">
                    {label}
                    <span class="has-text-danger">*</span>
                </label>
                <div class="control">
                    <input name="sample_species_other" class="input" value="{sample_species_other}" required 
                    oninvalid="this.setCustomValidity('Please fill in the information.')" oninput="this.setCustomValidity('')">
                </div>
            </div>
        '''
    else:
        html = '<input type="hidden" name="sample_species_other" class="input" value="">'
    resp = make_response(html)
    return resp


@academic_services.route("/request/gel_slices_other")
def get_gel_slices_other():
    request_id = request.args.get("request_id")
    gel_slices = request.args.getlist("gel_slices")
    label = 'Comment'
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        if service_request and service_request.data:
            data = service_request.data
            gel_slices_other = data.get('gel_slices_other', '')
        else:
            gel_slices_other = ''
    else:
        gel_slices_other = ''
    if "Others" in gel_slices:
        html = f'''
            <div class="field ml-4 mb-4">
                <label class="label">
                    {label}
                    <span class="has-text-danger">*</span>
                </label>
                <div class="control">
                    <input name="gel_slices_other" class="input" value="{gel_slices_other}" required 
                    oninvalid="this.setCustomValidity('Please fill in the information.')" oninput="this.setCustomValidity('')">
                </div>
            </div>
        '''
    else:
        html = '<input type="hidden" name="gel_slices_other" class="input" value="">'
    resp = make_response(html)
    return resp


@academic_services.route("/request/sample_type_other")
def get_sample_type_other():
    request_id = request.args.get("request_id")
    sample_type = request.args.getlist("sample_type")
    label = 'Comment'
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        if service_request and service_request.data:
            data = service_request.data
            sample_type_other = data.get('sample_type_other', '')
        else:
            sample_type_other = ''
    else:
        sample_type_other = ''
    if "Others" in sample_type:
        html = f'''
                <div class="field ml-4 mb-4">
                    <label class="label">
                        {label}
                        <span class="has-text-danger">*</span>
                    </label>
                    <div class="control">
                        <input name="sample_type_other" class="input" value="{sample_type_other}" required 
                        oninvalid="this.setCustomValidity('Please fill in the information.')" oninput="this.setCustomValidity('')">
                    </div>
                </div>
            '''
    else:
        html = '<input type="hidden" name="sample_type_other" class="input" value="">'
    resp = make_response(html)
    return resp


@academic_services.route('/request/endotoxin/add', methods=['GET', 'POST'])
@academic_services.route('/request/endotoxin/edit/<int:request_id>', methods=['GET', 'POST'])
def create_endotoxin_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = EndotoxinRequestForm(data=data)
    else:
        form = EndotoxinRequestForm()
    for item_form in form.endotoxin_condition_field:
        if not item_form.org_name.data:
            item_form.org_name.data = current_user.customer_info.cus_name
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(1)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(customer_id=current_user.id, created_at=arrow.now('Asia/Bangkok').datetime,
                                             sub_lab=sub_lab, request_no=request_no.number, data=format_data(form.data),
                                             status_id=status_id)
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('academic_services.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('academic_services/forms/endotoxin_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@academic_services.route('/api/request/endotoxin/item/add', methods=['POST'])
def add_endotoxin_condition_item():
    form = EndotoxinRequestForm()
    form.endotoxin_condition_field.append_entry()
    item_form = form.endotoxin_condition_field[-1]
    index = len(form.endotoxin_condition_field)
    item_form.org_name.data = current_user.customer_info.cus_name
    template = """
        <div id="{}">
            <hr style="background-color: #F3F3F3">
            <p><strong>รายการที่ {}</strong></p>
            <table class="table is-fullwidth ">
                <thead>
                    <th style="border: none">{}<span class="has-text-danger">*</span></th>
                    <th style="border: none">{}<span class="has-text-danger">*</span></th>
                    <th style="border: none">{}<span class="has-text-danger">*</span></th>
                    <th style="border: none">{}<span class="has-text-danger">*</span></th>
                    <th style="border: none">{}<span class="has-text-danger">*</span></th>
                    <th style="border: none">{}<span class="has-text-danger">*</span></th>
                </thead>
                <tbody>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="select">{}</td>
                    <td style="border: none" class="control">{}</td>
                    <td style="border: none" class="control">{}</td>
                </tbody>
            </table>
        </div>
    """
    resp = template.format(item_form.id,
                           index,
                           item_form.no.label,
                           item_form.org_name.label,
                           item_form.sample_name.label,
                           item_form.sample_type.label,
                           item_form.received_by.label,
                           item_form.received_at.label,
                           item_form.no(class_='input'),
                           item_form.org_name(class_='input'),
                           item_form.sample_name(class_='input'),
                           item_form.sample_type(),
                           item_form.received_by(class_='input'),
                           item_form.received_at(class_='input')
                           )
    resp = make_response(resp)
    resp.headers['HX-Trigger-After-Swap'] = 'activateDateRangePickerEvent'
    return resp


@academic_services.route('/api/request/endotoxin/item/remove', methods=['DELETE'])
def remove_endotoxin_condition_item():
    form = EndotoxinRequestForm()
    form.endotoxin_condition_field.pop_entry()
    resp = ''
    for i, item_form in enumerate(form.endotoxin_condition_field, start=1):
        hr = '<hr style="background-color: #F3F3F3">' if i > 1 else ''
        template = """
            <div id="{}">
                {}
                <p><strong>รายการที่ {}</strong></p>
                <table class="table is-fullwidth ">
                    <thead>
                        <th style="border: none">{}<span class="has-text-danger">*</span></th>
                        <th style="border: none">{}<span class="has-text-danger">*</span></th>
                        <th style="border: none">{}<span class="has-text-danger">*</span></th>
                        <th style="border: none">{}<span class="has-text-danger">*</span></th>
                        <th style="border: none">{}<span class="has-text-danger">*</span></th>
                        <th style="border: none">{}<span class="has-text-danger">*</span></th>
                    </thead>
                    <tbody>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="select">{}</td>
                        <td style="border: none" class="control">{}</td>
                        <td style="border: none" class="control">{}</td>
                    </tbody>
                </table>
            </div>
        """
        resp += template.format(item_form.id,
                                hr,
                                i,
                                item_form.no.label,
                                item_form.org_name.label,
                                item_form.sample_name.label,
                                item_form.sample_type.label,
                                item_form.received_by.label,
                                item_form.received_at.label,
                                item_form.no(class_='input'),
                                item_form.org_name(class_='input'),
                                item_form.sample_name(class_='input'),
                                item_form.sample_type(),
                                item_form.received_by(class_='input'),
                                item_form.received_at(class_='input')
                                )
    resp = make_response(resp)
    return resp


@academic_services.route('/customer/report_language/add/<int:request_id>', methods=['GET', 'POST'])
@login_required
def create_report_language(request_id):
    menu = request.args.get('menu')
    code = request.args.get('code')
    service_request = ServiceRequest.query.get(request_id)
    report_languages = ServiceReportLanguage.query.filter_by(sub_lab_id=service_request.sub_lab_id)
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
                                code=code))
    return render_template('academic_services/create_report_language.html', menu=menu, code=code,
                           request_id=request_id, report_languages=report_languages,
                           req_report_language=req_report_language,
                           req_report_language_id=req_report_language_id, service_request=service_request)


@academic_services.route('/customer/detail/add/<int:request_id>', methods=['GET', 'POST'])
@login_required
def create_customer_detail(request_id):
    form = None
    menu = request.args.get('menu')
    code = request.args.get('code')
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
                address = ServiceCustomerAddress.query.get(int(quotation_address_id))
                district_title = 'เขต' if address.province.name == 'กรุงเทพมหานคร' else 'อำเภอ'
                subdistrict_title = 'แขวง' if address.province.name == 'กรุงเทพมหานคร' else 'ตำบล'
                service_request.quotation_address_id = int(quotation_address_id)
                service_request.quotation_name = address.name
                service_request.quotation_issue_address = (
                    f"{address.address} "
                    f"{subdistrict_title}{address.subdistrict} "
                    f"{district_title}{address.district} "
                    f"จังหวัด{address.province} "
                    f"{address.zipcode}"
                )
                service_request.taxpayer_identification_no = address.taxpayer_identification_no
                service_request.quotation_phone_number = address.phone_number
                db.session.add(service_request)
                db.session.commit()
        if request.form.getlist('document_address'):
            for document_address_id in request.form.getlist('document_address'):
                address = ServiceCustomerAddress.query.get(int(quotation_address_id))
                district_title = 'เขต' if address.province.name == 'กรุงเทพมหานคร' else 'อำเภอ'
                subdistrict_title = 'แขวง' if address.province.name == 'กรุงเทพมหานคร' else 'ตำบล'
                service_request.document_address_id = int(document_address_id)
                service_request.receive_name = address.name
                service_request.receive_address = (
                    f"{address.address} "
                    f"{subdistrict_title}{address.subdistrict} "
                    f"{district_title}{address.district} "
                    f"จังหวัด{address.province} "
                    f"{address.zipcode}"
                )
                service_request.receive_phone_number = address.phone_number
                db.session.add(service_request)
                db.session.commit()
        else:
            for quotation_address_id in request.form.getlist('quotation_address'):
                quotation_address = ServiceCustomerAddress.query.get(int(quotation_address_id))
                district_title = 'เขต' if quotation_address.province.name == 'กรุงเทพมหานคร' else 'อำเภอ'
                subdistrict_title = 'แขวง' if quotation_address.province.name == 'กรุงเทพมหานคร' else 'ตำบล'
                service_request.document_address_id = int(quotation_address_id)
                service_request.receive_name = quotation_address.name
                service_request.receive_address = (
                    f"{quotation_address.address} "
                    f"{subdistrict_title}{quotation_address.subdistrict} "
                    f"{district_title}{quotation_address.district} "
                    f"จังหวัด{quotation_address.province} "
                    f"{quotation_address.zipcode}")
                service_request.receive_phone_number = quotation_address.phone_number
                db.session.add(service_request)
                remark = quotation_address.remark if quotation_address.remark else None
                if current_user.customer_info.addresses:
                    for address in current_user.customer_info.addresses:
                        if customer.has_document_address():
                            if address.address_type == 'document':
                                address.name = quotation_address.name
                                address.address_type = 'document'
                                address.province_id = quotation_address.province_id
                                address.district_id = quotation_address.district_id
                                address.subdistrict_id = quotation_address.subdistrict_id
                                address.zipcode = quotation_address.zipcode
                                address.phone_number = quotation_address.phone_number
                                address.remark = remark
                                address.customer_id = current_user.customer_info_id
                        else:
                            address = ServiceCustomerAddress(name=quotation_address.name, address_type='document',
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
                                                     address=quotation_address.address,
                                                     zipcode=quotation_address.zipcode,
                                                     phone_number=quotation_address.phone_number, reamerk=remark,
                                                     customer_id=current_user.customer_info_id,
                                                     province_id=quotation_address.province_id,
                                                     district_id=quotation_address.district_id,
                                                     subdistrict_id=quotation_address.subdistrict_id)
                db.session.add(address)
                db.session.commit()
        status_id = get_status(1)
        service_request.status_id = status_id
        service_request.is_completed = True
        db.session.add(service_request)
        db.session.commit()
        return redirect(url_for('academic_services.view_request', request_id=request_id, menu=menu))
    return render_template('academic_services/create_customer_detail.html', menu=menu,
                           customer=customer, request_id=request_id, code=code, form=form,
                           service_request=service_request,
                           selected_address_id=selected_address_id)


@academic_services.route('/customer/request/index')
@login_required
def request_index():
    menu = request.args.get('menu')
    status_groups = {
        'all': {
            'id': list(range(1, 24)),
            'name': 'รายการทั้งหมด',
            'icon': '<i class="fas fa-list-ul"></i>'
        },
        'send_request': {
            'id': [1, 2],
            'name': 'รอส่งคำขอรับบริการ',
            'icon': '<i class="fas fa-paper-plane"></i>'
        },
        'confirm_quotation': {
            'id': [3, 4, 5],
            'name': 'รอยืนยันใบเสนอราคา',
            'icon': '<i class="fas fa-file-invoice"></i>'
        },
        'send_sample': {
            'id': [6, 8, 9],
            'name': 'รอส่งตัวอย่าง',
            'icon': '<i class="fas fa-truck"></i>'
        },
        'wait_test': {
            'id': [10, 11, 14],
            'name': 'รอทดสอบตัวอย่าง',
            'icon': '<i class="fas fa-vial"></i>'
        },
        'wait_report': {
            'id': [12, 15],
            'name': 'รอยืนยันใบรายงานผล',
            'icon': '<i class="fas fa-file-alt"></i>'
        },
        'wait_payment': {
            'id': [20, 21],
            'name': 'รอชำระเงิน',
            'icon': '<i class="fas fa-money-check-alt"></i>'
        },
        'download_report': {
            'id': [22],
            'name': 'ใบรายงานผลฉบับจริง',
            'icon': '<i class="fas fa-download"></i>'
        }
    }

    for key, group in status_groups.items():
        group_ids = [i for i in group['id'] if i != 7 and i != 23]
        query = ServiceRequest.query.filter(
            ServiceRequest.status.has(ServiceStatus.status_id.in_(group_ids)
                                      ), ServiceRequest.customer_id == current_user.id,
                                         ServiceRequest.is_downloaded == None
        ).count()

        status_groups[key]['count'] = query
    return render_template('academic_services/request_index.html', menu=menu, status_groups=status_groups)


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
        html_blocks = []
        for result in item.results:
            for i in result.result_items:
                if i.final_file:
                    download_file = url_for('academic_services.download_file', key=i.final_file,
                                            download_filename=f"{i.report_language} (ฉบับจริง).pdf")
                    if item.status.status_id == 22:
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
                    else:
                        html = f'''
                                    <div class="field has-addons">
                                        <div class="control">
                                            <a class="button is-small is-light is-link is-rounded Warn">
                                                <span>{i.report_language} (ฉบับจริง)</span>
                                                <span class="icon is-small"><i class="fas fa-download"></i></span>
                                            </a>
                                        </div>
                                    </div>
                                '''
                elif i.draft_file:
                    download_file = url_for('academic_services.download_file', key=i.draft_file,
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


@academic_services.route('/request/view/<int:request_id>')
@login_required
def view_request(request_id=None):
    menu = request.args.get('menu')
    service_request = ServiceRequest.query.get(request_id)
    datas = request_data(service_request, type='form')
    return render_template('academic_services/view_request.html', service_request=service_request, menu=menu,
                           datas=datas)


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

    values = request_data(service_request, type='pdf')

    def all_page_setup(canvas, doc):
        global page_number
        canvas.saveState()
        canvas.setFont("Sarabun", 12)
        page_number = canvas.getPageNumber()
        canvas.drawString(530, 30, f"Page {page_number}")
        canvas.restoreState()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20,
                            leftMargin=20,
                            topMargin=40,
                            bottomMargin=40
                            )

    data = []
    first_page_limit = 700
    current_height = 0
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

    lab_information = '''<para><font size=13>
                        {address}
                        </font></para>'''.format(address=service_request.sub_lab.lab_information)

    lab_table = Table([[logo, Paragraph(lab_information, style=style_sheet['ThaiStyle'])]], colWidths=[45, 330])

    lab_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    staff_only = '''<para><font size=13>
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

    customer_header = Table([[Paragraph('<b>ข้อมูลผู้ส่งตรวจ / Customer</b>', style=header_style)]], colWidths=[530],
                            rowHeights=[25])

    customer_header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    detail_style = ParagraphStyle(
        'ThaiStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=13,
        leading=18
    )

    center_style = ParagraphStyle(
        'CenterStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=13,
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

    document_address = '''<para>ข้อมูลที่อยู่จัดส่งเอกสาร<br/>
                                       ถึง : {name}<br/>
                                       ที่อยู่ : {address}<br/>
                                       เบอร์โทรศัพท์ : {phone_number}<br/>
                                       อีเมล : {email}
                                   </para>
                                   '''.format(name=service_request.receive_name,
                                              address=service_request.receive_address,
                                              phone_number=service_request.receive_phone_number,
                                              email=service_request.customer.contact_email)

    document_address_table = Table([[Paragraph(document_address, style=detail_style)]], colWidths=[265])

    quotation_address = '''<para>ข้อมูลที่อยู่ใบเสนอราคา/ใบแจ้งหนี้/ใบกำกับภาษี<br/>
                                           ออกในนาม : {name}<br/>
                                           ที่อยู่ : {address}<br/>
                                           เลขประจำตัวผู้เสียภาษีอากร : {taxpayer_identification_no}<br/>
                                           เบอร์โทรศัพท์ : {phone_number}<br/>
                                           อีเมล : {email}
                                       </para>
                                       '''.format(name=service_request.quotation_name,
                                                  address=service_request.quotation_issue_address,
                                                  taxpayer_identification_no=service_request.taxpayer_identification_no,
                                                  phone_number=service_request.quotation_phone_number,
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

    title_table = Paragraph(
        '<para align=center><font size=18>ใบขอรับบริการ / REQUEST<br/><br/></font></para>',
        style=style_sheet['ThaiStyle']
    )

    data.append(
        KeepTogether(title_table))
    w, h = title_table.wrap(doc.width, first_page_limit)
    current_height += h
    data.append(KeepTogether(header))
    w, h = header.wrap(doc.width, first_page_limit)
    current_height += h
    data.append(KeepTogether(Spacer(3, 3)))
    current_height += 3
    data.append(KeepTogether(combined_table))
    w, h = combined_table.wrap(doc.width, first_page_limit)
    current_height += h
    data.append(KeepTogether(Spacer(3, 3)))
    current_height += 3
    data.append(KeepTogether(customer_header))
    w, h = customer_header.wrap(doc.width, first_page_limit)
    current_height += h
    data.append(KeepTogether(Spacer(3, 3)))
    current_height += 3
    data.append(KeepTogether(address_table))
    w, h = address_table.wrap(doc.width, first_page_limit)
    current_height += h
    data.append(KeepTogether(customer_table))
    w, h = customer_table.wrap(doc.width, first_page_limit)
    current_height += h

    index = 1
    groups = []
    current_group = None

    for item in values:
        if item['type'] == 'header':
            if current_group:
                groups.append(current_group)
            current_group = {'header': item['data'], 'contents': []}
        else:
            if current_group is None:
                current_group = {'header': 'รายการทดสอบ', 'contents': []}
            current_group['contents'].append(item)
    if current_group:
        groups.append(current_group)

    for group in groups:
        eng_header = 'Sample Detail' if group['header'] == 'ข้อมูลผลิตภัณฑ์' else 'Test Method'
        header_table = Table(
            [[Paragraph(f"<b>{group['header']} / {eng_header}</b>", style=header_style)]],
            colWidths=[530], rowHeights=[25]
        )
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        w, h_header = header_table.wrap(doc.width, first_page_limit)

        reserve_space = 30
        if current_height + h_header + reserve_space > first_page_limit:
            data.append(PageBreak())
            current_height = 0
        data.append(KeepTogether(Spacer(3, 3)))
        current_height += 3
        data.append(KeepTogether(header_table))
        current_height += h_header
        data.append(KeepTogether(Spacer(3, 3)))
        current_height += 3
        text_section = []
        for g in group['contents']:
            if g['type'] == 'content_header':
                text_section.append(f"{index}. {g['data'].strip()}")
                index += 1
            elif g['type'] == 'text':
                text_content = g['data'].split("<br/>")
                for t in text_content:
                    text = t.strip()
                    if not text:
                        continue

                    if ":" in text and "," in text:
                        header, contents = text.split(":", 1)
                        text_section.append(header.strip() + " " + ":")
                        for c in contents.split(","):
                            content = c.strip()
                            if content:
                                text_section.append(f"- {content}")
                    else:
                        text_section.append(text)
            elif g['type'] == 'table':
                if text_section:
                    para = Paragraph("<br/>".join(text_section), style=detail_style)
                    box = Table([[para]], colWidths=[530])
                    box.setStyle(TableStyle([
                        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LINEBELOW', (-1, 0), (-1, -1), 0, colors.white),
                    ]))
                    if current_height > first_page_limit:
                        data.append(PageBreak())
                        current_height = 0
                        data.append(KeepTogether(header_table))
                        w, h = header_table.wrap(doc.width, first_page_limit)
                        current_height += h
                        data.append(KeepTogether(Spacer(3, 3)))
                        current_height += 3
                    data.append(KeepTogether(box))
                    w, h = box.wrap(doc.width, first_page_limit)
                    current_height += h
                    text_section = []

                rows = g['data']
                headers = list(rows[0].keys())
                raw_widths = []
                for h in headers:
                    w = stringWidth(str(h), detail_style.fontName, detail_style.fontSize)
                    if h == "เชื้อ":
                        w += 100
                    else:
                        w += 20
                    raw_widths.append(w)
                total_width = sum(raw_widths)
                max_total = 490

                if total_width > max_total:
                    scale = max_total / total_width
                    col_widths = [w * scale for w in raw_widths]
                else:
                    col_widths = raw_widths
                table_data = [[Paragraph(h, detail_style) for h in headers]]
                for row in rows:
                    table_data.append([Paragraph(str(row.get(h, "")), detail_style) for h in headers])
                table = Table(table_data, colWidths=col_widths)
                table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4)
                ]))

                table_box = Table([[table]], colWidths=[530])
                table_box.setStyle(TableStyle([
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('LINEABOVE', (0, 0), (-1, 0), 0, colors.white),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER')
                ]))
                if current_height > first_page_limit:
                    data.append(PageBreak())
                    current_height = 0
                    data.append(KeepTogether(header_table))
                    w, h = header_table.wrap(doc.width, first_page_limit)
                    current_height += h
                    data.append(KeepTogether(Spacer(3, 3)))
                    current_height += 3
                data.append(KeepTogether(table_box))
                w, h = table.wrap(doc.width, first_page_limit)
                current_height += h

        if text_section:
            para = Paragraph("<br/>".join(text_section), style=detail_style)
            box = Table([[para]], colWidths=[530])
            box.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            data.append(KeepTogether(box))
            w, h = box.wrap(doc.width, first_page_limit)
            current_height += h

    if service_request.report_languages:
        report_header = Table([[Paragraph('<b>ใบรายงานผล / Report</b>', style=header_style)]],
                              colWidths=[530],
                              rowHeights=[25])

        report_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        report = Paragraph("<br/>".join([f"- {rl.report_language.item}" for rl in service_request.report_languages]),
                           style=detail_style)
        report_table = Table([[report]], colWidths=[530])
        report_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        if current_height > first_page_limit:
            data.append(PageBreak())
            current_height = 0
        else:
            data.append(KeepTogether(Spacer(3, 3)))
            current_height += 3
        data.append(KeepTogether(report_header))
        w, h = report_header.wrap(doc.width, first_page_limit)
        current_height += h
        data.append(KeepTogether(Spacer(3, 3)))
        current_height += 3
        data.append(KeepTogether(report_table))
        w, h = report_table.wrap(doc.width, first_page_limit)
        current_height += h

    if (service_request.sub_lab.code == 'bacteria' or service_request.sub_lab.code == 'disinfection' or
            service_request.sub_lab.code == 'air_disinfection'):
        lab_test_header = Table([[Paragraph('<b>สำหรับเจ้าหน้าที่ / Staff Only</b>', style=header_style)]],
                                colWidths=[530],
                                rowHeights=[25])

        lab_test_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        lab_test = '''<para><font size=12>
                            Lab No.<br/>
                            __________________________________________________________________________________________________________________________<br/>
                            สภาพตัวอย่าง <br/>
                            O ปกติ<br/>
                            O ไม่ปกติ<br/>
                            </font></para>'''

        lab_test_table = Table([[Paragraph(lab_test, style=detail_style)]], colWidths=[530])
        lab_test_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        if current_height > first_page_limit:
            data.append(PageBreak())
            current_height = 0
        else:
            data.append(KeepTogether(Spacer(3, 3)))
            current_height += 3
        data.append(KeepTogether(lab_test_header))
        data.append(KeepTogether(Spacer(3, 3)))
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


@academic_services.route('/request/pdf/<int:request_id>', methods=['GET'])
def export_request_pdf(request_id):
    service_request = ServiceRequest.query.get(request_id)
    buffer = generate_request_pdf(service_request)
    return send_file(buffer, download_name='Request_form.pdf', as_attachment=True)


@academic_services.route('/api/quotation/address', methods=['GET'])
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
    admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=service_request.sub_lab.code)).all()
    title_prefix = 'คุณ' if current_user.customer_info.type.type == 'บุคคล' else ''
    link = url_for("service_admin.generate_quotation", request_id=request_id, menu='quotation',
                   _external=True, _scheme=scheme)
    customer_name = service_request.customer.customer_name.replace(' ', '_')
    contact_email = current_user.contact_email if current_user.contact_email else current_user.email
    if admins:
        title = f'''[{service_request.request_no}] ใบคำขอรับบริการ - {title_prefix}{customer_name} ({service_request.quotation_address.name}) | แจ้งขอใบเสนอราคา'''
        message = f'''เรียน เจ้าหน้าที่{service_request.sub_lab.sub_lab}\n\n'''
        message += f'''ใบคำขอบริการเลขที่ : {service_request.request_no}\n'''
        message += f'''ลูกค้า : {service_request.customer.customer_name}\n'''
        message += f'''ในนาม : {service_request.quotation_address.name}\n'''
        message += f'''ที่รอการดำเนินการจัดทำใบเสนอราคา\n'''
        message += f'''กรุณาตรวจสอบและดำเนินการได้ที่ลิงก์ด้านล่าง\n'''
        message += f'''{link}\n\n'''
        message += f'''ผู้ประสานงาน\n'''
        message += f'''{service_request.customer.customer_name}\n'''
        message += f'''เบอร์โทร {service_request.customer.contact_phone_number}\n\n'''
        message += f'''ระบบงานบริการวิชาการ'''
        send_mail([a.admin.email + '@mahidol.ac.th' for a in admins if not a.is_supervisor or not a.is_central_admin],
                  title, message)
        msg = ('แจ้งขอใบเสนอราคา' \
               '\n\nเรียน เจ้าหน้าที่{}'
               '\n\nใบคำขอบริการเลขที่ {}' \
               '\nลูกค้า : {}' \
               '\nในนาม : {}' \
               '\nที่รอการดำเนินการออกใบเสนอราคา' \
               '\nกรุณาตรวจสอบและดำเนินการได้ที่ลิงก์ด้านล่าง' \
               '\n{}' \
               '\n\nผู้ประสานงาน' \
               '\n{}' \
               '\nเบอร์โทร {}' \
               '\n\nระบบงานบริการวิชาการ'.format(service_request.sub_lab.sub_lab, service_request.request_no,
                                                 service_request.customer.customer_name,
                                                 service_request.quotation_address.name, link,
                                                 service_request.customer.customer_name,
                                                 service_request.customer.contact_phone_number)
               )
        if not current_app.debug:
            for a in admins:
                if not a.is_supervisor or not a.is_central_admin:
                    try:
                        line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                    except LineBotApiError:
                        pass
    request_link = url_for("academic_services.view_request", request_id=request_id, menu='request',
                           _external=True, _scheme=scheme)
    title_for_customer = f'''แจ้งรับใบคำขอรับบริการ [{service_request.request_no}] – งานบริการตรวจวิเคราะห์ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
    message_for_customer = f'''เรียน {title_prefix}{current_user.customer_info.cus_name}\n\n'''
    message_for_customer += f'''ตามที่ท่านได้แจ้งความประสงค์ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล ขณะนี้ทางเจ้าหน้าที่ได้รับข้อมูลคำขอรับบริการเลขที่ {service_request.request_no}เป็นที่เรียบร้อยแล้ว'''
    message_for_customer += f'''ทางเจ้าหน้าที่จะพิจารณารายละเอียดและจัดทำใบเสนอราคาอย่างเป็นทางการต่อไป เมื่อใบเสนอราคาออกเรียบร้อยแล้ว ท่านจะได้รับอีเมลแจ้งอีกครั้งหนึ่ง พร้อมลิงก์สำหรับตรวจสอบและยืนยันใบเสนอราคา\n'''
    message_for_customer += f'''ท่านสามารถดูรายละเอียดใบคำขอรับบริการได้ที่ลิงก์ด้างล่างนี้\n'''
    message_for_customer += f'''{request_link}\n\n'''
    message_for_customer += f'''ขอขอบพระคุณที่ใช้บริการจากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล\n\n'''
    message_for_customer += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
    message_for_customer += f'''ขอแสดงความนับถือ\n'''
    message_for_customer += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
    message_for_customer += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
    send_mail([contact_email], title_for_customer, message_for_customer)
    flash('ส่งใบคำขอรับบริการสำเร็จ', 'send_request')
    return redirect(url_for('academic_services.request_index', menu=menu))


@academic_services.route('/customer/quotation/index')
@login_required
def quotation_index():
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    expire_time = arrow.now('Asia/Bangkok').shift(days=-1).datetime
    query = ServiceQuotation.query.filter(ServiceQuotation.request.has(customer_id=current_user.id),
                                          ServiceQuotation.approved_at != None)
    pending_count = query.filter(ServiceQuotation.confirmed_at == None, ServiceQuotation.cancelled_at == None).count()
    confirm_count = query.filter(ServiceQuotation.confirmed_at >= expire_time).count()
    cancel_count = query.filter(ServiceQuotation.cancelled_at >= expire_time).count()
    all_count = pending_count + confirm_count + cancel_count
    return render_template('academic_services/quotation_index.html', menu=menu, tab=tab, all_count=all_count,
                           pending_count=pending_count, cancel_count=cancel_count, confirm_count=confirm_count)


@academic_services.route('/api/quotation/index')
def get_quotations():
    tab = request.args.get('tab')
    query = ServiceQuotation.query.filter(ServiceQuotation.request.has(customer_id=current_user.id),
                                          ServiceQuotation.approved_at != None)
    if tab == 'pending':
        query = query.filter(ServiceQuotation.confirmed_at == None, ServiceQuotation.cancelled_at == None)
    elif tab == 'confirm':
        query = query.filter(ServiceQuotation.confirmed_at != None)
    elif tab == 'cancel':
        query = query.filter(ServiceQuotation.cancelled_at != None)
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


@academic_services.route('/quotation/view/<int:quotation_id>')
@login_required
def view_quotation(quotation_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    quotation = ServiceQuotation.query.get(quotation_id)
    return render_template('academic_services/view_quotation.html', quotation_id=quotation_id, menu=menu,
                           quotation=quotation, tab=tab)


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

    # lab_address = '''<para><font size=12>
    #                         {address}
    #                         </font></para>'''.format(address=lab.address if lab else sub_lab.address)

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

    n = len(items)

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
        Paragraph('<font size=12>{}</font>'.format(bahttext(quotation.grand_total)),
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
        Paragraph('<font size=12>{:,.2f}</font>'.format(quotation.grand_total), style=style_sheet['ThaiStyleNumber']),
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

    # document_address = '''<para><font size=12>ที่อยู่สำหรับจัดส่งเอกสาร<br/>
    #                 ถึง {name}<br/>
    #                 ที่อยู่ {address}<br/>
    #                 เบอร์โทรศัพท์ : {phone_number}<br/>
    #                 อีเมล : {email}
    #                 </font></para>
    #                 '''.format(name=quotation.request.receive_name,
    #                            address=quotation.request.receive_address,
    #                            phone_number=quotation.request.receive_phone_number,
    #                            email=quotation.request.customer.contact_email
    #                            )
    #
    # document_address_table = Table([[Paragraph(document_address, style=style_sheet['ThaiStyle'])]], colWidths=[200])

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
    # data.append(KeepTogether(document_address_table))
    # data.append(KeepTogether(Spacer(1, 3)))
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
    admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=quotation.request.sub_lab.code)).all()
    link = url_for('service_admin.view_quotation', menu='quotation', tab='all', quotation_id=quotation_id,
                   _external=True, _scheme=scheme)
    title_prefix = 'คุณ' if quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
    customer_name = quotation.customer_name.replace(' ', '_')
    if admins:
        title = f'''[{quotation.quotation_no}] ใบเสนอราคา - {title_prefix}{customer_name} ({quotation.name}) | แจ้งยืนยันใบเสนอราคา'''
        message = f'''เรียน เจ้าหน้าที่{quotation.request.sub_lab.sub_lab}่\n\n'''
        message += f'''ใบเสนอราคาเลขที่ {quotation.quotation_no}\n'''
        message += f'''ลูกค้า : {quotation.customer_name}\n'''
        message += f'''ในนาม : {quotation.name}\n'''
        message += f'''อ้างอิงจากใบคำขอรับบริการเลขที่ : {quotation.request.request_no}\n'''
        message += f'''ได้รับการยืนยันจากลูกค้าแล้ว\n'''
        message += f'''ท่านสามารถดูรายละเอียดได้ที่ลิงก์ด้านล่าง\n'''
        message += f'''{link}\n\n'''
        message += f'''ผู้ประสานงาน\n'''
        message += f'''{quotation.customer_name}\n'''
        message += f'''เบอร์โทร {quotation.request.customer.contact_phone_number}\n'''
        message += f'''ระบบบริการวิชาการ'''
        send_mail([a.admin.email + '@mahidol.ac.th' for a in admins if not a.is_central_admin], title, message)
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
        quotation.request.status_id = status_id
        db.session.add(quotation)
        db.session.commit()
        flash('ยกเลิกใบเสนอราคาสำเร็จ', 'success')
        admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=quotation.request.sub_lab.code)).all()
        title_prefix = 'คุณ' if quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
        customer_name = quotation.customer_name.replace(' ', '_')
        if admins:
            title = f'''[{quotation.quotation_no}] ใบเสนอราคา - {title_prefix}{customer_name} ({quotation.name}) | แจ้งปฏิเสธใบเสนอราคา'''
            message = f'''เรียน เจ้าหน้าที่{quotation.request.sub_lab.sub_lab}่\n\n'''
            message += f'''ใบเสนอราคาเลขที่ {quotation.quotation_no}\n'''
            message += f'''ลูกค้า : {quotation.customer_name}\n'''
            message += f'''ในนาม : {quotation.name}\n'''
            message += f'''อ้างอิงจากใบคำขอรับบริการเลขที่ : {quotation.request.request_no}\n'''
            message += f'''เหตุผลที่ปฏิเสธ : {quotation.reason or ''}'''
            if quotation.other:
                message += f'''รายละเอียดเพิ่มเติม : {quotation.other}'''
            message += f'''ได้รับการปฏิเสธจากลูกค้า\n'''
            message += f'''กรุณาตรวจสอบและดำเนินขั้นตอนที่เหมาะสมต่อไป\n\n'''
            message += f'''ผู้ประสานงาน\n'''
            message += f'''{quotation.customer_name}\n'''
            message += f'''เบอร์โทร {quotation.request.customer.contact_phone_number}\n'''
            message += f'''ระบบบริการวิชาการ'''
            send_mail([a.admin.email + '@mahidol.ac.th' for a in admins if not a.is_central_admin], title, message)
        resp = make_response()
        resp.headers['HX-Redirect'] = url_for('academic_services.quotation_index', menu=menu)
        return resp
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('academic_services/modal/reject_quotation_modal.html', form=form,
                           quotation_id=quotation_id, menu=menu, tab='cancel')


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
    address_type = address.address_type if address_id else None
    if not form.taxpayer_identification_no.data:
        form.taxpayer_identification_no.data = current_user.customer_info.taxpayer_identification_no
    if form.validate_on_submit():
        if address_id is None:
            address = ServiceCustomerAddress()
        form.populate_obj(address)
        if address_id is None:
            address.customer_id = current_user.customer_info.id
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
    return render_template('academic_services/modal/create_address_modal.html', address_id=address_id,
                           type=type, form=form, menu=menu, address_type=address_type)


@academic_services.route('/api/get_districts')
def get_districts():
    province_id = request.args.get('province_id')
    districts = District.query.filter_by(province_id=province_id).order_by(District.name).all()
    result = [{"id": d.id, "name": d.name} for d in districts]
    return jsonify(result)


@academic_services.route('/api/get_subdistricts')
def get_subdistricts():
    district_id = request.args.get('district_id')
    subdistricts = Subdistrict.query.filter_by(district_id=district_id).order_by(Subdistrict.name).all()
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
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    expire_time = arrow.now('Asia/Bangkok').shift(days=-1).datetime
    query = ServiceSample.query.filter(ServiceSample.request.has(customer_id=current_user.id))
    if tab == 'schedule':
        samples = query.filter(ServiceSample.appointment_date == None, ServiceSample.tracking_number == None,
                               ServiceSample.received_at == None)
    elif tab == 'delivery':
        samples = query.filter(or_(ServiceSample.appointment_date != None, ServiceSample.tracking_number != None),
                               ServiceSample.received_at == None)
    elif tab == 'received':
        samples = query.filter(ServiceSample.received_at != None)
    else:
        samples = query
    schedule_count = query.filter(ServiceSample.appointment_date == None, ServiceSample.tracking_number == None,
                                  ServiceSample.received_at == None).count()
    delivery_count = query.filter(or_(ServiceSample.appointment_date != None, ServiceSample.tracking_number != None),
                                  ServiceSample.received_at == None).count()
    received_count = query.filter(ServiceSample.received_at >= expire_time).count()
    all_count = schedule_count + delivery_count + received_count
    return render_template('academic_services/sample_index.html', samples=samples, menu=menu, tab=tab,
                           schedule_count=schedule_count, delivery_count=delivery_count, received_count=received_count,
                           all_count=all_count)


@academic_services.route('/customer/sample/add/<int:sample_id>', methods=['GET', 'POST'])
@login_required
def create_sample_appointment(sample_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    sample = ServiceSample.query.get(sample_id)
    service_request = ServiceRequest.query.get(sample.request_id)
    datas = request_data(service_request, type='form')
    form = ServiceSampleForm(obj=sample)
    admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=sample.request.sub_lab.code)).all()
    holidays = Holidays.query.all()
    if form.validate_on_submit():
        form.populate_obj(sample)
        if form.ship_type.data == 'ส่งทางไปรษณีย์':
            sample.appointment_date = None
            sample.location = None
            sample.location_name = None
        else:
            location = request.form.get('sample_address')
            if location == ('salaya_address'):
                sample.location = 'salaya'
                sample.location_name = 'คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล วิทยาเขตศาลายา'
            if location == ('siriraj_address'):
                sample.location = 'siriraj'
                sample.location_name = 'คณะเทคนิคการแพทย์ โรงพยาบาลศิริราช วิทยาเขตบางกอกน้อย'
            sample.appointment_date = arrow.get(form.appointment_date.data, 'Asia/Bangkok').date()
        db.session.add(sample)
        db.session.commit()
        scheme = 'http' if current_app.debug else 'https'
        title_prefix = 'คุณ' if service_request.customer.customer_info.type.type == 'บุคคล' else ''
        link = url_for("service_admin.sample_verification", sample_id=sample.id, menu=menu, tab='delivery',
                       _external=True, _scheme=scheme)
        customer_name = service_request.customer.customer_name.replace(' ', '_')
        if admins:
            if service_request.status.status_id == 9:
                title = f'''[{service_request.request_no}] นัดหมายส่งตัวอย่าง - {title_prefix}{customer_name} ({service_request.quotation_address.name}) | (แจ้งแก้ไขนัดหมายส่งตัวอย่าง)'''
                message = f'''เรียน เจ้าหน้าที่{service_request.sub_lab.sub_lab}\n\n'''
                message += f'''ใบคำขอรับบริการเลขที่ {service_request.request_no}\n'''
                message += f'''ลูกค้า : {service_request.customer.customer_name}\n'''
                message += f'''ในนาม : {service_request.quotation_address.name}\n'''
                message += f'''ได้ดำเนินการแก้ไขข้อมูลการนัดหมายส่งตัวอย่าง โดยมีรายละเอียดดังนี้\n'''
                message += f'''ใบเสนอราคา : {' , '.join(quotation.quotation_no for quotation in service_request.quotations)}\n'''
                if sample.appointment_date:
                    message += f'''วันที่นัดหมาย : {sample.appointment_date.strftime('%d/%m/%Y')}\n'''
                if sample.location:
                    message += f'''สถานที่นัดหมาย : {sample.location_name}\n'''
                    if sample.location == 'salaya':
                        message += f'''รายละเอียดสถานที่ : {service_request.sub_lab.salaya_address}\n'''
                    else:
                        message += f'''รายละเอียดสถานที่ : {service_request.sub_lab.siriraj_address}\n'''
                else:
                    message += f'''รายละเอียดสถานที่ : {service_request.sub_lab.address}\n'''
                message += f'''เบอร์โทรศัพท์ : {service_request.sub_lab.lab.phone_number}\n'''
                if service_request.sub_lab.lab.email:
                    message += f'''เบอร์โทรศัพท์ : {service_request.sub_lab.lab.email}\n'''
                message += f'''รูปแบบการจัดส่งตัวอย่าง : {sample.ship_type}\n\n'''
                message += f'''กรุณาตรวจสอบและดำเนินการได้ที่ลิงค์ด้านล่าง\n'''
                message += f'''{link}\n\n'''
                message += f'''ผู้ประสานงาน\n'''
                message += f'''{service_request.customer.customer_name}\n'''
                message += f'''เบอร์โทร {service_request.customer.contact_phone_number}\n'''
                message += f'''ระบบงานบริการวิชาการ'''
            else:
                title = f'''[{service_request.request_no}] นัดหมายส่งตัวอย่าง - {title_prefix}{customer_name} ({service_request.quotation_address.name}) | (แจ้งนัดหมายส่งตัวอย่าง)'''
                message = f'''เรียน เจ้าหน้าที่{service_request.sub_lab.sub_lab}\n\n'''
                message += f'''ใบคำขอรับบริการเลขที่ {service_request.request_no}\n'''
                message += f'''ลูกค้า : {service_request.customer.customer_name}\n'''
                message += f'''ในนาม : {service_request.quotation_address.name}\n'''
                message += f'''ได้ดำเนินการนัดหมายส่งตัวอย่าง โดยมีรายละเอียดดังนี้\n'''
                message += f'''ใบเสนอราคา : {' , '.join(quotation.quotation_no for quotation in service_request.quotations)}\n'''
                if sample.appointment_date:
                    message += f'''วันที่นัดหมาย : {sample.appointment_date.strftime('%d/%m/%Y')}\n'''
                if sample.location:
                    message += f'''สถานที่นัดหมาย : {sample.location_name}\n'''
                    if sample.location == 'salaya':
                        message += f'''รายละเอียดสถานที่ : {service_request.sub_lab.salaya_address}\n'''
                    else:
                        message += f'''รายละเอียดสถานที่ : {service_request.sub_lab.siriraj_address}\n'''
                else:
                    message += f'''รายละเอียดสถานที่ : {service_request.sub_lab.address}\n'''
                message += f'''เบอร์โทรศัพท์ : {service_request.sub_lab.lab.phone_number}\n'''
                if service_request.sub_lab.lab.email:
                    message += f'''เบอร์โทรศัพท์ : {service_request.sub_lab.lab.email}\n'''
                message += f'''รูปแบบการจัดส่งตัวอย่าง : {sample.ship_type}\n'''
                message += f'''กรุณาตรวจสอบและดำเนินการได้ที่ลิงค์ด้านล่าง\n'''
                message += f'''{link}\n\n'''
                message += f'''ผู้ประสานงาน\n'''
                message += f'''{service_request.customer.customer_name}\n'''
                message += f'''เบอร์โทร {service_request.customer.contact_phone_number}\n'''
                message += f'''ระบบงานบริการวิชาการ'''
            send_mail([a.admin.email + '@mahidol.ac.th' for a in admins if not a.is_central_admin], title, message)
        if service_request.status.status_id == 6:
            status_id = get_status(9)
            service_request.status_id = status_id
            db.session.add(service_request)
            db.session.commit()
        flash('อัพเดตข้อมูลสำเร็จ', 'success')
        return redirect(url_for('academic_services.confirm_sample_appointment_page', menu=menu, tab='delivery',
                                request_id=sample.request_id))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
        return render_template('academic_services/create_sample_appointment.html', form=form, menu=menu,
                               tab=tab, sample=sample, sample_id=sample_id, datas=datas,
                               service_request=service_request,
                               holidays=holidays)


@academic_services.route('/customer/sample-appointment/confirm/page/<int:request_id>', methods=['GET', 'POST'])
def confirm_sample_appointment_page(request_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    return render_template('academic_services/confirm_sample_appointment_page.html', request_id=request_id,
                           menu=menu, tab=tab)


@academic_services.route('/customer/sample/tracking_number/add/<int:sample_id>', methods=['GET', 'POST'])
def add_tracking_number(sample_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    sample = ServiceSample.query.get(sample_id)
    form = ServiceSampleForm(obj=sample)
    if form.validate_on_submit():
        form.populate_obj(sample)
        db.session.add(sample)
        db.session.commit()
        flash('อัพเดตข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('academic_services/modal/add_tracking_number_modal.html', form=form, menu=menu,
                           tab=tab, sample_id=sample_id)


@academic_services.route('/customer/sample/appointment/view/<int:sample_id>')
@login_required
def view_sample_appointment(sample_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    sample = ServiceSample.query.get(sample_id)
    return render_template('academic_services/view_sample_appointment.html', sample=sample, menu=menu,
                           tab=tab)


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


@academic_services.route('/customer/invoice/index')
@login_required
def invoice_index():
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    api = request.args.get('api', 'false')
    today = arrow.now('Asia/Bangkok').date()
    expire_time = arrow.now('Asia/Bangkok').shift(days=-1).datetime
    query = (
        ServiceInvoice.query
        .join(ServiceInvoice.quotation)
        .join(ServiceQuotation.request)
        .filter(
            ServiceInvoice.file_attached_at != None,
            ServiceRequest.customer_id == current_user.id
        )
    )
    pending_query = query.outerjoin(ServicePayment).filter(ServicePayment.invoice_id==None)

    for rec in pending_query:
        print(rec)
    print(f'pending count={pending_query.count()}')
    verify_query = query.join(ServicePayment).filter(ServicePayment.paid_at != None, ServicePayment.verified_at == None,
                                                     ServicePayment.cancelled_at == None)
    payment_query = query.join(ServicePayment).filter(ServicePayment.verified_at >= expire_time,
                                                      ServicePayment.cancelled_at == None)
    overdue_query = query.join(ServicePayment).filter(today > ServiceInvoice.due_date, ServicePayment.paid_at == None,
                                                      ServicePayment.cancelled_at == None)
    if api == 'true':
        if tab == 'pending':
            query = pending_query
        elif tab == 'verify':
            query = verify_query
        elif tab == 'payment':
            query = payment_query
        elif tab == 'overdue':
            query = overdue_query

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
            download_file = url_for('academic_services.download_file', key=item.file,
                                    download_filename=f"{item.invoice_no}.pdf")
            item_data['file'] = f'''<div class="field has-addons">
                             <div class="control">
                                 <a class="button is-small is-light is-link is-rounded" href="{download_file}">
                                     <span class="icon is-small"><i class="fas fa-file-invoice-dollar"></i></span>
                                     <span>ใบแจ้งหนี้</span>
                                 </a>
                             </div>
                         </div>
                     '''
            if item.payments:
                for payment in item.payments:
                    if payment.slip and payment.cancelled_at == None:
                        item_data['slip'] = generate_url(payment.slip)
                    else:
                        item_data['slip'] = None
            data.append(item_data)
        return jsonify({'data': data,
                        'recordFiltered': total_filtered,
                        'recordTotal': records_total,
                        'draw': request.args.get('draw', type=int)
                        })

    return render_template('academic_services/invoice_index.html', menu=menu, tab=tab,
                           pending_count=pending_query.count(), verify_count=verify_query.count(),
                           payment_count=payment_query.count(), overdue_count=overdue_query.count())


@academic_services.route('/api/invoice/index')
def get_invoices():
    tab = request.args.get('tab')
    today = arrow.now('Asia/Bangkok').date()
    query = (
        ServiceInvoice.query
        .join(ServiceInvoice.quotation)
        .join(ServiceQuotation.request)
        .filter(
            ServiceInvoice.file_attached_at != None,
            ServiceRequest.customer_id == current_user.id
        )
    )
    pending_query = query.join(ServicePayment).filter(
        ServicePayment.paid_at == None,
        today <= ServiceInvoice.due_date, ServicePayment.cancelled_at == None
    )
    if tab == 'pending':
        query = pending_query
    elif tab == 'verify':
        query = query.join(ServicePayment).filter(ServicePayment.paid_at != None, ServicePayment.verified_at == None,
                                                     ServicePayment.cancelled_at == None)
    elif tab == 'payment':
        query = query.join(ServicePayment).filter(ServicePayment.verified_at != None,
                                                     ServicePayment.cancelled_at == None)
    elif tab == 'overdue':
        query = query.join(ServicePayment).filter(today > ServiceInvoice.due_date, ServicePayment.paid_at == None,
                                                     ServicePayment.cancelled_at == None)
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
        download_file = url_for('academic_services.download_file', key=item.file,
                                download_filename=f"{item.invoice_no}.pdf")
        item_data['file'] = f'''<div class="field has-addons">
                        <div class="control">
                            <a class="button is-small is-light is-link is-rounded" href="{download_file}">
                                <span class="icon is-small"><i class="fas fa-file-invoice-dollar"></i></span>
                                <span>ใบแจ้งหนี้</span>
                            </a>
                        </div>
                    </div>
                '''
        if item.payments:
            for payment in item.payments:
                if payment.slip and payment.cancelled_at == None:
                    item_data['slip'] = generate_url(payment.slip)
                else:
                    item_data['slip'] = None
        data.append(item_data)
    return jsonify({'data': data,
                    'recordFiltered': total_filtered,
                    'recordTotal': records_total,
                    'draw': request.args.get('draw', type=int)
                    })


@academic_services.route('/customer/payment/add', methods=['GET', 'POST'])
def add_payment():
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    invoice_id = request.args.get('invoice_id')
    invoice = ServiceInvoice.query.get(invoice_id)
    form = ServicePaymentForm()
    if not form.amount_paid.data:
        form.amount_paid.data = invoice.grand_total
    if form.validate_on_submit():
        payment = ServicePayment()
        form.populate_obj(payment)
        status_id = get_status(21)
        file = form.file_upload.data
        if (file and form.paid_at.data and form.payment_type.data and form.amount_paid.data):
            payment.invoice_id = invoice_id
            payment.created_at = arrow.now('Asia/Bangkok').datetime
            payment.customer_id = current_user.id
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
                # invoice.paid_at = arrow.now('Asia/Bangkok').datetime
                invoice.quotation.request.status_id = status_id
                db.session.add(invoice)
                db.session.commit()
                scheme = 'http' if current_app.debug else 'https'
                org = Org.query.filter_by(name='หน่วยการเงินและบัญชี').first()
                staff = StaffAccount.get_account_by_email(org.head)
                title_prefix = 'คุณ' if current_user.customer_info.type.type == 'บุคคล' else ''
                link = url_for("service_admin.view_invoice_for_finance", invoice_id=invoice_id, _external=True,
                               _scheme=scheme)
                customer_name = invoice.customer_name.replace(' ', '_')
                title = f'''[{invoice.invoice_no}] ใบแจ้งหนี้ - {title_prefix}{customer_name} ({invoice.name}) | แจ้งอัปเดตการชำระเงิน'''
                message = f'''เรียน เจ้าหน้าที่การเงิน\n\n'''
                message += f'''ใบแจ้งหนี้เลขที่ {invoice.invoice_no} ของลูกค้า {invoice.customer_name}\n'''
                message += f'''ในนาม {invoice.name} จากหน่วยงาน {invoice.quotation.request.sub_lab.sub_lab}\n'''
                message += f'''จำนวนเงิน {invoice.grand_total:,.2f} บาท ได้มีการอัปเดตสถานะการชำระเงินเรียบร้อยแล้ว \n'''
                message += f'''กรุณาตรวจสอบรายละเอียดการชำระเงินได้ที่ลิงก์ด้านล่าง\n'''
                message += f'''{link}\n\n'''
                message += f'''ผู้ประสานงาน\n'''
                message += f'''{invoice.customer_name}\n'''
                message += f'''เบอร์โทร {invoice.contact_phone_number}\n\n'''
                message += f'''ระบบงานบริการวิชาการ'''
                send_mail([staff.email + '@mahidol.ac.th'], title, message)
                msg = (f'แจ้งอัพเดตการชำระเงินใบแจ้งหนี้เลขที่ {invoice.invoice_no}\n\n'
                       f'เรียน เจ้าหน้าที่การเงิน\n\n'
                       f'ใบแจ้งหนี้เลขที่ {invoice.invoice_no} ของลูกค้า {invoice.customer_name}\n'
                       f'ในนาม {invoice.name} จากหน่วยงาน {invoice.quotation.request.sub_lab.sub_lab}\n'
                       f'จำนวนเงิน {invoice.grand_total:,.2f} บาท ได้มีการอัปเดตสถานะการชำระเงินเรียบร้อยแล้ว \n'
                       f'กรุณาตรวจสอบรายละเอียดการชำระเงินได้ที่ลิงก์ด้านล่าง\n'
                       f'{link}\n\n'
                       f'ผู้ประสานงาน\n'
                       f'{invoice.customer_name}\n'
                       f'เบอร์โทร {invoice.contact_phone_number}\n\n'
                       f'ระบบงานบริการวิชาการ'
                       )
                if not current_app.debug:
                    try:
                        line_bot_api.push_message(to=staff.line_id, messages=TextSendMessage(text=msg))
                    except LineBotApiError:
                        pass
            flash('อัปโหลดหลักฐานการชำระเงินสำเร็จ', 'success')
            return redirect(url_for('academic_services.invoice_index', menu=menu, tab='verify'))
        else:
            flash('กรุณากรอกวันที่ชำระเงิน, วิธีการชำระเงิน, จำนวนเงิน และหลักฐานการชำระเงิน', 'danger')
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('academic_services/add_payment.html', menu=menu, form=form, invoice=invoice, tab=tab)


@academic_services.route('/invoice/view/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    invoice = ServiceInvoice.query.get(invoice_id)
    return render_template('academic_services/view_invoice.html', invoice_id=invoice_id, menu=menu,
                           tab=tab, invoice=invoice)


def generate_invoice_pdf(invoice, sign=False, cancel=False):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 60, 60)

    lab = ServiceLab.query.filter_by(code=invoice.quotation.request.lab).first()
    sub_lab = ServiceSubLab.query.filter_by(code=invoice.quotation.request.lab).first()

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

    # lab_address = '''<para><font size=12>
    #                         {address}
    #                         </font></para>'''.format(address=lab.address if lab else sub_lab.address)

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

    issued_date = arrow.get(invoice.mhesi_issued_at.astimezone(localtz)).format(fmt='DD MMMM YYYY',
                                                                                locale='th-th') if invoice.mhesi_issued_at else None
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

    n = len(items)

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
        Paragraph('<font size=12>{:,.2f}</font>'.format(invoice.subtotal()), style=style_sheet['ThaiStyleNumber']),
    ])

    items.append([
        Paragraph('<font size=12>{}</font>'.format(bahttext(invoice.grand_total)),
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
        Paragraph('<font size=12>{:,.2f}</font>'.format(invoice.grand_total), style=style_sheet['ThaiStyleNumber']),
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
    status_id = get_status(23)
    service_request = ServiceRequest.query.get(request_id)
    service_request.status_id = status_id
    db.session.add(service_request)
    db.session.commit()
    flash('ยกเลิกคำขอรับบริการสำเร็จ', 'success')
    return redirect(url_for('academic_services.request_index', menu=menu))


@academic_services.route('/edit/academic-service-form', methods=['GET'])
def edit_request_form():
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet(service_request.sub_lab.sheet)
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


@academic_services.route('/api/receipt/index')
def get_receipts():
    query = ServiceInvoice.query.filter(ServiceInvoice.receipts != None, ServiceInvoice.quotation.has(
        ServiceQuotation.request.has(customer_id=current_user.id)))
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


@academic_services.route('/customer/result/index')
@login_required
def result_index():
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    expire_time = arrow.now('Asia/Bangkok').shift(days=-1).datetime
    query = ServiceResult.query.join(ServiceResult.request).filter(ServiceRequest.customer_id == current_user.id)

    if tab == 'pending':
        results = query.filter(ServiceResult.sent_at == None)
    elif tab == 'edit':
        results = query.filter(ServiceResult.result_edit_at != None, ServiceResult.is_edited == False)
    elif tab == 'approve':
        results = query.filter(ServiceResult.sent_at != None, ServiceResult.approved_at == None,
                               or_(ServiceResult.result_edit_at == None, ServiceResult.is_edited == True
                                   )
                               )
    elif tab == 'confirm':
        results = query.filter(ServiceResult.approved_at != None)
    else:
        results = query
    pending_count = query.filter(ServiceResult.sent_at == None).count()
    edit_count = query.filter(ServiceResult.result_edit_at != None, ServiceResult.is_edited == False).count()
    approve_count = query.filter(ServiceResult.sent_at != None, ServiceResult.approved_at == None,
                                 or_(ServiceResult.result_edit_at == None, ServiceResult.is_edited == True
                                     )
                                 ).count()
    confirm_count = query.filter(ServiceResult.approved_at >= expire_time).count()
    all_count = edit_count + approve_count + pending_count + confirm_count
    return render_template('academic_services/result_index.html', results=results, menu=menu,
                           tab=tab, edit_count=edit_count, approve_count=approve_count, confirm_count=confirm_count,
                           all_count=all_count, pending_count=pending_count)


@academic_services.route('/customer/result/view/<int:result_id>/<int:result_item_id>', methods=['GET', 'POST'])
def view_result_item(result_id, result_item_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    result = ServiceResult.query.get(result_id)
    result_item = next((i for i in result.result_items if i.id == result_item_id), None)
    if not result_item:
        flash('ไม่พบรายการผล', 'danger')
        return redirect(url_for('academic_services.result_index', menu=menu, tab=tab))
    return render_template('academic_services/view_result_item.html', result=result, result_item=result_item,
                           menu=menu, tab=tab, generate_url=generate_url, result_item_id=result_item_id)


@academic_services.route('/customer/result/confirm/<int:result_id>', methods=['GET', 'POST'])
def confirm_result(result_id):
    menu = request.args.get('menu')
    status_id = get_status(13)
    result = ServiceResult.query.get(result_id)
    result.status_id = status_id
    result.approver_id = current_user.id
    result.approved_at = arrow.now('Asia/Bangkok').datetime
    result.request.status_id = status_id
    db.session.add(result)
    db.session.commit()
    scheme = 'http' if current_app.debug else 'https'
    admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=result.request.sub_lab.code)).all()
    title_prefix = 'คุณ' if current_user.customer_info.type.type == 'บุคคล' else ''
    link = url_for("service_admin.create_invoice", quotation_id=result.quotation_id, menu='invoice',
                   _external=True, _scheme=scheme)
    customer_name = result.request.customer.customer_name.replace(' ', '_')
    if admins:
        title = f'''[{result.request.request_no}] ใบรายงานผลการทดสอบ - {title_prefix}{customer_name} ({result.request.quotation_address.name}) | แจ้งยืนยันใบรายงานผลการทดสอบ'''
        message = f'''เรียน เจ้าหน้าที่{result.request.sub_lab.sub_lab}\n\n'''
        message += f'''ใบรายงานผลของใบคำขอรับบริการเลขที่ : {result.request.request_no}\n'''
        message += f'''ลูกค้า : {result.request.customer.customer_name}\n'''
        message += f'''ในนาม : {result.request.quotation_address.name}\n'''
        message += f'''ได้ดำเนินการยืนยันเรียบร้อยแล้ว\n'''
        message += f'''กรุณาดำเนินการออกใบแจ้งหนี้ได้ที่ลิงก์ด้านล่าง\n'''
        message += f'''{link}\n\n'''
        message += f'''ผู้ประสานงาน\n'''
        message += f'''{result.request.customer.customer_name}\n'''
        message += f'''เบอร์โทร {result.request.customer.contact_phone_number}\n\n'''
        message += f'''ระบบงานบริการวิชาการ'''
        send_mail([a.admin.email + '@mahidol.ac.th' for a in admins if not a.is_central_admin], title, message)
        msg = ('แจ้งยืนยันใบรายงานผลการทดสอบ' \
               '\n\nเรียน เจ้าหน้าที่{}'
               '\n\nใบรายงานผลของใบคำขอรับบริการเลขที่ {}' \
               '\nลูกค้า : {}' \
               '\nในนาม : {}' \
               '\nได้ดำเนินการยืนยันเรียบร้อยแล้ว' \
               '\nกรุณาดำเนินการออกใบแจ้งหนี้ได้ที่ลิงก์ด้านล่าง' \
               '\n{}' \
               '\n\nผู้ประสานงาน' \
               '\n{}' \
               '\nเบอร์โทร {}' \
               '\n\nระบบงานบริการวิชาการ'.format(result.request.sub_lab.sub_lab, result.request.request_no,
                                                 result.request.customer.customer_name,
                                                 result.request.quotation_address.name, link,
                                                 result.request.customer.customer_name,
                                                 result.request.customer.contact_phone_number)
               )
        if not current_app.debug:
            for a in admins:
                if not a.is_central_admin:
                    try:
                        line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                    except LineBotApiError:
                        pass
    flash('ยืนยันใบรายงานผลเรียบร้อยแล้ว', 'success')
    return redirect(url_for('academic_services.result_index', menu=menu))


@academic_services.route('/customer/result/edit/<int:result_id>', methods=['GET', 'POST'])
def edit_result(result_id):
    menu = request.args.get('menu')
    result = ServiceResult.query.get(result_id)
    form = ServiceResultForm(obj=result)
    if form.validate_on_submit():
        form.populate_obj(result)
        status_id = get_status(14)
        result.status_id = status_id
        result.edit_requester_id = current_user.id
        result.result_edit_at = arrow.now('Asia/Bangkok').datetime
        result.request.status_id = status_id
        db.session.add(result)
        db.session.commit()
        scheme = 'http' if current_app.debug else 'https'
        admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=result.request.sub_lab.code)).all()
        title_prefix = 'คุณ' if current_user.customer_info.type.type == 'บุคคล' else ''
        link = url_for("service_admin.create_draft_result", rresult_id=result.id, request_id=result.request.id,
                       menu='test_item', _external=True, _scheme=scheme)
        customer_name = result.request.customer.customer_name.replace(' ', '_')
        if admins:
            title = f'''[{result.request.request_no}] ใบรายงานผลการทดสอบ - {title_prefix}{customer_name} ({result.request.quotation_address.name}) | แจ้งขอแก้ไขใบรายงานผลการทดสอบ'''
            message = f'''เรียน เจ้าหน้าที่{result.request.sub_lab.sub_lab}\n\n'''
            message += f'''ใบรายงานผลของใบคำขอรับบริการเลขที่ : {result.request.request_no}\n'''
            message += f'''ลูกค้า : {result.request.customer.customer_name}\n'''
            message += f'''ในนาม : {result.request.quotation_address.name}\n'''
            message += f'''ได้ขอดำเนินการแก้ไขรายงานผลการทดสอบเนื่องจาก {result.note}\n'''
            message += f'''กรุณาดำเนินการแก้ไขรายงานผลการทดสอบได้ที่ลิงก์ด้านล่าง\n'''
            message += f'''{link}\n\n'''
            message += f'''ผู้ประสานงาน\n'''
            message += f'''{result.request.customer.customer_name}\n'''
            message += f'''เบอร์โทร {result.request.customer.contact_phone_number}\n\n'''
            message += f'''ระบบงานบริการวิชาการ'''
            send_mail([a.admin.email + '@mahidol.ac.th' for a in admins if not a.is_central_admin], title, message)
            msg = ('แจ้งขอแก้ไขใบรายงานผลการทดสอบ' \
                   '\n\nเรียน เจ้าหน้าที่{}'
                   '\n\nใบรายงานผลของใบคำขอรับบริการเลขที่ {}' \
                   '\nลูกค้า : {}' \
                   '\nในนาม : {}' \
                   '\nได้ขอดำเนินการแก้ไขรายงานผลการทดสอบเนื่องจาก {}' \
                   '\nกรุณาดำเนินการแก้ไขรายงานผลการทดสอบได้ที่ลิงก์ด้านล่าง' \
                   '\n{}' \
                   '\n\nผู้ประสานงาน' \
                   '\n{}' \
                   '\nเบอร์โทร {}' \
                   '\n\nระบบงานบริการวิชาการ'.format(result.request.sub_lab.sub_lab, result.request.request_no,
                                                     result.request.customer.customer_name,
                                                     result.request.quotation_address.name, result.note, link,
                                                     result.request.customer.customer_name,
                                                     result.request.customer.contact_phone_number)
                   )
            if not current_app.debug:
                for a in admins:
                    if not a.is_central_admin:
                        try:
                            line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                        except LineBotApiError:
                            pass
        flash('ส่งคำขอแก้ไขเรียบร้อยแล้ว', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('academic_services/modal/edit_result_modal.html', form=form, result_id=result_id, menu=menu)


@academic_services.route('/customer/result_item/confirm/<int:result_item_id>', methods=['GET', 'POST'])
def confirm_result_item(result_item_id):
    menu = request.args.get('menu')
    result_item = ServiceResultItem.query.get(result_item_id)
    result = ServiceResult.query.get(result_item.result_id)
    result_item.approver_id = current_user.id
    result_item.approved_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(result_item)
    approved_all = all(item.approved_at is not None for item in result.result_items)
    tab = 'confirm' if approved_all else 'approve'
    db.session.add(result_item)
    db.session.commit()
    if approved_all:
        status_id = get_status(13)
        result_item.result.status_id = status_id
        result_item.result.request.status_id = status_id
        result_item.result.approved_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(result_item)
        db.session.commit()
        scheme = 'http' if current_app.debug else 'https'
        admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=result_item.result.request.sub_lab.code)).all()
        title_prefix = 'คุณ' if current_user.customer_info.type.type == 'บุคคล' else ''
        link = url_for("service_admin.create_invoice", quotation_id=result_item.result.quotation_id, menu='invoice',
                       tab='draft', _external=True, _scheme=scheme)
        customer_name = result_item.result.request.customer.customer_name.replace(' ', '_')
        if admins:
            title = f'''[{result_item.result.request.request_no}] ใบรายงานผลการทดสอบ - {title_prefix}{customer_name} ({result_item.result.request.quotation_address.name}) | แจ้งยืนยันใบรายงานผลการทดสอบ'''
            message = f'''เรียน เจ้าหน้าที่{result_item.result.request.sub_lab.sub_lab}\n\n'''
            message += f'''ใบรายงานผลฉบับร่างของใบคำขอรับบริการเลขที่ : {result_item.result.request.request_no}\n'''
            message += f'''ลูกค้า : {result_item.result.request.customer.customer_name}\n'''
            message += f'''ในนาม : {result_item.result.request.quotation_address.name}\n'''
            message += f'''ได้ดำเนินการยืนยันเรียบร้อยแล้ว\n'''
            message += f'''กรุณาดำเนินการออกใบแจ้งหนี้ได้ที่ลิงก์ด้านล่าง\n'''
            message += f'''{link}\n\n'''
            message += f'''ผู้ประสานงาน\n'''
            message += f'''{result_item.result.request.customer.customer_name}\n'''
            message += f'''เบอร์โทร {result_item.result.request.customer.contact_phone_number}\n\n'''
            message += f'''ระบบงานบริการวิชาการ'''
            send_mail([a.admin.email + '@mahidol.ac.th' for a in admins if not a.is_central_admin], title, message)
            msg = ('แจ้งยืนยันใบรายงานผลการทดสอบ' \
                   '\n\nเรียน เจ้าหน้าที่{}'
                   '\n\nใบรายงานผลฉบับร่างของใบคำขอรับบริการเลขที่ {}' \
                   '\nลูกค้า : {}' \
                   '\nในนาม : {}' \
                   '\nได้ดำเนินการยืนยันเรียบร้อยแล้ว' \
                   '\nกรุณาดำเนินการออกใบแจ้งหนี้ได้ที่ลิงก์ด้านล่าง' \
                   '\n{}' \
                   '\n\nผู้ประสานงาน' \
                   '\n{}' \
                   '\nเบอร์โทร {}' \
                   '\n\nระบบงานบริการวิชาการ'.format(result_item.result.request.sub_lab.sub_lab,
                                                     result_item.result.request.request_no,
                                                     result_item.result.request.customer.customer_name,
                                                     result_item.result.request.quotation_address.name, link,
                                                     result_item.result.request.customer.customer_name,
                                                     result_item.result.request.customer.contact_phone_number)
                   )
            if not current_app.debug:
                for a in admins:
                    if not a.is_central_admin:
                        try:
                            line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                        except LineBotApiError:
                            pass
    flash('ยืนยันใบรายงานผลเรียบร้อยแล้ว', 'success')
    return redirect(url_for('academic_services.result_index', menu=menu, tab=tab))


@academic_services.route('/customer/result_item/edit/<int:result_item_id>', methods=['GET', 'POST'])
def edit_result_item(result_item_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    result_item = ServiceResultItem.query.get(result_item_id)
    result_item.is_edited = False
    result_item.edit_requester_id = None
    result_item.req_edit_at = None
    result_item.note = None
    db.session.add(result_item)
    db.session.commit()
    result = ServiceResult.query.get(result_item.result_id)
    form = ServiceResultItemForm(obj=result_item)
    if form.validate_on_submit():
        form.populate_obj(result_item)
        status_id = get_status(14)
        result_item.result.status_id = status_id
        result_item.edit_requester_id = current_user.id
        result_item.req_edit_at = arrow.now('Asia/Bangkok').datetime
        result_item.result.request.status_id = status_id
        result_item.result.result_edit_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(result_item)
        db.session.commit()
        scheme = 'http' if current_app.debug else 'https'
        admins = ServiceAdmin.query.filter(ServiceAdmin.sub_lab.has(code=result.request.sub_lab.code)).all()
        title_prefix = 'คุณ' if current_user.customer_info.type.type == 'บุคคล' else ''
        link = url_for("service_admin.create_draft_result", rresult_id=result.id, request_id=result.request.id,
                       menu='test_item', _external=True, _scheme=scheme)
        customer_name = result_item.result.request.customer.customer_name.replace(' ', '_')
        if admins:
            title = f'''[{result_item.result.request.request_no}] ใบรายงานผลการทดสอบ - {title_prefix}{customer_name} ({result_item.result.request.quotation_address.name}) | แจ้งขอแก้ไขใบรายงานผลการทดสอบ'''
            message = f'''เรียน เจ้าหน้าที่{result.request.sub_lab.sub_lab}\n\n'''
            message += f'''{result_item.report_language}ฉบับร่างของใบคำขอรับบริการเลขที่ : {result.request.request_no}\n'''
            message += f'''ลูกค้า : {result.request.customer.customer_name}\n'''
            message += f'''ในนาม : {result.request.quotation_address.name}\n'''
            message += f'''ได้ขอดำเนินการแก้ไขรายงานผลการทดสอบเนื่องจาก {result.note}\n'''
            message += f'''กรุณาดำเนินการแก้ไขรายงานผลการทดสอบได้ที่ลิงก์ด้านล่าง\n'''
            message += f'''{link}\n\n'''
            message += f'''ผู้ประสานงาน\n'''
            message += f'''{result.request.customer.customer_name}\n'''
            message += f'''เบอร์โทร {result.request.customer.contact_phone_number}\n\n'''
            message += f'''ระบบงานบริการวิชาการ'''
            send_mail([a.admin.email + '@mahidol.ac.th' for a in admins if not a.is_central_admin], title, message)
            msg = ('แจ้งขอแก้ไขใบรายงานผลการทดสอบ' \
                   '\n\nเรียน เจ้าหน้าที่{}'
                   '\n\n{}ฉบับร่างของใบคำขอรับบริการเลขที่ {}' \
                   '\nลูกค้า : {}' \
                   '\nในนาม : {}' \
                   '\nได้ขอดำเนินการแก้ไขรายงานผลการทดสอบเนื่องจาก {}' \
                   '\nกรุณาดำเนินการแก้ไขรายงานผลการทดสอบได้ที่ลิงก์ด้านล่าง' \
                   '\n{}' \
                   '\n\nผู้ประสานงาน' \
                   '\n{}' \
                   '\nเบอร์โทร {}' \
                   '\n\nระบบงานบริการวิชาการ'.format(result.request.sub_lab.sub_lab, result_item.report_language,
                                                     result.request.request_no,
                                                     result.request.customer.customer_name,
                                                     result.request.quotation_address.name, result_item.note, link,
                                                     result.request.customer.customer_name,
                                                     result.request.customer.contact_phone_number)
                   )
            if not current_app.debug:
                for a in admins:
                    if not a.is_central_admin:
                        try:
                            line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                        except LineBotApiError:
                            pass
        flash('ส่งคำขอแก้ไขเรียบร้อยแล้ว', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('academic_services/modal/edit_result_modal.html', form=form, result_item_id=result_item_id,
                           menu=menu, tab=tab)
