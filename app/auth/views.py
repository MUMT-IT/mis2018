from . import authbp as auth
from flask import render_template, redirect, request, url_for, flash
from flask_login import login_user
from ..models import User
from .forms import LoginForm

@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None:
            login_user(user, form.remember_me.data)
            print('you have logged in.', user.is_authenticated, user.email, user.username)
            next = request.args.get('next')
            if next is None or not next.startswith('/'):
                next = url_for('main.index')
            return redirect(next)
        flash('The user with this email address is not registered in this system.')
    return render_template('/auth/login.html', form=form)

