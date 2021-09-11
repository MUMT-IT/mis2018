# -*- coding:utf-8 -*-
from flask_login import login_required, current_user
from pandas import read_excel, isna, DataFrame

from models import *
from . import staffbp as staff
from app.main import db, get_weekdays, mail, app
from app.models import Holidays, Org
from flask import jsonify, render_template, request, redirect, url_for, flash, session, send_from_directory
from datetime import date, datetime
from collections import defaultdict, namedtuple
import pytz
from sqlalchemy import and_, desc, func
from werkzeug.utils import secure_filename
from app.auth.views import line_bot_api
from linebot.models import TextSendMessage
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive
import requests
import os
from flask_mail import Message
from flask_admin import BaseView, expose
from itsdangerous import TimedJSONWebSignatureSerializer

from ..comhealth.views import allowed_file

gauth = GoogleAuth()
keyfile_dict = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
scopes = ['https://www.googleapis.com/auth/drive']
gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scopes)
drive = GoogleDrive(gauth)

tz = pytz.timezone('Asia/Bangkok')

# TODO: remove hardcoded annual quota soon
LEAVE_ANNUAL_QUOTA = 10

today = datetime.today()
if today.month >= 10:
    START_FISCAL_DATE = datetime(today.year, 10, 1)
    END_FISCAL_DATE = datetime(today.year + 1, 9, 30)
else:
    START_FISCAL_DATE = datetime(today.year - 1, 10, 1)
    END_FISCAL_DATE = datetime(today.year, 9, 30)


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


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


@staff.route('/')
@login_required
def index():
    return render_template('staff/index.html')


@staff.route('/person/<int:account_id>')
def show_person_info(account_id=None):
    if account_id:
        account = StaffAccount.query.get(account_id)
        return render_template('staff/info.html', person=account)


@staff.route('/api/list/')
@staff.route('/api/list/<int:account_id>')
def get_staff(account_id=None):
    data = []
    if not account_id:
        accounts = StaffAccount.query.all()
        for account in accounts:
            data.append({
                'email': account.email,
                'firstname': account.personal_info.en_firstname,
                'lastname': account.personal_info.en_lastname,
            })
    else:
        account = StaffAccount.query.get(account_id)
        if account:
            data = [{
                'email': account.email,
                'firstname': account.personal_info.en_firstname,
                'lastname': account.personal_info.en_lastname,
            }]
        else:
            return jsonify(data), 401
    return jsonify(data), 200


@staff.route('/set_password', methods=['GET', 'POST'])
def set_password():
    if request.method == 'POST':
        email = request.form.get('email', None)
        return email
    return render_template('staff/set_password.html')


@staff.route('/leave/info')
@login_required
def show_leave_info():
    Quota = namedtuple('quota', ['id', 'limit'])
    cum_days = defaultdict(float)
    quota_days = defaultdict(float)
    pending_days = defaultdict(float)
    for req in current_user.leave_requests:
        used_quota = current_user.personal_info.get_total_leaves(req.quota.id, tz.localize(START_FISCAL_DATE),
                                                                 tz.localize(END_FISCAL_DATE))
        leave_type = unicode(req.quota.leave_type)
        cum_days[leave_type] = used_quota
        pending_day = current_user.personal_info.get_total_pending_leaves_request \
            (req.quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
        pending_days[leave_type] = pending_day
    for quota in current_user.personal_info.employment.quota:
        delta = current_user.personal_info.get_employ_period()
        max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
        last_quota = StaffLeaveRemainQuota.query.filter(and_(StaffLeaveRemainQuota.leave_quota_id == quota.id,
                                                             StaffLeaveRemainQuota.year == (START_FISCAL_DATE.year - 1),
                                                             StaffLeaveRemainQuota.staff_account_id == current_user.id)).first()
        if delta.years > 0:
            if max_cum_quota:
                if last_quota:
                    last_year_quota = last_quota.last_year_quota
                else:
                    last_year_quota = 0
                before_get_max_quota = last_year_quota + LEAVE_ANNUAL_QUOTA
                quota_limit = max_cum_quota if max_cum_quota < before_get_max_quota else before_get_max_quota
            else:
                quota_limit = quota.max_per_year
        else:
            if delta.months > 5:
                quota_limit = quota.first_year
            else:
                quota_limit = quota.first_year if not quota.min_employed_months else 0
        quota_days[quota.leave_type.type_] = Quota(quota.id, quota_limit)
    approver = StaffLeaveApprover.query.filter_by(approver_account_id=current_user.id).first()
    return render_template('staff/leave_info.html',
                           line_profile=session.get('line_profile'),
                           cum_days=cum_days,
                           pending_days=pending_days,
                           quota_days=quota_days,
                           approver=approver)


@staff.route('/leave/request/quota/<int:quota_id>',
             methods=['GET', 'POST'])
@login_required
def request_for_leave(quota_id=None):
    if request.method == 'POST':
        form = request.form
        if quota_id:
            quota = StaffLeaveQuota.query.get(quota_id)
            if quota:
                start_t = "08:30"
                end_t = "16:30"
                start_d, end_d = form.get('dates').split(' - ')
                start_dt = '{} {}'.format(start_d, start_t)
                end_dt = '{} {}'.format(end_d, end_t)
                start_datetime = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
                end_datetime = datetime.strptime(end_dt, '%d/%m/%Y %H:%M')
                req = StaffLeaveRequest(
                    start_datetime=tz.localize(start_datetime),
                    end_datetime=tz.localize(end_datetime),
                    created_at=tz.localize(datetime.today())
                )
                if form.get('traveldates'):
                    start_travel_dt, end_travel_dt = form.get('traveldates').split(' - ')
                    start_travel_datetime = datetime.strptime(start_travel_dt, '%d/%m/%Y')
                    end_travel_datetime = datetime.strptime(end_travel_dt, '%d/%m/%Y')
                    if not (start_travel_datetime <= start_datetime and end_travel_datetime >= end_datetime):
                        flash(u'ช่วงเวลาเดินทาง ไม่ครอบคลุมวันที่ต้องการขอลา กรุณาตรวจสอบอีกครั้ง', "danger")
                        return redirect(request.referrer)
                    else:
                        req.start_travel_datetime = tz.localize(start_travel_datetime)
                        req.end_travel_datetime = tz.localize(end_travel_datetime)
                upload_file = request.files.get('document')
                after_hour = True if form.getlist("after_hour") else False
                if upload_file:
                    upload_file_name = secure_filename(upload_file.filename)
                    upload_file.save(upload_file_name)
                    file_drive = drive.CreateFile({'title': upload_file_name})
                    file_drive.SetContentFile(upload_file_name)
                    file_drive.Upload()
                    permission = file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
                    upload_file_id = file_drive['id']
                else:
                    upload_file_id = None
                if start_datetime.date() <= END_FISCAL_DATE.date() and end_datetime.date() > END_FISCAL_DATE.date():
                    flash(u'ไม่สามารถลาข้ามปีงบประมาณได้ กรุณาส่งคำร้องแยกกัน 2 ครั้ง โดยแยกตามปีงบประมาณ')
                    return redirect(request.referrer)
                delta = start_datetime.date() - datetime.today().date()
                if delta.days > 0 and not quota.leave_type.request_in_advance:
                    flash(u'ไม่สามารถลาล่วงหน้าได้ กรุณาลองใหม่')
                    return redirect(request.referrer)
                    # retrieve cum periods
                used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                                         tz.localize(END_FISCAL_DATE))
                pending_days = current_user.personal_info.get_total_pending_leaves_request \
                    (quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
                req_duration = get_weekdays(req)
                holidays = Holidays.query.filter(and_(Holidays.holiday_date >= start_datetime.date(),
                                                      Holidays.holiday_date <= end_datetime.date())).all()
                req_duration = req_duration - len(holidays)
                delta = current_user.personal_info.get_employ_period()
                if req_duration == 0:
                    flash(u'วันลาตรงกับวันหยุด')
                    return redirect(request.referrer)
                if quota.max_per_leave:
                    if req_duration >= quota.max_per_leave and upload_file_id is None:
                        flash(
                            u'ไม่สามารถลาป่วยเกินสามวันได้โดยไม่มีใบรับรองแพทย์ประกอบ')
                        return redirect(request.referrer)
                    else:
                        if delta.years > 0:
                            quota_limit = quota.max_per_year
                        else:
                            quota_limit = quota.first_year
                else:
                    max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
                    if delta.years > 0:
                        if max_cum_quota:
                            if start_datetime.date() > END_FISCAL_DATE.date():
                                quota_limit = LEAVE_ANNUAL_QUOTA
                            else:
                                last_quota = StaffLeaveRemainQuota.query.filter(and_
                                                                                (
                                                                                    StaffLeaveRemainQuota.leave_quota_id == quota.id,
                                                                                    StaffLeaveRemainQuota.year == (
                                                                                                START_FISCAL_DATE.year - 1),
                                                                                    StaffLeaveRemainQuota.staff_account_id == current_user.id)).first()
                                if last_quota:
                                    last_year_quota = last_quota.last_year_quota
                                else:
                                    last_year_quota = 0
                                before_cut_max_quota = last_year_quota + LEAVE_ANNUAL_QUOTA
                                quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                        else:
                            quota_limit = quota.max_per_year
                    else:
                        # skip min employ month of annual leave because leave req button doesn't appear
                        quota_limit = quota.first_year
                req.quota = quota
                req.staff = current_user
                req.reason = form.get('reason')
                req.country = form.get('country')
                req.contact_address = form.get('contact_addr')
                req.contact_phone = form.get('contact_phone')
                req.total_leave_days = req_duration
                req.upload_file_url = upload_file_id
                req.after_hour = after_hour
                if used_quota + pending_days + req_duration <= quota_limit:
                    if form.getlist('notified_by_line'):
                        req.notify_to_line = True
                    db.session.add(req)
                    db.session.commit()
                    mails = []
                    req_title = u'แจ้งการขออนุมัติ' + req.quota.leave_type.type_
                    req_msg = u'{} ขออนุมัติ{} ระหว่างวันที่ {} ถึงวันที่ {}\nคลิกที่ Link เพื่อดูรายละเอียดเพิ่มเติม {} ' \
                              u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
                        format(current_user.personal_info.fullname, req.quota.leave_type.type_,
                               start_datetime, end_datetime,
                               url_for("staff.pending_leave_approval", req_id=req.id, _external=True))
                    for approver in StaffLeaveApprover.query.filter_by(staff_account_id=current_user.id):
                        if approver.is_active:
                            if approver.notified_by_line and approver.account.line_id:
                                if os.environ["FLASK_ENV"] == "production":
                                    line_bot_api.push_message(to=approver.account.line_id,
                                                              messages=TextSendMessage(text=req_msg))
                                else:
                                    print(req_msg ,approver.account.id)
                            mails.append(approver.account.email + "@mahidol.ac.th")
                    if os.environ["FLASK_ENV"] == "production":
                        send_mail(mails, req_title, req_msg)
                    flash(u'ส่งคำขอของท่านเรียบร้อยแล้ว (The request has been sent.)', 'success')
                    return redirect(url_for('staff.request_for_leave_info', quota_id=quota_id))
                else:
                    flash(u'วันลาที่ต้องการลา เกินจำนวนวันลาคงเหลือ (The quota is exceeded.)', 'danger')
                    return redirect(request.referrer)
            else:
                return 'Error happened'
    else:
        quota = StaffLeaveQuota.query.get(quota_id)
        holidays = [h.tojson()['date'] for h in Holidays.query.all()]
        used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                                 tz.localize(END_FISCAL_DATE))
        delta = current_user.personal_info.get_employ_period()
        max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
        if delta.years > 0:
            if max_cum_quota:
                last_quota = StaffLeaveRemainQuota.query.filter(and_
                                                                (StaffLeaveRemainQuota.leave_quota_id == quota.id,
                                                                 StaffLeaveRemainQuota.year == (START_FISCAL_DATE.year-1),
                                                                 StaffLeaveRemainQuota.staff_account_id == current_user.id)).first()
                if last_quota:
                    last_year_quota = last_quota.last_year_quota
                else:
                    last_year_quota = 0
                before_cut_max_quota = last_year_quota + LEAVE_ANNUAL_QUOTA
                quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
            else:
                quota_limit = quota.max_per_year
        else:
            quota_limit = quota.first_year
        return render_template('staff/leave_request.html', errors={}, quota=quota, holidays=holidays,
                                                            used_quota=used_quota, quota_limit=quota_limit)


