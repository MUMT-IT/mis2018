# -*- coding:utf-8 -*-
import requests, os
from flask import render_template, request, flash, redirect, url_for, send_from_directory, send_file
from flask_login import current_user, login_required
from oauth2client.service_account import ServiceAccountCredentials
from pandas import DataFrame
from pydrive.auth import GoogleAuth
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph
from sqlalchemy import cast, Date
from werkzeug.utils import secure_filename
from . import purchase_tracker_bp as purchase_tracker
from .forms import *
from datetime import datetime
from pytz import timezone
from pydrive.drive import GoogleDrive
from .models import PurchaseTrackerAccount, PurchaseTrackerForm
from flask_mail import Message
from ..main import mail
from ..staff.models import Role

# Upload images for Google Drive


FOLDER_ID = "1JYkU2kRvbvGnmpQ1Tb-TcQS-vWQKbXvy"

json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()

bangkok = timezone('Asia/Bangkok')

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


@purchase_tracker.route('/official/')
@login_required
def landing_page():
    return render_template('purchase_tracker/first_page.html')


@purchase_tracker.route('/personnel/personnel_index')
def staff_index():
    return render_template('purchase_tracker/personnel/personnel_index.html')


@purchase_tracker.route('/personnel/personnel_index/e-form/method/select/<int:account_id>')
def select_form(account_id):
    account = PurchaseTrackerAccount.query.get(account_id)
    return render_template('purchase_tracker/personnel/alternative_form.html', account=account)


@purchase_tracker.route('/main')
def index():
    return render_template('purchase_tracker/index.html')


@purchase_tracker.route('/account/create', methods=['GET', 'POST'])
@login_required
def add_account():
    form = CreateAccountForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            filename = ''
            account = PurchaseTrackerAccount()
            form.populate_obj(account)
            account.creation_date = bangkok.localize(datetime.now())
            account.staff = current_user
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
                        account.url = file_drive['id']

            db.session.add(account)
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


@purchase_tracker.route('/track/')
@purchase_tracker.route('/track/<int:account_id>', methods=['GET'])
def track(account_id=None):
    list_type = request.args.get('list_type')
    if list_type == "myAccount" or list_type is None:
        accounts = PurchaseTrackerAccount.query.filter_by(staff_id=current_user.id).all()
    elif list_type == "ourAccount":
        org = current_user.personal_info.org
        accounts = [account for account in PurchaseTrackerAccount.query.all()
                    if account.staff.personal_info.org == org]
    return render_template('purchase_tracker/tracking.html',
                           account_id=account_id, accounts=accounts, list_type=list_type)


@purchase_tracker.route('/track/<int:account_id>/view')
def view_info_track(account_id=None):
    from sqlalchemy import desc
    if account_id:
        account = PurchaseTrackerAccount.query.get(account_id)
        # better make use of the relationship!
        activities = [a.to_list() for a in account.records.all()]
    else:
        flash(u'ข้อมูลจะปรากฎเมื่อหน่วยงานคลังและพัสดุอัพเดตเรียบร้อย', 'warning')
        activities = []
    # activities = [a.to_list() for a in PurchaseTrackerStatus.query.filter_by(account_id=account_id)
    #     .order_by(PurchaseTrackerStatus.start_date)]
    if not activities:
        default_date = datetime.now().isoformat()
    else:
        default_date = activities[-1][3]
    return render_template('purchase_tracker/view_info_track.html',
                           account_id=account_id, account=account, desc=desc,
                           PurchaseTrackerStatus=PurchaseTrackerStatus,
                           activities=activities, default_date=default_date)


