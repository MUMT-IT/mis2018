# -*- coding: utf-8 -*-
import json
import pandas as pd
import os
from bahttext import bahttext
from datetime import datetime
from decimal import Decimal
from pandas import read_excel, isna
from flask_weasyprint import HTML, render_pdf
from sqlalchemy.orm.attributes import flag_modified
from flask import (render_template, flash, redirect,
                   url_for, session, stream_with_context,
                   request, send_file, send_from_directory,
                   Response, jsonify)
from flask_login import login_required
from collections import OrderedDict, defaultdict
import pytz
from . import comhealth
from .forms import (ServiceForm, TestProfileForm, TestListForm,
                    TestForm, TestGroupForm, CustomerForm)
from .models import *
from flask_admin import BaseView, expose

bangkok = pytz.timezone('Asia/Bangkok')

ALLOWED_EXTENSIONS = ['xlsx', 'xls']


@comhealth.route('/')
def landing():
    return render_template('comhealth/landing.html')


@comhealth.route('/finance', methods=('GET', 'POST'))
def finance_landing():
    cur_year = datetime.today().date().year + 543
    receipt_ids = ComHealthReceiptID.query.filter_by(buddhist_year=cur_year)
    if request.method == 'POST':
        code_id = request.form.get('code_id')
        venue = request.form.get('venue')
        if code_id:
            session['receipt_venue'] = venue
            session['receipt_code_id'] = int(code_id)
            return redirect(url_for('comhealth.finance_index'))
        else:
            flash('No receipt code ID specified.')
    return render_template('comhealth/finance_landing.html',
                           receipt_ids=receipt_ids)

@comhealth.route('/services/finance')
def finance_index():
    services = ComHealthService.query.all()
    services_data = []
    for sv in services:
        d = {
            'id': sv.id,
            'date': sv.date,
            'location': sv.location,
            'registered': len(sv.records),
            'checkedin': len([r for r in sv.records if r.checkin_datetime is not None])
        }
        services_data.append(d)
    return render_template('comhealth/finance_index.html', services=services_data)


@comhealth.route('/services/<int:service_id>/finance/summary')
def finance_summary(service_id):
    service = ComHealthService.query.get(service_id)
    receipts = defaultdict(list)
    counts = defaultdict(list)
    totals = defaultdict(Decimal)
    for rec in service.records:
        for receipt in rec.receipts:
            if not receipt.book_number:
                continue
            book = receipt.book_number[:3]
            count = int(receipt.book_number[3:])
            total = 0
            for invoice in receipt.invoices:
                if invoice.billed:
                    total += invoice.test_item.price or invoice.test_item.test.default_price
            receipts[book].append((receipt, total))
            totals[book] += total
            counts[book].append(count)
    return render_template('comhealth/finance_summary.html', service=service, receipts=receipts, counts=counts, totals=totals)


@comhealth.route('/api/services/<int:service_id>/records')
def api_finance_record(service_id):
    service = ComHealthService.query.get(service_id)
    records = [rec for rec in service.records if rec.is_checked_in]
    record_schema = ComHealthRecordSchema(many=True)
    return jsonify(record_schema.dump(records).data)


@comhealth.route('/services/<int:service_id>/records')
def finance_record(service_id):
    service = ComHealthService.query.get(service_id)
    return render_template('comhealth/finance_records.html', service=service)


@comhealth.route('/customers')
def index():
    services = ComHealthService.query.all()
    services_data = []
    for sv in services:
        d = {
            'id': sv.id,
            'date': sv.date,
            'location': sv.location,
            'registered': len(sv.records),
            'checkedin': len([r for r in sv.records if r.checkin_datetime is not None])
        }
        services_data.append(d)
    # sv_schema = ComHealthServiceSchema(many=True)
    return render_template('comhealth/index.html', services=services_data)


@comhealth.route('/api/services/<int:service_id>/search')
def search_service_customer(service_id):
    service = ComHealthService.query.get(service_id)
    record_schema = ComHealthRecordSchema(many=True)
    return jsonify(record_schema.dump(service.records).data)


@comhealth.route('/services/<int:service_id>')
def display_service_customers(service_id):
    service = ComHealthService.query.get(service_id)
    return render_template('comhealth/service_customers.html', service=service)


@comhealth.route('/checkin/<int:record_id>', methods=['GET', 'POST'])
def edit_record(record_id):
    # TODO: use decimal in price calculation instead of float

    record = ComHealthRecord.query.get(record_id)
    if not record.service.profiles and not record.service.groups:
        return redirect(url_for('comhealth.edit_service', service_id=record.service.id))

    emptypes = ComHealthCustomerEmploymentType.query.all()

    if request.method == 'GET':
        if not record.checkin_datetime:
            return render_template('comhealth/edit_record.html',
                                   record=record,
                                   emptypes=emptypes,
                                   )

    containers = set()
    profile_item_cost = 0.0
    group_item_cost = 0
    for profile in record.service.profiles:
        profile_item_cost += float(profile.quote)

    if request.method == 'POST':
        if not record.customer.dob and request.form.get('dob'):
            try:
                day, month, year = request.form.get('dob', '').split('/')
                year = int(year) - 543
                month = int(month)
                day = int(day)
            except:
                flash('Date of birth is not valid.')
                pass
            else:
                record.customer.dob = date(year, month, day)
        if not record.checkin_datetime:
            record.checkin_datetime = datetime.now(tz=bangkok)
        if not record.labno:
            labno = request.form.get('service_code')
            record.labno = int(labno)
            db.session.add(record)
            db.session.commit()
        for field in request.form:
            if field.startswith('test_'):
                _, test_id = field.split('_')
                test_item = ComHealthTestItem.query.get(int(test_id))
                group_item_cost += float(test_item.price) or float(test_item.test.default_price)
                containers.add(test_item.test.container)
                record.ordered_tests.append(test_item)
            elif field.startswith('profile_'):
                _, test_id = field.split('_')
                test_item = ComHealthTestItem.query.get(int(test_id))
                record.ordered_tests.append(test_item)
                containers.add(test_item.test.container)

        record.comment = request.form.get('comment')
        emptype_id = int(request.form.get('emptype_id', 0))
        department_id = int(request.form.get('department_id', 0))
        record.customer.emptype_id = emptype_id
        if department_id > 0:
            record.customer.dept_id = department_id

        record.updated_at = datetime.now(tz=bangkok)
        db.session.add(record)
        db.session.commit()

    special_tests = set(record.ordered_tests)

    for profile in record.service.profiles:
        # if all tests are ordered, the quote price is used.
        # if some tests in the profile are ordered, subtract the price of the tests that are not ordered
        if set(profile.test_items).intersection(record.ordered_tests):
            for test_item in set(profile.test_items).difference(record.ordered_tests):
                profile_item_cost -= float(test_item.price) or float(test_item.test.default_price)
        else:  # in case no tests in the profile is ordered, subtract a quote price from the total price
            profile_item_cost -= float(profile.quote)
        special_tests.difference_update(set(profile.test_items))

    group_item_cost = sum([item.price or item.test.default_price
                           for item in record.ordered_tests if item.group])
    special_item_cost = sum([item.price or item.test.default_price
                             for item in special_tests])
    containers = set([item.test.container for item in record.ordered_tests])

    return render_template('comhealth/record_summary.html',
                           record=record,
                           containers=containers,
                           profile_item_cost=profile_item_cost,
                           group_item_cost=float(group_item_cost),
                           special_tests=special_tests,
                           special_item_cost=float(special_item_cost),
                        )


