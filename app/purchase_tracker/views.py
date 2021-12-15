# -*- coding:utf-8 -*-
import requests, os
from flask import render_template, request, flash, redirect, url_for, session, jsonify, Flask
from flask_login import current_user, login_required
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from sqlalchemy_utils.types.arrow import arrow
from werkzeug.utils import secure_filename
from . import purchase_tracker_bp as purchase_tracker

from ..main import db
from .forms import *
from datetime import datetime, timedelta
from pytz import timezone
from pydrive.drive import GoogleDrive
from .models import PurchaseTrackerAccount
# Upload images for Google Drive
FOLDER_ID = "1JYkU2kRvbvGnmpQ1Tb-TcQS-vWQKbXvy"

json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()

bangkok = timezone('Asia/Bangkok')

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
ACTIVITIES = dict([(1, '1. รับเรื่องขออนุมัติหลักการ/ใบเบิก ดำเนินการลงรับหนังสือ เสนอหัวหน้าหน่วยพิจารณา'),
                         (2, '2. ดำเนินการสืบราคา 3 บริษัท(กรณีไม่มีใบเสนอราคาแนบมา)'),
                         (3, '3. จัดทำ PR ขอซื้อขอจ้าง พร้อมตั้งผุ้ตรวจรับหรือคณะกรรมการตรวจรับพัสดุ ผ่านระบบ MUERP'),
                         (4, '4. เสนอหัวหน้าหน่วยพัสดุตรวจสอบและอนุมัติ A1 ผ่านระบบ MUERP'),
                         (5, '5. ขอใบจองงบประมาณจากงานงบประมาณ ผ่านระบบ MUERP'),
                         (6, '6. เสนอหัวหน้าหน่วยคลังฯตรวจสอบและอนุมัติ A3 ผ่านระบบ MUERP'),
                         (7, '7. เสนอรองคณบดีฯ, คณบดี ลงนาม'),
                         (8, '8. เสนอหัวหน้าหน่วยพัสดุตรวจสอบและอนุมัติ A4 ผ่านระบบ MUERP'),
                         (9, '9. จัดทำ PO สั่งซื้อสั่งจ้าง(บันทึกในระบบเท่านั้น) และเสนอหัวหน้าหน่วยพัสดุตรวจสอบ'),
                         (10, '10. จัดส่งใบสั่งซื้อให้ทางบริษัท/โทรแจ้งบริษัทจัดส่งพัสดุ'),
                         (11, '11. บริษัทจัดส่งพัสดุ และทำการตรวจรับพัสดุในระบบ และเวียนลงนามตรวจรับ ผ่านระบบ MUERP'),
                         (12, '12. เสนอขออนุมัติเบิกจ่าย ผ่านหัวหน้าหน่วยพัสดุ หัวหน้างานคลังฯ รองคณบดีฝ่ายการคลังฯ และคณบดีลงนาม'),
                         (13, '13. สแกนเอกสารเก็บไฟล์ และส่งเอกสารเพื่อตั้งฎีกาเบิกจ่าย'),
                         (14, '14. ตั้งฎีกาเบิกจ่าย+เสนอคณบดีลงนามฎีกาเบิกจ่าย+ส่งเอกสารไปกองคลัง ผ่านระบบ MUERP'),
                         (15, '15. รอเช็คสั่งจ่ายจากกองคลัง ผ่านระบบ MUERP')]
                        )

@purchase_tracker.route('/first/')
def first_page():
    return render_template('purchase_tracker/first_page.html')


@purchase_tracker.route('/personnel/personnel_index')
def staff_index():
    return render_template('purchase_tracker/personnel/personnel_index.html')


@purchase_tracker.route('/home')
def index():
    return render_template('purchase_tracker/index.html')


@purchase_tracker.route('/create', methods=['GET', 'POST'])
def add_account():
    form = CreateAccountForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            filename = ''
            purchase_tracker = PurchaseTrackerAccount()
            form.populate_obj(purchase_tracker)
            purchase_tracker.creation_date = bangkok.localize(datetime.now())
            purchase_tracker.staff = current_user
            drive = initialize_gdrive()
            if form.upload.data:
                if not filename or (form.upload.data.filename != filename):
                    upfile = form.upload.data
                    filename = secure_filename(upfile.filename)
                    upfile.save(filename)
                    file_drive = drive.CreateFile({'title': filename,
                                                   'parents': [{'id': FOLDER_ID, "kind": "drive#fileLink"}]})
                    file_drive.SetContentFile(filename)
                    try:
                        file_drive.Upload()
                        permission = file_drive.InsertPermission({'type': 'anyone',
                                                                  'value': 'anyone',
                                                                  'role': 'reader'})
                    except:
                        flash('Failed to upload the attached file to the Google drive.', 'danger')
                    else:
                        flash('The attached file has been uploaded to the Google drive', 'success')
                        purchase_tracker.url = file_drive['id']

            db.session.add(purchase_tracker)
            db.session.commit()
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
            return render_template('purchase_tracker/personnel/personnel_index.html')
        # Check Error
        else:
            for er in form.errors:
                flash(er, 'danger')
    return render_template('purchase_tracker/create_account.html', form=form)


def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scopes)
    return GoogleDrive(gauth)


@purchase_tracker.route('/track')
def track():
    trackers = PurchaseTrackerAccount.query.filter_by(staff_id=current_user.id).all()
    chart_data = ACTIVITIES
    return render_template('purchase_tracker/tracking.html', trackers=trackers, chart_data=chart_data)



@purchase_tracker.route('/supplies')
def supplies():
    from sqlalchemy import desc
    purchase_trackers = PurchaseTrackerAccount.query.all()
    return render_template('purchase_tracker/procedure_supplies.html',
                           purchase_trackers=purchase_trackers,
                           desc=desc,
                           PurchaseTrackerStatus=PurchaseTrackerStatus)


@purchase_tracker.route('/description')
def description():
    return render_template('purchase_tracker/description.html')


@purchase_tracker.route('/contact')
def contact():
    return render_template('purchase_tracker/contact_us.html')


@purchase_tracker.route('/items/<int:account_id>/records/update', methods=['GET', 'POST'])
def view_items(account_id):
    form = StatusForm(obj=purchase_tracker)
    purchase_tracker.staff = current_user
    tracker = PurchaseTrackerAccount.query.get(account_id)
    return render_template('purchase_tracker/update_record.html', tracker=tracker, form=form)


@purchase_tracker.route('/update/<int:account_id>', methods=['GET', 'POST'])
@login_required
def update_status(account_id):
    form = StatusForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            status = PurchaseTrackerStatus()
            form.populate_obj(status)
            status.account_id = account_id
            status.status_date = bangkok.localize(datetime.now())
            status.creation_date = bangkok.localize(datetime.now())
            status.cancel_datetime = bangkok.localize(datetime.now())
            status.update_datetime = bangkok.localize(datetime.now())
            status.staff = current_user
            status.end_date = form.start_date.data + timedelta(days=int(form.days.data))
            # TODO: calculate end date from time needed to finish the task
            db.session.add(status)
            db.session.commit()
            flash(u'อัพเดตข้อมูลเรียบร้อย', 'success')
        # Check Error
        else:
            for er in form.errors:
                flash(er, 'danger')
    return redirect(url_for('purchase_tracker.view_items', account_id=account_id, form=form))

