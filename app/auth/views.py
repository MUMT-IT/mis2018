# -*- coding: utf-8 -*-
import os
import secrets
from urllib.parse import urljoin

from flask_admin.helpers import is_safe_url

from . import authbp as auth
from app.main import db, mail
from app.main import app
from app.url_utils import external_url
from flask_mail import Message
from flask import (render_template, redirect, request,
                   url_for, flash, abort, session, current_app)
from flask_login import login_user, current_user, logout_user, login_required
from flask_principal import Identity, identity_changed, AnonymousIdentity, identity_loaded, UserNeed
from app.staff.models import StaffAccount, StaffLeaveApprover
from .forms import LoginForm, ForgotPasswordForm, ResetPasswordForm
from itsdangerous.url_safe import URLSafeTimedSerializer as TimedJSONWebSignatureSerializer
import requests
from requests_oauthlib import OAuth2Session
from linebot import (LineBotApi, WebhookHandler)

LINE_CLIENT_ID = app.config['LINE_CLIENT_ID']
LINE_CLIENT_SECRET = app.config['LINE_CLIENT_SECRET']
LINE_MESSAGE_API_ACCESS_TOKEN = app.config['LINE_MESSAGE_API_ACCESS_TOKEN']
LINE_MESSAGE_API_CLIENT_SECRET = app.config['LINE_MESSAGE_API_CLIENT_SECRET']

line_bot_api = LineBotApi(LINE_MESSAGE_API_ACCESS_TOKEN)
handler = WebhookHandler(LINE_MESSAGE_API_CLIENT_SECRET)

GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid',
]


def _is_google_login_enabled():
    return bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET'))


def _google_redirect_uri():
    return os.getenv('GOOGLE_REDIRECT_URI') or external_url('auth.google_callback')


def _google_oauth_session(state=None):
    return OAuth2Session(
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        redirect_uri=_google_redirect_uri(),
        scope=GOOGLE_SCOPES,
        state=state,
    )


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    # Set the identity user object
    identity.user = current_user

    # Add the UserNeed to the identity
    if hasattr(current_user, 'id'):
        identity.provides.add(UserNeed(current_user.id))

    # Assuming the User model has a list of roles, update the
    # identity with the roles that the user provides
    if hasattr(current_user, 'roles'):
        for role in current_user.roles:
            identity.provides.add(role.to_tuple())


@auth.route('/login', methods=['GET', 'POST'])
def login(is_admin=False):
    if current_user.is_authenticated:
        next_url = request.args.get('next', url_for('auth.account'))
        if is_safe_url(next_url):
            return redirect(next_url)
        else:
            return abort(400)

    linking_line = True if request.args.get('linking_line') == 'yes' else False

    form = LoginForm()
    if form.validate_on_submit():
        # authenticate the user
        user = db.session.query(StaffAccount).filter_by(email=form.email.data).first()
        if user:
            pwd = form.password.data
            if user.verify_password(pwd):
                if not user.is_active:
                    flash(u'Your account is inactive. บัญชีผู้ใช้นี้ไม่สามารถเข้าใช้งานได้', 'danger')
                    return redirect(url_for('auth.login'))
                status = login_user(user, form.remember_me.data)
                if not status:
                    flash(u'Your account is inactive. บัญชีผู้ใช้นี้ไม่สามารถเข้าใช้งานได้', 'danger')
                    return redirect(url_for('auth.login'))
                session['user_type'] = 'staff'
                identity_changed.send(current_app._get_current_object(), identity=Identity(user.id))
                # session.pop('_flashes', None)  # this line clears all unconsumed flash messages.
                next_url = request.args.get('next', url_for('index'))
                if not is_safe_url(next_url):
                    return abort(400)
                else:
                    flash(u'You have just logged in. ลงทะเบียนเข้าใช้งานเรียบร้อย', 'success')
                    return redirect(next_url)
            else:
                flash(u'Wrong password, try again. รหัสผ่านไม่ถูกต้อง กรุณาลองอีกครั้ง', 'danger')
                return redirect(url_for('auth.login'))
        else:
            flash(u'User does not exists. ไม่พบบัญชีผู้ใช้ในระบบ', 'danger')
            return redirect(url_for('auth.login'))

    return render_template('/auth/login.html',
                           form=form,
                           errors=form.errors,
                           linking_line=linking_line,
                           google_login_enabled=_is_google_login_enabled(), is_admin=is_admin)


@auth.route('/login-admin', methods=['GET', 'POST'])
def login_for_admin():
    return login(is_admin=True)


@auth.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        new_password2 = request.form.get('new_password2')
        if new_password and new_password2:
            if new_password == new_password2:
                current_user.password = new_password
                db.session.add(current_user)
                db.session.commit()
                flash(u'Password has been updated. รหัสผ่านแก้ไขแล้ว', 'success')
            else:
                flash(u'Passwords do not match. รหัสผ่านไม่ตรงกัน', 'danger')
        else:
            flash(u'Passwords are required. กรุณากรอกรหัสใหม่', 'danger')

    approvers = StaffLeaveApprover.query.filter_by(staff_account_id=current_user.id).all()

    return render_template('/auth/account.html',
                           approvers=approvers,
                           line_profile=session.get('line_profile', {}))