@staff.route('/leave/request/quota/period/<int:quota_id>', methods=["POST", "GET"])
@login_required
def request_for_leave_period(quota_id=None):
    if request.method == 'POST':
        form = request.form
        if quota_id:
            quota = StaffLeaveQuota.query.get(quota_id)
            if quota:
                # retrieve cum periods
                used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                                         tz.localize(END_FISCAL_DATE))
                pending_days = current_user.personal_info.get_total_pending_leaves_request \
                    (quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
                start_t, end_t = form.get('times').split(' - ')
                start_d, end_d = form.get('dates').split(' - ')
                start_dt = '{} {}'.format(start_d, start_t)
                end_dt = '{} {}'.format(end_d, end_t)
                start_datetime = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
                end_datetime = datetime.strptime(end_dt, '%d/%m/%Y %H:%M')
                delta = start_datetime.date() - datetime.today().date()
                if delta.days > 0 and not quota.leave_type.request_in_advance:
                    flash(u'ไม่สามารถลาล่วงหน้าได้ กรุณาลองใหม่')
                    return redirect(request.referrer)
                req = StaffLeaveRequest(
                    start_datetime=tz.localize(start_datetime),
                    end_datetime=tz.localize(end_datetime),
                    created_at=tz.localize(datetime.today())
                )
                req_duration = get_weekdays(req)
                if req_duration == 0:
                    flash(u'วันลาตรงกับเสาร์-อาทิตย์')
                    return redirect(request.referrer)
                holidays = Holidays.query.filter(Holidays.holiday_date == start_datetime.date()).all()
                req_duration = req_duration - len(holidays)
                if req_duration <= 0:
                    flash(u'วันลาตรงกับวันหยุด')
                    return redirect(request.referrer)
                delta = current_user.personal_info.get_employ_period()
                last_quota = StaffLeaveRemainQuota.query.filter(and_
                                                                (StaffLeaveRemainQuota.leave_quota_id == quota.id,
                                                                 StaffLeaveRemainQuota.year == (
                                                                             START_FISCAL_DATE.year - 1),
                                                                 StaffLeaveRemainQuota.staff_account_id == current_user.id)).first()
                max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
                if delta.years > 0:
                    if max_cum_quota:
                        if last_quota:
                            last_year_quota = last_quota.last_year_quota
                        else:
                            last_year_quota = 0
                        before_cut_max_quota = last_year_quota + LEAVE_ANNUAL_QUOTA
                        quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                    else:
                        quota_limit = quota.max_per_year
                else:
                    quota_limit = quota.first_year
                req.quota = quota
                req.staff = current_user
                req.reason = form.get('reason')
                req.contact_address = form.get('contact_addr')
                req.contact_phone = form.get('contact_phone')
                req.total_leave_days = req_duration
                if used_quota + pending_days + req_duration <= quota_limit:
                    if form.getlist('notified_by_line'):
                        req.notify_to_line = True
                    db.session.add(req)
                    db.session.commit()
                    mails = []
                    req_title = u'แจ้งการขออนุมัติ' + req.quota.leave_type.type_
                    req_msg = u'{} ขออนุมัติ{} ระหว่างวันที่ {} ถึงวันที่ {}\nคลิกที่ Link เพื่อดูรายละเอียดเพิ่มเติม {} ' \
                              u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
                        format(current_user.personal_info.fullname, req.quota.leave_type.type_,
                               start_datetime, end_datetime,
                               url_for("staff.pending_leave_approval", req_id=req.id, _external=True))
                    for approver in StaffLeaveApprover.query.filter_by(staff_account_id=current_user.id):
                        if approver.is_active:
                            if approver.notified_by_line and approver.account.line_id:
                                if os.environ["FLASK_ENV"] == "production":
                                    line_bot_api.push_message(to=approver.account.line_id,
                                                              messages=TextSendMessage(text=req_msg))
                                else:
                                    print(req_msg, approver.account.id)
                            mails.append(approver.account.email + "@mahidol.ac.th")
                    if os.environ["FLASK_ENV"] == "production":
                        send_mail(mails, req_title, req_msg)
                    flash(u'ส่งคำขอของท่านเรียบร้อยแล้ว')
                    return redirect(url_for('staff.request_for_leave_info', quota_id=quota_id))
                else:
                    flash(u'วันลาที่ต้องการลา เกินจำนวนวันลาคงเหลือ')
                    return redirect(request.referrer)
            else:
                return 'Error happened'
    else:
        quota = StaffLeaveQuota.query.get(quota_id)
        holidays = [h.tojson()['date'] for h in Holidays.query.all()]
        used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                                 tz.localize(END_FISCAL_DATE))
        delta = current_user.personal_info.get_employ_period()
        max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
        if delta.years > 0:
            if max_cum_quota:
                last_quota = StaffLeaveRemainQuota.query.filter(and_
                                                                (StaffLeaveRemainQuota.leave_quota_id == quota.id,
                                                                 StaffLeaveRemainQuota.year == (START_FISCAL_DATE.year-1),
                                                                 StaffLeaveRemainQuota.staff_account_id == current_user.id)).first()
                if last_quota:
                    last_year_quota = last_quota.last_year_quota
                else:
                    last_year_quota = 0
                before_cut_max_quota = last_year_quota + LEAVE_ANNUAL_QUOTA
                quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
            else:
                quota_limit = quota.max_per_year
        else:
            quota_limit = quota.first_year
        return render_template('staff/leave_request_period.html', errors={}, quota=quota, holidays=holidays,
                                                                  used_quota=used_quota, quota_limit=quota_limit)


@staff.route('/leave/request/info/<int:quota_id>')
@login_required
def request_for_leave_info(quota_id=None):
    quota = StaffLeaveQuota.query.get(quota_id)
    leaves = []
    fiscal_years = set()
    for leave in current_user.leave_requests:
        if leave.start_datetime >= tz.localize(START_FISCAL_DATE) and leave.end_datetime <= tz.localize(
                END_FISCAL_DATE):
            if leave.quota == quota:
                leaves.append(leave)
        if leave.start_datetime.month in [10, 11, 12]:
            fiscal_years.add(leave.start_datetime.year + 1)
        else:
            fiscal_years.add(leave.start_datetime.year)
    used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                             tz.localize(END_FISCAL_DATE))

    delta = current_user.personal_info.get_employ_period()
    max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
    if delta.years > 0:
        if max_cum_quota:
            last_quota = StaffLeaveRemainQuota.query.filter(and_
                                                            (StaffLeaveRemainQuota.leave_quota_id == quota.id,
                                                             StaffLeaveRemainQuota.year == (START_FISCAL_DATE.year - 1),
                                                             StaffLeaveRemainQuota.staff_account_id == current_user.id)).first()
            if last_quota:
                last_year_quota = last_quota.last_year_quota
            else:
                last_year_quota = 0
            before_cut_max_quota = last_year_quota + LEAVE_ANNUAL_QUOTA
            quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
        else:
            quota_limit = quota.max_per_year
    else:
        quota_limit = quota.first_year
    return render_template('staff/request_info.html', leaves=leaves, quota=quota,
                           fiscal_years=fiscal_years, quota_limit=quota_limit, used_quota=used_quota)


@staff.route('/leave/request/info/<int:quota_id>/deleted')
@login_required
def leave_info_deleted_records(quota_id=None):
    quota = StaffLeaveQuota.query.get(quota_id)
    leaves = []
    fiscal_years = set()
    for leave in current_user.leave_requests:
        if leave.start_datetime >= tz.localize(START_FISCAL_DATE) and leave.end_datetime <= tz.localize(
                END_FISCAL_DATE) and leave.cancelled_at:
            if leave.quota == quota:
                leaves.append(leave)
        if leave.start_datetime.month in [10, 11, 12]:
            fiscal_years.add(leave.start_datetime.year + 1)
        else:
            fiscal_years.add(leave.start_datetime.year)
    return render_template('staff/leave_request_deleted_records.html', leaves=leaves, quota=quota,
                           fiscal_years=fiscal_years)


@staff.route('/leave/request/info/<int:quota_id>/others_year/<int:fiscal_year>')
@login_required
def request_for_leave_info_others_fiscal(quota_id=None, fiscal_year=None):
    quota = StaffLeaveQuota.query.get(quota_id)
    leaves = []
    for leave in current_user.leave_requests:
        if leave.start_datetime.month in [10, 11, 12]:
            fiscal_years = leave.start_datetime.year + 1
        else:
            fiscal_years = leave.start_datetime.year

        if fiscal_year == fiscal_years:
            if leave.quota == quota:
                leaves.append(leave)
                fiscal_year = fiscal_year

    requester = StaffLeaveApprover.query.filter_by(staff_account_id=current_user.id)

    return render_template('staff/leave_info_others_fiscal_year.html', leaves=leaves, reqester=requester, quota=quota,
                           fiscal_year=fiscal_year)


@staff.route('/leave/request/edit/<int:req_id>',
             methods=['GET', 'POST'])