@comhealth.route('/record/order/add-comment', methods=['GET', 'POST'])
def add_comment_to_order():
    if request.method == 'POST':
        record_id = request.form.get('record_id')
        record = ComHealthRecord.query.get(int(record_id))
        comment = request.form.get('comment')
        record.comment = comment
        db.session.add(record)
        db.session.commit()

        return redirect(url_for('comhealth.edit_record', record_id=record.id))


@comhealth.route('/record/<int:record_id>/order/add-test-item/<int:item_id>')
def add_item_to_order(record_id, item_id):
    if record_id and item_id:
        record = ComHealthRecord.query.get(record_id)
        item = ComHealthTestItem.query.get(item_id)

        if item not in record.ordered_tests:
            record.ordered_tests.append(item)
            record.updated_at = datetime.now(tz=bangkok)
            db.session.add(record)
            db.session.commit()
            flash('{} has been added to the order.'.format(item.test.name))
            return redirect(url_for('comhealth.edit_record', record_id=record.id))


@comhealth.route('/record/<int:record_id>/order/remove-test-item/<int:item_id>')
def remove_item_from_order(record_id, item_id):
    if record_id and item_id:
        record = ComHealthRecord.query.get(record_id)
        item = ComHealthTestItem.query.get(item_id)

        if item in record.ordered_tests:
            record.ordered_tests.remove(item)
            record.updated_at = datetime.now(tz=bangkok)
            db.session.add(record)
            db.session.commit()
            flash('{} has been removed from the order.'.format(item.test.name))
            return redirect(url_for('comhealth.edit_record', record_id=record.id))


@comhealth.route('/record/<int:record_id>/update-delivery-status')
def update_delivery_status(record_id):
    if record_id:
        record = ComHealthRecord.query.get(record_id)
        record.urgent = not record.urgent
        record.updated_at = datetime.now(tz=bangkok)
        db.session.add(record)
        db.session.commit()
        flash('Delivery request has been updated.')
        return redirect(url_for('comhealth.edit_record', record_id=record.id))


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


@comhealth.route('/test/profiles/new', methods=['GET', 'POST'])
def add_test_profile():
    form = TestProfileForm()
    if form.validate_on_submit():
        new_profile = ComHealthTestProfile(
            name=form.name.data,
            desc=form.desc.data,
            age_max=form.age_max.data,
            age_min=form.age_min.data,
            gender=form.gender.data,
            quote=form.quote.data,
        )
        db.session.add(new_profile)
        db.session.commit()
        flash('Profile {} has been added.')
        return redirect(url_for('comhealth.test_index'))
    else:
        for field_name, errors in form.errors.items():
            for error in errors:
                flash(u'{} {}'.format(field_name, error))

    return render_template('comhealth/new_profile.html', form=form)


@comhealth.route('/test/groups/new', methods=['GET', 'POST'])
def add_test_group():
    form = TestGroupForm()
    if form.validate_on_submit():
        new_group = ComHealthTestGroup(
            name=form.name.data,
            desc=form.desc.data,
            age_max=form.age_max.data,
            age_min=form.age_min.data,
            gender=form.gender.data,
        )
        db.session.add(new_group)
        db.session.commit()
        flash('Group {} has been added.')
        return redirect(url_for('comhealth.test_index'))
    else:
        for field_name, errors in form.errors.items():
            for error in errors:
                flash(u'{} {}'.format(field_name, error))

    return render_template('comhealth/new_group.html', form=form)


@comhealth.route('/test/tests/profile/menu/<int:profile_id>')
def profile_test_menu(profile_id=None):
    '''Shows a menu of tests to be added to the profile.

    :param profile_id:
    :return:
    '''
    if profile_id:
        tests = ComHealthTest.query.all()
        t_schema = ComHealthTestSchema(many=True)
        form = TestListForm()
        profile = ComHealthTestProfile.query.get(profile_id)
        action = url_for('comhealth.add_test_to_profile', profile_id=profile_id)
        return render_template('comhealth/test_menu.html',
                               tests=t_schema.dump(tests).data,
                               form=form,
                               action=action,
                               profile=profile)
    return redirect(url_for('comhealth.test_index'))


@comhealth.route('/test/profiles/<int:profile_id>/add-test',
                 methods=['GET', 'POST'])
def add_test_to_profile(profile_id):
    '''Add tests selected from the menu to be added to the profile.

    :param profile_id:
    :return:
    '''
    form = TestListForm()
    if form.validate_on_submit() and profile_id:
        data = form.test_list.data
        tests = json.loads(data)

        for test in tests:
            new_item = ComHealthTestItem(test_id=int(test['id']),
                                         price=float(test['default_price']), profile_id=profile_id)
            db.session.add(new_item)
        db.session.commit()
        flash('Test(s) have been added to the profile')
        return redirect(url_for('comhealth.test_profile', profile_id=profile_id))

    flash('Falied to add tests to the profile.')
    return redirect(url_for('comhealth.profile_test_menu', set_id=profile_id))