@auth.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    token = request.args.get('token')
    email = request.args.get('email')
    serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'))
    try:
        token_data = serializer.loads(token, max_age=72000)
    except:
        return u'Bad JSON Web token. You need a valid token to reset the password. รหัสสำหรับทำการตั้งค่า password หมดอายุหรือไม่ถูกต้อง'
    if token_data.get('email') != email:
        return u'Invalid JSON Web token.'

    user = StaffAccount.query.filter_by(email=email).first()
    if not user:
        flash(u'User does not exists. ไม่พบชื่อบัญชีในฐานข้อมูล')
        return redirect(url_for('auth.login'))

    form = ResetPasswordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            user.password = form.new_pass.data
            db.session.add(user)
            db.session.commit()
            flash(u'Password has been reset. ตั้งค่ารหัสผ่านใหม่เรียบร้อย', 'success')
            return redirect(url_for('auth.account'))
    return render_template('auth/reset_password.html', form=form, errors=form.errors)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('user_type', None)
    # Remove session keys set by Flask-Principal
    for key in ('identity.name', 'identity.auth_type'):
        session.pop(key, None)

    # Tell Flask-Principal the user is anonymous
    identity_changed.send(current_app._get_current_object(), identity=AnonymousIdentity())
    session.pop('line_profile', None)
    flash(u'Logged out successfully. ออกจากระบบเรียบร้อย', 'success')
    return redirect(url_for('auth.login'))


