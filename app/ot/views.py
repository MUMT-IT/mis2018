# -*- coding:utf-8 -*-
import json
from collections import defaultdict, namedtuple

import dateutil.parser
from dateutil import parser
import arrow
from flask_login import login_required, current_user
import requests
import os
from sqlalchemy import cast, Date, extract, and_

from werkzeug.utils import secure_filename

from app.ot.forms import *
from . import otbp as ot
from app.main import (db, func, StaffPersonalInfo, StaffSpecialGroup,
                      StaffShiftSchedule, StaffWorkLogin, StaffLeaveRequest)
from app.models import Org
from flask import jsonify, render_template, request, redirect, url_for, flash, make_response
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive
from datetime import date, datetime

from ..roles import secretary_permission, manager_permission

today = datetime.today()
if today.month >= 10:
    START_FISCAL_DATE = datetime(today.year, 10, 1)
    END_FISCAL_DATE = datetime(today.year + 1, 9, 30, 23, 59, 59, 0)
else:
    START_FISCAL_DATE = datetime(today.year - 1, 10, 1)
    END_FISCAL_DATE = datetime(today.year, 9, 30, 23, 59, 59, 0)

localtz = pytz.timezone('Asia/Bangkok')


login_tuple = namedtuple('LoginPair', ['start', 'end'])


def convert_to_fiscal_year(date):
    if date.month in [10, 11, 12]:
        return date.year + 1
    else:
        return date.year


def get_start_end_date_for_fiscal_year(fiscal_year):
    """Find start and end date from a given fiscal year.

    param fiscal_year:  fiscal year
    :return: date
    """
    start_date = date(fiscal_year - 1, 10, 1)
    end_date = date(fiscal_year, 9, 30)
    return start_date, end_date


gauth = GoogleAuth()
keyfile_dict = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
scopes = ['https://www.googleapis.com/auth/drive']
gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scopes)
drive = GoogleDrive(gauth)

tz = pytz.timezone('Asia/Bangkok')

FOLDER_ANNOUNCE_ID = '1xQQVOCtZHJmOLLVol8pkOz3CC7urxUAi'
FOLDER_DOCUMENT_ID = '1d8forb97XS-2v2puvH2FfhtD3lw2I4H5'
json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()


def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scopes)
    return GoogleDrive(gauth)


def edit_ot_record_factory(announces):
    class EditOtRecordForm(OtRecordForm):
        compensation = QuerySelectField(
            query_factory=lambda: OtCompensationRate.query.filter(OtCompensationRate.announce_id.in_(announces)),
            get_label='role',
        )

    return EditOtRecordForm


@ot.route('/')
@manager_permission.union(secretary_permission).require()
@login_required
def index():
    announcements = OtPaymentAnnounce.query.filter_by(cancelled_at=None)
    return render_template('ot/index.html', announcements=announcements)


@ot.route('/orgs/<int:org_id>/announcement-list-modal')
@login_required
def list_announcement_modal(org_id):
    announcements = OtPaymentAnnounce.query.filter_by(org_id=org_id)
    return render_template('ot/modals/announcements.html', announcements=announcements)


@ot.route('/announce')
@login_required
def announcement():
    # TODO: check permission of the current user
    if not current_user:
        flash(u'ไม่พบสิทธิในการเข้าถึงหน้าดังกล่าว', 'danger')
        return render_template('ot/index.html')
    compensations = OtCompensationRate.query.all()
    upload_file_url = None
    for compensation in compensations:
        if compensation.announcement.upload_file_url:
            upload_file = drive.CreateFile({'id': compensation.announcement.upload_file_url})
            upload_file.FetchMetadata()
            upload_file_url = upload_file.get('embedLink')
    return render_template('ot/announce.html',
                           compensations=compensations,
                           upload_file_url=upload_file_url)


@ot.route('/announce/create', methods=['GET', 'POST'])
@login_required
def announcement_create_document():
    form = OtPaymentAnnounceForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            payment = OtPaymentAnnounce()
            form.populate_obj(payment)
            drive = initialize_gdrive()
            if form.upload.data:
                upload_file = form.upload.data
                file_name = secure_filename(upload_file.filename)
                upload_file.save(file_name)
                file_drive = drive.CreateFile({'title': file_name,
                                               'parents': [{'id': FOLDER_ANNOUNCE_ID, 'kind': 'drive#fileLink'}]})
                file_drive.SetContentFile(file_name)
                try:
                    file_drive.Upload()
                    permission = file_drive.InsertPermission({'type': 'anyone',
                                                              'value': 'anyone',
                                                              'role': 'reader'})
                except:
                    flash('ไม่สามารถอัพโหลดไฟล์ขึ้น Google drive ได้', 'danger')
                else:
                    flash('ไฟล์ที่แนบมา ถูกบันทึกบน Google drive เรียบร้อยแล้ว', 'success')
                    payment.upload_file_url = file_drive['id']
                    payment.file_name = file_name
            payment.staff = current_user
            db.session.add(payment)
            db.session.commit()
            flash(u'เพิ่มประกาศเรียบร้อยแล้ว', 'success')
            return redirect(url_for('ot.announcement'))
        else:
            for field, err in form.errors.items():
                flash('{} {}'.format(field, err), 'danger')
    return render_template('ot/announce_create_document.html', form=form)


@ot.route('/announce/add-compensation', methods=['GET', 'POST'])
@login_required
def announcement_add_compensation():
    form = OtCompensationRateForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            compensation = OtCompensationRate()
            form.populate_obj(compensation)
            db.session.add(compensation)
            db.session.commit()
            flash(u'เพิ่มรายละเอียดของประกาศเรียบร้อยแล้ว', 'success')
            return redirect(url_for('ot.announcement'))
        else:
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('ot/announce_compensation.html', form=form)


@ot.route('/announce/edit-compensation/<int:com_id>', methods=['GET', 'POST'])
@login_required
def announcement_edit_compensation(com_id):
    compensation = OtCompensationRate.query.get(com_id)
    form = OtCompensationRateForm(obj=compensation)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(compensation)
            db.session.add(compensation)
            db.session.commit()
            flash(u'แก้ไขรายละเอียดของประกาศเรียบร้อยแล้ว', 'success')
            return redirect(url_for('ot.announcement'))
        else:
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('ot/announce_compensation.html', form=form, compensation=compensation)


