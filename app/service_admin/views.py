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

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from sqlalchemy.orm import make_transient
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
from app.auth.views import line_bot_api
from app.academic_services.forms import *
from app.e_sign_api import e_sign
from app.models import Org
from app.scb_payment_service.views import generate_qrcode
from app.service_admin import service_admin
from flask import render_template, flash, redirect, url_for, request, session, make_response, jsonify, current_app, \
    send_file
from flask_login import current_user, login_required, login_user
from sqlalchemy import or_, update, and_
from app.service_admin.forms import *
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
pdfmetrics.registerFont(TTFont('DejaVuSans', 'app/static/fonts/DejaVuSans.ttf'))
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


def sort_quotation_item(items):
    if 'สำเนา' in items.item:
        priority = 2
    elif 'ใบรายงานผล' in items.item:
        priority = 1
    else:
        priority = 0
    return (priority, items.id)


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
                clean_field_name = re.sub(r'_\d+$', '', field_name)
                if clean_field_name in quote_column_names:
                    if isinstance(f.data, list):
                        for item in f.data:
                            keys.append((field_name, values + str(item)))
                    else:
                        keys.append((field_name, values + str(f.data)))
    else:
        clean_field_name = re.sub(r'_\d+$', '', field.name)
        if clean_field_name in quote_column_names:
            if field.name != 'csrf_token' or field.name != 'submit':
                if isinstance(field.data, list):
                    for item in field.data:
                        keys.append((field.name, values + str(item)))
                else:
                    keys.append((field.name, values + str(field.data)))
    return keys


# def request_data(service_request, type):
#     data = service_request.data
#     if service_request.sub_lab.code == 'bacteria':
#         form = BacteriaRequestForm(data=data)
#     elif service_request.sub_lab.code == 'disinfection':
#         form = VirusDisinfectionRequestForm(data=data)
#     elif service_request.sub_lab.code == 'air_disinfection':
#         form = VirusAirDisinfectionRequestForm(data=data)
#     else:
#         form = ''
#     values = []
#     set_fields = set()
#     product_header = False
#     test_header = False
#     for field in form:
#         if field.type == 'FormField':
#             if not test_header:
#                 values.append({'type': 'header', 'data': 'รายการทดสอบ'})
#                 test_header = True
#             if not any([f.data for f in field._fields.values() if f.type != 'HiddenField' and f.type != 'FieldList']):
#                 continue
#             for fname, fn in field._fields.items():
#                 if fn.type == 'FieldList':
#                     rows = []
#                     for entry in fn.entries:
#                         row = {}
#                         for f_name, f in entry._fields.items():
#                             if f.data and f.label not in set_fields:
#                                 set_fields.add(f.label)
#                                 label = f.label.text
#                                 if label.startswith("เชื้อ"):
#                                     data = ', '.join(f.data) if isinstance(f.data, list) else str(f.data or '')
#                                     if type == 'form':
#                                         row[label] = f"<i>{data}</i>"
#                                     else:
#                                         row[label] = f"<font name='SarabunItalic'>{data}</font>"
#                                 else:
#                                     row[label] = f.data
#                         if row:
#                             rows.append(row)
#                     if rows:
#                         values.append({'type': 'table', 'data': rows})
#                 else:
#                     if fn.data and fn.label not in set_fields:
#                         set_fields.add(fn.label)
#                         label = fn.label.text
#                         value = ', '.join(fn.data) if fn.type == 'CheckboxField' else fn.data
#                         if fn.type == 'HiddenField':
#                             values.append({'type': 'content_header', 'data': f"{value}"})
#                         else:
#                             values.append({'type': 'text', 'data': f"{label} : {value}"})
#         else:
#             if not product_header:
#                 values.append({'type': 'header', 'data': 'ข้อมูลผลิตภัณฑ์'})
#                 product_header = True
#             if field.data and field.label not in set_fields:
#                 set_fields.add(field.label)
#                 label = field.label.text
#                 value = ', '.join(f.data) if field.type == 'CheckboxField' else field.data
#                 values.append({'type': 'text', 'data': f"{label} : {value}"})
#     return values


def bacteria_request_data(service_request, type):
    data = service_request.data
    form = BacteriaRequestForm(data=data)
    values = []
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
                            if f.data:
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
                    if fn.data:
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
            if field.data:
                label = field.label.text
                if field.type == 'CheckboxField':
                    value = ', '.join(field.data)
                    values.append({'type': 'text', 'data': f"{label} : {value}"})
                elif field.type == 'BooleanField':
                    values.append({'type': 'bool', 'data': f"{label}"})
                else:
                    value = field.data
                    values.append({'type': 'text', 'data': f"{label} : {value}"})
    return values


def virus_disinfection_request_data(service_request, type):
    data = service_request.data
    form = VirusDisinfectionRequestForm(data=data)
    values = []
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
                            if f.data:
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
                    if fn.data:
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
            if field.data:
                label = field.label.text
                if field.type == 'CheckboxField':
                    value = ', '.join(field.data)
                    values.append({'type': 'text', 'data': f"{label} : {value}"})
                elif field.type == 'BooleanField':
                    values.append({'type': 'bool', 'data': f"{label}"})
                elif field.name == 'note':
                    values.append({'type': 'remark', 'data': f"{field.data}"})
                else:
                    value = field.data
                    values.append({'type': 'text', 'data': f"{label} : {value}"})
    return values


def virus_air_disinfection_request_data(service_request, type):
    data = service_request.data
    form = VirusAirDisinfectionRequestForm(data=data)
    values = []
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
                            if f.data:
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
                    if fn.data:
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
            if field.data:
                label = field.label.text
                if field.type == 'CheckboxField':
                    value = ', '.join(field.data)
                    values.append({'type': 'text', 'data': f"{label} : {value}"})
                elif field.type == 'BooleanField':
                    values.append({'type': 'bool', 'data': f"{label}"})
                elif field.name == 'note':
                    values.append({'type': 'remark', 'data': f"{field.data}"})
                else:
                    value = field.data
                    values.append({'type': 'text', 'data': f"{label} : {value}"})
    return values


def heavymetal_request_data(service_request, type):
    data = service_request.data
    form = HeavyMetalRequestForm(data=data)
    values = []
    product_header = False
    test_header = False
    for field in form:
        if field.type == 'FieldList':
            if not test_header:
                values.append({'type': 'header', 'data': 'รายการทดสอบ'})
                test_header = True
            rows = []
            for fd in field:
                row = {}
                for f_name, f in fd._fields.items():
                    if f.type != 'CSRFTokenField':
                        label = f.label.text
                        if f.type == 'CheckboxField':
                            row[label] = ', '.join(f.data) if f.data else ''
                        else:
                            row[label] = f.data if f.data else ''

                rows.append(row)
            values.append({'type': 'table', 'data': rows})
        else:
            if not product_header:
                values.append({'type': 'header', 'data': 'ข้อมูลผลิตภัณฑ์'})
                product_header = True
            if field.data:
                label = field.label.text
                value = ', '.join(field.data) if field.type == 'CheckboxField' else field.data
                values.append({'type': 'text', 'data': f"{label} : {value}"})
    return values


def foodsafety_request_data(service_request, type):
    data = service_request.data
    form = FoodSafetyRequestForm(data=data)
    values = []
    product_header = False
    test_header = False
    for field in form:
        if field.type == 'FieldList':
            if not test_header:
                values.append({'type': 'header', 'data': 'รายการทดสอบ'})
                test_header = True
            rows = []
            for fd in field:
                row = {}
                for f_name, f in fd._fields.items():
                    if f.type != 'CSRFTokenField':
                        label = f.label.text
                        if f.type == 'CheckboxField':
                            row[label] = ', '.join(f.data) if f.data else ''
                        else:
                            row[label] = f.data if f.data else ''

                rows.append(row)
            values.append({'type': 'table', 'data': rows})
        else:
            if not product_header:
                values.append({'type': 'header', 'data': 'ข้อมูลผลิตภัณฑ์'})
                product_header = True
            if field.data:
                label = field.label.text
                value = ', '.join(field.data) if field.type == 'CheckboxField' else field.data
                values.append({'type': 'text', 'data': f"{label} : {value}"})
    return values


def protein_identification_request_data(service_request, type):
    data = service_request.data
    form = ProteinIdentificationRequestForm(data=data)
    values = []
    product_header = False
    test_header = False
    for field in form:
        if field.type == 'FieldList':
            if not test_header:
                values.append({'type': 'header', 'data': 'รายการทดสอบ'})
                test_header = True
            rows = []
            for fd in field:
                row = {}
                for f_name, f in fd._fields.items():
                    label = f.label.text
                    if label != 'CSRF Token':
                        if f.type == 'CheckboxField':
                            row[label] = ', '.join(f.data) if f.data else ''
                        else:
                            row[label] = f.data if f.data is not None else ''
                rows.append(row)
            values.append({'type': 'table', 'data': rows})
        else:
            if not product_header:
                values.append({'type': 'header', 'data': 'ข้อมูลผลิตภัณฑ์'})
                product_header = True
            if field.data:
                label = field.label.text
                value = ', '.join(field.data) if field.type == 'CheckboxField' else field.data
                values.append({'type': 'text', 'data': f"{label} : {value}"})
    return values


def sds_page_request_data(service_request, type):
    data = service_request.data
    form = SDSPageRequestForm(data=data)
    values = []
    product_header = False
    test_header = False
    for field in form:
        if field.type == 'FieldList':
            if not test_header:
                values.append({'type': 'header', 'data': 'รายการทดสอบ'})
                test_header = True
            rows = []
            for fd in field:
                row = {}
                for f_name, f in fd._fields.items():
                    label = f.label.text
                    if label != 'CSRF Token':
                        if f.type == 'CheckboxField':
                            row[label] = ', '.join(f.data) if f.data else ''
                        else:
                            row[label] = f.data if f.data is not None else ''
                rows.append(row)
            values.append({'type': 'table', 'data': rows})
        else:
            if not product_header:
                values.append({'type': 'header', 'data': 'ข้อมูลผลิตภัณฑ์'})
                product_header = True
            if field.data:
                label = field.label.text
                value = ', '.join(field.data) if field.type == 'CheckboxField' else field.data
                values.append({'type': 'text', 'data': f"{label} : {value}"})
    return values


def quantitative_request_data(service_request, type):
    data = service_request.data
    form = QuantitativeRequestForm(data=data)
    values = []
    product_header = False
    test_header = False
    for field in form:
        if field.type == 'FieldList':
            if not test_header:
                values.append({'type': 'header', 'data': 'รายการทดสอบ'})
                test_header = True
            rows = []
            for fd in field:
                row = {}
                for f_name, f in fd._fields.items():
                    label = f.label.text
                    if label != 'CSRF Token':
                        if f.type == 'CheckboxField':
                            row[label] = ', '.join(f.data) if f.data else ''
                        else:
                            row[label] = f.data if f.data is not None else ''
                rows.append(row)
            values.append({'type': 'table', 'data': rows})
        else:
            if not product_header:
                values.append({'type': 'header', 'data': 'ข้อมูลผลิตภัณฑ์'})
                product_header = True
            if field.data:
                label = field.label.text
                value = ', '.join(field.data) if field.type == 'CheckboxField' else field.data
                values.append({'type': 'text', 'data': f"{label} : {value}"})
    return values


def metabolomic_request_data(service_request, type):
    data = service_request.data
    form = MetabolomicRequestForm(data=data)
    values = []
    product_header = False
    test_header = False
    for field in form:
        if field.type == 'FieldList':
            if not test_header:
                values.append({'type': 'header', 'data': 'รายการทดสอบ'})
                test_header = True
            rows = []
            for fd in field:
                row = {}
                for f_name, f in fd._fields.items():
                    label = f.label.text
                    if label != 'CSRF Token':
                        if f.type == 'CheckboxField':
                            row[label] = ', '.join(f.data) if f.data else ''
                        else:
                            row[label] = f.data if f.data is not None else ''
                rows.append(row)
            values.append({'type': 'table', 'data': rows})
        else:
            if not product_header:
                values.append({'type': 'header', 'data': 'ข้อมูลผลิตภัณฑ์'})
                product_header = True
            if field.data:
                label = field.label.text
                value = ', '.join(field.data) if field.type == 'CheckboxField' else field.data
                values.append({'type': 'text', 'data': f"{label} : {value}"})
    return values


def endotoxin_request_data(service_request, type):
    data = service_request.data
    form = EndotoxinRequestForm(data=data)
    values = []
    product_header = False
    test_header = False
    for field in form:
        if field.type == 'FieldList':
            if not test_header:
                values.append({'type': 'header', 'data': 'รายการทดสอบ'})
                test_header = True
            rows = []
            for fd in field:
                row = {}
                for f_name, f in fd._fields.items():
                    label = f.label.text
                    if label != 'CSRF Token':
                        if f.type == 'CheckboxField':
                            row[label] = ', '.join(f.data) if f.data else ''
                        else:
                            row[label] = f.data if f.data is not None else ''
                rows.append(row)
            values.append({'type': 'table', 'data': rows})
        else:
            if not product_header:
                values.append({'type': 'header', 'data': 'ข้อมูลผลิตภัณฑ์'})
                product_header = True
            if field.data:
                label = field.label.text
                value = ', '.join(field.data) if field.type == 'CheckboxField' else field.data
                values.append({'type': 'text', 'data': f"{label} : {value}"})
    return values


def toxicology_request_data(service_request, type):
    data = service_request.data
    form = ToxicologyRequestForm(data=data)
    values = []
    product_header = False
    test_header = False
    for field in form:
        if field.type == 'FieldList':
            if not test_header:
                values.append({'type': 'header', 'data': 'รายการทดสอบ'})
                test_header = True
            rows = []
            for fd in field:
                row = {}
                for f_name, f in fd._fields.items():
                    label = f.label.text
                    if label != 'CSRF Token':
                        if f.type == 'CheckboxField':
                            row[label] = ', '.join(f.data) if f.data else ''
                        else:
                            row[label] = f.data if f.data is not None else ''
                rows.append(row)
            values.append({'type': 'table', 'data': rows})
        else:
            if not product_header:
                values.append({'type': 'header', 'data': 'ข้อมูลผลิตภัณฑ์'})
                product_header = True
            if field.data:
                label = field.label.text
                value = ', '.join(field.data) if field.type == 'CheckboxField' else field.data
                values.append({'type': 'text', 'data': f"{label} : {value}"})
    return values


request_data_paths = {'bacteria': bacteria_request_data,
                      'disinfection': virus_disinfection_request_data,
                      'air_disinfection': virus_air_disinfection_request_data,
                      'heavymetal': heavymetal_request_data,
                      'foodsafety': foodsafety_request_data,
                      'protein_identification': protein_identification_request_data,
                      'sds_page': sds_page_request_data,
                      'quantitative': quantitative_request_data,
                      'metabolomic': metabolomic_request_data,
                      'endotoxin': endotoxin_request_data,
                      'toxicology': toxicology_request_data
                      }


@service_admin.route('/')
# @login_required
def index():
    return render_template('service_admin/index.html')


@service_admin.context_processor
def menu():
    admin = False
    supervisor = False
    assistant = False
    central_admin = False
    request_count = None
    quotation_count = None
    sample_count = None
    test_item_count = None
    invoice_count = None
    report_count = None
    invoice_count_for_central_admin = None
    position = None
    if current_user.is_authenticated:
        admins = ServiceAdmin.query.filter_by(admin_id=current_user.id).first()
        if admins and admins.is_assistant:
            assistant = True
            position = 'Assistant of dean'
        elif admins and admins.is_supervisor:
            supervisor = True
            position = 'Supervisor'
        elif admins and admins.is_central_admin:
            central_admin = True
            position = 'Central Admin'
        else:
            admin = True
            position = 'Admin'

        request_count = (ServiceRequest.query
        .join(ServiceRequest.status)
        .join(ServiceRequest.sub_lab)
        .join(ServiceSubLab.admins)
        .filter(
            ServiceStatus.status_id.in_([2, 24]),
            ServiceAdmin.admin_id == current_user.id
        )).count()
        quotation_count = (ServiceRequest.query
        .join(ServiceRequest.status)
        .join(ServiceRequest.sub_lab)
        .join(ServiceSubLab.admins)
        .filter(
            ServiceStatus.status_id.in_([3, 4, 5]),
            ServiceAdmin.admin_id == current_user.id
        )).count()
        sample_count = (ServiceRequest.query
        .join(ServiceRequest.status)
        .join(ServiceRequest.sub_lab)
        .join(ServiceSubLab.admins)
        .filter(
            ServiceStatus.status_id.in_([6, 8, 9]),
            ServiceAdmin.admin_id == current_user.id
        )
        ).count()
        test_item_count = (ServiceTestItem.query
        .join(ServiceTestItem.request)
        .join(ServiceRequest.sub_lab)
        .join(ServiceSubLab.admins)
        .outerjoin(ServiceResult)
        .filter(
            ServiceAdmin.admin_id == current_user.id, or_(ServiceResult.request_id == None,
                                                          ServiceResult.approved_at == None)
        )
        ).count()
        invoice_count = (ServiceRequest.query
        .join(ServiceRequest.status)
        .join(ServiceRequest.sub_lab)
        .join(ServiceSubLab.admins)
        .filter(
            ServiceStatus.status_id.in_([16, 17, 18, 19, 20]),
            ServiceAdmin.admin_id == current_user.id
        )).count()
        invoice_count_for_central_admin = (ServiceRequest.query
        .join(ServiceRequest.status)
        .join(ServiceRequest.sub_lab)
        .join(ServiceSubLab.admins)
        .filter(
            ServiceStatus.status_id.in_([19, 20]),
            ServiceAdmin.admin_id == current_user.id
        )).count()
        report_count = (
            ServiceResult.query
            .join(ServiceResult.request)
            .join(ServiceRequest.sub_lab)
            .join(ServiceSubLab.admins)
            .filter(
                ServiceResult.approved_at == None,
                ServiceAdmin.admin_id == current_user.id
            )
        ).count()
    return dict(admin=admin, supervisor=supervisor, assistant=assistant, central_admin=central_admin, position=position,
                request_count=request_count, quotation_count=quotation_count, sample_count=sample_count,
                test_item_count=test_item_count, invoice_count=invoice_count, report_count=report_count,
                invoice_count_for_central_admin=invoice_count_for_central_admin)


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
        account = ServiceCustomerAccount.query.filter_by(customer_info_id=customer_id).first()
        form = ServiceCustomerInfoForm(obj=customer)
    else:
        account = None
        form = ServiceCustomerInfoForm()
    if form.validate_on_submit():
        if customer_id is None:
            customer = ServiceCustomerInfo()
        form.populate_obj(customer)
        if customer_id is None:
            customer.creator_id = current_user.id
            account = ServiceCustomerAccount(email=form.email.data, customer_info=customer,
                                             verify_datetime=arrow.now('Asia/Bangkok').datetime)
        else:
            account.email = form.email.data
        # if request.form.getlist('verify_email'):
        #     account.verify_datetime = arrow.now('Asia/Bangkok').datetime
        # else:
        #     account.verify_datetime = None
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
                           form=form, account=account)


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
        if a.is_assistant:
            assistant = True
        elif a.is_supervisor:
            supervisor = True
        else:
            admin = True
        sub_labs.append(a.sub_lab.code)

    ids = list(range(2, 23))
    ids.append(24)

    status_groups = {
        'all': {
            'id': ids,
            'name': 'รายการทั้งหมด',
            'icon': '<i class="fas fa-list-ul"></i>'
        },
        'create_quotation': {
            'id': [2, 3, 4, 5, 24],
            'name': 'รอออก/ยืนยันใบเสนอราคา',
            'color': 'is-info',
            'icon': '<i class="fas fa-file-invoice"></i>'
        },
        'received_sample': {
            'id': [6, 8, 9],
            'name': 'รอรับตัวอย่าง',
            'color': 'is-info',
            'icon': '<i class="fas fa-people-carry"></i>'
        },
        'waiting_test': {
            'id': [10],
            'name': 'รอทดสอบตัวอย่าง',
            'color': 'is-info',
            'icon': '<i class="fas fa-vial"></i>'
        },
        # 'waiting_report': {
        #     'id': [11, 12, 14, 15],
        #     'name': 'รอออกใบรายงานผล',
        #     'color': 'is-info',
        #     'icon': '<i class="fas fa-file-alt"></i>'
        # },
        'create_invoice': {
            'id': [13, 16, 17, 18, 19],
            'name': 'รอออก/ยืนยันใบแจ้งหนี้',
            'color': 'is-info',
            'icon': '<i class="fas fa-file-invoice-dollar"></i>'
        },
        'wait_payment': {
            'id': [20, 21],
            'name': 'รอชำระเงิน',
            'color': 'is-info',
            'icon': '<i class="fas fa-money-check-alt"></i>'
        },
        'confirm_payment': {
            'id': [22],
            'name': 'ชำระเงินสำเร็จ',
            'color': 'is-light',
            'icon': '<i class="fas fa-check"></i>'
        }
    }

    for key, group in status_groups.items():
        group_ids = [i for i in group['id'] if i != 7]
        query = (
            ServiceRequest.query
            .join(ServiceRequest.status)
            .join(ServiceRequest.sub_lab)
            .join(ServiceSubLab.admins)
            .filter(
                ServiceStatus.status_id.in_(group_ids),
                ServiceAdmin.admin_id == current_user.id
            )
        ).count()

        status_groups[key]['count'] = query
    return render_template('service_admin/request_index.html', menu=menu, admin=admin,
                           supervisor=supervisor, assistant=assistant, status_groups=status_groups)