@login_required
def edit_leave_request(req_id=None):
    req = StaffLeaveRequest.query.get(req_id)
    if req.total_leave_days == 0.5:
        return redirect(url_for("staff.edit_leave_request_period", req_id=req_id))
    if request.method == 'POST':
        quota = req.quota
        if quota:
            start_t = "08:30"
            end_t = "16:30"
            start_d, end_d = request.form.get('dates').split(' - ')
            start_dt = '{} {}'.format(start_d, start_t)
            end_dt = '{} {}'.format(end_d, end_t)
            start_datetime = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
            end_datetime = datetime.strptime(end_dt, '%d/%m/%Y %H:%M')
            req.start_datetime = tz.localize(start_datetime)
            req.end_datetime = tz.localize(end_datetime)
            if start_datetime <= END_FISCAL_DATE and end_datetime > END_FISCAL_DATE:
                flash(u'ไม่สามารถลาข้ามปีงบประมาณได้ กรุณาส่งคำร้องแยกกัน 2 ครั้ง โดยแยกตามปีงบประมาณ')
                return redirect(request.referrer)
            if request.form.get('traveldates'):
                start_travel_dt, end_travel_dt = request.form.get('traveldates').split(' - ')
                start_travel_datetime = datetime.strptime(start_travel_dt, '%d/%m/%Y')
                end_travel_datetime = datetime.strptime(end_travel_dt, '%d/%m/%Y')
                if not (start_travel_datetime <= start_datetime and end_travel_datetime >= end_datetime):
                    flash(u'ช่วงเวลาเดินทาง ไม่ครอบคลุมวันที่ต้องการขอลา กรุณาตรวจสอบอีกครั้ง', "danger")
                    return redirect(request.referrer)
                else:
                    req.start_travel_datetime = tz.localize(start_travel_datetime)
                    req.end_travel_datetime = tz.localize(end_travel_datetime)
            else:
                req.start_travel_datetime = None
                req.end_travel_datetime = None
            upload_file = request.files.get('document')
            after_hour = True if request.form.getlist("after_hour") else False
            if upload_file:
                upload_file_name = secure_filename(upload_file.filename)
                upload_file.save(upload_file_name)
                file_drive = drive.CreateFile({'title': upload_file_name})
                file_drive.SetContentFile(upload_file_name)
                file_drive.Upload()
                permission = file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
                upload_file_id = file_drive['id']
            else:
                if req.upload_file_url:
                    upload_file_id = req.upload_file_url
                else:
                    upload_file_id = None
            delta = start_datetime.date() - datetime.today().date()
            if delta.days > 0 and not quota.leave_type.request_in_advance:
                flash(u'ไม่สามารถลาล่วงหน้าได้ กรุณาลองใหม่')
                return redirect(request.referrer)
                # retrieve cum periods
            used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                                     tz.localize(END_FISCAL_DATE))
            pending_days = current_user.personal_info.get_total_pending_leaves_request \
                (quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
            req_duration = get_weekdays(req)
            holidays = Holidays.query.filter(and_(Holidays.holiday_date >= start_datetime,
                                                  Holidays.holiday_date <= end_datetime)).all()
            req_duration = req_duration - len(holidays)
            delta = current_user.personal_info.get_employ_period()
            if req_duration == 0:
                flash(u'วันลาตรงกับวันหยุด')
                return redirect(request.referrer)
            if quota.max_per_leave:
                if req_duration > quota.max_per_leave and upload_file_id is None:
                    flash(
                        u'ไม่สามารถลาป่วยเกินสามวันได้โดยไม่มีใบรับรองแพทย์ประกอบ')
                    return redirect(request.referrer)
                else:
                    if delta.years > 0:
                        quota_limit = quota.max_per_year
                    else:
                        quota_limit = quota.first_year
            else:
                max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
                if delta.years > 0:
                    if max_cum_quota:
                        if start_datetime > END_FISCAL_DATE:
                            quota_limit = LEAVE_ANNUAL_QUOTA
                        else:
                            last_quota = StaffLeaveRemainQuota.query.filter(and_
                                                                            (
                                                                                StaffLeaveRemainQuota.leave_quota_id == quota.id,
                                                                                StaffLeaveRemainQuota.year == (
                                                                                            START_FISCAL_DATE.year - 1),
                                                                                StaffLeaveRemainQuota.staff_account_id == current_user.id)).first()
                            if last_quota:
                                last_year_quota = last_quota.last_year_quota
                            else:
                                last_year_quota = 0
                            before_cut_max_quota = last_year_quota + LEAVE_ANNUAL_QUOTA
                            quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                    else:
                        quota_limit = quota.max_per_year
                else:
                    quota_limit = quota.first_year
            req.reason = request.form.get('reason')
            req.country = request.form.get('country')
            req.contact_address = request.form.get('contact_addr'),
            req.contact_phone = request.form.get('contact_phone'),
            req.total_leave_days = req_duration
            req.upload_file_url = upload_file_id
            req.after_hour = after_hour
            if used_quota + pending_days + req_duration <= quota_limit:
                req.notify_to_line = True if request.form.getlist("notified_by_line") else False
                db.session.add(req)
                db.session.commit()
                flash(u'แก้ไขคำขอของท่านเรียบร้อยแล้ว')
                return redirect(url_for('staff.request_for_leave_info', quota_id=req.leave_quota_id))
            else:
                flash(u'วันลาที่ต้องการลา เกินจำนวนวันลาคงเหลือ')
                return redirect(request.referrer)
        else:
            return 'Error happened'
    selected_dates = [req.start_datetime, req.end_datetime]
    travel_dates = [req.start_travel_datetime, req.end_travel_datetime]
    holidays = [h.tojson()['date'] for h in Holidays.query.all()]
    if req.upload_file_url:
        upload_file = drive.CreateFile({'id': req.upload_file_url})
        upload_file.FetchMetadata()
        upload_file_url = upload_file.get('embedLink')
    else:
        upload_file_url = None
    return render_template('staff/edit_leave_request.html', selected_dates=selected_dates, req=req, errors={},
                           travel_dates=travel_dates, holidays=holidays, upload_file_url=upload_file_url)


@staff.route('/leave/request/edit/period/<int:req_id>',
             methods=['GET', 'POST'])
@login_required
def edit_leave_request_period(req_id=None):
    req = StaffLeaveRequest.query.get(req_id)
    if request.method == 'POST':
        quota = req.quota
        if quota:
            used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                                     tz.localize(END_FISCAL_DATE))
            pending_days = current_user.personal_info.get_total_pending_leaves_request \
                (quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
            start_t, end_t = request.form.get('times').split(' - ')
            start_d, end_d = request.form.get('dates').split(' - ')
            start_dt = '{} {}'.format(start_d, start_t)
            end_dt = '{} {}'.format(end_d, end_t)
            start_datetime = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
            end_datetime = datetime.strptime(end_dt, '%d/%m/%Y %H:%M')
            delta = start_datetime - datetime.today()
            if delta.days > 0 and not quota.leave_type.request_in_advance:
                flash(u'ไม่สามารถลาล่วงหน้าได้ กรุณาลองใหม่')
                return redirect(request.referrer)
            holidays = Holidays.query.filter(Holidays.holiday_date == start_datetime.date()).all()
            if len(holidays) > 0:
                flash(u'วันลาตรงกับวันหยุด')
                return redirect(request.referrer)
            req.start_datetime = tz.localize(start_datetime)
            req.end_datetime = tz.localize(end_datetime)
            req_duration = get_weekdays(req)
            if req_duration == 0:
                flash(u'วันลาตรงกับเสาร์-อาทิตย์')
                return redirect(request.referrer)
            # if duration not exceeds quota
            delta = current_user.personal_info.get_employ_period()
            last_quota = StaffLeaveRemainQuota.query.filter(and_
                                                            (StaffLeaveRemainQuota.leave_quota_id == quota.id,
                                                             StaffLeaveRemainQuota.year == (START_FISCAL_DATE.year - 1),
                                                             StaffLeaveRemainQuota.staff_account_id == current_user.id)).first()
            max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
            if delta.years > 0:
                if max_cum_quota:
                    if last_quota:
                        last_year_quota = last_quota.last_year_quota
                    else:
                        last_year_quota = 0
                    before_cut_max_quota = last_year_quota + LEAVE_ANNUAL_QUOTA
                    quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                else:
                    quota_limit = quota.max_per_year
            else:
                quota_limit = quota.first_year
            req.reason = request.form.get('reason')
            req.contact_address = request.form.get('contact_addr')
            req.contact_phone = request.form.get('contact_phone')
            req.total_leave_days = req_duration
            if used_quota + pending_days + req_duration <= quota_limit:
                if request.form.getlist('notified_by_line'):
                    req.notify_to_line = True
                db.session.add(req)
                db.session.commit()
                flash(u'แก้ไขคำขอของท่านเรียบร้อยแล้ว')
                return redirect(url_for('staff.request_for_leave_info', quota_id=req.leave_quota_id))
            else:
                flash(u'วันลาที่ต้องการลา เกินจำนวนวันลาคงเหลือ')
                return redirect(request.referrer)
        else:
            return 'Error happened'

    selected_dates = req.start_datetime

    return render_template('staff/edit_leave_request_period.html', req=req, selected_dates=selected_dates, errors={})


@staff.route('/leave/requests/approval/info')
@login_required
def show_leave_approval_info():
    leave_types = StaffLeaveType.query.all()
    requesters = StaffLeaveApprover.query.filter_by(approver_account_id=current_user.id).all()
    requester_cum_periods = {}
    for requester in requesters:
        cum_periods = defaultdict(float)
        for leave_request in requester.requester.leave_requests:
            if leave_request.cancelled_at is None and leave_request.get_approved:
                if leave_request.start_datetime.date() >= START_FISCAL_DATE.date() and leave_request.end_datetime.date() \
                        <= END_FISCAL_DATE.date():
                    cum_periods[leave_request.quota.leave_type] += leave_request.total_leave_days
        requester_cum_periods[requester] = cum_periods
    approver = StaffLeaveApprover.query.filter_by(approver_account_id=current_user.id).first()
    if approver:
        line_notified = approver.notified_by_line
    else:
        return redirect(url_for('staff.show_leave_info'))
    today = datetime.today().date()
    return render_template('staff/leave_request_approval_info.html',
                           requesters=requesters,
                           approver=approver,
                           requester_cum_periods=requester_cum_periods,
                           leave_types=leave_types, line_notified=line_notified, today=today)


@staff.route('/leave/requests/approval/info/download')
@login_required
def show_leave_approval_info_download():
    requesters = StaffLeaveApprover.query.filter_by(approver_account_id=current_user.id, is_active=True).all()
    requester_cum_periods = {}
    records = []
    for requester in requesters:
        cum_periods = defaultdict(float)
        for leave_request in requester.requester.leave_requests:
            if leave_request.cancelled_at is None and leave_request.get_approved:
                if leave_request.start_datetime.date() >= START_FISCAL_DATE.date() and leave_request.end_datetime.date() \
                        <= END_FISCAL_DATE.date():
                    cum_periods[u"{}".format(leave_request.quota.leave_type)] += leave_request.total_leave_days
                    records.append({
                        'name': requester.requester.personal_info.fullname,
                        'leave_type': u"{}".format(leave_request.quota.leave_type)
                    })
        requester_cum_periods[requester] = cum_periods
    df = DataFrame(records)
    summary = df.pivot_table(index='name', columns='leave_type', aggfunc=len, fill_value=0)
    summary.to_excel('leave_summary.xlsx')
    flash(u'ดาวน์โหลดไฟล์เรียบร้อยแล้ว ชื่อไฟล์ leave_summary.xlsx')
    return redirect(url_for('staff.show_leave_approval_info'))


@staff.route('/api/leave/requests/linenotified')
@login_required
def update_line_notification():
    notified = request.args.get("notified")
    if notified:
        is_notified = True if notified == "true" else False
        for approver in StaffLeaveApprover.query.filter_by(approver_account_id=current_user.id):
            approver.notified_by_line = is_notified
            db.session.add(approver)
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "failed"})


