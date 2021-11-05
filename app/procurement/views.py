# -*- coding:utf-8 -*-
from flask import render_template, request, flash, redirect, url_for, session, jsonify

from . import procurementbp as procurement
from .models import ProcurementDetail
from ..main import db


@procurement.route('/add', methods=['GET','POST'])

def add_procurement():
    if request.method == 'POST':
        form = request.form
        procurement = ProcurementDetail(
        list = form.get('list'),
        type = form.get('type'),
        code = form.get('code'),
        location = form.get('location'),
        available = form.get('available')
        )
        db.session.add(procurement)
        db.session.commit()
        return render_template('procurement/index.html')
    return render_template('procurement/createprocurement.html')


@procurement.route('/home')
def index():
    return render_template('procurement/index.html')


@procurement.route('/alldata')
def view_procurement():
    procurement_list = []
    procurement_query = ProcurementDetail.query.all()
    for procurement in procurement_query:
        record = {}
        record["list"] = procurement.list
        record["type"] = procurement.type
        record["code"] = procurement.code
        record["location"] = procurement.location
        record["available"] = procurement.available
        procurement_list.append(record)
    return render_template('procurement/view_all_data.html', procurement_list=procurement_list)


