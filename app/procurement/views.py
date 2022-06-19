# -*- coding:utf-8 -*-
import os, requests

from flask import render_template, request, flash, redirect, url_for, session, jsonify, Flask, send_file
from flask_login import current_user, login_required
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing

from werkzeug.utils import secure_filename
from . import procurementbp as procurement
from .forms import *
from datetime import datetime
from pytz import timezone
from pydrive.drive import GoogleDrive
from flask import (request, send_file)
from reportlab.platypus import (SimpleDocTemplate, Table, Image,
                                Spacer, Paragraph, TableStyle, PageBreak, Frame)
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
import qrcode
from reportlab.platypus import Image
from reportlab.graphics.barcode import qr
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib import colors


style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))
style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', alignment=TA_CENTER))

# Upload images for Google Drive


FOLDER_ID = "1JYkU2kRvbvGnmpQ1Tb-TcQS-vWQKbXvy"

json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()

bangkok = timezone('Asia/Bangkok')

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


@procurement.route('/new/add', methods=['GET', 'POST'])
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


@procurement.route('/landing')
def landing():
    return render_template('procurement/landing.html')


@procurement.route('/information/all')
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


@procurement.route('/information/find', methods=['POST', 'GET'])
@login_required
def find_data():
    return render_template('procurement/find_data.html')


@procurement.route('/edit/<int:procurement_id>', methods=['GET', 'POST'])
@login_required
def edit_procurement(procurement_id):
    procurement = ProcurementDetail.query.get(procurement_id)
    form = CreateProcurementForm(obj=procurement)
    if request.method == 'POST':
        form.populate_obj(procurement)
        db.session.add(procurement)
        db.session.commit()
        flash(u'แก้ไขข้อมูลเรียบร้อย', 'success')
        return redirect(url_for('procurement.view_procurement'))
    return render_template('procurement/edit_procurement.html', form=form, procurement=procurement)


@procurement.route('/qrcode/view/<int:procurement_id>')
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


@procurement.route('/service/require', methods=['GET', 'POST'])
def require_service():
    form = ProcurementRequireForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_contact = ProcurementRequire()
            form.populate_obj(new_contact)
            new_contact.staff = current_user
            db.session.add(new_contact)
            db.session.commit()
            flash('New record has been added.', 'success')
            return redirect(url_for('procurement.view_maintenance'))
    return render_template('procurement/contact_maintenance.html', form=form)


@procurement.route('/maintenance/all')
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


@procurement.route('/maintenance/user/require')
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


@procurement.route('/qrcode/scanner')
def qrcode_scanner():
    return render_template('procurement/qr_scanner.html')


@procurement.route('/qrcode/render/<string:procurement_no>')
def qrcode_render(procurement_no):
    item = ProcurementDetail.query.filter_by(procurement_no=procurement_no)
    return render_template('procurement/qrcode_render.html',
                           item=item)


@procurement.route('/qrcode/list')
def list_qrcode():
    qrcode_list = []
    procurement_query = ProcurementDetail.query.all()
    for procurement in procurement_query:
        record = {}
        record["id"] = procurement.id
        record["name"] = procurement.name
        record["procurement_no"] = procurement.procurement_no
        record["budget_year"] = procurement.budget_year
        record["responsible_person"] = procurement.responsible_person
        qrcode_list.append(record)
    return render_template('procurement/list_qrcode.html', qrcode_list=qrcode_list)


@procurement.route('/qrcode/list/<int:procurement_id>/view')
def list_qrcode_one_by_one(procurement_id):
    item = ProcurementDetail.query.get(procurement_id)
    return render_template('procurement/list_qrcode_one_by_one.html',
                           model=ProcurementRecord, item=item,
                           procurement_no=item.procurement_no)