@staff.route('/leave/requests/approval/pending/<int:req_id>')
@login_required
def pending_leave_approval(req_id):
    req = StaffLeaveRequest.query.get(req_id)
    approver = StaffLeaveApprover.query.filter_by(account=current_user, requester=req.staff).first()
    approve = StaffLeaveApproval.query.filter_by(approver=approver, request=req).first()
    approvers = StaffLeaveApproval.query.filter_by(request_id=req_id)
    if approve:
        return render_template('staff/leave_approve_status.html', approve=approve, req=req)
    if req.upload_file_url:
        upload_file = drive.CreateFile({'id': req.upload_file_url})
        upload_file.FetchMetadata()
        upload_file_url = upload_file.get('embedLink')
    else:
        upload_file_url = None
    used_quota = req.staff.personal_info.get_total_leaves(req.quota.id, tz.localize(START_FISCAL_DATE),
                                                             tz.localize(END_FISCAL_DATE))
    last_req = None
    for last_req in StaffLeaveRequest.query.filter_by(staff_account_id=req.staff_account_id, cancelled_at=None).\
                                                order_by(desc(StaffLeaveRequest.start_datetime)):
        if last_req.get_approved:
            break

    return render_template('staff/leave_request_pending_approval.html', req=req, approver=approver, approvers=approvers,
                           upload_file_url=upload_file_url, used_quota=used_quota, last_req=last_req)


@staff.route('/leave/requests/approve/<int:req_id>/<int:approver_id>', methods=['GET', 'POST'])
@login_required
def leave_approve(req_id, approver_id):
    approved = request.args.get("approved")
    if request.method == 'POST':
        comment = request.form.get('approval_comment')
        approval = StaffLeaveApproval(
            request_id=req_id,
            approver_id=approver_id,
            is_approved=True if approved == 'yes' else False,
            updated_at=tz.localize(datetime.today()),
            approval_comment=comment if comment != "" else None
        )
        db.session.add(approval)
        db.session.commit()
        flash(u'อนุมัติการลาให้บุคลากรในสังกัดเรียบร้อย หากเปิดบน Line สามารถปิดหน้าต่างนี้ได้ทันที')
        req = StaffLeaveRequest.query.get(req_id)
        if approval.is_approved is True:
            approve_msg = u'การขออนุมัติ{} ระหว่างวันที่ {} ถึงวันที่ {} ได้รับการอนุมัติโดย {} เรียบร้อยแล้ว รายละเอียดเพิ่มเติม {}' \
                          u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(req.quota.leave_type.type_,
                        req.start_datetime,req.end_datetime,
                        current_user.personal_info.fullname,
                        url_for( "staff.show_leave_approval",req_id=req_id,_external=True))
        else:
            approve_msg = u'การขออนุมัติ{} ระหว่างวันที่ {} ถึงวันที่ {} ไม่ได้รับการอนุมัติโดย {} รายละเอียดเพิ่มเติม {}' \
                          u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(req.quota.leave_type.type_,
                          req.start_datetime,req.end_datetime,
                          current_user.personal_info.fullname,
                          url_for( "staff.show_leave_approval",req_id=req_id,_external=True))

        if req.notify_to_line and req.staff.line_id:
            if os.environ["FLASK_ENV"] == "production":
                line_bot_api.push_message(to=req.staff.line_id, messages=TextSendMessage(text=approve_msg))
            else:
                print(approve_msg, req.staff.id)
        approve_title = u'แจ้งสถานะการอนุมัติ' + req.quota.leave_type.type_
        if os.environ["FLASK_ENV"] == "production":
            send_mail([req.staff.email + "@mahidol.ac.th"], approve_title, approve_msg)
        return redirect(url_for('staff.show_leave_approval_info'))
    if approved is not None:
        return render_template('staff/leave_request_approval_comment.html')
    else:
        return redirect(url_for('staff.pending_leave_approval', req_id=req_id))


@staff.route('/leave/requests/<int:req_id>/approvals')
@login_required
def show_leave_approval(req_id):
    req = StaffLeaveRequest.query.get(req_id)
    approvers = StaffLeaveApprover.query.filter_by(staff_account_id=current_user.id)
    return render_template('staff/leave_approval_status.html', req=req, approvers=approvers)


@staff.route('/leave/requests/<int:req_id>/cancel-approved')
@login_required
def request_cancel_leave_request(req_id):
    req = StaffLeaveRequest.query.get(req_id)
    if req.get_last_cancel_request_from_now > 1 or not req.last_cancel_requested_at:
        req.last_cancel_requested_at = datetime.now(tz)
        db.session.add(req)
        db.session.commit()
        for approval in StaffLeaveApproval.query.filter_by(request_id=req_id):
            serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'), expires_in=86400)
            token = serializer.dumps({'approver_id': approval.approver_id, 'req_id': req.id})
            req_to_cancel_msg = u'{} ยื่นคำขอยกเลิก {} วันที่ {} ถึง {}\nคลิกที่ Link {} เพื่อยกเลิกการลา' \
                                u'\n\n\n หน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
                format(current_user.personal_info.fullname, req.quota.leave_type.type_,
                       req.start_datetime, req.end_datetime, url_for("staff.info_request_cancel_leave_request",
                                                                    token=token, _external=True))
            if approval.approver.notified_by_line and approval.approver.account.line_id:
                if os.environ["FLASK_ENV"] == "production":
                    line_bot_api.push_message(to=approval.approver.account.line_id,messages=TextSendMessage(text=req_to_cancel_msg))
                else:
                    print(req_to_cancel_msg, approval.approver.account.id)

            req_title = u'แจ้งการขอยกเลิก' + req.quota.leave_type.type_
            if os.environ["FLASK_ENV"] == "production":
                send_mail([approval.approver.account.email + "@mahidol.ac.th"], req_title, req_to_cancel_msg)
            else:
                print(req_to_cancel_msg)
        flash(u'ส่งคำขอยกเลิกการลาของท่านเรียบร้อยแล้ว', 'success')
        return redirect(url_for('staff.request_for_leave_info', quota_id=req.leave_quota_id))
    else:
        flash(u'ไม่สามารถส่งคำขอซ้ำภายใน 1 วันได้', 'warning')
    return redirect(url_for('staff.show_leave_info'))


@staff.route('/leave/requests/cancel-approved/info')
def info_request_cancel_leave_request():
    token = request.args.get('token')
    serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'))
    try:
        token_data = serializer.loads(token)
    except:
        return u'Bad JSON Web token. You need a valid token to cancelled leave request. รหัสสำหรับยกเลิกการลา หมดอายุหรือไม่ถูกต้อง'
    req_id = token_data.get("req_id")
    approver_id = token_data.get("approver_id")
    req = StaffLeaveRequest.query.get(req_id)
    approval = StaffLeaveApproval.query.filter_by(approver_id=approver_id).first()
    approvers = StaffLeaveApproval.query.filter_by(request_id=req_id)
    return render_template('staff/leave_request_cancel_request.html', req=req, approval=approval, approvers=approvers)


@staff.route('/leave/requests/<int:req_id>/cancel/by/<int:cancelled_account_id>')
def approver_cancel_leave_request(req_id, cancelled_account_id):
    req = StaffLeaveRequest.query.get(req_id)
    req.cancelled_at = tz.localize(datetime.today())
    req.cancelled_account_id = cancelled_account_id
    db.session.add(req)
    db.session.commit()
    cancelled_msg = u'คำขออนุมัติ{} วันที่ใน {} ถึง {} ถูกยกเลิกโดย {} เรียบร้อยแล้ว' \
                    u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(req.quota.leave_type.type_,
                                                                                          req.start_datetime,
                                                                                          req.end_datetime,
                                                                                          req.cancelled_by.personal_info
                                                                                          ,_external=True)
    if req.notify_to_line and req.staff.line_id:
        if os.environ["FLASK_ENV"] == "production":
            line_bot_api.push_message(to=req.staff.line_id, messages=TextSendMessage(text=cancelled_msg))
        else:
            print(cancelled_msg, req.staff.id)
    cancelled_title = u'แจ้งยกเลิกการขอ' + req.quota.leave_type.type_ + u'โดยผู้บังคับบัญชา'
    if os.environ["FLASK_ENV"] == "production":
        send_mail([req.staff.email + "@mahidol.ac.th"], cancelled_title, cancelled_msg)
    return redirect(request.referrer)


@staff.route('/leave/requests/<int:req_id>/cancel/<int:cancelled_account_id>')
@login_required
def cancel_leave_request(req_id, cancelled_account_id):
    req = StaffLeaveRequest.query.get(req_id)
    req.cancelled_at = tz.localize(datetime.today())
    req.cancelled_account_id = cancelled_account_id
    db.session.add(req)
    db.session.commit()
    cancelled_msg = u'การขออนุมัติ{} วันที่ใน {} ถึง {} ถูกยกเลิกโดย {} เรียบร้อยแล้ว' \
                    u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(req.quota.leave_type.type_,
                                                                                          req.start_datetime,
                                                                                          req.end_datetime,
                                                                                          current_user.personal_info.fullname
                                                                                          , _external=True)
    if req.notify_to_line and req.staff.line_id:
        if os.environ["FLASK_ENV"] == "production":
            line_bot_api.push_message(to=req.staff.line_id, messages=TextSendMessage(text=cancelled_msg))
        else:
            print(cancelled_msg, req.staff.id)
    cancelled_title = u'แจ้งยกเลิกการขอ' + req.quota.leave_type.type_
    if os.environ["FLASK_ENV"] == "production":
        send_mail([req.staff.email + "@mahidol.ac.th"], cancelled_title, cancelled_msg)
    return redirect(request.referrer)


@staff.route('/leave/requests/approved/info/<int:requester_id>')
@login_required
def show_leave_approval_info_each_person(requester_id):
    requester = StaffLeaveRequest.query.filter_by(staff_account_id=requester_id).all()
    return render_template('staff/leave_request_approved_each_person.html', requester=requester)


@staff.route('leave/<int:request_id>/record/info')
@login_required
def record_each_request_leave_request(request_id):
    req = StaffLeaveRequest.query.get(request_id)
    approvers = StaffLeaveApproval.query.filter_by(request_id=request_id)
    if req.upload_file_url:
        upload_file = drive.CreateFile({'id': req.upload_file_url})
        upload_file.FetchMetadata()
        upload_file_url = upload_file.get('embedLink')
    else:
        upload_file_url = None
    print (u"get last cancel {}".format(req.get_last_cancel_request_from_now))
    return render_template('staff/leave_record_info.html', req=req, approvers=approvers, upload_file_url=upload_file_url)


