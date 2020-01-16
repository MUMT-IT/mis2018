from flask_login import login_required, current_user

from models import (StaffAccount, StaffPersonalInfo,
                    StaffLeaveRequest, StaffLeaveQuota)
from . import staffbp as staff
from app.main import db
from flask import jsonify, render_template, request
from datetime import datetime
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


@staff.route('/leave/info')
@login_required
def show_leave_info():
    return render_template('staff/leave_info.html')


#TODO: If employed for more than  6 months, can leave for 10 days max.
#TODO: If employed fewer than 10 years, can accumulate up to 20 days max per year, otherwise 30 days.
#TODO: Temporary employed staff can accumulate up to 20 days.
@staff.route('/leave/request/quota/<int:quota_id>',
             methods=['GET', 'POST'])
@login_required
def request_for_leave(quota_id=None):
    if request.method == 'POST':
        start_date, end_date = request.form.get('dates').split(' - ')
        start_date = datetime.strptime(start_date, '%m/%d/%Y')
        end_date = datetime.strptime(end_date, '%m/%d/%Y')
        if quota_id:
            req = StaffLeaveRequest(
                staff=current_user,
                leave_quota_id=quota_id,
                start_datetime=tz.localize(start_date),
                end_datetime=tz.localize(end_date),
                reason=request.form.get('reason'),
                contact_address=request.form.get('contact_addr'),
                contact_phone=request.form.get('contact_phone')
            )
            db.session.add(req)
            db.session.commit()
            return 'Done.'
    else:
        return render_template('staff/leave_request.html', errors={})
