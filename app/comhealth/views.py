from flask import render_template
from flask_login import login_required
from . import comhealth
from .models import (ComHealthService, ComHealthRecord, ComHealthTestProfile,
                     ComHealthTestProfile, ComHealthTest)
from .models import ComHealthRecordSchema, ComHealthServiceSchema, ComHealthTestProfileSchema


@comhealth.route('/')
def index():
    services = ComHealthService.query.all()
    sv_schema = ComHealthServiceSchema(many=True)
    return render_template('comhealth/index.html',
                           services=sv_schema.dump(services).data)


@comhealth.route('/services/<int:service_id>')
def display_service_customers(service_id):
    service = ComHealthService.query.get(service_id)
    record_schema = ComHealthRecordSchema(many=True)
    return render_template('comhealth/service_customers.html',
                           service=service,
                           records=record_schema.dump(service.records).data)


@comhealth.route('/checkin/<int:record_id>')
def edit_record(record_id):
    record = ComHealthRecord.query.get(record_id)
    test_profiles = {}
    tests = ComHealthTest.query.all()

    for p in ComHealthTestProfile.query.all():
        test_profiles[p.name] = p.tests

    ordered_tests = []
    ordered_profiled_tests = []

    for p in record.test_profile_items:
        ordered_profiled_tests += p.profile.tests

    for item in record.test_items:
        if item not in ordered_profiled_tests:
            ordered_tests.append(item.test)

    return render_template('comhealth/edit_record.html',
                           record=record,
                           test_profiles=test_profiles,
                           ordered_tests=set(ordered_tests),
                           ordered_profiled_tests=ordered_profiled_tests,
                           tests=tests)


@comhealth.route('/tests')
def test_index():
    profiles = ComHealthTestProfile.query.all()
    pf_schema = ComHealthTestProfileSchema(many=True)
    return render_template('comhealth/test_profile.html',
                           profiles=pf_schema.dump(profiles).data)
