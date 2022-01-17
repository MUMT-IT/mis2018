# -*- coding:utf-8 -*-
import os, requests

from flask import render_template, request, flash, redirect, url_for, session, jsonify, Flask
from flask_login import current_user, login_required
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from werkzeug.utils import secure_filename

from . import procurementbp as procurement
from .models import ProcurementDetail
from ..main import db
from .forms import *
from datetime import datetime
from pytz import timezone
from pydrive.drive import GoogleDrive
# Upload images for Google Drive
FOLDER_ID = "1JYkU2kRvbvGnmpQ1Tb-TcQS-vWQKbXvy"

json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()

bangkok = timezone('Asia/Bangkok')

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


@procurement.route('/add', methods=['GET','POST'])
@login_required
def add_procurement():
    form = CreateProcurementForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            filename = ''
            procurement = ProcurementDetail()
            form.populate_obj(procurement)
            procurement.creation_date = bangkok.localize(datetime.now())
            procurement.staff = current_user
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
                        procurement.url = file_drive['id']

            db.session.add(procurement)
            db.session.commit()
            flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
            return redirect(url_for('procurement.view_procurement'))
        # Check Error
        else:
            for er in form.errors:
                flash(er, 'danger')
    return render_template('procurement/new_procurement.html', form=form)


def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scopes)
    return GoogleDrive(gauth)


@procurement.route('/home')
def index():
    return render_template('procurement/index.html')


@procurement.route('/allData')
@login_required
def view_procurement():
    procurement_list = []
    procurement_query = ProcurementDetail.query.all()
    for procurement in procurement_query:
        record = {}
        record["id"] = procurement.id
        record["name"] = procurement.name
        record["procurement_no"] = procurement.procurement_no
        record["erp_code"] = procurement.erp_code
        record["budget_year"] = procurement.budget_year
        record["received_date"] = procurement.received_date
        record["bought_by"] = procurement.bought_by
        record["available"] = procurement.available
        procurement_list.append(record)
    return render_template('procurement/view_all_data.html', procurement_list=procurement_list)


@procurement.route('/findData', methods=['POST', 'GET'])
@login_required
def find_data():
    return render_template('procurement/find_data.html')


@procurement.route('/explanation')
def explanation():
    return render_template('procurement/explanation.html')

@procurement.route('/edit/<int:procurement_id>', methods=['GET','POST'])
@login_required
def edit_procurement(procurement_id):
    procurement = ProcurementDetail.query.get(procurement_id)
    form = CreateProcurementForm(obj=procurement)
    if request.method == 'POST':
        pro_edit = ProcurementDetail()
        form.populate_obj(pro_edit)
        db.session.add(pro_edit)
        db.session.commit()
        flash(u'แก้ไขข้อมูลเรียบร้อย', 'success')
        return redirect(url_for('procurement.view_procurement'))
    return render_template('procurement/edit_procurement.html', form=form, procurement=procurement)


@procurement.route('/viewqrcode/<int:procurement_id>')
@login_required
def view_qrcode(procurement_id):
    item = ProcurementDetail.query.get(procurement_id)
    return render_template('procurement/view_qrcode.html',
                           model=ProcurementRecord,
                           item=item,
                           procurement_no=item.procurement_no)


@procurement.route('/items/<int:item_id>/records/add', methods=['GET', 'POST'])
@login_required
def add_record(item_id):
    form = ProcurementRecordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_record = ProcurementRecord()
            form.populate_obj(new_record)
            new_record.item_id = item_id
            new_record.staff = current_user
            new_record.updated_at = datetime.now(tz=bangkok)
            db.session.add(new_record)
            db.session.commit()
            flash('New Record Has Been Added.', 'success')
            return redirect(url_for('procurement.view_procurement'))
    return render_template('procurement/record_form.html', form=form)


@procurement.route('/category/add', methods=['GET', 'POST'])
def add_category_ref():
    category = db.session.query(ProcurementCategory)
    form = ProcurementCategoryForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_category = ProcurementCategory()
            form.populate_obj(new_category)
            db.session.add(new_category)
            db.session.commit()
            flash('New record has been added.', 'success')
            return redirect(url_for('procurement.index'))
    return render_template('procurement/category_ref.html', form=form, category=category)


@procurement.route('/contact/select')
def select_contact():
    return render_template('procurement/maintenance_contact.html')


@procurement.route('/contact/select/it', methods=['GET', 'POST'])
def contact_it():
    form = ProcurementRequireForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_contact = ProcurementRequire()
            form.populate_obj(new_contact)
            new_contact.staff = current_user
            db.session.add(new_contact)
            db.session.commit()
            flash('New record has been added.', 'success')
            return redirect(url_for('procurement.select_contact'))
    return render_template('procurement/contact_it.html', form=form)


@procurement.route('/contact/select/repair', methods=['GET', 'POST'])
def contact_repair():
    form = ProcurementRequireForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_contact = ProcurementRequire()
            form.populate_obj(new_contact)
            new_contact.staff = current_user
            db.session.add(new_contact)
            db.session.commit()
            flash('New record has been added.', 'success')
            return redirect(url_for('procurement.select_contact'))
    return render_template('procurement/contact_repair.html', form=form)


@procurement.route('/allMaintenance')
@login_required
def view_maintenance():
    maintenance_list = []
    maintenance_query = ProcurementRequire.query.all()
    for maintenance in maintenance_query:
        record = {}
        record["id"] = maintenance.id
        record["service"] = maintenance.service
        record["notice_date"] = maintenance.notice_date
        record["explan"] = maintenance.explan
        maintenance_list.append(record)
    return render_template('procurement/view_all_maintenance.html', maintenance_list=maintenance_list)


@procurement.route('/maintenance/user_require/')
@login_required
def view_require_service():
    require_list = []
    maintenance_query = ProcurementRequire.query.all()
    for maintenance in maintenance_query:
        record = {}
        record["id"] = maintenance.id
        record["service"] = maintenance.service
        record["notice_date"] = maintenance.notice_date
        record["explan"] = maintenance.explan
        require_list.append(record)
    return render_template('procurement/view_by_ITxRepair.html', require_list=require_list)


@procurement.route('/service/<int:service_id>/update', methods=['GET', 'POST'])
@login_required
def update_record(service_id):
    form = ProcurementMaintenanceForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            update_record = ProcurementMaintenance()
            form.populate_obj(update_record)
            update_record.service_id = service_id
            update_record.staff = current_user
            db.session.add(update_record)
            db.session.commit()
            flash('Update record has been added.', 'success')
            return redirect(url_for('procurement.view_require_service'))
    return render_template('procurement/update_by_ITxRepair.html', form=form)