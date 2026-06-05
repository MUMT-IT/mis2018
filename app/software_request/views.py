import os
from datetime import timedelta
import arrow
import  pytz
import requests
from dateutil import parser
from app.main import mail
from flask_mail import Message
from sqlalchemy import or_, func, case, and_
from sqlalchemy.orm import joinedload
from flask import render_template, redirect, flash, url_for, jsonify, request, make_response, current_app
from flask_login import login_required, current_user
from app.roles import it_permission, software_request_permission
from app.software_request import software_request
from app.software_request.forms import create_request_form, create_timeline_form, SoftwareRequestIssueForm, \
    create_test_result_form
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

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'docx', 'doc'}


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scopes)
    return GoogleDrive(gauth)


def update_test_result(test_result, status, note):
    old_note = test_result.note
    old_status = test_result.status
    test_result.status = status
    test_result.note = note
    if test_result.recorded_at and status == old_status and note == old_note:
        test_result.recorded_at = arrow.get(test_result.recorded_at, 'Asia/Bangkok').datetime
        test_result.recorder_id = current_user.id
    elif status or note:
        test_result.recorded_at = arrow.now('Asia/Bangkok').datetime
        test_result.recorder_id = current_user.id
    else:
        test_result.recorded_at = None
        test_result.recorder_id = None
    db.session.add(test_result)
    db.session.commit()


def _get_drive_embed_url(file_id):
    # Avoid a metadata round-trip just to render an already-known Drive file link.
    return f'https://drive.google.com/file/d/{file_id}/preview'


def _build_admin_request_query(tab):
    query = SoftwareRequestDetail.query
    if tab == 'pending':
        return query.filter_by(status='ส่งคำขอแล้ว')
    elif tab == 'consider':
        return query.filter_by(status='อยู่ระหว่างพิจารณา')
    elif tab == 'approve':
        return query.filter_by(status='อนุมัติ')
    elif tab == 'complete':
        return query.filter_by(status='เสร็จสิ้น')
    elif tab == 'disapprove':
        return query.filter_by(status='ไม่อนุมัติ')
    elif tab == 'cancel':
        return query.filter_by(status='ยกเลิก')
    elif tab == 'private':
        return query.outerjoin(SoftwareRequestDetail.timelines).outerjoin(SoftwareRequestDetail.staffs).filter(
            or_(SoftwareRequestTimeline.admin_id == current_user.id,
                StaffAccount.id == current_user.id)
        ).distinct()
    return query


def _build_admin_request_listing_query(base_query):
    # Aggregate counts in SQL so the admin table does not trigger N+1 queries for each row.
    active_timeline_counts = db.session.query(
        SoftwareRequestTimeline.request_id.label('request_id'),
        func.count(SoftwareRequestTimeline.id).label('num_timelines')
    ).filter(
        SoftwareRequestTimeline.status.notin_(['ยกเลิกการพัฒนา', 'เสร็จสิ้น'])
    ).group_by(SoftwareRequestTimeline.request_id).subquery()

    open_issue_counts = db.session.query(
        SoftwareIssues.software_request_detail_id.label('request_id'),
        func.sum(
            case(
                [(SoftwareIssues.closed_at.is_(None), 1)],
                else_=0
            )
        ).label('open_issues')
    ).group_by(SoftwareIssues.software_request_detail_id).subquery()

    return base_query.options(
        # Eager-load requester/org data because the table always renders these fields.
        joinedload(SoftwareRequestDetail.created_by)
            .joinedload(StaffAccount.personal_info)
            .joinedload('org')
    ).outerjoin(
        active_timeline_counts,
        active_timeline_counts.c.request_id == SoftwareRequestDetail.id
    ).outerjoin(
        open_issue_counts,
        open_issue_counts.c.request_id == SoftwareRequestDetail.id
    ).add_columns(
        func.coalesce(active_timeline_counts.c.num_timelines, 0).label('num_timelines'),
        func.coalesce(open_issue_counts.c.open_issues, 0).label('open_issues')
    )