@ot.route('/document-approval')
@login_required
def document_approval_records():
    # TODO: filter valid document
    documents = OtDocumentApproval.query.all()
    upload_file_url = None
    for document in documents:
        if document.upload_file_url:
            upload_file = drive.CreateFile({'id': document.upload_file_url})
            # upload_file.FetchMetadata()
            upload_file_url = upload_file.get('embedLink')
    return render_template('ot/document_approvals.html',
                           documents=documents, upload_file_url=upload_file_url)


@ot.route('/document-approval/create', methods=['GET', 'POST'])
@login_required
def document_approval_create_document():
    form = OtDocumentApprovalForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            document = OtDocumentApproval()
            form.populate_obj(document)
            drive = initialize_gdrive()
            if form.upload.data:
                upload_file = form.upload.data
                file_name = secure_filename(upload_file.filename)
                upload_file.save(file_name)
                file_drive = drive.CreateFile({'title': file_name,
                                               'parents': [{'id': FOLDER_DOCUMENT_ID, 'kind': 'drive#fileLink'}]})
                file_drive.SetContentFile(file_name)
                try:
                    file_drive.Upload()
                    permission = file_drive.InsertPermission({'type': 'anyone',
                                                              'value': 'anyone',
                                                              'role': 'reader'})
                except:
                    flash('ไม่สามารถอัพโหลดไฟล์ขึ้น Google drive ได้', 'danger')
                else:
                    flash('ไฟล์ที่แนบมา ถูกบันทึกบน Google drive เรียบร้อยแล้ว', 'success')
                    document.upload_file_url = file_drive['id']
                    document.file_name = file_name
            document.created_staff = current_user
            document.org = current_user.personal_info.org
            db.session.add(document)
            db.session.commit()
            flash(u'เพิ่มอนุมัติในหลักการเรียบร้อยแล้ว', 'success')
            return redirect(url_for('ot.document_approval_show_announcement', document_id=document.id))
        else:
            for field, err in form.errors.items():
                flash('{} {}'.format(field, err), 'danger')
    return render_template('ot/document_create_approval.html', form=form)


@ot.route('/document-approval/edit/<int:document_id>', methods=['GET', 'POST'])
@login_required
def document_approval_edit_document(document_id):
    document = OtDocumentApproval.query.get(document_id)
    form = OtDocumentApprovalForm(obj=document)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(document)
            drive = initialize_gdrive()
            # TODO: ถ้าไม่บันทึกไฟล์ใหม่(แก้ข้อมูลส่วนอื่น) ไฟล์เก่าจะหายไปจาก db แต่ไม่หายจาก gg
            if form.upload.data:
                upload_file = form.upload.data
                file_name = secure_filename(upload_file.filename)
                upload_file.save(file_name)
                file_drive = drive.CreateFile({'title': file_name,
                                               'parents': [{'id': FOLDER_DOCUMENT_ID, 'kind': 'drive#fileLink'}]})
                file_drive.SetContentFile(file_name)
                try:
                    file_drive.Upload()
                    permission = file_drive.InsertPermission({'type': 'anyone',
                                                              'value': 'anyone',
                                                              'role': 'reader'})
                except:
                    flash('ไม่สามารถอัพโหลดไฟล์ขึ้น Google drive ได้', 'danger')
                else:
                    flash('ไฟล์ที่แนบมา ถูกบันทึกบน Google drive เรียบร้อยแล้ว', 'success')
                    document.upload_file_url = file_drive['id']
                    document.file_name = file_name
            document.created_staff = current_user
            document.org = current_user.personal_info.org
            db.session.add(document)
            db.session.commit()
            flash(u'แก้ไขอนุมัติในหลักการเรียบร้อยแล้ว', 'success')
            return redirect(url_for('ot.document_approval_records'))
        else:
            for field, err in form.errors.items():
                flash('{} {}'.format(field, err), 'danger')
    return render_template('ot/document_create_approval.html', form=form)


@ot.route('/document-approval/create/<int:document_id>/announcement')
@login_required
def document_approval_show_announcement(document_id):
    approval = OtDocumentApproval.query.get(document_id)
    announcements = OtPaymentAnnounce.query.all()
    if approval.upload_file_url:
        upload_file = drive.CreateFile({'id': approval.upload_file_url})
        upload_file.FetchMetadata()
        upload_file_url = upload_file.get('embedLink')
    else:
        upload_file_url = None
    return render_template('ot/document_announcement.html', approval=approval, upload_file_url=upload_file_url,
                           announcements=announcements)


@ot.route('/document-approval/create/<int:document_id>/add-announcement/<int:announce_id>')
@login_required
def document_approval_add_announcement(document_id, announce_id):
    announcement = OtPaymentAnnounce.query.get(announce_id)
    approval = OtDocumentApproval.query.get(document_id)
    if announcement and approval:
        approval.announce.append(announcement)
        db.session.add(approval)
        db.session.commit()
        flash(u'เพิ่มประกาศสำหรับอนุมัติในหลักการเรียบร้อยแล้ว', 'success')
        return redirect(url_for('ot.document_approval_show_announcement', document_id=document_id))
    else:
        flash(u'ไม่สามารถเพิ่มประกาศได้', 'danger')
        return redirect(url_for('ot.document_approval_show_announcement', document_id=document_id))


@ot.route('/document-approval/create/<int:document_id>/delete-announcement/<int:announce_id>')
@login_required
def document_approval_delete_announcement(document_id, announce_id):
    announcement = OtPaymentAnnounce.query.get(announce_id)
    approval = OtDocumentApproval.query.get(document_id)
    if approval and announcement:
        # TODO: หาว่ามีrecord ไหนที่ใช้อยู่่และเชื่อม ประกาศนี้อยู่ ยังไม่อนุญาตให้ลบหรือไม่ หรือจะหาทางออกยังไง
        approval.announce.remove(announcement)
        db.session.add(approval)
        db.session.commit()
        flash(u'ลบประกาศสำหรับอนุมัติในหลักการเรียบร้อยแล้ว', 'success')
        return redirect(url_for('ot.document_approval_show_announcement', document_id=document_id))
    else:
        flash(u'ไม่สามารถลบประกาศได้', 'danger')
        return redirect(url_for('ot.document_approval_show_announcement', document_id=document_id))


@ot.route('/document-approval/staff/<int:document_id>')
@login_required
def document_approval_show_approved_staff(document_id):
    approval = OtDocumentApproval.query.get(document_id)
    staff = StaffAccount.query.all()
    if approval.upload_file_url:
        upload_file = drive.CreateFile({'id': approval.upload_file_url})
        upload_file.FetchMetadata()
        upload_file_url = upload_file.get('embedLink')
    else:
        upload_file_url = None
    return render_template('ot/document_staff.html', approval=approval, staff=staff, upload_file_url=upload_file_url)


