# -*- coding:utf-8 -*-
from flask import render_template, request, url_for, jsonify, flash, redirect
from flask_login import current_user
from pandas import read_excel
from werkzeug.utils import secure_filename

from . import alumnibp as alumni
from .forms import AlumniInformationForm
from .models import AlumniInformation
from ..comhealth.views import allowed_file
from ..main import db


@alumni.route('/landing')
def landing():
    return render_template('alumni/landing.html', name=current_user)


@alumni.route('/for-student/search-info', methods=['GET', 'POST'])
def search_student_info():
    return render_template('alumni/search_student_info.html')


@alumni.route('/api/data/search')
def get_student_search_data():
    query = AlumniInformation.query
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        AlumniInformation.th_firstname.ilike(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': AlumniInformation.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@alumni.route('/add', methods=['GET', 'POST'])
def add_alumni():
    form = AlumniInformationForm()

    if form.validate_on_submit():
        student = AlumniInformation()
        form.populate_obj(student)
        db.session.add(student)
        db.session.commit()
        flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return redirect(url_for('alumni.search_student_info'))
        # Check Error
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('alumni/add_alumni.html', form=form)


@alumni.route('/file/upload', methods=['GET', 'POST'])
def add_many_alumni():
    form = AlumniInformationForm()
    if form.validate_on_submit():
        if form.upload.data:
            upfile = form.upload.data
            filename = secure_filename(upfile.filename)
            upfile.save(filename)
            print(request.files['upload'])
            if allowed_file(upfile.filename):
                df = read_excel(request.files['upload'])
                print(df.head())
                df = df.fillna("")
                for idx, rec in df.iterrows():
                    no, student_id, th_title, th_firstname, th_lastname, contact, occupation, workplace, province = rec
                    alumni = AlumniInformation.query.filter_by(student_id=student_id).first()
                    if not alumni:
                        new_alumni = AlumniInformation(
                            student_id=student_id,
                            th_title=th_title,
                            th_firstname=th_firstname,
                            th_lastname=th_lastname,
                            contact=contact,
                            occupation=occupation,
                            workplace=workplace,
                            province=province,
                        )
                        db.session.add(new_alumni)
                db.session.commit()
                flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
                return redirect(url_for('alumni.search_student_info'))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('alumni/alumni_upload.html', form=form)