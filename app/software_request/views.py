import os
import arrow
import requests
from sqlalchemy import or_
from flask import render_template, redirect, flash, url_for, jsonify, request, make_response
from flask_login import login_required, current_user

from app.roles import admin_permission
from app.software_request import software_request
from app.software_request.forms import SoftwareRequestDetailForm
from app.software_request.models import *
from werkzeug.utils import secure_filename
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive

gauth = GoogleAuth()
keyfile_dict = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
scopes = ['https://www.googleapis.com/auth/drive']
gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scopes)
drive = GoogleDrive(gauth)

FOLDER_ID = '1832el0EAqQ6NVz2wB7Ade6wRe-PsHQsu'

json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


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


@software_request.route('/request/add', methods=['GET', 'POST'])
def create_request():
    form = SoftwareRequestDetailForm()
    if form.validate_on_submit():
        detail = SoftwareRequestDetail()
        form.populate_obj(detail)
        file = form.file_upload.data
        drive = initialize_gdrive()
        if form.system.data:
            system = SoftwareRequestSystem.query.get(request.form.getlist('system'))
            detail.title = system.system
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
    pending_count = SoftwareRequestDetail.query.filter_by(status='ส่งคำขอแล้ว').count()
    consider_count = SoftwareRequestDetail.query.filter_by(status='อยู่ระหว่างพิจารณา').count()
    approve_count = SoftwareRequestDetail.query.filter_by(status='อนุมัติ').count()
    disapprove_count = SoftwareRequestDetail.query.filter_by(status='ไม่อนุมัติ').count()
    cancel_count = SoftwareRequestDetail.query.filter_by(status='ยกเลิก').count()
    return render_template('software_request/admin_index.html', tab=tab, pending_count=pending_count,
                           consider_count=consider_count, approve_count=approve_count,
                           disapprove_count=disapprove_count,
                           cancel_count=cancel_count)


@software_request.route('/api/request/index')
def get_requests():
    tab = request.args.get('tab')
    if tab == 'pending':
        query = SoftwareRequestDetail.query.filter_by(status='ส่งคำขอแล้ว')
    elif tab == 'consider':
        query = SoftwareRequestDetail.query.filter_by(status='อยู่ระหว่างพิจารณา')
    elif tab == 'approve':
        query = SoftwareRequestDetail.query.filter_by(status='อนุมัติ')
    elif tab == 'disapprove':
        query = SoftwareRequestDetail.query.filter_by(status='ไม่อนุมัติ')
    elif tab == 'cancel':
        query = SoftwareRequestDetail.query.filter_by(status='ยกเลิก')
    else:
        query = SoftwareRequestDetail.query
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


@software_request.route('/admin/request/edit/<int:detail_id>', methods=['GET', 'POST'])
def update_request(detail_id):
    tab = request.args.get('tab')
    detail = SoftwareRequestDetail.query.get(detail_id)
    form = SoftwareRequestDetailForm(obj=detail)
    if detail.url:
        file_upload = drive.CreateFile({'id': detail.url})
        file_upload.FetchMetadata()
        file_url = file_upload.get('embedLink')
    else:
        file_url = None
    if form.validate_on_submit():
        form.populate_obj(detail)
        detail.updated_date = arrow.now('Asia/Bangkok').datetime
        detail.approver_id = current_user.id
        db.session.add(detail)
        db.session.commit()
        flash('ส่งคำขอสำเร็จ', 'success')
        return redirect(url_for('software_request.admin_index', tab=tab))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('software_request/update_request.html', form=form, tab=tab, detail=detail,
                           file_url=file_url)