@software_request.route('/')
@login_required
def index():
    org = current_user.personal_info.org
    api = request.args.get('api', 'false')
    query = SoftwareRequestDetail.query.filter(or_(
        SoftwareRequestDetail.created_id == current_user.id,
        SoftwareRequestDetail.created_by.has(
            StaffAccount.personal_info.has(org=org)
        )
    ))

    if api == 'true':
        records_total = query.count()
        search = request.args.get('search[value]')
        if search:
            search_term = u'%{}%'.format(search)
            query = query.filter(or_(
                SoftwareRequestDetail.title.ilike(search_term),
                SoftwareRequestDetail.type.ilike(search_term),
                SoftwareRequestDetail.description.ilike(search_term),
                SoftwareRequestDetail.status.ilike(search_term)
            ))

        start = request.args.get('start', type=int)
        length = request.args.get('length', type=int)
        total_filtered = query.count()

        sort_columns = {
            0: SoftwareRequestDetail.title,
            1: SoftwareRequestDetail.type,
            2: SoftwareRequestDetail.description,
            3: SoftwareRequestDetail.created_date,
            4: SoftwareRequestDetail.status,
        }
        sort_column_index = request.args.get('order[0][column]', default=3, type=int)
        sort_direction = request.args.get('order[0][dir]', default='desc')
        sort_column = sort_columns.get(sort_column_index, SoftwareRequestDetail.created_date)
        if sort_direction == 'asc':
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        if start:
            query = query.offset(start)
        if length and length > 0:
            query = query.limit(length)

        data = []
        for item in query.all():
            data.append({
                'id': item.id,
                'title': item.title,
                'type': item.type,
                'description': item.description,
                'created_date': item.created_date,
                'status': item.status,
                'status_color': item.status_color,
            })

        return jsonify({
            'data': data,
            'recordsFiltered': total_filtered,
            'recordsTotal': records_total,
            'draw': request.args.get('draw', type=int)
        })

    return render_template('software_request/index.html', org=org)


@software_request.route('/condition')
def condition_for_service_request():
    return render_template('software_request/condition_page.html')