@ot.route('/document-approval/<int:document_id>/add-staff/<int:staff_id>')
@login_required
def document_approval_add_staff(document_id, staff_id):
    document = OtDocumentApproval.query.get(document_id)
    staff = StaffAccount.query.get(staff_id)
    if document:
        document.staff.append(staff)
        db.session.add(document)
        db.session.commit()
        flash(u'เพิ่มบุคลากรเรียบร้อยแล้ว', 'success')
        return redirect(url_for('ot.document_approval_show_approved_staff', document_id=document_id))
    else:
        flash(u'ไม่สามารถเพิ่มบุคลากรได้', 'danger')
        return redirect(url_for('ot.document_approval_show_approved_staff', document_id=document_id))


@ot.route('/document-approval/<int:document_id>/delete-staff/<int:staff_id>')
@login_required
def document_approval_delete_staff(document_id, staff_id):
    document = OtDocumentApproval.query.get(document_id)
    staff = StaffAccount.query.get(staff_id)
    if document:
        document.staff.remove(staff)
        db.session.add(document)
        db.session.commit()
        flash(u'ลบบุคลากรเรียบร้อยแล้ว', 'warning')
        return redirect(url_for('ot.document_approval_show_approved_staff', document_id=document_id))
    else:
        flash(u'ไม่สามารถลบบุคลากรได้', 'danger')
        return redirect(url_for('ot.document_approval_show_approved_staff', document_id=document_id))


@ot.route('/document-approvals/list/for-ot')
@login_required
def document_approvals_list_for_create_ot():
    documents = OtDocumentApproval.query.filter_by(org_id=current_user.personal_info.org.id).all()
    if documents:
        for document in documents:
            if document.upload_file_url:
                upload_file = drive.CreateFile({'id': document.upload_file_url})
                # upload_file.FetchMetadata()
                upload_file_url = upload_file.get('embedLink')
            else:
                upload_file_url = None
            # TODO: warning expired document
            # if document.end_datetime:
            #     if document.end_datetime <= today:
            #         is_expired = True
        return render_template('ot/document_approvals_list_create_scedule.html', documents=documents,
                               upload_file_url=upload_file_url)
    else:
        flash(u'หน่วยงานของท่านไม่มีอนุมัติในหลักการ กรุณาสร้างอนุมัติในหลักการก่อนทำการเบิกค่าตอบแทนล่วงเวลา',
              'warning')
        return render_template('ot/index.html')


@ot.route('/schedule/create/<int:document_id>', methods=['GET', 'POST'])
@login_required
def add_schedule(document_id):
    document = OtDocumentApproval.query.get(document_id)
    EditOtRecordForm = edit_ot_record_factory([a.id for a in document.announce])
    form = EditOtRecordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            for staff_id in request.form.getlist("otworker"):
                record = OtRecord()
                form.populate_obj(record)
                if form.compensation.data.start_time:
                    start_t = form.compensation.data.start_time
                    end_t = form.compensation.data.end_time
                else:
                    if form.start_time.data == "None" or form.end_time.data == "None":
                        flash(u'จำเป็นต้องใส่เวลาเริ่มต้น สิ้นสุด', 'danger')
                        return render_template('ot/schedule_add.html', form=form, document=document)
                    else:
                        start_t = form.start_time.data + ':00'
                        end_t = form.end_time.data + ':00'
                start_d = form.start_date.data
                end_d = form.start_date.data
                start_dt = '{} {}'.format(start_d, start_t)
                end_dt = '{} {}'.format(end_d, end_t)
                start_datetime = datetime.strptime(start_dt, '%Y-%m-%d %H:%M:%S')
                end_datetime = datetime.strptime(end_dt, '%Y-%m-%d %H:%M:%S')
                ot_records_begin_overlaps = OtRecord.query.filter(OtRecord.staff_account_id == staff_id) \
                    .filter(OtRecord.start_datetime <= start_datetime) \
                    .filter(OtRecord.end_datetime >= start_datetime).all()
                ot_records_end_overlaps = OtRecord.query.filter(OtRecord.staff_account_id == staff_id) \
                    .filter(OtRecord.start_datetime <= end_datetime) \
                    .filter(OtRecord.end_datetime >= end_datetime).all()
                staff_name = StaffAccount.query.get(staff_id)
                if ot_records_begin_overlaps or ot_records_end_overlaps:
                    flash(u'{} มีข้อมูลการทำOT ในช่วงเวลานี้แล้ว กรุณาตรวจสอบเวลาใหม่อีกครั้ง'.format(
                        staff_name.personal_info.fullname), 'danger')
                else:
                    record.start_datetime = start_datetime
                    record.end_datetime = end_datetime
                    record.created_staff = current_user
                    record.org = current_user.personal_info.org
                    record.staff_account_id = staff_id
                    record.document_id = document_id
                    if request.form.get('sub_role'):
                        record.sub_role = request.form.get('sub_role')
                    flash(u'บันทึกการทำงานของ {} เรียบร้อยแล้ว'.format(staff_name.personal_info.fullname), 'success')
                    db.session.add(record)
                    db.session.commit()
            return redirect(url_for('ot.document_approvals_list_for_create_ot'))
        else:
            print(form.errors, form.start_time.data)
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('ot/schedule_add.html', form=form, document=document)


@ot.route('/schedule/cancel/<int:record_id>')
@login_required
def cancel_ot_record(record_id):
    record = OtRecord.query.get(record_id)
    record.canceled_at = tz.localize(datetime.today())
    record.canceled_by_account_id = current_user.id
    db.session.add(record)
    db.session.commit()
    flash(u'ยกเลิก OT ของ {} {} เรียบร้อยแล้ว'.format(record.staff.personal_info.fullname, record.start_datetime),
          'danger')
    return redirect(url_for('ot.summary_ot_each_document', document_id=record.document_id,
                            month=record.start_datetime.month, year=record.start_datetime.year))


@ot.route('/announcements/<int:announcement_id>/schedule', methods=['GET', 'POST'])
@manager_permission.union(secretary_permission).require()
@login_required
def add_ot_schedule(announcement_id):
    slots = OtTimeSlot.query.filter_by(announcement_id=announcement_id).order_by(OtTimeSlot.start).all()
    return render_template('ot/schedule_add.html', announcement_id=announcement_id, slots=slots)


