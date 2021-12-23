# -*- coding:utf-8 -*-
import requests, os, smtplib
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


@purchase_tracker.route('/official/')
def first_page():
    return render_template('purchase_tracker/first_page.html')


@purchase_tracker.route('/personnel/personnel_index')
def staff_index():
    return render_template('purchase_tracker/personnel/personnel_index.html')


@purchase_tracker.route('/main')
def index():
    return render_template('purchase_tracker/index.html')


@purchase_tracker.route('/create', methods=['GET', 'POST'])
@login_required
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


@purchase_tracker.route('/track/')
@purchase_tracker.route('/track/<int:account_id>')
def track(account_id=None):
    if account_id is not None:
        from sqlalchemy import desc
        tracker = PurchaseTrackerAccount.query.get(account_id)
        trackers = PurchaseTrackerAccount.query.filter_by(staff_id=current_user.id).all()
        activities = [a.to_list() for a in PurchaseTrackerStatus.query.filter_by(account_id=account_id)
            .order_by(PurchaseTrackerStatus.start_date)]
        if not activities:
            default_date = datetime.now().isoformat()
        else:
            default_date = activities[-1][3]
        return render_template('purchase_tracker/tracking.html',
                               account_id=account_id,
                               tracker=tracker,
                               trackers=trackers,
                               desc=desc,
                               PurchaseTrackerStatus=PurchaseTrackerStatus,
                               activities=activities,
                               default_date=default_date)
    else:
        from sqlalchemy import desc
        tracker = PurchaseTrackerAccount.query.get(account_id)
        trackers = PurchaseTrackerAccount.query.filter_by(staff_id=current_user.id).all()
        activities = [a.to_list() for a in PurchaseTrackerStatus.query.filter_by(account_id=account_id)
            .order_by(PurchaseTrackerStatus.start_date)]
        if not activities:
            default_date = datetime.now().isoformat()
        else:
            default_date = activities[-1][3]
        return render_template('purchase_tracker/tracking.html',
                               account_id=account_id,
                               tracker=tracker,
                               trackers=trackers,
                               desc=desc,
                               PurchaseTrackerStatus=PurchaseTrackerStatus,
                               activities=activities,
                               default_date=default_date)


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


@purchase_tracker.route('/update/<int:account_id>', methods=['GET', 'POST'])
@login_required
def update_status(account_id):
    form = StatusForm()
    tracker = PurchaseTrackerAccount.query.get(account_id)
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
    activities = [a.to_list() for a in PurchaseTrackerStatus.query.filter_by(account_id=account_id)
        .order_by(PurchaseTrackerStatus.start_date)]
    if not activities:
        default_date = datetime.now().isoformat()
    else:
        default_date = activities[-1][3]
    return render_template('purchase_tracker/update_record.html',
                            account_id=account_id, form=form, activities=activities, tracker=tracker,
                           default_date=default_date)


@purchase_tracker.route('/edit_update/<int:account_id>', methods=['GET', 'POST'])
@login_required
def edit_update_status(account_id):
    tracker = PurchaseTrackerStatus.query.get(account_id)
    form = StatusForm(obj=tracker)
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
    return render_template('purchase_tracker/edit_update_record.html',
                                account_id=account_id, form=form, tracker=tracker)


@purchase_tracker.route('/edit_update/delete/<int:account_id>')
@login_required
def delete_update_status(account_id):
    if account_id:
        tracker = PurchaseTrackerStatus.query.get(account_id)
        flash(u'Information {} has been removed from the update status.')
        db.session.delete(tracker)
        db.session.commit()
    return redirect(url_for('purchase_tracker.update_status', account_id=tracker.id))
