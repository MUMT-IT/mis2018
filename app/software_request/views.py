import os
import arrow
import  pytz
import requests
from app.main import mail
from flask_mail import Message
from sqlalchemy import or_
from flask import render_template, redirect, flash, url_for, jsonify, request, make_response, current_app
from flask_login import login_required, current_user
from app.roles import admin_permission
from app.software_request import software_request
from app.software_request.forms import create_request_form, SoftwareRequestTimelineForm, SoftwareRequestIssueForm
from app.software_request.models import *
from werkzeug.utils import secure_filename
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive

localtz = pytz.timezone('Asia/Bangkok')

gauth = GoogleAuth()
keyfile_dict = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
scopes = ['https://www.googleapis.com/auth/drive']
gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scopes)
drive = GoogleDrive(gauth)

FOLDER_ID = '1832el0EAqQ6NVz2wB7Ade6wRe-PsHQsu'

json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scopes)
    return GoogleDrive(gauth)


@software_request.route('/')
@login_required
def index():
    org = current_user.personal_info.org
    details = SoftwareRequestDetail.query.filter(or_(SoftwareRequestDetail.created_id == current_user.id,
                                                     SoftwareRequestDetail.created_by.has(
                                                         StaffAccount.personal_info.has(org=org))))
    return render_template('software_request/index.html', details=details, org=org)


@software_request.route('/condition')
def condition_for_service_request():
    return render_template('software_request/condition_page.html')


@software_request.route('/request/view/<int:detail_id>')
def view_request(detail_id):
    detail = SoftwareRequestDetail.query.get(detail_id)
    return render_template('software_request/view_request.html', detail=detail)


@software_request.route('/request/add', methods=['GET', 'POST'])
def create_request():
    SoftwareRequestDetailForm = create_request_form(detail_id=None)
    form = SoftwareRequestDetailForm()
    if form.validate_on_submit():
        detail = SoftwareRequestDetail()
        form.populate_obj(detail)
        file = form.file_upload.data
        drive = initialize_gdrive()
        if file:
            file_name = secure_filename(file.filename)
            file.save(file_name)
            file_drive = drive.CreateFile({'title': file_name,
                                           'parents': [{'id': FOLDER_ID, "kind": "drive#fileLink"}]})
            file_drive.SetContentFile(file_name)
            file_drive.Upload()
            file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
            detail.url = file_drive['id']
            detail.file_name = file_name
        if form.system.data:
            system = SoftwareRequestSystem.query.get(request.form.getlist('system'))
            detail.title = system.system
        detail.status = 'ส่งคำขอแล้ว'
        detail.created_date = arrow.now('Asia/Bangkok').datetime
        detail.created_id = current_user.id
        db.session.add(detail)
        db.session.commit()
        flash('ส่งคำขอสำเร็จ', 'success')
        return redirect(url_for('software_request.index'))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('software_request/create_request.html', form=form)


@software_request.route('/api/system', methods=['GET'])
@login_required
def get_systems():
    search_term = request.args.get('term', '')
    key = request.args.get('key', 'id')
    results = []
    systems = SoftwareRequestSystem.query.all()
    for system in systems:
        if search_term in system.system:
            index_ = getattr(system, key) if hasattr(system, key) else getattr(system.system, key)
            results.append({
                "id": index_,
                "text": system.system
            })
    return jsonify({'results': results})


@software_request.route('/admin/index')
@admin_permission.require()
@login_required
def admin_index():
    tab = request.args.get('tab')
    api = request.args.get('api', 'false')
    query = SoftwareRequestDetail.query
    timelines = SoftwareRequestTimeline.query.filter_by(admin_id=current_user.id)
    pending_query = query.filter_by(status='ส่งคำขอแล้ว')
    consider_query = query.filter_by(status='อยู่ระหว่างพิจารณา')
    approve_query = query.filter_by(status='อนุมัติ')
    complete_query = query.filter_by(status='เสร็จสิ้น')
    disapprove_query = query.filter_by(status='ไม่อนุมัติ')
    cancel_query = query.filter_by(status='ยกเลิก')
    if api == 'true':
        tab = request.args.get('tab')
        if tab == 'pending':
            query = pending_query
        elif tab == 'consider':
            query = consider_query
        elif tab == 'approve':
            query = approve_query
        elif tab == 'complete':
            query = complete_query
        elif tab == 'disapprove':
            query = disapprove_query
        elif tab == 'cancel':
            query = cancel_query

        records_total = query.count()
        search = request.args.get('search[value]')
        if search:
            query = query.filter(db.or_
                                 (SoftwareRequestDetail.type.ilike(u'%{}%'.format(search)),
                                  SoftwareRequestDetail.description.ilike(u'%{}%'.format(search)),
                                  SoftwareRequestDetail.created_by.ilike(u'%{}%'.format(search)),
                                  SoftwareRequestDetail.created_date.ilike(u'%{}%'.format(search)),
                                  SoftwareRequestDetail.status.ilike(u'%{}%'.format(search))
                                  ))
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
    return render_template('software_request/admin_index.html', tab=tab, pending_count=pending_query.count(),
                           consider_count=consider_query.count(), approve_count=approve_query.count(),
                           complete_count=complete_query.count(), disapprove_count=disapprove_query.count(),
                           cancel_count=cancel_query.count(), timelines=timelines)