@software_request.route('/request/view/<int:detail_id>', methods=['GET', 'POST'])
@login_required
def view_request(detail_id):
    count = 0
    detail = SoftwareRequestDetail.query.get(detail_id)
    datetime_now = arrow.now('Asia/Bangkok').datetime
    if request.method == 'POST':
        for form in request.form:
            if form.startswith("result_") :
                item_id = form.replace("result_", "")
                test_result = SoftwareRequestTestResult.query.get(item_id)
                value = request.form.get(form)
                update_test_result(test_result=test_result, status=value, note=test_result.note if test_result.note else '')
                recorded_at = arrow.get(test_result.recorded_at, 'Asia/Bangkok').datetime if test_result.recorded_at else None
                if datetime_now == recorded_at:
                    count += 1
            if form.startswith("note_") :
                item_id = form.replace("note_", "")
                test_result = SoftwareRequestTestResult.query.get(item_id)
                value = request.form.get(form)
                update_test_result(test_result=test_result, status=test_result.status if test_result.status else '',
                                   note=value)
        flash('บันทึกผลเรียบร้อยแล้ว', 'success')
        if detail.staffs and count > 0:
            scheme = 'http' if current_app.debug else 'https'
            link = url_for("software_request.update_request", detail_id=detail_id, tab='approve', _external=True, _scheme=scheme)
            title = f'''แจ้งผลการทดสอบ{detail.title}'''
            message = f'''ผลการทดสอบ{detail.title} เสร็จสิ้นแล้ว\n'''
            message += f'''โดยมีจำนวนรายการที่ทำการทดสอบทั้งหมด {count} รายการ\n'''
            message += f'''กรุณาตรวจสอบรายละเอียดผลการทดสอบในระบบ\n'''
            message += f'''{link}\n\n'''
            message += f'''ขอบคุณค่ะ\n'''
            message += f'''ระบบขอรับบริการพัฒนา Software\n'''
            message += f'''คณะเทคนิคการแพทย์'''
            send_mail([staff.email + '@mahidol.ac.th' for staff in detail.staffs], title, message)
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
        if form.type.data == 'ปรับปรุงระบบที่มีอยู่' and not form.system.data:
            flash('กรุณาเลือกระบบที่ต้องการปรับปรุง', 'danger')
            return render_template('software_request/create_request.html', form=form)
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
            system_id = request.form.getlist('system')
            system = SoftwareRequestSystem.query.get(system_id)
            detail.title = system.system
            detail.system_id = system.id
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
@software_request_permission.require()
@login_required
def admin_index():
    tab = request.args.get('tab')
    api = request.args.get('api', 'false')
    timelines = SoftwareRequestTimeline.query.filter_by(admin_id=current_user.id)
    pending_query = SoftwareRequestDetail.query.filter_by(status='ส่งคำขอแล้ว')
    consider_query = SoftwareRequestDetail.query.filter_by(status='อยู่ระหว่างพิจารณา')
    approve_query = SoftwareRequestDetail.query.filter_by(status='อนุมัติ')
    complete_query = SoftwareRequestDetail.query.filter_by(status='เสร็จสิ้น')
    disapprove_query = SoftwareRequestDetail.query.filter_by(status='ไม่อนุมัติ')
    cancel_query = SoftwareRequestDetail.query.filter_by(status='ยกเลิก')
    if api == 'true':
        query = _build_admin_request_query(tab)
        records_total = query.count()
        search = request.args.get('search[value]')
        if search:
            search_term = u'%{}%'.format(search)
            query = query.filter(or_(
                SoftwareRequestDetail.title.ilike(search_term),
                SoftwareRequestDetail.type.ilike(search_term),
                SoftwareRequestDetail.description.ilike(search_term),
                SoftwareRequestDetail.status.ilike(search_term)
            ))

        start = request.args.get('start', type=int)
        length = request.args.get('length', type=int)
        total_filtered = query.count()
        # Apply pagination after building the enriched query used by DataTables.
        query = _build_admin_request_listing_query(query)

        sort_columns = {
            0: SoftwareRequestDetail.title,
            1: SoftwareRequestDetail.type,
            2: SoftwareRequestDetail.description,
            5: SoftwareRequestDetail.created_date,
        }
        sort_column_index = request.args.get('order[0][column]', default=5, type=int)
        sort_direction = request.args.get('order[0][dir]', default='desc')
        sort_column = sort_columns.get(sort_column_index, SoftwareRequestDetail.created_date)
        if sort_direction == 'asc':
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        if start:
            query = query.offset(start)
        if length and length > 0:
            query = query.limit(length)

        data = []
        for item, num_timelines, open_issues in query.all():
            data.append(item.to_dict(
                num_timelines=num_timelines,
                open_issues=open_issues,
                has_timeline=bool(num_timelines)
            ))
        return jsonify({'data': data,
                        'recordsFiltered': total_filtered,
                        'recordsTotal': records_total,
                        'draw': request.args.get('draw', type=int)
                        })
    return render_template('software_request/admin_index.html', tab=tab, pending_count=pending_query.count(),
                           consider_count=consider_query.count(), approve_count=approve_query.count(),
                           complete_count=complete_query.count(), disapprove_count=disapprove_query.count(),
                           cancel_count=cancel_query.count(), timelines=timelines)


