from flask import render_template
from flask_login import login_required
from . import comhealth
from .models import (ComHealthService, ComHealthRecord, ComHealthTestProfile,
                     ComHealthTestProfile, ComHealthTest, ComHealthTestGroup,
                     ComHealthTest)
from .models import (ComHealthRecordSchema, ComHealthServiceSchema, ComHealthTestProfileSchema,
                     ComHealthTestGroupSchema, ComHealthTestSchema)


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

    return render_template('comhealth/edit_record.html',
                           record=record)


@comhealth.route('/tests')
def test_index():
    profiles = ComHealthTestProfile.query.all()
    pf_schema = ComHealthTestProfileSchema(many=True)
    return render_template('comhealth/test_profile.html',
                           profiles=pf_schema.dump(profiles).data)


@comhealth.route('/test/groups')
@comhealth.route('/test/groups/<int:group_id>')
def test_group_index(group_id=None):
    if group_id:
        group = ComHealthTestGroup.query.get(group_id)
        return render_template('comhealth/test_group_edit.html', group=group)

    groups = ComHealthTestGroup.query.all()
    gr_schema = ComHealthTestGroupSchema(many=True)
    return render_template('comhealth/test_group.html',
                           groups=gr_schema.dump(groups).data)


@comhealth.route('/test/profiles/<int:profile_id>')
def test_profile(profile_id):
    profile = ComHealthTestProfile.query.get(profile_id)
    return render_template('comhealth/test_profile_edit.html', profile=profile)


@comhealth.route('/test/tests')
@comhealth.route('/test/tests/<int:group_id>')
def test_test_index(test_id=None):
    if test_id:
        test = ComHealthTest.query.get(test_id)
        return render_template('comhealth/test_group_edit.html', test=test)

    tests = ComHealthTest.query.all()
    t_schema = ComHealthTestSchema(many=True)
    return render_template('comhealth/test_test.html',
                           tests=t_schema.dump(tests).data)