@comhealth.route('/test/profiles/<int:profile_id>')
def test_profile(profile_id):
    '''Main Test Index with Profile, Group and Test tabs.

    :param profile_id:
    :return:
    '''
    profile = ComHealthTestProfile.query.get(profile_id)
    return render_template('comhealth/test_profile_edit.html', profile=profile)


@comhealth.route('/test/profiles/<int:profile_id>/save', methods=['GET', 'POST'])
def save_test_profile(profile_id):
    '''Generates a form for editing the price of the test item.

    :param profile_id:
    :return:
    '''
    profile = ComHealthTestProfile.query.get(profile_id)
    for test in request.form:
        if test.startswith('test'):
            _, test_id = test.split('_')
            test_item = ComHealthTestItem.query.get(int(test_id))
            test_item.price = float(request.form.get(test))
            db.session.add(test_item)
    db.session.commit()
    flash('Change has been saved.')
    return redirect(url_for('comhealth.test_profile', profile_id=profile_id))


@comhealth.route('/test/profiles/<int:profile_id>/tests/<int:item_id>/remove', methods=['GET', 'POST'])
def remove_test_profile(profile_id, item_id):
    '''Delete the test item from the profile.

    :param profile_id:
    :return:
    '''
    profile = ComHealthTestProfile.query.get(profile_id)
    tests = [test for test in profile.test_items if test.id != item_id]
    profile.test_items = tests
    db.session.add(profile)
    db.session.commit()
    return redirect(url_for('comhealth.test_profile', profile_id=profile.id))


@comhealth.route('/test/tests/group/menu/<int:group_id>')
def group_test_menu(group_id=None):
    '''Shows a menu of tests to be added to the profile.

    :param profile_id:
    :return:
    '''
    if group_id:
        tests = ComHealthTest.query.all()
        t_schema = ComHealthTestSchema(many=True)
        form = TestListForm()
        group = ComHealthTestGroup.query.get(group_id)
        action = url_for('comhealth.add_test_to_group', group_id=group_id)
        return render_template('comhealth/group_test_menu.html',
                               tests=t_schema.dump(tests).data,
                               form=form,
                               action=action,
                               group=group)
    return redirect(url_for('comhealth.test_index'))


@comhealth.route('/test/groups/<int:group_id>/add-test',
                 methods=['GET', 'POST'])
def add_test_to_group(group_id):
    '''Add tests selected from the menu to be added to the group.

    :param group_id:
    :return:
    '''
    form = TestListForm()
    if form.validate_on_submit() and group_id:
        data = form.test_list.data
        tests = json.loads(data)

        for test in tests:
            new_item = ComHealthTestItem(test_id=int(test['id']),
                                         price=float(test['default_price']), group_id=group_id)
            db.session.add(new_item)
        db.session.commit()
        flash('Test(s) have been added to the group')
        return redirect(url_for('comhealth.test_group_index', group_id=group_id))

    flash('Falied to add tests to the group.')
    return redirect(url_for('comhealth.group_test_menu', set_id=group_id))


@comhealth.route('/test/groups/<int:group_id>/save', methods=['GET', 'POST'])
def save_test_group(group_id):
    '''Generates a form for editing the price of the test item.

    :param group_id:
    :return:
    '''
    group = ComHealthTestProfile.query.get(group_id)
    for test in request.form:
        if test.startswith('test'):
            _, test_id = test.split('_')
            test_item = ComHealthTestItem.query.get(int(test_id))
            test_item.price = float(request.form.get(test))
            db.session.add(test_item)
    db.session.commit()
    flash('Change has been saved.')
    return redirect(url_for('comhealth.test_group_index', group_id=group_id))


@comhealth.route('/test/groups/<int:group_id>/tests/<int:item_id>/remove', methods=['GET', 'POST'])
def remove_group_test_item(group_id, item_id):
    '''Delete the test item from the group.

    :param group_id:
    :return:
    '''
    group = ComHealthTestGroup.query.get(group_id)
    tests = [test for test in group.test_items if test.id != item_id]
    group.test_items = tests
    db.session.add(group)
    db.session.commit()
    return redirect(url_for('comhealth.test_group_index', group_id=group.id))


@comhealth.route('/test/tests')
@comhealth.route('/test/tests/<int:test_id>')
def test_test_index(test_id=None):
    if test_id:
        test = ComHealthTest.query.get(test_id)
        # TODO: create the test_test_edit.html
        return render_template('comhealth/test_test_edit.html', test=test)

    tests = ComHealthTest.query.all()
    t_schema = ComHealthTestSchema(many=True)
    return render_template('comhealth/test_test.html',
                           tests=t_schema.dump(tests).data)


@comhealth.route('/test/tests/new', methods=['GET', 'POST'])
def add_new_test():
    form = TestForm()
    containers = [(c.id, c.name) for c in ComHealthContainer.query.all()]
    form.container.choices = containers
    if form.validate_on_submit():
        new_test = ComHealthTest(
            code=form.code.data,
            name=form.name.data,
            desc=form.desc.data,
            default_price=form.default_price.data,
            container_id=form.container.data
        )
        db.session.add(new_test)
        db.session.commit()
        flash('New test added successfully.')
        return redirect(url_for('comhealth.test_test_index'))
    return render_template('comhealth/new_test.html',
                           form=form)


@comhealth.route('/test/tests/edit/<int:test_id>', methods=['GET', 'POST'])
def edit_test(test_id):
    return render_template('comhealth/edit_test.html')


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
    flash(u'Profile {} has been added to the service.'.format(profile.name))
    return redirect(url_for('comhealth.edit_service', service_id=service.id))