@software_request.route('/api/timelines/<tab>')
@login_required
def get_timelines(tab):
    start = request.args.get('start')
    end = request.args.get('end')

    if start:
        start = parser.isoparse(start)
    if end:
        end = parser.isoparse(end)

    all_timelines = []
    # Eager-load related objects used to render calendar labels to avoid per-event queries.
    timelines = SoftwareRequestTimeline.query.options(
        joinedload(SoftwareRequestTimeline.request),
        joinedload(SoftwareRequestTimeline.admin).joinedload(StaffAccount.personal_info)
    ).filter(
        SoftwareRequestTimeline.start <= end,
        SoftwareRequestTimeline.estimate >= start,
        SoftwareRequestTimeline.status != 'ยกเลิกการพัฒนา'
    )
    if tab == 'private':
        timelines = timelines.filter(SoftwareRequestTimeline.admin_id == current_user.id)

    for timeline in timelines:
        all_timelines.append({
            'id': timeline.id,
            'detail_id': timeline.request_id,
            'title': '{} ({}) - {}'.format(timeline.task, timeline.request.title, timeline.admin.fullname),
            'start': timeline.start.isoformat(),
            'end': (timeline.estimate + timedelta(days=1)).isoformat(),
            'borderColor': '#aed581' if timeline.status == 'เสร็จสิ้น' else '#b3e5fc',
            'backgroundColor': '#aed581' if timeline.status == 'เสร็จสิ้น' else '#b3e5fc',
            'textColor': '#000000',
        })
    return jsonify(all_timelines)


@software_request.route('/timelines/<int:timeline_id>')
def show_timeline_detail(timeline_id):
    tab = request.args.get('tab')
    timeline = SoftwareRequestTimeline.query.get(timeline_id)
    return render_template('software_request/timeline_detail.html', tab=tab, timeline=timeline)


@software_request.route('/admin/request/edit/<int:detail_id>', methods=['GET', 'POST'])
def update_request(detail_id):
    tab = request.args.get('tab')
    detail = SoftwareRequestDetail.query.get(detail_id)
    status = detail.status
    required_information = detail.required_information
    suggestion = detail.suggestion

    SoftwareRequestDetailForm = create_request_form(detail_id=detail_id)
    form = SoftwareRequestDetailForm(obj=detail)
    if detail.url:
        file_url = _get_drive_embed_url(detail.url)
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
        scheme = 'http' if current_app.debug else 'https'
        link = url_for("software_request.view_request", detail_id=detail_id, _external=True, _scheme=scheme)

        # Consolidate notifications so submit does not block on multiple synchronous mail sends.
        message_sections = []
        if required_information != detail.required_information:
            message_sections.append(
                f'''ทางหน่วยงานไอทีมีความประสงค์ขอข้อมูลเพิ่มเติมเพื่อใช้ประกอบการดำเนินงาน ดังนี้\n{detail.required_information}'''
            )
        if suggestion != detail.suggestion:
            message_sections.append(
                f'''ทางหน่วยงานไอทีมีข้อเสนอแนะเพิ่มเติมเพื่อประกอบการพัฒนาระบบ ดังนี้\n{detail.suggestion}'''
            )
        if form.status.data:
            message_sections.append(
                f'''{detail.approver.fullname} ได้ทำการอัปเดตสถานะคำร้องขอรับบริการพัฒนา Software ของ {detail.title} เป็น "{detail.status}"'''
            )

        if message_sections:
            title = f'''แจ้งอัปเดตคำร้องขอรับบริการพัฒนา Software'''
            message = f'''เรียน {detail.created_by.fullname}\n\n'''
            message += f'''ตามที่ท่านได้ดำเนินการขอรับบริการพัฒนา Software สำหรับ {detail.title} นั้น มีการอัปเดตดังต่อไปนี้\n\n'''
            message += '\n\n'.join(message_sections)
            message += f'''\n\nท่านสามารถตรวจสอบรายละเอียดและความคืบหน้าเพิ่มเติมได้ที่ลิงก์ด้านล่าง\n'''
            message += f'''{link}\n\n'''
            message += f'''หากมีข้อสงสัยหรือต้องการสอบถามข้อมูลเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ที่รับผิดชอบ\n\n'''
            message += f'''ขอบคุณค่ะ\n'''
            message += f'''ระบบขอรับบริการพัฒนา Software\n'''
            message += f'''คณะเทคนิคการแพทย์'''
            send_mail([detail.created_by.email + '@mahidol.ac.th'], title, message)

        # PRG avoids re-running the heavy page setup on POST and prevents duplicate submits on refresh.
        if form.status.data:
            flash('อัพเดตสถานะสำเร็จ', 'success')
        else:
            flash('อัพเดตข้อมูลสำเร็จ  ', 'success')
        return redirect(url_for('software_request.update_request', detail_id=detail_id, tab=tab))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('software_request/update_request.html', form=form, tab=tab, detail=detail,
                           file_url=file_url, appointment_date=appointment_date)


