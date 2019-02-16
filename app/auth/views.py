from flask_admin.helpers import is_safe_url
from . import authbp as auth
from app.main import db
from flask import render_template, redirect, request, url_for, flash, abort, session
from flask_login import login_user, current_user
from app.staff.models import StaffAccount
from .forms import LoginForm


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        next = request.args.get('next')
        if not is_safe_url(next):
            return abort(400)
        return redirect(next)

    form = LoginForm()
    if form.validate_on_submit():
        # authenticate the user
        user = db.session.query(StaffAccount).filter_by(email=form.email.data).first()
        if user:
            status = login_user(user, form.remember_me.data)
            next = request.args.get('next')
            if not is_safe_url(next):
                return abort(400)
            # return redirect(next or url_for('index'))
            return redirect(next or url_for('index'))
        else:
            return redirect(url_for('auth.account'))
    return render_template('/auth/login.html', form=form)


@auth.route('/account')
def account():
    return 'Welcome to your account.'