@staff.route('/leave/requests/search')
@login_required
def search_leave_request_info():
    reqs = StaffLeaveRequest.query.all()
    record_schema = StaffLeaveRequestSchema(many=True)
    return jsonify(record_schema.dump(reqs).data)


@staff.route('/leave/requests')
@login_required
def leave_request_info():
    return render_template('staff/leave_request_info.html')


@staff.route('/wfh/requests/search')
@login_required
def search_wfh_request_info():
    reqs = StaffWorkFromHomeRequest.query.all()
    record_schema = StaffWorkFromHomeRequestSchema(many=True)
    return jsonify(record_schema.dump(reqs).data)


@staff.route('/wfh/requests')
@login_required
def wfh_request_info():
    return render_template('staff/wfh_list.html')


@staff.route('/leave/requests/result-by-date',
             methods=['GET', 'POST'])
@login_required
def leave_request_result_by_date():
    if request.method == 'POST':
        form = request.form

        start_dt, end_dt = form.get('dates').split(' - ')
        start_date = datetime.strptime(start_dt, '%d/%m/%Y')
        end_date = datetime.strptime(end_dt, '%d/%m/%Y')

        leaves = StaffLeaveRequest.query.filter(and_(StaffLeaveRequest.start_datetime >= start_date,
                                                     StaffLeaveRequest.end_datetime <= end_date))
        return render_template('staff/leave_request_result_by_date.html', leaves=leaves,
                               start_date=start_date.date(), end_date=end_date.date())
    else:
        return render_template('staff/leave_request_info_by_date.html')


@staff.route('/leave/requests/result-by-person',
             methods=['GET', 'POST'])
@login_required
def leave_request_result_by_person():
    org_id = request.args.get('deptid')
    fiscal_year = request.args.get('fiscal_year')
    if fiscal_year is not None:
        start_date, end_date = get_start_end_date_for_fiscal_year(int(fiscal_year))
    else:
        start_date = None
        end_date = None
    years = set()
    leaves_list = []
    departments = Org.query.all()
    leave_types = [t.type_ for t in StaffLeaveType.query.all()]
    if org_id is None:
        account_query = StaffAccount.query.all()
    else:
        account_query = StaffAccount.query.filter(StaffAccount.personal_info.has(org_id=org_id))

    for account in account_query:
        record = {}
        record["staffid"] = account.id
        record["fullname"] = account.personal_info.fullname
        record["total"] = 0
        record["pending"] = 0
        if account.personal_info.org:
            record["org"] = account.personal_info.org.name
        else:
            record["org"] = ""
        for leave_type in leave_types:
            record[leave_type] = 0
        for req in account.leave_requests:
            if not req.cancelled_at:
                if req.get_approved:
                    years.add(req.start_datetime.year)
                    if start_date and end_date:
                        if req.start_datetime.date() < start_date or req.start_datetime.date() > end_date:
                            continue
                    leave_type = req.quota.leave_type.type_
                    record[leave_type] += req.total_leave_days
                    record["total"] += req.total_leave_days
                if not req.get_approved and not req.get_unapproved:
                    record["pending"] += req.total_leave_days
        leaves_list.append(record)
    years = sorted(years)
    if len(years) > 0:
        years.append(years[-1] + 1)
        years.insert(0, years[0] - 1)
    return render_template('staff/leave_request_by_person.html', leave_types=leave_types,
                           sel_dept=org_id, year=fiscal_year,
                           leaves_list=leaves_list, departments=[{'id': d.id, 'name': d.name}
                                                                 for d in departments], years=years)


@staff.route('leave/requests/result-by-person/<int:requester_id>')
@login_required
def leave_request_by_person_detail(requester_id):
    requester = StaffLeaveRequest.query.filter_by(staff_account_id=requester_id)
    return render_template('staff/leave_request_by_person_detail.html', requester=requester)


@staff.route('/wfh')
@login_required
def show_work_from_home():
    req = StaffWorkFromHomeRequest.query.filter_by(staff_account_id=current_user.id).all()
    checkjob = StaffWorkFromHomeCheckedJob.query.all()
    return render_template('staff/wfh_info.html', req=req, checkjob=checkjob)


@staff.route('/wfh/request',
             methods=['GET', 'POST'])
@login_required
def request_work_from_home():
    if request.method == 'POST':
        form = request.form
        start_t = "08:30"
        end_t = "16:30"
        start_d, end_d = form.get('dates').split(' - ')
        start_dt = '{} {}'.format(start_d, start_t)
        end_dt = '{} {}'.format(end_d, end_t)
        start_datetime = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
        end_datetime = datetime.strptime(end_dt, '%d/%m/%Y %H:%M')
        deadline_date = datetime.strptime(form.get('deadline_date'), '%d/%m/%Y')
        req = StaffWorkFromHomeRequest(
            staff=current_user,
            start_datetime=tz.localize(start_datetime),
            end_datetime=tz.localize(end_datetime),
            detail=form.get('detail'),
            contact_phone=form.get('contact_phone'),
            deadline_date=deadline_date
        )
        db.session.add(req)
        db.session.commit()
        return redirect(url_for('staff.show_work_from_home'))

    else:
        return render_template('staff/wfh_request.html')


@staff.route('/wfh/request/<int:request_id>/edit',
             methods=['GET', 'POST'])
@login_required
def edit_request_work_from_home(request_id):
    req = StaffWorkFromHomeRequest.query.get(request_id)
    if request.method == 'POST':
        start_dt, end_dt = request.form.get('dates').split(' - ')
        start_datetime = datetime.strptime(start_dt, '%d/%m/%Y')
        end_datetime = datetime.strptime(end_dt, '%d/%m/%Y')
        req.start_datetime = tz.localize(start_datetime),
        req.end_datetime = tz.localize(end_datetime),
        req.detail = request.form.get('detail'),
        req.contact_phone = request.form.get('contact_phone'),
        req.deadline_date = request.form.get('deadline_date')
        db.session.add(req)
        db.session.commit()
        return redirect(url_for('staff.show_work_from_home'))

    selected_dates = [req.start_datetime, req.end_datetime]
    deadline = req.deadline_date
    return render_template('staff/edit_wfh_request.html', req=req, selected_dates=selected_dates, deadline=deadline)


@staff.route('/wfh/request/<int:request_id>/cancel')
@login_required
def cancel_wfh_request(request_id):
    req = StaffWorkFromHomeRequest.query.get(request_id)
    req.cancelled_at = tz.localize(datetime.today())
    db.session.add(req)
    db.session.commit()
    return redirect(request.referrer)


@staff.route('/wfh/<int:request_id>/info',
             methods=['GET', 'POST'])
@login_required
def wfh_show_request_info(request_id):
    if request.method == 'POST':
        form = request.form
        req = StaffWorkFromHomeJobDetail(
            wfh_id=request_id,
            activity=form.get('activity')
        )
        db.session.add(req)
        db.session.commit()
        wfhreq = StaffWorkFromHomeRequest.query.get(request_id)
        detail = StaffWorkFromHomeJobDetail.query.filter_by(wfh_id=request_id)
        return render_template('staff/wfh_request_job_details.html', wfhreq=wfhreq, detail=detail)
    else:
        check = StaffWorkFromHomeCheckedJob.query.filter_by(request_id=request_id).first()
        if check:
            return redirect(url_for("staff.record_each_request_wfh_request", request_id=request_id))
        else:
            wfhreq = StaffWorkFromHomeRequest.query.get(request_id)
            detail = StaffWorkFromHomeJobDetail.query.filter_by(wfh_id=request_id)
            return render_template('staff/wfh_request_job_details.html', wfhreq=wfhreq, detail=detail)


@staff.route('/wfh/requests/approval')
@login_required
def show_wfh_requests_for_approval():
    approvers = StaffWorkFromHomeApprover.query.filter_by(approver_account_id=current_user.id).all()
    checkjob = StaffWorkFromHomeCheckedJob.query.all()
    return render_template('staff/wfh_requests_approval_info.html', approvers=approvers, checkjob=checkjob)


@staff.route('/wfh/requests/approval/pending/<int:req_id>')
@login_required
def pending_wfh_request_for_approval(req_id):
    req = StaffWorkFromHomeRequest.query.get(req_id)
    approver = StaffWorkFromHomeApprover.query.filter_by(account=current_user, requester=req.staff).first()
    approve = StaffWorkFromHomeApproval.query.filter_by(approver=approver, request=req).first()
    if approve:
        return render_template('staff/wfh_record_info_each_request.html', req=req, approver=approver)
    return render_template('staff/wfh_request_pending_approval.html', req=req, approver=approver)


@staff.route('/wfh/requests/approve/<int:req_id>/<int:approver_id>')
@login_required
def wfh_approve(req_id, approver_id):
    approval = StaffWorkFromHomeApproval(
        request_id=req_id,
        approver_id=approver_id,
        is_approved=True,
        updated_at=tz.localize(datetime.today())
    )
    db.session.add(approval)
    db.session.commit()
    # approve_msg = u'การขออนุมัติWFH {} ได้รับการอนุมัติโดย {} เรียบร้อยแล้ว'.format(approval, current_user.personal_info.fullname)
    # line_bot_api.push_message(to=req.staff.line_id,messages=TextSendMessage(text=approve_msg))
    flash(u'อนุมัติขอทำงานที่บ้านให้บุคลากรในสังกัดเรียบร้อยแล้ว')
    return redirect(url_for('staff.show_wfh_requests_for_approval'))


@staff.route('/wfh/requests/reject/<int:req_id>/<int:approver_id>')
@login_required
def wfh_reject(req_id, approver_id):
    approval = StaffWorkFromHomeApproval(
        request_id=req_id,
        approver_id=approver_id,
        is_approved=False,
        updated_at=tz.localize(datetime.today())
    )
    db.session.add(approval)
    db.session.commit()
    # approve_msg = u'การขออนุมัติWFH {} ไม่ได้รับการอนุมัติ กรุณาติดต่อ {}'.format(approval, current_user.personal_info.fullname)
    # line_bot_api.push_message(to=req.staff.line_id,messages=TextSendMessage(text=approve_msg))
    flash(u'ไม่อนุมัติขอทำงานที่บ้านให้บุคลากรในสังกัดเรียบร้อยแล้ว')
    return redirect(url_for('staff.show_wfh_requests_for_approval'))


@staff.route('/wfh/requests/approved/list/<int:requester_id>')
@login_required
def show_wfh_approved_list_each_person(requester_id):
    requester = StaffWorkFromHomeRequest.query.filter_by(staff_account_id=requester_id)

    return render_template('staff/wfh_all_approved_list_each_person.html', requester=requester)