@software_request.route('/admin/request/timeline/add/<int:detail_id>', methods=['GET', 'POST'])
@software_request.route('/admin/request/timeline/edit/<int:timeline_id>', methods=['GET', 'POST'])
def create_timeline(detail_id=None, timeline_id=None):
    tab = request.args.get('tab')
    template = request.args.get('template')
    if detail_id:
        SoftwareRequestTimelineForm = create_timeline_form(detail_id=detail_id)
        form = SoftwareRequestTimelineForm()
        sequence_no = SoftwareRequestNumberID.get_number('Num', db, software_request='software_request_'+str(detail_id))
    else:
        timeline = SoftwareRequestTimeline.query.get(timeline_id)
        SoftwareRequestTimelineForm = create_timeline_form(detail_id=timeline.request_id)
        form = SoftwareRequestTimelineForm(obj=timeline)
        status = timeline.status
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
        timeline.request.approver_id = current_user.id
        db.session.add(timeline)
        db.session.commit()
        if detail_id:
            scheme = 'http' if current_app.debug else 'https'
            link = url_for("software_request.view_request", detail_id=timeline.request_id, _external=True,
                           _scheme=scheme)
            title = f'''แจ้งเพิ่มความคืบหน้า (Timeline) คำร้องขอรับบริการพัฒนา Software'''
            message = f'''เรียน {timeline.request.created_by.fullname}\n\n'''
            message += f'''{timeline.request.approver.fullname} ได้ทำการเพิ่มความคืบหน้า (Timeline) ของคำร้องขอรับบริการพัฒนา \n\n'''
            message += f'''โดยมีรายละเอียดข้อมูลดังต่อไปนี้\n'''
            message += f'''  – งานที่ต้องดำเนินการ (Task): {timeline.task}\n'''
            message += f'''  – สถานะการดำเนินงาน: {timeline.status}\n'''
            message += f'''  – วันที่เริ่มต้น: {timeline.start.strftime('%d/%m/%Y')}\n'''
            message += f'''  – วันที่คาดว่าจะแล้วเสร็จ: {timeline.estimate.strftime('%d/%m/%Y')}\n'''
            message += f'''  – สถานะ: {timeline.status}\n'''
            message += f'''ท่านสามารถตรวจสอบรายละเอียดและความคืบหน้าเพิ่มเติมได้ที่ลิงก์ด้านล่าง\n\n'''
            message += f'''{link}\n\n'''
            message += f'''หากมีข้อสงสัยหรือต้องการสอบถามข้อมูลเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ที่รับผิดชอบ\n\n'''
            message += f'''ขอบคุณค่ะ\n'''
            message += f'''ระบบขอรับบริการพัฒนา Software\n'''
            message += f'''คณะเทคนิคการแพทย์'''
            send_mail([timeline.request.created_by.email + '@mahidol.ac.th'], title, message)
            flash('เพิ่มข้อมูลสำเร็จ', 'success')
            resp = make_response(render_template('software_request/timeline_template.html',tab=tab,
                                                 timeline=timeline, template=template))
            resp.headers['HX-Trigger'] = 'closeTimelineModal '
        else:
            if status != timeline.status:
                scheme = 'http' if current_app.debug else 'https'
                link = url_for("software_request.view_request", detail_id=timeline.request_id, _external=True,
                               _scheme=scheme)
                title = f'''แจ้งอัปเดตสถานะความคืบหน้า (Timeline) คำร้องขอรับบริการพัฒนา Software'''
                message = f'''เรียน {timeline.request.created_by.fullname}\n\n'''
                message += f'''{timeline.request.approver.fullname} ได้ทำการอัปเดตความคืบหน้า (Timeline) ของคำร้องขอรับบริการพัฒนา Software ของ{timeline.request.title}เป็น "{timeline.status}"\n\n'''
                message += f'''ท่านสามารถตรวจสอบรายละเอียดและความคืบหน้าเพิ่มเติมได้ที่ลิงก์ด้านล่าง\n'''
                message += f'''{link}\n\n'''
                message += f'''หากมีข้อสงสัยหรือต้องการสอบถามข้อมูลเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ที่รับผิดชอบ\n\n'''
                message += f'''ขอบคุณค่ะ\n'''
                message += f'''ระบบขอรับบริการพัฒนา Software\n'''
                message += f'''คณะเทคนิคการแพทย์'''
                send_mail([timeline.request.created_by.email + '@mahidol.ac.th'], title, message)
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
            resp = make_response()
            resp.headers['HX-Refresh'] = 'true'
        return resp
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('software_request/modal/create_timeline_modal.html', form=form, tab=tab,
                           detail_id=detail_id, timeline_id=timeline_id, template=template)