@comhealth.route('/services/profiles/delete/<int:service_id>/<int:profile_id>')
def delete_service_profile(service_id=None, profile_id=None):
    if service_id and profile_id:
        service = ComHealthService.query.get(service_id)
        kept_profiles = []
        for profile in service.profiles:
            if profile.id != profile_id:
                kept_profiles.append(profile)
            else:
                flash(u'Profile {} has been removed from the service.'.format(profile.name))

        service.profiles = kept_profiles
        db.session.add(service)
        db.session.commit()

    return redirect(url_for('comhealth.edit_service', service_id=service.id))


@comhealth.route('/services/groups/<int:service_id>')
@comhealth.route('/services/groups/<int:service_id>/<int:group_id>')
def add_service_group(service_id=None, group_id=None):
    if not (service_id and group_id):
        service = ComHealthService.query.get(service_id)
        groups = [gr for gr in ComHealthTestGroup.query.all() if gr not in service.groups]
        return render_template('comhealth/group_list.html',
                               groups=groups,
                               service=service)

    service = ComHealthService.query.get(service_id)
    group = ComHealthTestGroup.query.get(group_id)
    service.groups.append(group)
    db.session.add(service)
    db.session.commit()
    flash(u'Group {} has been added to the service.'.format(group.name))
    return redirect(url_for('comhealth.edit_service', service_id=service.id))


@comhealth.route('/services/groups/delete/<int:service_id>/<int:group_id>')
def delete_service_group(service_id=None, group_id=None):
    if service_id and group_id:
        service = ComHealthService.query.get(service_id)
        kept_groups = []
        for group in service.groups:
            if group.id != group_id:
                kept_groups.append(group)
            else:
                flash(u'Group {} has been removed to the service.'.format(group.name))
        service.groups = kept_groups
        db.session.add(service)
        db.session.commit()

    return redirect(url_for('comhealth.edit_service', service_id=service.id))


@comhealth.route('/services/<int:service_id>/specimens-summary')
def summarize_specimens(service_id):
    containers = set()
    if service_id:
        service = ComHealthService.query.get(service_id)
        for profile in service.profiles:
            for test_item in profile.test_items:
                containers.add(test_item.test.container)
        for group in service.groups:
            for test_item in group.test_items:
                containers.add(test_item.test.container)

        record_ids = dict([(int(r.labno[-4:]), r) for r in service.records if r.labno])
        sorted_records = []
        for i in range(len(service.records)):
            if i + 1 in record_ids:
                sorted_records.append(record_ids[i + 1])
            else:
                sorted_records.append(None)

        return render_template('comhealth/specimens_checklist.html',
                               summary_date=datetime.now(tz=bangkok),
                               service=service,
                               containers=sorted(containers, key=lambda x: x.name),
                               sorted_records=sorted_records)


@comhealth.route('/services/<int:service_id>/containers/<int:container_id>')
def list_tests_in_container(service_id, container_id):
    tests = defaultdict(list)
    if service_id:
        service = ComHealthService.query.get(service_id)
        container = ComHealthContainer.query.get(container_id)
        for record in service.records:
            for test_item in record.ordered_tests:
                if test_item.test.container_id == container_id:
                    tests[record.labno].append(test_item.test.code)
    return render_template('comhealth/container_tests.html',
                           tests=tests, service=service, container=container)


@comhealth.route('/organizations')
def list_orgs():
    org_schema = ComHealthOrgSchema(many=True)
    orgs = ComHealthOrg.query.all()
    return render_template('comhealth/org_list.html',
                           orgs=org_schema.dump(orgs).data)


@comhealth.route('/services/add-to-org/<int:org_id>', methods=['GET', 'POST'])
def add_service_to_org(org_id):
    form = ServiceForm()
    org = ComHealthOrg.query.get(org_id)
    if form.validate_on_submit():
        try:
            service_date = datetime.strptime(form.service_date.data, '%Y-%m-%d')
        except ValueError:
            flash('Date data not valid.')
        else:
            existing_service = ComHealthService.query\
                .filter_by(date=service_date, location=form.location.data).first()
            if not existing_service:
                new_service = ComHealthService(date=service_date, location=form.location.data)
                db.session.add(new_service)
                for employee in org.employees:
                    new_record = ComHealthRecord(date=service_date, service=new_service,
                                                 customer=employee)
                    db.session.add(new_record)
                db.session.commit()
            else:
                for employee in org.employees:
                    services = set([rec.service for rec in employee.records])
                    if existing_service not in services:
                        new_record = ComHealthRecord(date=service_date, service=existing_service,
                                                     customer=employee)
                        db.session.add(new_record)
                        db.session.commit()

            flash('New service has been added to the organization.')
            return redirect(url_for('comhealth.index'))
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash('{} {}'.format(field, error))
    return render_template('comhealth/new_schedule.html',
                           form=form, org=org)


@comhealth.route('/services/<int:service_id>/add-new-customer/<int:org_id>', methods=['GET', 'POST'])
def add_customer_to_service_org(service_id, org_id):
    form = CustomerForm()
    if form.validate_on_submit():
        service_id = form.service_id.data
        org_id = form.org_id.data
        if form.dob.data:
            d, m, y = form.dob.data.split('/')
            dob = date(int(y) - 543, int(m), int(d))  # convert to Thai Buddhist year
        else:
            dob = None
        customer = ComHealthCustomer(title=form.title.data,
                                     firstname=form.firstname.data,
                                     lastname=form.lastname.data,
                                     gender=form.gender.data,
                                     dob=dob,
                                     org_id=org_id)
        new_record = ComHealthRecord(service_id=service_id, customer=customer)
        db.session.add(customer)
        db.session.add(new_record)
        db.session.commit()
        flash('New customer has been added to the database and service.')
        return redirect(url_for('comhealth.display_service_customers', service_id=service_id))
    else:
        for field, errors in form.errors.items():
            for err in errors:
                flash('{} {}'.format(field, err))

    if service_id and org_id:
        form.service_id.default = service_id
        form.org_id.default = org_id
        form.process()
        return render_template('comhealth/new_customer_service_org.html', form=form)


#TODO: export the price of tests