@service_admin.route('/api/request/index')
def get_requests():
    query = (
        ServiceRequest.query
        .join(ServiceRequest.status)
        .join(ServiceRequest.sub_lab)
        .join(ServiceSubLab.admins)
        .filter(
            ServiceStatus.status_id.notin_([1, 23]),
            ServiceAdmin.admin_id == current_user.id

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


# @service_admin.route('/request/add/<int:customer_id>', methods=['GET'])
# @service_admin.route('/request/edit/<int:request_id>', methods=['GET'])
# @login_required
# def create_request(request_id=None, customer_id=None):
#     code = request.args.get('code')
#     sub_lab = ServiceSubLab.query.filter_by(code=code)
#     return render_template('service_admin/create_request.html', code=code, request_id=request_id,
#                            customer_id=customer_id, sub_lab=sub_lab)
#

# @service_admin.route('/api/request/form', methods=['GET'])
# def get_request_form():
#     code = request.args.get('code')
#     request_id = request.args.get('request_id')
#     service_request = ServiceRequest.query.get(request_id)
#     sub_lab = ServiceSubLab.query.filter_by(code=code).first() if code else ServiceSubLab.query.filter_by(
#         code=service_request.sub_lab.code).first()
#     sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
#     print('Authorizing with Google..')
#     gc = get_credential(json_keyfile)
#     wks = gc.open_by_key(sheetid)
#     sheet = wks.worksheet(sub_lab.sheet)
#     df = pandas.DataFrame(sheet.get_all_records())
#     if request_id:
#         data = service_request.data
#         form = create_request_form(df)(**data)
#     else:
#         form = create_request_form(df)()
#     template = ''
#     for f in form:
#         template += str(f)
#     return template
#
#
# @service_admin.route('/submit-request/add/<int:customer_id>', methods=['POST'])
# @service_admin.route('/submit-request/edit/<int:request_id>', methods=['POST'])
# def submit_request(request_id=None, customer_id=None):
#     if request_id:
#         service_request = ServiceRequest.query.get(request_id)
#         sub_lab = ServiceSubLab.query.filter_by(code=service_request.sub_lab.code).first()
#     else:
#         code = request.args.get('code')
#         sub_lab = ServiceSubLab.query.filter_by(code=code).first()
#         request_no = ServiceNumberID.get_number('RQ', db,
#                                                 lab=sub_lab.lab.code if sub_lab and sub_lab.lab.code == 'protein' else code)
#     sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
#     gc = get_credential(json_keyfile)
#     wks = gc.open_by_key(sheetid)
#     sheet = wks.worksheet(sub_lab.sheet)
#     df = pandas.DataFrame(sheet.get_all_records())
#     form = create_request_form(df)(request.form)
#     products = []
#     for _, values in form.data.items():
#         if isinstance(values, dict):
#             if 'product_name' in values:
#                 products.append(values['product_name'])
#             elif 'ware_name' in values:
#                 products.append(values['ware_name'])
#             elif 'sample_name' in values:
#                 products.append(values['sample_name'])
#             elif 'รายการ' in values:
#                 for v in values['รายการ']:
#                     if 'sample_name' in v:
#                         products.append(v['sample_name'])
#             elif 'test_sample_of_trace' in values:
#                 products.append(values['test_sample_of_trace'])
#             elif 'test_sample_of_heavy' in values:
#                 products.append(values['test_sample_of_heavy'])
#     if request_id:
#         service_request.data = format_data(form.data)
#         service_request.modified_at = arrow.now('Asia/Bangkok').datetime
#         service_request.product = products
#     else:
#         service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id,
#                                          created_at=arrow.now('Asia/Bangkok').datetime, lab=code,
#                                          request_no=request_no.number,
#                                          product=products, data=format_data(form.data))
#         request_no.count += 1
#     db.session.add(service_request)
#     db.session.commit()
#     return redirect(url_for('service_admin.create_report_language', request_id=service_request.id,
#                             code=service_request.sub_lab.code))

@service_admin.route('/portal/request')
def create_request():
    menu = request.args.get('menu')
    code = request.args.get('code')
    request_id = request.args.get('request_id')
    customer_id = request.args.get('customer_id')
    request_paths = {'bacteria': 'service_admin.create_bacteria_request',
                     'disinfection': 'service_admin.create_virus_disinfection_request',
                     'air_disinfection': 'service_admin.create_virus_air_disinfection_request',
                     'heavymetal': 'service_admin.create_heavy_metal_request',
                     'foodsafety': 'service_admin.create_food_safety_request',
                     'protein_identification': 'service_admin.create_protein_identification_request',
                     'sds_page': 'service_admin.create_sds_page_request',
                     'quantitative': 'service_admin.create_quantitative_request',
                     'metabolomic': 'service_admin.create_metabolomic_request',
                     'endotoxin': 'service_admin.create_endotoxin_request',
                     'toxicology': 'service_admin.create_toxicology_request'
                     }
    return redirect(url_for(request_paths[code], code=code, menu=menu, request_id=request_id, customer_id=customer_id))


@service_admin.route('/request/bacteria/add', methods=['GET', 'POST'])
@service_admin.route('/request/bacteria/edit/<int:request_id>', methods=['GET', 'POST'])
def create_bacteria_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    customer_id = request.args.get('customer_id')
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
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(2)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id, status_id=status_id,
                                             created_at=arrow.now('Asia/Bangkok').datetime, sub_lab=sub_lab,
                                             request_no=request_no.number, data=format_data(form.data))
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('service_admin.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('service_admin/forms/bacteria_request_form.html', code=code, sub_lab=sub_lab,
                           menu=menu, form=form, request_id=request_id)


@service_admin.route("/request/collect_sample_during_testing")
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


@service_admin.route('/request/bacteria/condition')
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
    return render_template('service_admin/partials/bacteria_request_condition_form.html', fields=fields)


@service_admin.route('/request/virus_disinfection/add', methods=['GET', 'POST'])
@service_admin.route('/request/virus_disinfection/edit/<int:request_id>', methods=['GET', 'POST'])
def create_virus_disinfection_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    customer_id = request.args.get('customer_id')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = VirusDisinfectionRequestForm(data=data)
    else:
        form = VirusDisinfectionRequestForm()
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(2)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id, status_id=status_id,
                                             created_at=arrow.now('Asia/Bangkok').datetime, sub_lab=sub_lab,
                                             request_no=request_no.number, data=format_data(form.data))
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(url_for('service_admin.create_report_language', request_id=service_request.id, menu=menu,
                                code=code))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('service_admin/forms/virus_disinfection_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@service_admin.route("/request/product_storage")
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


@service_admin.route('/request/virus_disinfection/condition')
def get_virus_disinfection_condition_form():
    product_type = request.args.get("product_type")
    if not product_type:
        return ''
    form = VirusDisinfectionRequestForm()
    field_name = f"{product_type}_condition_field"
    fields = getattr(form, field_name)
    return render_template('service_admin/partials/virus_disinfection_request_condition_form.html',
                           fields=fields, product_type=product_type)


@service_admin.route('/request/virus_liquid_organism_form_entry/add', methods=['POST'])
def add_virus_liquid_organism_form_entry():
    form = VirusDisinfectionRequestForm()
    form.liquid_condition_field.liquid_organism_fields.append_entry()
    item_form = form.liquid_condition_field.liquid_organism_fields[-1]
    template = """
        <tr>
            <td style="border: none">
                <div class="select">{}</div>
            </td>
            <td style="border: none">{}</td>
            <td style="border: none">{}</td>
            <td style="border: none">
                <a class="button is-danger is-outlined"
                    hx-delete="{}" 
                    hx-target="closest tr"
                    hx-swap="outerHTML"
                >
                    <span class="icon"><i class="fas fa-trash-alt"></i></span>
                </a>
            </td>
        </tr>
    """
    resp = template.format(item_form.liquid_organism(),
                           item_form.liquid_ratio(class_='input'),
                           item_form.liquid_time_duration(class_='input', required=True,
                                                          oninvalid="this.setCustomValidity('กรุณากรอกข้อมูล')",
                                                          oninput="this.setCustomValidity('')"),
                           url_for('service_admin.remove_virus_liquid_organism_form_entry', name=item_form.name)
                           )
    resp = make_response(resp)
    return resp


@service_admin.route('/request/virus_liquid_organism_form_entry/remove', methods=['DELETE'])
def remove_virus_liquid_organism_form_entry():
    field_name = request.args.get('name')
    form = VirusDisinfectionRequestForm()
    temp_entries = []
    for entry in form.liquid_condition_field.liquid_organism_fields:
        if entry.name != field_name:
            temp_entries.append(entry)
    while len(form.liquid_condition_field.liquid_organism_fields) > 0:
        form.liquid_condition_field.liquid_organism_fields.pop_entry()
    for entry in temp_entries:
        form.liquid_condition_field.liquid_organism_fields.append_entry(entry)
    return ""


@service_admin.route('/request/virus_spray_organism_form_entry/add', methods=['POST'])
def add_virus_spray_organism_form_entry():
    form = VirusDisinfectionRequestForm()
    form.spray_condition_field.spray_organism_fields.append_entry()
    item_form = form.spray_condition_field.spray_organism_fields[-1]
    template = """
        <tr>
            <td style="border: none">
                <div class="select">{}</div>
            </td>
            <td style="border: none">{}</td>
            <td style="border: none">{}</td>
            <td style="border: none">{}</td>
            <td style="border: none">{}</td>
            <td style="border: none">
                <a class="button is-danger is-outlined"
                    hx-delete="{}" 
                    hx-target="closest tr"
                    hx-swap="outerHTML"
                >
                    <span class="icon"><i class="fas fa-trash-alt"></i></span>
                </a>
            </td>
        </tr>
    """
    resp = template.format(item_form.spray_organism(),
                           item_form.spray_ratio(class_='input'),
                           item_form.spray_distance(class_='input', required=True,
                                                    oninvalid="this.setCustomValidity('กรุณากรอกข้อมูล')",
                                                    oninput="this.setCustomValidity('')"),
                           item_form.spray_of_time(class_='input', required=True,
                                                   oninvalid="this.setCustomValidity('กรุณากรอกข้อมูล')",
                                                   oninput="this.setCustomValidity('')"),
                           item_form.spray_time_duration(class_='input', required=True,
                                                         oninvalid="this.setCustomValidity('กรุณากรอกข้อมูล')",
                                                         oninput="this.setCustomValidity('')"),
                           url_for('service_admin.remove_virus_spray_organism_form_entry', name=item_form.name)
                           )
    resp = make_response(resp)
    return resp


@service_admin.route('/request/virus_spray_organism_form_entry/remove', methods=['DELETE'])
def remove_virus_spray_organism_form_entry():
    field_name = request.args.get('name')
    form = VirusDisinfectionRequestForm()
    temp_entries = []
    for entry in form.spray_condition_field.spray_organism_fields:
        if entry.name != field_name:
            temp_entries.append(entry)
    while len(form.spray_condition_field.spray_organism_fields) > 0:
        form.spray_condition_field.spray_organism_fields.pop_entry()
    for entry in temp_entries:
        form.spray_condition_field.spray_organism_fields.append_entry(entry)
    return ""


@service_admin.route('/request/virus_coat_organism_form_entry/add', methods=['POST'])
def add_virus_coat_organism_form_entry():
    form = VirusDisinfectionRequestForm()
    form.coat_condition_field.coat_organism_fields.append_entry()
    item_form = form.coat_condition_field.coat_organism_fields[-1]
    template = """
        <tr>
            <td style="border: none">
                <div class="select">{}</div>
            </td>
            <td style="border: none">{}</td>
            <td style="border: none">
                <a class="button is-danger is-outlined"
                    hx-delete="{}" 
                    hx-target="closest tr"
                    hx-swap="outerHTML"
                >
                    <span class="icon"><i class="fas fa-trash-alt"></i></span>
                </a>
            </td>
        </tr>
    """
    resp = template.format(item_form.coat_organism(),
                           item_form.coat_time_duration(class_='input', required=True,
                                                        oninvalid="this.setCustomValidity('กรุณากรอกข้อมูล')",
                                                        oninput="this.setCustomValidity('')"),
                           url_for('service_admin.remove_virus_coat_organism_form_entry', name=item_form.name)
                           )
    resp = make_response(resp)
    return resp


@service_admin.route('/request/virus_coat_organism_form_entry/remove', methods=['DELETE'])
def remove_virus_coat_organism_form_entry():
    field_name = request.args.get('name')
    form = VirusDisinfectionRequestForm()
    temp_entries = []
    for entry in form.coat_condition_field.coat_organism_fields:
        if entry.name != field_name:
            temp_entries.append(entry)
    while len(form.coat_condition_field.coat_organism_fields) > 0:
        form.coat_condition_field.coat_organism_fields.pop_entry()
    for entry in temp_entries:
        form.coat_condition_field.coat_organism_fields.append_entry(entry)
    return ""


@service_admin.route('/request/virus_air_disinfection/add', methods=['GET', 'POST'])
@service_admin.route('/request/virus_air_disinfection/edit/<int:request_id>', methods=['GET', 'POST'])
def create_virus_air_disinfection_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    customer_id = request.args.get('customer_id')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = VirusAirDisinfectionRequestForm(data=data)
    else:
        form = VirusAirDisinfectionRequestForm()

    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(2)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id, status_id=status_id,
                                             created_at=arrow.now('Asia/Bangkok').datetime, sub_lab=sub_lab,
                                             request_no=request_no.number, data=format_data(form.data))
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(url_for('service_admin.create_report_language', request_id=service_request.id, menu=menu,
                                code=code))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('service_admin/forms/virus_air_disinfection_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, request_id=request_id, menu=menu)


@service_admin.route('/request/virus_surface_disinfection_organism_form_entry/add', methods=['POST'])
def add_virus_surface_disinfection_organism_form_entry():
    form = VirusAirDisinfectionRequestForm()
    form.surface_disinfection_condition_field.surface_disinfection_organism_fields.append_entry()
    item_form = form.surface_disinfection_condition_field.surface_disinfection_organism_fields[-1]
    template = """
        <tr>
            <td style="border: none">
                <div class="select">{}</div>
            </td>
            <td style="border: none">{}</td>
            <td style="border: none">
                <a class="button is-danger is-outlined"
                    hx-delete="{}" 
                    hx-target="closest tr"
                    hx-swap="outerHTML"
                >
                    <span class="icon"><i class="fas fa-trash-alt"></i></span>
                </a>
            </td>
        </tr>
    """
    resp = template.format(item_form.surface_disinfection_organism(),
                           item_form.surface_disinfection_period_test(class_='input', required=True,
                                                                      oninvalid="this.setCustomValidity('กรุณากรอกข้อมูล')",
                                                                      oninput="this.setCustomValidity('')"),
                           url_for('service_admin.remove_virus_surface_disinfection_organism_form_entry',
                                   name=item_form.name)
                           )
    resp = make_response(resp)
    return resp


@service_admin.route('/request/virus_surface_disinfection_organism_form_entry/remove', methods=['DELETE'])
def remove_virus_surface_disinfection_organism_form_entry():
    field_name = request.args.get('name')
    form = VirusAirDisinfectionRequestForm()
    temp_entries = []
    for entry in form.surface_disinfection_condition_field.surface_disinfection_organism_fields:
        if entry.name != field_name:
            temp_entries.append(entry)
    while len(form.surface_disinfection_condition_field.surface_disinfection_organism_fields) > 0:
        form.surface_disinfection_condition_field.surface_disinfection_organism_fields.pop_entry()
    for entry in temp_entries:
        form.surface_disinfection_condition_field.surface_disinfection_organism_fields.append_entry(entry)
    return ""


@service_admin.route('/request/condition/remove', methods=['GET', 'POST'])
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


@service_admin.route('/request/heavy_metal/add', methods=['GET', 'POST'])
@service_admin.route('/request/heavy_metal/edit/<int:request_id>', methods=['GET', 'POST'])
def create_heavy_metal_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    customer_id = request.args.get('customer_id')
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
            status_id = get_status(2)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id, status_id=status_id,
                                             created_at=arrow.now('Asia/Bangkok').datetime, sub_lab=sub_lab,
                                             request_no=request_no.number, data=format_data(form.data))
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('service_admin.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('service_admin/forms/heavy_metal_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@service_admin.route('/api/request/heavy_metal/item/add', methods=['POST'])
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
                    <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
                    <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
                    <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
                    <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
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


@service_admin.route('/api/request/heavy_metal/item/remove', methods=['DELETE'])
def remove_heavy_metal_condition_item():
    form = HeavyMetalRequestForm()
    form.heavy_metal_condition_field.pop_entry()
    resp = ''
    for i, item_form in enumerate(form.heavy_metal_condition_field, start=1):
        hr = '<hr style="background-color: #F3F3F3">' if i > 1 else ''
        template = """
            <div id="{}">
                {}
                <p><strong>รายการที่ {}</strong></p>
                <table class="table is-fullwidth ">
                    <thead>
                        <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
                        <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
                        <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
                        <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
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


@service_admin.route('/request/food_safety/add', methods=['GET', 'POST'])
@service_admin.route('/request/food_safety/edit/<int:request_id>', methods=['GET', 'POST'])
def create_food_safety_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    customer_id = request.args.get('customer_id')
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
            status_id = get_status(2)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id, status_id=status_id,
                                             created_at=arrow.now('Asia/Bangkok').datetime, sub_lab=sub_lab,
                                             request_no=request_no.number, data=format_data(form.data))
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('service_admin.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('service_admin/forms/food_safety_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@service_admin.route('/api/request/food_safety/item/add', methods=['POST'])
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
                    <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
                    <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
                    <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
                    <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
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


@service_admin.route('/api/request/food_safety/item/remove', methods=['DELETE'])
def remove_food_safety_condition_item():
    form = FoodSafetyRequestForm()
    form.food_safety_condition_field.pop_entry()
    resp = ''
    for i, item_form in enumerate(form.food_safety_condition_field, start=1):
        hr = '<hr style="background-color: #F3F3F3">' if i > 1 else ''
        template = """
            <div id="{}">
                {}
                <p><strong>รายการที่ {}</strong></p>
                <table class="table is-fullwidth ">
                    <thead>
                        <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
                        <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
                        <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
                        <th style="border: none">{}<span class="has-text-danger ml-1">*</span></th>
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


@service_admin.route("/request/objective")
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


@service_admin.route("/request/standard_limitation")
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


@service_admin.route("/request/other_service")
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
            <div class="field ml-4">
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


@service_admin.route('/request/protein_identification/add', methods=['GET', 'POST'])
@service_admin.route('/request/protein_identification/edit/<int:request_id>', methods=['GET', 'POST'])
def create_protein_identification_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    customer_id = request.args.get('customer_id')
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
            status_id = get_status(2)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id, status_id=status_id,
                                             created_at=arrow.now('Asia/Bangkok').datetime, sub_lab=sub_lab,
                                             request_no=request_no.number, data=format_data(form.data))
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('service_admin.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('service_admin/forms/protein_identification_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@service_admin.route('/api/request/protein_identification/item/add', methods=['POST'])
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
                    <th style="border: none">
                        {}
                        <span class="has-text-danger">*</span>
                    </th>
                    <th style="border: none">{}</th>
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
                           item_form.clean_up.label,
                           item_form.protein_identification.label,
                           item_form.sample_name(class_='input'),
                           item_form.clean_up(),
                           item_form.protein_identification()
                           )
    resp = make_response(resp)
    return resp


@service_admin.route('/api/request/protein_identification/item/remove', methods=['DELETE'])
def remove_protein_identification_condition_item():
    form = ProteinIdentificationRequestForm()
    form.protein_identification_condition_field.pop_entry()
    resp = ''
    for i, item_form in enumerate(form.protein_identification_condition_field, start=1):
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
                        <th style="border: none">{}</th>
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
                                item_form.clean_up.label,
                                item_form.protein_identification.label,
                                item_form.sample_name(class_='input'),
                                item_form.clean_up(),
                                item_form.protein_identification()
                                )
    resp = make_response(resp)
    return resp


@service_admin.route('/request/sds_page/add', methods=['GET', 'POST'])
@service_admin.route('/request/sds_page/edit/<int:request_id>', methods=['GET', 'POST'])
def create_sds_page_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    customer_id = request.args.get('customer_id')
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
            status_id = get_status(2)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id, status_id=status_id,
                                             created_at=arrow.now('Asia/Bangkok').datetime, sub_lab=sub_lab,
                                             request_no=request_no.number, data=format_data(form.data))
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('service_admin.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('service_admin/forms/sds_page_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@service_admin.route('/api/request/sds_page/item/add', methods=['POST'])
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
                    <th style="border: none">
                        {}
                        <span class="has-text-danger">*</span>
                    </th>
                    <th style="border: none">{}</th>
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
                           item_form.clean_up.label,
                           item_form.staining.label,
                           item_form.sample_name(class_='input'),
                           item_form.clean_up(),
                           item_form.staining()
                           )
    resp = make_response(resp)
    return resp


@service_admin.route('/api/request/sds_page/item/remove', methods=['DELETE'])
def remove_sds_page_condition_item():
    form = SDSPageRequestForm()
    form.sds_page_condition_field.pop_entry()
    resp = ''
    for i, item_form in enumerate(form.sds_page_condition_field, start=1):
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
                        <th style="border: none">{}</th>
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
                                item_form.clean_up.label,
                                item_form.staining.label,
                                item_form.sample_name(class_='input'),
                                item_form.clean_up(),
                                item_form.staining()
                                )
    resp = make_response(resp)
    return resp


@service_admin.route('/request/quantitative/add', methods=['GET', 'POST'])
@service_admin.route('/request/quantitative/edit/<int:request_id>', methods=['GET', 'POST'])
def create_quantitative_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    customer_id = request.args.get('customer_id')
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
            status_id = get_status(2)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id, status_id=status_id,
                                             created_at=arrow.now('Asia/Bangkok').datetime, sub_lab=sub_lab,
                                             request_no=request_no.number, data=format_data(form.data))
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('service_admin.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('service_admin/forms/quantitative_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@service_admin.route('/api/request/quantitative/item/add', methods=['POST'])
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


@service_admin.route('/api/request/quantitative/item/remove', methods=['DELETE'])
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


@service_admin.route('/request/metabolomic/add', methods=['GET', 'POST'])
@service_admin.route('/request/metabolomic/edit/<int:request_id>', methods=['GET', 'POST'])
def create_metabolomic_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    customer_id = request.args.get('customer_id')
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
            status_id = get_status(2)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id, status_id=status_id,
                                             created_at=arrow.now('Asia/Bangkok').datetime, sub_lab=sub_lab,
                                             request_no=request_no.number, data=format_data(form.data))
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('service_admin.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('service_admin/forms/metabolomic_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id)


@service_admin.route('/api/request/metabolomic/item/add', methods=['POST'])
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
                    <th style="border: none">
                        {}
                        <span class="has-text-danger">*</span>
                    </th>
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


@service_admin.route('/api/request/metabolomic/item/remove', methods=['DELETE'])
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
                        <th style="border: none">
                            {}
                            <span class="has-text-danger">*</span>
                        </th>
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


@service_admin.route("/request/sample_species_other")
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
            <div class="field ml-4">
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


@service_admin.route("/request/gel_slices_other")
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
            <div class="field ml-4">
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


@service_admin.route("/request/sample_type_other")
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
                <div class="field ml-4">
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


@service_admin.route('/request/endotoxin/add', methods=['GET', 'POST'])
@service_admin.route('/request/endotoxin/edit/<int:request_id>', methods=['GET', 'POST'])
def create_endotoxin_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    customer_id = request.args.get('customer_id')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = EndotoxinRequestForm(data=data)
    else:
        form = EndotoxinRequestForm()
    for item_form in form.endotoxin_condition_field:
        if not item_form.org_name.data:
            customer = ServiceCustomerAccount.query.get(customer_id)
            item_form.org_name.data = customer.customer_info.cus_name
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(2)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id, status_id=status_id,
                                             created_at=arrow.now('Asia/Bangkok').datetime, sub_lab=sub_lab,
                                             request_no=request_no.number, data=format_data(form.data))
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('service_admin.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('service_admin/forms/endotoxin_request_form.html', code=code, sub_lab=sub_lab,
                           form=form, menu=menu, request_id=request_id, customer_id=customer_id)