@purchase_tracker.route('/account/<int:account_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_account(account_id):
    account = PurchaseTrackerAccount.query.get(account_id)
    form = CreateAccountForm(obj=account)
    if request.method == 'POST':
        if form.validate_on_submit():
            filename = ''
            form.populate_obj(account)
            account.creation_date = bangkok.localize(datetime.now())
            account.staff = current_user
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

            db.session.add(account)
            db.session.commit()
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
            return redirect(url_for('purchase_tracker.track'))
        # Check Error
        else:
            for er in form.errors:
                flash(er, 'danger')
    return render_template('purchase_tracker/edit_account.html', form=form, account_id=account_id)


@purchase_tracker.route('/accounts/<int:account_id>/cancel', methods=['GET'])
@login_required
def cancel_account(account_id):
    account = PurchaseTrackerAccount.query.get(account_id)
    if not account.cancelled_datetime:
        account.cancelled_datetime = datetime.now(tz=bangkok)
        account.cancelled_by = current_user
        db.session.add(account)
        db.session.commit()
        flash(u'ยกเลิกบัญชีเรียบร้อยแล้ว', 'success')
    else:
        flash(u'บัญชีนี้ถูกยุติการดำเนินการแล้ว', 'warning')
    next = request.args.get('next')
    if next:
        return redirect(next)
    return redirect(url_for('purchase_tracker.track', account_id=account_id))


@purchase_tracker.route('/accounts/<int:account_id>/close', methods=['GET'])
@login_required
def close_account(account_id):
    account = PurchaseTrackerAccount.query.get(account_id)
    if not account.end_datetime:
        account.end_datetime = datetime.now(tz=bangkok)
        db.session.add(account)
        db.session.commit()
        flash(u'ปิดบัญชีเรียบร้อยแล้ว', 'success')
    else:
        flash(u'บัญชีนี้ถูกปิดการดำเนินการแล้ว', 'warning')
    return redirect(url_for('purchase_tracker.update_status', account_id=account_id))


@purchase_tracker.route('/supplies/')
def supplies():
    role = Role.query.filter_by(name='admin', app_name='PurchaseTracker').first()
    if role in current_user.roles:
        from sqlalchemy import desc
        accounts = PurchaseTrackerAccount.query.all()
        return render_template('purchase_tracker/procedure_supplies.html',
                               accounts=accounts,
                               desc=desc,
                               PurchaseTrackerStatus=PurchaseTrackerStatus)
    else:
        flash('Permission not allow', 'danger')
        return redirect(url_for('purchase_tracker.landing_page'))


@purchase_tracker.route('/description')
def description():
    return render_template('purchase_tracker/description.html')


@purchase_tracker.route('/contact')
def contact():
    return render_template('purchase_tracker/contact_us.html')


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


@purchase_tracker.route('/account/<int:account_id>/update', methods=['GET', 'POST'])
@login_required
def update_status(account_id):
    form = StatusForm()
    account = PurchaseTrackerAccount.query.get(account_id)
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
            if not form.other_activity.data and not form.activity.data:
                flash(u'กรุณาเลือกหัวข้อกิจกรรมหรือใส่กิจกรรมอื่นๆ.', 'danger')
                return redirect(url_for('purchase_tracker.update_status', account_id=account_id, form=form, account=account))
            db.session.add(status)
            db.session.commit()
            title = u'แจ้งเตือนการปรับเปลี่ยนสถานะการจัดซื้อพัสดุและครุภัณฑ์หมายเลข {}'.format(status.account.number)
            message = u'เรียน {}\n\nสถานะการจัดซื้อพัสดุและครุภัณฑ์หมายเลข {} คือ {}'\
                .format(current_user.personal_info.fullname, status.account.number, status.other_activity or status.activity.activity)
            message += u'\n\n======================================================'
            message += u'\nอีเมลนี้ส่งโดยระบบอัตโนมัติ กรุณาอย่าตอบกลับ ' \
                       u'หากมีปัญหาใดๆเกี่ยวกับเว็บไซต์กรุณาติดต่อหน่วยข้อมูลและสารสนเทศ '
            message += u'\nThis email was sent by an automated system. Please do not reply.' \
                       u' If you have any problem about website, please contact the IT unit.'
            send_mail([u'{}@mahidol.ac.th'.format(account.staff.email)], title, message)
            flash(u'อัพเดตข้อมูลเรียบร้อย', 'success')
            form.activity.data = ""
            form.other_activity.data = ""
            form.comment.data = ""
        # Check Error
        else:
            flash(form.errors, 'danger')

    activities = [a.to_list() for a in PurchaseTrackerStatus.query.filter_by(account_id=account_id)
        .order_by(PurchaseTrackerStatus.start_date)]
    if not activities:
        default_date = datetime.now().isoformat()
    else:
        default_date = activities[-1][3]
    return render_template('purchase_tracker/update_record.html',
                            account_id=account_id, form=form, activities=activities, account=account,
                           default_date=default_date)


@purchase_tracker.route('/account/<int:account_id>/status/<int:status_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_update_status(account_id, status_id):
    status = PurchaseTrackerStatus.query.get(status_id)
    form = StatusForm(obj=status)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(status)
            status.account_id = account_id
            status.status_date = bangkok.localize(datetime.now())
            status.creation_date = bangkok.localize(datetime.now())
            status.cancel_datetime = bangkok.localize(datetime.now())
            status.update_datetime = bangkok.localize(datetime.now())
            status.staff = current_user
            db.session.add(status)
            db.session.commit()
            title = u'แจ้งเตือนการแก้ไขปรับเปลี่ยนสถานะการจัดซื้อพัสดุและครุภัณฑ์หมายเลข {}'.format(status.account.number)
            message = u'เรียน {}\n\nสถานะการจัดซื้อพัสดุและครุภัณฑ์หมายเลข {} คือ {}' \
                .format(current_user.personal_info.fullname, status.account.number, status.other_activity or status.activity.activity)
            message += u'\n\n======================================================'
            message += u'\nอีเมลนี้ส่งโดยระบบอัตโนมัติ กรุณาอย่าตอบกลับ ' \
                       u'หากมีปัญหาใดๆเกี่ยวกับเว็บไซต์กรุณาติดต่อหน่วยข้อมูลและสารสนเทศ '
            message += u'\nThis email was sent by an automated system. Please do not reply.' \
                       u' If you have any problem about website, please contact the IT unit.'
            send_mail([u'{}@mahidol.ac.th'.format(status.account.staff.email)], title, message)
            flash(u'แก้ไขข้อมูลเรียบร้อย', 'success')
        return redirect(url_for('purchase_tracker.update_status', status_id=status.id, account_id=account_id))
    return render_template('purchase_tracker/edit_update_record.html',
                                account_id=account_id, form=form)


@purchase_tracker.route('/account/<int:account_id>/status/<int:status_id>/delete')
@login_required
def delete_update_status(account_id, status_id):
    if account_id:
        status = PurchaseTrackerStatus.query.get(status_id)
        flash(u'The update status has been removed.')
        db.session.delete(status)
        db.session.commit()
        return redirect(url_for('purchase_tracker.update_status', account_id=account_id))


@purchase_tracker.route('/account/update_status/info/download')
@login_required
def update_status_info_download():
    accounts = PurchaseTrackerAccount.query.filter_by(staff_id=current_user.id).all()
    records = []
    for account in accounts:
        for record in account.records:
            records.append({
                u'เลขที่หนังสือ': u"{}".format(account.number),
                u'วันที่หนังสือ': u"{}".format(account.booking_date),
                u'ชื่อ': u"{}".format(account.subject),
                u'วงเงินหลักการ': u"{:,.2f}".format(account.amount),
                u'รูปแบบหลักการ': u"{}".format(account.formats),
                u'ผู้สร้าง account โดย': u"{}".format(account.staff.personal_info.fullname),
                u'หน่วยงาน/ภาควิชา': u"{}".format(account.staff.personal_info.org.name),
                u'กิจกรรม': u"{}".format(record.other_activity or record.activity.activity),
                u'ผู้รับผิดชอบ': u"{}".format(record.staff.personal_info.fullname),
                u'วันเริ่มกิจกรรม': u"{}".format(record.start_date),
                u'วันสิ้นสุดกิจกรรม': u"{}".format(record.end_date),
                u'หมายเหตุเพิ่มเติม': u"{}".format(record.comment),
                u'เวลาดำเนินกิจกรรม': u"{}".format(record.weekdays),
                    })
    df = DataFrame(records)
    df.to_excel('account_summary.xlsx')
    return send_from_directory(os.getcwd(), filename='account_summary.xlsx')


@purchase_tracker.route('/create/<int:account_id>/activity', methods=['GET', 'POST'])
@login_required
def add_activity(account_id):
    activity = db.session.query(PurchaseTrackerActivity)
    form = CreateActivityForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_activity = PurchaseTrackerActivity()
            form.populate_obj(new_activity)
            db.session.add(new_activity)
            db.session.commit()
            flash(u'บันทึกการเพิ่มกิจกรรมใหม่สำเร็จ.', 'success')
            return redirect(url_for('purchase_tracker.update_status', account_id=account_id))
        # Check Error
        else:
            for er in form.errors:
                flash(er, 'danger')
    return render_template('purchase_tracker/create_activity.html', form=form, activity=activity, account_id=account_id)


@purchase_tracker.route('/dashboard/', methods=['GET', 'POST'])
def show_info_page():
    start_date = None
    end_date = None
    account_query = PurchaseTrackerAccount.query.all()
    form = ReportDateForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            start_date = datetime.strptime(form.start_date.data, '%d-%m-%Y')
            end_date = datetime.strptime(form.end_date.data, '%d-%m-%Y')
            account_query = PurchaseTrackerAccount.query.filter(cast(PurchaseTrackerAccount.booking_date, Date) >= start_date)\
                .filter(cast(PurchaseTrackerAccount.booking_date, Date) <= end_date)
        else:
            flash(form.errors, 'danger')
    return render_template('purchase_tracker/info_page.html', account_query=account_query, form=form,
                           start_date=start_date, end_date=end_date)


@purchase_tracker.route('/dashboard/info/download', methods=['GET'])
def dashboard_info_download():
    records = []
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if start_date and end_date:
        accounts = PurchaseTrackerAccount.query.filter(cast(PurchaseTrackerAccount.booking_date, Date) >= start_date)\
                .filter(cast(PurchaseTrackerAccount.booking_date, Date) <= end_date)
    else:
        accounts = PurchaseTrackerAccount.query.all()

    for account in accounts:
        for record in account.records:
            records.append({
                u'เลขที่หนังสือ': u"{}".format(account.number),
                u'วันที่หนังสือ': u"{}".format(account.booking_date),
                u'ชื่อ': u"{}".format(account.subject),
                u'วงเงินหลักการ': u"{:,.2f}".format(account.amount),
                u'รูปแบบหลักการ': u"{}".format(account.formats),
                u'ผู้สร้าง account โดย': u"{}".format(account.staff.personal_info.fullname),
                u'หน่วยงาน/ภาควิชา': u"{}".format(account.staff.personal_info.org.name),
                u'กิจกรรม': u"{}".format(record.other_activity or record.activity.activity),
                u'ผู้รับผิดชอบ': u"{}".format(record.staff.personal_info.fullname),
                u'วันเริ่มกิจกรรม': u"{}".format(record.start_date),
                u'วันสิ้นสุดกิจกรรม': u"{}".format(record.end_date),
                u'หมายเหตุเพิ่มเติม': u"{}".format(record.comment),
                u'เวลาดำเนินกิจกรรม': u"{}".format(record.weekdays),
            })
    df = DataFrame(records)
    df.to_excel('account_summary.xlsx')
    return send_from_directory(os.getcwd(), filename='account_summary.xlsx')


@purchase_tracker.route('/personnel/personnel_index/e-form/create/<string:form_code>/<int:account_id>', methods=['GET', 'POST'])
@login_required
def create_form(account_id, form_code):
    account = PurchaseTrackerAccount.query.get(account_id)
    MTPCform = create_MTPCForm(acnt=account)
    form = MTPCform()
    if form.validate_on_submit():
        new_form = PurchaseTrackerForm()
        form.populate_obj(new_form)
        new_form.staff = current_user
        db.session.add(new_form)
        db.session.commit()
        flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        export_blank_form_pdf(new_form)
    # Check Error
    else:
        for er in form.errors:
            flash("{}:{}".format(er,form.errors[er]), 'danger')
    return render_template('purchase_tracker/personnel/create_form_{}.html'.format(form_code), form=form, account=account)


sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
pdfmetrics.registerFont(sarabun_font)
style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))
style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', alignment=TA_CENTER))


def export_blank_form_pdf(form):

    def all_page_setup(canvas, doc):
        canvas.saveState()
        logo_image = ImageReader('app/static/img/logo-MU_black-white-2-1.png')
        canvas.drawImage(logo_image, 10, 700, width=250, height=100)
        canvas.restoreState()

    doc = SimpleDocTemplate("app/e-form.pdf",
                            rightMargin=20,
                            leftMargin=20,
                            topMargin=20,
                            bottomMargin=10
                            )
    data = [ Paragraph('<font size=12>{}</font>'.format(form.account.number), style=style_sheet['ThaiStyle']),]

    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    return send_file('e-form.pdf')