@comhealth.route('/services/<int:service_id>/to-csv')
def export_csv(service_id):
    #TODO: add employment types (number)
    #TODO: add age, gender
    #TODO: add organization + dept + unit
    service = ComHealthService.query.get(service_id)
    rows = []
    for record in sorted(service.records, key=lambda x: x.labno):
        if not record.labno:
            continue
        tests = ','.join([item.test.code for item in record.ordered_tests])
        rows.append({'firstname': u'{}'.format(record.customer.firstname),
                     'lastname': u'{}'.format(record.customer.lastname),
                     'labno': u'{}'.format(record.labno),
                     'tests': u'{}'.format(tests),
                     'urgent': record.urgent})
        pd.DataFrame(rows).to_excel('export.xlsx',
                                    header=True,
                                    columns=['labno',
                                             'firstname',
                                             'lastname',
                                             'tests',
                                             'urgent'],
                                    index=False,
                                    encoding='utf-8')
    return send_from_directory(os.getcwd(), filename='export.xlsx')


@comhealth.route('/organizations/add', methods=['GET', 'POST'])
def add_org():
    name = request.form.get('name', '')
    if name:
        org_ = ComHealthOrg.query.filter_by(name=name).first()
        if org_:
            return 'Organization exists!'
        else:
            new_org = ComHealthOrg(name=name)
            db.session.add(new_org)
            db.session.commit()
            return redirect(url_for('comhealth.list_orgs'))
    return 'No name found.'


@comhealth.route('/organizations/<int:orgid>/employees', methods=['GET', 'POST'])
def list_employees(orgid):
    if orgid:
        org = ComHealthOrg.query.get(orgid)
        customer_schema = ComHealthCustomerSchema(many=True)
        return render_template('comhealth/employees.html',
                                    employees=customer_schema.dump(org.employees).data,
                                    org=org)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS 


@comhealth.route('/organizations/<int:orgid>/employees/info', methods=['POST', 'GET'])
def add_employee_info(orgid):
    """Add employees info from a file.
    """

    org = ComHealthOrg.query.get(orgid)
    info_items = ComHealthCustomerInfoItem.query.all()
    info_items = set([item.text for item in info_items])

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file alert')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            df = read_excel(file)
            for idx, rec in df.iterrows():
                rec = rec.fillna('')
                data = {}
                for col in rec.keys():
                    if col in info_items:
                        data[col] = rec[col]

                customer = ComHealthCustomer.query\
                    .filter_by(firstname=rec['firstname'], lastname=rec['lastname']).first()
                if not customer:
                    dept = None
                    emptype = None
                    if rec['department']:
                        existing_dept = ComHealthDepartment.query.filter_by(name=rec['department']).first()
                        if existing_dept:
                            dept = existing_dept
                        else:
                            dept = ComHealthDepartment(name=rec['department'], parent_id=orgid)
                    if rec['employmentType']:
                        existing_emptype = ComHealthCustomerEmploymentType.query\
                            .filter_by(name=rec['employmentType']).first()
                        if existing_emptype:
                            emptype = existing_emptype
                        else:
                            emptype = ComHealthCustomerEmploymentType(name=rec['employmentType'])
                    customer = ComHealthCustomer(
                        title=rec['title'],
                        firstname=rec['firstname'],
                        lastname=rec['lastname'],
                        org_id=orgid,
                        dept=dept,
                        gender=rec['gender'],
                        phone=rec['phone'],
                        emptype=emptype,
                        unit=rec['unit'],
                    )
                    db.session.add(customer)
                    db.session.commit()
                    customer.generate_hn()

                if not customer.info:
                    info = ComHealthCustomerInfo(
                        customer=customer,
                        data=data,
                        updated_at=datetime.now(tz=bangkok)
                    )
                    db.session.add(info)
                else:
                    customer.info.data = data
                db.session.add(customer)
                db.session.commit()
        return redirect(url_for('comhealth.list_employees', orgid=org.id))

    return render_template('comhealth/employee_info_upload.html', org=org)


@comhealth.route('/organizations/employees/info/<int:custid>',
    methods=["POST", "GET"])
def show_employee_info(custid):
    info_items = ComHealthCustomerInfoItem.query.all()
    info_items = [(it.text, it) for it in info_items]
    info_items = OrderedDict(sorted(info_items, key=lambda x: x[1].order))

    if request.method == 'GET':
        if not custid:
            flash('No customer ID specified.')
            return redirect(request.referrer)

        customer = ComHealthCustomer.query.get(custid)
        if customer:
            if not customer.info:
                info = ComHealthCustomerInfo(customer=customer, data={})
                db.session.add(info)
                db.session.commit()
            return render_template('comhealth/employee_info_update.html',
                                        info_items=info_items,
                                        customer=customer)
        else:
            flash('Customer with ID={} does not exist.'.format(customer.id))
            return redirect(request.referrer)

    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        print('customer id is {}'.format(customer_id))
        if customer_id:
            customer = ComHealthCustomer.query.get(int(customer_id))
            print(u'{}'.format(customer.fullname))
            for k, item in info_items.items():
                if not item.multiple_selection:
                    customer.info.data[k] = request.form.get(k)
                else:
                    values = ' '.join(request.form.getlist(k))
                    customer.info.data[k] = values
            for k,v in customer.info.data.items():
                print(u'{} {}'.format(k,v))
            flag_modified(customer.info, "data")
            db.session.add(customer)
            db.session.commit()
        else:
            flash('Customer ID not found.')
        return redirect(url_for('comhealth.list_employees',
                                        orgid=customer.org.id))


