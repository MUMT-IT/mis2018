# -*- coding:utf-8 -*-
import os
import datetime

import requests
from werkzeug.utils import secure_filename

from . import docbp
from flask_login import current_user
from flask import render_template, url_for, request, flash, redirect, jsonify
from models import *
from pytz import timezone
from forms import *
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive


bkk = timezone('Asia/Bangkok')

# TODO: folder ID should be stored in the Org model to organize files by organization

FOLDER_ID = '1832el0EAqQ6NVz2wB7Ade6wRe-PsHQsu'

json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()


def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scopes)
    return GoogleDrive(gauth)


ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

@docbp.route('/')
def index():
    rounds = DocRound.query.all()
    return render_template('documents/index.html', rounds=rounds)


@docbp.route('/admin/rounds/<int:round_id>/documents')
def admin_view_round(round_id):
    round = DocRound.query.get(round_id)
    return render_template('documents/admin/docs.html', round=round)


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
    return render_template('documents/admin/index.html', rounds=rounds)


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
    return render_template('documents/admin/round_form.html', form=form)


@docbp.route('/admin/rounds/<int:round_id>/docs', methods=['GET', 'POST'])
def add_document(round_id):
    form = DocumentForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_doc = DocDocument()
            form.populate_obj(new_doc)
            new_doc.round_id = round_id
            drive = initialize_gdrive()
            if form.upload.data:
                upfile = form.upload.data
                filename = secure_filename(upfile.filename)
                upfile.save(filename)
                file_drive = drive.CreateFile({'title': filename,
                                               'parents': [{'id': FOLDER_ID, "kind": "drive#fileLink"}]})
                file_drive.SetContentFile(filename)
                try:
                    file_drive.Upload()
                    permission = file_drive.InsertPermission({'type': 'anyone',
                                                              'value': 'anyone',
                                                              'role': 'reader'})
                except:
                    flash('Failed to upload the attached file to the Google drive.', 'danger')
                else:
                    flash('The attached file has been uploaded to the Google drive', 'success')
                    new_doc.url = file_drive['id']
                    new_doc.file_name = filename
            new_doc.addedAt = bkk.localize(datetime.datetime.now())
            db.session.add(new_doc)
            db.session.commit()
            flash('New document has been added.', 'success')
            return redirect(url_for('doc.admin_view_round', round_id=round_id))
        else:
            for field, err in form.errors.items():
                flash('{} {}'.format(field, err), 'danger')
    return render_template('documents/admin/document_form.html', form=form, round_id=round_id)