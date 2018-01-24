# -*- coding: utf-8 -*-
from flask import render_template, request
from . import foodbp as food
from models import Person, Farm, AgriType
from ..models import Province, District, Subdistrict
from ..main import db


@food.route('/farm/add/')
def add_farm():
    provinces = []
    districts = []
    subdistricts = []
    for pv in Province.query.all():
        provinces.append({
            'name': pv.name,
            'id': pv.id,
            'code': pv.code
            })

    for ds in District.query.all():
        districts.append({
            'name': ds.name,
            'id': ds.id,
            'code': ds.code,
            'province_id': ds.province_id
            })
    for sd in Subdistrict.query.all():
        subdistricts.append({
            'name': sd.name,
            'id': sd.id,
            'code': sd.code,
            'district_id': sd.district_id
            })
    provinces = sorted(provinces, key=lambda x: x['name'])
    districts = sorted(districts, key=lambda x: x['name'])
    subdistricts = sorted(subdistricts, key=lambda x: x['name'])
    agritypes = []
    for ag in AgriType.query.all():
        agritypes.append({
        'name': ag.name,
        'id': ag.id,
        'desc': ag.desc
        })

    return render_template('food/add_farm.html',
            provinces=provinces,
            districts=districts,
            subdistricts=subdistricts,
            agritypes=agritypes)


@food.route('/farm/owner/add/', methods=['GET', 'POST'])
def add_farm_owner():
    errors = []
    if request.method == 'POST':
        firstname = request.form.get('firstname', '')
        lastname = request.form.get('lastname', '')
        pid = request.form.get('pid', '')
        if not firstname:
            errors.append(u'โปรดระบุชื่อจริง')
        if not lastname:
            errors.append(u'โปรดระบุชื่อนามสกุล')
        if not pid or not pid.isdigit() or len(pid) != 13:
            errors.append(u'โปรดระบุรหัสบัตรประชาชนให้ถูกต้อง')
        else:
            existing_pid = Person.query.filter_by(pid=pid).first()
            if existing_pid:
                errors.append(u'รหัสบัตรประชาชนที่ท่านกรอก มีในฐานข้อมูลแล้ว')
        if not errors:
            person = Person(firstname=firstname,
                            lastname=lastname,
                            pid=pid)
            db.session.add(person)
            db.session.commit()
            return "<h1>Data Submitted.</h1>"
    return render_template('food/add_farm_owner.html', errors=errors)
