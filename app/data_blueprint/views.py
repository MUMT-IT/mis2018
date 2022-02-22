# -*- coding:utf-8 -*-

from . import data_bp
from app.main import db
from forms import CoreServiceForm
from models import CoreService
from flask import url_for, render_template, redirect, flash
from flask_login import current_user, login_required


@data_bp.route('/')
def index():
    return 'This is our data blueprint.'


@data_bp.route('/core-services/new', methods=['GET', 'POST'])
@login_required
def core_service_form():
    form = CoreServiceForm()
    if form.validate_on_submit():
        new_service = CoreService()
        form.populate_obj(new_service)
        new_service.creator_id = current_user.id
        db.session.add(new_service)
        db.session.commit()
        flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
        return redirect(url_for('data_bp.index'))
    return render_template('data_blueprint/core_services.html', form=form)