# @software_request.route('/api/request/add_timeline', methods=['POST'])
# def add_timeline():
#     SoftwareRequestDetailForm = create_request_form(status='have')
#     form = SoftwareRequestDetailForm()
#     form.timelines.append_entry()
#     timeline_form = form.timelines[-1]
#     template = """
#         <div id="{}">
#             <div class="columns">
#                 <div class="column">
#                     <label class="label">{}</label>
#                     <div class="control">
#                         {}
#                     </div>
#                 </div>
#                 <div class="column">
#                     <label class="label">{}</label>
#                     <div class="control">
#                         {}
#                     </div>
#                 </div>
#                 <div class="column">
#                     <label class="label">{}</label>
#                     <div class="control">
#                         {}
#                     </div>
#                 </div>
#                 <div class="column">
#                     <label class="label">{}</label>
#                     <div class="control">
#                         {}
#                     </div>
#                 </div>
#                 <div class="column">
#                     <label class="label">{}</label>
#                     <div class="control">
#                         {}
#                     </div>
#                 </div>
#                 <div class="column">
#                     <label class="label">{}</label>
#                     <div class="control">
#                         {}
#                     </div>
#                 </div>
#             </div>
#         </div>
#     """
#     resp = template.format(timeline_form.id,
#                            timeline_form.requirement.label,
#                            timeline_form.requirement(class_='input'),
#                            timeline_form.start.label,
#                            timeline_form.start(class_='input'),
#                            timeline_form.estimate.label,
#                            timeline_form.estimate(class_='input'),
#                            timeline_form.phase.label,
#                            timeline_form.phase(class_='input'),
#                            timeline_form.status.label,
#                            timeline_form.status(class_='js-example-basic-single'),
#                            timeline_form.admin.label,
#                            timeline_form.admin(class_='js-example-basic-single')
#                            )
#     resp = make_response(resp)
#     resp.headers['HX-Trigger-After-Swap'] = 'activateInput'
#     return resp
#
#
# @software_request.route('/api/request/remove_timeline', methods=['DELETE'])
# def remove_timeline():
#     SoftwareRequestDetailForm = create_request_form(status='have')
#     form = SoftwareRequestDetailForm()
#     form.timelines.pop_entry()
#     resp = ''
#     for timeline_form in form.timelines:
#         template = """
#             <div id="{}" hx-preserve>
#                 <div class="columns">
#                     <div class="column">
#                         <label class="label">{}</label>
#                         <div class="control">
#                             {}
#                         </div>
#                     </div>
#                     <div class="column">
#                         <label class="label">{}</label>
#                         <div class="control">
#                             {}
#                         </div>
#                     </div>
#                     <div class="column">
#                         <label class="label">{}</label>
#                         <div class="control">
#                             {}
#                         </div>
#                     </div>
#                     <div class="column">
#                         <label class="label">{}</label>
#                         <div class="control">
#                             {}
#                         </div>
#                     </div>
#                     <div class="column">
#                         <label class="label">{}</label>
#                         <div class="control">
#                             {}
#                         </div>
#                     </div>
#                     <div class="column">
#                         <label class="label">{}</label>
#                         <div class="control">
#                             {}
#                         </div>
#                     </div>
#                 </div>
#             </div>
#         """
#         resp += template.format(timeline_form.id,
#                                 timeline_form.requirement.label,
#                                 timeline_form.requirement(class_='input'),
#                                 timeline_form.start.label,
#                                 timeline_form.start(class_='input'),
#                                 timeline_form.estimate.label,
#                                 timeline_form.estimate(class_='input'),
#                                 timeline_form.phase.label,
#                                 timeline_form.phase(class_='input'),
#                                 timeline_form.status.label,
#                                 timeline_form.status(class_='js-example-basic-single'),
#                                 timeline_form.admin.label,
#                                 timeline_form.admin(class_='js-example-basic-single')
#                                 )
#     resp = make_response(resp)
#     return resp


@software_request.route('/admin/request/status/update/<int:detail_id>', methods=['GET', 'POST'])
def update_status_of_request(detail_id):
    tab = request.args.get('tab')
    status = request.args.get('status')
    detail = SoftwareRequestDetail.query.get(detail_id)
    detail.status = status
    detail.updated_date = arrow.now('Asia/Bangkok').datetime
    detail.approver_id = current_user.id
    db.session.add(detail)
    db.session.commit()
    flash('อัพเดตสถานะสำเร็จ', 'success')
    return redirect(url_for('software_request.update_request', tab=tab, detail_id=detail_id))