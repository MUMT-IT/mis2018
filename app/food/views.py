# -*- coding: utf-8 -*-
from pandas import DataFrame, Series
from flask import render_template, request, redirect, url_for, jsonify
from . import foodbp as food
from models import (Person, Farm, AgriType, SampleLot, Produce,
                        Sample, ProduceBreed, GrownProduce, PesticideTest, PesticideResult,
                        ToxicoResult, ToxicoTest, BactResult, BactTest, HealthPerson,
                        HealthServices, SurveyResult)
from ..models import Province, District, Subdistrict
from ..main import db


@food.route('/')
def index():
    farms = []
    for farm in db.session.query(Farm).order_by(db.desc(Farm.created_at)):
        subdistrict = Subdistrict.query.get(farm.subdistrict_id).name
        district = District.query.get(farm.district_id).name
        province = Province.query.get(farm.province_id).name
        farms.append({
            'id': farm.id,
            'ref_id': farm.ref_id(),
            'sample_lots': farm.sample_lots,
            'street': farm.street,
            'subdistrict': subdistrict,
            'district': district,
            'province': province,
            'owners': farm.get_owners()
        })
    return render_template('food/index.html', farms=farms)


@food.route('/farm/add/', methods=['POST', 'GET'])
def add_farm():
    errors = []
    if request.method == 'POST':
        street_addr = request.form.get('street_address')
        village = request.form.get('village')
        province_id = request.form.get('province')
        district_id = request.form.get('district')
        subdistrict_id = request.form.get('subdistrict')
        owner_id = request.form.get('owner_id')
        total_size = request.form.get('total_size')
        total_owned_size = request.form.get('total_owned_size')
        total_leased_size = request.form.get('total_leased_size')
        agritype_id = request.form.get('agritype')
        produce = request.form.getlist('selected_produce')

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
            for prod in produce:
                prod_id, bred_id = map(int, prod.split(','))
                p = Produce.query.get(prod_id)
                b = ProduceBreed.query.get(bred_id)
                if p and b:
                    gp = GrownProduce(produce=p, breed=b)
                elif p:
                    gp = GrownProduce(produce=p, breed=b)
                farm.produce.append(gp)

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

    produce = []
    for prod in Produce.query.all():
        if prod.breeds:
            for breed in prod.breeds:
                produce.append({
                    'id': prod.id,
                    'name': prod.name,
                    'breed': breed.name,
                    'breed_id': breed.id,
                    'ref': u'{},{}'.format(prod.id, breed.id)
                })
        else:
            produce.append({
                'id': prod.id,
                'name': prod.name,
                'breed': '',
                'breed_id': 0,
                'ref': u'{},0'.format(prod.id)
            })

    produce = sorted(produce, key=lambda x: x['name'])

    return render_template('food/add_farm.html',
                           provinces=provinces,
                           districts=districts,
                           subdistricts=subdistricts,
                           agritypes=agritypes,
                           owner=owner,
                           errors=errors,
                           produce=produce)


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
            farm = Farm.query.get(farm_id)
            for grown_produce in farm.produce:
                # automatically adds samples from all grown produce
                sample = Sample(produce=grown_produce)
                lot.samples.append(sample)
            db.session.add(lot)
            db.session.commit()
            return redirect(url_for('food.index'))

    farm = Farm.query.get(farm_id)
    return render_template('food/add_samplelot.html',
                           farm=farm, errors=errors)


@food.route('/farm/<int:farm_id>/tests/lots/<int:lot_id>/add/', methods=['POST', 'GET'])
def add_sample(farm_id, lot_id):
    """Add sample to the sample lot."""

    errors = []
    if request.method == 'POST':
        produce_id = request.form.get('produce', '')
        if not produce_id:
            errors.append(u'กรุณาเลือกชนิดของผลผลิต')
        else:
            lot = SampleLot.query.get(lot_id)
            p = Produce.query.get(produce_id)
            gp = GrownProduce(produce=p)
            sample = Sample(produce=gp)
            lot.samples.append(sample)
            db.session.add(lot)
            db.session.commit()
            return redirect(url_for('food.list_samples',
                            farm_id=farm_id, lot_id=lot_id))

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
    health_info = set()
    for record in db.session.query(HealthPerson):
        name = u'{} {}'.format(record.firstname, record.lastname)
        health_info.add(name)
    return render_template('food/owners.html',
                           owners=owners, health_info=health_info)


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
            'sample_lots': farm.sample_lots,
            'province': Province.query.get(farm.province_id).name,
            'district': District.query.get(farm.district_id).name,
            'subdistrict': Subdistrict.query.get(farm.subdistrict_id).name,
        })
    return render_template('food/farms.html', owner=owner, farms=farms)


@food.route('/farm/<int:farm_id>/info/')
def display_farm_info(farm_id):
    farm = Farm.query.get(farm_id)
    province = Province.query.get(farm.province_id)
    district = District.query.get(farm.district_id)
    subdistrict = Subdistrict.query.get(farm.subdistrict_id)
    return render_template('food/farm_info.html',
                           farm=farm,
                           subdistrict=subdistrict,
                           district=district,
                           province=province
                           )


