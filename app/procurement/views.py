# -*- coding:utf-8 -*-
from flask import render_template, request, flash, redirect, url_for, session, jsonify, Flask

from . import procurementbp as procurement
from .models import ProcurementDetail
from ..main import db
from flask_qrcode import QRcode


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
        record["id"] = procurement.id
        record["list"] = procurement.list
        record["type"] = procurement.type
        record["code"] = procurement.code
        record["location"] = procurement.location
        record["available"] = procurement.available
        procurement_list.append(record)
    return render_template('procurement/view_all_data.html', procurement_list=procurement_list)

@procurement.route('/createqrcode')
def create_qrcode():
    return render_template('procurement/generate_qrcode.html')

@procurement.route('/explanation')
def explanation():
    return render_template('procurement/explanation.html')

@procurement.route('/edit/<int:procurement_id>', methods=['GET','POST'])
def edit_procurement(procurement_id):
    procurement = ProcurementDetail.query.get(procurement_id)
    if request.method == 'POST':
        form = request.form
        procurement.list = form.get('list')
        procurement.type = form.get('type')
        procurement.code = form.get('code')
        procurement.location = form.get('location')
        procurement.available = form.get('available')
        db.session.add(procurement)
        db.session.commit()
        flash(u'แก้ไขข้อมูลเรียบร้อย', 'success')
        return redirect(url_for('procurement.view_procurement'))
    return render_template('procurement/edit_procurement.html', procurement=procurement)


procurement = Flask(__name__)

# this line is important
QRcode(procurement)

@procurement.route('/qrcode', methods=['POST', 'GET'])
def view_qrcode():
    qr = None
    if request.method == 'POST':
        qr = request.form['code']
    return render_template('procurement/view_qrcode.html', qr=qr)


if __name__ == '__main__':
    procurement.run(port=5000, debug=True)



