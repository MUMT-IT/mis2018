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
            name = form.get('name'),
            number = form.get('number')
        )
        db.session.add(procurement)
        db.session.commit()
        return render_template('procurement/index.html')
    return render_template('procurement/createprocurement.html')


@procurement.route('/home')
def index():
    print ("Test")
    return render_template('procurement/index.html')

