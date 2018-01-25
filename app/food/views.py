# -*- coding: utf-8 -*-
from flask import render_template, request, redirect, url_for
from . import foodbp as food
from models import Person, Farm, AgriType
from ..models import Province, District, Subdistrict
from ..main import db


@food.route('/farm/add/', methods=['POST', 'GET'])
def add_farm():
    errors = []
    if request.method == 'POST':
        street_addr = request.form.get('street_address', '')
        village = request.form.get('village', '')
        province_id = request.form.get('province', '')
        district_id = request.form.get('district', '')
        subdistrict_id = request.form.get('subdistrict', '')
        owner_id = request.form.get('owner_id', '')
        total_size = request.form.get('total_size', '')
        total_owned_size = request.form.get('total_owned_size', '')
        total_leased_size = request.form.get('total_leased_size', '')
        agritype_id = request.form.get('agritype', '')

        if not street_addr:
            errors.append(u'โปรดระบุที่อยู่ของแปลงเกษตร')
        if not village:
            errors.append(u'โปรดระบุหมู่บ้าน')
        if not province_id:
            errors.append(u'โปรดระบุจังหวัด')
        if not district_id:
            errors.append(u'โปรดระบุอำเภอ')
        if not subdistrict_id:
            errors.append(u'โปรดระบุตำบล')
        if not total_size:
            errors.append(u'โปรดระบุขนาดแปลงโดยรวม')
        if not agritype_id:
            errors.append(u'โปรดระบุประเภทของแปลงเกษตร')
        if not errors:
            owner = Person.query.get(int(owner_id))
            farm = Farm(street=street_addr,
                    province_id=int(province_id),
                    district_id=int(district_id),
                    subdistrict_id=int(subdistrict_id),
                    village=village,
                    estimated_total_size=float(total_size),
                    estimated_leased_size=float(total_leased_size),
                    estimated_owned_size=float(total_owned_size),
                    agritype_id=int(agritype_id),
                    )
            db.session.add(farm)
            owner.farms.append(farm)
            db.session.commit()
            return 'hello, world'

    owner_id = request.args.get('owner_id', None)
    if not owner_id:
        redirect(url_for('food.index'))

    owner = Person.query.get(owner_id)

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
            agritypes=agritypes,
            owner=owner,
            errors=errors)


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
            return redirect(url_for('food.list_owners'))
    return render_template('food/add_farm_owner.html', errors=errors)


@food.route('/farm/owner/')
def list_owners():
    owners = db.session.query(Person).order_by(Person.created_at)
    return render_template('food/owners.html',
            owners=owners)


@food.route('/farm/owned/<int:owner_id>/')
def list_owned_farm(owner_id):
    owner = Person.query.get(owner_id)
    farms = []
    for farm in owner.farms:
        farms.append({
            'ref_id': farm.ref_id(),
            'street': farm.street,
            'total_size': farm.estimated_total_size,
            'province': Province.query.get(farm.province_id).name,
            'district': District.query.get(farm.district_id).name,
            'subdistrict': Subdistrict.query.get(farm.subdistrict_id).name,
            })
    return render_template('food/farms.html', owner=owner, farms=farms)
