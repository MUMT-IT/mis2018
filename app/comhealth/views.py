from datetime import datetime
from flask import render_template, flash, redirect, url_for
from flask_login import login_required
from app.main import db
from . import comhealth
from .forms import ServiceForm
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



@comhealth.route('/services/new', methods=['GET', 'POST'])
def add_service():
    form = ServiceForm()
    if form.validate_on_submit():
        try:
            service_date = datetime.strptime(form.service_date.data, '%Y-%m-%d')
        except ValueError:
            flash('Date data not valid.')
        else:
            new_service = ComHealthService(location=form.location.data,
                                           date=service_date)
            db.session.add(new_service)
            db.session.commit()
            flash('The schedule has been updated.')
            return redirect(url_for('comhealth.index'))

    return render_template('comhealth/new_schedule.html', form=form)


@comhealth.route('/services/edit/<int:service_id>', methods=['GET', 'POST'])
def edit_service(service_id=None):
    if service_id:
        service = ComHealthService.query.get(service_id)
        return render_template('comhealth/edit_service.html', service=service)



@comhealth.route('/services/profiles/<int:service_id>')
@comhealth.route('/services/profiles/<int:service_id>/<int:profile_id>')
def add_service_profile(service_id=None, profile_id=None):
    if not (service_id and profile_id):
        service = ComHealthService.query.get(service_id)
        profiles = [pf for pf in ComHealthTestProfile.query.all() if pf not in service.profiles]
        return render_template('comhealth/profile_list.html',
                               profiles=profiles,
                               service=service)

    service = ComHealthService.query.get(service_id)
    profile = ComHealthTestProfile.query.get(profile_id)
    service.profiles.append(profile)
    db.session.add(service)
    db.session.commit()
    flash('Profile {} has been added to the service.'.format(profile.name))
    return redirect(url_for('comhealth.edit_service', service_id=service.id))


@comhealth.route('/services/profiles/delete/<int:service_id>/<int:profile_id>')
def delete_service_profile(service_id=None, profile_id=None):
    if service_id and profile_id:
        service = ComHealthService.query.get(service_id)
        kept_profiles = []
        for profile in service.profiles:
            if profile.id != profile_id:
                kept_profiles.append(profile)

        service.profiles = kept_profiles
        db.session.add(service)
        db.session.commit()
        flash('Profile {} has been removed to the service.'.format(profile.name))

    return redirect(url_for('comhealth.edit_service', service_id=service.id))
