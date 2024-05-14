import arrow
from app.main import app
from app.academic_services import academic_services
from app.academic_services.forms import (ServiceCustomerInfoForm, LoginForm, ForgetPasswordForm, ResetPasswordForm,
                                         ServiceCustomerOrganizationForm)
from app.academic_services.models import *
from flask import render_template, flash, redirect, url_for, request, current_app, abort, session, make_response
from flask_login import login_user, current_user, logout_user, login_required
from flask_principal import Identity, identity_changed, AnonymousIdentity, identity_loaded, UserNeed
from flask_admin.helpers import is_safe_url
from itsdangerous.url_safe import URLSafeTimedSerializer as TimedJSONWebSignatureSerializer
from app.main import mail
from flask_mail import Message


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


@academic_services.route('/')
def index():
    return render_template('academic_services/index.html')


@academic_services.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        next_url = request.args.get('next', url_for('academic_services.customer_account'))
        if is_safe_url(next_url):
            return redirect(next_url)
        else:
            return abort(400)
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(ServiceCustomerAccount).filter_by(email=form.email.data).first()
        if user:
            pwd = form.password.data
            if user.verify_password(pwd):
                login_user(user)
                identity_changed.send(current_app._get_current_object(), identity=Identity(user.id))
                next_url = request.args.get('next', url_for('index'))
                if not is_safe_url(next_url):
                    return abort(400)
                else:
                    flash('ลงทะเบียนเข้าใช้งานเรียบร้อย', 'success')
                    return redirect(url_for('academic_services.customer_account'))
            else:
                flash('รหัสผ่านไม่ถูกต้อง กรุณาลองอีกครั้ง', 'danger')
                return redirect(url_for('academic_services.login'))
        else:
            flash('ไม่พบบัญชีผู้ใช้งาน', 'danger')
            return redirect(url_for('academic_services.login'))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('academic_services/login.html', form=form)


@academic_services.route('/logout')
@login_required
def logout():
    logout_user()
    for key in ('identity.name', 'identity.auth_type'):
        session.pop(key, None)
    identity_changed.send(current_app._get_current_object(), identity=AnonymousIdentity())
    flash('ออกจากระบบเรียบร้อย', 'success')
    return redirect(url_for('academic_services.login'))


@academic_services.route('/forget_password', methods=['GET', 'POST'])
def forget_password():
    if current_user.is_authenticated:
        return redirect('academic_services.customer_account')
    form = ForgetPasswordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            user = ServiceCustomerAccount.query.filter_by(email=form.email.data).first()
            if not user:
                flash('ไม่พบบัญชีผู้ใช้งาน', 'warning')
                return render_template('academic_services/forget_password.html', form=form, errors=form.errors)
            serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'))
            token = serializer.dumps({'email': form.email.data})
            url = url_for('academic_services.reset_password', token=token, email=form.email.data, _external=True)
            message = 'Click the link below to reset the password.'\
                      ' กรุณาคลิกที่ลิงค์เพื่อทำการตั้งรหัสผ่านใหม่\n\n{}'.format(url)
            try:
                send_mail([form.email.data],
                          title='MUMT-MIS: Password Reset. ตั้งรหัสผ่านใหม่สำหรับระบบ MUMT-MIS',
                          message=message)
            except:
                flash('ระบบไม่สามารถส่งอีเมลได้กรุณาตรวจสอบอีกครั้ง'.format(form.email.data),'danger')
            else:
                flash('โปรดตรวจสอบอีเมลของท่านเพื่อทำการแก้ไขรหัสผ่านภายใน 20 นาที', 'success')
            return redirect(url_for('academic_services.login'))
        else:
            for er in form.errors:
                flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('academic_services/forget_password.html', form=form)


@academic_services.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    token = request.args.get('token')
    email = request.args.get('email')
    serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'))
    try:
        token_data = serializer.loads(token, max_age=72000)
    except:
        return 'รหัสสำหรับทำการตั้งค่า password หมดอายุหรือไม่ถูกต้อง'
    if token_data.get('email') != email:
        return 'Invalid JSON Web token.'

    user = ServiceCustomerAccount.query.filter_by(email=email).first()
    if not user:
        flash('ไม่พบชื่อบัญชีในฐานข้อมูล')
        return redirect(url_for('academic_services.login'))

    form = ResetPasswordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            user.password = form.new_password.data
            db.session.add(user)
            db.session.commit()
            flash('ตั้งรหัสผ่านใหม่เรียบร้อย', 'success')
            return redirect(url_for('academic_services.login'))
        else:
            for er in form.errors:
                flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('academic_services/reset_password.html', form=form)


@academic_services.route('/customer/index')
def customer_index():
    return render_template('academic_services/customer_index.html')


@academic_services.route('/customer/view', methods=['GET', 'POST'])
def customer_account():
    menu = request.args.get('menu')
    return render_template('academic_services/customer_account.html', menu=menu)