@staff.route('/wfh/requests/<int:request_id>/approvals')
@login_required
def show_wfh_approval(request_id):
    request = StaffWorkFromHomeRequest.query.get(request_id)
    approvers = StaffWorkFromHomeApprover.query.filter_by(staff_account_id=current_user.id)
    return render_template('staff/wfh_approval_status.html', request=request, approvers=approvers)


@staff.route('/wfh/<int:request_id>/info/edit-detail/<detail_id>',
             methods=['GET', 'POST'])
@login_required
def edit_wfh_job_detail(request_id, detail_id):
    detail = StaffWorkFromHomeJobDetail.query.get(detail_id)
    if request.method == 'POST':
        detail.activity = request.form.get('activity')
        db.session.add(detail)
        db.session.commit()
        return redirect(url_for('staff.wfh_show_request_info', request_id=request_id))

    detail = StaffWorkFromHomeJobDetail.query.get(detail_id)
    return render_template('staff/edit_wfh_job_detail.html', detail=detail, request_id=request_id)


@staff.route('/wfh/<int:request_id>/info/finish-job-detail/<detail_id>')
@login_required
def finish_wfh_job_detail(request_id, detail_id):
    detail = StaffWorkFromHomeJobDetail.query.get(detail_id)
    if detail:
        detail.status = True
        db.session.add(detail)
        db.session.commit()
        return redirect(url_for('staff.wfh_show_request_info', request_id=request_id))


@staff.route('/wfh/info/cancel-job-detail/<detail_id>')
@login_required
def cancel_wfh_job_detail(detail_id):
    detail = StaffWorkFromHomeJobDetail.query.get(detail_id)
    if detail:
        db.session.delete(detail)
        db.session.commit()
        return redirect(url_for('staff.wfh_show_request_info', request_id=detail.wfh_id))


@staff.route('/wfh/<int:request_id>/info/unfinish-job-detail/<detail_id>')
@login_required
def unfinish_wfh_job_detail(request_id, detail_id):
    detail = StaffWorkFromHomeJobDetail.query.get(detail_id)
    if detail:
        detail.status = False
        db.session.add(detail)
        db.session.commit()
        return redirect(url_for('staff.wfh_show_request_info', request_id=request_id))


@staff.route('/wfh/<int:request_id>/info/add-overall-result',
             methods=['GET', 'POST'])
@login_required
def add_overall_result_work_from_home(request_id):
    if request.method == 'POST':
        form = request.form
        result = StaffWorkFromHomeCheckedJob(
            overall_result=form.get('overall_result'),
            finished_at=tz.localize(datetime.today()),
            request_id=request_id
        )
        db.session.add(result)
        db.session.commit()
        wfhreq = StaffWorkFromHomeRequest.query.get(request_id)
        detail = StaffWorkFromHomeJobDetail.query.filter_by(wfh_id=request_id)
        check = StaffWorkFromHomeCheckedJob.query.filter_by(request_id=request_id)
        return render_template('staff/wfh_record_info_each_request_subordinate.html',
                               req=wfhreq, job_detail=detail, checkjob=check)

    else:
        wfhreq = StaffWorkFromHomeRequest.query.get(request_id)
        detail = StaffWorkFromHomeJobDetail.query.filter_by(wfh_id=request_id)
        return render_template('staff/wfh_add_overall_result.html', wfhreq=wfhreq, detail=detail)


@staff.route('wfh/<int:request_id>/check/<int:check_id>',
             methods=['GET', 'POST'])
@login_required
def comment_wfh_request(request_id, check_id):
    checkjob = StaffWorkFromHomeCheckedJob.query.get(check_id)
    approval = StaffWorkFromHomeApproval.query.filter(and_(StaffWorkFromHomeApproval.request_id == request_id,
                                                           StaffWorkFromHomeApproval.approver.has(
                                                               account=current_user))).first()
    if request.method == 'POST':
        checkjob.id = check_id,
        if not approval.approval_comment:
            approval.approval_comment = request.form.get('approval_comment')
        else:
            approval.approval_comment += "," + request.form.get('approval_comment')
        approval.checked_at = tz.localize(datetime.today())
        db.session.add(checkjob)
        db.session.commit()
        return redirect(url_for('staff.show_wfh_requests_for_approval'))

    else:
        req = StaffWorkFromHomeRequest.query.get(request_id)
        job_detail = StaffWorkFromHomeJobDetail.query.filter_by(wfh_id=request_id)
        check = StaffWorkFromHomeCheckedJob.query.filter_by(id=check_id)
        return render_template('staff/wfh_approval_comment.html', req=req, job_detail=job_detail,
                               checkjob=check)


@staff.route('wfh/<int:request_id>/record/info',
             methods=['GET', 'POST'])
@login_required
def record_each_request_wfh_request(request_id):
    req = StaffWorkFromHomeRequest.query.get(request_id)
    job_detail = StaffWorkFromHomeJobDetail.query.filter_by(wfh_id=request_id)
    check = StaffWorkFromHomeCheckedJob.query.filter_by(request_id=request_id)
    return render_template('staff/wfh_record_info_each_request.html', req=req, job_detail=job_detail,
                           checkjob=check)


@staff.route('/wfh/requests/list',
             methods=['GET', 'POST'])
@login_required
def wfh_requests_list():
    if request.method == 'POST':
        form = request.form
        start_dt, end_dt = form.get('dates').split(' - ')
        start_date = datetime.strptime(start_dt, '%d/%m/%Y')
        end_date = datetime.strptime(end_dt, '%d/%m/%Y')

        wfh_request = StaffWorkFromHomeRequest.query.filter(and_(StaffWorkFromHomeRequest.start_datetime >= start_date,
                                                                 StaffWorkFromHomeRequest.end_datetime <= end_date))
        return render_template('staff/wfh_request_result_by_date.html', request=wfh_request,
                               start_date=start_date.date(), end_date=end_date.date())
    else:
        return render_template('staff/wfh_request_info_by_date.html')


@staff.route('/for-hr')
@login_required
def for_hr():
    return render_template('staff/for_hr.html')


class LoginDataUploadView(BaseView):
    @expose('/')
    def index(self):
        return self.render('staff/login_datetime_upload.html')

    def calculate(self, row):
        DATETIME_FORMAT = '%d/%m/%Y %H:%M'
        office_starttime = '09:00'
        office_endtime = '16:30'

        if not isna(row.Time):
            account = StaffPersonalInfo.query.filter_by(finger_scan_id=row.ID).first()
            if not account:
                return

            start, end = row.Time.split()[0], row.Time.split()[-1]

            if start != end:
                start_dt = datetime.strptime(u'{} {}'.format(row.Date, start), DATETIME_FORMAT)
                end_dt = datetime.strptime(u'{} {}'.format(row.Date, end), DATETIME_FORMAT)
            else:
                start_dt = datetime.strptime(u'{} {}'.format(row.Date, start), DATETIME_FORMAT)
                end_dt = None
            office_startdt = datetime.strptime(u'{} {}'.format(row.Date, office_starttime), DATETIME_FORMAT)
            office_enddt = datetime.strptime(u'{} {}'.format(row.Date, office_endtime), DATETIME_FORMAT)

            if start_dt:
                if office_startdt > start_dt:
                    morning = office_startdt - start_dt
                    morning = (morning.seconds / 60.0) * -1
                else:
                    morning = start_dt - office_startdt
                    morning = morning.seconds / 60.0
                # status = "Late" if morning > 0 else "On time"
            if end_dt:
                if office_enddt < end_dt:
                    evening = end_dt - office_enddt
                    evening = evening.seconds / 60.0
                else:
                    evening = office_enddt - end_dt
                    evening = (evening.seconds / 60.0) * -1
                # status = "Off early" if evening < 0 else "On time"
            if start_dt and end_dt:
                record = StaffWorkLogin(
                    staff=account.staff_account,
                    start_datetime=tz.localize(start_dt),
                    end_datetime=tz.localize(end_dt),
                    checkin_mins=morning,
                    checkout_mins=evening
                )
            else:
                record = StaffWorkLogin(
                    staff=account.staff_account,
                    start_datetime=tz.localize(start_dt),
                    checkin_mins=morning,
                )
            db.session.add(record)
            db.session.commit()

    @expose('/upload', methods=['GET', 'POST'])
    def upload(self):
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file alert')
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                flash('No file selected')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                df = read_excel(file, dtype=object)
                df.apply(self.calculate, axis=1)
        return 'Done'


