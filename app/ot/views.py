# -*- coding:utf-8 -*-
from flask_login import login_required, current_user
import pytz
import requests
import os

from werkzeug.utils import secure_filename

from models import *
from forms import *
from . import otbp as ot
from app.main import db, get_weekdays, app
from app.models import Holidays, Org
from flask import jsonify, render_template, request, redirect, url_for, flash, session, send_from_directory
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive
from datetime import date, datetime

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


# TODO: สร้าง permission สำหรับคนที่สามารถใส่ข้อมูลเอกสารประกาศ rateOT
@ot.route('/index')
@login_required
def index():
    return render_template('ot/index.html')


@ot.route('/announce')
@login_required
def announcement():
    compensations = OtCompensationRate.query.all()
    return render_template('ot/announce.html', compensations=compensations)


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
            approval = OtDocumentApproval()
            form.populate_obj(approval)
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
                    approval.upload_file_url = file_drive['id']
                    approval.file_name = file_name
            approval.created_staff = current_user
            approval.org = current_user.personal_info.org
            db.session.add(approval)
            db.session.commit()
            flash(u'เพิ่มอนุมัติในหลักการเรียบร้อยแล้ว', 'success')
            return redirect(url_for('ot.document_approval_show_announcement', document_id=approval.id))
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