@procurement.route('/qrcode/pdf/list/<int:procurement_id>/<string:procurement_no>')
def export_qrcode_pdf(procurement_id, procurement_no):
    procurement = ProcurementDetail.query.get(procurement_id)

    def all_page_setup(canvas, doc):
        canvas.saveState()
        logo_image = ImageReader('app/static/img/mumt-logo.png')
        canvas.drawImage(logo_image, 10, 700, width=250, height=100)
        canvas.restoreState()

    doc = SimpleDocTemplate("app/qrcode.pdf",
                            rightMargin=20,
                            leftMargin=20,
                            topMargin=20,
                            bottomMargin=10,
                            pagesize=letter
                            )
    data = []
    qr_img = qrcode.make(procurement_no, box_size=4)
    qr_img.save('test.png')
    data.append(Image('test.png'))

    # pdf = canvas.Canvas("qrcode.pdf")
    # frame = Frame(300, 150, 200, 300, showBoundary=1)
    # frame.addFromList(data, pdf)
    # pdf.save()
    data.append(Paragraph('<para align=center><font size=18>ชื่อ / Name: {}<br/><br/></font></para>'
                          .format(procurement.name.encode('utf-8')),
                          style=style_sheet['ThaiStyle']))
    data.append(Paragraph('<para align=center><font size=18>รหัสครุภัณฑ์ / Procurement No: {}<br/><br/></font></para>'
                          .format(procurement.procurement_no.encode('utf-8')),
                          style=style_sheet['ThaiStyle']))
    data.append(Paragraph('<para align=center><font size=18>ปีงบประมาณที่ได้มา / Year: {}<br/><br/></font></para>'
                          .format(procurement.budget_year.encode('utf-8')),
                          style=style_sheet['ThaiStyle']))
    data.append(Paragraph('<para align=center><font size=18>ผู้รับผิดชอบ: {}<br/><br/></font></para>'
                          .format(procurement.responsible_person.encode('utf-8')),
                          style=style_sheet['ThaiStyle']))
    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    return send_file('qrcode.pdf')


@procurement.route('/qrcode/list/pdf/all')
def export_all_qrcode_pdf():
    procurement_query = ProcurementDetail.query.all()

    def all_page_setup(canvas, doc):
        canvas.saveState()
        # logo_image = ImageReader('app/static/img/mumt-logo.png')
        # canvas.drawImage(logo_image, 10, 700, width=250, height=100)
        canvas.restoreState()

    doc = SimpleDocTemplate("app/all_qrcode.pdf",
                            rightMargin=20,
                            leftMargin=20,
                            topMargin=20,
                            bottomMargin=10,
                            pagesize=letter
                            )
    data = []


    # pdf = canvas.Canvas("qrcode.pdf")
    # frame = Frame(300, 150, 200, 300, showBoundary=1)
    # frame.addFromList(data, pdf)
    # pdf.save()
    for procurement in procurement_query:
        qr_img = qrcode.make(procurement.procurement_no, box_size=4)
        qr_img.save('testing.png')
        data.append(Image('testing.png'))

        data.append(Paragraph('<para align=center><font size=18>ชื่อ / Name: {}<br/><br/></font></para>'
                              .format(procurement.name.encode('utf-8')),
                              style=style_sheet['ThaiStyle']))
        data.append(Paragraph('<para align=center><font size=18>รหัสครุภัณฑ์ / Procurement No: {}<br/><br/></font></para>'
                              .format(procurement.procurement_no.encode('utf-8')),
                              style=style_sheet['ThaiStyle']))
        data.append(Paragraph('<para align=center><font size=18>ปีงบประมาณที่ได้มา / Year: {}<br/><br/></font></para>'
                              .format(procurement.budget_year.encode('utf-8')),
                              style=style_sheet['ThaiStyle']))
        data.append(Paragraph('<para align=center><font size=18>ผู้รับผิดชอบ: {}<br/><br/></font></para>'
                              .format(procurement.responsible_person.encode('utf-8')),
                              style=style_sheet['ThaiStyle']))
    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    return send_file('all_qrcode.pdf')
