import os
import arrow
import requests
from pytz import timezone
from app.service_admin import service_admin
from app.academic_services.models import *
from flask import render_template, flash, redirect, url_for, request, session, make_response, jsonify, current_app
from flask_login import current_user, login_required
from sqlalchemy import or_, and_
from app.service_admin.forms import (ServiceCustomerInfoForm, ServiceCustomerAddressForm, ServiceResultForm)
from app.main import mail
from flask_mail import Message
from werkzeug.utils import secure_filename
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive

localtz = timezone('Asia/Bangkok')

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
    return render_template('service_admin/view_customer.html', customers=customers)


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
    for a in admin:
        if a.lab:
            lab = a.lab.code
        else:
            sub_lab = a.sub_lab.code
    query = ServiceRequest.query.filter(or_(ServiceRequest.admin.has(id=current_user.id), ServiceRequest.lab==lab)) \
        if lab else ServiceRequest.query.filter(or_(ServiceRequest.admin.has(id=current_user.id), ServiceRequest.lab==sub_lab))
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


@service_admin.route('/request/test/confirm/<int:request_id>', methods=['GET'])
def confirm_test(request_id):
    service_request = ServiceRequest.query.get(request_id)
    service_request.status = 'กำลังเริ่มการทดสอบ'
    db.session.add(service_request)
    db.session.commit()
    flash('เปลี่ยนสถานะสำเร็จ', 'success')
    return redirect(url_for('service_admin.request_index'))


@service_admin.route('/result/index')
def result_index():
    return render_template('service_admin/result_index.html')


@service_admin.route('/api/result/index')
def get_results():
    query = ServiceResult.query.filter_by(admin_id=current_user.id)
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
        result.status = 'ออกใบรายงายผลการทดสอบ'
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
def payment_index():
    return render_template('service_admin/payment_index.html')


@service_admin.route('/api/payment/index')
def get_payments():
    admin = ServiceAdmin.query.filter_by(admin_id=current_user.id).all()
    for a in admin:
        if a.lab:
            lab = a.lab.code
        else:
            sub_lab = a.sub_lab.code
    query = ServiceRequest.query.filter(or_(ServiceRequest.admin.has(id=current_user.id), ServiceRequest.lab==lab)) \
        if lab else ServiceRequest.query.filter(or_(ServiceRequest.admin.has(id=current_user.id), ServiceRequest.lab==sub_lab))
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
    db.session.add(service_request)
    db.session.commit()
    flash('เปลี่ยนสถานะสำเร็จ', 'success')
    return redirect(url_for('service_admin.payment_index'))


@service_admin.route('/payment/cancel/<int:request_id>', methods=['GET'])
def cancel_payment(request_id):
    service_request = ServiceRequest.query.get(request_id)
    service_request.status = 'ชำระเงินไม่สำเร็จ'
    service_request.payment.status = 'ชำระเงินไม่สำเร็จ'
    db.session.add(service_request)
    db.session.commit()
    flash('เปลี่ยนสถานะสำเร็จ', 'success')
    return redirect(url_for('service_admin.payment_index'))