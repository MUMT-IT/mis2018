# -*- coding:utf-8 -*-
from . import docbp
from flask_login import current_user
from flask import render_template, url_for, request, flash, redirect
from models import *
from forms import *


@docbp.route('/')
def index():
    rounds = DocRound.query.all()
    return render_template('documents/index.html', rounds=rounds)


@docbp.route('/rounds/<int:round_id>/documents')
def view_round(round_id):
    round = DocRound.query.get(round_id)
    records = []
    for doc in round.documents.all():
        for rec in doc.recv_records:
            if rec.staff == current_user:
                records.append(rec)
    return render_template('documents/round.html', round=round, records=records)


@docbp.route('/documents/<int:rec_id>')
def view_recv_record(rec_id):
    rec = DocReceiveRecord.query.get(rec_id)
    return render_template('documents/recv_record.html', rec=rec)


@docbp.route('/admin')
def admin_index():
    rounds = DocRound.query.all()
    return render_template('documents/admin_index.html', rounds=rounds)


@docbp.route('/admin/rounds', methods=['GET', 'POST'])
def add_round():
    form = RoundForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_round = DocRound()
            form.populate_obj(new_round)
            db.session.add(new_round)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
            return redirect(url_for('doc.admin_index'))
        else:
            for err in form.errors:
                flash('{}'.format(err), 'danger')
    return render_template('documents/round_edit.html', form=form)


@docbp.route('/admin/docs', methods=['GET', 'POST'])
def add_document():
    form = DocumentForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            pass
    return render_template('documents/document_form.html', form=form)
