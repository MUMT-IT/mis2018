from flask import render_template, url_for, redirect
from flask_login import current_user, login_required
from . import km_bp as km


@km.route('/')
@login_required
def index():
    return render_template('km/index.html')


@km.route('/topics/add')
@login_required
def add_topic():
    return render_template('km/add.html')