@academic_services.route('/customer/add', methods=['GET', 'POST'])
def create_customer_account(customer_id=None):
    menu = request.args.get('menu')
    email = request.form.get('email')
    confirm_email = request.form.get('confirm_email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    form = ServiceCustomerInfoForm()
    if form.validate_on_submit():
        customer = ServiceCustomerInfo()
        form.populate_obj(customer)
        db.session.add(customer)
        db.session.commit()
        if email == confirm_email and password == confirm_password:
            account = ServiceCustomerAccount(customer_info_id=customer.id, email=email, password=password)
            db.session.add(account)
            db.session.commit()
            serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'))
            token = serializer.dumps({'email': email})
            url = url_for('academic_services.account_successfully', token=token, email=email, _external=True,
                          _scheme='https')
            message = 'Click the link below to confirm.' \
                      ' กรุณาคลิกที่ลิงค์เพื่อทำการยืนยันการสมัครบัญชีระบบ MUMT-MIS\n\n{}'.format(url)
            send_mail([email], title='ยืนยันการสมัครบัญชีระบบ MUMT-MIS', message=message)
            flash('โปรดตรวจสอบอีเมลของท่านผ่านภายใน 20 นาที', 'success')
            return redirect(url_for('academic_services.login'))
        else:
            flash('อีเมลหรือรหัสผ่านไม่ตรงกัน', 'danger')
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('academic_services/create_customer.html', form=form, customer_id=customer_id,
                           menu=menu)


@academic_services.route('/successfully', methods=['GET', 'POST'])
def account_successfully():
    token = request.args.get('token')
    email = request.args.get('email')
    serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'))
    try:
        token_data = serializer.loads(token, max_age=72000)
    except:
        return 'รหัสสำหรับทำการสมัครบัญชีหมดอายุหรือไม่ถูกต้อง'
    if token_data.get('email') != email:
        return ' Invalid JSON Web token.'
    user = ServiceCustomerAccount.query.filter_by(email=email).first()
    customer = ServiceCustomerInfo.query.filter_by(id=user.customer_info_id).first()
    if not user:
        flash('ไม่พบชื่อบัญชีผู้ใช้งาน')
        return redirect(url_for('academic_services.login'))
    form = ServiceCustomerInfoForm(obj=customer)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(customer)
            customer.validated_datetime = arrow.now('Asia/Bangkok').datetime
            db.session.add(user)
            db.session.commit()
            flash('Verify account successfully', 'success')
            return redirect(url_for('academic_services.login'))
        else:
            for er in form.errors:
                flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('academic_services/account_successfully.html')


@academic_services.route('/customer/edit/<int:customer_id>', methods=['GET', 'POST'])
def edit_customer_account(customer_id):
    menu = request.args.get('menu')
    customer = ServiceCustomerInfo.query.get(customer_id)
    form = ServiceCustomerInfoForm(obj=customer)
    if form.validate_on_submit():
        form.populate_obj(customer)
        db.session.add(customer)
        db.session.commit()
        flash('แก้ไขข้อมูลบัญชีสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('academic_services/modal/edit_customer_modal.html', form=form, menu=menu,
                           customer_id=customer_id)


@academic_services.route('/edit_password', methods=['GET', 'POST'])
def edit_password():
    menu = request.args.get('menu')
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if new_password and confirm_password:
            if new_password == confirm_password:
                current_user.password = new_password
                db.session.add(current_user)
                db.session.commit()
                flash('รหัสผ่านแก้ไขแล้ว', 'success')
            else:
                flash('รหัสผ่านไม่ตรงกัน', 'danger')
        else:
            flash('กรุณากรอกรหัสใหม่', 'danger')
    return render_template('academic_services/edit_password.html', menu=menu)


@academic_services.route('/organization/view', methods=['GET', 'POST'])
def organization_list():
    menu = request.args.get('menu')
    organization = request.form.get('organization')
    if organization:
        organizations = ServiceCustomerOrganization.query.filter(ServiceCustomerOrganization.organization_name.like('%{}%'.format(organization)))
    else:
        organizations = []
    if request.headers.get('HX-Request') == 'true':
        return render_template('academic_services/partials/organization_list.html', organizations=organizations)
    return render_template('academic_services/organization_list.html', menu=menu)


@academic_services.route('/customer/organization/add/<int:customer_id>', methods=['GET', 'POST'])
def add_organization(customer_id):
    if request.method == 'POST':
        organization_id = request.args.get('organization_id')
        customer = ServiceCustomerInfo.query.get(customer_id)
        form = ServiceCustomerInfoForm(obj=customer)
        form.populate_obj(customer)
        customer.organization_id = organization_id
        db.session.add(customer)
        db.session.commit()
        flash('เพิ่มบริษัท/องค์กรในข้อมูลบัญชีของท่านสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@academic_services.route('/organization/add', methods=['GET', 'POST'])
@academic_services.route('/organization/edit/<int:organization_id>', methods=['GET', 'POST'])
def create_organization(organization_id=None):
    if organization_id:
        organization = ServiceCustomerOrganization.query.get(organization_id)
        form = ServiceCustomerOrganizationForm(obj=organization)
    else:
        form = ServiceCustomerOrganizationForm()
    if form.validate_on_submit():
        if organization_id is None:
            organization = ServiceCustomerOrganization()
        form.populate_obj(organization)
        db.session.add(organization)
        db.session.commit()
        if organization_id:
            flash('แก้ไขข้อมูลบริษัท/องค์กรสำเร็จ', 'success')
        else:
            flash('เพิ่มข้อมูลบริษัท/องค์กรสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('academic_services/modal/create_organization_modal.html', form=form,
                           organization_id=organization_id)