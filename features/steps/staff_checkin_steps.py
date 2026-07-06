from datetime import datetime

import pytz
from behave import given, then, when
from unittest.mock import patch


BANGKOK_TZ = pytz.timezone('Asia/Bangkok')
UTC = pytz.utc


def _parse_time(value):
    return datetime.strptime(value, '%H:%M').time()


def _parse_date(value):
    return datetime.strptime(value, '%Y-%m-%d').date()


def _ensure_employee(context, employee_code):
    if not hasattr(context, 'checkin_employees'):
        context.checkin_employees = {}

    employee = context.checkin_employees.get(employee_code)
    if employee is not None:
        return employee

    from app.models import Org
    from app.staff.models import StaffAccount, StaffPersonalInfo

    org = Org(name=f'{employee_code} Org', is_external=False)
    personal_info = StaffPersonalInfo(
        en_firstname='Test',
        en_lastname=employee_code,
        th_firstname='ทดสอบ',
        th_lastname=employee_code,
        org=org,
        academic_staff=False,
        finger_scan_id=int(employee_code[1:]),
    )
    account = StaffAccount(
        email=employee_code.lower(),
        personal_info=personal_info,
    )
    account.password = 'Secret123!'

    context.db.session.add_all([org, personal_info, account])
    context.db.session.commit()

    employee = {
        'code': employee_code,
        'account': account,
        'gps_times': [],
        'gps_place': 'gj',
        'target_date': None,
        'work_login': None,
        'work_login_count': 0,
        'last_geo_response': None,
        'first_geo_response': None,
        'geo_responses': [],
        'qrcode_times': [],
        'qrcode_responses': [],
        'first_qrcode_response': None,
        'last_qrcode_response': None,
        'time_report_records': [],
    }
    context.checkin_employees[employee_code] = employee
    return employee


def _login_employee(context, employee):
    response = context.client.post(
        '/auth/login',
        data={
            'email': employee['account'].email,
            'password': 'Secret123!',
            'remember_me': 'y',
        },
        follow_redirects=False,
    )
    assert response.status_code == 302, response.get_data(as_text=True)


def _frozen_datetime_class(fixed_dt):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_dt.replace(tzinfo=None)
            return fixed_dt.astimezone(tz)

    return FrozenDateTime