@food.route('/farm/edit/<int:farm_id>')
def edit_farm_info(farm_id):
    farm = Farm.query.get(farm_id)
    return render_template('food/edit_farm_info.html',
                            farm=farm)


@food.route('/farm/<int:farm_id>/tests/lots/')
def list_sample_lots(farm_id):
    farm = Farm.query.get(farm_id)
    return render_template('food/samplelots.html', farm=farm)


@food.route('/farm/<int:farm_id>/tests/lots/<int:lot_id>/samples/')
def list_samples(farm_id, lot_id):
    farm = Farm.query.get(farm_id)
    lot = SampleLot.query.get(lot_id)
    produces = Produce.query.all()
    samples = []
    for s in lot.samples:
        grown_produce = GrownProduce.query.get(s.produce_id)
        samples.append({
            'id': s.id,
            'produce': grown_produce.produce.name
        })
    return render_template('food/samples.html',
                           farm=farm, lot=lot,
                           samples=samples,
                           produces=produces)


@food.route('/farm/<int:farm_id>/lot/<int:lot_id>/sample/<int:sample_id>/tests')
def show_results(farm_id, lot_id, sample_id):
    farm = Farm.query.get(farm_id)
    sample = Sample.query.get(sample_id)
    lot = SampleLot.query.get(lot_id)
    return render_template('food/show_results.html', farm=farm, sample=sample, lot=lot)


@food.route('/farm/<int:farm_id>/lots/<int:lot_id>/samples/<int:sample_id>/tests/pesticides/add/')
def add_pesticide_results(farm_id, lot_id, sample_id):
    farm = Farm.query.get(farm_id)
    lot = SampleLot.query.get(lot_id)
    sample = Sample.query.get(sample_id)
    pest_tests = PesticideTest.query.all()
    result_dict = {}
    for res in sample.pesticide_results:
        result_dict[res.test.id] = res.value
    return render_template('food/pest_results.html', farm=farm, lot=lot,
                        sample=sample, pest_tests=pest_tests, result_dict=result_dict)


@food.route('/farm/results/pesticides/', methods=['POST'])
def add_pesticide_results_from_form():
    sample_id = request.form.get('sample_id', None)
    farm_id = request.form.get('farm_id', None)
    lot_id = request.form.get('lot_id', None)
    if sample_id:
        sample = Sample.query.get(sample_id)
        test_results_dict = {}
        for res in sample.pesticide_results:
            test_results_dict[res.test.id] = res
        for pt in PesticideTest.query.all():
            test_value = request.form.get(str(pt.id), None)
            if pt.id in test_results_dict:
                res = test_results_dict[pt.id]
                res.value = float(test_value) if test_value else None
            else:
                if test_value:
                    pest_test_result = PesticideResult(sample_id=sample.id,
                                        test_id=pt.id, value=float(test_value))
                else:
                    pest_test_result = PesticideResult(sample_id=sample.id,
                                        test_id=pt.id, value=None)
                sample.pesticide_results.append(pest_test_result)
        db.session.add(sample)
        db.session.commit()
        return redirect(url_for("food.list_samples", farm_id=farm_id, lot_id=lot_id))
    else:
        return "<h3>An error has occurred. Please contact the system admin.</h3>"


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
    bact_tests = BactTest.query.all()
    result_dict = {}
    for res in sample.bact_results:
        result_dict[res.test.id] = res.value
    return render_template('food/bact_results.html', farm=farm, lot=lot,
                           sample=sample, bact_tests=bact_tests, result_dict=result_dict)


@food.route('/farm/results/bacteria/', methods=['POST'])
def add_bact_results_from_form():
    sample_id = request.form.get('sample_id', None)
    farm_id = request.form.get('farm_id', None)
    lot_id = request.form.get('lot_id', None)
    if sample_id:
        sample = Sample.query.get(sample_id)
        test_results_dict = {}
        for res in sample.bact_results:
            test_results_dict[res.test.id] = res
        for pt in BactTest.query.all():
            test_value = request.form.get(str(pt.id), None)
            if pt.id in test_results_dict:
                res = test_results_dict[pt.id]
                res.value = test_value if test_value else None
            else:
                bact_test_result = BactResult(sample_id=sample.id,
                                    test_id=pt.id, value=test_value)
                sample.bact_results.append(bact_test_result)
        db.session.add(sample)
        db.session.commit()
        return redirect(url_for("food.list_samples", farm_id=farm_id, lot_id=lot_id))
    else:
        return "<h3>An error has occurred. Please contact the system admin.</h3>"


@food.route('/farm/<int:farm_id>/lots/<int:lot_id>/samples/<int:sample_id>/tests/toxicology/add/')
def add_toxicology_results(farm_id, lot_id, sample_id):
    farm = Farm.query.get(farm_id)
    lot = SampleLot.query.get(lot_id)
    sample = Sample.query.get(sample_id)
    tox_tests = ToxicoTest.query.all()
    result_dict = {}
    for res in sample.toxico_results:
        result_dict[res.test.id] = res.value
    return render_template('food/toxico_results.html', farm=farm, lot=lot,
                        sample=sample, tox_tests=tox_tests, result_dict=result_dict)

