from flask import render_template
from . import foodbp as food
from models import Person, Farm
from ..models import Province, District, Subdistrict


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
    agritypes = [{
        'name': 'GPA',
        'id': 1
        },
        {
            'name': 'Organic',
            'id': 2
            }
        ]
    return render_template('food/add_farm.html',
            provinces=provinces,
            districts=districts,
            subdistricts=subdistricts,
            agritypes=agritypes)


@food.route('/farm/owner/add/')
def add_farm_owner():
    return render_template('food/add_farm_owner.html')