@comhealth.route('/organizations/<int:orgid>/employees/addmany', methods=['GET', 'POST'])
def add_many_employees(orgid):
    """Add employees from Excel file.

    Note that the birthdate is in Thai year.
    The columns are labno, title, firstname, lastname, dob, gender, and servicedate
    :type orgid: int
    """
    org = ComHealthOrg.query.get(orgid)

    if request.method == 'POST':
        labno_included = request.form.get('labno_included')
        if 'file' not in request.files:
            flash('No file alert')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            service = None
            df = read_excel(file)
            for idx, rec in df.iterrows():
                labno, title, firstname, lastname, dob, gender, servicedate = rec
                if not firstname or not lastname:
                    continue
                try:
                    day, month, year = map(int, dob.split('/'))
                except Exception as e:
                    if isna(dob) or isinstance(e, ValueError):
                        dob = None
                    elif isinstance(e, AttributeError):
                        day, month, year = map(int, [dob.day, dob.month, dob.year])
                        year = year - 543
                        dob = date(year, month, day)
                else:
                    year = year - 543
                    dob = date(year, month, day)

                if not service:
                    service = ComHealthService.query.filter_by(date=servicedate).first()
                    if not service:
                        service = ComHealthService(date=servicedate,
                                                   location=org.name)
                        db.session.add(service)
                        db.session.commit()

                customer_ = ComHealthCustomer.query.filter_by(
                                    firstname=firstname, lastname=lastname).first()
                if customer_:
                    record_ = ComHealthRecord.query.filter_by(
                                        service=service, customer=customer_).first()
                    if record_:
                        # print(u'Record exists. Continue..{} {}'.format(firstname, lastname))
                        continue

                    # A new customer is created for this org even when the name exists in the db.
                    # This helps resolve the issue of redundant names.
                    if dob:
                        cdob = dob
                    else:
                        cdob = customer_.dob

                    gender = int(gender) if not isna(gender) else None

                    new_customer = ComHealthCustomer(
                        title=customer_.title,
                        firstname=customer_.firstname,
                        lastname=customer_.lastname,
                        dob=cdob,
                        org=org,
                        gender=gender,
                    )
                else:
                    new_customer = ComHealthCustomer(
                        title=title,
                        firstname=firstname,
                        lastname=lastname,
                        dob=dob,
                        org=org,
                        gender=gender
                    )
                db.session.add(new_customer)

                if labno_included == 'true' and labno:
                    labno = int(labno)
                    labno = '{}{:02}{:02}2{:04}'.format(str(service.date.year)[-1],
                                                        service.date.month,
                                                        service.date.day,
                                                        labno)
                    new_record = ComHealthRecord(
                        date=service.date,
                        labno=labno,
                        service=service,
                        customer=new_customer,
                    )
                    db.session.add(new_record)

            db.session.commit()
            return redirect(url_for('comhealth.list_employees', orgid=org.id))

    return render_template('comhealth/employee_upload.html', org=org)


@comhealth.route('/organizations/mudt/employees', methods=['GET', 'POST'])
def search_employees():
    df = read_excel('app/static/data/mudt2019.xls')
    data = []
    for idx, rec in df.iterrows():
        item = {
            'id': idx,
            'no': rec[0],
            'firstname': rec.firstname,
            'lastname': rec.lastname,
            'dob': rec.dob
            }
        data.append(item)
    return render_template('comhealth/search_employees.html', employees=data, org=u'การเคหะแห่งชาติ')


@comhealth.route('/checkin/<int:record_id>/receipts', methods=['GET', 'POST'])
def list_all_receipts(record_id):
    record = ComHealthRecord.query.get(record_id)
    return render_template('comhealth/receipts.html', record=record)


@comhealth.route('/checkin/records/<int:record_id>/receipts', methods=['POST', 'GET'])
def create_receipt(record_id):
    if request.method == 'GET':
        record = ComHealthRecord.query.get(record_id)
        customer_age = record.customer.age.years
        cashiers = ComHealthCashier.query.all()
        ref_profile = ComHealthReferenceTestProfile.query.\
            filter(ComHealthReferenceTestProfile.profile.\
                   has(ComHealthTestProfile.age_min<=customer_age)).first()
        if ref_profile:
            ref_profile_test_ids = [ti.test.id for ti in ref_profile.profile.test_items]
        else:
            ref_profile_test_ids = []
        valid_receipts = [rcp for rcp in record.receipts if not rcp.cancelled]
        return render_template('comhealth/new_receipt.html', record=record,
                                                valid_receipts=valid_receipts,
                                                cashiers=cashiers,
                                                ref_profile=ref_profile,
                                                ref_profile_test_ids=ref_profile_test_ids,
                                                )
    if request.method == 'POST':
        receipt_code = ComHealthReceiptID.query.get(session.get('receipt_code_id'))
        record_id = request.form.get('record_id')
        record = ComHealthRecord.query.get(record_id)
        issuer_id = request.form.get('issuer_id', None)
        cashier_id = request.form.get('cashier_id', None)
        print_profile_item = True if request.form.getlist('print_profile_items') else False
        print_profile_note = True if request.form.getlist('print_profile_note') else False
        valid_receipts = [rcp for rcp in record.receipts if not rcp.cancelled]
        if not valid_receipts:  # not active receipt
            receipt = ComHealthReceipt(
                created_datetime=datetime.now(tz=bangkok),
                record=record,
                issuer_id=int(issuer_id) if issuer_id is not None else None,
                cashier_id=int(cashier_id) if cashier_id is not None else None,
                print_profile_note=print_profile_note,
                book_number=receipt_code.next,
                issued_at=session.get('receipt_venue', ''),
                )
            db.session.add(receipt)
            receipt_code.count += 1
            receipt_code.updated_at = datetime.now(tz=bangkok)
            db.session.add(receipt_code)
        for test_item in record.ordered_tests:
            if test_item.profile and not print_profile_item:
                continue
            visible = test_item.test.code + '_visible'
            billed = test_item.test.code + '_billed'
            reimbursable = test_item.test.code + '_reimbursable'
            billed = True if request.form.getlist(billed) else False
            visible = True if request.form.getlist(visible) else False
            reimbursable = True if request.form.getlist(reimbursable) else False
            invoice = ComHealthInvoice(test_item=test_item,
                                       receipt=receipt,
                                       billed=billed,
                                       reimbursable=reimbursable,
                                       visible=visible)
            db.session.add(invoice)
        db.session.commit()
        return redirect(url_for('comhealth.list_all_receipts', record_id=record.id)) 


@comhealth.route('/checkin/receipts/cancel/confirm/<int:receipt_id>', methods=['GET', 'POST'])
def confirm_cancel_receipt(receipt_id):
    receipt = ComHealthReceipt.query.get(receipt_id)
    if not receipt.cancelled:
        return render_template('/comhealth/confirm_cancel_receipt.html', receipt=receipt)


