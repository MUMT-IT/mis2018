# -*- coding:utf-8 -*-

from flask import render_template, flash, redirect, url_for

from app.complaint_tracker import complaint_tracker
from app.complaint_tracker.forms import ComplaintRecordForm
from app.complaint_tracker.models import *


@complaint_tracker.route('/')
def index():
    categories = ComplaintCategory.query.all()
    return render_template('complaint_tracker/index.html', categories=categories)


@complaint_tracker.route('/issue/<int:topic_id>', methods=['GET', 'POST'])
def new_record(topic_id):
    topic = ComplaintTopic.query.get(topic_id)
    form = ComplaintRecordForm()
    if form.validate_on_submit():
        record = ComplaintRecord()
        form.populate_obj(record)
        record.topic = topic
        db.session.add(record)
        db.session.commit()
        flash(u'ส่งคำร้องเรียบร้อย', 'success')
        return redirect(url_for('comp_tracker.index'))
    return render_template('complaint_tracker/record_form.html', form=form, topic=topic)
