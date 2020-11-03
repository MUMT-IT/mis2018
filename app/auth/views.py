# -*- coding: utf-8 -*-
from flask_admin.helpers import is_safe_url

from . import authbp as auth
from app.main import db, csrf
from app.main import app
from flask import render_template, redirect, request, url_for, flash, abort, session, jsonify
from flask_login import login_user, current_user, logout_user, login_required
from app.staff.models import StaffAccount, StaffLeaveApprover
from .forms import LoginForm
import requests
from linebot import (LineBotApi, WebhookHandler)

LINE_CLIENT_ID = app.config['LINE_CLIENT_ID']
LINE_CLIENT_SECRET = app.config['LINE_CLIENT_SECRET']
LINE_MESSAGE_API_ACCESS_TOKEN = app.config['LINE_MESSAGE_API_ACCESS_TOKEN']
LINE_MESSAGE_API_CLIENT_SECRET = app.config['LINE_MESSAGE_API_CLIENT_SECRET']

line_bot_api = LineBotApi(LINE_MESSAGE_API_ACCESS_TOKEN)
handler = WebhookHandler(LINE_MESSAGE_API_CLIENT_SECRET)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        next = request.args.get('next')
        if not is_safe_url(next):
            return abort(400)
        if next:
            return redirect(next)
        else:
            return redirect(url_for('auth.account'))

    linking_line = True if request.args.get('linking_line') == 'yes' else False

    form = LoginForm()
    if form.validate_on_submit():
        # authenticate the user
        user = db.session.query(StaffAccount).filter_by(email=form.email.data).first()
        if user:
            pwd = form.password.data
            if user.verify_password(pwd):
                status = login_user(user, form.remember_me.data)
                next = request.args.get('next')
                if not is_safe_url(next):
                    return abort(400)
                return redirect(next or url_for('index'))
            else:
                flash(u'รหัสผ่านไม่ถูกต้อง กรุณาลองอีกครั้ง')
                return redirect(url_for('auth.login'))
        else:
            flash('User does not exists.')
            return redirect(url_for('auth.login'))

    return render_template('/auth/login.html', form=form, errors=form.errors, linking_line=linking_line)


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
                flash('Password has been updated.')
            else:
                flash('Passwords do not match. Try again.')
        else:
            flash('New passwords are missing. Try again.')

    approvers = StaffLeaveApprover.query.filter_by(staff_account_id=current_user.id).all()

    return render_template('/auth/account.html',
                           approvers=approvers,
                           line_profile=session.get('line_profile', {}))


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('line_profile', None)
    return redirect(url_for('auth.login'))


@auth.route('/line')
@auth.route('/line/login')
def line_login():
    line_auth_url = 'https://access.line.me/oauth2/v2.1/authorize?response_type=code&client_id={}&redirect_uri={}&state=494959&scope=profile'
    line_auth_url = line_auth_url.format(LINE_CLIENT_ID, url_for('auth.line_callback', _external=True, _scheme='https'))
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
                'redirect_uri': url_for('auth.line_callback', _external=True, _scheme='https'),
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

    userId = session['line_profile'].get('userId')
    line_user = StaffAccount.query.filter_by(line_id=userId).first()
    if line_user:
        # Automatically login the user with the associated Line account
        if not current_user.is_authenticated:
            login_user(line_user)
        return redirect(url_for('auth.account'))
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


