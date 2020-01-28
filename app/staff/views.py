# -*- coding:utf-8 -*-
from flask_login import login_required, current_user

from models import (StaffAccount, StaffPersonalInfo,
                    StaffLeaveRequest, StaffLeaveQuota)
from . import staffbp as staff
from app.main import db
from flask import jsonify, render_template, request, redirect, url_for, flash
from datetime import datetime
from collections import defaultdict, namedtuple
import pytz

tz = pytz.timezone('Asia/Bangkok')

LEAVE_ANNUAL_QUOTA = 10


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
    if request.method=='POST':
        email = request.form.get('email', None)
        return email
    return render_template('staff/set_password.html')


def cal_leave_duration(request_record):
    if request_record.start_datetime.date() != request_record.end_datetime.date():
        return len(request_record)
    else:
        delta = request_record.end_datetime - request_record.start_datetime
        if delta.seconds/3600.0 == 3.5:
            return 0.5
        elif delta.seconds == 0:
            return 1.0


@staff.route('/leave/info')
@login_required
def show_leave_info():
    Quota = namedtuple('quota', ['id','limit'])
    cum_days = defaultdict(float)
    quota_days = defaultdict(float)
    for req in current_user.leave_requests:
        leave_type = unicode(req.quota.leave_type)
        cum_days[leave_type] += cal_leave_duration(req)

    for quota in current_user.personal_info.employment.quota:
        delta = datetime.today().date() - current_user.personal_info.employed_date
        if delta.days > 3650:
            quota_limit = quota.cum_max_per_year2 if quota.cum_max_per_year2 else quota.max_per_year
        elif delta.days > 365:
            quota_limit = quota.cum_max_per_year1 if quota.cum_max_per_year1 else quota.max_per_year
        else:
            if quota.min_employed_months:
                if delta.days > 180:
                    quota_limit = quota.first_year
                else:
                    quota_limit = 0
            else:
                quota_limit = quota.first_year
        quota_days[quota.leave_type.type_] = Quota(quota.id, quota_limit)

    return render_template('staff/leave_info.html', cum_days=cum_days, quota_days=quota_days)


#TODO: If employed for more than  6 months, can leave for 10 days max.
#TODO: If employed fewer than 10 years, can accumulate up to 20 days max per year, otherwise 30 days.
#TODO: Temporary employed staff can accumulate up to 20 days.
@staff.route('/leave/request/quota/<int:quota_id>',
             methods=['GET', 'POST'])
@login_required
def request_for_leave(quota_id=None):
    if request.method == 'POST':
        #return jsonify(request.form)
        form = request.form
        if quota_id:
            quota = StaffLeaveQuota.query.get(quota_id)
            if quota:
                # retrieve cum periods
                cum_periods = 0
                for req in current_user.leave_requests:
                    if req.quota == quota:
                        cum_periods += cal_leave_duration(req)

                start_dt, end_dt = form.get('dates').split(' - ')
                start_datetime = datetime.strptime(start_dt, '%m/%d/%Y')
                end_datetime = datetime.strptime(end_dt, '%m/%d/%Y')
                req = StaffLeaveRequest(
                        staff=current_user,
                        quota=quota,
                        start_datetime=tz.localize(start_datetime),
                        end_datetime=tz.localize(end_datetime),
                        reason=form.get('reason'),
                        contact_address=form.get('contact_addr'),
                        contact_phone=form.get('contact_phone')
                    )
                req_duration = cal_leave_duration(req)
                delta = start_datetime.date() - current_user.personal_info.employed_date
                if quota.max_per_leave:
                    if req_duration > quota.max_per_leave:
                        flash(u'ไม่สามารถลาป่วยเกินสามวันได้โดยไม่มีใบรับรองแพทย์ประกอบ กรุณาติดต่อหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่(HR)')
                        return redirect(request.referrer)
                    else:
                        if delta.days > 365:
                            quota_limit = quota.max_per_year
                        else:
                            quota_limit = quota.first_year
                else:
                    if delta.days > 3650:
                        quota_limit = quota.cum_max_per_year2 if quota.cum_max_per_year2 else quota.max_per_year
                    elif delta.days > 365:
                        quota_limit = quota.cum_max_per_year1 if quota.cum_max_per_year1 else quota.max_per_year
                    else:
                        quota_limit = quota.first_year

                if cum_periods + req_duration <= quota_limit:
                    db.session.add(req)
                    db.session.commit()
                    return redirect(url_for('staff.show_leave_info'))
                else:
                    flash(u'วันลาที่ต้องการลา เกินจำนวนวันลาคงเหลือ')
                    return redirect(request.referrer)
            else:
                return 'Error happened'
    else:
        return render_template('staff/leave_request.html', errors={})


@staff.route('/leave/request/quota/period/<int:quota_id>', methods=["POST", "GET"])
@login_required
def request_for_leave_period(quota_id=None):
    if request.method == 'POST':
        #return jsonify(request.form)
        form = request.form
        if quota_id:
            quota = StaffLeaveQuota.query.get(quota_id)
            if quota:
                # retrieve cum periods
                cum_periods = 0
                for req in current_user.leave_requests:
                    if req.quota == quota:
                        cum_periods += cal_leave_duration(req)

                start_t, end_t = form.get('times').split(' - ')
                start_dt = '{} {}'.format(form.get('dates'), start_t)
                end_dt = '{} {}'.format(form.get('dates'), end_t)
                start_datetime = datetime.strptime(start_dt, '%m/%d/%Y %H:%M')
                end_datetime = datetime.strptime(end_dt, '%m/%d/%Y %H:%M')
                req = StaffLeaveRequest(
                    staff=current_user,
                    quota=quota,
                    start_datetime=tz.localize(start_datetime),
                    end_datetime=tz.localize(end_datetime),
                    reason=form.get('reason'),
                    contact_address=form.get('contact_addr'),
                    contact_phone=form.get('contact_phone')
                )
                req_duration = cal_leave_duration(req)
                # if duration not exceeds quota
                delta = start_datetime.date() - current_user.personal_info.employed_date
                if delta.days > 3650:
                    quota_limit = quota.cum_max_per_year2 if quota.cum_max_per_year2 else quota.max_per_year
                elif delta.days > 365:
                    quota_limit = quota.cum_max_per_year1 if quota.cum_max_per_year1 else quota.max_per_year
                else:
                    quota_limit = quota.first_year

                if cum_periods+req_duration <= quota_limit:
                    db.session.add(req)
                    db.session.commit()
                    return redirect(url_for('staff.show_leave_info'))
                else:
                    flash(u'วันลาที่ต้องการลา เกินจำนวนวันลาคงเหลือ')
                    return redirect(request.referrer)
            else:
                return 'Error happened'
    else:
        return render_template('staff/leave_request_period.html', errors={})

@staff.route('/leave/request/info/<int:quota_id>')
@login_required
def request_for_leave_info(quota_id=None):
    quota = StaffLeaveQuota.query.get(quota_id)
    leaves = []
    for leave in current_user.leave_requests:
        if leave.quota == quota:
            leaves.append(leave)

    return render_template('staff/request_info.html', leaves=leaves)
