from flask import render_template, flash, redirect, url_for, request
from app.academic_services import academic_services
from app.academic_services.forms import ServiceCustomerInfoForm
from app.academic_services.models import *


@academic_services.route('/')
def index():
    return render_template('academic_services/index.html')


@academic_services.route('/customer/index')
def customer_index():
    return render_template('academic_services/customer_index.html')


@academic_services.route('/customer/personal/add', methods=['GET', 'POST'])
def add_customer_account():
    form = ServiceCustomerInfoForm()
    customer = request.args.get('customer')
    if form.validate_on_submit():
        info = ServiceCustomerInfo()
        for account in form.account:
            if account.email.data != account.confirm_email.data or account.password.data != account.confirm_password.data:
                flash('อีเมลหรือรหัสผ่านไม่ตรงกัน', 'danger')
            else:
                form.populate_obj(info)
                db.session.add(info)
                db.session.commit()
                flash('สร้างบัญชีสำเร็จ', 'success')
                return redirect(url_for('academic_services.customer_index'))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('academic_services/add_customer_account.html', form=form, customer=customer)