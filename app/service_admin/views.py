import requests
from app.service_admin import service_admin
from app.academic_services.models import *
from flask import render_template, flash, redirect, url_for, request, current_app, abort, session, make_response, \
    jsonify
from flask_login import login_user, current_user, logout_user, login_required
from app.service_admin.forms import (ServiceCustomerInfoForm, ServiceCustomerAddressForm)


@service_admin.route('/')
# @login_required
def index():
    return render_template('service_admin/index.html')


@service_admin.route('/customer/view')
@login_required
def view_customer():
    customers = ServiceCustomerInfo.query.all()
    return render_template('service_admin/view_customer.html', customers=customers)


@service_admin.route('/customer/add', methods=['GET', 'POST'])
@service_admin.route('/customer/edit/<int:customer_id>', methods=['GET', 'POST'])
def create_customer(customer_id=None):
    if customer_id:
        customer = ServiceCustomerInfo.query.get(customer_id)
        form = ServiceCustomerInfoForm(obj=customer)
    else:
        form = ServiceCustomerInfoForm()
    if form.validate_on_submit():
        if customer_id is None:
            customer = ServiceCustomerInfo()
        form.populate_obj(customer)
        if customer_id is None:
            customer.creator_id = current_user.id
        db.session.add(customer)
        db.session.commit()
        if customer_id:
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
        else:
            flash('เพิ่มลูกค้าสำเร็จ', 'success')
        return redirect(url_for('service_admin.view_customer'))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('service_admin/create_customer.html', customer_id=customer_id,
                           form=form)


@service_admin.route('/customer/address/edit/<int:customer_id>', methods=['GET', 'POST'])
def create_address(customer_id=None):
    if customer_id:
        customer = ServiceCustomerInfo.query.get(customer_id)
        form = ServiceCustomerInfoForm(obj=customer)
    else:
        form = ServiceCustomerInfoForm()
    if form.validate_on_submit():
        if customer_id is None:
            customer = ServiceCustomerInfo()
        form.populate_obj(customer)
        if customer_id is None:
            customer.creator_id = current_user.id
        db.session.add(customer)
        db.session.commit()
        if customer_id:
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
        else:
            flash('เพิ่มลูกค้าสำเร็จ', 'success')
        return redirect(url_for('service_admin.view_customer'))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('service_admin/create_customer.html', customer_id=customer_id,
                           form=form)