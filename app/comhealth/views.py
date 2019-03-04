from flask import render_template
from . import comhealth
from .models import (ComHealthService, ComHealthRecord,
                     ComHealthTestProfile, ComHealthTest)


@comhealth.route('/')
def index():
    services = ComHealthService.query.order_by('date desc').all()
    return render_template('comhealth/index.html',
                           services=services)


@comhealth.route('/services/<int:service_id>')
def display_service_customers(service_id):
    service = ComHealthService.query.get(service_id)
    return render_template('comhealth/service_customers.html',
                           service=service)


@comhealth.route('/records/<int:record_id>')
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