@ot.route('/announcements/<int:announcement_id>/shifts')
@manager_permission.union(secretary_permission).require()
@login_required
def get_shifts(announcement_id):
    start = request.args.get('start')
    start = arrow.get(dateutil.parser.parse(start), 'Asia/Bangkok').datetime
    shifts = []
    for slot in OtTimeSlot.query.filter_by(announcement_id=announcement_id):
        for shift in slot.shifts:
            if shift.datetime.lower.date() == start.date():
                shifts.append({
                    'id': f'shift-{shift.id}',
                    'start': shift.datetime.lower.isoformat(),
                    'end': shift.datetime.upper.isoformat(),
                    'title': ','.join([rec.staff.personal_info.th_firstname for rec in shift.records]),
                    'textColor': shift.timeslot.color or '',
                })
    return jsonify(shifts)


@ot.route('/timeslots/<_id>/ot-form-modal', methods=['GET', 'POST'])
@ot.route('/timeslots/ot-form-modal', methods=['GET', 'POST'])
@manager_permission.union(secretary_permission).require()
@login_required
def show_ot_form_modal(_id=None):
    start = request.args.get('start')
    start = arrow.get(dateutil.parser.parse(start), 'Asia/Bangkok').datetime

    if _id is None:
        _id = request.args.get('slot-id')

    if _id.startswith('timeslot'):
        _, slot_id = _id.split('-')
        slot = OtTimeSlot.query.get(slot_id)
        start = datetime.combine(start.date(), slot.start)
        end = datetime.combine(start.date(), slot.end)
        if slot.end.hour == 0 and slot.end.minute == 0:
            datetime_ = DateTimeRange(lower=start, upper=end + timedelta(days=1), bounds='[)')
        else:
            datetime_ = DateTimeRange(lower=start, upper=end, bounds='[)')
        shift = OtShift.query.filter_by(datetime=datetime_).first()
    elif _id.startswith('shift'):
        _, shift_id = _id.split('-')
        shift = OtShift.query.get(shift_id)
        slot = shift.timeslot

    RecordForm = create_ot_record_form(slot.id)
    form = RecordForm()
    form.staff.choices = [(staff.id, staff.fullname) for staff in StaffAccount.query]
    if form.validate_on_submit():
        if not shift:
            shift = OtShift(date=start.date(), timeslot=slot, creator=current_user)
        for staff_id in form.staff.data:
            ot_record = OtRecord.query.filter_by(shift=shift, staff_account_id=staff_id).first()
            if not ot_record:
                ot_record = OtRecord(
                    staff_account_id=staff_id,
                    created_account_id=current_user.id,
                    shift=shift,
                    compensation=form.compensation.data,
                )
                shift.records.append(ot_record)
        db.session.add(shift)
        db.session.commit()
    else:
        print(form.errors)
    template = render_template('ot/modals/ot_record_form.html',
                               start=start,
                               target_url=url_for('ot.show_ot_form_modal', _id=_id, start=request.args.get('start')),
                               form=form, slot_id=slot.id, slot=slot, shift=shift)
    resp = make_response(template)
    resp.headers['HX-Trigger-After-Swap'] = json.dumps({"initSelect2js": "",
                                                        "clearSelection": "",
                                                        "refetchEvents": ""})
    return resp


@ot.route('/records/<int:record_id>/remove', methods=['DELETE'])
@manager_permission.union(secretary_permission).require()
@login_required
def remove_record(record_id):
    record = OtRecord.query.get(record_id)
    db.session.delete(record)
    db.session.commit()
    resp = make_response()
    resp.headers['HX-Trigger'] = 'refetchEvents'
    return resp


@ot.route('/documents/<int:doc_id>/compensation_rates', methods=['POST'])
@manager_permission.union(secretary_permission).require()
@login_required
def get_compensation_rates(doc_id):
    form = OtScheduleForm()
    document = OtDocumentApproval.query.get(doc_id)
    compensations = []
    for a in document.announce:
        compensations += [rate for rate in a.ot_rate if rate.role == form.role.data]

    entry_ = form.items.append_entry()
    entry_.compensation.choices = [(rate.id, rate) for rate in compensations]
    entry_.time_slots.choices = [(slot.id, slot) for slot in compensations[0].time_slots]
    entry_.staff.choices = [(staff.id, staff.fullname) for staff in document.org.active_staff]
    template = f'''
    <div class="field">
        <div class="select">
            {entry_.compensation()}
        </div>
    </div>
    <div class="field" id="{entry_.staff.id}">
        {entry_.staff(class_="js-example-basic-multiple")}
    </div>
    <div class="field" id="{entry_.time_slots.id}">
        {entry_.time_slots()}
    </div>
    '''
    resp = make_response(template)
    resp.headers['HX-Trigger-After-Swap'] = 'initSelect2jsEvent'
    return resp


@ot.route('/documents/<int:doc_id>/schedule/records')
@manager_permission.union(secretary_permission).require()
@login_required
def list_ot_records(doc_id):
    document = OtDocumentApproval.query.get(doc_id)
    shifts = defaultdict(list)
    for rec in document.ot_records:
        shifts[rec.shift_datetime].append(rec)
    return render_template('ot/records.html', doc=document, shifts=shifts)


@ot.route('/schedule/<int:record_id>/delete', methods=['DELETE'])
@manager_permission.union(secretary_permission).require()
@login_required
def delete_ot_record(record_id):
    record = OtRecord.query.get(record_id)
    db.session.delete(record)
    db.session.commit()
    return ''


