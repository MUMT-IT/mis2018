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
        return 'You are already logged in.'

    form = LoginForm()
    if form.validate_on_submit():
        # authenticate the user
        user = db.session.query(StaffAccount).filter_by(email=form.email.data).first()
        if user:
            status = login_user(user, form.remember_me.data)
            next = request.args.get('next')
            print(status, next)
            if not is_safe_url(next):
                return abort(400)
            # return redirect(next or url_for('index'))
            return redirect(url_for('room.index'))
        else:
            flash('The user with this email address is not registered in this system.')
    return render_template('/auth/login.html', form=form)