@staff.route('/summary')
@login_required
def summary_index():
    depts = Org.query.filter_by(head=current_user.email).all()
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
        return redirect(url_for("staff.summary_org"))
    curr_dept_id = request.args.get('curr_dept_id')
    tab = request.args.get('tab', 'all')
    if curr_dept_id is None:
        curr_dept_id = depts[0].id
    employees = StaffPersonalInfo.query.filter_by(org_id=int(curr_dept_id))
    leaves = []
    wfhs = []
    seminars = []
    logins = []
    for emp in employees:
        if tab == 'login' or tab == 'all':
            fiscal_years = StaffWorkLogin.query.distinct(func.date_part('YEAR', StaffWorkLogin.start_datetime))
            fiscal_years = [convert_to_fiscal_year(req.start_datetime) for req in fiscal_years]
            start_fiscal_date, end_fiscal_date = get_start_end_date_for_fiscal_year(fiscal_year)
            border_color = '#ffffff'
            for rec in StaffWorkLogin.query.filter_by(staff=emp) \
                    .filter(StaffWorkLogin.start_datetime.between(start_fiscal_date, end_fiscal_date)):
                text_color = '#ffffff'
                if (rec.checkin_mins < 0) or (rec.checkout_mins > 0):
                    bg_color = '#4da6ff'
                    status = ''
                if rec.end_datetime is None:
                    status = '???'
                    text_color = '#000000'
                    bg_color = '#ffff66'
                elif rec.checkin_mins > 0 and rec.checkout_mins < 0:
                    status = u'สาย/ออกก่อน'
                    bg_color = '#ff5c33'
                elif rec.checkin_mins > 0:
                    status = u'เข้าสาย'
                    text_color = '#000000'
                    bg_color = '#ffff66'
                elif rec.checkout_mins < 0:
                    status = u'ออกก่อน'
                    text_color = '#000000'
                    bg_color = '#ffff66'
                logins.append({
                    'id': rec.id,
                    'start': rec.start_datetime.astimezone(tz).isoformat(),
                    'end': None if rec.end_datetime is None else rec.end_datetime.astimezone(tz).isoformat(),
                    'title': u'{} {}'.format(emp.th_firstname, status),
                    'backgroundColor': bg_color,
                    'borderColor': border_color,
                    'textColor': text_color,
                    'type': 'login'
                })
            all = logins

        if tab == 'leave' or tab == 'all':
            fiscal_years = StaffLeaveRequest.query.distinct(func.date_part('YEAR', StaffLeaveRequest.start_datetime))
            fiscal_years = [convert_to_fiscal_year(req.start_datetime) for req in fiscal_years]
            start_fiscal_date, end_fiscal_date = get_start_end_date_for_fiscal_year(fiscal_year)
            for leave_req in StaffLeaveRequest.query.filter_by(staff=emp) \
                    .filter(StaffLeaveRequest.start_datetime.between(start_fiscal_date, end_fiscal_date)):
                if not leave_req.cancelled_at:
                    if leave_req.get_approved:
                        text_color = '#ffffff'
                        bg_color = '#2b8c36'
                        border_color = '#ffffff'
                    else:
                        text_color = '#989898'
                        bg_color = '#d1e0e0'
                        border_color = '#ffffff'
                    leaves.append({
                        'id': leave_req.id,
                        'start': leave_req.start_datetime.astimezone(tz).isoformat(),
                        'end': leave_req.end_datetime.astimezone(tz).isoformat(),
                        'title': u'{} {}'.format(emp.th_firstname, leave_req.quota.leave_type),
                        'backgroundColor': bg_color,
                        'borderColor': border_color,
                        'textColor': text_color,
                        'type': 'leave'
                    })
            all = leaves

        if tab == 'wfh' or tab == 'all':
            fiscal_years = StaffWorkFromHomeRequest.query.distinct(
                func.date_part('YEAR', StaffWorkFromHomeRequest.start_datetime))
            fiscal_years = [convert_to_fiscal_year(req.start_datetime) for req in fiscal_years]
            start_fiscal_date, end_fiscal_date = get_start_end_date_for_fiscal_year(fiscal_year)
            for wfh_req in StaffWorkFromHomeRequest.query.filter_by(staff=emp).filter(
                    StaffWorkFromHomeRequest.start_datetime.between(start_fiscal_date, end_fiscal_date)):
                if not wfh_req.cancelled_at:
                    if wfh_req.get_approved:
                        text_color = '#ffffff'
                        bg_color = '#109AD3'
                        border_color = '#ffffff'
                    else:
                        text_color = '#989898'
                        bg_color = '#C5ECFB'
                        border_color = '#ffffff'
                    wfhs.append({
                        'id': wfh_req.id,
                        'start': wfh_req.start_datetime.astimezone(tz).isoformat(),
                        'end': wfh_req.end_datetime.astimezone(tz).isoformat(),
                        'title': emp.th_firstname + " WFH",
                        'backgroundColor': bg_color,
                        'borderColor': border_color,
                        'textColor': text_color,
                        'type': 'wfh'
                    })
            all = wfhs
        if tab == 'smr' or tab == 'all':
            fiscal_years = StaffSeminarAttend.query.distinct(
                func.date_part('YEAR', StaffSeminarAttend.start_datetime))
            fiscal_years = [convert_to_fiscal_year(req.start_datetime) for req in fiscal_years]
            start_fiscal_date, end_fiscal_date = get_start_end_date_for_fiscal_year(fiscal_year)
            for smr in emp.staff_account.seminar_attends.filter(
                    StaffSeminarAttend.start_datetime.between(start_fiscal_date, end_fiscal_date)):
                text_color = '#ffffff'
                bg_color = '#FF33A5'
                border_color = '#ffffff'
                seminars.append({
                    'id': smr.id,
                    'start': smr.start_datetime.astimezone(tz).isoformat(),
                    'end': smr.end_datetime.astimezone(tz).isoformat(),
                    'title': emp.th_firstname + " " + smr.seminar.topic,
                    'backgroundColor': bg_color,
                    'borderColor': border_color,
                    'textColor': text_color,
                    'type': 'smr'
                })
            all = seminars

    if tab == 'all':
        all = wfhs + leaves + logins + seminars

    return render_template('staff/summary_index.html',
                           init_date=init_date,
                           depts=depts, curr_dept_id=int(curr_dept_id),
                           all=all, tab=tab, fiscal_years=fiscal_years, fiscal_year=fiscal_year)


@staff.route('/api/staffids')
def get_staffid():
    staff = []
    for sid in StaffPersonalInfo.query.all():
        staff.append({
            'id': sid.id,
            'fullname': sid.fullname,
            'org': sid.org.name if sid.org else 'ไม่มีต้นสังกัด'
        })

    return jsonify(staff)


@staff.route('/summary/org')
@login_required
def summary_org():
    gj = StaffSpecialGroup.query.filter_by(group_code='gj').first()
    secret = StaffSpecialGroup.query.filter_by(group_code='secretary').first()
    if current_user not in gj.staffs and current_user not in secret.staffs:
        return redirect(url_for("staff.index"))
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

    curr_dept_id = request.args.get('curr_dept_id', current_user.personal_info.org.id)
    tab = request.args.get('tab', 'all')

    employees = StaffPersonalInfo.query.filter_by(org_id=int(curr_dept_id))

    leaves = []
    for emp in employees:
        if tab == 'leave' or tab == 'all':
            fiscal_years = StaffLeaveRequest.query.distinct(func.date_part('YEAR', StaffLeaveRequest.start_datetime))
            fiscal_years = [convert_to_fiscal_year(req.start_datetime) for req in fiscal_years]
            start_fiscal_date, end_fiscal_date = get_start_end_date_for_fiscal_year(fiscal_year)
            for leave_req in StaffLeaveRequest.query.filter_by(staff=emp) \
                    .filter(StaffLeaveRequest.start_datetime.between(start_fiscal_date, end_fiscal_date)):
                if not leave_req.cancelled_at:
                    if leave_req.get_approved:
                        text_color = '#ffffff'
                        bg_color = '#2b8c36'
                        border_color = '#ffffff'
                    else:
                        text_color = '#989898'
                        bg_color = '#d1e0e0'
                        border_color = '#ffffff'
                    leaves.append({
                        'id': leave_req.id,
                        'start': leave_req.start_datetime.astimezone(tz).isoformat(),
                        'end': leave_req.end_datetime.astimezone(tz).isoformat(),
                        'title': u'{} {}'.format(emp.th_firstname, leave_req.quota.leave_type),
                        'backgroundColor': bg_color,
                        'borderColor': border_color,
                        'textColor': text_color,
                        'type': 'leave'
                    })
            all = leaves

    if tab == 'all':
        all = leaves

    return render_template('staff/summary_org.html', init_date=init_date,
                           curr_dept_id=int(curr_dept_id),
                           all=all, tab=tab, fiscal_years=fiscal_years, fiscal_year=fiscal_year)


@staff.route('/for-hr/seminar')
@login_required
def seminar():
    return render_template('staff/seminar.html')


@staff.route('/seminar/create', methods=['GET', 'POST'])
@login_required
def create_seminar():
    if request.method == 'POST':
        form = request.form
        start_datetime = datetime.strptime(form.get('start_datetime'), '%d/%m/%Y %H:%M')
        end_datetime = datetime.strptime(form.get('end_datetime'), '%d/%m/%Y %H:%M')
        timedelta = end_datetime - start_datetime
        if timedelta.days < 0 or timedelta.seconds == 0:
            flash(u'วันที่สิ้นสุดต้องไม่เร็วกว่าวันที่เริ่มต้น', 'danger')
        else:
            seminar = StaffSeminar(
                start_datetime=tz.localize(start_datetime),
                end_datetime=tz.localize(end_datetime)
            )
            seminar.topic_type = form.get('topic_type')
            seminar.topic = form.get('topic')
            seminar.mission = form.get('mission')
            seminar.location = form.get('location')
            seminar.country = form.get('country')
            seminar.is_online = True if form.getlist("online") else False
            db.session.add(seminar)
            db.session.commit()
            flash(u'เพิ่มข้อมูลกิจกรรมเรียบร้อย', 'success')
            return redirect(url_for('staff.seminar_records'))
    return render_template('staff/seminar_create_event.html')


@staff.route('/seminar/add-attend/<int:seminar_id>', methods=['GET', 'POST'])
@login_required
def seminar_attend_info(seminar_id):
    seminar = StaffSeminar.query.get(seminar_id)
    attends = StaffSeminarAttend.query.filter_by(seminar_id=seminar_id).all()
    return render_template('staff/seminar_attend_info.html', seminar=seminar, attends=attends)


@staff.route('/seminar/all-seminars', methods=['GET', 'POST'])
@login_required
def seminar_records():
    seminar_list = []
    seminar_query = StaffSeminar.query.filter(StaffSeminar.cancelled_at==None).all()
    for seminar in seminar_query:
        record = {}
        record["id"] = seminar.id
        record["topic_type"] = seminar.topic_type
        record["name"] = seminar.topic
        record["start"] = seminar.start_datetime
        record["end"] = seminar.end_datetime
        seminar_list.append(record)
    return render_template('staff/seminar_records.html', seminar_list=seminar_list)


@staff.route('/seminar/add-attend/add-attendee/<int:seminar_id>', methods=['GET', 'POST'])
@login_required
def seminar_add_attendee(seminar_id):
    seminar = StaffSeminar.query.get(seminar_id)
    staff_list = []
    account_query = StaffAccount.query.all()
    for account in account_query:
        record = dict(staffid=account.id,
                      fullname=account.personal_info.fullname,
                      email=account.email)
        organization = account.personal_info.org
        record["org"] = organization.name if organization else ""
        staff_list.append(record)
    if request.method == "POST":
        form = request.form
        start_datetime = datetime.strptime(form.get('start_dt'), '%d/%m/%Y %H:%M')
        end_datetime = datetime.strptime(form.get('end_dt'), '%d/%m/%Y %H:%M')
        timedelta = end_datetime - start_datetime
        if timedelta.days < 0 or timedelta.seconds == 0:
            flash(u'วันที่สิ้นสุดต้องไม่เร็วกว่าวันที่เริ่มต้น', 'danger')
            return render_template('staff/seminar_add_attendee.html', seminar=seminar, staff_list=staff_list)
        else:
            attend = StaffSeminarAttend(
                staff=[StaffAccount.query.get(int(staff_id)) for staff_id in form.getlist("participants")],
                seminar_id=seminar_id,
                role=form.get('role'),
                registration_fee=form.get('registration_fee'),
                budget_type=form.get('budget_type'),
                budget=form.get('budget'),
                start_datetime=tz.localize(start_datetime),
                end_datetime=tz.localize(end_datetime),
                attend_online=True if form.get("attend_online") else False
            )
            db.session.add(attend)
            db.session.commit()
            seminar = StaffSeminar.query.get(seminar_id)
            attends = StaffSeminarAttend.query.filter_by(seminar_id=seminar_id).all()
            flash(u'เพิ่มผู้เข้าร่วมใหม่เรียบร้อยแล้ว', 'success')
            return render_template('staff/seminar_attend_info.html', seminar=seminar, attends=attends)

    return render_template('staff/seminar_add_attendee.html', seminar=seminar, staff_list=staff_list)


@staff.route('/seminar/seminar-attend/<int:attend_id>/participants/<int:participant_id>')
@login_required
def delete_participant(attend_id,participant_id):
    participant = StaffAccount.query.get(participant_id)
    attend = StaffSeminarAttend.query.get(attend_id)
    attend.staff.remove(participant)
    db.session.delete(attend)
    db.session.commit()
    seminar = StaffSeminar.query.get(attend.seminar_id)
    attends = StaffSeminarAttend.query.filter_by(seminar_id=attend.seminar_id).all()
    return render_template('staff/seminar_attend_info.html', seminar=seminar, attends=attends)