@auth.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect('auth.account')
    form = ForgotPasswordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            user = StaffAccount.query.filter_by(email=form.email.data).first()
            if not user:
                flash(u'User not found. ไม่พบบัญชีในฐานข้อมูล', 'warning')
                return render_template('auth/forgot_password.html', form=form, errors=form.errors)
            serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'))
            token = serializer.dumps({'email': form.email.data})
            url = external_url('auth.reset_password', token=token, email=form.email.data)
            message = u'Click the link below to reset the password.'\
                      u' กรุณาคลิกที่ลิงค์เพื่อทำการตั้งค่ารหัสผ่านใหม่\n\n{}'.format(url)
            try:
                send_mail(['{}@mahidol.ac.th'.format(form.email.data)],
                          title='MUMT-MIS: Password Reset. ตั้งรหัสผ่านใหม่สำหรับระบบ MUMT-MIS',
                          message=message)
            except:
                flash(u'Failed to send an email to {}. ระบบไม่สามารถส่งอีเมลได้กรุณาตรวจสอบอีกครั้ง'\
                      .format(form.email.data), 'danger')
            else:
                flash(u'Please check your mahidol.ac.th email for the link to reset the password within 20 minutes.'
                      u' โปรดตรวจสอบอีเมล mahidol.ac.th ของท่านเพื่อทำการแก้ไขรหัสผ่านภายใน 20 นาที', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html', form=form, errors=form.errors)


@auth.route('/google/login')
def google_login():
    if not _is_google_login_enabled():
        flash(u'Google sign-in is not configured yet.', 'warning')
        return redirect(url_for('auth.login'))

    next_url = request.args.get('next')
    if next_url and not is_safe_url(next_url):
        return abort(400)

    oauth = _google_oauth_session()
    authorization_base_url = 'https://accounts.google.com/o/oauth2/v2/auth'
    state = secrets.token_urlsafe(16)
    session['auth_google_oauth_state'] = state
    if next_url:
        session['auth_google_oauth_next'] = next_url
    authorization_url, _ = oauth.authorization_url(
        authorization_base_url,
        state=state,
        hd='mahidol.ac.th',
        prompt='select_account',
    )
    return redirect(authorization_url)


@auth.route('/google/callback')
def google_callback():
    if not _is_google_login_enabled():
        flash(u'Google sign-in is not configured yet.', 'warning')
        return redirect(url_for('auth.login'))

    expected_state = session.pop('auth_google_oauth_state', None)
    next_url = session.pop('auth_google_oauth_next', None)
    state = request.args.get('state')
    if not state or state != expected_state:
        flash(u'Invalid Google sign-in state. Please try again.', 'danger')
        return redirect(url_for('auth.login'))

    oauth = _google_oauth_session(state=state)
    try:
        oauth.fetch_token(
            token_url='https://oauth2.googleapis.com/token',
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
            authorization_response=request.url,
        )
        resp = oauth.get('https://www.googleapis.com/oauth2/v3/userinfo')
        resp.raise_for_status()
        profile = resp.json()
    except Exception as exc:
        current_app.logger.exception('Google sign-in failed during OAuth callback.')
        if current_app.debug:
            flash(u'Google sign-in failed: {}'.format(exc), 'danger')
        else:
            flash(u'Google sign-in failed. Please try again.', 'danger')
        return redirect(url_for('auth.login'))

    email = (profile.get('email') or '').strip().lower()
    if not email.endswith('@mahidol.ac.th'):
        flash(u'Please use your Mahidol Google account (@mahidol.ac.th).', 'danger')
        return redirect(url_for('auth.login'))

    email_local = email.split('@')[0]
    user = StaffAccount.query.filter_by(email=email_local).first()
    if not user:
        user = StaffAccount.query.filter_by(email=email).first()
    if not user:
        flash(u'User does not exists. ไม่พบบัญชีผู้ใช้ในระบบ', 'danger')
        return redirect(url_for('auth.login'))

    if not user.is_active:
        flash(u'Your account is inactive. บัญชีผู้ใช้นี้ไม่สามารถเข้าใช้งานได้', 'danger')
        return redirect(url_for('auth.login'))

    if not login_user(user, True):
        flash(u'Your account is inactive. บัญชีผู้ใช้นี้ไม่สามารถเข้าใช้งานได้', 'danger')
        return redirect(url_for('auth.login'))
    session['user_type'] = 'staff'
    identity_changed.send(current_app._get_current_object(), identity=Identity(user.id))
    flash(u'You have just logged in with Google. ลงทะเบียนเข้าใช้งานเรียบร้อย', 'success')

    if next_url and not is_safe_url(next_url):
        return abort(400)
    return redirect(next_url or url_for('index'))


@auth.route('/line')
@auth.route('/line/login')
def line_login():
    next_url = request.args.get('next') or request.referrer
    if next_url and not is_safe_url(next_url):
        return abort(400)
    if next_url:
        session['auth_line_oauth_next'] = next_url
    line_auth_url = 'https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id={}&redirect_uri={}&state=494959&scope=profile'
    line_auth_url = line_auth_url.format(LINE_CLIENT_ID, external_url('auth.line_callback'))
    return redirect(line_auth_url)


@auth.route('/line/callback')
def line_callback():
    if request.args.get('error') == 'access_denied':
        return 'User rejected the permission.'

    code = request.args.get('code')
    if code:
        data = {'Content-Type': 'application/x-www-form-urlencoded',
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': external_url('auth.line_callback'),
                'client_id': LINE_CLIENT_ID,
                'client_secret': LINE_CLIENT_SECRET
                }
        try:
            resp = requests.post('https://api.line.me/oauth2/v2.1/token', data=data)
        except:
            return 'Failed to retrieve access token.'
        else:
            if resp.status_code == 200:
                payload = resp.json()
            else:
                return 'Failed to get an access token'

            headers = {'Authorization': 'Bearer {}'.format(payload['access_token'])}
            profile = requests.get('https://api.line.me/v2/profile', headers=headers)
            if profile.status_code == 200:
                profile_data = profile.json()
                session['line_profile'] = profile_data
                return redirect(url_for('auth.line_profile'))
            else:
                return "Failed to retrieve a user's profile."
    return 'Failed to retrieve the access code from Line.'


@auth.route('/line/profile')
def line_profile():
    if 'line_profile' not in session:
        return redirect('auth.line_login')

    next_url = session.pop('auth_line_oauth_next', None)
    if next_url and not is_safe_url(next_url):
        return abort(400)

    userId = session['line_profile'].get('userId')
    line_user = StaffAccount.query.filter_by(line_id=userId).first()
    if line_user:
        if not line_user.is_active:
            flash(u'Your account is inactive. บัญชีผู้ใช้นี้ไม่สามารถเข้าใช้งานได้', 'danger')
            return redirect(url_for('auth.login'))
        # Automatically login the user with the associated Line account
        if not current_user.is_authenticated:
            if not login_user(line_user):
                flash(u'Your account is inactive. บัญชีผู้ใช้นี้ไม่สามารถเข้าใช้งานได้', 'danger')
                return redirect(url_for('auth.login'))
            session['user_type'] = 'staff'
        return redirect(next_url or url_for('index'))
    else:
        return render_template('auth/line_account.html',
                               profile=session['line_profile'],
                               line_account=line_user)


@auth.route('/line/account/link')
def link_line_account():
    if not session.get('line_profile'):
        return redirect(url_for('auth.line_login'))
    else:
        profile_data = session.get('line_profile')

    if current_user.is_authenticated:
        current_user.line_id = profile_data.get('userId'),
        db.session.add(current_user)
        db.session.commit()
        flash(u'ระบบได้ทำการเชื่อมบัญชีไลน์ของคุณแล้ว', 'success')
        return redirect(url_for('auth.account'))
    else:
        return redirect(url_for('auth.login', linking_line='yes', next=request.url))


@auth.route('/line/account/unlink')
@login_required
def unlink_line_account():
    if current_user.line_id:
        current_user.line_id = ''
        db.session.add(current_user)
        db.session.commit()
        del session['line_profile']
        flash(u'ระบบได้ทำการยกเลิกการเชื่อมบัญชีไลน์ของคุณแล้ว', 'success')
        return redirect(url_for('auth.account'))
    else:
        flash(u'บัญชีของท่านไม่ได้เชื่อมต่อกับไลน์', 'warning')
        return redirect(url_for('auth.account'))
