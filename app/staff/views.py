from models import StaffAccount, StaffPersonalInfo
from . import staffbp as staff
from flask import jsonify

@staff.route('/')
def index():
    return '<h1>Staff page</h1><br>'


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
            return jsonify({'data': data, 'status': 'fail'})
    return jsonify({'data': data, 'status': 'success'})