@ot.route('/schedule/edit/<int:record_id>', methods=['GET', 'POST'])
@login_required
def edit_ot_record(record_id):
    record = OtRecord.query.get(record_id)
    document = OtDocumentApproval.query.get(record.document_id)
    EditOtRecordForm = edit_ot_record_factory([a.id for a in document.announce])
    form = EditOtRecordForm(obj=record)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(record)
            if form.compensation.data.start_time:
                start_t = form.compensation.data.start_time
                end_t = form.compensation.data.end_time
            else:
                if form.start_time.data == "None" or form.end_time.data == "None":
                    flash(u'จำเป็นต้องใส่เวลาเริ่มต้น สิ้นสุด', 'danger')
                else:
                    start_t = form.start_time.data + ':00'
                    end_t = form.end_time.data + ':00'
            start_d = form.start_date.data
            end_d = form.start_date.data
            start_dt = '{} {}'.format(start_d, start_t)
            end_dt = '{} {}'.format(end_d, end_t)
            start_datetime = datetime.strptime(start_dt, '%Y-%m-%d %H:%M:%S')
            end_datetime = datetime.strptime(end_dt, '%Y-%m-%d %H:%M:%S')
            record.start_datetime = start_datetime
            record.end_datetime = end_datetime
            ot_records_begin_overlaps = OtRecord.query.filter(and_(OtRecord.id != record.id,
                                                                   OtRecord.staff_account_id == record.staff_account_id,
                                                                   OtRecord.start_datetime <= start_datetime,
                                                                   OtRecord.end_datetime >= start_datetime)).all()
            ot_records_end_overlaps = OtRecord.query.filter(and_(OtRecord.id != record.id,
                                                                 OtRecord.staff_account_id == record.staff_account_id,
                                                                 OtRecord.start_datetime <= end_datetime,
                                                                 OtRecord.end_datetime >= end_datetime)).all()
            if ot_records_begin_overlaps or ot_records_end_overlaps:
                flash(u'{} มีข้อมูลการทำOT ในช่วงเวลานี้แล้ว กรุณาตรวจสอบเวลาใหม่อีกครั้ง'.format(
                    record.staff.personal_info.fullname), 'danger')
            else:
                record.created_staff = current_user
                record.org = current_user.personal_info.org
                if request.form.get('sub_role'):
                    record.sub_role = request.form.get('sub_role')
                db.session.add(record)
                db.session.commit()
                flash(u'แก้ไขการทำงานของ {} เรียบร้อยแล้ว'.format(record.staff.personal_info.fullname), 'success')
                year = form.start_date.data.year
                month = form.start_date.data.month
                return redirect(
                    url_for('ot.summary_ot_each_document', document_id=record.document_id, month=month, year=year))
        else:
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    form.start_date.data = record.start_datetime.date()
    form.start_time.data = record.start_datetime.strftime("%H:%M")
    form.end_time.data = record.end_datetime.strftime("%H:%M")
    return render_template('ot/schedule_edit_each_record.html', form=form, record=record)


@ot.route('/api/get-file-url/<int:announcement_id>')
@login_required
def get_file_url(announcement_id):
    ann = OtPaymentAnnounce.query.get(announcement_id)
    return jsonify({'url': ann.upload_file_url})


@ot.route('/api/compensation-detail/<int:compensation_id>')
@login_required
def get_compensation_detail(compensation_id):
    comp = OtCompensationRate.query.get(compensation_id)
    return jsonify({'info': comp.to_dict()})


@ot.route('/schedule/summary')
@login_required
def summary_index():
    depts = Org.query.all()
    fiscal_year = request.args.get('fiscal_year')
    if fiscal_year is None:
        if today.month in [10, 11, 12]:
            fiscal_year = today.year + 1
        else:
            fiscal_year = today.year
        init_date = today
    else:
        fiscal_year = int(fiscal_year)
        init_date = date(fiscal_year - 1, 10, 1)
    if len(depts) == 0:
        # return redirect(request.referrer)
        return redirect(url_for("ot.schedule"))
    curr_dept_id = request.args.get('curr_dept_id')
    tab = request.args.get('tab', 'all')
    if curr_dept_id is None:
        curr_dept_id = depts[0].id
    employees = StaffPersonalInfo.query.all()
    ot_r = []
    for emp in employees:
        if tab == 'ot' or tab == 'all':
            fiscal_years = OtRecord.query.distinct(func.date_part('YEAR', OtRecord.start_datetime))
            fiscal_years = [convert_to_fiscal_year(ot.start_datetime) for ot in fiscal_years]
            start_fiscal_date, end_fiscal_date = get_start_end_date_for_fiscal_year(fiscal_year)
            for ot_record in OtRecord.query.filter_by(org_id=current_user.personal_info.org.id,
                                                      staff=emp.staff_account).filter(
                OtRecord.start_datetime.between(start_fiscal_date, end_fiscal_date)):
                shift_schedule_overlaps = StaffShiftSchedule.query.filter(StaffShiftSchedule.staff == ot_record.staff) \
                    .filter(StaffShiftSchedule.start_datetime <= ot_record.start_datetime) \
                    .filter(StaffShiftSchedule.end_datetime >= ot_record.start_datetime).all()
                shift_schedules = StaffShiftSchedule.query.filter(StaffShiftSchedule.staff == ot_record.staff) \
                    .filter(cast(StaffShiftSchedule.start_datetime, Date) == ot_record.start_datetime.date()).all()
                work_login_checkin = StaffWorkLogin.query.filter(StaffWorkLogin.staff == ot_record.staff) \
                    .filter(cast(StaffWorkLogin.start_datetime, Date) == ot_record.start_datetime.date()).all()
                work_login_checkout = StaffWorkLogin.query.filter(StaffWorkLogin.staff == ot_record.staff) \
                    .filter(cast(StaffWorkLogin.end_datetime, Date) == ot_record.end_datetime.date()).all()
                leave_request = StaffLeaveRequest.query.filter(StaffLeaveRequest.staff == ot_record.staff) \
                    .filter(cast(StaffLeaveRequest.start_datetime, Date) == ot_record.start_datetime.date()).all()

                if not shift_schedules and not work_login_checkin and not work_login_checkout:
                    text_color = '#ffffff'
                    bg_color = '#F0475A'
                    # u'ไม่พบเวลาปฏิบัติงาน และไม่พบบันทึกเวลาสแกนเข้า-ออกงาน'
                elif shift_schedule_overlaps and not work_login_checkin or not work_login_checkout:
                    text_color = '#ffffff'
                    bg_color = '#F0475A'
                    # u'เวลาปฏิบัติงานปกติตรงกับเวลาที่ขอเบิกค่าล่วงเวลา และไม่พบบันทึกเวลาสแกนเข้า-ออกงาน'
                elif not shift_schedules and not work_login_checkin:
                    text_color = '#ffffff'
                    bg_color = '#F0475A'
                    # u'ไม่พบเวลาปฏิบัติงาน และไม่พบบันทึกเวลาสแกนเข้างาน'
                elif not shift_schedules and not work_login_checkout:
                    text_color = '#ffffff'
                    bg_color = '#F0475A'
                    # u'ไม่พบเวลาปฏิบัติงาน และไม่พบบันทึกเวลาสแกนออกงาน'
                elif not work_login_checkin or not work_login_checkout:
                    text_color = '#ffffff'
                    bg_color = '#F0475A'
                    # u'ไม่พบบันทึกเวลาสแกนเข้า-ออกงาน'
                elif not shift_schedules:
                    text_color = '#ffffff'
                    bg_color = '#F0475A'
                    # u'ไม่พบเวลาปฏิบัติงาน'
                elif shift_schedule_overlaps:
                    text_color = '#ffffff'
                    bg_color = '#F0475A'
                    # u'เวลาปฏิบัติงานปกติตรงกับเวลาที่ขอเบิกค่าล่วงเวลา'
                elif not work_login_checkin:
                    text_color = '#ffffff'
                    bg_color = '#F0475A'
                    # u'ไม่พบบันทึกเวลาสแกนเข้างาน'
                elif not work_login_checkout:
                    text_color = '#ffffff'
                    bg_color = '#F0475A'
                    # ot_record["condition"] = u'ไม่พบบันทึกเวลาสแกนสิ้นสุดงาน'
                elif not leave_request:
                    text_color = '#ffffff'
                    bg_color = '#F0475A'
                    # ot_record["condition"] = u'ตรงกับวันลาปฏิบัติงาน'
                else:
                    text_color = '#ffffff'
                    bg_color = '#2268F3'
                border_color = '#ffffff'
                ot_r.append({
                    'id': ot_record.id,
                    'start': ot_record.start_datetime,
                    'end': ot_record.end_datetime,
                    'title': u'{} {}'.format(emp.th_firstname, ot_record.compensation.role),
                    'backgroundColor': bg_color,
                    'borderColor': border_color,
                    'textColor': text_color,
                    'type': 'ot'
                })
            all = ot_r
    return render_template('ot/schedule_summary.html',
                           init_date=init_date,
                           depts=depts, curr_dept_id=int(curr_dept_id),
                           all=all, tab=tab, fiscal_years=fiscal_years, fiscal_year=fiscal_year)