@comhealth.route('/checkin/receipts/cancel/<int:receipt_id>', methods=['POST'])
def cancel_receipt(receipt_id):
    receipt = ComHealthReceipt.query.get(receipt_id)
    receipt.cancelled = True
    receipt.cancel_comment = request.form.get('comment')
    db.session.add(receipt)
    db.session.commit()
    return redirect(url_for('comhealth.list_all_receipts',
                                record_id=receipt.record.id))


@comhealth.route('/checkin/receipts/pay/<int:receipt_id>', methods=['POST'])
def pay_receipt(receipt_id):
    pay_method = request.form.get('pay_method')
    if pay_method == 'card':
        card_number = request.form.get('card_number')
    receipt = ComHealthReceipt.query.get(receipt_id)
    if not receipt.paid:
        receipt.paid = True
        receipt.payment_method = pay_method
        if pay_method == 'card':
            receipt.card_number = card_number
        db.session.add(receipt)
        db.session.commit()
    return redirect(url_for('comhealth.show_receipt_detail',
                            receipt_id=receipt_id))


@comhealth.route('/checkin/receipts/<int:receipt_id>', methods=['GET', 'POST'])
def show_receipt_detail(receipt_id):
    receipt = ComHealthReceipt.query.get(receipt_id)
    action = request.args.get('action', None)
    if action == 'pay':
        receipt.paid = True
        db.session.add(receipt)
        db.session.commit()

    total_cost = sum([t.test_item.price or t.test_item.test.default_price
                        for t in receipt.invoices if t.billed])
    total_special_cost = sum([t.test_item.price or t.test_item.test.default_price
                        for t in receipt.invoices if t.billed and t.test_item.group])

    total_profile_cost = sum([t.test_item.price or t.test_item.test.default_price
                        for t in receipt.invoices if t.billed and t.test_item.profile])

    total_special_cost_thai = bahttext(total_special_cost)
    
    visible_special_tests = [t for t in receipt.invoices if t.visible and t.test_item.group]
    visible_profile_tests = [t for t in receipt.invoices if t.visible and t.test_item.profile]

    return render_template('comhealth/receipt_detail.html',
                           receipt=receipt,
                           total_cost=total_cost,
                           total_special_cost=total_special_cost,
                           total_profile_cost=total_profile_cost,
                           total_special_cost_thai=total_special_cost_thai,
                           visible_special_tests=visible_special_tests,
                           visible_profile_tests=visible_profile_tests)


@comhealth.route('/receipts/slip/<int:record_id>')
def print_slip(record_id):
    paidamt = request.args.get('paidamt', 0.0)
    paidamt = Decimal(paidamt)
    record = ComHealthRecord.query.get(record_id)

    containers = set()
    profile_item_cost = 0.0
    group_item_cost = 0
    for profile in record.service.profiles:
        profile_item_cost += float(profile.quote)

    special_tests = set(record.ordered_tests)

    for profile in record.service.profiles:
        # if all tests are ordered, the quote price is used.
        # if some tests in the profile are ordered, subtract the price of the tests that are not ordered
        if set(profile.test_items).intersection(record.ordered_tests):
            for test_item in set(profile.test_items).difference(record.ordered_tests):
                profile_item_cost -= float(test_item.price) or float(test_item.test.default_price)
        else:  # in case no tests in the profile is ordered, subtract a quote price from the total price
            profile_item_cost -= float(profile.quote)
        special_tests.difference_update(set(profile.test_items))

    group_item_cost = sum([item.price or item.test.default_price
                           for item in record.ordered_tests if item.group])
    special_item_cost = sum([item.price or item.test.default_price
                             for item in special_tests])
    containers = set([item.test.container for item in record.ordered_tests])
    change = paidamt - special_item_cost

    html = render_template('comhealth/slip.html',
                           record=record,
                           customer=record.customer,
                           special_tests=special_tests,
                           special_item_cost="{:10.2f}".format(special_item_cost),
                           paidamt="{:10.2f}".format(paidamt),
                           change="{:10.2f}".format(change)
                          )
    return render_pdf(HTML(string=html))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5, landscape
from reportlab.platypus import (SimpleDocTemplate, Table, Image,
                                Spacer, Paragraph, TableStyle)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
pdfmetrics.registerFont(sarabun_font)
style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))