@software_request.route('/admin/request/timeline/update/<int:timeline_id>', methods=['GET', 'POST'])
def update_timeline_status(timeline_id):
    status = request.form.get('status')
    timeline = SoftwareRequestTimeline.query.get(timeline_id)
    timeline.status = status
    timeline.request.updated_date = arrow.now('Asia/Bangkok').datetime
    timeline.request.approver_id = current_user.id
    db.session.add(timeline)
    db.session.commit()
    scheme = 'http' if current_app.debug else 'https'
    link = url_for("software_request.view_request", detail_id=timeline.request_id, _external=True, _scheme=scheme)
    title = f'''แจ้งอัปเดตสถานะความคืบหน้า (Timeline) คำร้องขอรับบริการพัฒนา Software'''
    message = f'''เรียน {timeline.request.created_by.fullname}\n\n'''
    message += f'''{timeline.request.approver.fullname} ได้ทำการอัปเดตความคืบหน้า (Timeline) ของคำร้องขอรับบริการพัฒนา Software ของท่านเป็น "{timeline.status}"\n\n'''
    message += f'''ท่านสามารถตรวจสอบรายละเอียดและความคืบหน้าเพิ่มเติมได้ที่ลิงก์ด้านล่าง\n'''
    message += f'''{link}\n\n'''
    message += f'''หากมีข้อสงสัยหรือต้องการสอบถามข้อมูลเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ที่รับผิดชอบ\n\n'''
    message += f'''ขอบคุณค่ะ\n'''
    message += f'''ระบบขอรับบริการพัฒนา Software\n'''
    message += f'''คณะเทคนิคการแพทย์'''
    send_mail([timeline.request.created_by.email + '@mahidol.ac.th'], title, message)
    flash('อัพเดตสถานะสำเร็จ', 'success')
    resp = make_response()
    resp.headers['HX-Redirect'] = 'true'
    return resp