# @software_request.route('/api/request/index')
# def get_requests():
#     tab = request.args.get('tab')
#     if tab == 'pending':
#         query = SoftwareRequestDetail.query.filter_by(status='ส่งคำขอแล้ว')
#     elif tab == 'consider':
#         query = SoftwareRequestDetail.query.filter_by(status='อยู่ระหว่างพิจารณา')
#     elif tab == 'approve':
#         query = SoftwareRequestDetail.query.filter_by(status='อนุมัติ')
#     elif tab == 'disapprove':
#         query = SoftwareRequestDetail.query.filter_by(status='ไม่อนุมัติ')
#     elif tab == 'cancel':
#         query = SoftwareRequestDetail.query.filter_by(status='ยกเลิก')
#     else:
#         query = SoftwareRequestDetail.query
#     records_total = query.count()
#     search = request.args.get('search[value]')
#     if search:
#         query = query.filter(db.or_
#                              (SoftwareRequestDetail.type.ilike(u'%{}%'.format(search)),
#                               SoftwareRequestDetail.description.ilike(u'%{}%'.format(search)),
#                               SoftwareRequestDetail.created_by.ilike(u'%{}%'.format(search)),
#                               SoftwareRequestDetail.created_date.ilike(u'%{}%'.format(search)),
#                               SoftwareRequestDetail.status.ilike(u'%{}%'.format(search))
#                               ))
#     start = request.args.get('start', type=int)
#     length = request.args.get('length', type=int)
#     total_filtered = query.count()
#     query = query.offset(start).limit(length)
#     data = []
#     for item in query:
#         item_data = item.to_dict()
#         data.append(item_data)
#     return jsonify({'data': data,
#                     'recordFiltered': total_filtered,
#                     'recordTotal': records_total,
#                     'draw': request.args.get('draw', type=int)
#                     })


@software_request.route('/admin/request/edit/<int:detail_id>', methods=['GET', 'POST'])
def update_request(detail_id):
    tab = request.args.get('tab')
    detail = SoftwareRequestDetail.query.get(detail_id)
    status = detail.status
    SoftwareRequestDetailForm = create_request_form(detail_id=detail_id)
    form = SoftwareRequestDetailForm(obj=detail)
    if detail.url:
        file_upload = drive.CreateFile({'id': detail.url})
        file_upload.FetchMetadata()
        file_url = file_upload.get('embedLink')
    else:
        file_url = None
    appointment_date = form.appointment_date.data.astimezone(localtz) if form.appointment_date.data else None
    if form.validate_on_submit():
        form.populate_obj(detail)
        detail.updated_date = arrow.now('Asia/Bangkok').datetime
        detail.approver_id = current_user.id
        detail.appointment_date = arrow.get(form.appointment_date.data, 'Asia/Bangkok').datetime if form.appointment_date.data else None
        detail.status = form.status.data if form.status.data else status
        db.session.add(detail)
        db.session.commit()
        if form.status.data:
            scheme = 'http' if current_app.debug else 'https'
            link = url_for("software_request.view_request", detail_id=detail_id, _external=True, _scheme=scheme)
            title = f'''แจ้งอัพเดตสถานะ{detail.title}'''
            message = f'''เรียน คุณ{detail.created_by.fullname}\n\n'''
            message += f'''{detail.approver.fullname} ได้ทำการอัปเดตสถานะคำร้องขอใช้ซอฟต์แวร์ของท่านเป็น "{detail.status}"\n'''
            message += f'''ท่านสามารถตรวจสอบรายละเอียดเพิ่มเติมได้ที่ลิงก์ด้านล่าง\n'''
            message += f'''{link}\n\n'''
            message += f'''หากมีข้อสงสัยหรือต้องการสอบถามข้อมูลเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ที่รับผิดชอบ\n\n'''
            message += f'''ขอบคุณค่ะ\n'''
            message += f'''ระบบขอรับบริการพัฒนา Software\n'''
            message += f'''คณะเทคนิคการแพทย์'''
            send_mail([detail.created_by.email + '@mahidol.ac.th'], title, message)
            flash('อัพเดตสถานะสำเร็จ', 'success')
        else:
            flash('อัพเดตข้อมูลสำเร็จ  ', 'success')
            return redirect(url_for('software_request.admin_index', tab=tab))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('software_request/update_request.html', form=form, tab=tab, detail=detail,
                           file_url=file_url, appointment_date=appointment_date)