@comhealth.route('/receipts/pdf/<int:receipt_id>')
def export_receipt_pdf(receipt_id):
    receipt = ComHealthReceipt.query.get(receipt_id)
    doc = SimpleDocTemplate("app/receipt.pdf",
                            rightMargin=20,
                            leftMargin=20,
                            topMargin=5,
                            bottomMargin=10,
                            )
    data = []
    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 40, 40)
    data.append(logo)
    affiliation = '''<para align=center><font size=14>
    มหาวิทยาลัยมหิดล<br/>
    คณะเทคนิคการแพทย์<br/><br/>
    </font>
    <font size=18>ใบเสร็จรับเงิน</font></para>
    '''
    address = '''<font size=12>
    เลขที่ 999 พุทธมณฑลสาย 4<br/>
    ต.ศาลายา อ.พุทธมณฑล<br/>
    จ.นครปฐม 73170<br/>
    เลขประจำตัวผู้เสียภาษี 4107039192<br/><br/>
    </font>
    '''

    receipt_info = '''<font size=12>
    เลขที่ {book_number} แผ่นที่ 1<br/>
    วันที่ {issued_date}<br/>
    ออกที่ {venue}<br/>
    </font>
    '''
    issued_date = datetime.now().strftime('%d/%m/%Y')
    receipt_info = receipt_info.format(book_number=receipt.book_number,
                                       issued_date=issued_date,
                                       venue=receipt.issued_at.encode('utf-8'))

    header_content = [[Paragraph(address, style=style_sheet['ThaiStyle']),
                        Paragraph(affiliation, style=style_sheet['ThaiStyle']),
                        Paragraph(receipt_info, style=style_sheet['ThaiStyle'])]]

    header_styles = TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ])

    header = Table(header_content, colWidths=[120, 300, 120])
    header.hAlign = 'CENTER'
    header.setStyle(header_styles)
    customer_name = '''<para align=center><font size=11>
    ชื่อ {customer_name}
    </font></para>
    '''.format(customer_name=receipt.record.customer.fullname.encode('utf-8'))
    customer_hn = '''<para align=center><font size=11>
    หมายเลขรายการ {customer_hn}
    </font></para>
    '''.format(customer_hn=receipt.record.labno)
    customer = Table([[Paragraph(customer_name, style=style_sheet['ThaiStyle']),
                      Paragraph(customer_hn, style=style_sheet['ThaiStyle'])]])
    body_text = '''<para align=center><font size=16>
    รายการ</font></para>
    '''
    body = Table([[Paragraph(body_text, style=style_sheet['ThaiStyle'])]])
    body.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))

    items = [[Paragraph('', style=style_sheet['ThaiStyle']),
              Paragraph('<font size=11>เบิกได้ (บาท)*</font>', style=style_sheet['ThaiStyle']),
              Paragraph('<font size=11>เบิกไม่ได้ (บาท)*</font>',
                        style=style_sheet['ThaiStyle'])]]
    total = 0
    if receipt.print_profile_note:
        profile_tests = [t for t in receipt.record.ordered_tests if t.profile]
        if profile_tests:
            profile_price = profile_tests[0].profile.quote
            item = [Paragraph('<font size=11>การตรวจสุขภาพทางห้องปฏิบัติการ</font>', style=style_sheet['ThaiStyle']),
                    Paragraph('<font size=11>{:,.2f}</font>'.format(profile_price), style=style_sheet['ThaiStyle']),
                    Paragraph('<font size=11>{:,.2f}</font>'.format(0.0), style=style_sheet['ThaiStyle'])]
            items.append(item)
    for t in receipt.invoices:
        if t.visible:
            if t.billed:
                price = t.test_item.price or t.test_item.test.default_price
                total += price
                item = [Paragraph('<font size=11>{} (รหัส {})</font>'\
                                  .format(t.test_item.test.desc.encode('utf-8'), t.test_item.test.gov_code or '-'),
                                  style=style_sheet['ThaiStyle'])]
                if t.reimbursable:
                    item.append(Paragraph('<font size=11>{:,.2f}</font>'.format(price), style=style_sheet['ThaiStyle']))
                    item.append(Paragraph('<font size=11>{:,.2f}</font>'.format(0.0), style=style_sheet['ThaiStyle']))
                else:
                    item.append(Paragraph('<font size=11>{:,.2f}</font>'.format(0.0), style=style_sheet['ThaiStyle']))
                    item.append(Paragraph('<font size=11>{:,.2f}</font>'.format(price), style=style_sheet['ThaiStyle']))
                items.append(item)

    item_table = Table(items, colWidths=[200,80,180])

    total_thai = bahttext(total)
    total_text = Paragraph('<font size=12>รวมเงิน (ตัวอักษร) {}</font>'.format(total_thai.encode('utf-8')),
                           style=style_sheet['ThaiStyle'])
    total_number = Paragraph('<font size=12>รวมเงินทั้งสิ้น {:,.2f} บาท</font>'.format(total),
                             style=style_sheet['ThaiStyle'])
    total_content = [[total_text, total_number]]
    total_table = Table(total_content, colWidths=[405, 150])

    def later_page(canvas, document):
        canvas.saveState()
        canvas.setFont('Sarabun', 12)
        canvas.drawString(400,20,
                          u'ใบเสร็จเลขที่ {} แผ่นที่ {} ออกวันที่ {}'.format(
                                  receipt_id, document.page, issued_date))
        canvas.restoreState()

    if receipt.payment_method == 'cash':
        payment_info = '''<font size=12>
        ชำระเงินด้วยเงินสด
        </font>'''
    elif receipt.payment_method == 'card':
        payment_info = '''<font size=12>
        ชำระเงินด้วยบัตรเครดิต หมายเลข {}
        </font>'''.format(receipt.card_number)
    else:
        payment_info = '''<font size=12>ยังไม่ชำระเงิน</font>'''

    notice_text = '''<para align=center><font size=12>
    ใบเสร็จนี้จะสมบูรณ์ก็ต่อเมื่อคณะเทคนิคการแพทย์ได้รับเงินครบถ้วนแล้วเท่านั้น
    <br/>*ตามระเบียบกระทรวงการคลัง</font></para>
    '''
    notice = Table([[Paragraph(notice_text, style=style_sheet['ThaiStyle'])]])

    sign_text = '''<para align=center><font size=12>
    ลงชื่อ .........................................<br/>
    ({})<br/>
    ตำแหน่ง {}
    </font></para>'''.format(receipt.issuer.staff.personal_info.fullname.encode('utf-8'),
                             receipt.issuer.position.encode('utf-8'))

    data.append(header)
    data.append(customer)
    data.append(Spacer(1,12))
    data.append(body)
    data.append(Spacer(1,6))
    data.append(item_table)
    data.append(Spacer(1,6))
    data.append(total_table)
    data.append(Spacer(1,6))
    data.append(Paragraph(payment_info, style=style_sheet['ThaiStyle']))
    data.append(Spacer(1,12))
    data.append(Paragraph(sign_text, style=style_sheet['ThaiStyle']))
    data.append(Spacer(1,6))
    data.append(notice)
    doc.build(data, onLaterPages=later_page)
    return send_file('receipt.pdf')


class CustomerEmploymentTypeUploadView(BaseView):
    @expose('/')
    def index(self):
        return self.render('comhealth/employment_type_upload.html')

    @expose('/upload', methods=('POST', 'GET'))
    def upload(self):
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file alert')
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                flash('No file selected')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                df = read_excel(file, dtype=object)
                for idx, row in df.iterrows():
                    rec = ComHealthCustomerEmploymentType.query\
                            .filter_by(emptype_id=row[0]).first()
                    if rec:
                        if not isna(row[1]):
                            rec.name = row[1]
                            db.session.add(rec)
                    else:
                        if not isna(row[1]) and not isna(row[0]):
                            rec = ComHealthCustomerEmploymentType(emptype_id=row[0], name=row[1])
                            db.session.add(rec)
                db.session.commit()
        return request.method