@ot.route('/schedule/summary/each-org')
@login_required
def summary_ot_each_org():
    documents = set()
    records = OtRecord.query.filter_by(org_id=current_user.personal_info.org.id) \
        .filter(OtRecord.round_id == None) \
        .filter(OtRecord.canceled_at == None).all()
    for record in records:
        documents.add(
            (record.document.id, record.document.title, record.start_datetime.month, record.start_datetime.year))
    return render_template('ot/schedule_summary_each_org.html', documents=documents)


@ot.route('/schedule/summary/each-org/<int:document_id>/<int:month>/<int:year>')
@login_required
def summary_ot_each_document(document_id, month, year):
    records = OtRecord.query.filter_by(document_id=document_id, org_id=current_user.personal_info.org.id) \
        .filter(extract('month', OtRecord.start_datetime) == month) \
        .filter(extract('year', OtRecord.start_datetime) == year).filter(OtRecord.round_id == None).all()
    document = OtDocumentApproval.query.get(document_id)
    ot_records = []
    for record in records:
        ot_record = dict(
            id=record.id,
            staff=record.staff.personal_info.fullname,
            start_date=record.start_datetime.date(),
            start_time=record.start_datetime.time(),
            end_time=record.end_datetime.time(),
            compensation=record.compensation,
            work_at=record.compensation.work_at_org,
            work_for=record.compensation.work_for_org,
            sub_role=record.sub_role,
            condition=None,
            rate=None,
            hour=None,
            total_rate=None,
            canceled_at=record.canceled_at
        )
        ot_record["hour"] = record.total_ot_hours()
        ot_record["total_rate"] = record.count_rate()
        if record.compensation.per_period:
            ot_record["rate"] = u'{} บาทต่อคาบ'.format(record.compensation.per_period)
        elif record.compensation.per_hour:
            ot_record["rate"] = u'{} บาทต่อชั่วโมง'.format(record.compensation.per_hour)
        else:
            ot_record["rate"] = u'{} บาทต่อวัน'.format(record.compensation.per_day)
        shift_schedule_overlaps = StaffShiftSchedule.query.filter(StaffShiftSchedule.staff == record.staff) \
            .filter(StaffShiftSchedule.start_datetime <= record.start_datetime) \
            .filter(StaffShiftSchedule.end_datetime >= record.start_datetime) \
            .filter(StaffShiftSchedule.start_datetime <= record.end_datetime) \
            .filter(StaffShiftSchedule.end_datetime >= record.end_datetime).all()
        shift_schedules = StaffShiftSchedule.query.filter(StaffShiftSchedule.staff == record.staff) \
            .filter(cast(StaffShiftSchedule.start_datetime, Date) == record.start_datetime.date()).all()
        work_login_checkin = StaffWorkLogin.query.filter(StaffWorkLogin.staff == record.staff) \
            .filter(cast(StaffWorkLogin.start_datetime, Date) == record.start_datetime.date()).all()
        work_login_checkout = StaffWorkLogin.query.filter(StaffWorkLogin.staff == record.staff) \
            .filter(cast(StaffWorkLogin.end_datetime, Date) == record.end_datetime.date()).all()
        leave_request = StaffLeaveRequest.query.filter(StaffLeaveRequest.staff == record.staff) \
            .filter(cast(StaffLeaveRequest.start_datetime, Date) == record.start_datetime.date()).all()
        # TODO: compare ot record with worklogin
        if not shift_schedules and not work_login_checkin and not work_login_checkout:
            ot_record["condition"] = u'ไม่พบเวลาปฏิบัติงาน และไม่พบบันทึกเวลาสแกนเข้า-ออกงาน'
        elif shift_schedule_overlaps and not work_login_checkin or not work_login_checkout:
            ot_record[
                "condition"] = u'เวลาปฏิบัติงานปกติตรงกับเวลาที่ขอเบิกค่าล่วงเวลา และไม่พบบันทึกเวลาสแกนเข้า-ออกงาน'
        elif not shift_schedules and not work_login_checkin:
            ot_record["condition"] = u'ไม่พบเวลาปฏิบัติงาน และไม่พบบันทึกเวลาสแกนเข้างาน'
        elif not shift_schedules and not work_login_checkout:
            ot_record["condition"] = u'ไม่พบเวลาปฏิบัติงาน และไม่พบบันทึกเวลาสแกนออกงาน'
        elif not work_login_checkin or not work_login_checkout:
            ot_record["condition"] = u'ไม่พบบันทึกเวลาสแกนเข้า-ออกงาน'
        elif not shift_schedules:
            ot_record["condition"] = u'ไม่พบเวลาปฏิบัติงาน'
        elif shift_schedule_overlaps:
            ot_record["condition"] = u'เวลาปฏิบัติงานปกติตรงกับเวลาที่ขอเบิกค่าล่วงเวลา'
        elif not work_login_checkin:
            ot_record["condition"] = u'ไม่พบบันทึกเวลาสแกนเข้างาน'
        elif not work_login_checkout:
            ot_record["condition"] = u'ไม่พบบันทึกเวลาสแกนสิ้นสุดงาน'
        elif not leave_request:
            ot_record["condition"] = u'ตรงกับวันลาปฏิบัติงาน'
        ot_records.append(ot_record)
    return render_template('ot/schedule_each_document.html', records=records, document=document, ot_records=ot_records,
                           month=month, year=year)


