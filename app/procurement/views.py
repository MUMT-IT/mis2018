# -*- coding:utf-8 -*-
import cStringIO
import os, requests
from base64 import b64decode

import dateutil
from flask import render_template, request, flash, redirect, url_for, send_file, send_from_directory, jsonify, session, \
    make_response
from flask_login import current_user, login_required
from pandas import DataFrame
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from sqlalchemy import cast, Date
from werkzeug.utils import secure_filename
from . import procurementbp as procurement
from .forms import *
from datetime import datetime
from pytz import timezone
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, TableStyle, Table, Spacer
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from ..main import csrf
from ..roles import procurement_committee_permission, procurement_permission

style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Times-Bold'))
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
    form = ProcurementDetailForm()

    if form.validate_on_submit():
        procurement = ProcurementDetail()
        form.populate_obj(procurement)
        procurement.creation_date = bangkok.localize(datetime.now())
        file = form.image_file_upload.data
        if file:
            img_name = secure_filename(file.filename)
            file.save(img_name)
            # convert image to base64(text) in database
            import base64
            with open(img_name, "rb") as img_file:
                procurement.image = base64.b64encode(img_file.read())

        db.session.add(procurement)
        db.session.commit()
        record = procurement.records.order_by(ProcurementRecord.id.desc()).first()
        record.updater = current_user
        record.updated_at = bangkok.localize(datetime.now())
        db.session.add(record)
        db.session.commit()
        flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return redirect(url_for('procurement.view_procurement'))
        # Check Error
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('procurement/new_procurement.html', form=form)


@procurement.route('/official/login')
@login_required
def first_page():
    return render_template('procurement/select_type_login.html')


@procurement.route('/official/for-user/login')
def user_first():
    return render_template('procurement/user_first_page.html', name=current_user)


@procurement.route('/official/for-procurement-staff/login')
@login_required
@procurement_permission.require()
def landing():
    return render_template('procurement/landing.html')


@procurement.route('/official/for-committee/login')
@login_required
@procurement_committee_permission.require()
def committee_first():
    return render_template('procurement/committee_first_page.html', name=current_user)


# @procurement.route('/info/by-committee/view', methods=['GET', 'POST'])
# @login_required
# def view_procurement_by_committee():
#     start_date = None
#     end_date = None
#     form = ProcurementApprovalForm()
#     if request.method == 'POST':
#         if form.validate_on_submit():
#             start_date = datetime.strptime(form.updated_at.data, '%d-%m-%Y')
#             end_date = datetime.strptime(form.updated_at.data, '%d-%m-%Y')
#
#         else:
#             flash(form.errors, 'danger')
#     return render_template('procurement/view_procurement_by_committee.html',
#                             start_date=start_date, end_date=end_date, form=form)
@procurement.route('/info/by-committee/view')
@login_required
def view_procurement_by_committee():
    return render_template('procurement/view_procurement_by_committee.html')