@food.route('/farm/results/heavymetals/', methods=['POST'])
def add_toxico_results_from_form():
    sample_id = request.form.get('sample_id', None)
    farm_id = request.form.get('farm_id', None)
    lot_id = request.form.get('lot_id', None)
    if sample_id:
        sample = Sample.query.get(sample_id)
        test_results_dict = {}
        for res in sample.toxico_results:
            test_results_dict[res.test.id] = res
        for pt in ToxicoTest.query.all():
            test_value = request.form.get(str(pt.id), None)
            if pt.id in test_results_dict:
                res = test_results_dict[pt.id]
                res.value = float(test_value) if test_value else None
            else:
                if test_value:
                    toxico_test_result = ToxicoResult(sample_id=sample.id,
                                        test_id=pt.id, value=float(test_value))
                else:
                    toxico_test_result = ToxicoResult(sample_id=sample.id,
                                        test_id=pt.id, value=None)
                sample.toxico_results.append(toxico_test_result)
        db.session.add(sample)
        db.session.commit()
        return redirect(url_for("food.list_samples", farm_id=farm_id, lot_id=lot_id))
    else:
        return "<h3>An error has occurred. Please contact the system admin.</h3>"


@food.route('/farm/produce/', methods=['POST', 'GET'])
def list_produce():
    if request.method == 'POST':
        produce = request.form.get('produce')
        if produce:
            db.session.add(Produce(name=produce))
            db.session.commit()
    all_produce = Produce.query.all()
    return render_template('food/list_produce.html',
                           all_produce=all_produce)


@food.route('/farm/produce/<int:produce_id>')
def display_produce_info(produce_id=None):
    if produce_id:
        produce = Produce.query.get(produce_id)
        if produce:
            farms = []
            province_flt = request.args.get('province', None)
            for grown_produce in produce.grown_produces:
                for farm in grown_produce.farms:
                    subdistrict = Subdistrict.query.get(farm.subdistrict_id).name
                    district = District.query.get(farm.district_id).name
                    province = Province.query.get(farm.province_id).name
                    estimated_area_size = float(grown_produce.estimated_area) if \
                                            grown_produce.estimated_area is not None else 0
                    if not province_flt or province_flt == province:
                        farms.append({
                            'id': farm.id,
                            'ref_id': farm.ref_id(),
                            'total_size': farm.estimated_total_size,
                            'total_produce_area_size': estimated_area_size,
                            'street': farm.street,
                            'subdistrict': subdistrict,
                            'district': district,
                            'province': province,
                            'owners': farm.get_owners()
                        })
            if farms:
                data_farms = DataFrame(farms)
                plant_counts = data_farms.groupby(['province'])['province'].count()
                area_total = data_farms.groupby(['province'])['total_size'].sum()
                prod_area_total = data_farms.groupby(['province'])['total_produce_area_size'].sum()
                return render_template("food/produce_info.html",
                                       produce=produce, farms=farms,
                                       plant_counts=plant_counts,
                                       area_total=area_total,
                                       prod_area_total=prod_area_total)
            else:
                return render_template("food/produce_info.html",
                                       produce=produce, farms=farms,
                                       plant_counts=Series(),
                                       area_total=Series(),
                                       prod_area_total=Series())

    else:
        return 'No produce ID specified.'


@food.route('/farm/producer/', methods=['GET'])
def list_farm_producer():
    produce = request.form.get('produce', None)
    if produce:
        farms = db.session.add(Farm)

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


@food.route('/health/person/')
def show_health_data():
    firstname = request.args.get('firstname', '')
    lastname = request.args.get('lastname', '')
    person = db.session.query(HealthPerson).filter(
                    HealthPerson.firstname==firstname,
                    HealthPerson.lastname==lastname).first()
    if person:
        return render_template('food/health.html',
                    person=person, genders={u'1': u'ชาย', u'2': u'หญิง'})
    else:
        return 'Data not found.'


@food.route('/health/person/lab/')
def display_health_lab_results():
    cmscode = request.args.get('cmscode', None)
    serviceno = request.args.get('serviceno', None)
    service = db.session.query(HealthServices).filter(HealthServices.serviceno==serviceno).first()
    person = db.session.query(HealthPerson).filter(HealthPerson.cmscode==cmscode).first()
    genders = {u'1': u'ชาย', u'2': u'หญิง'}
    return render_template('food/health_lab.html', person=person, service=service,genders=genders)


@food.route('/survey/results/')
def display_survey_results():
    firstname = request.args.get('firstname', None)
    lastname = request.args.get('lastname', None)
    survey = SurveyResult.query.filter(SurveyResult.firstname==firstname, SurveyResult.lastname==lastname).first()
    if survey:
        questions = sorted(survey.questions.iteritems(), key=lambda x: x[1])
        return render_template('food/show_survey_results.html',
                        survey=survey, questions=questions)
    else:
        return 'Not survey data from this person yet.'