@ot.route('/schedule/summary/each-org/<int:document_id>/<int:month>/<int:year>/create-approval-create-download')
@login_required
def create_ot_approval_and_download(document_id, month, year):
    approver = Org.query.filter_by(id=current_user.personal_info.org.id).first()
    org_head = StaffAccount.query.filter_by(email=approver.head).first()
    round = OtRoundRequest(
        created_at=datetime.now(tz),
        created_by_account_id=current_user.id,
        approval_by_account_id=org_head.id,
        round_no=str(month) + "/" + str(year) + "-" + str(document_id)
    )
    db.session.add(round)
    for record in OtRecord.query.filter_by(document_id=document_id).filter(
            extract('month', OtRecord.start_datetime) == month) \
            .filter(extract('year', OtRecord.start_datetime) == year).filter(OtRecord.canceled_at == None).all():
        record.round = round
        db.session.add(record)
    db.session.commit()
    flash(u'ส่งคำขอเรียบร้อยแล้ว', 'success')
    # for ot_record in ot_records_query:
    #     record = {}
    #     record["start_datetime"] = ot_record.start_datetime
    #     record["staff"] = ot_record.staff.personal_info.fullname
    #     ot_list.append(record)
    # df = DataFrame(record)
    # summary = df.pivot_table(index='staff', columns='start_datetime', aggfunc=len, fill_value=0)
    # summary.to_excel('ot_summary.xlsx')
    # flash(u'ดาวน์โหลดไฟล์เรียบร้อยแล้ว ชื่อไฟล์ ot_summary.xlsx', 'success')
    return redirect(url_for('ot.round_request_status'))


@ot.route('/summary/each-org/round-request/status')
@login_required
def round_request_status():
    rounds = OtRoundRequest.query.filter_by(created_by=current_user).all()
    return render_template('ot/request_status.html', rounds=rounds)


@ot.route('/approver/requests-pending-list')
@login_required
def round_request_approval_requests_pending():
    rounds = OtRoundRequest.query.filter_by(approval_by=current_user).all()
    return render_template('ot/approver_pending_list.html', rounds=rounds)


@ot.route('/round-request/<int:round_id>/approval-info')
@login_required
def round_request_info(round_id):
    round = OtRoundRequest.query.filter_by(id=round_id).first()
    return render_template('ot/request_info_each_round.html', round=round)


@ot.route('/approver/round-request/<int:round_id>/approved')
@login_required
def round_request_approve_request(round_id):
    round = OtRoundRequest.query.get(round_id)
    round.approval_at = datetime.now(tz);
    db.session.add(round)
    db.session.commit()
    flash(u'อนุมัติรายการ{} เรียบร้อยแล้ว'.format(round.round_no), 'success')
    rounds = OtRoundRequest.query.filter_by(approval_by=current_user).all()
    return render_template('ot/approver_pending_list.html', rounds=rounds)


@ot.route('/finance/approved-list')
@login_required
def approved_list_from_org_head():
    rounds = OtRoundRequest.query.all()
    return render_template('ot/approved_list.html', rounds=rounds)


@ot.route('/finance/requests-pending-list/<int:round_id>')
@login_required
def round_request_info_for_finance(round_id):
    it = StaffSpecialGroup.query.filter_by(group_code='it').first()
    finance = StaffSpecialGroup.query.filter_by(group_code='finance').first()
    if current_user in it.staffs or current_user in finance.staffs:
        round = OtRoundRequest.query.filter_by(id=round_id).first()
        return render_template('ot/finance_approval_info.html', round=round)
    else:
        flash(u'ไม่พบสิทธิในการเข้าถึงหน้าดังกล่าว', 'danger')
        return redirect(request.referrer)


@ot.route('/finance/requests-pending-list/<int:round_id>/verify')
@login_required
def round_request_verify(round_id):
    for record in OtRecord.query.filter_by(round_id=round_id).all():
        if record.compensation.is_count_in_mins:
            record.total_hours = record.total_ot_hours()
        else:
            record.total_minutes = record.total_ot_hours()
        record.amount_paid = record.count_rate()
        db.session.add(record)
    round = OtRoundRequest.query.get(round_id)
    round.verified_by_account_id = current_user.id
    round.verified_at = datetime.now(tz)
    db.session.add(round)
    db.session.commit()
    flash(u'รับรองรายการ{} เรียบร้อยแล้ว'.format(round.round_no), 'success')
    rounds = OtRoundRequest.query.all()
    return render_template('ot/approved_list.html', rounds=rounds)


@ot.route('/<list_type>')
def event_list(list_type='timelineDay'):
    return render_template('ot/summary_chart.html', list_type=list_type)


@ot.route('/api/staff')
@login_required
def get_records(org_id):
    # org_id = request.args.get('deptid')
    # if org_id is None:
    #     ot_query = OtRecord.query.all()
    # else:
    #     ot_query = OtRecord.query.filter_by(org_id=org_id)
    record = OtRecord.query.all()
    otrecord = []
    for ot in record:
        otrecord.append({
            'id': ot.id,
            'location': ot.location,
            'title': ot.compensation.role,
            'stafforg': ot.staff.personal_info.org.name,
            'businessHours': {
                'start': ot.start_datetime.strftime('%H:%M'),
                'end': ot.end_datetime.strftime('%H:%M'),
            }
        })
    return jsonify(otrecord)


@ot.route('/api/otrecords')
def get_events():
    all_events = []
    text_color = '#ffffff'
    bg_color = '#2b8c36'
    border_color = '#ffffff'
    otrecords = OtRecord.query.all()
    for record in otrecords:
        event = {
            'location': event.get('location', None),
            'title': record.staff.personal_info.fullname,
            'description': event.get('description', ''),
            'start': record.start_datetime.strftime('%H:%M'),
            'end': record.end_datetime.strftime('%H:%M'),
            'resourceId': otrecords.id,
            'status': otrecords.round,
            'borderColor': border_color,
            'backgroundColor': bg_color,
            'textColor': text_color,
            'id': record.id,
        }
        all_events.append(event)
    return jsonify(all_events)


@ot.route('/records/<int:event_id>', methods=['POST', 'GET'])
def show_event_detail(event_id=None):
    tz = pytz.timezone('Asia/Bangkok')
    if event_id:
        event = OtRecord.query.get(event_id)
        if event:
            event.start = event.start_date.astimezone(tz)
            event.end = event.end_date.astimezone(tz)
            return render_template(
                'ot/summary_chart.html', event=event)
    else:
        return 'No event ID specified.'


# @room.route('/events/<int:event_id>', methods=['POST', 'GET'])
# def show_event_detail(event_id=None):
#     tz = pytz.timezone('Asia/Bangkok')
#     if event_id:
#         event = RoomEvent.query.get(event_id)
#         if event:
#             event.start = event.start.astimezone(tz)
#             event.end = event.end.astimezone(tz)
#             return render_template(
#                 'scheduler/event_detail.html', event=event)
#     else:
#         return 'No event ID specified.'


@ot.route('/summary')
@login_required
def summary_chart():
    # ot_records = OtRecord.query.filter(OtRecord.canceled_at==None)\
    #                             .filter(OtRoundRequest.approval_at!=None).all()
    # records = [record.list_records() for record in ot_records]
    # records = []
    # for record in ot_records:
    #     ot = dict(
    #         record.compensation.role,
    #         record.staff.personal_info.fullname,
    #         record.start_datetime,
    #         record.end_datetime,
    #         record.total_hours or record.total_minutes
    #     )
    #     records.append(ot)
    # departments = Org.query.all()
    return render_template('ot/summary_chart.html')


@ot.route('/summary/each-person')
@login_required
def summary_each_person():
    ot_records = OtRecord.query.filter_by(staff=current_user) \
        .filter(OtRecord.canceled_at == None) \
        .filter(OtRecord.round_id != None) \
        .filter(OtRoundRequest.approval_at != None) \
        .filter(OtRoundRequest.verified_at != None).all()
    records = [record.list_records() for record in ot_records]
    return render_template('ot/summary_each_person.html', records=records)


@ot.route('/records/monthly')
@login_required
def view_monthly_records():
    return render_template('ot/staff_calendar.html')


@ot.route('/api/ot_records')
@login_required
def get_ot_records():
    cal_start = request.args.get('start')
    cal_end = request.args.get('end')
    if cal_start:
        cal_start = parser.isoparse(cal_start)
    if cal_end:
        cal_end = parser.isoparse(cal_end)
    all_records = []
    text_color = '#000000'
    for shift in OtShift.query.filter(OtShift.datetime.op('&&')
                                          (DateTimeRange(lower=cal_start,
                                                         upper=cal_end,
                                                         bounds='[]'))):
        for record in shift.records:
            if record.staff == current_user:
                start = localtz.localize(record.shift.datetime.lower)
                end = localtz.localize(record.shift.datetime.upper)

                rec = {
                    'title': u'{}'.format(record.compensation.ot_job_role),
                    'start': start.isoformat(),
                    'end': end.isoformat(),
                    'borderColor': '#000000',
                    'backgroundColor': record.shift.timeslot.color,
                    'textColor': text_color,
                    'id': record.id,
                }
                all_records.append(rec)
    return jsonify(all_records)


@ot.route('/api/ot_records/table')
@login_required
def get_ot_records_table(datetimefmt='%d-%m-%Y %-H:%M'):
    cal_start = request.args.get('start')
    cal_end = request.args.get('end')
    if cal_start:
        cal_start = parser.isoparse(cal_start)
    if cal_end:
        cal_end = parser.isoparse(cal_end)
    all_records = []
    login_pairs = []
    cal_daterange = DateTimeRange(lower=cal_start, upper=cal_end, bounds='[]')
    logins = StaffWorkLogin.query.filter(func.timezone('Asia/Bangkok', StaffWorkLogin.start_datetime) >= cal_start)\
              .filter(func.timezone('Asia/Bangkok', StaffWorkLogin.start_datetime) <= cal_end)\
              .filter_by(staff=current_user).order_by(StaffWorkLogin.id).all()
    i = 0
    while i < len(logins):
        if not logins[i].end_datetime:
            _pair = login_tuple(logins[i].start_datetime.astimezone(localtz),
                                logins[i+1].start_datetime.astimezone(localtz))
            i += 1
        else:
            _pair = login_tuple(logins[i].start_datetime.astimezone(localtz),
                                logins[i].end_datetime.astimezone(localtz))
        login_pairs.append(_pair)
        i += 1
    if cal_end and cal_start:
        for shift in OtShift.query.filter(OtShift.datetime.op('&&')(cal_daterange)):
            for record in shift.records:
                if record.staff == current_user:
                    shift_start = localtz.localize(record.shift.datetime.lower)
                    shift_end = localtz.localize(record.shift.datetime.upper)
                    overlapped_logins = []
                    overlapped_logouts = []
                    late_mins = []
                    payments = []
                    for _pair in login_pairs:
                        delta_start = _pair.start - shift_start
                        delta_minutes = divmod(delta_start.total_seconds(), 60)
                        if -90 < delta_minutes[0] < 40:
                            overlapped_logins.append(f'{_pair.start.strftime(datetimefmt)}')
                            overlapped_logouts.append(f'{_pair.end.strftime(datetimefmt)}')
                            late_mins.append(str(delta_minutes[0]))
                            if delta_minutes[0] > 0:
                                total_pay = record.calculate_total_pay(record.total_hours - delta_minutes[0])
                            else:
                                total_pay = record.calculate_total_pay(record.total_hours)
                            payments.append(total_pay)

                    rec = {
                        'title': u'{}'.format(record.compensation.ot_job_role),
                        'start': shift_start.isoformat(),
                        'end': shift_end.isoformat(),
                        'id': record.id,
                        'checkins': ','.join(overlapped_logins),
                        'checkouts': ','.join(overlapped_logouts),
                        'late': ','.join([str(m) for m in late_mins]),
                        'payment': ','.join([f'{p:.2f}' for p in payments])
                    }
                    all_records.append(rec)
    return jsonify({'data': all_records})