@software_request.route('/admin/request/timeline/delete/<int:timeline_id>', methods=['GET', 'DELETE'])
def delete_timeline(timeline_id):
    tab = request.args.get('tab')
    cancel = request.args.get('cancel', 'false')
    timeline = SoftwareRequestTimeline.query.get(timeline_id)
    timeline.status = 'ยกเลิกการพัฒนา'
    timeline.request.updated_date = arrow.now('Asia/Bangkok').datetime
    timeline.request.approver_id = current_user.id
    db.session.add(timeline)
    db.session.commit()
    scheme = 'http' if current_app.debug else 'https'
    link = url_for("software_request.view_request", detail_id=timeline.request_id, _external=True, _scheme=scheme)
    title = f'''แจ้งการยกเลิกพัฒนาความคืบหน้า (Timeline) คำร้องขอรับบริการพัฒนา Software'''
    message = f'''เรียน {timeline.request.created_by.fullname}\n\n'''
    message += f'''{timeline.request.approver.fullname} ได้ทำการยกเลิกพัฒนาความคืบหน้า (Timeline) ของคำร้องขอรับบริการพัฒนา \n\n'''
    message += f'''โดยมีรายละเอียดข้อมูลดังต่อไปนี้\n'''
    message += f'''  – งานที่ต้องดำเนินการ (Task): {timeline.task}\n'''
    message += f'''  – สถานะการดำเนินงาน: {timeline.status}\n'''
    message += f'''  – วันที่เริ่มต้น: {timeline.start.strftime('%d/%m/%Y')}\n'''
    message += f'''  – วันที่คาดว่าจะแล้วเสร็จ: {timeline.estimate.strftime('%d/%m/%Y')}\n'''
    message += f'''  – สถานะ: {timeline.status}\n'''
    message += f'''ท่านสามารถตรวจสอบรายละเอียดเพิ่มเติมได้ที่ลิงก์ด้านล่าง\n'''
    message += f'''{link}\n\n'''
    message += f'''หากมีข้อสงสัยหรือต้องการสอบถามข้อมูลเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ที่รับผิดชอบ\n\n'''
    message += f'''ขอบคุณค่ะ\n'''
    message += f'''ระบบขอรับบริการพัฒนา Software\n'''
    message += f'''คณะเทคนิคการแพทย์'''
    send_mail([timeline.request.created_by.email + '@mahidol.ac.th'], title, message)
    db.session.delete(timeline)
    db.session.commit()

    resp = make_response()
    if cancel == 'true':
        flash('ยกเลิกรายการสำเร็จ', 'success')
        resp.headers['HX-Redirect'] = url_for('software_request.admin_index', tab=tab)
    else:
        flash('ลบข้อมูลสำเร็จ', 'success')
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
                issue.updated_at = arrow.now('Asia/Bangkok').datetime
                issue.updater = current_user
            else:
                issue = SoftwareIssues(software_request_detail_id=detail_id)
                issue.created_at = arrow.now('Asia/Bangkok').datetime
                issue.creator = current_user
                current_status = ''
            form.populate_obj(issue)

            if form.status_.data != current_status:
                if form.status_.data == 'Cancelled':
                    issue.cancelled_at = arrow.now('Asia/Bangkok').datetime
                    issue.closed_at = None
                    issue.accepted_at = None
                    issue.tested_at = None
                    if issue.timelines:
                        for timeline in issue.timelines:
                            timeline.status = 'ยกเลิกการพัฒนา'
                            db.session.add(timeline)
                        db.session.commit()
                elif form.status_.data == 'Closed':
                    issue.closed_at = arrow.now('Asia/Bangkok').datetime
                    issue.cancelled_at = None
                    issue.accepted_at = None
                    issue.tested_at = None
                    if issue.timelines:
                        for timeline in issue.timelines:
                            timeline.status = 'เสร็จสิ้น'
                            db.session.add(timeline)
                        db.session.commit()
                elif form.status_.data == 'Working':
                    issue.accepted_at = arrow.now('Asia/Bangkok').datetime
                    issue.closed_at = None
                    issue.cancelled_at = None
                    issue.tested_at = None
                    if issue.timelines:
                        for timeline in issue.timelines:
                            timeline.status = 'รอดำเนินการ'
                            db.session.add(timeline)
                        db.session.commit()
                elif form.status_.data == 'Testing':
                    issue.tested_at = arrow.now('Asia/Bangkok').datetime
                    issue.accepted_at = None
                    issue.closed_at = None
                    issue.cancelled_at = None
                    if issue.timelines:
                        for timeline in issue.timelines:
                            timeline.status = 'เสร็จสิ้น'
                            db.session.add(timeline)
                        db.session.commit()
                else:
                    issue.accepted_at = None
                    issue.closed_at = None
                    issue.cancelled_at = None
                    issue.tested_at = None

            db.session.add(issue)
            db.session.commit()
            issue.deadline = arrow.get(form.deadline.data, 'Asia/Bangkok').date() if form.deadline.data else None
            issue.software_request_detail.updated_date = arrow.now('Asia/Bangkok').datetime
            issue.software_request_detail.approver_id = current_user.id
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


