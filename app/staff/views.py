from flask_login import login_required

from models import StaffAccount, StaffPersonalInfo
from . import staffbp as staff
from flask import jsonify, render_template, request

@staff.route('/')
def index():
    return '<h1>Staff page</h1><br>'


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

@login_required
@staff.route('/leave/info/')
def show_leave_info():
    return render_template('staff/leave_info.html')