def _post_geo_checkin(context, fixed_dt, place='salaya'):
    with patch('app.staff.views.datetime', _frozen_datetime_class(fixed_dt)), patch(
        'app.staff.views.line_bot_api.push_message',
        return_value=None,
    ):
        response = context.client.post(
            '/staff/users/geo-checkin',
            json={
                'data': {
                    'place': place,
                    'lat': '13.0000',
                    'lon': '100.0000',
                }
            },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def _post_qrcode_checkin(context, fixed_dt, employee):
    qr_exp_datetime = BANGKOK_TZ.localize(
        datetime.combine(employee['target_date'], datetime.strptime('23:59:59', '%H:%M:%S').time())
    )
    with patch('app.staff.views.datetime', _frozen_datetime_class(fixed_dt)), patch(
        'app.staff.views.line_bot_api.push_message',
        return_value=None,
    ):
        response = context.client.post(
            '/staff/login-scan',
            json={
                'data': {
                    'lat': '13.0000',
                    'long': '100.0000',
                    'qrCodeExpDateTime': qr_exp_datetime.strftime('%d/%m/%Y %H:%M:%S'),
                    'thName': f"{employee['account'].personal_info.th_firstname} {employee['account'].personal_info.th_lastname}",
                    'enName': f"{employee['account'].personal_info.en_firstname} {employee['account'].personal_info.en_lastname}",
                }
            },
        )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def _fetch_time_report(context, target_date):
    start = BANGKOK_TZ.localize(datetime.combine(target_date, datetime.min.time())).isoformat()
    end = BANGKOK_TZ.localize(datetime.combine(target_date, datetime.max.time())).isoformat()
    response = context.client.get('/staff/api/time-report', query_string={'start': start, 'end': end})
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def _fetch_raw_work_login_count(employee, target_date):
    from app.staff.models import StaffWorkLogin

    date_id = StaffWorkLogin.generate_date_id(target_date)
    return StaffWorkLogin.query.filter_by(
        staff_id=employee['account'].id,
        date_id=date_id,
    ).count()


@given('the normal work period is from "{start}" to "{end}"')
def step_impl(context, start, end):
    context.office_start = _parse_time(start)
    context.office_end = _parse_time(end)


@given('employee "{employee_code}" has GPS check-in records on "{date_value}" at')
def step_impl(context, employee_code, date_value):
    employee = _ensure_employee(context, employee_code)
    context.active_employee = employee_code
    employee['gps_place'] = 'gj'
    employee['target_date'] = _parse_date(date_value)
    employee['gps_times'] = [_parse_time(row['time']) for row in context.table]


@given('employee "{employee_code}" has GPS check-in records at place "{place}" on "{date_value}" at')
def step_impl(context, employee_code, place, date_value):
    employee = _ensure_employee(context, employee_code)
    context.active_employee = employee_code
    employee['gps_place'] = place
    employee['target_date'] = _parse_date(date_value)
    employee['gps_times'] = [_parse_time(row['time']) for row in context.table]


@given('employee "{employee_code}" has no GPS check-in records on "{date_value}"')
def step_impl(context, employee_code, date_value):
    employee = _ensure_employee(context, employee_code)
    context.active_employee = employee_code
    employee['gps_place'] = 'gj'
    employee['target_date'] = _parse_date(date_value)
    employee['gps_times'] = []


@given('employee "{employee_code}" has QR check-in records on "{date_value}" at')
def step_impl(context, employee_code, date_value):
    employee = _ensure_employee(context, employee_code)
    context.active_employee = employee_code
    employee['target_date'] = _parse_date(date_value)
    employee['qrcode_times'] = [_parse_time(row['time']) for row in context.table]


@when('the system derives normal attendance for employee "{employee_code}" on "{date_value}"')
def step_impl(context, employee_code, date_value):
    from app.staff.models import StaffWorkLogin

    employee = _ensure_employee(context, employee_code)
    context.active_employee = employee_code
    target_date = _parse_date(date_value)
    employee['target_date'] = target_date
    _login_employee(context, employee)

    for scan_time in employee['gps_times']:
        fixed_dt = BANGKOK_TZ.localize(datetime.combine(target_date, scan_time)).astimezone(UTC)
        geo_response = _post_geo_checkin(context, fixed_dt, place=employee.get('gps_place') or 'gj')
        employee['geo_responses'].append(geo_response)
        employee['last_geo_response'] = geo_response
        if employee['first_geo_response'] is None:
            employee['first_geo_response'] = geo_response

    date_id = StaffWorkLogin.generate_date_id(target_date)
    employee['work_login_count'] = StaffWorkLogin.query.filter_by(
        staff_id=employee['account'].id,
        date_id=date_id,
    ).count()
    employee['work_login'] = StaffWorkLogin.query.filter_by(
        staff_id=employee['account'].id,
        date_id=date_id,
    ).order_by(StaffWorkLogin.start_datetime.asc()).first()
    employee['time_report_records'] = _fetch_time_report(context, target_date)


@when('the system derives QR attendance for employee "{employee_code}" on "{date_value}"')
def step_impl(context, employee_code, date_value):
    from app.staff.models import StaffWorkLogin

    employee = _ensure_employee(context, employee_code)
    context.active_employee = employee_code
    target_date = _parse_date(date_value)
    employee['target_date'] = target_date
    _login_employee(context, employee)

    for scan_time in employee['qrcode_times']:
        fixed_dt = BANGKOK_TZ.localize(datetime.combine(target_date, scan_time)).astimezone(UTC)
        qrcode_response = _post_qrcode_checkin(context, fixed_dt, employee)
        employee['qrcode_responses'].append(qrcode_response)
        employee['last_qrcode_response'] = qrcode_response
        if employee['first_qrcode_response'] is None:
            employee['first_qrcode_response'] = qrcode_response

    employee['gps_times'] = list(employee['qrcode_times'])
    employee['first_geo_response'] = employee['first_qrcode_response']
    employee['last_geo_response'] = employee['last_qrcode_response']

    date_id = StaffWorkLogin.generate_date_id(target_date)
    employee['work_login_count'] = StaffWorkLogin.query.filter_by(
        staff_id=employee['account'].id,
        date_id=date_id,
    ).count()
    employee['work_login'] = StaffWorkLogin.query.filter_by(
        staff_id=employee['account'].id,
        date_id=date_id,
    ).order_by(StaffWorkLogin.start_datetime.asc()).first()
    employee['time_report_records'] = _fetch_time_report(context, target_date)


def _current_employee(context):
    return context.checkin_employees[context.active_employee]


@then('the employee should have {expected_count:d} work login rows for the day')
def step_impl(context, expected_count):
    employee = _current_employee(context)
    assert employee['work_login_count'] == expected_count


def _to_bangkok(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(BANGKOK_TZ)


def _response_time_to_bangkok(response_payload):
    return datetime.fromisoformat(response_payload['time']).astimezone(BANGKOK_TZ)


@then('the actual check-in time should be "{expected_time}"')
def step_impl(context, expected_time):
    expected = _parse_time(expected_time)
    employee = _current_employee(context)
    if len(employee['gps_times']) > 1:
        assert len(employee['time_report_records']) == 1
        actual = datetime.fromisoformat(employee['time_report_records'][0]['start']).time().replace(second=0, microsecond=0)
    else:
        assert employee['first_geo_response'] is not None
        actual = _response_time_to_bangkok(employee['first_geo_response']).time().replace(second=0, microsecond=0)
    record = employee['work_login']
    assert record is not None
    assert actual == expected
    assert employee['last_geo_response'] is not None
    assert employee['last_geo_response']['message'] == 'success'
    assert employee['last_geo_response']['numScans'] == len(employee['gps_times'])
    if len(employee['gps_times']) > 1:
        assert employee['last_geo_response']['activity'] == 'checked out'
    else:
        assert employee['last_geo_response']['activity'] == 'checked in'


@then('the actual check-in time should be missing')
def step_impl(context):
    employee = _current_employee(context)
    assert employee['work_login'] is None
    assert employee['first_geo_response'] is None
    assert employee['last_geo_response'] is None
    assert employee['time_report_records'] == []


@then('the actual check-out time should be "{expected_time}"')
def step_impl(context, expected_time):
    expected = _parse_time(expected_time)
    employee = _current_employee(context)
    record = employee['work_login']
    assert record is not None
    assert employee['time_report_records']
    if len(employee['gps_times']) > 1:
        assert len(employee['time_report_records']) == 1
        actual = datetime.fromisoformat(employee['time_report_records'][0]['end']).time().replace(second=0, microsecond=0)
    else:
        assert employee['last_geo_response'] is not None
        actual = _response_time_to_bangkok(employee['last_geo_response']).time().replace(second=0, microsecond=0)
    assert actual == expected
    assert employee['last_geo_response'] is not None
    assert employee['last_geo_response']['message'] == 'success'
    assert employee['last_geo_response']['numScans'] == len(employee['gps_times'])


@then('the actual check-out time should be missing')
def step_impl(context):
    employee = _current_employee(context)
    record = employee['work_login']
    if record is None:
        assert employee['gps_times'] == []
        assert employee['first_geo_response'] is None
        assert employee['last_geo_response'] is None
        assert employee['time_report_records'] == []
        return
    if len(employee['gps_times']) > 1:
        assert len(employee['time_report_records']) == 1
        assert employee['time_report_records'][0]['end'] is None
    else:
        assert employee['last_geo_response'] is not None
        assert employee['last_geo_response']['numScans'] == 1
    assert employee['last_geo_response'] is not None
    assert employee['last_geo_response']['message'] == 'success'
    assert employee['last_geo_response']['numScans'] == len(employee['gps_times'])


@then('the employee should be marked as late')
def step_impl(context):
    employee = _current_employee(context)
    record = employee['work_login']
    assert record is not None
    if len(employee['gps_times']) > 1:
        assert len(employee['time_report_records']) == 1
        actual = datetime.fromisoformat(employee['time_report_records'][0]['start']).time()
    else:
        assert employee['first_geo_response'] is not None
        actual = _response_time_to_bangkok(employee['first_geo_response']).time()
    assert actual > context.office_start


@then('the employee should not be marked as late')
def step_impl(context):
    employee = _current_employee(context)
    record = employee['work_login']
    assert record is not None
    if len(employee['gps_times']) > 1:
        assert len(employee['time_report_records']) == 1
        actual = datetime.fromisoformat(employee['time_report_records'][0]['start']).time()
    else:
        assert employee['first_geo_response'] is not None
        actual = _response_time_to_bangkok(employee['first_geo_response']).time()
    assert actual <= context.office_start


@then('the employee should be marked as early checkout')
def step_impl(context):
    employee = _current_employee(context)
    record = employee['work_login']
    assert record is not None
    if len(employee['gps_times']) > 1:
        assert len(employee['time_report_records']) == 1
        assert employee['time_report_records'][0]['end'] is not None
        actual = datetime.fromisoformat(employee['time_report_records'][0]['end']).time()
    else:
        assert employee['last_geo_response'] is not None
        actual = _response_time_to_bangkok(employee['last_geo_response']).time()
    assert actual < context.office_end


@then('the employee should not be marked as early checkout')
def step_impl(context):
    employee = _current_employee(context)
    record = employee['work_login']
    assert record is not None
    if len(employee['gps_times']) > 1:
        assert len(employee['time_report_records']) == 1
        if employee['time_report_records'][0]['end'] is not None:
            actual = datetime.fromisoformat(employee['time_report_records'][0]['end']).time()
            assert actual >= context.office_end
    else:
        if employee['last_geo_response'] is not None:
            actual = _response_time_to_bangkok(employee['last_geo_response']).time()
        assert actual >= context.office_end


@then('the attendance record should require review')
def step_impl(context):
    employee = _current_employee(context)
    record = employee['work_login']
    assert record is None or record.end_datetime is None
    if employee['time_report_records']:
        assert employee['time_report_records'][0]['end'] is None