@software_request.route('/request/test_result/add/<int:detail_id>', methods=['GET', 'POST'])
@software_request.route('/request/test_result/edit/<int:test_result_id>', methods=['GET', 'POST'])
def create_test_result(detail_id=None, test_result_id=None):
    if detail_id:
        SoftwareRequestTestResultForm = create_test_result_form(detail_id=detail_id, has_note=False)
        form = SoftwareRequestTestResultForm()
    else:
        test_result = SoftwareRequestTestResult.query.get(test_result_id)
        SoftwareRequestTestResultForm = create_test_result_form(detail_id=test_result.request_id, has_note=False)
        form = SoftwareRequestTestResultForm(obj=test_result)
    if form.validate_on_submit():
        if detail_id:
           test_result = SoftwareRequestTestResult()
        form.populate_obj(test_result)
        if detail_id:
            test_result.request_id = detail_id
            test_result.created_at = arrow.now('Asia/Bangkok').datetime
            test_result.creator_id = current_user.id
        else:
            test_result.updated_at = arrow.now('Asia/Bangkok').datetime
            test_result.updater_id = current_user.id
        db.session.add(test_result)
        db.session.commit()
        if detail_id:
            flash('บันทึกข้อมูลผลการทดสอบสำเร็จ', 'success')
            resp = make_response(render_template('software_request/test_result_template.html',
                                                 test_result=test_result))
            resp.headers['HX-Trigger'] = 'closeTestResultModal'
        else:
            flash('อัพเดตข้อมูลผลการทดสอบสำเร็จ', 'success')
            resp = make_response()
            resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('software_request/modal/create_test_result_modal.html', detail_id=detail_id,
                           test_result_id=test_result_id, form=form)


@software_request.route('/request/test_result/delete/<int:test_result_id>', methods=['GET', 'DELETE'])
def delete_test_result(test_result_id):
    test_result = SoftwareRequestTestResult.query.get(test_result_id)
    db.session.delete(test_result)
    db.session.commit()
    flash('ลบผลการทดสอบสำเร็จ', 'success')
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@software_request.route('/request/test_result/note/edit/<int:test_result_id>', methods=['GET', 'POST'])
def create_note(test_result_id):
    test_result = SoftwareRequestTestResult.query.get(test_result_id)
    SoftwareRequestTestResultForm = create_test_result_form(detail_id=test_result.request_id, has_note=True)
    form = SoftwareRequestTestResultForm(obj=test_result)
    if form.validate_on_submit():
        form.populate_obj(test_result)
        db.session.add(test_result)
        db.session.commit()
        flash('บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
        resp = make_response(render_template('software_request/note_template.html',
                                             test_result=test_result))
        resp.headers['HX-Trigger'] = 'closeNoteModal'
        return resp
    return render_template('software_request/modal/create_note_modal.html', form=form,
                           test_result_id=test_result_id)
