from app.main import app
from app.academic_services import academic_services
from app.academic_services.forms import (StaffCustomerInfoForm, LoginForm, ForgetPasswordForm, ResetPasswordForm,
                                         StaffEditCustomerInfoForm)
from app.academic_services.models import *
from flask import render_template, flash, redirect, url_for, request, current_app, abort, session
from flask_login import login_user, current_user, logout_user, login_required
from flask_principal import Identity, identity_changed, AnonymousIdentity, identity_loaded, UserNeed
from flask_admin.helpers import is_safe_url
from app.staff.models import StaffAccount, StaffCustomerInfo
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
        next_url = request.args.get('next', url_for('academic_services.customer_index'))
        if is_safe_url(next_url):
            return redirect(next_url)
        else:
            return abort(400)
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(StaffAccount).filter_by(email=form.email.data).first()
        if user:
            pwd = form.password.data
            if user.verify_password(pwd):
                status = login_user(user)
                identity_changed.send(current_app._get_current_object(), identity=Identity(user.id))
                next_url = request.args.get('next', url_for('index'))
                if not is_safe_url(next_url):
                    return abort(400)
                else:
                    flash('ลงทะเบียนเข้าใช้งานเรียบร้อย', 'success')
                    return redirect(url_for('academic_services.customer_index'))
            else:
                flash('รหัสผ่านไม่ถูกต้อง กรุณาลองอีกครั้ง', 'danger')
                return redirect(url_for('academic_services.login'))
        else:
            flash('ไม่พบบัญชีผู้ใช้ในระบบ', 'danger')
            return redirect(url_for('academic_services.login'))

    return render_template('academic_services/login.html', form=form, errors=form.errors)


@academic_services.route('/logout')
@login_required
def logout():
    logout_user()
    # Remove session keys set by Flask-Principal
    for key in ('identity.name', 'identity.auth_type'):
        session.pop(key, None)

    identity_changed.send(current_app._get_current_object(), identity=AnonymousIdentity())
    flash('ออกจากระบบเรียบร้อย', 'success')
    return redirect(url_for('academic_services.login'))


@academic_services.route('/forget_password', methods=['GET', 'POST'])
def forget_password():
    if current_user.is_authenticated:
        return redirect('academic_services.customer_index')
    form = ForgetPasswordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            user = StaffAccount.query.filter_by(email=form.email.data).first()
            if not user:
                flash('ไม่พบบัญชีในฐานข้อมูล', 'warning')
                return render_template('academic_services/forget_password.html', form=form, errors=form.errors)
            serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'))
            token = serializer.dumps({'email': form.email.data})
            url = url_for('academic_services.reset_password', token=token, email=form.email.data, _external=True)
            message = 'Click the link below to reset the password.'\
                      ' กรุณาคลิกที่ลิงค์เพื่อทำการตั้งค่ารหัสผ่านใหม่\n\n{}'.format(url)
            try:
                send_mail([form.email.data],
                          title='MUMT-MIS: Password Reset. ตั้งรหัสผ่านใหม่สำหรับระบบ MUMT-MIS',
                          message=message)
            except:
                flash('ระบบไม่สามารถส่งอีเมลได้กรุณาตรวจสอบอีกครั้ง'.format(form.email.data),'danger')
            else:
                flash('โปรดตรวจสอบอีเมลของท่านเพื่อทำการแก้ไขรหัสผ่านภายใน 20 นาที', 'success')
            return redirect(url_for('academic_services.login'))
    return render_template('academic_services/forget_password.html', form=form, errors=form.errors)


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

    user = StaffAccount.query.filter_by(email=email).first()
    if not user:
        flash('ไม่พบชื่อบัญชีในฐานข้อมูล')
        return redirect(url_for('academic_services.login'))

    form = ResetPasswordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            user.password = form.new_password.data
            db.session.add(user)
            db.session.commit()
            flash('ตั้งค่ารหัสผ่านใหม่เรียบร้อย', 'success')
            return redirect(url_for('academic_services.login'))
    return render_template('academic_services/reset_password.html', form=form, errors=form.errors)


@academic_services.route('/customer/index')
def customer_index():
    return render_template('academic_services/customer_index.html')


@academic_services.route('/customer/view', methods=['GET', 'POST'])
def customer_account():
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
    return render_template('academic_services/customer_account.html')


@academic_services.route('/customer/add', methods=['GET', 'POST'])
def create_customer():
    email = request.form.get('email')
    confirm_email = request.form.get('confirm_email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    form = StaffCustomerInfoForm()
    if form.validate_on_submit():
        customer = StaffCustomerInfo()
        form.populate_obj(customer)
        db.session.add(customer)
        db.session.commit()
        if email == confirm_email and password == confirm_password:
            account = StaffAccount(customer_info_id=customer.id, email=email, password=password)
            db.session.add(account)
            db.session.commit()
            flash('สร้างบัญชีสำเร็จ', 'success')
            return redirect(url_for('academic_services.customer_index'))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('academic_services/create_customer.html', form=form)


@academic_services.route('/customer/edit/<int:customer_id>', methods=['GET', 'POST'])
def edit_customer(customer_id=None):
    customer = StaffCustomerInfo.query.get(customer_id)
    form = StaffEditCustomerInfoForm(obj=customer)
    if form.validate_on_submit():
        form.populate_obj(customer)
        for account in customer.staff_account:
            account.line_id = None
        db.session.add(customer)
        db.session.commit()
        flash('แก้ไขข้อมูลสำเร็จ', 'success')
        return redirect(url_for('academic_services.customer_index'))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('academic_services/edit_customer.html', form=form, customer_id=customer_id)