@procurement.route('/api/data/committee')
def get_procurement_data_to_committee():
    query = ProcurementDetail.query
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ProcurementDetail.procurement_no.like(u'%{}%'.format(search)),
        ProcurementDetail.name.like(u'%{}%'.format(search)),
        ProcurementDetail.erp_code.like(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        current_record = item.current_record
        item_data = item.to_dict()
        item_data['updated_at'] = current_record.approval.updated_at.strftime('%d/%m/%Y') if current_record and current_record.approval else ''
        item_data['checking_result'] = current_record.approval.checking_result if current_record and current_record.approval else ''
        item_data['approver'] = current_record.approval.approver.personal_info.fullname if current_record and current_record.approval else ''
        item_data['status'] = current_record.approval.asset_status if current_record and current_record.approval else ''
        item_data['approver_comment'] = current_record.approval.approval_comment if current_record and current_record.approval else ''
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementDetail.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@procurement.route('/info/by-committee/download', methods=['GET'])
def report_info_download():
    records = []
    procurement_query = ProcurementDetail.query

    for item in procurement_query:
        current_record = item.current_record
        if current_record and current_record.approval:
            records.append({
            u'ศูนย์ต้นทุน': u"{}".format(item.cost_center),
            u'Inventory Number/ERP': u"{}".format(item.erp_code),
            u'เลขครุภัณฑ์': u"{}".format(item.procurement_no),
            u'Sub Number': u"{}".format(item.sub_number),
            u'ชื่อครุภัณฑ์': u"{}".format(item.name),
            u'จัดซื้อด้วยเงิน': u"{}".format(item.purchasing_type),
            u'มูลค่าที่ได้มา': u"{}".format(item.curr_acq_value),
            u'Original value': u"{}".format(item.price),
            u'สภาพของสินทรัพย์': u"{}".format(item.available),
            u'วันที่ได้รับ': u"{}".format(item.received_date),
            u'ปีงบประมาณ': u"{}".format(item.budget_year),
            u'วัน-เวลาที่ตรวจ': u"{}".format(
                current_record.approval.updated_at),
            u'ผลการตรวจสอบ': u"{}".format(
                current_record.approval.checking_result),
            u'ผู้ตรวจสอบ': u"{}".format(
                current_record.approval.approver.personal_info.fullname),
            u'สถานะ': u"{}".format(
                current_record.approval.asset_status),
            u'Comment': u"{}".format(
                current_record.approval.approval_comment)
        })
    df = DataFrame(records)
    df.to_excel('report.xlsx',
                header=True,
                columns=[u'ศูนย์ต้นทุน',
                         u'Inventory Number/ERP',
                         u'เลขครุภัณฑ์',
                         u'Sub Number',
                         u'ชื่อครุภัณฑ์',
                         u'จัดซื้อด้วยเงิน',
                         u'มูลค่าที่ได้มา',
                         u'Original value',
                         u'สภาพของสินทรัพย์',
                         u'วันที่ได้รับ',
                         u'ปีงบประมาณ',
                         u'วัน-เวลาที่ตรวจ',
                         u'ผลการตรวจสอบ',
                         u'ผู้ตรวจสอบ',
                         u'สถานะ',
                         u'Comment'
                         ],
                index=False,
                encoding='utf-8')
    return send_from_directory(os.getcwd(), filename='report.xlsx')


@procurement.route('/for-committee/search-info', methods=['GET', 'POST'])
@login_required
def search_erp_code_info():
    return render_template('procurement/committee_find_erp_code_to_approve.html')


@procurement.route('/api/data/search')
def get_procurement_search_data():
    query = ProcurementDetail.query
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ProcurementDetail.erp_code.like(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        item_data['check'] = '<a href="{}"><i class="far fa-check-circle"></i></a>'.format(
            url_for('procurement.view_procurement_on_scan', procurement_no=item.procurement_no))
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementDetail.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@procurement.route('/information/view')
@login_required
def view_procurement():
    return render_template('procurement/view_all_data.html')


@procurement.route('/api/data')
def get_procurement_data():
    query = ProcurementDetail.query
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ProcurementDetail.procurement_no.like(u'%{}%'.format(search)),
        ProcurementDetail.name.like(u'%{}%'.format(search)),
        ProcurementDetail.erp_code.like(u'%{}%'.format(search)),
        ProcurementDetail.available.like(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        item_data['view'] = '<a href="{}"><i class="fas fa-eye"></i></a>'.format(
            url_for('procurement.view_qrcode', procurement_id=item.id))
        item_data['edit'] = '<a href="{}"><i class="fas fa-edit"></i></a>'.format(
            url_for('procurement.edit_procurement', procurement_id=item.id))
        item_data['received_date'] = item_data['received_date'].strftime('%d/%m/%Y') if item_data[
            'received_date'] else ''
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementDetail.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@procurement.route('/information/updated')
@login_required
def view_procurement_updated():
    return render_template('procurement/view_all_data_is_updated.html')


@procurement.route('/api/data/updated')
def get_procurement_data_is_updated():
    query = ProcurementDetail.query
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ProcurementDetail.procurement_no.like(u'%{}%'.format(search)),
        ProcurementDetail.name.like(u'%{}%'.format(search)),
        ProcurementDetail.erp_code.like(u'%{}%'.format(search)),
        ProcurementDetail.available.like(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        current_record = item.current_record
        item_data = item.to_dict()
        item_data['location'] = u'{}'.format(current_record.location)
        item_data['status'] = u'{}'.format(current_record.status)
        item_data['updater'] = u'{}'.format(current_record.updater)
        item_data['updated_at'] = u'{}'.format(current_record.updated_at)
        item_data['received_date'] = item_data['received_date'].strftime('%d/%m/%Y') if item_data[
            'received_date'] else ''
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementDetail.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@procurement.route('/information/find', methods=['POST', 'GET'])
@login_required
def find_data():
    return render_template('procurement/find_data.html')


@procurement.route('/edit/<int:procurement_id>', methods=['GET', 'POST'])
@login_required
def edit_procurement(procurement_id):
    procurement = ProcurementDetail.query.get(procurement_id)
    form = ProcurementDetailForm(obj=procurement)
    if request.method == 'POST':
        form.populate_obj(procurement)
        record = procurement.current_record
        record.updated_at = bangkok.localize(datetime.now())
        db.session.add(record)

        file = form.image_file_upload.data
        if file:
            img_name = secure_filename(file.filename)
            file.save(img_name)
            # convert image to base64(text) in database
            import base64
            with open(img_name, "rb") as img_file:
                procurement.image = base64.b64encode(img_file.read())
        db.session.add(procurement)
        db.session.commit()
        flash(u'แก้ไขข้อมูลเรียบร้อย', 'success')
        return redirect(url_for('procurement.view_qrcode', procurement_id=procurement_id, url_next=url_for('procurement.view_procurement')))
    return render_template('procurement/edit_procurement.html', form=form, procurement=procurement,
                           url_callback=request.referrer)


# @procurement.route('information/report')
# @login_required
# def report_info():
#     data = ProcurementDetail.query
#     return render_template('procurement/report_info.html', data=data)


@procurement.route('/qrcode/view/<int:procurement_id>')
@login_required
def view_qrcode(procurement_id):
    item = ProcurementDetail.query.get(procurement_id)
    next_url = request.args.get('url_next', url_for('procurement.view_procurement'))
    return render_template('procurement/view_qrcode.html',
                           model=ProcurementRecord,
                           item=item, url_next=next_url)


@procurement.route('/items/<int:item_id>/records/add', methods=['GET', 'POST'])
@login_required
def add_record(item_id):
    item = ProcurementDetail.query.get(item_id)
    form = ProcurementUpdateRecordForm(obj=item.current_record)
    if request.method == 'POST':
        if form.validate_on_submit():
            new_record = ProcurementRecord()
            form.populate_obj(new_record)
            new_record.item_id = item_id
            new_record.updater = current_user
            new_record.updated_at = datetime.now(tz=bangkok)
            db.session.add(new_record)
            db.session.commit()
            flash(u'บันทึกสำเร็จ', 'success')
        else:
            for er in form.errors:
                flash(er, 'danger')
        return redirect(url_for('procurement.view_qrcode', procurement_id=item_id))
    return render_template('procurement/record_form.html', form=form, url_callback=request.referrer)


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
            flash('New category has been added.', 'success')
            return redirect(url_for('procurement.add_procurement'))
    return render_template('procurement/category_ref.html', form=form, category=category, url_callback=request.referrer)


@procurement.route('/status/add', methods=['GET', 'POST'])
def add_status_ref():
    status = db.session.query(ProcurementStatus)
    form = ProcurementStatusForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_status = ProcurementStatus()
            form.populate_obj(new_status)
            db.session.add(new_status)
            db.session.commit()
            flash('New status has been added.', 'success')
            return redirect(url_for('procurement.add_procurement'))
    return render_template('procurement/status_ref.html', form=form, status=status, url_callback=request.referrer)


@procurement.route('/service/maintenance/require')
def require_maintenance():
    return render_template('procurement/require_maintenance.html')


@procurement.route('/service/list', methods=['POST', 'GET'])
def list_maintenance():
    if request.method == 'GET':
        maintenance_query = ProcurementDetail.query.all()
    else:
        procurement_number = request.form.get('procurement_number', None)
        users = request.form.get('users', 0)
        if procurement_number:
            maintenance_query = ProcurementDetail.query.filter(
                ProcurementDetail.procurement_no.like('%{}%'.format(procurement_number)))
        else:
            maintenance_query = []
        if request.headers.get('HX-Request') == 'true':
            return render_template('procurement/partials/maintenance_list.html', maintenance_query=maintenance_query)

    return render_template('procurement/maintenance_list.html', maintenance_query=maintenance_query)


@procurement.route('/service/contact', methods=['GET', 'POST'])
def contact_service():
    return render_template('procurement/maintenance_contact.html')


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
        # record["explan"] = maintenance.explan
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


@procurement.route('/qrcode/list', methods=['GET', 'POST'])
def list_qrcode():
    session['selected_procurement_items_printing'] = []

    def all_page_setup(canvas, doc):
        canvas.saveState()
        # logo_image = ImageReader('app/static/img/mumt-logo.png')
        # canvas.drawImage(logo_image, 10, 700, width=250, height=100)
        canvas.restoreState()

    if request.method == "POST":
        doc = SimpleDocTemplate("app/qrcode.pdf",
                                rightMargin=7,
                                leftMargin=5,
                                topMargin=35,
                                bottomMargin=0,
                                pagesize=(170, 150)
                                )
        data = []
        for item_id in request.form.getlist('selected_items'):
            item = ProcurementDetail.query.get(int(item_id))
            if not item.qrcode:
                item.generate_qrcode()

            decoded_img = b64decode(item.qrcode)
            img_string = cStringIO.StringIO(decoded_img)
            img_string.seek(0)
            data.append(Image(img_string, 50 * mm, 30 * mm, kind='bound'))
            data.append(Paragraph('<para align=center leading=10><font size=13>{}</font></para>'
                                  .format(item.erp_code.encode('utf-8')),
                                  style=style_sheet['ThaiStyle']))
            data.append(PageBreak())
        doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
        if 'selected_procurement_items_printing' in session:
            del session['selected_procurement_items_printing']
        return send_file('qrcode.pdf')

    return render_template('procurement/list_qrcode.html')


@procurement.route('/api/data/selected-items', methods=['POST'])
def select_items_for_printing_qrcode():
    if request.method == 'POST':
        items = ''
        print_items = session.get('selected_procurement_items_printing', [])
        for _id in request.form.getlist('selected_items'):
            if _id not in print_items:
                print_items.append(_id)
                item = ProcurementDetail.query.get(int(_id))
                items += (u'<tr><td><input class="is-checkradio" id="pro_no{}_selected" type="checkbox"'
                          u'name="selected_items" checked value="{}"><label for="pro_no{}_selected"></label></td>'
                          u'<td>{}</td><td>{}</td><td>{}</td></tr>').format(_id, _id, _id, item.name,
                                                                            item.procurement_no, item.erp_code)
        return items


@procurement.route('/api/data/qrcode/list')
def get_procurement_data_qrcode_list():
    query = ProcurementDetail.query
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ProcurementDetail.procurement_no.like(u'%{}%'.format(search)),
        ProcurementDetail.name.like(u'%{}%'.format(search)),
        ProcurementDetail.erp_code.like(u'%{}%'.format(search)),
        ProcurementDetail.budget_year.like(u'%{}%'.format(search)),
        ProcurementDetail.available.like(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        item_data['received_date'] = item_data['received_date'].strftime('%d/%m/%Y') if item_data[
            'received_date'] else ''
        item_data['print'] = '<a href="{}"><i class="fas fa-print"></i></a>'.format(
            url_for('procurement.export_qrcode_pdf', procurement_id=item.id))
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementDetail.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@procurement.route('/qrcode/pdf/list/<int:procurement_id>')
def export_qrcode_pdf(procurement_id):
    procurement = ProcurementDetail.query.get(procurement_id)

    def all_page_setup(canvas, doc):
        canvas.saveState()
        # logo_image = ImageReader('app/static/img/mumt-logo.png')
        # canvas.drawImage(logo_image, 10, 700, width=250, height=100)
        canvas.restoreState()

    doc = SimpleDocTemplate("app/qrcode.pdf",
                            rightMargin=7,
                            leftMargin=5,
                            topMargin=35,
                            bottomMargin=0,
                            pagesize=(170, 150)
                            )
    data = []
    if not procurement.qrcode:
        procurement.generate_qrcode()

    decoded_img = b64decode(procurement.qrcode)
    img_string = cStringIO.StringIO(decoded_img)
    img_string.seek(0)
    im = Image(img_string, 50 * mm, 30 * mm, kind='bound')
    data.append(im)
    data.append(Paragraph('<para align=center leading=10><font size=13>{}</font></para>'
                          .format(procurement.erp_code.encode('utf-8')),
                          style=style_sheet['ThaiStyle']))
    doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    return send_file('qrcode.pdf')


@procurement.route('/scan-qrcode', methods=['GET'])
@csrf.exempt
@login_required
def qrcode_scan():
    return render_template('procurement/qr_scanner.html')


@procurement.route('/scan-qrcode/info/view')
@procurement.route('/scan-qrcode/info/view/procurement_no/<string:procurement_no>')
def view_procurement_on_scan(procurement_no=None):
    procurement_id = request.args.get('procurement_id')
    if procurement_id:
        item = ProcurementDetail.query.get(procurement_id)
    if procurement_no:
        item_count = ProcurementDetail.query.filter_by(procurement_no=procurement_no).count()
        if item_count > 1:
            return redirect(url_for('procurement.view_sub_items', procurement_no=procurement_no,
                                    next_view="procurement.view_procurement_on_scan"))
        else:
            item = ProcurementDetail.query.filter_by(procurement_no=procurement_no).first()

    return render_template('procurement/view_data_on_scan.html', item=item,
                           procurement_no=item.procurement_no, url_callback=request.referrer)


@procurement.route('/items/<int:procurement_id>/check', methods=['GET', 'POST'])
@login_required
def check_procurement(procurement_id):
    procurement = ProcurementDetail.query.get(procurement_id)
    approval = procurement.current_record.approval
    if approval:
        form = ProcurementApprovalForm(obj=approval)
    else:
        form = ProcurementApprovalForm()
        approval = ProcurementCommitteeApproval()
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(approval)
            approval.approver = current_user
            approval.updated_at = datetime.now(tz=bangkok)
            approval.record = procurement.current_record
            db.session.add(approval)
            db.session.commit()
            flash(u'ตรวจสอบเรียบร้อย.', 'success')
        return redirect(url_for('procurement.view_procurement_on_scan', procurement_no=procurement.procurement_no))
    return render_template('procurement/approval_by_committee.html', form=form, procurement_no=procurement.procurement_no)


@procurement.route('/item/image/view')
def view_img_procurement():
    return render_template('procurement/view_img_procurement.html')


@procurement.route('/api/data/image/view')
def get_procurement_image_data():
    query = ProcurementDetail.query
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ProcurementDetail.procurement_no.like(u'%{}%'.format(search)),
        ProcurementDetail.name.like(u'%{}%'.format(search)),
        ProcurementDetail.erp_code.like(u'%{}%'.format(search)),
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        item_data['view_img'] = ('<img style="display:block; width:128px;height:128px;" id="base64image"'
                                 'src="data:image/png;base64, {}">').format(item_data['image'])
        item_data['img'] = '<a href="{}"><i class="fas fa-image"></a>'.format(
            url_for('procurement.add_img_procurement', procurement_id=item.id))
        item_data['edit'] = '<a href="{}"><i class="fas fa-edit"></i></a>'.format(
            url_for('procurement.edit_procurement', procurement_id=item.id))
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementDetail.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@procurement.route('/item/<int:procurement_id>/img/add', methods=['GET', 'POST'])
@login_required
def add_img_procurement(procurement_id):
    procurement = ProcurementDetail.query.get(procurement_id)
    form = ProcurementAddImageForm(obj=procurement)
    if form.validate_on_submit():
        form.populate_obj(procurement)
        file = form.image_upload.data
        if file:
            img_name = secure_filename(file.filename)
            file.save(img_name)  # convert image to base64(text) in database
            import base64
            with open(img_name, "rb") as img_file:
                procurement.image = base64.b64encode(img_file.read())
        db.session.add(procurement)
        db.session.commit()
        flash(u'บันทึกรูปภาพสำเร็จ.', 'success')
        return redirect(url_for('procurement.view_img_procurement'))
        # Check Error
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('procurement/add_img_procurement.html', form=form, procurement_id=procurement_id,
                           procurement=procurement, url_callback=request.referrer)


@procurement.route('/scan-qrcode/location/status/update', methods=['GET'])
@csrf.exempt
@login_required
def update_location_and_status():
    return render_template('procurement/update_location_and_status.html')


@procurement.route('/scan-qrcode/info/location-status')
@procurement.route('/scan-qrcode/info/location-status/view/<string:procurement_no>')
def view_location_and_status_on_scan(procurement_no=None):
    procurement_id = request.args.get('procurement_id')
    if procurement_id:
        item = ProcurementDetail.query.get(procurement_id)
    if procurement_no:
        item_count = ProcurementDetail.query.filter_by(procurement_no=procurement_no).count()
        if item_count > 1:
            return redirect(url_for('procurement.view_sub_items', procurement_no=procurement_no,
                                    next_view="procurement.view_location_and_status_on_scan"))
        else:
            item = ProcurementDetail.query.filter_by(procurement_no=procurement_no).first()

    return render_template('procurement/view_location_and_status_on_scan.html', item=item,
                           procurement_no=item.procurement_no, url_callback=request.referrer)


@procurement.route('/<string:procurement_no>/sub-items')
@login_required
def view_sub_items(procurement_no):
    sub_items = ProcurementDetail.query.filter_by(procurement_no=procurement_no).all()
    next_view = request.args.get('next_view')
    return render_template('procurement/view_sub_items.html', next_view=next_view, sub_items=sub_items,
                           request_args=request.args, procurement_no=procurement_no)


@procurement.route('/room/add', methods=['GET', 'POST'])
@login_required
def add_room_ref():
    form = ProcurementRoomForm()
    if request.method == 'POST':
       new_room = RoomResource()
       form.populate_obj(new_room)
       db.session.add(new_room)
       db.session.commit()
       flash('New room has been added.', 'success')
       return redirect(url_for('procurement.view_room'))
    return render_template('procurement/room_ref.html', form=form, url_callback=request.referrer)


@procurement.route('/room/all')
@login_required
def view_room():
    room_list = []
    room = RoomResource.query.all()
    for r in room:
        record = {}
        record["id"] = r.id
        record["location"] = r.location
        record["number"] = r.number
        record["floor"] = r.floor
        record["desc"] = r.desc
        room_list.append(record)
    return render_template('procurement/view_room.html', room_list=room_list)


@procurement.route('/room/<int:room_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_room(room_id):
    room = RoomResource.query.get(room_id)
    form = ProcurementRoomForm(obj=room)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(room)
            db.session.add(room)
            db.session.commit()
            flash(u'แก้ไขข้อมูลเรียบร้อย', 'success')
        return redirect(url_for('procurement.view_room', room_id=room_id))
    return render_template('procurement/edit_room.html',
                           room_id=room_id, form=form)


@procurement.route('/official/for-information-technology-and-maintenance/login')
def information_technology_first_page():
    return render_template('procurement/information_technology_first_page.html', name=current_user)


@procurement.route('/official/for-information-technology-and-maintenance/landing')
def landing_survey_info():
    return render_template('procurement/landing_survey_info.html')


@procurement.route('computer/<int:procurement_id>/checking/edit', methods=['GET', 'POST'])
def new_checking_computer_info(procurement_id):
    procurement = ProcurementDetail.query.get(procurement_id)
    if procurement.computer_info:
        computer_info = procurement.computer_info
        form = ProcurementComputerInfoForm(obj=computer_info)
    else:
        form = ProcurementComputerInfoForm()
        computer_info = None
    if form.validate_on_submit():
        if not computer_info:
            computer_info = ProcurementInfoComputer()
        form.populate_obj(computer_info)
        computer_info.detail_id = procurement_id
        db.session.add(computer_info)
        db.session.commit()
        flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('procurement/new_checking_computer_info.html',
                           form=form, procurement_id=procurement_id,
                           procurement_no=procurement.procurement_no,
                           computer_info=computer_info,
                           procurement=procurement)


@procurement.route('computer/check', methods=['GET', 'POST'])
def view_all_check_computer():
    return render_template('procurement/view_all_check_computer.html')


@procurement.route('api/computer/check')
def get_check_computer():
    query = ProcurementInfoComputer.query
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ProcurementInfoComputer.computer_name.ilike(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        item_data['survey_record'] = '<a href="{}" class="button is-small is-rounded is-info is-outlined">Survey</a>'.format(
            url_for('procurement.add_survey_computer_info', procurement_no=item.detail.procurement_no))
        item_data[
            'view_survey'] = '<a href="{}" class="button is-small is-rounded is-primary is-outlined">View</a>'.format(
            url_for('procurement.view_survey_computer_info', procurement_id=item.id))
        item_data['erp_code'] = u'{}'.format(item.detail.erp_code)
        item_data['procurement_no'] = u'{}'.format(item.detail.procurement_no)
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementInfoComputer.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@procurement.route('/scan-qrcode/survey/new', methods=['GET'])
@csrf.exempt
def qrcode_scan_to_survey():
    return render_template('procurement/qr_code_scan_to_survey.html')


@procurement.route('/computer/survey/add/<string:procurement_no>', methods=['GET', 'POST'])
def add_survey_computer_info(procurement_no):
    procurement = ProcurementDetail.query.filter_by(procurement_no=procurement_no).first()
    form = ProcurementSurveyComputerForm()
    if form.validate_on_submit():
        survey_com = ProcurementSurveyComputer()
        form.populate_obj(survey_com)
        survey_com.surveyor = current_user
        survey_com.survey_date = bangkok.localize(datetime.now())
        survey_com.computer_info = procurement.computer_info
        db.session.add(survey_com)
        db.session.commit()
        flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return redirect(url_for('procurement.new_checking_computer_info', procurement_id=procurement.id))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('procurement/add_survey_computer_info.html',
                           form=form, procurement=procurement, url_callback=request.referrer)


@procurement.route('/info-tests/view/<int:survey_id>')
def view_survey_computer_info(survey_id):
    survey = ProcurementSurveyComputer.query.get(survey_id)
    return render_template('procurement/view_survey_computer_info.html', survey=survey)


@procurement.route('/computer/erp_code/search')
@login_required
def computer_search_by_erp_code():
    return render_template('procurement/computer_search_by_erp_code.html')


@procurement.route('/list', methods=['POST', 'GET'])
@login_required
def computer_list():
    if request.method == 'GET':
        computers_detail = ProcurementDetail.query.filter(ProcurementDetail.erp_code.contains("41000"))
    else:
        erp_code = request.form.get('erp_code', None)
        if erp_code:
            computers_detail = ProcurementDetail.query.filter(ProcurementDetail.erp_code.like('%{}%'.format(erp_code)))
        else:
            computers_detail = []
        if request.headers.get('HX-Request') == 'true':
            return render_template('procurement/partials/computer_list.html', computers_detail=computers_detail)

    return render_template('procurement/computer_list.html', computers_detail=computers_detail)


@procurement.route('/borrow-return/index')
def index_borrow_detail():
    return render_template('procurement/borrow_detail_index.html', list_type='default')


@procurement.route('/borrow-return/available/<list_type>')
def procurement_available_list(list_type='timelineDay'):
    return render_template('procurement/procurement_available_list.html', list_type=list_type)


# @procurement.route('/api/procurements')
# def get_procurements():
#     start = request.args.get('start')
#     end = request.args.get('end')
#     if start:
#         start = dateutil.parser.isoparse(start)
#     if end:
#         end = dateutil.parser.isoparse(end)
#     procurements = ProcurementDetail.query.filter(ProcurementDetail.start >= start) \
#         .filter(ProcurementDetail.end <= end)
#     all_procurements = []
#     for procurement in procurements:
#         if procurement.is_closed:
#             text_color = '#ffffff'
#             bg_color = '#066b02'
#             border_color = '#ffffff'
#         elif procurement.cancelled_at:
#             text_color = '#ffffff'
#             bg_color = '#ff6666'
#             border_color = '#ffffff'
#         elif procurement.approved:
#             text_color = '#000000'
#             bg_color = '#62c45e'
#             border_color = '#ffffff'
#         else:
#             text_color = '#000000'
#             bg_color = '#f0f0f5'
#             border_color = '#ffffff'
#         evt = procurement.to_dict()
#         evt['resourceId'] = procurement.vehicle.license
#         evt['borderColor'] = border_color
#         evt['backgroundColor'] = bg_color
#         evt['textColor'] = text_color
#         all_procurements.append(evt)
#     return jsonify(all_procurements)

@procurement.route('/reservation/new')
def new_reservation():
    return render_template('procurement/new_reservation.html')


@procurement.route('/list/search', methods=['POST', 'GET'])
def procurement_list():
    erp_code = request.form.get('erp_code', None)
    if erp_code:
        procurements = ProcurementDetail.query.filter_by(erp_code=erp_code)
    else:
        procurements = []

    return render_template('procurement/procurement_list.html', procurements=procurements)


@procurement.route('procurement_list/all', methods=['GET', 'POST'])
def view_all_procurement_to_borrow():
    return render_template('procurement/view_all_procurement_to_borrow.html')


@procurement.route('api/procurement_list/all')
def get_procurement_list():
    query = ProcurementDetail.query.filter_by(is_reserved=True)
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ProcurementDetail.erp_code.ilike(u'%{}%'.format(search)),
        ProcurementDetail.procurement_no.ilike(u'%{}%'.format(search)),
        ProcurementDetail.name.ilike(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        item_data['reserve'] = '<a href="{}" class="button is-small is-rounded is-info is-outlined">จอง</a>'.format(
            url_for('procurement.add_borrow_detail', procurement_no=item.procurement_no))
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementDetail.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@procurement.route('/borrow-return/detail/add/<string:procurement_no>', methods=['GET', 'POST'])
def add_borrow_detail(procurement_no):
    procurement = ProcurementDetail.query.filter_by(procurement_no=procurement_no).first()
    form = ProcurementBorrowDetailForm()
    if form.validate_on_submit():
        borrow_detail = ProcurementBorrowDetail()
        form.populate_obj(borrow_detail)
        borrow_detail.borrower = current_user
        db.session.add(borrow_detail)
        db.session.commit()
        flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return redirect(url_for('procurement.view_borrow_detail'))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('procurement/add_borrow_detail.html',
                           form=form, url_callback=request.referrer,
                           procurement_no=procurement_no,
                           procurement=procurement)


@procurement.route('procurement_list/reserve/all', methods=['GET', 'POST'])
def view_all_procurement_to_reserve():
    return render_template('procurement/view_all_procurement_to_reserve.html')


@procurement.route('api/procurement_list/reserve/all')
def get_procurement_to_reserve():
    query = ProcurementDetail.query
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ProcurementDetail.erp_code.ilike(u'%{}%'.format(search)),
        ProcurementDetail.procurement_no.ilike(u'%{}%'.format(search)),
        ProcurementDetail.name.ilike(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        item_data['add'] = '<a href="{}" class="button is-small is-rounded is-info is-outlined">Add</a>'.format(
            url_for('procurement.add_borrow_detail', procurement_no=item.procurement_no))
        item_data['add_item'] = (
            '<input class="is-checkradio" id="pro_no{}" type="checkbox" name="add_items" value="{}">'
            '<label for="pro_no{}"></label>').format(item.id, item.id, item.id)
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementDetail.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@procurement.route('/list/add-items', methods=['POST', 'GET'])
def list_add_items():
    form = ProcurementBorrowDetailForm()
    form.items.append_entry()
    item_form = form.items[-1]
    form_text = u'''
    <div class="field">
        <label class="label">{}</label>
        <div class="control">
            {}
        </div>
    </div>
    <div class="field-body">
    <div class="field">
        <label class="label">{}</label>
        <div class="control">
            {}
        </div>
    </div>
    <div class="field">
        <label class="label">{}</label>
        <div class="control">
            {}
        </div>
    </div>
    </div>
    <div class="field">
        <label class="label">{}</label>
        <div class="control">
            {}
        </div>
    </div>
    '''.format(item_form.item.label, item_form.item(class_="input"),
               item_form.quantity.label, item_form.quantity(class_="input"),
               item_form.unit.label, item_form.unit(class_="input"),
               item_form.note.label, item_form.note(class_="textarea")
               )
    resp = make_response(form_text)
    return resp


@procurement.route('/list/delete-items', methods=['POST', 'GET'])
def delete_items():
    form = ProcurementBorrowDetailForm()
    if len(form.items.entries) > 1:
        form.items.pop_entry()
        alert = False
    else:
        alert = True
    form_text = ''
    for item_form in form.items.entries:
        form_text += u'''
            <div class="field">
                <label class="label">{}</label>
                <div class="control">
                    {}
                </div>
            </div>
             <div class="field-body">
            <div class="field">
                <label class="label">{}</label>
                <div class="control">
                    {}
                </div>
            </div>
            <div class="field">
                <label class="label">{}</label>
                <div class="control">
                    {}
                </div>
            </div>
            </div>
            <div class="field">
                <label class="label">{}</label>
                <div class="control">
                    {}
                </div>
            </div>
            '''.format(item_form.item.label, item_form.item(class_="input"),
                       item_form.quantity.label, item_form.quantity(class_="input"),
                       item_form.unit.label, item_form.unit(class_="input"),
                       item_form.note.label, item_form.note(class_="textarea")
                       )
    resp = make_response(form_text)
    if alert:
        resp.headers['HX-Trigger-After-Swap'] = 'delete_warning'
    return resp


@procurement.route('/scan-qrcode/borrow', methods=['GET'])
@csrf.exempt
def qrcode_scan_to_borrow():
    return render_template('procurement/qr_code_scan_to_borrow.html')


@procurement.route('detail/borrow', methods=['GET', 'POST'])
def view_borrow_detail():
    return render_template('procurement/view_borrow_detail.html')


@procurement.route('api/detail/borrow')
def get_borrow_detail():
    query = ProcurementBorrowItem.query
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ProcurementBorrowItem.item.ilike(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        # item_data['view_record'] = '<a href="{}" class="button is-small is-rounded is-info is-outlined">View</a>'.format(
        #     url_for('procurement.add_survey_computer_info', procurement_no=item.detail.procurement_no))
        # item_data['print_record'] = '<a href="{}" class="button is-small is-rounded is-primary is-outlined">Print</a>'.format(
        #     url_for('procurement.view_survey_computer_info', procurement_id=item.id))
        # item_data['erp_code'] = u'{}'.format(item.procurement_detail.erp_code)
        item_data['purpose'] = u'{}'.format(item.borrow_detail.purpose)
        item_data['location_of_use'] = u'{}'.format(item.borrow_detail.location_of_use)
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementBorrowItem.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })

# sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
# pdfmetrics.registerFont(sarabun_font)
# style_sheet = getSampleStyleSheet()
# style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))
# style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', alignment=TA_RIGHT))
# style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', alignment=TA_CENTER))
#
#
# @procurement.route('/borrow-form/pdf/<int:borrow_id>')
# def export_borrow_form_pdf(borrow_id):
#     borrow_detail = ProcurementBorrowDetail.query.get(borrow_id)
#
#     def all_page_setup(canvas, doc):
#         canvas.saveState()
#         logo_image = ImageReader('app/static/img/logo-MU_black-white-2-1.png')
#         canvas.drawImage(logo_image, 200, 200, mask='auto')
#         canvas.restoreState()
#
#     doc = SimpleDocTemplate("app/borrow_form.pdf",
#                             rightMargin=20,
#                             leftMargin=20,
#                             topMargin=20,
#                             bottomMargin=10,
#                             )
#     no = borrow_detail.number
#     booking_date = borrow_detail.book_date
#     data = []
#
#     borrow_info = '''<font size=15>
#     {original}</font><br/><br/>
#     <font size=11>
#     เลขที่ {no}<br/>
#     วันที่ {booking_date}
#     </font>
#     '''
#     borrow_info_ori = borrow_info.format(original=u'ต้นฉบับ<br/>(Original)'.encode('utf-8'),
#                                            no=no,
#                                            booking_date=booking_date
#                                            )
#
#     header_content_ori = [[Paragraph(borrow_info_ori, style=style_sheet['ThaiStyle'])]]
#
#     header_styles = TableStyle([
#         ('VALIGN', (0, 0), (-1, -1), 'TOP'),
#         ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
#     ])
#
#     header_ori = Table(header_content_ori, colWidths=[150, 200, 50, 100])
#
#     header_ori.hAlign = 'CENTER'
#     header_ori.setStyle(header_styles)
#
#     form_borrow_detail = '''<para><font size=12>
#     ข้าพเจ้า {borrower}<br/>
#     ตำแหน่ง {position}
#     สังกัด คณะ/สถาบัน/ภาควิชา/หน่วยงาน {org}
#     โทร {telephone}
#     มือถือ {mobile_phone}
#     มีความประสงค์ขอยืมพัสดุของ คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>
#     {}<br/>
#     เพื่อใช้ในงาน {}<br/>
#     ระบุเหตุผลความจำเป็น {}<br/>
#     สถานที่นำไปใช้งาน {} เลขที่ {} หมู่ที่ {} ถนน {} ตำบล/แขวง {} อำเภอ/เขต {} จังหวัด {} รหัสไปรษณีย์ {}
#     โดยมีกำหนดการยืมคืนในระหว่างวันที่ {} ถึง {}
#     &nbsp;และข้าพเจ้าขอนำส่งพัสดุในสภาพที่ใช้การได้ตามปกติ ภายใน 7 วันนับแต่วันที่ครบกำหนดการยืมโดยเป็นไปตามประกาศ มหาวิทยาลัยมหิดล
#     เรื่องหลักเกณฑ์และวิธีการยืมพัสดุของมหาวิทยาลัยมหิดล พ.ศ. 2563 ดังมีรายการยืมดังต่อไปนี้
#     </font></para>
#     '''.format(borrower=borrow_detail.borrower.encode('utf-8'),
#                position=borrow_detail.borrower.personal_info.position.encode('utf-8'),
#                org=borrow_detail.borrower.personal_info.org.encode('utf-8'),
#                telephone=borrow_detail.borrower.personal_info.telephone.encode('utf-8'),
#                mobile_phone=borrow_detail.borrower.personal_info.mobile_phone.encode('utf-8'),
#                type_of_purpose=borrow_detail.type_of_purpose.encode('utf-8'),
#                purpose=borrow_detail.purpose.encode('utf-8'),
#                reason=borrow_detail.reason.encode('utf-8'),
#                location_of_use=borrow_detail.location_of_use.encode('utf-8'),
#                address_number=borrow_detail.address_number.encode('utf-8'),
#                moo=borrow_detail.moo.encode('utf-8'),
#                road=borrow_detail.road.encode('utf-8'),
#                sub_district=borrow_detail.sub_district.encode('utf-8'),
#                district=borrow_detail.district.encode('utf-8'),
#                province=borrow_detail.province.encode('utf-8'),
#                postal_code=borrow_detail.postal_code.encode('utf-8'),
#                start_date=borrow_detail.start_date.encode('utf-8'),
#                end_date=borrow_detail.end_date.encode('utf-8')
#                )
#
#     form_detail = Table([[Paragraph(form_borrow_detail, style=style_sheet['ThaiStyle']),
#                     ]],
#                      colWidths=[580, 200]
#                      )
#     form_detail.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'),
#                                   ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
#     items = [[Paragraph('<font size=10>ลำดับ</font>', style=style_sheet['ThaiStyleCenter']),
#               Paragraph('<font size=10>รายการ</font>', style=style_sheet['ThaiStyleCenter']),
#               Paragraph('<font size=10>รหัสพัสดุ</font>', style=style_sheet['ThaiStyleCenter']),
#               Paragraph('<font size=10>จำนวน</font>', style=style_sheet['ThaiStyleCenter']),
#               Paragraph('<font size=10>หน่วยนับ</font>', style=style_sheet['ThaiStyleCenter']),
#               Paragraph('<font size=10>หมายเหตุ</font>', style=style_sheet['ThaiStyleCenter']),
#               ]]
#
#     for n, item in enumerate(borrow_detail.items, start=1):
#         item_record = [Paragraph('<font size=12>{}</font>'.format(n), style=style_sheet['ThaiStyleCenter']),
#                 Paragraph('<font size=12>{}</font>'.format(item.item.encode('utf-8')), style=style_sheet['ThaiStyle']),
#                 Paragraph('<font size=12>{}</font>'.format(item.erp_code.encode('utf-8')), style=style_sheet['ThaiStyle']),
#                 Paragraph('<font size=12>{}</font>'.format(item.quantity.encode('utf-8')), style=style_sheet['ThaiStyle']),
#                 Paragraph('<font size=12>{}</font>'.format(item.unit.encode('utf-8')), style=style_sheet['ThaiStyle']),
#                 Paragraph('<font size=12>{}</font>'.format(item.note.encode('utf-8')), style=style_sheet['ThaiStyle']),
#                 ]
#         items.append(item_record)
#
#     n = len(items)
#     for i in range(5-n):
#         items.append([
#             Paragraph('<font size=12>&nbsp; </font>', style=style_sheet['ThaiStyleNumber']),
#             Paragraph('<font size=12> </font>', style=style_sheet['ThaiStyleNumber']),
#             Paragraph('<font size=12> </font>', style=style_sheet['ThaiStyleNumber']),
#         ])
#     item_table = Table(items, colWidths=[50, 450, 75])
#     item_table.setStyle(TableStyle([
#         ('BOX', (0, 0), (-1, 0), 0.25, colors.black),
#         ('BOX', (0, -1), (-1, -1), 0.25, colors.black),
#         ('BOX', (0, 0), (0, -1), 0.25, colors.black),
#         ('BOX', (1, 0), (1, -1), 0.25, colors.black),
#         ('BOX', (2, 0), (2, -1), 0.25, colors.black),
#         ('BOX', (3, 0), (3, -1), 0.25, colors.black),
#         ('BOX', (4, 0), (4, -1), 0.25, colors.black),
#         ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
#         ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
#         ('BOTTOMPADDING', (0, -2), (-1, -2), 10),
#     ]))
#     item_table.setStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')])
#     item_table.setStyle([('SPAN', (0, -1), (1, -1))])
   # # ผู้ยืม
   #  sign_text = Paragraph(
   #      '<br/><font size=12>............................................................................ ผู้ยืม<br/></font>',
   #      style=style_sheet['ThaiStyle'])
   #  borrower = [[sign_text,
   #              Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
   #              Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
   #  borrower_officer = Table(borrower, colWidths=[0, 80, 20])
   #  fullname = Paragraph(
   #      '<font size=12>({})<br/></font>'.format(borrow_detail.borrower.personal_info.fullname.encode('utf-8')),
   #      style=style_sheet['ThaiStyle'])
   #  personal_info = [[fullname,
   #                    Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
   #  borrower_personal_info = Table(personal_info, colWidths=[0, 30, 20])
   #  # หัวหน้าหน่วยงานผู้ยืม
   #  sign_text = Paragraph(
   #      '<br/><font size=12>............................................................................ หัวหน้าหน่วยงานผู้ยืม<br/></font>',
   #      style=style_sheet['ThaiStyle'])
   #  receive = [[sign_text,
   #              Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
   #              Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
   #  receive_officer = Table(receive, colWidths=[0, 80, 20])
   #  fullname = Paragraph(
   #      '<font size=12>({})<br/></font>'.format(borrow_detail.borrower.personal_info.fullname.encode('utf-8')),
   #      style=style_sheet['ThaiStyle'])
   #  personal_info = [[fullname,
   #                    Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
   #  hrad_borrower_personal_info = Table(personal_info, colWidths=[0, 30, 20])
   #
   #  position = Paragraph('<font size=12>..............{}..................... ตำแหน่ง / POSITION </font>'.format(
   #      borrow_detail.borrower.personal_info.position.encode('utf-8')),
   #                       style=style_sheet['ThaiStyle'])
   #  position_info = [[position,
   #                    Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
   #  hrad_borrower_position = Table(position_info, colWidths=[0, 80, 20])
   #
   #  notice_text = '''<para align=left><font size=10>
   #  ส่วนที่ 2 สำหรับผู้อนุมัติ : หัวหน้าส่วนงาน </font></para>
   #  '''
   #  notice = Table([[Paragraph(notice_text, style=style_sheet['ThaiStyle'])]])
   #  #หัวหน้าส่วนงาน
   #  sign_text = Paragraph('<br/><font size=12>............................................................................ หัวหน้าหน่วยพัสดุ<br/></font>',
   #                        style=style_sheet['ThaiStyle'])
   #  receive = [[sign_text,
   #                    Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
   #                    Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
   #  receive_officer = Table(receive, colWidths=[0, 80, 20])
   #
   #  fullname = Paragraph('<font size=12>({})<br/></font>'.format(borrow_detail.borrower.personal_info.fullname.encode('utf-8')),
   #                       style=style_sheet['ThaiStyle'])
   #  personal_info = [[fullname,
   #              Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
   #  head_personal_info = Table(personal_info, colWidths=[0, 30, 20])
   #
   #  position = Paragraph('<font size=12>..............{}..................... ตำแหน่ง / POSITION </font>'.format(borrow_detail.borrower.personal_info.position.encode('utf-8')),
   #                       style=style_sheet['ThaiStyle'])
   #  position_info = [[position,
   #                    Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
   #  head_position = Table(position_info, colWidths=[0, 80, 20])
   #  # หัวหน้าหน่วยพัสดุ
   #  sign_text = Paragraph(
   #      '<br/><font size=12>............................................................................ หัวหน้าหน่วยพัสดุ<br/></font>',
   #      style=style_sheet['ThaiStyle'])
   #  receive = [[sign_text,
   #              Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle']),
   #              Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
   #  receive_officer = Table(receive, colWidths=[0, 80, 20])
   #
   #  fullname = Paragraph(
   #      '<font size=12>({})<br/></font>'.format(borrow_detail.borrower.personal_info.fullname.encode('utf-8')),
   #      style=style_sheet['ThaiStyle'])
   #  personal_info = [[fullname,
   #                    Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
   #  head_procurement_personal_info = Table(personal_info, colWidths=[0, 30, 20])
   #
   #  position = Paragraph('<font size=12>..............{}..................... ตำแหน่ง / POSITION </font>'.format(
   #      borrow_detail.borrower.personal_info.position.encode('utf-8')),
   #                       style=style_sheet['ThaiStyle'])
   #  position_info = [[position,
   #                    Paragraph('<font size=12></font>', style=style_sheet['ThaiStyle'])]]
   #  head_procurementposition = Table(position_info, colWidths=[0, 80, 20])

    # data.append(form_detail)
    # data.append(Spacer(1, 12))
    # data.append(Spacer(1, 6))
    # data.append(item_table)
    # data.append(Spacer(1, 6))
    # data.append(Spacer(1, 12))
    # data.append(PageBreak())
    # doc.build(data, onLaterPages=all_page_setup, onFirstPage=all_page_setup)
    #
    # return send_file('borrow_form.pdf')


@procurement.route('check-instruments/all', methods=['GET', 'POST'])
def view_all_procurement_to_check_instruments():
    return render_template('procurement/view_all_procurement_to_check_instruments.html')


@procurement.route('api/check-instruments/all')
def get_procurement_to_check_instruments():
    query = ProcurementDetail.query
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ProcurementDetail.erp_code.ilike(u'%{}%'.format(search)),
        ProcurementDetail.procurement_no.ilike(u'%{}%'.format(search)),
        ProcurementDetail.name.ilike(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        item_data['add'] = '<a href="{}" class="button is-small is-rounded is-info is-outlined">Add</a>'.format(
            url_for('procurement.add_borrow_detail', procurement_no=item.procurement_no))
        item_data['add_item'] = (
            '<input class="is-checkradio" id="pro_no{}" type="checkbox" name="add_items" value="{}">'
            '<label for="pro_no{}"></label>').format(item.id, item.id, item.id)
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementDetail.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })
