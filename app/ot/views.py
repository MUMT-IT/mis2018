# -*- coding:utf-8 -*-
import wtforms
from flask_login import login_required, current_user
import pytz
import requests
import os

from werkzeug.utils import secure_filename

from models import *
from forms import *
from . import otbp as ot
from app.main import db, get_weekdays, app, func, StaffPersonalInfo, StaffWorkLogin
from app.models import Holidays, Org
from flask import jsonify, render_template, request, redirect, url_for, flash, session, send_from_directory
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive
from datetime import date, datetime

today = datetime.today()
if today.month >= 10:
    START_FISCAL_DATE = datetime(today.year, 10, 1)
    END_FISCAL_DATE = datetime(today.year + 1, 9, 30, 23, 59, 59, 0)
else:
    START_FISCAL_DATE = datetime(today.year - 1, 10, 1)
    END_FISCAL_DATE = datetime(today.year, 9, 30, 23, 59, 59, 0)

def convert_to_fiscal_year(date):
    if date.month in [10, 11, 12]:
        return date.year + 1
    else:
        return date.year

def get_start_end_date_for_fiscal_year(fiscal_year):
    '''Find start and end date from a given fiscal year.

    :param fiscal_year:  fiscal year
    :return: date
    '''
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


# TODO: สร้าง permission สำหรับคนที่สามารถใส่ข้อมูลเอกสารประกาศ rateOT
@ot.route('/')
@login_required
def index():
    return render_template('ot/index.html')


@ot.route('/announce')
@login_required
def announcement():
    compensations = OtCompensationRate.query.all()
    for compensation in compensations:
        if compensation.announcement.upload_file_url:
            upload_file = drive.CreateFile({'id': compensation.announcement.upload_file_url})
            upload_file.FetchMetadata()
            upload_file_url = upload_file.get('embedLink')
        else:
            upload_file_url = None
    return render_template('ot/announce.html', compensations=compensations, upload_file_url=upload_file_url)


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
    return render_template('ot/announce_compensation.html', form=form)


@ot.route('/document-approval')
@login_required
def document_approval_records():
    # TODO: filter valid document
    documents = OtDocumentApproval.query.all()
    for document in documents:
        if document.upload_file_url:
            upload_file = drive.CreateFile({'id': document.upload_file_url})
            upload_file.FetchMetadata()
            upload_file_url = upload_file.get('embedLink')
        else:
            upload_file_url = None
    return render_template('ot/document_approvals.html', documents=documents, upload_file_url=upload_file_url)


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
            #TODO: ถ้าไม่บันทึกไฟล์ใหม่(แก้ข้อมูลส่วนอื่น) ไฟล์เก่าจะหายไปจาก db แต่ไม่หายจาก gg
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
        #TODO: หาว่ามีrecord ไหนที่ใช้อยู่่และเชื่อม ประกาศนี้อยู่ ยังไม่อนุญาตให้ลบหรือไม่ หรือจะหาทางออกยังไง
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


@ot.route('/schedule')
@login_required
def schedule():
    # TODO: filter valid document
    documents = OtDocumentApproval.query.filter_by(org_id=current_user.personal_info.org.id).all()
    if documents:
        for document in documents:
            if document.upload_file_url:
                upload_file = drive.CreateFile({'id': document.upload_file_url})
                upload_file.FetchMetadata()
                upload_file_url = upload_file.get('embedLink')
            else:
                upload_file_url = None
        return render_template('ot/schedule_home.html', documents=documents, upload_file_url=upload_file_url)
    else:
        flash(u'หน่วยงานของท่านไม่มีอนุมัติในหลักการ กรุณาสร้างอนุมัติในหลักการก่อนทำการเบิกค่าตอบแทนล่วงเวลา', 'warning')
        return  render_template('ot/index.html')


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
                    start_t = form.start_time.data+':00'
                    end_t = form.end_time.data+':00'
                start_d = form.start_datetime.data.date()
                end_d = form.start_datetime.data.date()
                start_dt = '{} {}'.format(start_d, start_t)
                end_dt = '{} {}'.format(end_d, end_t)
                start_datetime = datetime.strptime(start_dt, '%Y-%m-%d %H:%M:%S')
                end_datetime = datetime.strptime(end_dt, '%Y-%m-%d %H:%M:%S')
                #TODO: check ว่าขาดเวลาเข้าหรือออกงานมั้ย
                #TODO: check ว่าเข้าช้าหรืออกก่อนเวลาที่จะเบิกมั้ย
                #TODO: เช็คว่าซ้ำกับอันอื่นมั้ย
                #for ot_records in OtRecord.query.all():
                #     if ot_records.staff_account_id==staff_id and ot_records.start_datetime == start_datetime or ot_records.start_datetime == end_datetime or \
                #             ot_records.end_datetime == end_datetime or ot_records.end_datetime == end_datetime:
                #             flash(u'{} มีข้อมูลการทำOT ในเวลานี้แล้ว กรุณาตรวจสอบเวลาใหม่อีกครั้ง'.format(
                #             ot_records.staff.personal_info.fullname), 'danger')
                record.start_datetime = start_datetime
                record.end_datetime = end_datetime
                record.created_staff = current_user
                record.org = current_user.personal_info.org
                record.staff_account_id = staff_id
                staff_name = StaffAccount.query.get(staff_id)
                if request.form.get('sub_role'):
                    record.sub_role = request.form.get('sub_role')
                flash(u'บันทึกการทำงานของ {} เรียบร้อยแล้ว'.format(staff_name.personal_info.fullname), 'success')
                db.session.add(record)
                db.session.commit()
            return redirect(url_for('ot.schedule'))
        else:
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('ot/schedule_add.html', form=form, document=document)


# @ot.route('/schedule/edit/<int:record_id>', methods=['GET', 'POST'])
# @login_required
# def edit_ot_record(record_id):
#     document = OtRecord.query.get(record_id)
#     EditOtRecordForm = edit_ot_record_factory([a.id for a in document.announce])
#     form = EditOtRecordForm(obj=document)
#     form.start_time.data = document.start_datetime.strftime('%H:%M')
#     form.end_time.data = document.end_datetime.strftime('%H:%M')
#     if request.method == 'POST':
#         if form.validate_on_submit():
#             form.populate_obj(document)
#             for staff_id in request.form.getlist("otworker"):
#                 record = OtRecord()
#                 form.populate_obj(record)
#                 if form.compensation.data.start_time:
#                     start_t = form.compensation.data.start_time
#                     end_t = form.compensation.data.end_time
#                 else:
#                     start_t = form.start_time.data+':00'
#                     end_t = form.end_time.data+':00'
#                 start_d = form.start_datetime.data.date()
#                 end_d = form.start_datetime.data.date()
#                 start_dt = '{} {}'.format(start_d, start_t)
#                 end_dt = '{} {}'.format(end_d, end_t)
#                 start_datetime = datetime.strptime(start_dt, '%Y-%m-%d %H:%M:%S')
#                 end_datetime = datetime.strptime(end_dt, '%Y-%m-%d %H:%M:%S')
#                 record.start_datetime = start_datetime
#                 record.end_datetime = end_datetime
#                 record.created_staff = current_user
#                 record.org = current_user.personal_info.org
#                 record.staff_account_id = staff_id
#                 staff_name = StaffAccount.query.get(staff_id)
#                 flash(u'บันทึกการทำงานของ {} เรียบร้อยแล้ว'.format(staff_name.personal_info.fullname), 'success')
#                 db.session.add(record)
#                 db.session.commit()
#             return redirect(url_for('ot.schedule'))
#         else:
#             flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
#     return render_template('ot/schedule_add.html', form=form, document=document)


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


# @ot.route('/schedule/summary')
# @login_required
# def summary_index():
#     depts = Org.query.all()
#     fiscal_year = request.args.get('fiscal_year')
#     if fiscal_year is None:
#         if today.month in [10, 11, 12]:
#             fiscal_year = today.year + 1
#         else:
#             fiscal_year = today.year
#         init_date = today
#     else:
#         fiscal_year = int(fiscal_year)
#         init_date = date(fiscal_year - 1, 10, 1)
#     if len(depts) == 0:
#         # return redirect(request.referrer)
#         return redirect(url_for("ot.schedule"))
#     curr_dept_id = request.args.get('curr_dept_id')
#     tab = request.args.get('tab', 'all')
#     if curr_dept_id is None:
#         curr_dept_id = depts[0].id
#     employees = StaffPersonalInfo.query.all()
#     ot_r = []
#     for emp in employees:
#         if tab == 'ot' or tab == 'all':
#             fiscal_years = OtRecord.query.distinct(func.date_part('YEAR', OtRecord.start_datetime))
#             fiscal_years = [convert_to_fiscal_year(ot.start_datetime) for ot in fiscal_years]
#             start_fiscal_date, end_fiscal_date = get_start_end_date_for_fiscal_year(fiscal_year)
#             for ot_record in OtRecord.query.filter_by(org_id=current_user.personal_info.org.id, staff=emp.staff_account)\
#                                 .filter(OtRecord.start_datetime.between(start_fiscal_date, end_fiscal_date)):
#                 text_color = '#ffffff'
#                 bg_color = '#FF785C'
#                 border_color = '#ffffff'
#                 ot_r.append({
#                         'id': ot_record.id,
#                         'start': ot_record.start_datetime,
#                         'end': ot_record.end_datetime,
#                         'title': u'{} {}'.format(emp.th_firstname, ot_record.compensation.role),
#                         'backgroundColor': bg_color,
#                         'borderColor': border_color,
#                         'textColor': text_color,
#                         'type': 'ot'
#                     })
#             all = ot_r
#     return render_template('ot/schedule_ot_summary.html',
#                            init_date=init_date,
#                            depts=depts, curr_dept_id=int(curr_dept_id),
#                            all=all, tab=tab, fiscal_years=fiscal_years, fiscal_year=fiscal_year)
#
#
# @ot.route('/schedule/summary/each-person')
# @login_required
# def summary_ot_each_person():
#     fiscal_year = request.args.get('fiscal_year')
#     if fiscal_year is None:
#         if today.month in [10, 11, 12]:
#             fiscal_year = today.year + 1
#         else:
#             fiscal_year = today.year
#         init_date = today
#     else:
#         fiscal_year = int(fiscal_year)
#         init_date = date(fiscal_year - 1, 10, 1)
#     tab = request.args.get('tab', 'all')
#     ot_r = []
#     fiscal_years = OtRecord.query.distinct(func.date_part('YEAR', OtRecord.start_datetime))
#     fiscal_years = [convert_to_fiscal_year(ot.start_datetime) for ot in fiscal_years]
#     start_fiscal_date, end_fiscal_date = get_start_end_date_for_fiscal_year(fiscal_year)
#     for ot_record in OtRecord.query.filter_by(staff_account_id=current_user.id).filter(OtRecord.start_datetime
#                                               .between(start_fiscal_date, end_fiscal_date)):
#         text_color = '#ffffff'
#         bg_color = '#2b8c36'
#         border_color = '#ffffff'
#         ot_r.append({
#                     'id': ot_record.id,
#                     'start': ot_record.start_datetime,
#                     'end': ot_record.end_datetime,
#                     'title': u'{} {}'.format(current_user.personal_info.th_firstname, ot_record.compensation.role),
#                     'backgroundColor': bg_color,
#                     'borderColor': border_color,
#                     'textColor': text_color,
#                     'type': 'ot'
#                 })
#         all = ot_r
#     return render_template('ot/schedule_summary_ot_each_person.html',
#                            init_date=init_date,
#                            all=all, tab=tab, fiscal_years=fiscal_years, fiscal_year=fiscal_year)