@service_admin.route('/api/request/endotoxin/item/add', methods=['POST'])
def add_endotoxin_condition_item():
    customer_id = request.args.get('customer_id')
    form = EndotoxinRequestForm()
    form.endotoxin_condition_field.append_entry()
    item_form = form.endotoxin_condition_field[-1]
    index = len(form.endotoxin_condition_field)
    customer = ServiceCustomerAccount.query.get(customer_id)
    item_form.org_name.data = customer.customer_info.cus_name
    template = """
        <div id="{}">
            <hr style="background-color: #F3F3F3">
            <p><strong>รายการที่ {}</strong></p>
            <table class="table is-fullwidth ">
                <thead>
                    <th style="border: none">{}
                        <span class="has-text-danger">*</span>
                    </th>
                    <th style="border: none">{}
                        <span class="has-text-danger">*</span>
                    </th>
                    <th style="border: none">{}
                        <span class="has-text-danger">*</span>
                    </th>
                    <th style="border: none">{}
                        <span class="has-text-danger">*</span>
                    </th>
                    <th style="border: none">{}
                        <span class="has-text-danger">*</span>
                    </th>
                    <th style="border: none">{}
                        <span class="has-text-danger">*</span>
                    </th>
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


@service_admin.route('/api/request/endotoxin/item/remove', methods=['DELETE'])
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
                        <th style="border: none">{}
                            <span class="has-text-danger">*</span>
                        </th>
                        <th style="border: none">{}
                            <span class="has-text-danger">*</span>
                        </th>
                        <th style="border: none">{}
                            <span class="has-text-danger">*</span>
                        </th>
                        <th style="border: none">{}
                            <span class="has-text-danger">*</span>
                        </th>
                        <th style="border: none">{}
                            <span class="has-text-danger">*</span>
                        </th>
                        <th style="border: none">{}
                            <span class="has-text-danger">*</span>
                        </th>
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


@service_admin.route('/request/toxicology/add', methods=['GET', 'POST'])
@service_admin.route('/request/toxicology/edit/<int:request_id>', methods=['GET', 'POST'])
def create_toxicology_request(request_id=None):
    menu = request.args.get('menu')
    code = request.args.get('code')
    customer_id = request.args.get('customer_id')
    sub_lab = ServiceSubLab.query.filter_by(code=code).first()
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        data = service_request.data
        form = ToxicologyRequestForm(data=data)
    else:
        form = ToxicologyRequestForm()
    if form.validate_on_submit():
        if request_id:
            service_request.data = format_data(form.data)
            service_request.modified_at = arrow.now('Asia/Bangkok').datetime
        else:
            status_id = get_status(2)
            request_no = ServiceNumberID.get_number('Request', db, lab=sub_lab.ref)
            service_request = ServiceRequest(admin_id=current_user.id, customer_id=customer_id, status_id=status_id,
                                             created_at=arrow.now('Asia/Bangkok').datetime, sub_lab=sub_lab,
                                             request_no=request_no.number, data=format_data(form.data))
            request_no.count += 1
        db.session.add(service_request)
        db.session.commit()
        return redirect(
            url_for('service_admin.create_report_language', request_id=service_request.id, menu=menu,
                    code=code))
    else:
        for er in form.errors:
            flash(f'{er} {form.errors[er]}', 'danger')
    return render_template('service_admin/forms/toxicology_request_form.html', code=code,
                           sub_lab=sub_lab, form=form, menu=menu, request_id=request_id)


@service_admin.route('/api/request/toxicology/item/add', methods=['POST'])
def add_toxicology_condition_item():
    form = ToxicologyRequestForm()
    form.toxicology_condition_field.append_entry()
    item_form = form.toxicology_condition_field[-1]
    index = len(form.toxicology_condition_field)
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
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                    <th style="border: none">{}</th>
                </thead>
                <tbody>
                    <td style="border: none" class="control">{}</td>
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
                           item_form.test.label,
                           item_form.blood_sample_of_trace_element.label,
                           item_form.blood_sample_of_heavy_metal.label,
                           item_form.urine_sample_of_trace_element.label,
                           item_form.urine_sample_of_heavy_metal.label,
                           item_form.test(class_='input'),
                           item_form.blood_sample_of_trace_element(),
                           item_form.blood_sample_of_heavy_metal(),
                           item_form.urine_sample_of_trace_element(),
                           item_form.urine_sample_of_heavy_metal()
                           )
    resp = make_response(resp)
    return resp


@service_admin.route('/api/request/toxicology/item/remove', methods=['DELETE'])
def remove_toxicology_condition_item():
    form = ToxicologyRequestForm()
    form.toxicology_condition_field.pop_entry()
    resp = ''
    for i, item_form in enumerate(form.toxicology_condition_field, start=1):
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
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                        <th style="border: none">{}</th>
                    </thead>
                    <tbody>
                        <td style="border: none" class="control">{}</td>
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
                                item_form.test.label,
                                item_form.blood_sample_of_trace_element.label,
                                item_form.blood_sample_of_heavy_metal.label,
                                item_form.urine_sample_of_trace_element.label,
                                item_form.urine_sample_of_heavy_metal.label,
                                item_form.test(class_='input'),
                                item_form.blood_sample_of_trace_element(),
                                item_form.blood_sample_of_heavy_metal(),
                                item_form.urine_sample_of_trace_element(),
                                item_form.urine_sample_of_heavy_metal()
                                )
    resp = make_response(resp)
    return resp


@service_admin.route("/request/other")
def get_other():
    request_id = request.args.get("request_id")
    sample_type = request.args.get("sample_type")
    if request_id:
        service_request = ServiceRequest.query.get(request_id)
        if service_request and service_request.data:
            data = service_request.data
            volume = data.get('volume', '')
            other = data.get('other', '')
        else:
            volume = ''
            other = ''
    else:
        volume = ''
        other = ''
    if sample_type == 'Urine 24 hrs.':
        html = f'''
            <div class="field ml-4 mb-4">
                <label class="label">
                    Total Volume (mL)
                    <span class="has-text-danger">*</span>
                </label>
                <div class="control">
                    <input name="volume" class="input" value="{volume}" required 
                    oninvalid="this.setCustomValidity('กรุณากรอกข้อมูล')" oninput="this.setCustomValidity('')">
                </div>
            </div>
            <input type="hidden" name="other" class="input" value="">
        '''
    elif sample_type == 'Other':
        html = f'''
            <div class="field ml-4 mb-4">
                <label class="label">
                    Comment
                    <span class="has-text-danger">*</span>
                </label>
                <div class="control">
                    <input name="other" class="input" value="{other}" required  
                    oninvalid="this.setCustomValidity('กรุณากรอกข้อมูล')" oninput="this.setCustomValidity('')">
                </div>
            </div>
            <input type="hidden" name="volume" class="input" value="">
        '''
    else:
        html = ('<input type="hidden" name=volume" class="input" value="">'
                '<input type="hidden" name="other" class="input" value="">')
    resp = make_response(html)
    return resp


@service_admin.route('/request/report_language/add/<int:request_id>', methods=['GET', 'POST'])
@login_required
def create_report_language(request_id):
    menu = request.args.get('menu')
    code = request.args.get('code')
    service_request = ServiceRequest.query.get(request_id)
    report_languages = ServiceReportLanguage.query.filter_by(sub_lab_id=service_request.sub_lab_id)
    report_receive_channels = ServiceReportReceiveChannel.query.filter_by(sub_lab_id=service_request.sub_lab_id)
    req_report_language_id = [rl.report_language_id for rl in service_request.report_languages]
    req_report_language = [rl.report_language.language for rl in sorted(service_request.report_languages,
                                                                        key=lambda rl: rl.report_language.no)]
    if request.method == 'POST':
        report_receive_channel_id = request.form.get('report_receive_channel', type=int)
        if report_receive_channel_id:
            service_request.report_receive_channel_id = report_receive_channel_id
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
                                    code=code))
        else:
            flash('กรุณาเลือกช่องทางการรับใบรายงานผล', 'danger')
    return render_template('service_admin/create_report_language.html', menu=menu, code=code,
                           request_id=request_id, report_languages=report_languages,
                           req_report_language=req_report_language,
                           service_request=service_request, req_report_language_id=req_report_language_id,
                           report_receive_channels=report_receive_channels)


@service_admin.route('/request/customer/detail/add/<int:request_id>', methods=['GET', 'POST'])
@login_required
def create_customer_detail(request_id):
    form = None
    menu = request.args.get('menu')
    code = request.args.get('code')
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
        else:
            flash('กรุณากรอกข้อมูลที่อยู่ใบเสนอราคา/ใบแจ้งหนี้/ใบกำกับภาษี และที่อยู่จัดส่งเอกสาร', 'danger')
            return redirect(url_for('service_admin.create_customer_detail', request_id=request_id, menu=menu,
                                    code=code))
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
                                address.customer_id = customer_id
                        else:
                            address = ServiceCustomerAddress(name=quotation_address.name, address_type='document',
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
                                                     address=quotation_address.address,
                                                     zipcode=quotation_address.zipcode,
                                                     phone_number=quotation_address.phone_number, reamerk=remark,
                                                     customer_id=customer_id,
                                                     province_id=quotation_address.province_id,
                                                     district_id=quotation_address.district_id,
                                                     subdistrict_id=quotation_address.subdistrict_id)
                db.session.add(address)
                db.session.commit()
        service_request.is_completed = True
        db.session.commit()
        return redirect(url_for('service_admin.view_request', request_id=request_id, menu=menu))
    return render_template('service_admin/create_customer_detail.html', form=form, customer=customer,
                           request_id=request_id, code=code, customer_id=customer_id, menu=menu,
                           service_request=service_request,
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

    if form.province.data:
        form.district.query = form.province.data.districts
    if form.district.data:
        form.subdistrict.query = form.district.data.subdistricts
    else:
        province = Province.query.first()
        form.district.query = province.districts
        form.subdistrict.query = province.districts[0].subdistricts if province.districts else ''

    if not form.taxpayer_identification_no.data and (type == 'quotation' or address.address_type == 'quotation'):
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
    tab = request.args.get('tab')
    api = request.args.get('api', 'false')
    query = (
        ServiceSample.query
        .join(ServiceSample.request)
        .join(ServiceRequest.sub_lab)
        .join(ServiceSubLab.admins)
        .filter(
            ServiceAdmin.admin_id == current_user.id
        )
    )
    schedule_query = query.filter(ServiceSample.appointment_date == None, ServiceSample.tracking_number == None,
                                  ServiceSample.received_at == None)
    delivery_query = query.filter(or_(ServiceSample.appointment_date != None, ServiceSample.tracking_number != None),
                                  ServiceSample.received_at == None)
    received_query = query.filter(ServiceSample.received_at != None)

    if api == 'true':
        if tab == 'schedule':
            query = schedule_query
        elif tab == 'delivery':
            query = delivery_query
        elif tab == 'received':
            query = received_query

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
    return render_template('service_admin/sample_index.html', menu=menu, tab=tab,
                           schedule_count=schedule_query.count(), delivery_count=delivery_query.count())


@service_admin.route('/api/sample/index')
def get_samples():
    tab = request.args.get('tab')
    query = (
        ServiceSample.query
        .join(ServiceSample.request)
        .join(ServiceRequest.sub_lab)
        .outerjoin(ServiceSubLab.admins)
        .filter(
            or_(
                ServiceSubLab.assistant_id == current_user.id,
                ServiceAdmin.admin_id == current_user.id
            )
        ).distinct()
    )
    if tab == 'schedule':
        query = query.filter(ServiceSample.appointment_date == None, ServiceSample.tracking_number == None,
                             ServiceSample.received_at == None)
    elif tab == 'delivery':
        query = query.filter(or_(ServiceSample.appointment_date != None, ServiceSample.tracking_number != None),
                             ServiceSample.received_at == None)
    elif tab == 'received':
        query = query.filter(ServiceSample.received_at != None)
    else:
        query = query
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
    tab = request.args.get('tab')
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
            # contact_email = sample.request.customer.contact_email if sample.request.customer.contact_email else sample.request.customer.email
            title_prefix = 'คุณ' if sample.request.customer.customer_info.type.type == 'บุคคล' else ''
            # link = url_for("academic_services.request_index", menu='request', _external=True, _scheme=scheme)
            title = f'''แจ้งตรวจรับตัวอย่างจากคำขอรับบริการ'''
            message = f'''เรียน {title_prefix}{sample.request.customer.customer_name}\n\n'''
            message += f'''ตามที่ท่านได้ส่งตัวอย่างเพื่อตรวจวิเคราะห์มายังคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล\nขณะนี้ทางเจ้าหน้าที่ได้ตรวจรับตัวอย่างของท่านเรียบร้อยแล้ว '''
            message += f'''เจ้าหน้าที่จะดำเนินการตรวจวิเคราะห์ และจัดทำรายงานผลการตรวจวิเคราะห์ต่อไป\n'''
            # message += f'''ท่านสามารถติดตามสถานะการตรวจวิเคราะห์ได้ที่ลิงก์ด้านล่างนี้้\n'''
            # message += f'''{link}\n\n'''
            message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
            message += f'''ขอขอบพระคุณที่ใช้บริการ\n\n'''
            message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
            message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
            if not current_app.debug:
                send_mail([sample.request.customer.email], title, message)
            else:
                print('message', message)
            flash('ผลการตรวจสอบตัวอย่างได้รับการบันทึกเรียบร้อยแล้ว', 'success')
            return redirect(url_for('service_admin.sample_index', menu=menu, tab='received'))
    else:
        return render_template('service_admin/sample_verify_page.html', request_no=sample.request.request_no,
                               menu=menu, tab='received')
    return render_template('service_admin/sample_verification_form.html', form=form, menu=menu, tab=tab,
                           request_no=sample.request.request_no)


@service_admin.route('/sample/appointment/view/<int:sample_id>')
@login_required
def view_sample_appointment(sample_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    sample = ServiceSample.query.get(sample_id)
    return render_template('service_admin/view_sample_appointment.html', sample=sample, menu=menu, tab=tab)


@service_admin.route('/test_item/index')
@login_required
def test_item_index():
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    api = request.args.get('api', 'false')
    query = (
        ServiceTestItem.query
        .join(ServiceTestItem.request)
        .join(ServiceRequest.sub_lab)
        .join(ServiceSubLab.admins)
        .filter(
            ServiceAdmin.admin_id == current_user.id
        )
    )
    not_started_query = query.outerjoin(ServiceResult).filter(ServiceResult.request_id == None)
    testing_query = query.join(ServiceResult).filter(ServiceResult.sent_at == None)
    edit_report_query = query.join(ServiceResult).filter(ServiceResult.req_edit_at != None,
                                                         ServiceResult.is_edited == False)
    waiting_confirm_query = query.join(ServiceResult).filter(ServiceResult.sent_at != None,
                                                             ServiceResult.approved_at == None,
                                                             or_(ServiceResult.req_edit_at == None,
                                                                 ServiceResult.is_edited == True
                                                                 )
                                                             )
    confirm_query = query.join(ServiceResult).filter(ServiceResult.approved_at != None)
    # pending_invoice_query = (
    #     query
    #     .join(
    #         ServiceQuotation,
    #         ServiceQuotation.request_id == ServiceRequest.id
    #     )
    #     .outerjoin(
    #         ServiceInvoice,
    #         ServiceInvoice.quotation_id == ServiceQuotation.id
    #     )
    #     .filter(ServiceInvoice.id == None)
    # )
    # invoice_query = (query.join(
    #         ServiceQuotation,
    #         ServiceQuotation.request_id == ServiceRequest.id
    #     ).outerjoin(
    #         ServiceInvoice,
    #         ServiceInvoice.quotation_id == ServiceQuotation.id
    #     )
    #     .filter(ServiceInvoice.id != None)
    # )

    if api == 'true':
        if tab == 'not_started':
            query = not_started_query
        elif tab == 'testing':
            query = testing_query
        elif tab == 'edit_report':
            query = edit_report_query
        elif tab == 'waiting_confirm':
            query = waiting_confirm_query
        elif tab == 'confirm':
            query = confirm_query
        # elif tab == 'pending_invoice':
        #     query = pending_invoice_query
        # elif tab == 'invoice':
        #     query = invoice_query

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
            html_blocks = []
            edit_html_blocks = []
            item_data = item.to_dict()
            for result in item.request.results:
                for i in result.result_items:
                    edit_html = ''
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
                        edit_result = url_for('service_admin.edit_draft_result', menu='report', tab='approve',
                                              result_item_id=i.id)
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
                        if i.req_edit_at and not i.is_edited:
                            edit_html = f'''<div class="field has-addons">
                                                <div class="control">
                                                    <a class="button is-small is-warning is-rounded" href="{edit_result}">
                                                        <span class="icon is-small"><i class="fas fa-pen"></i></span>
                                                        <span>แก้ไข{i.report_language}</span>
                                                    </a>
                                                </div>
                                            </div>
                                        '''
                    else:
                        html = ''
                    html_blocks.append(html)
                    if edit_html:
                        edit_html_blocks.append(edit_html)
            item_data['files'] = ''.join(
                html_blocks) if html_blocks else ''
            item_data['edit_file'] = ''.join(edit_html_blocks) if edit_html_blocks else ''
            data.append(item_data)
        return jsonify({'data': data,
                        'recordFiltered': total_filtered,
                        'recordTotal': records_total,
                        'draw': request.args.get('draw', type=int)
                        })
    return render_template('service_admin/test_item_index.html', menu=menu, tab=tab,
                           not_started_count=not_started_query.count(),
                           testing_count=testing_query.count(), edit_report_count=edit_report_query.count(),
                           waiting_confirm_query=waiting_confirm_query.count()
                           )


@service_admin.route('/request/view/<int:request_id>')
@login_required
def view_request(request_id=None):
    menu = request.args.get('menu')
    service_request = ServiceRequest.query.get(request_id)
    sub_lab = ServiceSubLab.query.filter_by(code=service_request.sub_lab.code)
    request_data = request_data_paths[service_request.sub_lab.code]
    datas = request_data(service_request, type='form')
    result_id = None
    if service_request.results:
        for result in service_request.results:
            result_id = result.id
    else:
        result_id = None
    return render_template('service_admin/view_request.html', service_request=service_request, menu=menu,
                           sub_lab=sub_lab, datas=datas, result_id=result_id)


@service_admin.route('/request/pdf/<int:request_id>', methods=['GET'])
@login_required
def export_request_pdf(request_id):
    code = request.args.get('code')
    request_paths = {'bacteria': 'service_admin.export_bacteria_request_pdf',
                     'disinfection': 'service_admin.export_virus_request_pdf',
                     'air_disinfection': 'service_admin.export_virus_request_pdf',
                     }
    return redirect(url_for(request_paths[code], code=code, request_id=request_id))


def generate_bacteria_request_pdf(service_request):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 40, 40)
    request_data = request_data_paths[service_request.sub_lab.code]
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
                            topMargin=30,
                            bottomMargin=30
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
                        เลขที่ใบคำขอ &nbsp;  <u>&nbsp;&nbsp;&nbsp;{request_no}&nbsp;&nbsp;&nbsp;</u><br/>
                        วันที่รับตัวอย่าง <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u><br/>
                        วันที่รายงานผล <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u><br/>
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
        leading=30,
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
    data.append(KeepTogether(Spacer(5, 5)))
    current_height += 5
    data.append(KeepTogether(combined_table))
    w, h = combined_table.wrap(doc.width, first_page_limit)
    current_height += h
    data.append(KeepTogether(Spacer(5, 5)))
    current_height += 5
    data.append(KeepTogether(customer_header))
    w, h = customer_header.wrap(doc.width, first_page_limit)
    current_height += h
    data.append(KeepTogether(Spacer(5, 5)))
    current_height += 5
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
        data.append(KeepTogether(Spacer(5, 5)))
        current_height += 5
        data.append(KeepTogether(header_table))
        current_height += h_header
        data.append(KeepTogether(Spacer(5, 5)))
        current_height += 5
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
                    bw, bh = box.wrap(doc.width, first_page_limit)
                    hit_page_end = current_height + bh >= first_page_limit
                    if not hit_page_end:
                        box.setStyle(TableStyle([
                            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LINEBELOW', (-1, 0), (-1, -1), 0, colors.white),
                        ]))
                    else:
                        box.setStyle(TableStyle([
                            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ]))
                    if current_height > first_page_limit:
                        data.append(PageBreak())
                        current_height = 0
                        data.append(KeepTogether(header_table))
                        w, h = header_table.wrap(doc.width, first_page_limit)
                        current_height += h
                        data.append(KeepTogether(Spacer(5, 5)))
                        current_height += 5
                    data.append(KeepTogether(box))
                    w, h = box.wrap(doc.width, first_page_limit)
                    current_height += h
                    text_section = []

                rows = g['data']
                for i, row in enumerate(rows):
                    row['Lab no'] = ''
                    row['สภาพตัวอย่าง'] = 'O ปกติ<br/>O ไม่ปกติ' if i == 0 else ''
                headers = list(rows[0].keys())
                raw_widths = []
                for h in headers:
                    w = stringWidth(str(h), detail_style.fontName, detail_style.fontSize)
                    if h == "เชื้อ":
                        w += 100
                    else:
                        w += 10
                    raw_widths.append(w)
                total_width = sum(raw_widths)
                max_total = 506

                if total_width > max_total:
                    scale = max_total / total_width
                    col_widths = [w * scale for w in raw_widths]
                else:
                    col_widths = raw_widths
                table_data = [[Paragraph(h, detail_style) for h in headers]]
                for row in rows:
                    table_data.append([Paragraph(row.get(h, ""), detail_style) for h in headers])
                table = Table(table_data, colWidths=col_widths)
                table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ('SPAN', (-1, 1), (-1, -1)),
                    ('SPAN', (-2, 1), (-2, -1)),
                    ('ALIGN', (-1, 1), (-1, -1), 'CENTER'),
                    ('VALIGN', (-1, 1), (-1, -1), 'MIDDLE'),
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
                    data.append(KeepTogether(Spacer(5, 5)))
                    current_height += 5
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

    report_header_table = Table(
        [[
            Paragraph('<b>ใบรายงานผล / Report</b>', header_style),
            Paragraph('<b>ช่องทางการรับใบรายงานผล / Reporting via</b>', header_style)
        ]],
        colWidths=[265, 265],
        rowHeights=[25]
    )

    report_header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEAFTER', (0, 0), (0, -1), 0.1, colors.grey)
    ]))

    report_language = Paragraph(
        "<br/>".join([f"{rl.report_language.item}" for rl in service_request.report_languages]),
        style=detail_style)
    report_language_table = Table([[report_language]], colWidths=[265])

    report_receive_channel = Paragraph(f"{service_request.report_receive_channel.item}", style=detail_style)
    report_receive_channel_table = Table([[report_receive_channel]], colWidths=[265])

    report_table = Table(
        [[report_language_table, report_receive_channel_table]],
        colWidths=[265, 265]
    )

    report_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (0, 0), 0.5, colors.grey),
        ('BOX', (1, 0), (1, 0), 0.5, colors.grey),
    ]))

    if current_height > first_page_limit:
        data.append(PageBreak())
        current_height = 0
    else:
        data.append(KeepTogether(Spacer(5, 5)))
        current_height += 5
    data.append(KeepTogether(report_header_table))
    w, h = report_header_table.wrap(doc.width, first_page_limit)
    current_height += h
    data.append(KeepTogether(Spacer(5, 5)))
    current_height += 5
    data.append(KeepTogether(report_table))
    w, h = report_table.wrap(doc.width, first_page_limit)
    current_height += h

    sub_header_bold_style = ParagraphStyle(
        'SubHeaderBoldStyle',
        parent=style_sheet['ThaiStyleBold'],
        fontSize=14,
        leading=18
    )

    selected_checkbox = f'<font name="DejaVuSans">☑</font>'
    item_data = "".join(item['data'] for item in values if item['type'] == 'bool')

    sign_table = Table([
        [Spacer(1, 6)],
        [Paragraph(f'{selected_checkbox} {item_data}',
                   style=detail_style)],
        [Paragraph(
            "ลงชื่อผู้ส่งตัวอย่าง / Sent by <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>"
            "วันที่ <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> "
            "<font name='Sarabun'>/</font> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> "
            "<font name='Sarabun'>/</font> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>",
            style=sub_header_bold_style)],
        [Paragraph(
            "ลงชื่อผู้รับตัวอย่าง / Received by <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;</u>"
            "วันที่ <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> "
            "<font name='Sarabun'>/</font> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> "
            "<font name='Sarabun'>/</font> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>",
            style=sub_header_bold_style)],
        [Spacer(1, 6)]
    ], colWidths=[530])

    sign_table.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    if current_height > first_page_limit:
        data.append(PageBreak())
        current_height = 0
    else:
        data.append(KeepTogether(Spacer(5, 5)))
        current_height += 5
    data.append(KeepTogether(sign_table))
    w, h = sign_table.wrap(doc.width, first_page_limit)
    current_height += h

    if service_request.samples:
        sample_id = int(''.join(str(s.id) for s in service_request.samples))
        qr_buffer = BytesIO()
        qr_img = qrcode.make(url_for('service_admin.sample_verification', sample_id=sample_id, menu='sample',
                                     _external=True))
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        qr_code = Image(qr_buffer, width=80, height=80)
        qr_code_label = Paragraph("QR Code สำหรับเจ้าหน้าที่ตรวจรับตัวอย่าง", style=center_style)
        qr_code_table = Table([
            [qr_code_label],
            [qr_code],
        ], colWidths=[220])
        qr_code_table.hAlign = 'LEFT'
        qr_code_table.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (0, 0), 12),
            ('LEFTPADDING', (0, 1), (0, 1), 70),
            ('TOPPADDING', (0, 1), (0, 1), -7),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        if current_height > first_page_limit:
            data.append(PageBreak())
        else:
            data.append(Spacer(1, 30))
        data.append(KeepTogether(qr_code_table))
    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    buffer.seek(0)
    return buffer


@service_admin.route('/request/bacteria/pdf/<int:request_id>', methods=['GET'])
def export_bacteria_request_pdf(request_id):
    service_request = ServiceRequest.query.get(request_id)
    buffer = generate_bacteria_request_pdf(service_request)
    return send_file(buffer, download_name='Request.pdf', as_attachment=True)


def generate_virus_request_pdf(service_request):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 40, 40)
    request_data = request_data_paths[service_request.sub_lab.code]
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
                            topMargin=30,
                            bottomMargin=30
                            )

    data = []
    first_page_limit = 650
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
                        เลขที่ใบคำขอ &nbsp;  <u>&nbsp;&nbsp;&nbsp;{request_no}&nbsp;&nbsp;&nbsp;</u><br/>
                        วันที่รับตัวอย่าง <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u><br/>
                        วันที่รายงานผล <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u><br/>
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
        leading=30,
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
    data.append(KeepTogether(Spacer(5, 5)))
    current_height += 5
    data.append(KeepTogether(combined_table))
    w, h = combined_table.wrap(doc.width, first_page_limit)
    current_height += h
    data.append(KeepTogether(Spacer(5, 5)))
    current_height += 5
    data.append(KeepTogether(customer_header))
    w, h = customer_header.wrap(doc.width, first_page_limit)
    current_height += h
    data.append(KeepTogether(Spacer(5, 5)))
    current_height += 5
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
        data.append(KeepTogether(Spacer(5, 5)))
        current_height += 5
        data.append(KeepTogether(header_table))
        current_height += h_header
        data.append(KeepTogether(Spacer(5, 5)))
        current_height += 5
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
                    bw, bh = box.wrap(doc.width, first_page_limit)
                    hit_page_end = current_height + bh >= first_page_limit
                    if not hit_page_end:
                        box.setStyle(TableStyle([
                            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LINEBELOW', (-1, 0), (-1, -1), 0, colors.white),
                        ]))
                    else:
                        box.setStyle(TableStyle([
                            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ]))
                    if current_height > first_page_limit:
                        data.append(PageBreak())
                        current_height = 0
                        data.append(KeepTogether(header_table))
                        w, h = header_table.wrap(doc.width, first_page_limit)
                        current_height += h
                        data.append(KeepTogether(Spacer(5, 5)))
                        current_height += 5
                    data.append(KeepTogether(box))
                    w, h = box.wrap(doc.width, first_page_limit)
                    current_height += h
                    text_section = []

                rows = g['data']
                for i, row in enumerate(rows):
                    row['Lab no'] = ''
                    if service_request.sub_lab.code == 'disinfection':
                        row['สภาพตัวอย่าง'] = 'O ปกติ<br/>O ไม่ปกติ' if i == 0 else ''
                    else:
                        row['การทำงานของอุปกรณ์'] = 'O ปกติ<br/>O ไม่ปกติ' if i == 0 else ''
                headers = list(rows[0].keys())
                raw_widths = []
                for h in headers:
                    w = stringWidth(str(h), detail_style.fontName, detail_style.fontSize)
                    if h == "เชื้อ":
                        w += 120
                    else:
                        w += 18
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
                    table_data.append([Paragraph(row.get(h, ""), detail_style) for h in headers])
                table = Table(table_data, colWidths=col_widths)
                table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ('SPAN', (-1, 1), (-1, -1)),
                    ('ALIGN', (-1, 1), (-1, -1), 'CENTER'),
                    ('VALIGN', (-1, 1), (-1, -1), 'MIDDLE'),
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
                    data.append(KeepTogether(Spacer(5, 5)))
                    current_height += 5
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

    report_header_table = Table(
        [[
            Paragraph('<b>ใบรายงานผล / Report</b>', header_style),
            Paragraph('<b>ช่องทางการรับใบรายงานผล / Reporting via</b>', header_style)
        ]],
        colWidths=[265, 265],
        rowHeights=[25]
    )

    report_header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEAFTER', (0, 0), (0, -1), 0.1, colors.grey)
    ]))

    report_language = Paragraph(
        "<br/>".join([f"{rl.report_language.item}" for rl in service_request.report_languages]),
        style=detail_style)
    report_language_table = Table([[report_language]], colWidths=[265])

    report_receive_channel = Paragraph(f"{service_request.report_receive_channel.item}", style=detail_style)
    report_receive_channel_table = Table([[report_receive_channel]], colWidths=[265])

    report_table = Table(
        [[report_language_table, report_receive_channel_table]],
        colWidths=[265, 265]
    )

    report_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (0, 0), 0.5, colors.grey),
        ('BOX', (1, 0), (1, 0), 0.5, colors.grey),
    ]))

    if current_height > first_page_limit:
        data.append(PageBreak())
        current_height = 0
    else:
        data.append(KeepTogether(Spacer(5, 5)))
        current_height += 5
    data.append(KeepTogether(report_header_table))
    w, h = report_header_table.wrap(doc.width, first_page_limit)
    current_height += h
    data.append(KeepTogether(Spacer(5, 5)))
    current_height += 5
    data.append(KeepTogether(report_table))
    w, h = report_table.wrap(doc.width, first_page_limit)
    current_height += h

    remark_data = "".join(item['data'] for item in values if item['type'] == 'remark')

    remark_header_table = Table(
        [[
            Paragraph('<b>บันทึก/หมายเหตุ สำหรับผู้รับบริการ</b>', header_style),
            Paragraph('<b>บันทึก/หมายเหตุ สำหรับห้องปฏิบัติการ</b>', header_style)
        ]],
        colWidths=[265, 265],
        rowHeights=[25]
    )

    remark_header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEAFTER', (0, 0), (0, -1), 0.1, colors.grey)
    ]))
    if remark_data:
        remark_customer = Paragraph(f"{remark_data}", style=detail_style)
    else:
        remark_customer = Paragraph('', style=detail_style)
    remark_customer_table = Table([[remark_customer]], colWidths=[265])

    remark_admin_table = Table([['']], colWidths=[265])

    remark_table = Table(
        [[remark_customer_table, remark_admin_table]],
        colWidths=[265, 265], rowHeights=[80]
    )

    remark_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (0, 0), 0.5, colors.grey),
        ('BOX', (1, 0), (1, 0), 0.5, colors.grey),
    ]))

    if current_height > first_page_limit:
        data.append(PageBreak())
        current_height = 0
    else:
        data.append(KeepTogether(Spacer(5, 5)))
        current_height += 5
    data.append(KeepTogether(remark_header_table))
    w, h = remark_header_table.wrap(doc.width, first_page_limit)
    current_height += h
    data.append(KeepTogether(Spacer(5, 5)))
    current_height += 5
    data.append(KeepTogether(remark_table))
    w, h = remark_table.wrap(doc.width, first_page_limit)
    current_height += h

    sub_header_bold_style = ParagraphStyle(
        'SubHeaderBoldStyle',
        parent=style_sheet['ThaiStyleBold'],
        fontSize=14,
        leading=18
    )

    sub_detail_style = ParagraphStyle(
        'SubDetailStyle',
        parent=detail_style,
        leftIndent=100
    )

    selected_checkbox = f'<font name="DejaVuSans">☑</font>'
    item_data = "".join(item['data'] for item in values if item['type'] == 'bool')

    sign_table = Table([
        [Spacer(1, 6)],
        [Paragraph(f'{selected_checkbox} {item_data}',
                   style=detail_style)],
        [Paragraph(
            "ลงชื่อผู้ส่งตัวอย่าง / Sent by <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>"
            "วันที่ <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> "
            "<font name='Sarabun'>/</font> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> "
            "<font name='Sarabun'>/</font> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>",
            style=sub_header_bold_style)],
        [Paragraph(
            "ลงชื่อผู้รับตัวอย่าง / Received by <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;</u>"
            "วันที่ <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> "
            "<font name='Sarabun'>/</font> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> "
            "<font name='Sarabun'>/</font> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>",
            style=sub_header_bold_style)],
        [Spacer(1, 6)]
    ], colWidths=[530])

    sign_table.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    if current_height > first_page_limit:
        data.append(PageBreak())
        current_height = 0
    else:
        data.append(KeepTogether(Spacer(5, 5)))
        current_height += 5
    data.append(KeepTogether(sign_table))
    w, h = sign_table.wrap(doc.width, first_page_limit)
    current_height += h

    checkbox = f'<font name="DejaVuSans">☐</font>'

    extend_analysis_table = Table([
        [Spacer(1, 6)],
        [Paragraph("กรณีที่มีการขยายระยะเวลาการตรวจวิเคราะห์", style=sub_header_bold_style)],
        [Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ขยายระยะเวลาการตรวจวิเคราะห์ เป็นระยะเวลา "
                   "<u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                   "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> วัน", style=detail_style)],
        [Paragraph(
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;เหตุผลความจำเป็น : &nbsp;&nbsp;&nbsp;&nbsp;{checkbox} เครื่องมือไม่พร้อม "
            f"<u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>",
            style=detail_style)],
        [Paragraph(
            f"{checkbox} ห้องปฏิบัติการไม่พร้อม "
            f"<u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;</u>",
            style=sub_detail_style)],
        [Paragraph(
            f"{checkbox} เจ้าหน้าที่ทดสอบไม่พร้อม "
            f"<u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>",
            style=sub_detail_style)],
        [Paragraph(
            f"{checkbox} ตัวอย่างไม่พร้อม "
            f"<u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>",
            style=sub_detail_style)],

        [Paragraph(
            f"{checkbox} อื่นๆ "
            f"<u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>",
            style=sub_detail_style)],
        [Spacer(1, 7)],
        [Paragraph("ลงชื่อหัวหน้าห้องปฏิบัติการ <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                   "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                   "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                   "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                   "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                   "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                   "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                   "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>"
                   "วันที่ <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> "
                   "<font name='Sarabun'>/</font> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> "
                   "<font name='Sarabun'>/</font> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>",
                   style=sub_header_bold_style)],
        [Paragraph(
            "ลงชื่อผู้รับบริการ <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>"
            "วันที่ <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> "
            "<font name='Sarabun'>/</font> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u> "
            "<font name='Sarabun'>/</font> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>",
            style=sub_header_bold_style)],
        [Spacer(1, 6)],
    ], colWidths=[530])

    extend_analysis_table.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    if current_height > first_page_limit:
        data.append(PageBreak())
        current_height = 0
    else:
        data.append(KeepTogether(Spacer(5, 5)))
        current_height += 5
    data.append(KeepTogether(extend_analysis_table))
    w, h = extend_analysis_table.wrap(doc.width, first_page_limit)
    current_height += h
    if service_request.samples:
        sample_id = int(''.join(str(s.id) for s in service_request.samples))
        qr_buffer = BytesIO()
        qr_img = qrcode.make(url_for('service_admin.sample_verification', sample_id=sample_id, menu='sample',
                                     _external=True))
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        qr_code = Image(qr_buffer, width=80, height=80)
        qr_code_label = Paragraph("QR Code สำหรับเจ้าหน้าที่ตรวจรับตัวอย่าง", style=center_style)
        qr_code_table = Table([
            [qr_code_label],
            [qr_code],
        ], colWidths=[220])
        qr_code_table.hAlign = 'LEFT'
        qr_code_table.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (0, 0), 12),
            ('LEFTPADDING', (0, 1), (0, 1), 70),
            ('TOPPADDING', (0, 1), (0, 1), -7),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        if current_height > first_page_limit:
            data.append(PageBreak())
        else:
            data.append(Spacer(1, 30))
        data.append(KeepTogether(qr_code_table))
    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    buffer.seek(0)
    return buffer


@service_admin.route('/request/virus/pdf/<int:request_id>', methods=['GET'])
def export_virus_request_pdf(request_id):
    service_request = ServiceRequest.query.get(request_id)
    buffer = generate_virus_request_pdf(service_request)
    return send_file(buffer, download_name='Request.pdf', as_attachment=True)


@service_admin.route('/result/index')
@login_required
def result_index():
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    api = request.args.get('api', 'false')
    query = (
        ServiceResult.query
        .join(ServiceResult.request)
        .join(ServiceRequest.sub_lab)
        .join(ServiceSubLab.admins)
        .filter(
            ServiceAdmin.admin_id == current_user.id
        )
    )
    pending_query = query.filter(ServiceResult.sent_at == None)
    edit_query = query.filter(ServiceResult.req_edit_at != None, ServiceResult.is_edited == False)
    approve_query = query.filter(ServiceResult.sent_at != None, ServiceResult.approved_at == None,
                                 or_(ServiceResult.req_edit_at == None, ServiceResult.is_edited == True
                                     )
                                 )
    confirm_query = query.filter(ServiceResult.approved_at != None)
    if api == 'true':
        if tab == 'pending':
            query = pending_query
        elif tab == 'edit':
            query = edit_query
        elif tab == 'approve':
            query = approve_query
        elif tab == 'confirm':
            query = confirm_query

        records_total = query.count()
        search = request.args.get('search[value]')
        if search:
            query = query.filter(ServiceRequest.request_no).contains(search)
        start = request.args.get('start', type=int)
        length = request.args.get('length', type=int)
        total_filtered = query.count()
        query = query.offset(start).limit(length)
        data = []
        for item in query:
            html_blocks = []
            edit_html_blocks = []
            note_html_blocks = []
            item_data = item.to_dict()
            for i in item.result_items:
                edit_html = ''
                note_html = ''
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
                    edit_result = url_for('service_admin.edit_draft_result', menu='report', tab='approve',
                                          result_item_id=i.id)
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

                if i.req_edit_at and not i.is_edited:
                    edit_html = f'''<div class="field has-addons">
                                            <div class="control">
                                                <a class="button is-small is-warning is-rounded" href="{edit_result}">
                                                    <span class="icon is-small"><i class="fas fa-pen"></i></span>
                                                    <span>แก้ไข{i.report_language}</span>
                                                </a>
                                            </div>
                                        </div>
                                    '''
                    note_html = f'''{i.report_language} : {i.note}<br/>'''
                elif i.req_edit_at and i.is_edited:
                    note_html = f'''{i.report_language} : {i.note}
                                    <br/>
                                    <span class="tag has-text-success is-rounded">ดำเนินการแล้ว</span>
                                    <br/>
                                '''
                if edit_html:
                    edit_html_blocks.append(edit_html)
                if note_html:
                    note_html_blocks.append(note_html)
            item_data['files'] = ''.join(
                html_blocks) if html_blocks else ''
            item_data['edit_file'] = ''.join(edit_html_blocks) if edit_html_blocks else ''
            item_data['note'] = ''.join(note_html_blocks) if note_html_blocks else ''
            data.append(item_data)
        return jsonify({'data': data,
                        'recordFiltered': total_filtered,
                        'recordTotal': records_total,
                        'draw': request.args.get('draw', type=int)
                        })
    return render_template('service_admin/result_index.html', menu=menu, tab=tab,
                           pending_count=pending_query.count(),
                           edit_count=edit_query.count(), approve_count=approve_query.count())


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
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    result = ServiceResult.query.get(result_id)
    form = ServiceResultForm(obj=result)
    if form.validate_on_submit():
        form.populate_obj(result)
        db.session.add(result)
        db.session.commit()
        customer_name = result.request.customer.customer_name.replace(' ', '_')
        title_prefix = 'คุณ' if result.request.customer.customer_info.type.type == 'บุคคล' else ''
        title = f'''แจ้งจัดส่งรายงานผลการทดสอบ'''
        message = f'''เรียน {title_prefix}{result.request.customer.customer_name}\n\n'''
        message += f'''ตามที่ท่านได้ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล\n'''
        message += f'''ขณะนี้ทางเจ้าหน้าที่ได้ดำเนินการจัดส่งรายงานผลการทดสอบฉบับจริงให้แก่ท่านทางไปรษณีย์เป็นที่เรียบร้อยแล้ว\nหมายเลขพัสดุ : {result.tracking_number}\n'''
        message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
        message += f'''ขอขอบพระคุณที่ใช้บริการ\n'''
        message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
        message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
        if not current_app.debug:
            send_mail([result.request.customer.email], title, message)
        else:
            print('message', message)
        flash('อัพเดตข้อมูลสำเร็จ', 'success')
        return redirect(url_for('service_admin.result_index', menu=menu, tab=tab))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('service_admin/add_tracking_number_for_result.html', form=form, menu=menu,
                           tab=tab, result_id=result_id)


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
        address = None

    if form.province.data:
        form.district.query = form.province.data.districts
    if form.district.data:
        form.subdistrict.query = form.district.data.subdistricts
    else:
        province = Province.query.first()
        form.district.query = province.districts
        form.subdistrict.query = province.districts[0].subdistricts if province.districts else ''

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
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('service_admin/create_customer_address.html', form=form, customer_id=customer_id,
                           address_id=address_id, address=address)


@service_admin.route('/api/items', methods=['POST'])
def get_items():
    trigger = request.headers.get('hx-trigger')
    use_type = request.args.get('use_type', type=bool)
    ServiceCustomerAddressForm = crate_address_form(use_type=use_type)
    form = ServiceCustomerAddressForm()

    if trigger == 'province':
        form.district.query = form.province.data.districts
        district = form.province.data.districts[0] if form.province.data.districts else ''
        form.subdistrict.query = district.subdistricts if district else ''
    elif trigger == 'district' or trigger == 'subdistrict':
        form.district.query = form.province.data.districts
        form.subdistrict.query = form.district.data.subdistricts
        if trigger == 'subdistrict':
            form.zipcode.data = form.subdistrict.data.zip_code

    template = f'''
        {form.province(**{'hx-trigger': 'change', 'hx-target': '#province', 'hx-swap': 'outerHTML', 'hx-post': url_for('service_admin.get_items', use_type=use_type)})}
        {form.district(**{'hx-swap-oob': 'true', 'hx-trigger': 'change', 'hx-target': '#province', 'hx-swap': 'outerHTML', 'hx-post': url_for('service_admin.get_items', use_type=use_type)})}
        {form.subdistrict(**{'hx-swap-oob': 'true', 'hx-trigger': 'change', 'hx-target': '#province', 'hx-swap': 'outerHTML', 'hx-post': url_for('service_admin.get_items', use_type=use_type)})}
        {form.zipcode(class_='input', **{'hx-swap-oob': 'true', 'hx-trigger': 'change', 'hx-target': '#province', 'hx-swap': 'outerHTML', 'hx-post': url_for('service_admin.get_items', use_type=use_type)})}
        '''
    return template


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
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    api = request.args.get('api', 'false')
    is_central_admin = ServiceAdmin.query.filter_by(admin_id=current_user.id, is_central_admin=True).first()
    query = (
        ServiceInvoice.query
        .join(ServiceInvoice.quotation)
        .join(ServiceQuotation.request)
        .join(ServiceRequest.sub_lab)
        .join(ServiceSubLab.admins)
        .filter(ServiceAdmin.admin_id == current_user.id)
    )
    draft_query = query.filter(ServiceInvoice.sent_at == None)
    pending_supervisor_query = query.filter(ServiceInvoice.sent_at != None, ServiceInvoice.head_approved_at == None)
    pending_assistant_query = query.filter(ServiceInvoice.head_approved_at != None,
                                           ServiceInvoice.assistant_approved_at == None)
    pending_dean_query = query.filter(ServiceInvoice.assistant_approved_at != None,
                                      ServiceInvoice.file_attached_at == None)
    waiting_payment_query = query.outerjoin(ServicePayment).filter(or_(ServicePayment.invoice_id == None,
                                                                       ServicePayment.verified_at == None),
                                                                   ServiceInvoice.file_attached_at != None)
    payment_query = query.join(ServicePayment).filter(ServicePayment.verified_at != None)
    if api == 'true':
        if tab == 'draft':
            query = draft_query
        elif tab == 'pending_supervisor':
            query = pending_supervisor_query
        elif tab == 'pending_assistant':
            query = pending_assistant_query
        elif tab == 'pending_dean':
            query = pending_dean_query
        elif tab == 'waiting_payment':
            query = waiting_payment_query
        elif tab == 'payment':
            query = payment_query
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
    return render_template('service_admin/invoice_index.html', menu=menu, tab=tab,
                           draft_count=draft_query.count(), pending_supervisor_count=pending_supervisor_query.count(),
                           pending_assistant_count=pending_assistant_query.count(),
                           pending_dean_count=pending_dean_query.count(),
                           waiting_payment_count=waiting_payment_query.count(),
                           payment_count=payment_query.count(), is_central_admin=is_central_admin)


@service_admin.route('/central_admin/invoice/index')
@login_required
def invoice_index_for_central_admin():
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    api = request.args.get('api', 'false')
    query = (
        ServiceInvoice.query
        .join(ServiceInvoice.quotation)
        .join(ServiceQuotation.request)
        .join(ServiceRequest.sub_lab)
        .join(ServiceSubLab.admins)
        .filter(ServiceAdmin.admin_id == current_user.id)
    )
    draft_query = query.filter(ServiceInvoice.sent_at == None)
    pending_supervisor_query = query.filter(ServiceInvoice.sent_at != None, ServiceInvoice.head_approved_at == None)
    pending_assistant_query = query.filter(ServiceInvoice.head_approved_at != None,
                                           ServiceInvoice.assistant_approved_at == None)
    pending_dean_query = query.filter(ServiceInvoice.assistant_approved_at != None,
                                      ServiceInvoice.file_attached_at == None)
    waiting_payment_query = query.outerjoin(ServicePayment).filter(or_(ServicePayment.invoice_id == None,
                                                                       ServicePayment.verified_at == None),
                                                                   ServiceInvoice.file_attached_at != None)
    payment_query = query.join(ServicePayment).filter(ServicePayment.verified_at != None)
    if api == 'true':
        if tab == 'draft':
            query = draft_query
        elif tab == 'pending_supervisor':
            query = pending_supervisor_query
        elif tab == 'pending_assistant':
            query = pending_assistant_query
        elif tab == 'pending_dean':
            query = pending_dean_query
        elif tab == 'waiting_payment':
            query = waiting_payment_query
        elif tab == 'payment':
            query = payment_query
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
    return render_template('service_admin/invoice_index_for_central_admin.html', menu=menu, tab=tab,
                           draft_count=draft_query.count(), pending_supervisor_count=pending_supervisor_query.count(),
                           pending_assistant_count=pending_assistant_query.count(),
                           pending_dean_count=pending_dean_query.count(),
                           waiting_payment_count=waiting_payment_query.count(),
                           payment_count=payment_query.count())


@service_admin.route('/invoice/add/<int:quotation_id>', methods=['GET', 'POST'])
@login_required
def create_invoice(quotation_id):
    menu = request.args.get('menu')
    quotation = ServiceQuotation.query.get(quotation_id)
    invoice = ServiceInvoice.query.filter_by(quotation_id=quotation_id).first()
    if not invoice:
        invoice_no = ServiceNumberID.get_number('Invoice', db, lab=quotation.request.sub_lab.ref)
        invoice = ServiceInvoice(invoice_no=invoice_no.number, quotation_id=quotation_id, name=quotation.name,
                                 address=quotation.address,
                                 taxpayer_identification_no=quotation.taxpayer_identification_no,
                                 created_at=arrow.now('Asia/Bangkok').datetime,
                                 creator_id=current_user.id)
        invoice_no.count += 1
        db.session.add(invoice)
        for quotation_item in quotation.quotation_items:
            invoice_item = ServiceInvoiceItem(sequence=quotation_item.sequence,
                                              discount_type=quotation_item.discount_type,
                                              invoice_id=invoice.id, item=quotation_item.item,
                                              quantity=quotation_item.quantity,
                                              unit_price=quotation_item.unit_price,
                                              total_price=quotation_item.total_price,
                                              discount=quotation_item.discount)
            db.session.add(invoice_item)
            db.session.commit()
        db.session.commit()
        status_id = get_status(16)
        quotation.request.status_id = status_id
        db.session.add(quotation)
        db.session.add(invoice)
        db.session.commit()
        flash('สร้างใบแจ้งหนี้สำเร็จ', 'success')
        return redirect(url_for('service_admin.view_invoice', invoice_id=invoice.id, menu=menu))
    else:
        return render_template('service_admin/invoice_created_confirmation_page.html', menu=menu,
                               invoice_id=[invoice.id for invoice in quotation.invoices])


@service_admin.route('/invoice/approve/<int:invoice_id>', methods=['GET', 'POST'])
def approve_invoice(invoice_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    admin = request.args.get('admin')
    invoice = ServiceInvoice.query.get(invoice_id)
    scheme = 'http' if current_app.debug else 'https'
    admins = (
        ServiceAdmin.query
        .join(ServiceSubLab)
        .filter(ServiceSubLab.code == invoice.quotation.request.sub_lab.code)
        .all()
    )
    invoice_url = url_for("service_admin.view_invoice", invoice_id=invoice.id, menu=menu, _external=True,
                          tab=tab, _scheme=scheme)
    customer_name = invoice.customer_name.replace(' ', '_')
    title_prefix = 'คุณ' if invoice.quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
    if admin == 'assistant':
        invoice_for_central_admin_url = url_for("service_admin.view_invoice_for_central_admin", invoice_id=invoice.id,
                                                menu=menu, _external=True,
                                                tab=tab, _scheme=scheme)
        status_id = get_status(19)
        invoice.quotation.request.status_id = status_id
        invoice.assistant_approved_at = arrow.now('Asia/Bangkok').datetime
        invoice.assistant_id = current_user.id
        db.session.add(invoice)
        db.session.commit()
        if admins:
            email = [a.admin.email + '@mahidol.ac.th' for a in admins if a.is_central_admin]
            if email:
                title = f'รายการดำเนินการใบแจ้งหนี้'
                message = f'''เรียน แอดมินส่วนกลาง\n\n'''
                message += f'''ตามที่มีการออกใบแจ้งหนี้เลขที่ : {invoice.invoice_no}\n'''
                # message += f'''ลูกค้า : {invoice.customer_name}\n'''
                # message += f'''ในนาม : {invoice.name}\n'''
                # message += f'''อ้างอิงเอกสาร : \n'''
                # message += f'''- ใบคำขอรับบริการเลขที่ : {invoice.quotation.request.request_no}\n'''
                # message += f'''- ใบเสนอราคาเลขที่ : {invoice.quotation.quotation_no}\n\n'''
                message += f'''ขอความกรุณา แอดมินส่วนกลางดำเนินการดังต่อไปนี้\n\n'''
                message += f'''1. พิมพ์ใบแจ้งหนี้\n'''
                message += f'''2. ออกเลขสารบรรณ\n'''
                message += f'''3. นำเข้าเอกสารเข้าสู่ระบบ e-Office เพื่อเสนอคณบดีลงนาม\n'''
                message += f'''4. หลังจากดำเนินการเรียบร้อยแล้ว กรุณาอัปโหลดไฟล์ใบแจ้งหนี้ที่ลงนามแล้วกลับเข้าสู่ระบบบริการวิชาการ เพื่อให้ระบบดำเนินการแจ้งลูกค้าต่อไป\n\n'''
                message += f'''ท่านสามารถเข้าดำเนินการได้ที่ระบบ\n'''
                message += f'''{invoice_for_central_admin_url}\n\n'''
                message += f'''หากมีข้อขัดข้องหรือข้อมูลเพิ่มเติมที่ต้องใช้\nสามารถประสานแจ้งกลับได้โดยตรง\n\n'''
                message += f'''ขอบคุณค่ะ\nฝ่ายระบบสารสนเทศ / MIS'''
                msg = ('ใบแจ้งหนี้เลขที่ {}\n' \
                       'ออกในนาม {}\n' \
                       'ณ วันที่ {} รอดำเนินการอัปโหลดใบแจ้งหนี้ฉบับลงนามคณบดี\n' \
                       'กรุณาดำเนินการอัปโหลดในระบบ\n'
                       'คลิกลิ้งค์เพื่อดำเนินการ\n'
                       '{}'.format(invoice.invoice_no, invoice.name,
                                   invoice.assistant_approved_at.astimezone(localtz).strftime('%d/%m/%Y'),
                                   invoice_for_central_admin_url)
                       )
                if not current_app.debug:
                    send_mail(email, title, message)
                    for a in admins:
                        if a.is_central_admin:
                            try:
                                line_bot_api.push_message(to=a.admin.line_id,
                                                          messages=TextSendMessage(text=msg))
                            except LineBotApiError:
                                pass
                else:
                    print('message_email', message, 'message_line', msg)
    elif admin == 'supervisor':
        status_id = get_status(18)
        invoice.quotation.request.status_id = status_id
        invoice.head_approved_at = arrow.now('Asia/Bangkok').datetime
        invoice.head_id = current_user.id
        if admins:
            email = [a.admin.email + '@mahidol.ac.th' for a in admins if a.is_assistant]
            if email:
                title = f'รายการอนุมัติใบแจ้งหนี้'
                message = f'''เรียน ผู้ช่วยคณบดีฝ่ายบริการวิชาการ\n\n'''
                # message += f'''ใบแจ้งหนี้เลขที่ : {invoice.invoice_no}\n'''
                # message += f'''ลูกค้า : {invoice.customer_name}\n'''
                # message += f'''ในนาม : {invoice.name}\n'''
                # message += f'''อ้างอิงจาก : \n'''
                # message += f'''- ใบคำขอรับบริการเลขที่ : {invoice.quotation.request.request_no}\n'''
                # message += f'''- ใบเสนอราคาเลขที่ : {invoice.quotation.quotation_no}\n'''
                message += f'''มีใบแจ้งหนี้เลขที่ {invoice.invoice_no} ที่รอดำเนินการอนุมัติใบแจ้งหนี้ ท่านสามารถตรวจสอบและดำเนินการได้ที่ลิงก์ด้านล่าง\n'''
                message += f'''{invoice_url}\n\n'''
                # message += f'''ผู้ประสานงาน\n'''
                # message += f'''{invoice.customer_name}\n'''
                # message += f'''เบอร์โทร {invoice.contact_phone_number}\n'''
                message += f'''ระบบบริการวิชาการ'''
                msg = ('ใบแจ้งหนี้เลขที่ {}\n' \
                       'ออกในนาม {}\n' \
                       'ณ วันที่ {} รอดำเนินการอนุมัติใบแจ้งหนี้\n' \
                       'กรุณาดำเนินการอนุมัติในระบบ\n'
                       'คลิกลิ้งค์เพื่อดำเนินการ\n'
                       '{}'.format(invoice.invoice_no, invoice.name,
                                   invoice.head_approved_at.astimezone(localtz).strftime('%d/%m/%Y'), invoice_url
                                   )
                       )
                if not current_app.debug:
                    send_mail(email, title, message)
                    for a in admins:
                        if a.is_assistant:
                            try:
                                line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                            except LineBotApiError:
                                pass
                else:
                    print('message_email', message, 'message_line', msg)
    else:
        status_id = get_status(17)
        invoice.sent_at = arrow.now('Asia/Bangkok').datetime
        invoice.sender_id = current_user.id
        invoice.quotation.request.status_id = status_id
        if admins:
            email = [a.admin.email + '@mahidol.ac.th' for a in admins if a.is_supervisor]
            if email:
                title = f'รายการอนุมัติใบแจ้งหนี้'
                message = f'''เรียน หัวหน้าห้องปฏิบัติการ{invoice.quotation.request.sub_lab.lab.lab}\n\n'''
                message += f'''มีใบแจ้งหนี้เลขที่ {invoice.invoice_no} ที่รอดำเนินการอนุมัติใบแจ้งหนี้ ท่านสามารถตรวจสอบและดำเนินการได้ที่ลิงก์ด้านล่าง\n'''
                message += f'''{invoice_url}\n\n'''
                message += f'''ระบบบริการวิชาการ'''
                msg = ('ใบแจ้งหนี้เลขที่ {}\n' \
                       'ออกในนาม {}\n' \
                       'ณ วันที่ {} รอดำเนินการอนุมัติใบแจ้งหนี้\n' \
                       'กรุณาดำเนินการอนุมัติในระบบ\n'
                       'คลิกลิ้งค์เพื่อดำเนินการ\n'
                       '{}'.format(invoice.invoice_no, invoice.name,
                                   invoice.sent_at.astimezone(localtz).strftime('%d/%m/%Y'), invoice_url
                                   )
                       )
                send_mail(email, title, message)
                if not current_app.debug:

                    for a in admins:
                        if a.is_supervisor:
                            try:
                                line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                            except LineBotApiError:
                                pass
                else:
                    print('message_email', message, 'message_line', msg)
    db.session.add(invoice)
    db.session.commit()
    flash('อนุมัติใบแจ้งหนี้สำเร็จ', 'success')
    return redirect(url_for('service_admin.invoice_index', menu=menu, tab=tab))


@service_admin.route('/invoice/file/add/<int:invoice_id>', methods=['GET', 'POST'])
def upload_invoice_file(invoice_id):
    tab = request.args.get('tab')
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
            # contact_email = invoice.quotation.request.customer.contact_email if invoice.quotation.request.customer.contact_email else invoice.quotation.request.customer.email
            org = Org.query.filter_by(name='หน่วยการเงินและบัญชี').first()
            staff = StaffAccount.get_account_by_email(org.head)
            invoice_url = url_for("academic_services.view_invoice", invoice_id=invoice.id, menu='invoice',
                                  tab='pending', _external=True, _scheme=scheme)
            msg = (f'แจ้งออกใบแจ้งหนี้เลขที่ {invoice.invoice_no}\n\n'
                   f'เรียน ฝ่ายการเงิน\n\n'
                   f'หน่วยงาน{invoice.quotation.request.sub_lab.sub_lab} ได้ดำเนินการออกใบแจ้งหนี้เลขที่ {invoice.invoice_no} เรียบร้อยแล้ว\n'
                   f'วันที่ออก : {invoice.file_attached_at.strftime("%d/%m/%Y")}\n'
                   f'จำนวนเงิน : {invoice.grand_total:,.2f} บาท\n'
                   f'กรุณาดำเนินการตรวจสอบและเตรียมออกใบเสร็จรับเงินเมื่อได้รับการชำระเงินจากลูกค้าตามขั้นตอนที่กำหนด\n\n'
                   f'ขอบคุณค่ะ\n'
                   f'ระบบงานบริการวิชาการ'
                   )
            title = f'''แจ้งออกใบแจ้งหนี้'''
            message = f'''เรียน {title_prefix}{invoice.customer_name}\n\n'''
            message += f'''ตามที่ท่านใช้บริการจากหน่วยงานตรวจวิเคราะห์ของคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล\nขณะนี้ทางเจ้าหน้าที่ได้ดำเนินการออกใบแจ้งหนี้เลขที่ {invoice.invoice_no} เรียบร้อยแล้ว\n'''
            message += f'''กรุณาดำเนินการชำระเงินภายใน 30 วันนับจากวันที่ออกใบแจ้งหนี้ โดยท่านสามารถตรวจสอบรายละเอียดใบแจ้งหนี้ได้จากลิงก์ด้านล่าง\n'''
            message += f'''{invoice_url}\n\n'''
            message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
            message += f'''ขอขอบพระคุณที่ใช้บริการ\n'''
            message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
            message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
            if not current_app.debug:
                send_mail([invoice.quotation.request.customer.email], title, message)
                try:
                    line_bot_api.push_message(to=staff.line_id, messages=TextSendMessage(text=msg))
                except LineBotApiError:
                    pass
            else:
                print('message_email', message, 'message_line', msg)
            flash('บันทึกข้อมูลสำเร็จ', 'success')
            return redirect(url_for('service_admin.invoice_index_for_central_admin', menu=menu, tab='waiting_payment'))
        else:
            flash('กรุณาอัปโหลดไฟล์', 'danger')
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('service_admin/upload_invoice_file.html', form=form, invoice_id=invoice_id,
                           menu=menu, invoice=invoice, tab=tab)


@service_admin.route('/invoice/view/<int:invoice_id>', methods=['GET'])
@login_required
def view_invoice(invoice_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    invoice = ServiceInvoice.query.get(invoice_id)
    admin_lab = (
        ServiceAdmin.query
        .join(ServiceSubLab)
        .filter(ServiceSubLab.code == invoice.quotation.request.sub_lab.code, ServiceAdmin.admin_id == current_user.id)
        .all()
    )
    admin = any(a for a in admin_lab if not a.is_supervisor)
    supervisor = any(a for a in admin_lab if a.is_supervisor)
    assistant = any(a for a in admin_lab if a.is_assistant)
    dean = invoice.quotation.request.sub_lab.signer if invoice.quotation.request.sub_lab.signer_id == current_user.id else None
    central_admin = any(a for a in admin_lab if a.is_central_admin)
    return render_template('service_admin/view_invoice.html', invoice=invoice, admin=admin, menu=menu,
                           supervisor=supervisor, assistant=assistant, dean=dean, central_admin=central_admin, tab=tab)


@service_admin.route('/central_admin/invoice/view/<int:invoice_id>', methods=['GET'])
@login_required
def view_invoice_for_central_admin(invoice_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    invoice = ServiceInvoice.query.get(invoice_id)
    return render_template('service_admin/view_invoice_for_central_admin.html', invoice=invoice,
                           menu=menu, tab=tab)


def generate_invoice_pdf(invoice, qr_image_base64=None):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 70, 70)

    def all_page_setup(canvas, doc):
        canvas.saveState()
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

    affiliation = '''<para><font size=11>
                           คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>
                           999 ต.ศาลายา อ.พุทธมณฑล จ.นครปฐม 73170<br/>
                           โทร 0-2441-4371-9 ต่อ 2820 2830<br/>
                           เลขประจำตัวผู้เสียภาษี 0994000158378
                           </font></para>
                           '''

    invoice_no = '''<br/><br/><font size=14>
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

    detail_style = ParagraphStyle(
        'DetailStyle',
        parent=style_sheet['ThaiStyle'],
        leading=20
    )

    customer = '''<para><font size=14>
                    ที่ <br/>
                    วันที่ <br/>
                    เรื่อง ใบแจ้งหนี้ค่าบริการตรวจวิเคราะห์ทางห้องปฏิบัติการ{lab}<br/>
                    เรียน {customer}<br/>
                    ที่อยู่ {address}<br/>
                    เลขประจำตัวผู้เสียภาษี {taxpayer_identification_no}
                    </font></para>
                    '''.format(lab=invoice.quotation.request.sub_lab.lab.lab, customer=invoice.name,
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
        Paragraph('<font size=13>รวมเป็นเงินทั้งสิ้น/Grand Total ({})</font>'.format(bahttext(invoice.grand_total)),
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
        Paragraph('<font size=12>{:,.2f}</font>'.format(invoice.grand_total), style=bold_style),
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
        ('VALIGN', (0, 0), (-1, -4), 'TOP'),
        ('VALIGN', (0, -3), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -4), (-1, -4), 9),
        ('BOTTOMPADDING', (0, -3), (-1, -1), 7)
    ]))

    head_remark_style = ParagraphStyle(
        'HeadRemarkStyle',
        parent=style_sheet['ThaiStyleBold'],
        fontSize=10,
        leading=13
    )

    remark_style = ParagraphStyle(
        'ThaiStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=8,
        leading=13
    )
    remark_table = Table([
        [Paragraph("<font size=14>หมายเหตุ/Remark<br/></font>", style=head_remark_style)],
        [Paragraph(
            "<font size=12>1. โปรดโอนเงินเข้าบัญชีออมทรัพย์ ในนาม <u>งานบริการ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล"
            "เลขที่บัญชี 016-433468-4</u>"
            "หรือ<u> Scan QR Code ด้านล่าง</u> หรือ <u>โปรดสั่งจ่ายเช็คในนาม มหาวิทยาลัยมหิดล</u><br/></font>",
            style=remark_style)],
        [Paragraph(
            "<font size=12>2. จัดส่งหลักฐานการชำระเงินผ่านทาง <u>Scan QR Code</u> ด้านล่าง<br/></font>",
            style=remark_style)],
        [Paragraph(
            "<font size=12>3. โปรดชำระค่าบริการตรวจวิเคราะห์ทางห้องปฏิบัติการ <u><b>ภายใน 30 วัน</b></u> นับถัดจากวันที่ลงนามใน"
            "หนังสือแจ้งชำระค่าบริการฉบับนี้<br/></font>", style=remark_style)],
        [Paragraph(
            "<font size=12>4. โปรดตรวจสอบรายละเอียดข้อมูลการชำระเงิน หากพบข้อมูลไม่ถูกต้อง โปรดทำหนังสือแจ้งกลับมายัง <u><b>หน่วย"
            "การเงินและบัญชี งานคลังและพัสดุ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล</b></u><br/></font>",
            style=remark_style)],
        [Paragraph("<font size=12>5. <u>หากชำระเงินแล้วจะไม่สามารถขอเงินคืนได้</u><br/></font>",
                   style=remark_style)],
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
    scheme = 'http' if current_app.debug else 'https'
    qr_payment_buffer = BytesIO()
    qr_payment_img = qrcode.make(url_for('academic_services.add_payment', invoice_id=invoice.id, menu='invoice',
                                         tab='pending', _external=True, _scheme=scheme))
    qr_payment_img.save(qr_payment_buffer, format='PNG')
    qr_code_payment = Image(qr_payment_buffer, width=105, height=102)

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

    data.append(KeepTogether(Spacer(30, 30)))
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

        qr_code_payment_text = Paragraph("QR Code<br/>แจ้งการโอนเงิน", style=style_sheet['ThaiStyleCenter'])
        qr_code_payment_table = Table([[qr_code_payment], [qr_code_payment_text]], colWidths=[150])
        qr_code_payment_table.hAlign = 'LEFT'

        qr_code_payment_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (0, 0), -3),
            ('TOPPADDING', (0, 1), (0, 1), -3),
        ]))

        combined_table = Table(
            [[qr_code_table, qr_code_payment_table, sign_table]],
            colWidths=[130, 130, 350]
        )
        combined_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (0, 0), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('VALIGN', (1, 0), (1, 0), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (2, 0), (2, 0), 60),
        ]))

        combined_table.hAlign = 'LEFT'
        combined_table.leftIndent = 200

        data.append(Spacer(1, 16))
        data.append(KeepTogether(combined_table))
    else:
        data.append(KeepTogether(Spacer(1, 16)))
        data.append(KeepTogether(sign_table))

    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    buffer.seek(0)
    return buffer


@service_admin.route('/invoice/pdf/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
def export_invoice_pdf(invoice_id):
    is_download = request.args.get('is_download', 'false')
    invoice = ServiceInvoice.query.get(invoice_id)
    sub_lab = ServiceSubLab.query.filter_by(code=invoice.quotation.request.sub_lab.code).first()
    ref1 = invoice.invoice_no
    ref2 = sub_lab.ref.upper()
    qrcode_data = generate_qrcode(amount=invoice.grand_total, ref1=ref1, ref2=ref2, ref3=None)

    if qrcode_data:
        qr_image_base64 = qrcode_data['qrImage']
    else:
        qr_image_base64 = None
    buffer = generate_invoice_pdf(invoice, qr_image_base64=qr_image_base64)
    if is_download == 'true' and not invoice.downloaded_at:
        invoice.downloaded_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(invoice)
        db.session.commit()
    return send_file(buffer, download_name='Invoice.pdf', as_attachment=True)


@service_admin.route('/payment/add', methods=['GET', 'POST'])
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
                invoice.quotation.request.status_id = status_id
                db.session.add(invoice)
                db.session.commit()
                scheme = 'http' if current_app.debug else 'https'
                org = Org.query.filter_by(name='หน่วยการเงินและบัญชี').first()
                staff = StaffAccount.get_account_by_email(org.head)
                title_prefix = 'คุณ' if invoice.quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
                link = url_for("service_admin.view_invoice_for_finance", invoice_id=invoice_id, _external=True,
                               _scheme=scheme)
                customer_name = invoice.customer_name.replace(' ', '_')
                title = f'''แจ้งอัปเดตการชำระเงิน'''
                message = f'''เรียน เจ้าหน้าที่การเงิน\n\n'''
                message += f'''ใบแจ้งหนี้เลขที่ {invoice.invoice_no} ของลูกค้า {invoice.customer_name}\n'''
                message += f'''ในนาม {invoice.name} จากหน่วยงาน {invoice.quotation.request.sub_lab.lab.lab}\n'''
                message += f'''จำนวนเงิน {invoice.grand_total:,.2f} บาท ได้มีการอัปเดตสถานะการชำระเงินเรียบร้อยแล้ว\n'''
                message += f'''ท่านสามารถตรวจสอบรายละเอียดการชำระเงินได้ที่ลิงก์ด้านล่าง\n'''
                message += f'''{link}\n\n'''
                # message += f'''ผู้ประสานงาน\n'''
                # message += f'''{invoice.customer_name}\n'''
                # message += f'''เบอร์โทร {invoice.contact_phone_number}\n\n'''
                message += f'''ระบบงานบริการวิชาการ'''
                if invoice.paid_at:
                    msg = ('ใบแจ้งหนี้เลขที่ {}\n' \
                           'ออกในนาม {}\n' \
                           'ณ วันที่ {} รอดำเนินการตรวจสอบการชำระเงิน\n' \
                           'กรุณาดำเนินการตรวจสอบในระบบ\n'
                           'คลิกลิ้งค์เพื่อดำเนินการ\n'
                           '{}'.format(invoice.invoice_no, invoice.name,
                                       invoice.paid_at.astimezone(localtz).strftime(
                                           '%d/%m/%Y'), link))
                else:
                    msg = ('ใบแจ้งหนี้เลขที่ {}\n' \
                           'ออกในนาม {}\n' \
                           'รอดำเนินการตรวจสอบการชำระเงิน\n' \
                           'กรุณาดำเนินการตรวจสอบในระบบ\n'
                           'คลิกลิ้งค์เพื่อดำเนินการ\n'
                           '{}'.format(invoice.invoice_no, invoice.name, link)
                           )
                if not current_app.debug:
                    send_mail([staff.email + '@mahidol.ac.th'], title, message)
                    try:
                        line_bot_api.push_message(to=staff.line_id, messages=TextSendMessage(text=msg))
                    except LineBotApiError:
                        pass
                else:
                    print('message_email', message, 'message_line', msg)
                flash('อัปโหลดหลักฐานการชำระเงินสำเร็จ', 'success')
                return redirect(url_for('service_admin.invoice_index_for_central_admin', menu=menu, tab=tab))
            else:
                flash('กรุณาอัปโหลดไฟล์ให้ถูกต้อง', 'danger')
        else:
            flash('กรุณากรอกวันที่ชำระเงิน, วิธีการชำระเงิน, จำนวนเงิน และหลักฐานการชำระเงิน', 'danger')
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('service_admin/add_payment.html', menu=menu, form=form, invoice=invoice,
                           tab=tab)


@service_admin.route('/quotation/index')
@login_required
def quotation_index():
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    api = request.args.get('api', 'false')
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    is_admin = any(a for a in admin if not a.is_supervisor)
    is_supervisor = any(a.is_supervisor for a in admin)
    query = (
        ServiceQuotation.query
        .join(ServiceQuotation.request)
        .join(ServiceRequest.sub_lab)
        .join(ServiceSubLab.admins)
        .filter(
            ServiceAdmin.admin_id == current_user.id
        )
    )
    draft_query = query.filter(ServiceQuotation.sent_at == None)
    pending_approval_for_supervisor_query = query.filter(ServiceQuotation.sent_at != None,
                                                         ServiceQuotation.approved_at == None,
                                                         ServiceQuotation.disapproved_at == None)
    pending_confirm_for_customer_query = query.filter(ServiceQuotation.approved_at != None,
                                                      ServiceQuotation.confirmed_at == None,
                                                      ServiceQuotation.cancelled_at == None)
    confirm_query = query.filter(ServiceQuotation.confirmed_at != None)
    cancel_query = query.filter(ServiceQuotation.cancelled_at != None)
    if api == 'true':
        if tab == 'draft':
            query = draft_query
        elif tab == 'pending_supervisor_approval' or tab == 'pending_approval':
            query = pending_approval_for_supervisor_query
        elif tab == 'awaiting_customer':
            query = pending_confirm_for_customer_query
        elif tab == 'confirmed':
            query = confirm_query
        elif tab == 'reject':
            query = cancel_query

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
    return render_template('service_admin/quotation_index.html', tab=tab, menu=menu, is_admin=is_admin,
                           is_supervisor=is_supervisor, draft_count=draft_query.count(),
                           pending_confirm_for_customer_count=pending_confirm_for_customer_query.count(),
                           pending_approval_for_supervisor_count=pending_approval_for_supervisor_query.count())


# @service_admin.route('/quotation/generate', methods=['GET', 'POST'])
# @login_required
# def generate_quotation():
#     menu = request.args.get('menu')
#     request_id = request.args.get('request_id')
#     service_request = ServiceRequest.query.get(request_id)
#     quotation = ServiceQuotation.query.filter_by(request_id=request_id).first()
#     if not quotation:
#         sheet_price_id = '1hX0WT27oRlGnQm997EV1yasxlRoBSnhw3xit1OljQ5g'
#         gc = get_credential(json_keyfile)
#         wksp = gc.open_by_key(sheet_price_id)
#         sheet_price = wksp.worksheet(service_request.sub_lab.code)
#         df_price = pandas.DataFrame(sheet_price.get_all_records())
#         quote_column_names = {}
#         quote_details = {}
#         quote_prices = {}
#         count_value = Counter()
#         data = service_request.data
#         for _, row in df_price.iterrows():
#             if service_request.sub_lab.code == 'quantitative':
#                 quote_column_names[row['field_group']] = set(row['field_name'].split(', '))
#             else:
#                 if row['field_group'] not in quote_column_names:
#                     quote_column_names[row['field_group']] = set()
#                 for field_name in row['field_name'].split(','):
#                     quote_column_names[row['field_group']].add(field_name.strip())
#             key = ''.join(sorted(row[4:].str.cat())).replace(' ', '')
#             if service_request.customer.customer_info.type.type == 'หน่วยงานรัฐ':
#                 quote_prices[key] = row['government_price']
#             else:
#                 quote_prices[key] = row['other_price']
#
#         if service_request.sub_lab.code == 'air_disinfection':
#             test_methods = []
#             surface_fields = data.get('surface_condition_field', {}).get('surface_disinfection_organism_fields', [])
#             airborne_fields = data.get('airborne_disinfection_organism', {}).get(
#                 'airborne_disinfection_organism_fields', [])
#
#             if surface_fields:
#                 for f in surface_fields:
#                     organisms = f.get('surface_disinfection_organism', '')
#                     period_tests = f.get('surface_disinfection_period_test', '')
#                     for organism in organisms:
#                         if organism and period_tests:
#                             test_methods.append((organism, period_tests))
#                     for _, row in df_price.iterrows():
#                         organism_rows = row['surface_disinfection_organism']
#                         period_test_rows = row['surface_disinfection_period_test']
#                         if (organism_rows, period_test_rows) in test_methods:
#                             p_key = ''.join(sorted(f"{organism_rows}{period_test_rows}".replace(' ', '')))
#                             values = f"<i>{organism_rows}</i> {period_test_rows}"
#                             price = quote_prices.get(p_key, 0)
#                             quote_details[p_key] = {"value": values, "price": price, "quantity": 1}
#             else:
#                 for f in airborne_fields:
#                     organisms = f.get('airborne_disinfection_organism', '')
#                     period_tests = f.get('airborne_disinfection_period_test', '')
#                     for organism in organisms:
#                         if organism and period_tests:
#                             test_methods.append((organism, period_tests))
#                     for _, row in df_price.iterrows():
#                         organism_rows = row['airborne_disinfection_organism']
#                         period_test_rows = row['airborne_disinfection_period_test']
#                         if (organism_rows, period_test_rows) in test_methods:
#                             p_key = ''.join(sorted(f"{organism_rows}{period_test_rows}".replace(' ', '')))
#                             values = f"<i>{organism_rows}</i> {period_test_rows}"
#                             price = quote_prices.get(p_key, 0)
#                             quote_details[p_key] = {"value": values, "price": price, "quantity": 1}
#         else:
#             if service_request.sub_lab.code == 'bacteria':
#                 form = BacteriaRequestForm(data=data)
#             elif service_request.sub_lab.code == 'disinfection':
#                 form = VirusDisinfectionRequestForm(data=data)
#             else:
#                 form = VirusAirDisinfectionRequestForm(data=data)
#             for field in form:
#                 if field.label.text not in quote_column_names:
#                     continue
#                 keys = []
#                 keys = walk_form_fields(field, quote_column_names[field.label.text], keys=keys)
#                 for r in range(1, len(quote_column_names[field.label.text]) + 1):
#                     for key in itertools.combinations(keys, r):
#                         sorted_key_ = sorted(''.join([k[1] for k in key]))
#                         p_key = ''.join(sorted_key_).replace(' ', '')
#                         values = ', '.join(
#                             [f"<i>{k[1]}</i>" if "organism" in k[0] and k[1] != "None" else k[1] for k in key]
#                         )
#                         count_value.update(values.split(', '))
#                         quantities = (
#                             ', '.join(str(count_value[v]) for v in values.split(', '))
#                             if ((service_request.sub_lab.code not in ['bacteria', 'disinfection', 'air_disinfection']))
#                             else 1
#                         )
#                         if service_request.sub_lab.code == 'endotoxin':
#                             for k in key:
#                                 if not k[1]:
#                                     break
#                                 for price in quote_prices.values():
#                                     quote_details[p_key] = {"value": values, "price": price, "quantity": quantities}
#                         else:
#                             if p_key in quote_prices:
#                                 prices = quote_prices[p_key]
#                                 quote_details[p_key] = {"value": values, "price": prices, "quantity": quantities}
#         quotation_no = ServiceNumberID.get_number('Quotation', db, lab=service_request.sub_lab.ref)
#         quotation = ServiceQuotation(quotation_no=quotation_no.number, request_id=request_id,
#                                      name=service_request.quotation_name,
#                                      address=service_request.quotation_issue_address,
#                                      taxpayer_identification_no=service_request.taxpayer_identification_no,
#                                      creator=current_user, created_at=arrow.now('Asia/Bangkok').datetime)
#         db.session.add(quotation)
#         quotation_no.count += 1
#         status_id = get_status(3)
#         service_request.status_id = status_id
#         db.session.add(service_request)
#         db.session.commit()
#         sequence_no = ServiceSequenceQuotationID.get_number('QT', db, quotation='quotation_' + str(quotation.id))
#         for _, (_, item) in enumerate(quote_details.items()):
#             quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
#                                                   item=item['value'],
#                                                   quantity=item['quantity'],
#                                                   unit_price=item['price'],
#                                                   total_price=int(item['quantity']) * item['price'])
#             sequence_no.count += 1
#             db.session.add(quotation_item)
#             db.session.commit()
#         if service_request.report_languages:
#             for rl in service_request.report_languages:
#                 quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
#                                                       item=rl.report_language.item,
#                                                       quantity=1,
#                                                       unit_price=rl.report_language.price,
#                                                       total_price=rl.report_language.price)
#                 sequence_no.count += 1
#                 db.session.add(quotation_item)
#                 db.session.commit()
#         flash('ร่างใบเสนอราคาสำเร็จ กรุณาดำเนินการตรวจสอบข้อมูล', 'success')
#         return redirect(
#             url_for('service_admin.create_quotation_for_admin', quotation_id=quotation.id, tab='draft', menu=menu))
#     else:
#         return render_template('service_admin/quotation_created_confirmation_page.html',
#                                quotation_id=quotation.id, request_no=service_request.request_no, menu=menu)


@service_admin.route('/quotation/generate')
@login_required
def generate_quotation():
   code = request.args.get('code')
   menu = request.args.get('menu')
   request_id = request.args.get('request_id')
   request_paths = {'bacteria': 'service_admin.generate_bacteria_quotation',
                    'disinfection': 'service_admin.generate_virus_disinfection_quotation',
                    'air_disinfection': 'service_admin.generate_virus_air_disinfection_quotation',
                    'heavymetal': 'service_admin.generate_heavy_metal_quotation',
                    'foodsafety': 'service_admin.generate_food_safety_quotation',
                    'protein_identification': 'service_admin.generate_protein_identification_quotation',
                    'sds_page': 'service_admin.generate_sds_page_quotation',
                    'quantitative': 'service_admin.generate_quantitative_quotation',
                    'endotoxin': 'service_admin.generate_endotoxin_quotation',
                    'toxicology': 'service_admin.generate_toxicology_quotation'
                    }
   return redirect(url_for(request_paths[code], menu=menu, request_id=request_id))


@service_admin.route('/quotation/bacteria/generate', methods=['GET', 'POST'])
def generate_bacteria_quotation():
    menu = request.args.get('menu')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    quotation = ServiceQuotation.query.filter_by(request_id=request_id, disapproved_at=None).first()
    if not quotation:
        sheet_price_id = '1hX0WT27oRlGnQm997EV1yasxlRoBSnhw3xit1OljQ5g'
        gc = get_credential(json_keyfile)
        wksp = gc.open_by_key(sheet_price_id)
        sheet_price = wksp.worksheet(service_request.sub_lab.code)
        df_price = pandas.DataFrame(sheet_price.get_all_records())
        quote_column_names = {}
        quote_details = {}
        quote_prices = {}
        data = service_request.data
        form = BacteriaRequestForm(data=data)

        for _, row in df_price.iterrows():
            if row['field_group'] not in quote_column_names:
                quote_column_names[row['field_group']] = set()
            for field_name in row['field_name'].split(','):
                quote_column_names[row['field_group']].add(field_name.strip())
            key = ''.join(sorted(row[4:].str.cat())).replace(' ', '')
            if service_request.customer.customer_info.type.type == 'หน่วยงานรัฐ':
                quote_prices[key] = row['government_price']
            else:
                quote_prices[key] = row['other_price']

        for field in form:
            if field.label.text not in quote_column_names:
                continue
            keys = []
            keys = walk_form_fields(field, quote_column_names[field.label.text], keys=keys)
            for key in list(itertools.combinations(keys, len(quote_column_names[field.label.text]))):
                sorted_key_ = sorted(''.join([k[1] for k in key]))
                p_key = ''.join(sorted_key_).replace(' ', '')
                values = ', '.join(
                    [f"<i>{k[1]}</i>" if "organism" in k[0] and k[1] != "None" else k[1] for k in key])

                if p_key in quote_prices:
                    prices = quote_prices[p_key]
                    if p_key in quote_details:
                        quote_details[p_key]["quantity"] += 1
                    else:
                        quote_details[p_key] = {"value": values, "price": prices, "quantity": 1}
        quotation_no = ServiceNumberID.get_number('Quotation', db, lab=service_request.sub_lab.ref)
        quotation = ServiceQuotation(quotation_no=quotation_no.number, request_id=request_id,
                                     name=service_request.quotation_name,
                                     address=service_request.quotation_issue_address,
                                     taxpayer_identification_no=service_request.taxpayer_identification_no,
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
                quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                      item=rl.report_language.item,
                                                      quantity=1,
                                                      unit_price=rl.report_language.price,
                                                      total_price=rl.report_language.price)
                sequence_no.count += 1
                db.session.add(quotation_item)
                db.session.commit()
        flash('ร่างใบเสนอราคาสำเร็จ กรุณาดำเนินการตรวจสอบข้อมูล', 'success')
        return redirect(
            url_for('service_admin.create_quotation_for_admin', quotation_id=quotation.id, tab='draft', menu=menu))
    else:
        return render_template('service_admin/quotation_created_confirmation_page.html',
                               quotation_id=quotation.id, request_no=service_request.request_no, menu=menu)


@service_admin.route('/quotation/virus/disinfection/generate', methods=['GET', 'POST'])
def generate_virus_disinfection_quotation():
    menu = request.args.get('menu')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    quotation = ServiceQuotation.query.filter_by(request_id=request_id, disapproved_at=None).first()
    if not quotation:
        sheet_price_id = '1hX0WT27oRlGnQm997EV1yasxlRoBSnhw3xit1OljQ5g'
        gc = get_credential(json_keyfile)
        wksp = gc.open_by_key(sheet_price_id)
        sheet_price = wksp.worksheet(service_request.sub_lab.code)
        df_price = pandas.DataFrame(sheet_price.get_all_records())
        quote_column_names = {}
        quote_details = {}
        quote_prices = {}
        data = service_request.data
        form = VirusDisinfectionRequestForm(data=data)

        for _, row in df_price.iterrows():
            if row['field_group'] not in quote_column_names:
                quote_column_names[row['field_group']] = set()
            for field_name in row['field_name'].split(','):
                quote_column_names[row['field_group']].add(field_name.strip())
            sorted_field_group = ''.join(sorted(row['field_group'])).replace(' ', '')
            key = sorted_field_group + ''.join(sorted(row[4:].str.cat())).replace(' ', '')
            if service_request.customer.customer_info.type.type == 'หน่วยงานรัฐ':
                quote_prices[key] = row['government_price']
            else:
                quote_prices[key] = row['other_price']

        for field in form:
            if field.label.text not in quote_column_names:
                continue
            keys = []
            keys = walk_form_fields(field, quote_column_names[field.label.text], keys=keys)
            for key in list(itertools.combinations(keys, len(quote_column_names[field.label.text]))):
                sorted_field_label = ''.join(sorted(field.label.text)).replace(' ', '')
                sorted_key_ = sorted(''.join([k[1] for k in key]))
                p_key = sorted_field_label + ''.join(sorted_key_).replace(' ', '')
                values = ', '.join(
                    [f"<i>{k[1]}</i>" if "organism" in k[0] and k[1] != "None" else k[1] for k in key])
                if p_key in quote_prices:
                    prices = quote_prices[p_key]
                    if p_key in quote_details:
                        quote_details[p_key]["quantity"] += 1
                    else:
                        quote_details[p_key] = {"value": values, "price": prices, "quantity": 1}
        quotation_no = ServiceNumberID.get_number('Quotation', db, lab=service_request.sub_lab.ref)
        quotation = ServiceQuotation(quotation_no=quotation_no.number, request_id=request_id,
                                     name=service_request.quotation_name,
                                     address=service_request.quotation_issue_address,
                                     taxpayer_identification_no=service_request.taxpayer_identification_no,
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
                quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                      item=rl.report_language.item,
                                                      quantity=1,
                                                      unit_price=rl.report_language.price,
                                                      total_price=rl.report_language.price)
                sequence_no.count += 1
                db.session.add(quotation_item)
                db.session.commit()
        flash('ร่างใบเสนอราคาสำเร็จ กรุณาดำเนินการตรวจสอบข้อมูล', 'success')
        return redirect(
            url_for('service_admin.create_quotation_for_admin', quotation_id=quotation.id, tab='draft', menu=menu))
    else:
        return render_template('service_admin/quotation_created_confirmation_page.html',
                               quotation_id=quotation.id, request_no=service_request.request_no, menu=menu)


@service_admin.route('/quotation/virus/air_disinfection/generate', methods=['GET', 'POST'])
@login_required
def generate_virus_air_disinfection_quotation():
    menu = request.args.get('menu')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    quotation = ServiceQuotation.query.filter_by(request_id=request_id, disapproved_at=None).first()
    if not quotation:
        sheet_price_id = '1hX0WT27oRlGnQm997EV1yasxlRoBSnhw3xit1OljQ5g'
        gc = get_credential(json_keyfile)
        wksp = gc.open_by_key(sheet_price_id)
        sheet_price = wksp.worksheet(service_request.sub_lab.code)
        df_price = pandas.DataFrame(sheet_price.get_all_records())
        quote_column_names = {}
        quote_details = {}
        quote_prices = {}
        data = service_request.data
        form = VirusAirDisinfectionRequestForm(data=data)

        for _, row in df_price.iterrows():
            if row['field_group'] not in quote_column_names:
                quote_column_names[row['field_group']] = set()
            for field_name in row['field_name'].split(','):
                quote_column_names[row['field_group']].add(field_name.strip())
            sorted_field_group = ''.join(sorted(row['field_group'])).replace(' ', '')
            key = sorted_field_group + ''.join(sorted(row[4:].str.cat())).replace(' ', '')
            if service_request.customer.customer_info.type.type == 'หน่วยงานรัฐ':
                quote_prices[key] = row['government_price']
            else:
                quote_prices[key] = row['other_price']

        for field in form:
            if field.label.text not in quote_column_names:
                continue
            keys = []
            keys = walk_form_fields(field, quote_column_names[field.label.text], keys=keys)
            for key in list(itertools.combinations(keys, len(quote_column_names[field.label.text]))):
                sorted_field_label = ''.join(sorted(field.label.text)).replace(' ', '')
                sorted_key_ = sorted(''.join([k[1] for k in key]))
                p_key = sorted_field_label + ''.join(sorted_key_).replace(' ', '')
                values = ', '.join(
                    [f"<i>{k[1]}</i>" if "organism" in k[0] and k[1] != "None" else k[1] for k in key])
                if p_key in quote_prices:
                    prices = quote_prices[p_key]
                    if p_key in quote_details:
                        quote_details[p_key]["quantity"] += 1
                    else:
                        quote_details[p_key] = {"value": values, "price": prices, "quantity": 1}
        quotation_no = ServiceNumberID.get_number('Quotation', db, lab=service_request.sub_lab.ref)
        quotation = ServiceQuotation(quotation_no=quotation_no.number, request_id=request_id,
                                     name=service_request.quotation_name,
                                     address=service_request.quotation_issue_address,
                                     taxpayer_identification_no=service_request.taxpayer_identification_no,
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
                quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                      item=rl.report_language.item,
                                                      quantity=1,
                                                      unit_price=rl.report_language.price,
                                                      total_price=rl.report_language.price)
                sequence_no.count += 1
                db.session.add(quotation_item)
                db.session.commit()
        flash('ร่างใบเสนอราคาสำเร็จ กรุณาดำเนินการตรวจสอบข้อมูล', 'success')
        return redirect(
            url_for('service_admin.create_quotation_for_admin', quotation_id=quotation.id, tab='draft', menu=menu))
    else:
        return render_template('service_admin/quotation_created_confirmation_page.html',
                               quotation_id=quotation.id, request_no=service_request.request_no, menu=menu)


@service_admin.route('/quotation/heavy_metal/generate', methods=['GET', 'POST'])
def generate_heavy_metal_quotation():
    menu = request.args.get('menu')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    quotation = ServiceQuotation.query.filter_by(request_id=request_id, disapproved_at=None).first()
    if not quotation:
        sheet_price_id = '1hX0WT27oRlGnQm997EV1yasxlRoBSnhw3xit1OljQ5g'
        gc = get_credential(json_keyfile)
        wksp = gc.open_by_key(sheet_price_id)
        sheet_price = wksp.worksheet(service_request.sub_lab.code)
        df_price = pandas.DataFrame(sheet_price.get_all_records())
        quote_column_names = {}
        quote_details = {}
        quote_prices = {}
        data = service_request.data
        form = HeavyMetalRequestForm(data=data)

        for _, row in df_price.iterrows():
            if row['field_group'] not in quote_column_names:
                quote_column_names[row['field_group']] = set()
            for field_name in row['field_name'].split(','):
                quote_column_names[row['field_group']].add(field_name.strip())
            sorted_field_group = ''.join(sorted(row['field_group'])).replace(' ', '')
            key = sorted_field_group + ''.join(sorted(row[4:].str.cat())).replace(' ', '')
            if service_request.customer.customer_info.type.type == 'หน่วยงานรัฐ':
                quote_prices[key] = row['government_price']
            else:
                quote_prices[key] = row['other_price']
        for field in form:
            if field.label.text not in quote_column_names:
                continue

            keys = []
            keys = walk_form_fields(field, quote_column_names[field.label.text], keys=keys)
            for key in list(itertools.combinations(keys, len(quote_column_names[field.label.text]))):
                sorted_field_label = ''.join(sorted(field.label.text)).replace(' ', '')
                sorted_key_ = sorted(''.join([k[1] for k in key]))
                p_key = sorted_field_label + ''.join(sorted_key_).replace(' ', '')
                values = ', '.join([k[1] for k in key])
                if p_key in quote_prices:
                    prices = quote_prices[p_key]
                    if p_key in quote_details:
                        quote_details[p_key]["quantity"] += 1
                    else:
                        quote_details[p_key] = {"value": values, "price": prices, "quantity": 1}
        quotation_no = ServiceNumberID.get_number('Quotation', db, lab=service_request.sub_lab.ref)
        quotation = ServiceQuotation(quotation_no=quotation_no.number, request_id=request_id,
                                     name=service_request.quotation_name,
                                     address=service_request.quotation_issue_address,
                                     taxpayer_identification_no=service_request.taxpayer_identification_no,
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
                quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                      item=rl.report_language.item,
                                                      quantity=1,
                                                      unit_price=rl.report_language.price,
                                                      total_price=rl.report_language.price)
                sequence_no.count += 1
                db.session.add(quotation_item)
                db.session.commit()
        flash('ร่างใบเสนอราคาสำเร็จ กรุณาดำเนินการตรวจสอบข้อมูล', 'success')
        return redirect(
            url_for('service_admin.create_quotation_for_admin', quotation_id=quotation.id, tab='draft', menu=menu))
    else:
        return render_template('service_admin/quotation_created_confirmation_page.html',
                               quotation_id=quotation.id, request_no=service_request.request_no, menu=menu)


@service_admin.route('/quotation/food_safety/generate', methods=['GET', 'POST'])
def generate_food_safety_quotation():
    menu = request.args.get('menu')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    quotation = ServiceQuotation.query.filter_by(request_id=request_id, disapproved_at=None).first()
    if not quotation:
        sheet_price_id = '1hX0WT27oRlGnQm997EV1yasxlRoBSnhw3xit1OljQ5g'
        gc = get_credential(json_keyfile)
        wksp = gc.open_by_key(sheet_price_id)
        sheet_price = wksp.worksheet(service_request.sub_lab.code)
        df_price = pandas.DataFrame(sheet_price.get_all_records())
        quote_column_names = {}
        quote_details = {}
        quote_prices = {}
        data = service_request.data
        form = FoodSafetyRequestForm(data=data)

        for _, row in df_price.iterrows():
            if row['field_group'] not in quote_column_names:
                quote_column_names[row['field_group']] = set()
            for field_name in row['field_name'].split(','):
                quote_column_names[row['field_group']].add(field_name.strip())
            sorted_field_group = ''.join(sorted(row['field_group'])).replace(' ', '')
            key = sorted_field_group + ''.join(sorted(row[4:].str.cat())).replace(' ', '')
            if service_request.customer.customer_info.type.type == 'หน่วยงานรัฐ':
                quote_prices[key] = row['government_price']
            else:
                quote_prices[key] = row['other_price']

        for field in form:
            if field.label.text not in quote_column_names:
                continue

            keys = []
            keys = walk_form_fields(field, quote_column_names[field.label.text], keys=keys)
            for key in list(itertools.combinations(keys, len(quote_column_names[field.label.text]))):
                sorted_field_label = ''.join(sorted(field.label.text)).replace(' ', '')
                sorted_key_ = sorted(''.join([k[1] for k in key]))
                values = ', '.join([k[1] for k in key])
                if field.label.text == 'Food Safety Condition Field':
                    p_key = sorted_field_label
                    unique_key = f"{p_key}_{values}"
                else:
                    p_key = sorted_field_label + ''.join(sorted_key_).replace(' ', '')
                    unique_key = p_key

                if p_key in quote_prices:
                    prices = quote_prices[p_key]

                    if unique_key in quote_details:
                        quote_details[unique_key]["quantity"] += 1
                    else:
                        quote_details[unique_key] = {"value": values, "price": prices, "quantity": 1}

        quotation_no = ServiceNumberID.get_number('Quotation', db, lab=service_request.sub_lab.ref)
        quotation = ServiceQuotation(quotation_no=quotation_no.number, request_id=request_id,
                                     name=service_request.quotation_name,
                                     address=service_request.quotation_issue_address,
                                     taxpayer_identification_no=service_request.taxpayer_identification_no,
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
                quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                      item=rl.report_language.item,
                                                      quantity=1,
                                                      unit_price=rl.report_language.price,
                                                      total_price=rl.report_language.price)
                sequence_no.count += 1
                db.session.add(quotation_item)
                db.session.commit()
        flash('ร่างใบเสนอราคาสำเร็จ กรุณาดำเนินการตรวจสอบข้อมูล', 'success')
        return redirect(
            url_for('service_admin.create_quotation_for_admin', quotation_id=quotation.id, tab='draft', menu=menu))
    else:
        return render_template('service_admin/quotation_created_confirmation_page.html',
                               quotation_id=quotation.id, request_no=service_request.request_no, menu=menu)


@service_admin.route('/quotation/protein_identification/generate', methods=['GET', 'POST'])
def generate_protein_identification_quotation():
    menu = request.args.get('menu')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    quotation = ServiceQuotation.query.filter_by(request_id=request_id, disapproved_at=None).first()
    if not quotation:
        sheet_price_id = '1hX0WT27oRlGnQm997EV1yasxlRoBSnhw3xit1OljQ5g'
        gc = get_credential(json_keyfile)
        wksp = gc.open_by_key(sheet_price_id)
        sheet_price = wksp.worksheet(service_request.sub_lab.code)
        df_price = pandas.DataFrame(sheet_price.get_all_records())
        quote_column_names = {}
        quote_details = {}
        quote_prices = {}
        data = service_request.data
        form = ProteinIdentificationRequestForm(data=data)

        for _, row in df_price.iterrows():
            if row['field_group'] not in quote_column_names:
                quote_column_names[row['field_group']] = set()
            for field_name in row['field_name'].split(','):
                quote_column_names[row['field_group']].add(field_name.strip())
            sorted_field_group = ''.join(sorted(row['field_group'])).replace(' ', '')
            key = sorted_field_group + ''.join(sorted(row[4:].str.cat())).replace(' ', '')
            if service_request.customer.customer_info.type.type == 'หน่วยงานรัฐ':
                quote_prices[key] = row['government_price']
            else:
                quote_prices[key] = row['other_price']
        for field in form:
            if field.label.text not in quote_column_names:
                continue

            keys = []
            keys = walk_form_fields(field, quote_column_names[field.label.text], keys=keys)
            for r in range(1, len(quote_column_names[field.label.text]) + 1):
                for key in itertools.combinations(keys, r):
                    sorted_field_label = ''.join(sorted(field.label.text)).replace(' ', '')
                    sorted_key_ = sorted(''.join([k[1] for k in key]))
                    p_key = sorted_field_label + ''.join(sorted_key_).replace(' ', '')
                    values = ', '.join([k[1] for k in key])

                    if p_key in quote_prices:
                        prices = quote_prices[p_key]
                        if p_key in quote_details:
                            quote_details[p_key]["quantity"] += 1
                        else:
                            quote_details[p_key] = {"value": values, "price": prices, "quantity": 1}
        quotation_no = ServiceNumberID.get_number('Quotation', db, lab=service_request.sub_lab.ref)
        quotation = ServiceQuotation(quotation_no=quotation_no.number, request_id=request_id,
                                     name=service_request.quotation_name,
                                     address=service_request.quotation_issue_address,
                                     taxpayer_identification_no=service_request.taxpayer_identification_no,
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
                quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                      item=rl.report_language.item,
                                                      quantity=1,
                                                      unit_price=rl.report_language.price,
                                                      total_price=rl.report_language.price)
                sequence_no.count += 1
                db.session.add(quotation_item)
                db.session.commit()
        flash('ร่างใบเสนอราคาสำเร็จ กรุณาดำเนินการตรวจสอบข้อมูล', 'success')
        return redirect(
            url_for('service_admin.create_quotation_for_admin', quotation_id=quotation.id, tab='draft', menu=menu))
    else:
        return render_template('service_admin/quotation_created_confirmation_page.html',
                               quotation_id=quotation.id, request_no=service_request.request_no, menu=menu)


@service_admin.route('/quotation/sds_page/generate', methods=['GET', 'POST'])
def generate_sds_page_quotation():
   menu = request.args.get('menu')
   request_id = request.args.get('request_id')
   service_request = ServiceRequest.query.get(request_id)
   quotation = ServiceQuotation.query.filter_by(request_id=request_id, disapproved_at=None).first()
   if not quotation:
       sheet_price_id = '1hX0WT27oRlGnQm997EV1yasxlRoBSnhw3xit1OljQ5g'
       gc = get_credential(json_keyfile)
       wksp = gc.open_by_key(sheet_price_id)
       sheet_price = wksp.worksheet(service_request.sub_lab.code)
       df_price = pandas.DataFrame(sheet_price.get_all_records())
       quote_column_names = {}
       quote_details = {}
       quote_prices = {}
       data = service_request.data
       form = SDSPageRequestForm(data=data)

       for _, row in df_price.iterrows():
           if row['field_group'] not in quote_column_names:
               quote_column_names[row['field_group']] = set()
           for field_name in row['field_name'].split(','):
               quote_column_names[row['field_group']].add(field_name.strip())
           sorted_field_group = ''.join(sorted(row['field_group'])).replace(' ', '')
           key = sorted_field_group + ''.join(sorted(row[4:].str.cat())).replace(' ', '')
           if service_request.customer.customer_info.type.type == 'หน่วยงานรัฐ':
               quote_prices[key] = row['government_price']
           else:
               quote_prices[key] = row['other_price']

       for field in form:
           if field.label.text not in quote_column_names:
               continue

           keys = []
           keys = walk_form_fields(field, quote_column_names[field.label.text], keys=keys)
           for r in range(1, len(quote_column_names[field.label.text]) + 1):
               for key in itertools.combinations(keys, r):
                   sorted_field_label = ''.join(sorted(field.label.text)).replace(' ', '')
                   sorted_key_ = sorted(''.join([k[1] for k in key]))
                   values = ', '.join([k[1] for k in key])

                   if field.label.text == 'SDS Page':
                       p_key = sorted_field_label
                       counts = re.findall(r'\d+', values)
                       quantity = int(counts[0])
                   else:
                       p_key = sorted_field_label + ''.join(sorted_key_).replace(' ', '')
                       quantity = None
                   if p_key in quote_prices:
                       prices = quote_prices[p_key]
                       if p_key in quote_details:
                           quote_details[p_key]["quantity"] += 1
                       else:
                           if quantity:
                               quote_details[p_key] = {"value": f'SDS Page {values}', "price": prices, "quantity": quantity}
                           else:
                               quote_details[p_key] = {"value": values, "price": prices, "quantity": 1}

       quotation_no = ServiceNumberID.get_number('Quotation', db, lab=service_request.sub_lab.ref)
       quotation = ServiceQuotation(quotation_no=quotation_no.number, request_id=request_id,
                                    name=service_request.quotation_name,
                                    address=service_request.quotation_issue_address,
                                    taxpayer_identification_no=service_request.taxpayer_identification_no,
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
               quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                     item=rl.report_language.item,
                                                     quantity=1,
                                                     unit_price=rl.report_language.price,
                                                     total_price=rl.report_language.price)
               sequence_no.count += 1
               db.session.add(quotation_item)
               db.session.commit()
       flash('ร่างใบเสนอราคาสำเร็จ กรุณาดำเนินการตรวจสอบข้อมูล', 'success')
       return redirect(
           url_for('service_admin.create_quotation_for_admin', quotation_id=quotation.id, tab='draft', menu=menu))
   else:
       return render_template('service_admin/quotation_created_confirmation_page.html',
                              quotation_id=quotation.id, request_no=service_request.request_no, menu=menu)


@service_admin.route('/quotation/quantitative/generate', methods=['GET', 'POST'])
def generate_quantitative_quotation():
   menu = request.args.get('menu')
   request_id = request.args.get('request_id')
   service_request = ServiceRequest.query.get(request_id)
   quotation = ServiceQuotation.query.filter_by(request_id=request_id, disapproved_at=None).first()
   if not quotation:
       sheet_price_id = '1hX0WT27oRlGnQm997EV1yasxlRoBSnhw3xit1OljQ5g'
       gc = get_credential(json_keyfile)
       wksp = gc.open_by_key(sheet_price_id)
       sheet_price = wksp.worksheet(service_request.sub_lab.code)
       df_price = pandas.DataFrame(sheet_price.get_all_records())
       quote_column_names = {}
       quote_details = {}
       quote_prices = {}
       data = service_request.data
       form = QuantitativeRequestForm(data=data)

       for _, row in df_price.iterrows():
           if row['field_group'] not in quote_column_names:
               quote_column_names[row['field_group']] = set()
           for field_name in row['field_name'].split(','):
               quote_column_names[row['field_group']].add(field_name.strip())
           sorted_field_group = ''.join(sorted(row['field_group'])).replace(' ', '')
           key = sorted_field_group + ''.join(sorted(row[4:].str.cat())).replace(' ', '')
           if service_request.customer.customer_info.type.type == 'หน่วยงานรัฐ':
               quote_prices[key] = row['government_price']
           else:
               quote_prices[key] = row['other_price']

       for field in form:
           if field.label.text not in quote_column_names:
               continue

           keys = []
           keys = walk_form_fields(field, quote_column_names[field.label.text], keys=keys)
           for r in range(1, len(quote_column_names[field.label.text]) + 1):
               for key in itertools.combinations(keys, r):
                   sorted_field_label = ''.join(sorted(field.label.text)).replace(' ', '')
                   sorted_key_ = sorted(''.join([k[1] for k in key]))
                   values = ', '.join([k[1] for k in key])
                   p_key = sorted_field_label + ''.join(sorted_key_).replace(' ', '')

                   if p_key in quote_prices:
                       prices = quote_prices[p_key]
                       if p_key in quote_details:
                           quote_details[p_key]["quantity"] += 1
                       else:
                           quote_details[p_key] = {"value": values, "price": prices, "quantity": 1}

       quotation_no = ServiceNumberID.get_number('Quotation', db, lab=service_request.sub_lab.ref)
       quotation = ServiceQuotation(quotation_no=quotation_no.number, request_id=request_id,
                                    name=service_request.quotation_name,
                                    address=service_request.quotation_issue_address,
                                    taxpayer_identification_no=service_request.taxpayer_identification_no,
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
               quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                     item=rl.report_language.item,
                                                     quantity=1,
                                                     unit_price=rl.report_language.price,
                                                     total_price=rl.report_language.price)
               sequence_no.count += 1
               db.session.add(quotation_item)
               db.session.commit()
       flash('ร่างใบเสนอราคาสำเร็จ กรุณาดำเนินการตรวจสอบข้อมูล', 'success')
       return redirect(
           url_for('service_admin.create_quotation_for_admin', quotation_id=quotation.id, tab='draft', menu=menu))
   else:
       return render_template('service_admin/quotation_created_confirmation_page.html',
                              quotation_id=quotation.id, request_no=service_request.request_no, menu=menu)


@service_admin.route('/quotation/endotoxin/generate', methods=['GET', 'POST'])
def generate_endotoxin_quotation():
    menu = request.args.get('menu')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    quotation = ServiceQuotation.query.filter_by(request_id=request_id, disapproved_at=None).first()
    if not quotation:
        sheet_price_id = '1hX0WT27oRlGnQm997EV1yasxlRoBSnhw3xit1OljQ5g'
        gc = get_credential(json_keyfile)
        wksp = gc.open_by_key(sheet_price_id)
        sheet_price = wksp.worksheet(service_request.sub_lab.code)
        df_price = pandas.DataFrame(sheet_price.get_all_records())
        quote_column_names = {}
        quote_details = {}
        quote_prices = {}
        data = service_request.data
        form = EndotoxinRequestForm(data=data)

        for _, row in df_price.iterrows():
            if row['field_group'] not in quote_column_names:
                quote_column_names[row['field_group']] = set()
            for field_name in row['field_name'].split(','):
                quote_column_names[row['field_group']].add(field_name.strip())
            sorted_field_group = ''.join(sorted(row['field_group'])).replace(' ', '')
            key = sorted_field_group + ''.join(sorted(row[4:].str.cat())).replace(' ', '')
            if service_request.customer.customer_info.type.type == 'หน่วยงานรัฐ':
                quote_prices[key] = row['government_price']
            else:
                quote_prices[key] = row['other_price']
        for field in form:
            if field.label.text not in quote_column_names:
                continue

            keys = []
            keys = walk_form_fields(field, quote_column_names[field.label.text], keys=keys)
            for key in list(itertools.combinations(keys, len(quote_column_names[field.label.text]))):
                p_key = ''.join(sorted(field.label.text)).replace(' ', '')
                if p_key in quote_prices:
                    prices = quote_prices[p_key]
                    if p_key in quote_details:
                        quote_details[p_key]["quantity"] += 1
                    else:
                        quote_details[p_key] = {"value": "Endotoxin test", "price": prices, "quantity": 1}
        quotation_no = ServiceNumberID.get_number('Quotation', db, lab=service_request.sub_lab.ref)
        quotation = ServiceQuotation(quotation_no=quotation_no.number, request_id=request_id,
                                     name=service_request.quotation_name,
                                     address=service_request.quotation_issue_address,
                                     taxpayer_identification_no=service_request.taxpayer_identification_no,
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
                quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                      item=rl.report_language.item,
                                                      quantity=1,
                                                      unit_price=rl.report_language.price,
                                                      total_price=rl.report_language.price)
                sequence_no.count += 1
                db.session.add(quotation_item)
                db.session.commit()
        flash('ร่างใบเสนอราคาสำเร็จ กรุณาดำเนินการตรวจสอบข้อมูล', 'success')
        return redirect(
            url_for('service_admin.create_quotation_for_admin', quotation_id=quotation.id, tab='draft', menu=menu))
    else:
        return render_template('service_admin/quotation_created_confirmation_page.html',
                               quotation_id=quotation.id, request_no=service_request.request_no, menu=menu)


@service_admin.route('/quotation/toxicology/generate', methods=['GET', 'POST'])
def generate_toxicology_quotation():
    menu = request.args.get('menu')
    request_id = request.args.get('request_id')
    service_request = ServiceRequest.query.get(request_id)
    quotation = ServiceQuotation.query.filter_by(request_id=request_id, disapproved_at=None).first()
    if not quotation:
        sheet_price_id = '1hX0WT27oRlGnQm997EV1yasxlRoBSnhw3xit1OljQ5g'
        gc = get_credential(json_keyfile)
        wksp = gc.open_by_key(sheet_price_id)
        sheet_price = wksp.worksheet(service_request.sub_lab.code)
        df_price = pandas.DataFrame(sheet_price.get_all_records())
        quote_column_names = {}
        quote_details = {}
        quote_prices = {}
        data = service_request.data
        form = ToxicologyRequestForm(data=data)

        for _, row in df_price.iterrows():
            if row['field_group'] not in quote_column_names:
                quote_column_names[row['field_group']] = set()
            for field_name in row['field_name'].split(','):
                quote_column_names[row['field_group']].add(field_name.strip())
            sorted_field_group = ''.join(sorted(row['field_group'])).replace(' ', '')
            key = sorted_field_group + ''.join(sorted(row[4:].str.cat())).replace(' ', '')
            if service_request.customer.customer_info.type.type == 'หน่วยงานรัฐ':
                quote_prices[key] = row['government_price']
            else:
                quote_prices[key] = row['other_price']
        for field in form:
            if field.label.text not in quote_column_names:
                continue

            keys = []
            keys = walk_form_fields(field, quote_column_names[field.label.text], keys=keys)
            for r in range(1, len(quote_column_names[field.label.text]) + 1):
                for key in itertools.combinations(keys, r):
                    sorted_field_label = ''.join(sorted(field.label.text)).replace(' ', '')
                    sorted_key_ = sorted(''.join([k[1] for k in key]))
                    p_key = sorted_field_label + ''.join(sorted_key_).replace(' ', '')
                    values = ', '.join([k[1] for k in key])

                    if p_key in quote_prices:
                        prices = quote_prices[p_key]
                        if p_key in quote_details:
                            quote_details[p_key]["quantity"] += 1
                        else:
                            quote_details[p_key] = {"value": values, "price": prices, "quantity": 1}
        quotation_no = ServiceNumberID.get_number('Quotation', db, lab=service_request.sub_lab.ref)
        quotation = ServiceQuotation(quotation_no=quotation_no.number, request_id=request_id,
                                     name=service_request.quotation_name,
                                     address=service_request.quotation_issue_address,
                                     taxpayer_identification_no=service_request.taxpayer_identification_no,
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
                quotation_item = ServiceQuotationItem(sequence=sequence_no.number, quotation_id=quotation.id,
                                                      item=rl.report_language.item,
                                                      quantity=1,
                                                      unit_price=rl.report_language.price,
                                                      total_price=rl.report_language.price)
                sequence_no.count += 1
                db.session.add(quotation_item)
                db.session.commit()
        flash('ร่างใบเสนอราคาสำเร็จ กรุณาดำเนินการตรวจสอบข้อมูล', 'success')
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
    request_data = request_data_paths[quotation.request.sub_lab.code]
    datas = request_data(quotation.request, type='form')
    quotation.quotation_items = sorted(quotation.quotation_items, key=lambda x: x.sequence)
    ServiceQuotationForm = create_quotation_form(is_use=True)
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
            admins = (
                ServiceAdmin.query
                .join(ServiceSubLab)
                .filter(ServiceSubLab.code == quotation.request.sub_lab.code)
            )
            quotation_link = url_for("service_admin.approval_quotation_for_supervisor", quotation_id=quotation_id,
                                     tab='pending_approval', _external=True, _scheme=scheme, menu=menu)
            if admins:
                email = [a.admin.email + '@mahidol.ac.th' for a in admins if a.is_supervisor]
                if email:
                    title = f'''รายการขออนุมัติใบเสนอราคา'''
                    message = f'''เรียน หัวหน้าห้องปฏิบัติการ{quotation.request.sub_lab.lab.lab}\n\n'''
                    # message += f'''ใบเสนอราคาเลขที่ : {quotation.quotation_no}\n'''
                    # message += f'''ลูกค้า : {quotation.customer_name}\n'''
                    # message += f'''ในนาม : {quotation.name}\n'''
                    # message += f'''อ้างอิงจากใบคำขอรับบริการเลขที่ : {quotation.request.request_no}\n'''
                    message += f'''มีใบเสนอราคาเลขที่ {quotation.quotation_no} ที่รอการอนุมัติใบเสนอราคา ท่านสามารถตรวจสอบและดำเนินการได้ที่ลิงก์ด้านล่าง\n'''
                    message += f'''{quotation_link}\n\n'''
                    # message += f'''เจ้าหน้าที่ห้องปฏิบัติการ\n'''
                    # message += f'''{quotation.creator.fullname}\n'''
                    message += f'''ระบบงานบริการวิชาการ'''
                    msg = ('ใบเสนอราคาเลขที่ {}\n' \
                           'ออกในนาม {}\n' \
                           'ณ วันที่ {} รอดำเนินการอนุมัติใบเสนอราคา\n' \
                           'กรุณาดำเนินการอนุมัติในระบบ\n'
                           'คลิกลิ้งค์เพื่อดำเนินการ\n'
                           '{}'
                           .format(quotation.quotation_no, quotation.name,
                                   quotation.sent_at.astimezone(localtz).strftime('%d/%m/%Y'),
                                   quotation_link
                                   )
                           )
                    if not current_app.debug:
                        send_mail(email, title, message)
                        for a in admins:
                            if a.is_supervisor:
                                try:
                                    line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                                except LineBotApiError:
                                    pass
                    else:
                        print('message_email', message, 'message_line', msg)
            flash('ส่งข้อมูลให้หัวหน้าอนุมัติเรียบร้อยแล้ว กรุณารอดำเนินการ', 'success')
            return redirect(url_for('service_admin.quotation_index', tab='pending_supervisor_approval', menu=menu))
        else:
            flash('บันทึกข้อมูลแบบร่างเรียบร้อยแล้ว', 'success')
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('service_admin/create_quotation_for_admin.html', quotation=quotation, menu=menu,
                           tab=tab, form=form, datas=datas)


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


@service_admin.route('/quotation/supervisor/approve/<int:quotation_id>', methods=['GET', 'POST'])
@login_required
def approval_quotation_for_supervisor(quotation_id):
    menu = request.args.get('menu')
    tab = request.args.get('tab')
    quotation = ServiceQuotation.query.get(quotation_id)
    if not quotation.approved_at:
        if request.method == 'POST':
            if quotation.digital_signature is None:

                try:
                    status_id = get_status(5)
                    password = request.form.get('password')
                    quotation.approver_id = current_user.id
                    quotation.approved_at = arrow.now('Asia/Bangkok').datetime
                    quotation.request.status_id = status_id
                    db.session.add(quotation)
                    buffer = generate_quotation_pdf(quotation, sign=True)
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
                    scheme = 'http' if current_app.debug else 'https'
                    # contact_email = quotation.request.customer.contact_email if quotation.request.customer.contact_email else quotation.request.customer.email
                    quotation_link = url_for("academic_services.view_quotation", quotation_id=quotation_id, menu=menu,
                                             tab='pending', _external=True, _scheme=scheme)
                    total_items = len(quotation.quotation_items)
                    title_prefix = 'คุณ' if quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
                    title = f'''แจ้งออกใบเสนอราคา'''
                    customer_name = quotation.customer_name.replace(' ', '_')
                    message = f'''เรียน {title_prefix}{quotation.customer_name}\n\n'''
                    message += f'''ตามที่ท่านได้แจ้งความประสงค์ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล\n'''
                    message += f'''ขณะนี้ทางเจ้าหน้าที่ได้ดำเนินการออกใบเสนอราคาเลขที่ {quotation.quotation_no} เรียบร้อยแล้ว ท่านสามารถตรวจสอบและดำเนินการได้ที่ลิงค์ด้านล่าง\n'''
                    message += f'''{quotation_link}\n\n'''
                    message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
                    message += f'''ขอขอบคุณพระคุณที่ใช้บริการ\n'''
                    message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
                    message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
                    admins = (
                        ServiceAdmin.query
                        .join(ServiceSubLab)
                        .filter(ServiceSubLab.code == quotation.request.sub_lab.code)
                        .all()
                    )
                    quotation_link_for_assistant = url_for("service_admin.view_quotation", quotation_id=quotation_id,
                                                           tab='awaiting_customer', menu=menu, _external=True,
                                                           _scheme=scheme)
                    if admins:
                        email = [a.admin.email + '@mahidol.ac.th' for a in admins if a.is_assistant]
                        if email:
                            title_for_assistant = f'''รายการอนุมัติใบเสนอราคา'''
                            message_for_assistant = f'''เรียน ผู้ช่วยคณบดีฝ่ายบริการวิชาการ\n\n'''
                            message_for_assistant += f'''มีใบเสนอราคาเลขที่ {quotation.quotation_no} ที่ได้รับการอนุมัติจากหัวหน้าห้องปฏิบัติการแล้ว ท่านสามารดูรายละเอียดเพิ่มเติมได้ที่ลิงค์ด้านล่าง\n'''
                            message_for_assistant += f'''{quotation_link_for_assistant}\n\n'''
                            # message_for_assistant += f'''หัวหน้าห้องปฏิบัติการ\n'''
                            # message_for_assistant += f'''{quotation.approver.fullname}\n'''
                            message_for_assistant += f'''ระบบงานบริการวิชาการ'''
                        if not current_app.debug:
                            send_mail([quotation.request.customer.email], title, message)
                            send_mail(email, title_for_assistant, message_for_assistant)
                        else:
                            print('message_email_for_customer', message, 'message_for_assistant', message_for_assistant)
                    flash(f'อนุมัติใบเสนอราคาเลขที่ {quotation.quotation_no} สำเร็จ กรุณารอลูกค้ายืนยันใบเสนอราคา',
                          'success')
                    return redirect(
                        url_for('service_admin.quotation_index', quotation_id=quotation.id, tab='awaiting_customer',
                                menu=menu))
        return render_template('service_admin/approval_quotation_for_supervisor.html', quotation=quotation,
                               tab=tab, quotation_id=quotation_id, menu=menu)
    else:
        return render_template('service_admin/quotation_approved_page.html', quotation_id=quotation.id,
                               quotaiton_no=quotation.quotation_no, menu=menu, tab='all')


@service_admin.route('/quotation/password/enter/<int:quotation_id>', methods=['GET', 'POST'])
@login_required
def enter_password_for_sign_digital(quotation_id):
    menu = request.args.get('menu')
    form = PasswordOfSignDigitalForm()
    return render_template('service_admin/modal/password_modal.html', form=form, menu=menu,
                           quotation_id=quotation_id)


@service_admin.route('/quotation/disapprove/<int:quotation_id>', methods=['GET', 'POST'])
def disapprove_quotation(quotation_id):
    menu = request.args.get('menu')
    quotation = ServiceQuotation.query.get(quotation_id)
    ServiceQuotationForm = create_quotation_form(is_use=False)
    form = ServiceQuotationForm(obj=quotation)
    if form.validate_on_submit():
        form.populate_obj(quotation)
        if form.note.data:
            status_id = get_status(24)
            quotation.disapprover_id = current_user.id
            quotation.disapproved_at = arrow.now('Asia/Bangkok').datetime
            quotation.request.status_id = status_id
            db.session.add(quotation)
            db.session.commit()
            admins = (
                ServiceAdmin.query
                .join(ServiceSubLab)
                .filter(ServiceSubLab.code == quotation.request.sub_lab.code)
                .all()
            )
            title_prefix = 'คุณ' if quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
            customer_name = quotation.customer_name.replace(' ', '_')
            if admins:
                title = f'''รายการไม่อนุมัติใบเสนอราคา'''
                message = f'''เรียน เจ้าหน้าที่{quotation.request.sub_lab.lab.lab}\n\n'''
                message += f'''มีใบเสนอราคาเลขที่ {quotation.quotation_no} ที่ไม่ผ่านการอนุมัติจากหัวหน้าห้องปฏิบัติการ เนื่องจาก{quotation.note}\n\n'''
                # message += f'''หัวหน้าห้องปฏิบัติการ\n'''
                # message += f'''{quotation.disapprover.fullname}\n'''
                message += f'''ระบบงานบริการวิชาการ'''
                if not current_app.debug:
                    send_mail(
                        [a.admin.email + '@mahidol.ac.th' for a in admins if
                         not a.is_central_admin and not a.is_assistant
                         and not a.is_supervisor],
                        title, message)
                else:
                    print('message', message)
            flash('ไม่อนุมัติใบเสนอราคาสำเร็จ', 'success')
            resp = make_response()
            resp.headers['HX-Redirect'] = url_for('service_admin.quotation_index', menu=menu, tab='all')
        else:
            flash('กรุณากรอกรายละเอียด', 'danger')
            resp = make_response()
            resp.headers['HX-Refresh'] = 'true'
        return resp
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('service_admin/modal/disapprove_quotation_modal.html', form=form,
                           quotation_id=quotation_id, menu=menu, tab='pending_approval')


@service_admin.route('/quotation/view/<int:quotation_id>')
@login_required
def view_quotation(quotation_id):
    menu = request.args.get('menu')
    tab = request.args.get('tab')
    quotation = ServiceQuotation.query.get(quotation_id)
    return render_template('service_admin/view_quotation.html', quotation_id=quotation_id, tab=tab,
                           quotation=quotation, menu=menu)


def generate_quotation_pdf(quotation, sign=False):
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 70, 70)
    approver = quotation.approver.fullname if sign else ''
    digital_sign = 'ลายมือชื่อดิจิทัล/Digital Signature' if sign else (
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;')

    def all_page_setup(canvas, doc):
        canvas.saveState()
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

    affiliation = '''<para><font size=11>
                   คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>
                   999 ต.ศาลายา อ.พุทธมณฑล จ.นครปฐม 73170<br/>
                   โทร 0-2441-4371-9 ต่อ 2820 2830<br/>
                   เลขประจำตัวผู้เสียภาษี 0994000158378
                   </font></para>
                   '''

    quotation_no = '''<br/><br/><font size=14>
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

    detail_style = ParagraphStyle(
        'DetailStyle',
        parent=style_sheet['ThaiStyle'],
        leading=20
    )

    issued_date = arrow.get(quotation.approved_at.astimezone(localtz)).format(fmt='DD MMMM YYYY',
                                                                              locale='th-th') if sign else ''
    customer = '''<para><font size=14>
                    วันที่ {issued_date}<br/>
                    เรื่อง ใบเสนอราคาค่าบริการตรวจวิเคราะห์ทางห้องปฏิบัติการ{lab}<br/>
                    เรียน {customer}<br/>
                    ที่อยู่ {address}<br/>
                    เลขประจำตัวผู้เสียภาษี {taxpayer_identification_no}
                    </font></para>
                    '''.format(issued_date=issued_date, lab=quotation.request.sub_lab.lab.lab, customer=quotation.name,
                               address=quotation.address,
                               taxpayer_identification_no=quotation.taxpayer_identification_no if quotation.taxpayer_identification_no else '-')

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

    items.append([
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>รวมเป็นเงิน</font>', style=style_sheet['ThaiStyleBold']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(quotation.subtotal()), style=bold_style),
    ])

    items.append([
        Paragraph('<font size=13>รวมเป็นเงินทั้งสิ้น/Grand Total ({})</font>'.format(bahttext(quotation.grand_total())),
                  style=label_style),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>ส่วนลด</font>', style=style_sheet['ThaiStyleBold']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(quotation.discount()), style=bold_style),
    ])

    items.append([
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>รวมเป็นเงินทั้งสิ้น/Grand Total</font>', style=style_sheet['ThaiStyleBold']),
        Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
        Paragraph('<font size=12>{:,.2f}</font>'.format(quotation.grand_total()), style=bold_style),
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
        ('VALIGN', (0, 0), (-1, -4), 'TOP'),
        ('VALIGN', (0, -3), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -4), (-1, -4), 9),
        ('BOTTOMPADDING', (0, -3), (-1, -1), 7)
    ]))

    head_remark_style = ParagraphStyle(
        'HeadRemarkStyle',
        parent=style_sheet['ThaiStyleBold'],
        fontSize=10,
        leading=13
    )

    remark_style = ParagraphStyle(
        'ThaiStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=8,
        leading=13
    )
    remark_table = Table([
        [Paragraph("<font size=14>หมายเหตุ/Remark<br/></font>", style=head_remark_style)],
        [Paragraph("<font size=12>ยืนยันราคาตามใบเสนอราคา ภายใน 90 วัน<br/></font>", style=remark_style)]
    ],
        colWidths=[500]
    )
    remark_table.hAlign = 'LEFT'
    remark_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 1), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 0),
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

    data.append(KeepTogether(Spacer(30, 30)))
    data.append(KeepTogether(header_ori))
    data.append(KeepTogether(Spacer(1, 12)))
    data.append(KeepTogether(customer_table))
    data.append(KeepTogether(Spacer(1, 16)))
    data.append(KeepTogether(item_table))
    data.append(KeepTogether(Spacer(1, 16)))
    data.append(KeepTogether(remark_table))
    data.append(KeepTogether(Spacer(1, 16)))
    data.append(KeepTogether(sign_table))

    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    buffer.seek(0)
    return buffer


@service_admin.route('/quotation/pdf/<int:quotation_id>', methods=['GET'])
def export_quotation_pdf(quotation_id):
    quotation = ServiceQuotation.query.get(quotation_id)
    if quotation.digital_signature:
        return send_file(BytesIO(quotation.digital_signature), download_name='Quotation.pdf',
                         as_attachment=True)
    buffer = generate_quotation_pdf(quotation)
    return send_file(buffer, download_name='Quotation.pdf', as_attachment=True)


@service_admin.route('/procurement/meeting/add', methods=['GET'])
def add_meeting():
    return render_template('procurement/add_meeting.html')


@service_admin.route('/result/draft/add', methods=['GET', 'POST'])
@service_admin.route('/result/draft/edit/<int:result_id>', methods=['GET', 'POST'])
@login_required
def create_draft_result(result_id=None):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    action = request.form.get('action')
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
                    sequence_no = ServiceSequenceResultItemID.get_number('RS', db,
                                                                         result='result_' + str(result_list.id))
                    for rl in service_request.report_languages:
                        result_item = ServiceResultItem(sequence=sequence_no.number,
                                                        report_language=rl.report_language.item,
                                                        result=result_list,
                                                        released_at=arrow.now('Asia/Bangkok').datetime,
                                                        creator_id=current_user.id)
                        sequence_no.count += 1
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
                item.sent_at = arrow.now('Asia/Bangkok').datetime
                if result_id:
                    item.modified_at = arrow.now('Asia/Bangkok').datetime
                    item.result.modified_at = arrow.now('Asia/Bangkok').datetime
                db.session.add(item)
                db.session.commit()
        upload_all = all(item.draft_file for item in result.result_items)
        if action == 'send':
            if upload_all:
                result.is_edited = False
                result.sent_at = arrow.now('Asia/Bangkok').datetime
                result.sender_id = current_user.id
                db.session.add(result)
                db.session.commit()
                scheme = 'http' if current_app.debug else 'https'
                result_url = url_for('academic_services.view_result_item', result_id=result.id,
                                     result_item_id=result.result_items[0].id, menu='report', tab='approve',
                                     _external=True, _scheme=scheme)
                customer_name = result.request.customer.customer_name.replace(' ', '_')
                # contact_email = result.request.customer.contact_email if result.request.customer.contact_email else result.request.customer.email
                title_prefix = 'คุณ' if result.request.customer.customer_info.type.type == 'บุคคล' else ''
                title = f'''แจ้งออกรายงานผลการทดสอบฉบับร่างของใบคำขอรับบริการ'''
                message = f'''เรียน {title_prefix}{result.request.customer.customer_name}\n\n'''
                message += f'''ตามที่ท่านได้ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล\n'''
                message += f'''ขณะนี้ทางเจ้าหน้าที่ได้จัดทำรายงานผลการทดสอบฉบับร่างของใบคำขอบริการเลขที่ {result.request.request_no}เรียบร้อยแล้ว\n'''
                message += f'''ท่านสามารถตรวจสอบและดำเนินการยืนยันได้ที่ลิงค์ด้านล่าง\n'''
                message += f'''{result_url}\n\n'''
                message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
                message += f'''ขอขอบพระคุณที่ใช้บริการ\n'''
                message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
                message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
                if not current_app.debug:
                    send_mail([result.request.customer.email], title, message)
                else:
                    print('message', message)
                flash("ส่งข้อมูลเรียบร้อยแล้ว", "success")
                return redirect(url_for('service_admin.test_item_index', menu='test_item', tab='waiting_confirm'))
            else:
                flash("กรุณาแนบไฟล์ให้ครบถ้วน", "danger")
        else:
            db.session.add(result)
            db.session.commit()
            flash("บันทึกไฟล์เรียบร้อยแล้ว", "success")
            return redirect(url_for('service_admin.test_item_index', menu='test_item', tab='testing'))
    return render_template('service_admin/create_draft_result.html', result_id=result_id, menu=menu,
                           result=result, tab=tab)


@service_admin.route('/result_item/draft/edit/<int:result_item_id>', methods=['GET', 'POST'])
@login_required
def edit_draft_result(result_item_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    result_item = ServiceResultItem.query.get(result_item_id)
    if result_item.is_edited:
        return render_template('service_admin/result_edit_notice_page.html', menu=menu, tab=tab)
    else:
        form = ServiceResultItemForm(obj=result_item)
        if form.validate_on_submit():
            file = request.files.get(f'file_{result_item_id}')
            if file and allowed_file(file.filename):
                mime_type = file.mimetype
                file_name = '{}.{}'.format(result_item.report_language, file.filename.split('.')[-1])
                file_data = file.stream.read()
                response = s3.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=file_name,
                    Body=file_data,
                    ContentType=mime_type
                )
                result_item.draft_file = file_name
                result_item.edited_at = arrow.now('Asia/Bangkok').datetime
                result_item.is_edited = True
                result_item.modified_at = arrow.now('Asia/Bangkok').datetime
                db.session.add(result_item)
                db.session.commit()
            edited_all = all(item.edited_at for item in result_item.result.result_items if item.req_edit_at)
            tab = 'approve' if edited_all else 'edit'
            if edited_all:
                result_item.result.is_edited = True
                db.session.add(result_item)
                db.session.commit()
            scheme = 'http' if current_app.debug else 'https'
            result_url = url_for('academic_services.view_result_item', result_id=result_item.result_id,
                                 result_item_id=result_item_id, menu='report', tab=tab, _external=True,
                                 _scheme=scheme)
            customer_name = result_item.result.request.customer.customer_name.replace(' ', '_')
            # contact_email = result_item.result.request.customer.contact_email if result_item.result.request.customer.contact_email else result_item.result.request.customer.email
            title_prefix = 'คุณ' if result_item.result.request.customer.customer_info.type.type == 'บุคคล' else ''
            title = f'''แจ้งแก้ไขรายงานผลการทดสอบฉบับร่างของใบคำขอรับบริการ'''
            message = f'''เรียน {title_prefix}{result_item.result.request.customer.customer_name}\n\n'''
            message += f'''ตามที่ท่านได้ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล\n'''
            message += f'''ขณะนี้ทางเจ้าหน้าที่ได้แก้ไข{result_item.report_language}ฉบับร่างเรียบร้อยแล้ว\n'''
            message += f'''ท่านสามารถตรวจสอบความถูกต้องของข้อมูลในรายงานผลการทดสอบฉบับร่าง และดำเนินการยืนยันได้ที่ลิงค์ด้านล่าง\n'''
            message += f'''{result_url}\n\n'''
            message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
            message += f'''ขอขอบพระคุณที่ใช้บริการ\n'''
            message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
            message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
            if not current_app.debug:
                send_mail([result_item.result.request.customer.email], title, message)
            else:
                print('message', message)
            flash("บันทึกไฟล์เรียบร้อยแล้ว", "success")
            return redirect(url_for('service_admin.result_index', menu=menu, tab=tab))
        else:
            return render_template('service_admin/edit_draft_result.html', result_item_id=result_item_id,
                                   menu=menu, tab=tab, result_item=result_item, result_id=result_item.result_id)


@service_admin.route('/result/draft/delete/<int:item_id>', methods=['GET', 'POST'])
def delete_draft_result(item_id):
    item = ServiceResultItem.query.get(item_id)
    item.draft_file = None
    item.modified_at = arrow.now('Asia/Bangkok').datetime
    item.result.modified_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(item)
    db.session.commit()
    flash("ลบไฟล์เรียบร้อยแล้ว", "success")
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@service_admin.route('/result/final/add', methods=['GET', 'POST'])
@service_admin.route('/result/final/edit/<int:result_id>', methods=['GET', 'POST'])
@login_required
def create_final_result(result_id=None):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
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
        uploaded_all = all(item.final_file for item in result.result_items)
        if uploaded_all:
            scheme = 'http' if current_app.debug else 'https'
            result_url = url_for('academic_services.result_index', menu='report', tab='all', _external=True,
                                 _scheme=scheme)
            customer_name = result.request.customer.customer_name.replace(' ', '_')
            # contact_email = result.request.customer.contact_email if result.request.customer.contact_email else result.request.customer.email
            title_prefix = 'คุณ' if result.request.customer.customer_info.type.type == 'บุคคล' else ''
            title = f'''แจ้งออกรายงานผลการทดสอบฉบับจริงของใบคำขอรับบริการ'''
            message = f'''เรียน {title_prefix}{result.request.customer.customer_name}\n\n'''
            message += f'''ตามที่ท่านได้ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล\n'''
            message += f'''ขณะนี้ทางเจ้าหน้าที่ได้ดำเนินการออกรายงานผลการทดสอบฉบับจริงเรียบร้อยแล้ว ท่านสามารถดูรายละเอียดเพิ่มเติมได้ที่ลิงค์ด้านล่าง\n'''
            message += f'''{result_url}\n\n'''
            message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
            message += f'''ขอขอบพระคุณที่ใช้บริการ\n'''
            message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
            message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
            if not current_app.debug:
                send_mail([result.request.customer.email], title, message)
            else:
                print('message', message)
        flash("บันทึกไฟล์เรียบร้อยแล้ว", "success")
        return redirect(url_for('service_admin.test_item_index', menu='test_item', tab='all'))
    return render_template('service_admin/create_final_result.html', result_id=result_id, menu=menu,
                           tab=tab, result=result)


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


@service_admin.route('/invoice/payment/index')
@login_required
def invoice_payment_index():
    menu = request.args.get('menu')
    return render_template('service_admin/invoice_payment_index.html', menu=menu)


@service_admin.route('/api/invoice/payment/index')
def get_invoice_payments():
    query = ServiceInvoice.query.filter(ServiceInvoice.file_attached_at != None)
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
                            <a class="button is-small is-outlined is-link is-rounded" href="{download_file}">
                                <span class="icon is-small"><i class="fas fa-file-invoice-dollar"></i></span>
                                <span>ใบแจ้งหนี้</span>
                            </a>
                        </div>
                    </div>
                '''
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


@service_admin.route('/finance/invoice/view/<int:invoice_id>', methods=['GET'])
@login_required
def view_invoice_for_finance(invoice_id):
    today = arrow.now('Asia/Bangkok').date()
    invoice = ServiceInvoice.query.get(invoice_id)
    is_overdue = False
    slip_url = None
    if today > invoice.due_date.date() and not invoice.paid_at:
        is_overdue = True
    if invoice.payments:
        for payment in invoice.payments:
            slip_url = generate_url(payment.slip)
    else:
        slip_url = None
    return render_template('service_admin/view_invoice_for_finance.html', invoice=invoice, slip_url=slip_url,
                           is_overdue=is_overdue, invoice_id=invoice_id)


@service_admin.route('/invoice/payment/confirm/<int:invoice_id>', methods=['GET', 'POST'])
def confirm_payment(invoice_id):
    status_id = get_status(22)
    payment = ServicePayment.query.filter_by(invoice_id=invoice_id, cancelled_at=None).first()
    if not payment:
        invoice = ServiceInvoice.query.get(invoice_id)
        payment = ServicePayment(invoice_id=invoice_id, payment_type='เช็คเงินสด',
                                 amount_paid=invoice.grand_total,
                                 paid_at=arrow.now('Asia/Bangkok').datetime,
                                 customer_id=invoice.quotation.request.customer_id,
                                 created_at=arrow.now('Asia/Bangkok').datetime,
                                 verified_at=arrow.now('Asia/Bangkok').datetime,
                                 verifier_id=current_user.id
                                 )
        db.session.add(payment)
        invoice.quotation.request.status_id = status_id
        db.session.add(invoice)
        db.session.commit()
    else:
        payment = ServicePayment.query.filter_by(invoice_id=invoice_id, cancelled_at=None).first()
        payment.verified_at = arrow.now('Asia/Bangkok').datetime
        payment.verifier_id = current_user.id
        payment.invoice.quotation.request.status_id = status_id
        db.session.add(payment)
        db.session.commit()
    flash('ยืนยันการชำระเงินเรียบร้อยแล้ว', 'success')
    return render_template('service_admin/invoice_payment_index.html')


@service_admin.route('/invoice/payment/cancel/<int:invoice_id>', methods=['GET', 'POST'])
def cancel_payment(invoice_id):
    status_id = get_status(20)
    payment = ServicePayment.query.filter_by(invoice_id=invoice_id, cancelled_at=None).first()
    db.session.delete(payment)
    db.session.commit()
    invoice = ServiceInvoice.query.get(invoice_id)
    invoice.quotation.request.status_id = status_id
    scheme = 'http' if current_app.debug else 'https'
    db.session.add(invoice)
    db.session.commit()
    upload_payment_link = url_for("academic_services.add_payment", invoice_id=invoice_id, tab='pending', menu='invoice',
                                  _external=True, _scheme=scheme)
    customer_name = invoice.quotation.request.customer.customer_name.replace(' ', '_')
    # contact_email = invoice.quotation.request.customer.contact_email if invoice.quotation.request.customer.contact_email else invoice.quotation.request.customer.email
    title_prefix = 'คุณ' if invoice.quotation.request.customer.customer_info.type.type == 'บุคคล' else ''
    title = f'''แจ้งยกเลิกการชำระเงินของใบแจ้งหนี้'''
    message = f'''เรียน {title_prefix}{invoice.quotation.request.customer.customer_name}\n\n'''
    message += f'''ตามที่ท่านได้ขอรับบริการตรวจวิเคราะห์จากคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล\n'''
    message += f'''ขณะนี้ทางเจ้าหน้าที่ขอแจ้งให้ทราบว่า การชำระเงินสำหรับใบแจ้งหนี้เลขที่่ {invoice.invoice_no} มีความจำเป็นต้องยกเลิกการชำระเงินเดิม\n'''
    message += f'''จึงขอความร่วมมือให้ท่านดำเนินการชำระเงินใหม่ตามจำนวนที่ระบุไว้ในใบแจ้งหนี้\n'''
    message += f'''ท่านสามารถดำเนินการแนบหลักฐานการชำระเงินใหม่ได้ที่ลิงค์ด้านล่าง\n'''
    message += f'''{upload_payment_link}\n\n'''
    message += f'''ทางคณะฯ ต้องขออภัยในความไม่สะดวกมา ณ ที่นี้\n\n'''
    message += f'''หมายเหตุ : อีเมลฉบับนี้จัดส่งโดยระบบอัตโนมัติ โปรดอย่าตอบกลับมายังอีเมลนี้\n\n'''
    message += f'''ขอขอบพระคุณที่ใช้บริการ\n'''
    message += f'''ระบบงานบริการตรวจวิเคราะห์\n'''
    message += f'''คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล'''
    if not current_app.debug:
        send_mail([invoice.quotation.request.customer.email], title, message)
    else:
        print('message', message)
    flash('ยกเลิกการชำระเงินเรียบร้อยแล้ว', 'success')
    return redirect(url_for('service_admin.invoice_payment_index'))


@service_admin.route('/receipt/index', methods=['GET'])
@login_required
def receipt_index():
    menu = request.args.get('menu')
    return render_template('service_admin/receipt_index.html', menu=menu)


@service_admin.route('/api/receipt/index')
def get_receipts():
    query = (
        ServiceInvoice.query
        .join(ServiceInvoice.quotation)
        .join(ServiceQuotation.request)
        .join(ServiceRequest.sub_lab)
        .join(ServiceInvoice.receipts)
        .join(ServiceSubLab.admins)
        .filter(
            ServiceAdmin.admin_id == current_user.id
        )
    )
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
