# -*- coding:utf-8 -*-
from flask import render_template, url_for, redirect, request, flash
from flask_login import current_user, login_required
from sqlalchemy import desc

from . import km_bp as km
from .forms import KMTopicForm
from .models import *


@km.route('/')
@login_required
def index():
    topics = KMTopic.query.order_by(KMTopic.id.desc()).limit(5).all()
    return render_template('km/index.html', topics=topics)


@km.route('/process/<int:process_id>/topics/add', methods=['GET', 'POST'])
@login_required
def add_topic(process_id):
    form = KMTopicForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            topic = KMTopic()
            form.populate_obj(topic)
            topic.process_id = process_id
            topic.creator = current_user
            db.session.add(topic)
            db.session.commit()
            flash(u'New topic added. เพิ่มหัวข้อใหม่เรียบร้อยแล้ว', 'success')
            return redirect(url_for('km.detail_process', process_id=process_id))
        else:
            flash('Invalid form data', 'danger')
    return render_template('km/add.html', form=form, errors=form.errors)


@km.route('/processes')
@login_required
def list_processes():
    processes = KMProcess.query.all()
    return render_template('km/processes.html', processes=processes)


@km.route('/processes/<int:process_id>')
@login_required
def detail_process(process_id):
    process = KMProcess.query.get(process_id)
    return render_template('km/process_detail.html', process=process)


#TODO: add topic detail view