#TODO : delete this function after finished edit seminar model
@staff.route('/seminar/all-records/each-person/<int:staff_id>')
@login_required
def show_seminar_info_each_person(staff_id):
    staff = StaffSeminar.query.filter_by(staff_account_id=staff_id)
    return render_template('staff/seminar_records_each_person.html', staff=staff)


@staff.route('/seminar/edit-seminar/<int:seminar_id>', methods=['GET', 'POST'])
@login_required
def edit_seminar_info(seminar_id):
    seminar = StaffSeminar.query.get(seminar_id)
    if request.method == 'POST':
        form = request.form
        start_datetime = datetime.strptime(form.get('start_datetime'), '%d/%m/%Y %H:%M')
        end_datetime = datetime.strptime(form.get('end_datetime'), '%d/%m/%Y %H:%M')
        timedelta = end_datetime - start_datetime
        if timedelta.days < 0 or timedelta.seconds == 0:
            flash(u'วันที่สิ้นสุดต้องไม่เร็วกว่าวันที่เริ่มต้น', 'danger')
            return render_template('staff/seminar_edit_seminar_info.html', seminar=seminar)
        else:
            seminar.start_datetime=tz.localize(start_datetime)
            seminar.end_datetime=tz.localize(end_datetime)
            seminar.topic_type = form.get('topic_type')
            seminar.topic = form.get('topic')
            seminar.mission = form.get('mission')
            seminar.location = form.get('location')
            seminar.country = form.get('country')
            seminar.is_online = True if form.getlist("online") else False
            db.session.add(seminar)
            db.session.commit()
            flash(u'การแก้ไขถูกบันทึกเรียบร้อย', 'success')
            return redirect(url_for('staff.seminar_records'))

    return render_template('staff/seminar_edit_seminar_info.html', seminar=seminar)


@staff.route('/seminar/cancel-seminar/<int:seminar_id>', methods=['GET', 'POST'])
@login_required
def cancel_seminar(seminar_id):
    seminar = StaffSeminar.query.get(seminar_id)
    attends = StaffSeminarAttend.query.filter_by(seminar_id=seminar_id).all()
    if attends:
        flash(u'ไม่สามารถลบกิจกรรมนี้ได้ เนื่องจากมีข้อมูลผู้เข้าร่วมอยู่ในกิจกรรม จำเป็นต้องลบข้อมูลผู้เข้าร่วมก่อน', 'danger')
    else:
        seminar.cancelled_at = tz.localize(datetime.today())
        db.session.add(seminar)
        db.session.commit()
        flash(u'ลบกิจกรรมเรียบร้อยแล้ว', 'success')
    return redirect(url_for('staff.seminar_records'))


@staff.route('/time-report/report')
@login_required
def show_time_report():
    return render_template('staff/time_report.html')


@staff.route('/for-hr/staff-info')
@login_required
def staff_index():
    return render_template('staff/staff_index.html')


@staff.route('/for-hr/staff-info/create', methods=['GET', 'POST'])
@login_required
def staff_create_info():
    if request.method == 'POST':
        form = request.form
        start_d = form.get('employed_date')
        start_date = datetime.strptime(start_d, '%d/%m/%Y')
        createstaff = StaffPersonalInfo(
            en_firstname=form.get('en_firstname'),
            en_lastname=form.get('en_lastname'),
            th_firstname=form.get('th_firstname'),
            th_lastname=form.get('th_lastname'),
            #TODO: try removing localize
            employed_date=tz.localize(start_date),
            finger_scan_id=form.get('finger_scan_id'),
            employment_id=form.get('employment_id'),
            org_id=form.get('org_id')
        )
        academic_staff = True if form.getlist("academic_staff") else False
        createstaff.academic_staff = academic_staff

        db.session.add(createstaff)
        db.session.commit()

        create_email = StaffAccount(
            personal_id=createstaff.id,
            email=form.get('email'),
            password=form.get('password')
        )
        db.session.add(create_email)
        db.session.commit()

        flash(u'เพิ่มบุคลากรเรียบร้อย', 'success')
        staff = StaffPersonalInfo.query.get(createstaff.id)
        return render_template('staff/staff_show_info.html', staff=staff)
    departments = Org.query.all()
    employments = StaffEmployment.query.all()
    return render_template('staff/staff_create_info.html', departments=departments, employments=employments)


@staff.route('/for-hr/staff-info/search-info', methods=['GET', 'POST'])
@login_required
def staff_search_info():
    if request.method == 'POST':
        staff_id = request.form.get('staffname')
        staff = StaffPersonalInfo.query.get(staff_id)
        emp_date = staff.employed_date
        employments = StaffEmployment.query.all()
        departments = Org.query.all()
        return render_template('staff/staff_edit_info.html', staff=staff, emp_date=emp_date, employments=employments,
                               departments=departments)
    return render_template('staff/staff_find_name_to_edit.html')


@staff.route('/for-hr/staff-info/edit-info/<int:staff_id>', methods=['GET', 'POST'])
@login_required
def staff_edit_info(staff_id):
    staff = StaffPersonalInfo.query.get(staff_id)
    if request.method == 'POST':
        form = request.form
        staff_email = StaffAccount.query.filter_by(personal_id=staff_id).first()
        if staff_email:
            staff_email.email = form.get('email')
            db.session.add(staff_email)
        else:
            createstaff = StaffAccount(
                personal_id=staff_id,
                email=form.get('email')
            )
            db.session.add(createstaff)
        start_d = form.get('employed_date')
        start_date = datetime.strptime(start_d, '%d/%m/%Y')
        staff.en_firstname = form.get('en_firstname')
        staff.en_lastname = form.get('en_lastname')
        staff.th_firstname = form.get('th_firstname')
        staff.th_lastname = form.get('th_lastname')
        staff.employed_date = tz.localize(start_date)
        if form.get('finger_scan_id'):
            staff.finger_scan_id = form.get('finger_scan_id')
        staff.employment_id = form.get('employment_id')
        staff.org_id = form.get('org_id')
        academic_staff = True if form.getlist("academic_staff") else False
        staff.academic_staff = academic_staff
        db.session.add(staff)
        db.session.commit()
        flash(u'แก้ไขข้อมูลบุคลากรเรียบร้อย')
        return render_template('staff/staff_show_info.html', staff=staff)
    return render_template('staff/staff_index.html')


@staff.route('/for-hr/staff-info/edit-info/<int:staff_id>/show-info')
@login_required
def staff_show_info(staff_id):
    staff = StaffPersonalInfo.query.get(staff_id)
    return render_template('staff/staff_show_info.html', staff=staff)


@staff.route('/for-hr/staff-info/search-account', methods=['GET', 'POST'])
@login_required
def staff_search_to_change_pwd():
    if request.method == 'POST':
        staff_id = request.form.get('staffname')
        account = StaffAccount.query.filter_by(id=staff_id).first()
        return render_template('staff/staff_edit_pwd.html', account=account)
    return render_template('staff/staff_search_to_change_pwd.html')


@staff.route('/for-hr/staff-info/search-account/edit-pwd/<int:staff_id>', methods=['GET', 'POST'])
@login_required
def staff_edit_pwd(staff_id):
    if request.method == 'POST':
        form = request.form
        staff_email = StaffAccount.query.filter_by(id=staff_id).first()
        staff_email.password = form.get('pwd')
        db.session.add(staff_email)
        db.session.commit()
        flash(u'แก้ไขรหัสผ่านเรียบร้อย')
        return render_template('staff/staff_index.html')
    return render_template('staff/staff_search_to_change_pwadd_seminar_recordd.html')



@staff.route('/for-hr/staff-info/approvers',
             methods=['GET', 'POST'])
@login_required
def staff_show_approvers():
    org_id = request.args.get('deptid')
    departments = Org.query.all()
    if org_id is None:
        account_query = StaffAccount.query.all()
    else:
        account_query = StaffAccount.query.filter(StaffAccount.personal_info.has(org_id=org_id))

    return render_template('staff/show_leave_approver.html',
                           sel_dept=org_id, account_list=list(account_query),
                            departments=[{'id': d.id, 'name': d.name} for d in departments])


@staff.route('/for-hr/staff-info/approvers/add/<int:approver_id>',
             methods=['GET', 'POST'])
@login_required
def staff_add_approver(approver_id):
    if request.method == 'POST':
        staff_account_id = request.form.get('staffname')
        find_requester = StaffLeaveApprover.query.filter_by\
            (approver_account_id=approver_id, staff_account_id=staff_account_id).first()
        if find_requester:
            flash(u'ไม่สามารถเพิ่มบุคลากรท่านนี้ได้ เนื่องจากมีข้อมูลบุคลากรท่านนี้อยู่แล้ว', 'warning')
        else:
            createrequester = StaffLeaveApprover(
                staff_account_id = staff_account_id,
                approver_account_id = approver_id
            )
            db.session.add(createrequester)
            db.session.commit()
            flash(u'เพิ่มบุคลากรเรียบร้อยแล้ว', 'success')
    approvers = StaffLeaveApprover.query.filter_by(approver_account_id=approver_id)
    return render_template('staff/leave_request_manage_approver.html', approvers=approvers )


@staff.route('/for-hr/staff-info/approvers/edit/<int:approver_id>/<int:requester_id>/change-active-status')
@login_required
def staff_approver_change_active_status(approver_id,requester_id):
    approver = StaffLeaveApprover.query.filter_by(approver_account_id=approver_id, staff_account_id=requester_id).first()
    approver.is_active = True if not approver.is_active else False
    db.session.add(approver)
    db.session.commit()
    flash(u'แก้ไขสถานะการอนุมัติเรียบร้อยแล้ว', 'success')
    return redirect(request.referrer)


@staff.route('/for-hr/staff-info/approvers/add/requester/<int:requester_id>',
             methods=['GET', 'POST'])
@login_required
def staff_add_requester(requester_id):
    if request.method == 'POST':
        approver_account_id = request.form.get('staffname'),
        find_approver = StaffLeaveApprover.query.filter_by\
            (approver_account_id=approver_account_id, staff_account_id=requester_id).first()
        if find_approver:
            flash(u'ไม่สามารถเพิ่มผู้อนุมัติได้เนื่องจากมีผู้อนุมัตินี้อยู่แล้ว', 'warning')
        else:
            createapprover = StaffLeaveApprover(
                approver_account_id = approver_account_id,
                staff_account_id = requester_id
            )
            db.session.add(createapprover)
            db.session.commit()
            flash(u'เพิ่มผู้อนุมัติเรียบร้อยแล้ว', 'success')

    requester = StaffLeaveApprover.query.filter_by(staff_account_id=requester_id)
    requester_name = StaffLeaveApprover.query.filter_by(staff_account_id=requester_id).first()
    return render_template('staff/leave_request_manage_requester.html', approvers=requester,
                           requester_name=requester_name)