@software_request.route('/admin/request/timeline/add/<int:detail_id>', methods=['GET', 'POST'])
@software_request.route('/admin/request/timeline/edit/<int:timeline_id>', methods=['GET', 'POST'])
def create_timeline(detail_id=None, timeline_id=None):
    tab = request.args.get('tab')
    if detail_id:
        form = SoftwareRequestTimelineForm()
        sequence_no = SoftwareRequestNumberID.get_number('Num', db, software_request='software_request_'+str(detail_id))
    else:
        timeline = SoftwareRequestTimeline.query.get(timeline_id)
        form = SoftwareRequestTimelineForm(obj=timeline)
    if form.validate_on_submit():
        if detail_id:
            timeline = SoftwareRequestTimeline()
        form.populate_obj(timeline)
        if detail_id:
            timeline.sequence = sequence_no.number
            timeline.request_id = detail_id
            timeline.created_at = arrow.now('Asia/Bangkok').datetime
            sequence_no.count += 1
        timeline.start = arrow.get(form.start.data, 'Asia/Bangkok').date()
        timeline.estimate = arrow.get(form.estimate.data, 'Asia/Bangkok').date()
        db.session.add(timeline)
        db.session.commit()
        timeline.request.updated_date = arrow.now('Asia/Bangkok').datetime
        db.session.add(timeline)
        db.session.commit()
        if detail_id:
            flash('เพิ่มข้อมูลสำเร็จ', 'success')
            resp = make_response(render_template('software_request/timeline_template.html',tab=tab,
                                                 timeline=timeline))
            resp.headers['HX-Trigger'] = 'closeTimeline'
        else:
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
            resp = make_response()
            resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('software_request/modal/create_timeline_modal.html', form=form, tab=tab,
                           detail_id=detail_id, timeline_id=timeline_id)


@software_request.route('/admin/request/timeline/update/<int:timeline_id>', methods=['GET', 'POST'])
def update_timeline_status(timeline_id):
    status = request.form.get('status')
    timeline = SoftwareRequestTimeline.query.get(timeline_id)
    timeline.status = status
    timeline.request.updated_date = arrow.now('Asia/Bangkok').datetime
    db.session.add(timeline)
    db.session.commit()
    flash('อัพเดตสถานะสำเร็จ', 'success')
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@software_request.route('/admin/request/timeline/delete/<int:timeline_id>', methods=['GET', 'DELETE'])
def delete_timeline(timeline_id):
    timeline = SoftwareRequestTimeline.query.get(timeline_id)
    timeline.request.updated_date = arrow.now('Asia/Bangkok').datetime
    db.session.add(timeline)
    db.session.commit()
    db.session.delete(timeline)
    db.session.commit()
    flash('ลบข้อมูลสำเร็จ', 'success')
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@software_request.route('/admin/request/issues/<int:issue_id>', methods=['GET', 'POST'])
@software_request.route('/admin/request/details/<int:detail_id>/issues', methods=['GET', 'POST'])
def create_issue(detail_id=None, issue_id=None):
    form = SoftwareRequestIssueForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            if issue_id:
                issue =  SoftwareIssues.query.get(issue_id)
                current_status = issue.status
            else:
                issue = SoftwareIssues(software_request_detail_id=detail_id)
                issue.created_at = arrow.now('Asia/Bangkok').datetime
                issue.creator = current_user
                current_status = ''
            form.populate_obj(issue)

            if form.status_.data != current_status:
                if form.status_.data == 'Cancelled':
                    issue.cancelled_at = arrow.now('Asia/Bangkok').datetime
                elif form.status_.data == 'Closed':
                    issue.closed_at = arrow.now('Asia/Bangkok').datetime
                elif form.status_.data == 'Working':
                    issue.accepted_at = arrow.now('Asia/Bangkok').datetime

            db.session.add(issue)
            db.session.commit()
        else:
            flash(f'{form.errors}', 'danger')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    if issue_id:
        issue = SoftwareIssues.query.get(issue_id)
        form = SoftwareRequestIssueForm(obj=issue)
        form.status_.data = issue.status
        form.populate_obj(issue)
    return render_template('software_request/modal/create_issue_modal.html',
                           form=form, issue_id=issue_id, detail_id=detail_id)