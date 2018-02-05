# -*- coding: utf-8 -*-
from flask import render_template, request, redirect, url_for
from . import foodbp as food
from models import Person, Farm, AgriType, SampleLot, Produce, Sample
from ..models import Province, District, Subdistrict
from ..main import db


@food.route('/')
def index():
    return render_template('food/index.html')


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
            return redirect(url_for('food.index'))

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


@food.route('/farm/<int:farm_id>/samplelot/', methods=['POST', 'GET'])
def add_samplelot(farm_id):
    errors = []
    if request.method == 'POST':
        collected_date = request.form.get('collected_date', '')
        if not collected_date:
            errors.append(u'โปรดกรอกข้อมูลวันที่เก็บผลผลิต')
        else:
            lot = SampleLot(
                collected_at=collected_date,
                farm_id=farm_id)
            db.session.add(lot)
            db.session.commit()
            return redirect(url_for('food.index'))

    farm = Farm.query.get(farm_id)
    return render_template('food/add_samplelot.html',
                           farm=farm, errors=errors)


@food.route('/farm/<int:farm_id>/tests/lots/<int:lot_id>/add/', methods=['POST', 'GET'])
def add_sample(farm_id, lot_id):
    errors = []
    if request.method == 'POST':
        produce_id = request.form.get('produce', '')
        if not produce_id:
            errors.append(u'กรุณาเลือกชนิดของผลผลิต')
        else:
            sample = Sample(produce_id=produce_id, lot_id=lot_id)
            db.session.add(sample)
            db.session.commit()
            return redirect(url_for('food.index'))

    farm = Farm.query.get(farm_id)
    lot = SampleLot.query.get(lot_id)
    produces = []
    for p in Produce.query.all():
        produces.append({
            'id': p.id,
            'name': p.name
        })

    return render_template('food/add_sample.html',
                           farm=farm, lot=lot, produces=produces)


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
            'id': farm.id,
            'ref_id': farm.ref_id(),
            'street': farm.street,
            'total_size': farm.estimated_total_size,
            'province': Province.query.get(farm.province_id).name,
            'district': District.query.get(farm.district_id).name,
            'subdistrict': Subdistrict.query.get(farm.subdistrict_id).name,
        })
    return render_template('food/farms.html', owner=owner, farms=farms)


@food.route('/farm/<int:farm_id>/tests/lots/')
def list_sample_lots(farm_id):
    farm = Farm.query.get(farm_id)
    return render_template('food/samplelots.html', farm=farm)


@food.route('/farm/<int:farm_id>/tests/lots/<int:lot_id>/samples/')
def list_samples(farm_id, lot_id):
    farm = Farm.query.get(farm_id)
    lot = SampleLot.query.get(lot_id)
    samples = []
    for s in lot.samples:
        produce = Produce.query.get(s.produce_id)
        samples.append({
            'id': s.id,
            'produce': produce.name
        })
    return render_template('food/samples.html',
                           farm=farm, lot=lot, samples=samples)


@food.route('/farm/<int:farm_id>/lots/<int:lot_id>/samples/<int:sample_id>/tests/pesticides/add/')
def add_pesticide_results(farm_id, lot_id, sample_id):
    farm = Farm.query.get(farm_id)
    lot = SampleLot.query.get(lot_id)
    sample = Sample.query.get(sample_id)
    return render_template('food/pest_results.html', farm=farm, lot=lot,
                           sample=sample)


@food.route('/farm/<int:farm_id>/lots/<int:lot_id>/samples/<int:sample_id>/tests/parasites/add/')
def add_parasite_results(farm_id, lot_id, sample_id):
    farm = Farm.query.get(farm_id)
    lot = SampleLot.query.get(lot_id)
    sample = Sample.query.get(sample_id)
    return render_template('food/parasit_results.html', farm=farm, lot=lot,
                           sample=sample)


@food.route('/farm/<int:farm_id>/lots/<int:lot_id>/samples/<int:sample_id>/tests/bacteria/add/')
def add_bacteria_results(farm_id, lot_id, sample_id):
    farm = Farm.query.get(farm_id)
    lot = SampleLot.query.get(lot_id)
    sample = Sample.query.get(sample_id)
    return render_template('food/bact_results.html', farm=farm, lot=lot,
                           sample=sample)


@food.route('/farm/<int:farm_id>/lots/<int:lot_id>/samples/<int:sample_id>/tests/toxicology/add/')
def add_toxicology_results(farm_id, lot_id, sample_id):
    farm = Farm.query.get(farm_id)
    lot = SampleLot.query.get(lot_id)
    sample = Sample.query.get(sample_id)
    return render_template('food/toxico_results.html', farm=farm, lot=lot,
                           sample=sample)


@food.route('/farm/produce/')
def list_produce():
    all_produce = Produce.query.all()
    return render_template('food/list_produce.html',
                           all_produce=all_produce)


@food.route('/farm/produce/add', methods=['POST', 'GET'])
def add_produce():
    errors = []
    if request.method == 'POST':
        pname = request.form['produce_name']
        produce = db.session.query(Produce).filter_by(name=pname).first()
        if produce:
            errors.append(u'{} มีในฐานข้อมูลแล้ว กรุณาเพิ่มรายการใหม่'.format(pname))
            print(errors)
        else:
            new_produce = Produce(name=pname)
            db.session.add(new_produce)
            db.session.commit()
            return redirect(url_for('food.index'))
    return render_template('food/add_produce.html', errors=errors)
