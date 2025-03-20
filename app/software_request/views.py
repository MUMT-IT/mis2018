from flask import render_template, redirect, flash, url_for
from flask_login import login_required
from app.software_request import software_request


@software_request.route('/')
@login_required
def index():
    return render_template('software_request/index.html')


@software_request.route('/condition')
def condition_for_service_request():
    return render_template('software_request/condition_page.html')


@software_request.route('/request/add')
def create_request():
    return render_template('software_request/create_request.html')