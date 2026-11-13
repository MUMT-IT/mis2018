from __future__ import annotations

import importlib
import sys
import types
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import pytz
from werkzeug.exceptions import Forbidden, NotFound


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class _NoOpPermission:
    def union(self, _other):
        return self

    def require(self):
        def decorator(fn):
            return fn

        return decorator


class _NoOpBlueprint:
    def route(self, *_args, **_kwargs):
        def decorator(fn):
            return fn

        return decorator

    def before_request(self, fn):
        return fn


class _FakeQuery:
    def __init__(self, count_value=0):
        self.count_value = count_value
        self.filters = []
        self.rows = []

    def filter_by(self, **kwargs):
        self.filters.append(kwargs)
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self.rows)

    def count(self):
        return self.count_value

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.rows[0] if self.rows else None


class _FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1


def _module(name: str, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def _install_import_stubs(monkeypatch):
    class _ArrowMoment:
        def __init__(self, dt):
            self._dt = dt

        @property
        def datetime(self):
            return self._dt

        def date(self):
            return self._dt.date()

    def _arrow_now(_tz=None):
        return _ArrowMoment(pytz.timezone("Asia/Bangkok").localize(datetime(2026, 7, 21, 12, 0)))

    def _arrow_get(value, _tz=None):
        if isinstance(value, datetime):
            dt_value = value
            if dt_value.tzinfo is None:
                dt_value = pytz.timezone("Asia/Bangkok").localize(dt_value)
            return _ArrowMoment(dt_value)
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = pytz.timezone("Asia/Bangkok").localize(parsed)
        return _ArrowMoment(parsed)

    monkeypatch.setitem(sys.modules, "arrow", _module("arrow", now=_arrow_now, get=_arrow_get))

    staff_pkg = _module("app.staff", staffbp=_NoOpBlueprint())
    staff_pkg.__path__ = [str(PROJECT_ROOT / "app" / "staff")]
    monkeypatch.setitem(sys.modules, "app.staff", staff_pkg)

    main_mod = _module(
        "app.main",
        app=SimpleNamespace(config={}),
        db=SimpleNamespace(session=SimpleNamespace(add=lambda *_a, **_k: None, commit=lambda: None)),
        mail=SimpleNamespace(send=lambda *_a, **_k: None),
        csrf=SimpleNamespace(exempt=lambda fn: fn),
        get_weekdays=lambda *_a, **_k: [],
    )
    monkeypatch.setitem(sys.modules, "app.main", main_mod)

    models_mod = _module("app.models", Holidays=object(), Org=object())
    monkeypatch.setitem(sys.modules, "app.models", models_mod)

    pandas_mod = _module(
        "pandas",
        read_excel=lambda *_a, **_k: SimpleNamespace(apply=lambda *_a, **_k: None),
        isna=lambda value: value is None,
        DataFrame=lambda *args, **kwargs: SimpleNamespace(args=args, kwargs=kwargs),
    )
    monkeypatch.setitem(sys.modules, "pandas", pandas_mod)

    roles_mod = _module(
        "app.roles",
        admin_permission=_NoOpPermission(),
        hr_permission=_NoOpPermission(),
        secretary_permission=_NoOpPermission(),
        manager_permission=_NoOpPermission(),
        head_permission=_NoOpPermission(),
        event_staff_permission=_NoOpPermission(),
    )
    monkeypatch.setitem(sys.modules, "app.roles", roles_mod)

    linebot_mod = _module(
        "app.linebot_compat",
        LineBotApiError=RuntimeError,
        TextSendMessage=lambda text: SimpleNamespace(text=text),
        FlexSendMessage=lambda **kwargs: SimpleNamespace(**kwargs),
        BubbleContainer=lambda **kwargs: SimpleNamespace(**kwargs),
        BoxComponent=lambda **kwargs: SimpleNamespace(**kwargs),
        TextComponent=lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setitem(sys.modules, "app.linebot_compat", linebot_mod)

    auth_views_mod = _module(
        "app.auth.views",
        line_bot_api=SimpleNamespace(push_message=lambda *_a, **_k: None),
        _normalize_staff_email=lambda value: value,
    )
    monkeypatch.setitem(sys.modules, "app.auth.views", auth_views_mod)

    staff_forms_mod = _module(
        "app.staff.forms",
        StaffSeminarForm=object,
        create_seminar_attend_form=object,
        StaffGroupDetailForm=object,
        HeadPositionForm=object,
    )
    monkeypatch.setitem(sys.modules, "app.staff.forms", staff_forms_mod)

    staff_models_mod = _module(
        "app.staff.models",
        db=SimpleNamespace(session=_FakeSession()),
        StaffSpecialWorkFromHomeDay=SimpleNamespace(query=_FakeQuery()),
        StaffCheckinReminderSetting=SimpleNamespace(query=_FakeQuery()),
        StaffWorkLogin=SimpleNamespace(query=_FakeQuery()),
        StaffAccount=object,
        StaffLeaveQuota=object,
        StaffLeaveUsedQuota=object,
        StaffWorkFromHomeRequest=object,
        StaffSeminar=object,
        StaffSeminarAttend=object,
        StaffPersonalInfo=object,
        StaffRequestWorkLogin=object,
        StaffShiftSchedule=object,
        StaffSpecialGroup=object,
    )
    monkeypatch.setitem(sys.modules, "app.staff.models", staff_models_mod)

    eduqa_mod = _module("app.eduqa.models", EduQAInstructor=object)
    monkeypatch.setitem(sys.modules, "app.eduqa.models", eduqa_mod)

    comhealth_mod = _module("app.comhealth.views", allowed_file=lambda *_a, **_k: True)
    monkeypatch.setitem(sys.modules, "app.comhealth.views", comhealth_mod)

    google_cred_mod = _module("app.google_credential_utils", load_google_credentials_json=lambda: None)
    monkeypatch.setitem(sys.modules, "app.google_credential_utils", google_cred_mod)

    url_utils_mod = _module("app.url_utils", external_url=lambda value: value)
    monkeypatch.setitem(sys.modules, "app.url_utils", url_utils_mod)

    requests_mod = _module("requests")
    monkeypatch.setitem(sys.modules, "requests", requests_mod)

    gviz_mod = _module("gviz_api", DataTable=lambda *_a, **_k: SimpleNamespace(LoadData=lambda *_a, **_k: None, ToJSon=lambda *_a, **_k: "{}"))
    monkeypatch.setitem(sys.modules, "gviz_api", gviz_mod)

    qrcode_mod = _module("qrcode")
    monkeypatch.setitem(sys.modules, "qrcode", qrcode_mod)

    flask_mail_mod = _module("flask_mail", Message=lambda *args, **kwargs: SimpleNamespace(args=args, kwargs=kwargs))
    monkeypatch.setitem(sys.modules, "flask_mail", flask_mail_mod)

    flask_admin_mod = _module("flask_admin", BaseView=object, expose=lambda *args, **kwargs: (lambda fn: fn))
    monkeypatch.setitem(sys.modules, "flask_admin", flask_admin_mod)

    pydrive_auth_mod = _module("pydrive.auth", ServiceAccountCredentials=object, GoogleAuth=object)
    monkeypatch.setitem(sys.modules, "pydrive.auth", pydrive_auth_mod)

    pydrive_drive_mod = _module("pydrive.drive", GoogleDrive=object)
    monkeypatch.setitem(sys.modules, "pydrive.drive", pydrive_drive_mod)

    monkeypatch.setitem(sys.modules, "pydrive", _module("pydrive"))
    monkeypatch.setitem(
        sys.modules,
        "app.procurement.models",
        _module(
            "app.procurement.models",
            ProcurementPlan=object,
            ProcurementPlanCommitteeMember=object,
        ),
    )

    sys.modules.pop("app.staff.views", None)


@pytest.fixture
def staff_views(monkeypatch):
    _install_import_stubs(monkeypatch)
    views = importlib.import_module("app.staff.views")
    from sqlalchemy import column
    for name in ('StaffLeaveRequest', 'StaffWorkFromHomeRequest'):
        monkeypatch.setattr(views, name, SimpleNamespace(
            query=_FakeQuery(), start_datetime=column('start'),
            end_datetime=column('end'), cancelled_at=column('cancelled_at')), raising=False)
    def fake_delivery(account, target_date, mode, scheduled_time, message):
        views.line_bot_api.push_message(to=account.line_id, messages=message)
        return 'sent'
    monkeypatch.setattr(views, '_deliver_checkin_reminder', fake_delivery)
    return views


@pytest.mark.parametrize("has_records", [False, True])
@pytest.mark.parametrize("load_mode", [None, "table", "full"])
def test_daily_attendance_staff_detail_loading(staff_views, monkeypatch, has_records, load_mode):
    day = date(2026, 11, 10)
    account = SimpleNamespace(leave_requests=[])
    record = SimpleNamespace(
        attendance_date=day,
        status="present",
        first_checkin_at=datetime(2026, 11, 10, 3),
        last_checkout_at=datetime(2026, 11, 10, 10),
    )
    account_query = Mock()
    account_query.join.return_value.filter.return_value.first_or_404.return_value = account
    attendance_query = Mock()
    attendance_query.filter.return_value.order_by.return_value.all.return_value = (
        [record] if has_records else []
    )
    monkeypatch.setattr(staff_views, "StaffAccount", SimpleNamespace(
        query=account_query, id=1, personal_id=1,
    ))
    monkeypatch.setattr(staff_views, "StaffPersonalInfo", SimpleNamespace(id=1))
    monkeypatch.setattr(staff_views, "StaffDailyAttendance", SimpleNamespace(
        query=attendance_query, staff_id=1, attendance_date=Mock(),
    ), raising=False)
    monkeypatch.setattr(staff_views, "_active_staff_filters", lambda: ())
    refresh = Mock()
    monkeypatch.setattr(staff_views, "refresh_daily_attendance", refresh)
    badges = Mock(return_value=["double-tap"])
    monkeypatch.setattr(staff_views, "get_home_attendance_badges", badges)
    monkeypatch.setattr(staff_views, "request", SimpleNamespace(
        args={"start": day.isoformat(), "end": day.isoformat(), "load": load_mode},
    ))
    monkeypatch.setattr(staff_views, "render_template", lambda template, **context: (template, context))

    response = staff_views.hr_daily_attendance_staff_detail.__wrapped__(1)

    if load_mode == "table":
        (template, context), status, headers = response
        assert template == "staff/_hr_daily_attendance_staff_table.html"
        assert status == 200
        assert headers["X-Attendance-Table"] == "1"
        badges.assert_not_called()
    else:
        template, context = response
        assert template == "staff/hr_daily_attendance_staff_detail.html"
        badges.assert_called_once_with(account, datetime.now(staff_views.tz).date())
        assert context["attendance_badges"] == ["double-tap"]
    if load_mode is None:
        refresh.assert_not_called()
        attendance_query.filter.assert_not_called()
        assert "rows" not in context
        return

    refresh.assert_called_once_with(day, staff_ids=[1])
    assert context["rows"] == ([
        {"record": record, "leave_period": None, "is_late": True, "is_short_hours": True}
    ] if has_records else [])


@pytest.mark.parametrize('reference_date, expected_start, expected_end', [
    (date(2026, 1, 1), date(2026, 1, 1), date(2026, 6, 30)),
    (date(2026, 6, 1), date(2026, 1, 1), date(2026, 6, 30)),
    (date(2026, 6, 30), date(2026, 1, 1), date(2026, 6, 30)),
    (date(2026, 9, 1), date(2026, 9, 1), date(2026, 12, 31)),
    (date(2026, 10, 1), date(2026, 9, 1), date(2026, 12, 31)),
    (date(2026, 12, 31), date(2026, 9, 1), date(2026, 12, 31)),
    (date(2027, 1, 1), date(2027, 1, 1), date(2027, 6, 30)),
    (date(2027, 6, 30), date(2027, 1, 1), date(2027, 6, 30)),
    (date(2027, 7, 1), date(2027, 7, 1), date(2027, 12, 31)),
    (date(2028, 1, 1), date(2028, 1, 1), date(2028, 6, 30)),
])
def test_civil_servant_login_quota_period_boundaries(
    staff_views, reference_date, expected_start, expected_end
):
    staff = SimpleNamespace(employment=SimpleNamespace(title='ข้าราชการ'))

    assert staff_views._current_login_quota_period(reference_date, staff) == (
        expected_start, expected_end, 15
    )


@pytest.mark.parametrize('employment_title, quota_limit', [
    ('พนักงานมหาวิทยาลัย', 30),
    ('ลูกจ้างประจำ', 30),
    ('ลูกจ้างชั่วคราว', 30),
    ('ลูกจ้างปฏิบัติงานนอกเวลา', 30),
])
@pytest.mark.parametrize('reference_date, expected_start, expected_end', [
    (date(2026, 9, 1), date(2026, 9, 1), date(2027, 6, 30)),
    (date(2026, 10, 1), date(2026, 9, 1), date(2027, 6, 30)),
    (date(2026, 12, 31), date(2026, 9, 1), date(2027, 6, 30)),
    (date(2027, 1, 1), date(2026, 9, 1), date(2027, 6, 30)),
    (date(2027, 6, 30), date(2026, 9, 1), date(2027, 6, 30)),
    (date(2027, 7, 1), date(2027, 7, 1), date(2028, 6, 30)),
    (date(2028, 6, 30), date(2027, 7, 1), date(2028, 6, 30)),
    (date(2028, 7, 1), date(2028, 7, 1), date(2029, 6, 30)),
])
def test_other_employment_login_quota_periods(
    staff_views, employment_title, quota_limit, reference_date, expected_start, expected_end
):
    staff = SimpleNamespace(employment=SimpleNamespace(title=employment_title))
    assert staff_views._current_login_quota_period(reference_date, staff) == (
        expected_start, expected_end, quota_limit
    )


@pytest.mark.parametrize('round_time, expected_ids', [
    ('16:30', [1, 2]), ('17:00', [3, 7]),
])
def test_checkout_reminder_groups_and_exclusions(staff_views, monkeypatch, round_time, expected_ids):
    bangkok = pytz.timezone('Asia/Bangkok')
    target_date = date(2026, 11, 5)
    accounts = [SimpleNamespace(id=i, line_id=f'line-{i}') for i in range(1, 9)]
    accounts[7].line_id = None
    monkeypatch.setattr(staff_views, 'StaffAccount', SimpleNamespace(get_active_accounts=lambda: accounts))

    def record(staff_id, hour, minute=0, end=None, day=5):
        return SimpleNamespace(
            staff_id=staff_id,
            start_datetime=bangkok.localize(datetime(2026, 11, day, hour, minute)),
            end_datetime=end,
        )

    records = [
        record(1, 7), record(2, 8, 30), record(3, 8, 31),
        record(4, 8, end=bangkok.localize(datetime(2026, 11, 5, 16, 30))),
        record(5, 8), record(5, 16, 30),  # Scan-based checkout.
        record(6, 8, day=4),  # No check-in today.
        record(7, 9), record(8, 8),
    ]
    assert [account.id for account in staff_views._build_missing_checkout_recipients(
        target_date, round_time, records=records
    )] == expected_ids

    # An approved checkout removes the remaining staff member on recalculation.
    records[2].end_datetime = bangkok.localize(datetime(2026, 11, 5, 16, 45))
    records[-2].correction_type = 'checkout'
    assert 3 not in [account.id for account in staff_views._build_missing_checkout_recipients(
        target_date, '17:00', records=records
    )]
    assert staff_views._build_missing_checkout_recipients(target_date, '17:00', records=records) == []


@pytest.mark.parametrize('method, holiday, expected_sent', [
    ('GET', False, 0), ('POST', False, 1), ('POST', True, 0),
])
def test_checkout_reminder_preview_send_and_holiday(
    staff_views, monkeypatch, method, holiday, expected_sent
):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, zone):
            return zone.localize(cls(2026, 11, 5, 16, 30))

    monkeypatch.setenv('JOB_TOKEN', 'test-token')
    monkeypatch.setattr(staff_views, 'datetime', FixedDatetime)
    monkeypatch.setattr(staff_views, 'request', SimpleNamespace(
        method=method, values={'job_token': 'test-token', 'round': '16:30'},
    ))
    monkeypatch.setattr(staff_views, '_get_holiday_for_date', lambda _: holiday)
    monkeypatch.setattr(staff_views, '_build_missing_checkout_recipients', lambda *_: [
        SimpleNamespace(id=1, fullname='Test Staff', line_id='line-1'),
    ])
    monkeypatch.setattr(staff_views, 'jsonify', lambda payload: payload)
    pushes = []
    monkeypatch.setattr(staff_views, 'line_bot_api', SimpleNamespace(
        push_message=lambda **kwargs: pushes.append(kwargs),
    ))
    payload = staff_views.line_remind_missing_checkout()

    assert payload['sent_count'] == expected_sent
    assert len(pushes) == expected_sent
    assert payload['recipient_count'] == (0 if holiday else 1)


@pytest.mark.parametrize('token', [None, 'wrong-token'])
def test_checkout_reminder_requires_scheduler_token_or_admin(staff_views, monkeypatch, token):
    monkeypatch.setenv('JOB_TOKEN', 'test-token')
    monkeypatch.setattr(staff_views, 'request', SimpleNamespace(
        method='POST', values={'job_token': token, 'round': '16:30'},
    ))
    monkeypatch.setattr(staff_views, 'current_user', SimpleNamespace(is_authenticated=False))
    from werkzeug.exceptions import Unauthorized
    with pytest.raises(Unauthorized):
        staff_views.line_remind_missing_checkout()


@pytest.mark.parametrize('record_source', ['scan', 'approved_request'])
@pytest.mark.parametrize('endpoint', ['send_summary_data', 'send_time_report_data'])
def test_summary_calendar_includes_weekend_and_holiday_checkins(staff_views, monkeypatch, record_source, endpoint):
    class Query(_FakeQuery):
        def __iter__(self):
            return iter(self.rows)

    class Column:
        def in_(self, _values):
            return self

        def between(self, *_args):
            return self

    employee_query = Query()
    employee_query.rows = [SimpleNamespace(th_firstname='Test', staff_account=SimpleNamespace())]
    monkeypatch.setattr(staff_views, 'StaffPersonalInfo', SimpleNamespace(
        query=employee_query, org_id=Column(),
    ))
    login_query = Query()
    monkeypatch.setattr(staff_views, 'StaffWorkLogin', SimpleNamespace(query=login_query, start_datetime=Column()))
    monkeypatch.setattr(staff_views, 'func', SimpleNamespace(timezone=lambda *_: Column()))
    monkeypatch.setattr(staff_views, 'jsonify', lambda payload: payload)
    monkeypatch.setattr(staff_views, 'request', SimpleNamespace(args=SimpleNamespace(
        get=lambda key, **_: {'tab': 'login'}.get(key),
    )))
    monkeypatch.setattr(staff_views, '_approved_half_day_leave_period', lambda *_: None)
    monkeypatch.setattr(staff_views, 'current_user', SimpleNamespace(
        personal_info=SimpleNamespace(th_firstname='Test'),
    ))
    # Friday holiday, Saturday, Sunday, and an ordinary Monday.
    dates = [date(2026, 10, day) for day in (23, 24, 25, 26)]
    monkeypatch.setattr(staff_views, '_working_dates_between', lambda *_: {dates[-1]})
    login_query.rows = [
        SimpleNamespace(
            id=index, staff_id=1, staff=SimpleNamespace(fullname='Test Staff'),
            start_datetime=pytz.timezone('Asia/Bangkok').localize(
                datetime.combine(day, datetime.strptime('08:00', '%H:%M').time())
            ),
            end_datetime=None, qrcode_in_exp_datetime=None, qrcode_out_exp_datetime=None,
            lat=None, long=None, record_source=record_source,
            correction_type='checkin' if record_source == 'approved_request' else None,
        )
        for index, day in enumerate(dates)
    ]

    events = getattr(staff_views, endpoint).__wrapped__()

    assert [event['start'][:10] for event in events] == [day.isoformat() for day in dates]
    assert all(event['type'] == 'login' for event in events)
    assert all(event['approved_checkin'] == (record_source == 'approved_request') for event in events)
    assert all(event['has_approved_correction'] == (record_source == 'approved_request') for event in events)


def test_create_work_login_record_increments_daily_scan_count_and_sets_qrcode_expiry(staff_views, monkeypatch):
    fake_session = _FakeSession()
    monkeypatch.setattr(staff_views, "db", SimpleNamespace(session=fake_session))

    class FakeStaffWorkLogin:
        query = _FakeQuery(count_value=2)

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        @staticmethod
        def generate_date_id(date_value):
            return date_value.strftime("%Y%m%d")

    monkeypatch.setattr(staff_views, "StaffWorkLogin", FakeStaffWorkLogin)

    staff_account = SimpleNamespace(id=7, fullname="Test User")
    now = pytz.utc.localize(datetime(2026, 6, 26, 1, 30))
    qrcode_exp = pytz.timezone("Asia/Bangkok").localize(datetime(2026, 6, 26, 23, 59, 59))

    record, activity, num_scans = staff_views._create_work_login_record(
        staff_account,
        now,
        "13.0000",
        "100.0000",
        qrcode_exp_datetime=qrcode_exp,
        note="qrcode",
    )

    assert num_scans == 3
    assert activity == "checked out"
    assert record.date_id == "20260626"
    assert record.staff is staff_account
    assert record.lat == 13.0
    assert record.long == 100.0
    assert record.num_scans == 3
    assert record.note == "qrcode"
    assert record.qrcode_in_exp_datetime == qrcode_exp.astimezone(pytz.utc)
    assert fake_session.added == [record]
    assert fake_session.commits == 1


def test_morning_ot_ending_at_0830_counts_work_hours_from_ot_end(staff_views, monkeypatch):
    bangkok = pytz.timezone("Asia/Bangkok")
    query = _FakeQuery(count_value=1)
    query.rows = [SimpleNamespace(start_datetime=bangkok.localize(datetime(2026, 6, 26, 6, 0)))]

    class FakeStaffWorkLogin:
        start_datetime = SimpleNamespace(asc=lambda: None)

        @staticmethod
        def generate_date_id(_date_value):
            return "20260626"

    FakeStaffWorkLogin.query = query
    ot_range = SimpleNamespace(
        lower=datetime(2026, 6, 26, 6, 0),
        upper=datetime(2026, 6, 26, 8, 30),
    )
    staff = SimpleNamespace(
        ot_record_staff=[SimpleNamespace(canceled_at=None, shift=SimpleNamespace(datetime=ot_range))]
    )
    monkeypatch.setattr(staff_views, "StaffWorkLogin", FakeStaffWorkLogin)

    info = staff_views._get_early_checkout_info(
        staff, bangkok.localize(datetime(2026, 6, 26, 16, 0)).astimezone(pytz.utc)
    )

    assert info["worked_hours"] == 7.5
    assert info["work_start"].isoformat() == "2026-06-26T08:30:00+07:00"


def test_morning_ot_ending_at_0815_completes_eight_hours_at_1615(staff_views, monkeypatch):
    bangkok = pytz.timezone("Asia/Bangkok")
    query = _FakeQuery(count_value=1)
    query.rows = [SimpleNamespace(start_datetime=bangkok.localize(datetime(2026, 6, 26, 6, 0)))]

    class FakeStaffWorkLogin:
        start_datetime = SimpleNamespace(asc=lambda: None)

        @staticmethod
        def generate_date_id(_date_value):
            return "20260626"

    FakeStaffWorkLogin.query = query
    ot_range = SimpleNamespace(
        lower=datetime(2026, 6, 26, 6, 0),
        upper=datetime(2026, 6, 26, 8, 15),
    )
    staff = SimpleNamespace(
        ot_record_staff=[SimpleNamespace(canceled_at=None, shift=SimpleNamespace(datetime=ot_range))]
    )
    monkeypatch.setattr(staff_views, "StaffWorkLogin", FakeStaffWorkLogin)

    assert staff_views._get_early_checkout_info(
        staff, bangkok.localize(datetime(2026, 6, 26, 16, 15)).astimezone(pytz.utc)
    ) is None


def test_morning_ot_ending_at_eight_does_not_add_1630_block(staff_views, monkeypatch):
    bangkok = pytz.timezone("Asia/Bangkok")
    query = _FakeQuery(count_value=1)
    query.rows = [SimpleNamespace(start_datetime=bangkok.localize(datetime(2026, 6, 26, 6, 0)))]

    class FakeStaffWorkLogin:
        start_datetime = SimpleNamespace(asc=lambda: None)

        @staticmethod
        def generate_date_id(_date_value):
            return "20260626"

    FakeStaffWorkLogin.query = query
    staff = SimpleNamespace(ot_record_staff=[SimpleNamespace(
        canceled_at=None,
        shift=SimpleNamespace(datetime=SimpleNamespace(
            lower=datetime(2026, 6, 26, 6, 0),
            upper=datetime(2026, 6, 26, 8, 0),
        )),
    )])
    monkeypatch.setattr(staff_views, "StaffWorkLogin", FakeStaffWorkLogin)

    assert staff_views._get_early_checkout_info(
        staff, bangkok.localize(datetime(2026, 6, 26, 16, 0)).astimezone(pytz.utc)
    ) is None


def test_daily_work_login_rows_collapses_scans_by_day_and_uses_first_and_last_scan(staff_views):
    tz = pytz.timezone("Asia/Bangkok")
    staff = SimpleNamespace(fullname="Test Staff")

    def _record(record_id, local_dt, lat, lon, *, qrcode_in=None, qrcode_out=None):
        start_dt = tz.localize(local_dt).astimezone(pytz.utc).replace(tzinfo=None)
        kwargs = {
            "id": record_id,
            "staff_id": 7,
            "staff": staff,
            "start_datetime": start_dt,
            "end_datetime": None,
            "lat": lat,
            "long": lon,
            "qrcode_in_exp_datetime": qrcode_in,
            "qrcode_out_exp_datetime": qrcode_out,
        }
        return SimpleNamespace(**kwargs)

    rows = staff_views._daily_work_login_rows(
        [
            _record(11, datetime(2026, 6, 26, 7, 48), 13.1, 100.1, qrcode_in=pytz.utc.localize(datetime(2026, 6, 26, 7, 50))),
            _record(12, datetime(2026, 6, 26, 12, 3), 13.2, 100.2, qrcode_in=pytz.utc.localize(datetime(2026, 6, 26, 12, 5))),
            _record(13, datetime(2026, 6, 26, 18, 30), 13.3, 100.3, qrcode_in=pytz.utc.localize(datetime(2026, 6, 26, 18, 32))),
        ]
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["staff_id"] == 7
    assert row["date"].isoformat() == "2026-06-26"
    assert row["start"] == "2026-06-26T07:48:00+07:00"
    assert row["end"] == "2026-06-26T18:30:00+07:00"
    assert row["lat"] == pytest.approx(13.1)
    assert row["lon"] == pytest.approx(100.1)
    assert row["location"] == '<a href="https://maps.google.com/?q=13.1,100.1">Click</a>'
    assert row["start_expired"] is False
    assert row["end_expired"] is False


def test_to_bangkok_normalizes_naive_utc_datetimes(staff_views):
    converted = staff_views._to_bangkok(datetime(2026, 6, 26, 0, 48))
    assert converted.isoformat() == "2026-06-26T07:48:00+07:00"


@pytest.mark.parametrize(
    "stored_datetime",
    [
        datetime(2026, 6, 26, 0, 48),
        pytz.utc.localize(datetime(2026, 6, 26, 0, 48)),
    ],
)
def test_format_bangkok_datetime_normalizes_database_values(staff_views, stored_datetime):
    assert staff_views._format_bangkok_datetime(stored_datetime) == "26/06/2026 07:48"


@pytest.mark.parametrize("list_view", ["summary", "request_list"])
def test_approver_lists_hide_own_request(staff_views, monkeypatch, list_view):
    own_request = SimpleNamespace(id=1, staff_account_id=29, approver_id=29)
    other_request = SimpleNamespace(id=2, staff_account_id=42, approver_id=29)
    query = _FakeQuery()
    query.rows = [own_request, other_request]
    class StaffIdColumn:
        def __ne__(self, account_id):
            return lambda row: row.staff_account_id != account_id

    def filter_rows(predicate):
        query.rows = [row for row in query.rows if predicate(row)]
        return query

    query.filter = filter_rows
    monkeypatch.setattr(staff_views, "StaffRequestWorkLogin", SimpleNamespace(
        query=query, requested_at=SimpleNamespace(desc=lambda: None), staff_account_id=StaffIdColumn(),
    ))

    if list_view == "summary":
        assert staff_views._pending_clockin_requests_for(29) == [other_request]
        assert query.filters == [{"approver_id": 29, "approved_at": None, "cancelled_at": None}]
    else:
        monkeypatch.setattr(staff_views, "current_user", SimpleNamespace(id=29))
        monkeypatch.setattr(staff_views, "render_template", lambda template, **context: context)
        assert staff_views.list_for_clockin_clockout.__wrapped__()["all_requests"] == [other_request]
        assert query.filters == [{"approver_id": 29}]


def test_clock_requester_can_view_approved_request(staff_views, monkeypatch):
    clock_request = SimpleNamespace(
        id=5051,
        staff_account_id=42,
        approver_id=29,
        approved_at=pytz.utc.localize(datetime(2026, 9, 30, 3, 0)),
    )
    monkeypatch.setattr(
        staff_views,
        "StaffRequestWorkLogin",
        SimpleNamespace(query=SimpleNamespace(get_or_404=lambda request_id: clock_request)),
    )
    monkeypatch.setattr(staff_views, "current_user", SimpleNamespace(id=42))
    monkeypatch.setattr(
        staff_views,
        "request",
        SimpleNamespace(method="GET", args=SimpleNamespace(get=lambda _key: None)),
    )
    monkeypatch.setattr(
        staff_views,
        "render_template",
        lambda template, **context: (template, context),
    )

    template, context = staff_views.approved_for_clockin_clockout.__wrapped__(5051)

    assert template == "staff/checkin_approval.html"
    assert context["clock_request"] is clock_request
    assert context["can_approve"] is False


@pytest.mark.parametrize("approver_id", [29, 42])
@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("decision", ["yes", "no"])
def test_clock_requester_cannot_submit_approval_decision(staff_views, monkeypatch, approver_id, method, decision):
    clock_request = SimpleNamespace(
        id=5051,
        staff_account_id=42,
        approver_id=approver_id,
    )
    monkeypatch.setattr(
        staff_views,
        "StaffRequestWorkLogin",
        SimpleNamespace(query=SimpleNamespace(get_or_404=lambda request_id: clock_request)),
    )
    monkeypatch.setattr(staff_views, "current_user", SimpleNamespace(id=42))
    monkeypatch.setattr(
        staff_views,
        "request",
        SimpleNamespace(method=method, args={"approved": decision}, form={"approved": decision}),
    )

    with pytest.raises(Forbidden):
        staff_views.approved_for_clockin_clockout.__wrapped__(5051)


def test_unrelated_staff_cannot_view_clock_request(staff_views, monkeypatch):
    monkeypatch.setattr(staff_views, "StaffWorkFromHomeApprover", SimpleNamespace(
        query=_FakeQuery(),
    ), raising=False)
    clock_request = SimpleNamespace(
        id=5051,
        staff_account_id=42,
        approver_id=29,
    )
    monkeypatch.setattr(
        staff_views,
        "StaffRequestWorkLogin",
        SimpleNamespace(query=SimpleNamespace(get_or_404=lambda request_id: clock_request)),
    )
    monkeypatch.setattr(staff_views, "current_user", SimpleNamespace(id=77))

    with pytest.raises(NotFound):
        staff_views.approved_for_clockin_clockout.__wrapped__(5051)


@pytest.mark.parametrize(
    ("start_time", "end_time", "expected_hours"),
    [
        ((7, 30), (17, 30), 8.0),
        ((8, 30), (16, 30), 8.0),
        ((9, 15), (18, 45), 7.75),
        ((9, 15), (15, 0), 5.75),
        ((10, 0), (18, 0), 7.0),
        ((6, 0), (10, 0), 2.0),
        ((8, 0), (17, 0), 8.0),
        ((17, 0), (20, 0), 0.0),
        ((6, 30), (7, 30), 0.0),
        ((18, 0), (19, 0), 0.0),
    ],
)
def test_calculate_work_hours_counts_only_eight_to_seventeen_and_caps_total(
    staff_views, start_time, end_time, expected_hours
):
    tz = pytz.timezone("Asia/Bangkok")
    start_dt = tz.localize(datetime(2026, 6, 26, *start_time))
    end_dt = tz.localize(datetime(2026, 6, 26, *end_time))

    assert staff_views._calculate_work_hours(start_dt, end_dt) == expected_hours


def test_calculate_work_hours_requires_checkout(staff_views):
    start_dt = pytz.timezone("Asia/Bangkok").localize(datetime(2026, 6, 26, 8, 0))

    assert staff_views._calculate_work_hours(start_dt, None) is None


@pytest.mark.parametrize(
    ('end_time', 'expected_short_hours'),
    [((16, 32, 26), True), ((16, 32, 31), False), ((16, 32, 36), False)],
)
def test_work_hours_status_uses_exact_duration_before_display_rounding(
    staff_views, end_time, expected_short_hours
):
    tz = pytz.timezone('Asia/Bangkok')
    checkin = tz.localize(datetime(2026, 11, 12, 8, 32, 31))
    checkout = tz.localize(datetime(2026, 11, 12, *end_time))

    worked_hours = staff_views._calculate_work_hours(checkin, checkout)
    display, is_short_hours = staff_views._work_hours_display_and_status(worked_hours)

    assert display == '8.0 hrs.'
    assert is_short_hours is expected_short_hours
    style = staff_views._work_login_event_style(False, is_short_hours, True)
    assert style[3] == (['is-short-hours'] if expected_short_hours else ['is-complete-hours'])


def test_work_login_event_style_uses_warning_for_short_hours(staff_views):
    text_color, background_color, border_color, class_names = (
        staff_views._work_login_event_style(True, True, True)
    )

    assert text_color == "#10264c"
    assert background_color == "#fff3bf"
    assert border_color == "#e6cf73"
    assert class_names == ["is-late-login", "is-short-hours"]


def test_work_login_event_style_uses_soft_green_for_complete_hours(staff_views):
    text_color, background_color, border_color, class_names = (
        staff_views._work_login_event_style(False, False, True)
    )

    assert text_color == "#245b38"
    assert background_color == "#e4f3e9"
    assert border_color == "#b8ddc4"
    assert class_names == ["is-complete-hours"]


def test_get_login_records_collapses_multiple_scans_and_filters_by_department(staff_views, monkeypatch):
    tz = pytz.timezone("Asia/Bangkok")
    org_id = 41

    staff_match = SimpleNamespace(
        id=7,
        fullname="Matched Staff",
        personal_info=SimpleNamespace(org_id=org_id),
    )
    staff_other = SimpleNamespace(
        id=8,
        fullname="Other Staff",
        personal_info=SimpleNamespace(org_id=99),
    )

    def _record(record_id, staff, local_dt, *, lat, lon):
        return SimpleNamespace(
            id=record_id,
            staff_id=staff.id,
            staff=staff,
            start_datetime=tz.localize(local_dt).astimezone(pytz.utc).replace(tzinfo=None),
            end_datetime=None,
            lat=lat,
            long=lon,
            qrcode_in_exp_datetime=pytz.utc.localize(datetime(2026, 6, 26, 0, 0)),
            qrcode_out_exp_datetime=None,
        )

    query = _FakeQuery()
    query.rows = [
        _record(1, staff_match, datetime(2026, 6, 26, 7, 48), lat=13.1, lon=100.1),
        _record(2, staff_match, datetime(2026, 6, 26, 18, 30), lat=13.2, lon=100.2),
        _record(3, staff_other, datetime(2026, 6, 26, 8, 10), lat=99.9, lon=99.9),
    ]

    staff_account_query = SimpleNamespace(get=lambda staff_id: staff_match if staff_id == staff_match.id else staff_other)
    monkeypatch.setattr(staff_views, "StaffAccount", SimpleNamespace(query=staff_account_query))
    monkeypatch.setattr(staff_views, "StaffWorkLogin", SimpleNamespace(query=query, start_datetime=None))
    monkeypatch.setattr(
        staff_views,
        "request",
        SimpleNamespace(args=SimpleNamespace(get=lambda key, default=None, type=None: {"date": "26/06/2026", "dept_id": org_id}.get(key, default))),
    )
    monkeypatch.setattr(staff_views, "current_user", SimpleNamespace(personal_info=SimpleNamespace(org_id=org_id)))
    monkeypatch.setitem(staff_views.__dict__, "func", SimpleNamespace(timezone=lambda *_a, **_k: None))
    monkeypatch.setattr(staff_views, "jsonify", lambda payload: SimpleNamespace(get_json=lambda: payload))

    response = staff_views.get_login_records.__wrapped__()
    payload = response.get_json()

    assert len(payload["data"]) == 1
    row = payload["data"][0]
    assert row["staff_name"] == "Matched Staff"
    assert row["start"] == "2026-06-26T07:48:00+07:00"
    assert row["end"] == "2026-06-26T18:30:00+07:00"
    assert row["lat"] == pytest.approx(13.1)
    assert row["lon"] == pytest.approx(100.1)
    assert row["location"] == '<a href="https://maps.google.com/?q=13.1,100.1">Click</a>'


def test_build_login_summary_dashboard_groups_by_employee_and_calculates_counts(staff_views, monkeypatch):
    tz = pytz.timezone("Asia/Bangkok")
    dept_id = 41

    alice_account = SimpleNamespace(id=7, fullname="Alice Example")
    bob_account = SimpleNamespace(id=8, fullname="Bob Example")

    alice = SimpleNamespace(
        staff_account=alice_account,
        fullname="Alice Example",
        org=SimpleNamespace(name="HR"),
        position="Officer",
        job_position=None,
        academic_staff=False,
    )
    bob = SimpleNamespace(
        staff_account=bob_account,
        fullname="Bob Example",
        org=SimpleNamespace(name="HR"),
        position=None,
        job_position=None,
        academic_staff=False,
    )

    records = [
        SimpleNamespace(
            id=1,
            staff_id=alice_account.id,
            staff=alice_account,
            start_datetime=tz.localize(datetime(2026, 7, 1, 8, 50)).astimezone(pytz.utc).replace(tzinfo=None),
            end_datetime=tz.localize(datetime(2026, 7, 1, 17, 0)).astimezone(pytz.utc).replace(tzinfo=None),
            lat=13.1,
            long=100.1,
            qrcode_in_exp_datetime=pytz.utc.localize(datetime(2026, 7, 1, 9, 0)),
            qrcode_out_exp_datetime=pytz.utc.localize(datetime(2026, 7, 1, 16, 30)),
        ),
        SimpleNamespace(
            id=2,
            staff_id=alice_account.id,
            staff=alice_account,
            start_datetime=tz.localize(datetime(2026, 7, 2, 9, 10)).astimezone(pytz.utc).replace(tzinfo=None),
            end_datetime=tz.localize(datetime(2026, 7, 2, 16, 0)).astimezone(pytz.utc).replace(tzinfo=None),
            lat=13.2,
            long=100.2,
            qrcode_in_exp_datetime=pytz.utc.localize(datetime(2026, 7, 2, 9, 0)),
            qrcode_out_exp_datetime=pytz.utc.localize(datetime(2026, 7, 2, 16, 30)),
        ),
    ]

    staff_personal_query = SimpleNamespace(filter_by=lambda **kwargs: SimpleNamespace(all=lambda: [alice, bob]))
    staff_work_query = _FakeQuery()
    staff_work_query.rows = records

    monkeypatch.setattr(staff_views, "StaffPersonalInfo", SimpleNamespace(query=staff_personal_query))
    monkeypatch.setattr(staff_views, "StaffWorkLogin", SimpleNamespace(query=staff_work_query))

    dashboard = staff_views._build_login_summary_dashboard(
        datetime(2026, 7, 1).date(),
        datetime(2026, 7, 31).date(),
        dept_id,
    )

    assert dashboard["totals"]["employees"] == 2
    assert dashboard["totals"]["employees_with_records"] == 1
    assert dashboard["totals"]["complete_days"] == 2
    assert dashboard["totals"]["late_checkins"] == 1
    assert dashboard["totals"]["early_checkouts"] == 1
    assert dashboard["totals"]["average_hours_per_day"] == 7.4

    alice_summary = dashboard["employees"][0]
    assert alice_summary["name"] == "Alice Example"
    assert alice_summary["complete_days"] == 2
    assert alice_summary["late_checkins"] == 1
    assert alice_summary["early_checkouts"] == 1
    assert alice_summary["average_hours_per_day"] == 7.4

    bob_summary = dashboard["employees"][1]
    assert bob_summary["name"] == "Bob Example"
    assert bob_summary["complete_days"] == 0


def test_get_login_summary_data_uses_requested_date_range(staff_views, monkeypatch):
    captured = {}

    monkeypatch.setattr(
        staff_views,
        "_build_login_summary_dashboard",
        lambda start_date, end_date, dept_id: captured.update(
            {"start_date": start_date, "end_date": end_date, "dept_id": dept_id}
        ) or {"totals": {}, "employees": [], "date_range": {"start": "2026-07-01", "end": "2026-07-31"}},
    )
    monkeypatch.setattr(staff_views, "jsonify", lambda payload: SimpleNamespace(get_json=lambda: payload))
    monkeypatch.setattr(
        staff_views,
        "request",
        SimpleNamespace(
            args=SimpleNamespace(
                get=lambda key, default=None, type=None: {"start": "01/07/2026", "end": "31/07/2026", "dept_id": 41}.get(
                    key, default
                )
            )
        ),
    )
    monkeypatch.setattr(staff_views, "current_user", SimpleNamespace(personal_info=SimpleNamespace(org_id=99)))

    response = staff_views.get_login_summary_data.__wrapped__()
    payload = response.get_json()

    assert payload["date_range"]["start"] == "2026-07-01"
    assert captured["start_date"].isoformat() == "2026-07-01"
    assert captured["end_date"].isoformat() == "2026-07-31"
    assert captured["dept_id"] == 41


def test_build_missing_checkin_recipients_uses_same_day_records(staff_views, monkeypatch):
    target_date = datetime(2026, 6, 26).date()
    target_date_id = "20260626"
    active_a = SimpleNamespace(
        id=1,
        email="alice",
        fullname="Alice",
        line_id="line-a",
        personal_info=SimpleNamespace(academic_staff=False),
    )
    active_b = SimpleNamespace(
        id=2,
        email="bob",
        fullname="Bob",
        line_id="line-b",
        personal_info=SimpleNamespace(academic_staff=None),
    )
    academic = SimpleNamespace(
        id=3,
        email="cara",
        fullname="Cara",
        line_id="line-c",
        personal_info=SimpleNamespace(academic_staff=True),
    )
    no_line = SimpleNamespace(
        id=4,
        email="dana",
        fullname="Dana",
        line_id=None,
        personal_info=SimpleNamespace(academic_staff=False),
    )

    monkeypatch.setattr(
        staff_views,
        "StaffAccount",
        SimpleNamespace(get_active_accounts=lambda: [active_a, active_b, academic, no_line]),
    )

    records = [
        SimpleNamespace(
            staff_id=1,
            date_id=target_date_id,
            start_datetime=pytz.timezone("Asia/Bangkok").localize(datetime(2026, 6, 26, 8, 45)),
        ),
    ]

    recipients = staff_views._build_missing_checkin_recipients(target_date, records=records)

    assert recipients == [active_b]


def test_build_missing_checkin_recipients_queries_by_date_id(staff_views, monkeypatch):
    target_date = datetime(2026, 6, 26).date()
    target_date_id = "20260626"
    active_a = SimpleNamespace(
        id=1,
        email="alice",
        fullname="Alice",
        line_id="line-a",
        personal_info=SimpleNamespace(academic_staff=False),
    )
    active_b = SimpleNamespace(
        id=2,
        email="bob",
        fullname="Bob",
        line_id="line-b",
        personal_info=SimpleNamespace(academic_staff=False),
    )
    fake_query = _FakeQuery()
    fake_query.rows = [
        SimpleNamespace(staff_id=1, date_id=target_date_id),
    ]

    monkeypatch.setattr(
        staff_views,
        "StaffAccount",
        SimpleNamespace(get_active_accounts=lambda: [active_a, active_b]),
    )
    monkeypatch.setattr(staff_views, "StaffWorkLogin", SimpleNamespace(query=fake_query))

    recipients = staff_views._build_missing_checkin_recipients(target_date)

    assert recipients == [active_b]
    assert fake_query.filters == [{"date_id": target_date_id}]


def test_build_missing_checkin_recipients_filters_by_staff_email(staff_views, monkeypatch):
    target_date = datetime(2026, 6, 26).date()
    active_a = SimpleNamespace(
        id=1,
        email="alice",
        fullname="Alice",
        line_id="line-a",
        personal_info=SimpleNamespace(academic_staff=False),
    )
    active_b = SimpleNamespace(
        id=2,
        email="bob",
        fullname="Bob",
        line_id="line-b",
        personal_info=SimpleNamespace(academic_staff=False),
    )

    monkeypatch.setattr(
        staff_views,
        "StaffAccount",
        SimpleNamespace(get_active_accounts=lambda: [active_a, active_b]),
    )

    records = [SimpleNamespace(staff_id=2, start_datetime=pytz.timezone("Asia/Bangkok").localize(datetime(2026, 6, 26, 8, 45)))]

    recipients = staff_views._build_missing_checkin_recipients(target_date, records=records, staff_email="alice")

    assert recipients == [active_a]


def test_line_remind_missing_checkin_sends_only_to_missing_staff(staff_views, monkeypatch):
    target_date = datetime(2026, 6, 26).date()
    recipient = SimpleNamespace(id=11, email="alice", fullname="Test User", line_id="line-11")
    captured = []

    monkeypatch.setattr(staff_views, "_parse_checkin_reminder_date", lambda *_args, **_kwargs: target_date)
    monkeypatch.setattr(
        staff_views,
        "_build_missing_checkin_recipients",
        lambda *_args, **kwargs: captured.append(kwargs.get("staff_email")) or [recipient],
    )
    monkeypatch.setattr(staff_views, "_get_holiday_for_date", lambda *_args, **_kwargs: None)

    pushes = []
    monkeypatch.setattr(staff_views, "line_bot_api", SimpleNamespace(push_message=lambda **kwargs: pushes.append(kwargs)))
    monkeypatch.setattr(staff_views, "TextSendMessage", lambda text: SimpleNamespace(text=text))
    monkeypatch.setattr(staff_views, "jsonify", lambda payload: SimpleNamespace(get_json=lambda: payload))
    monkeypatch.setattr(
        staff_views,
        "request",
        SimpleNamespace(
            method="POST",
            values=SimpleNamespace(
                get=lambda key, default=None: {"date": "26/06/2026", "email": "alice"}.get(key, default)
            ),
        ),
    )

    response = staff_views.line_remind_missing_checkin.__wrapped__()
    payload = response.get_json()

    assert payload["message"] == "success"
    assert payload["recipient_count"] == 1
    assert payload["sent_count"] == 1
    assert payload["failed_count"] == 0
    assert pushes[0]["to"] == "line-11"
    assert pushes[0]["messages"].alt_text == "Check In Reminder"
    assert pushes[0]["messages"].contents.body.contents[0].text == "Check In Reminder"
    assert pushes[0]["messages"].contents.body.contents[1].contents[0].contents[0].text.startswith(
        "ท่านยังไม่ได้ลงชื่อเข้างานในวันนี้"
    )
    assert pushes[0]["messages"].contents.body.contents[1].contents[1].contents[0].text == "26/06/2026"
    assert captured == ["alice"]
    assert payload["staff_email"] == "alice"


def test_line_remind_missing_checkin_skips_holidays(staff_views, monkeypatch):
    target_date = datetime(2026, 6, 26).date()
    holiday = SimpleNamespace(holiday_name="Holiday")

    monkeypatch.setattr(staff_views, "_get_holiday_for_date", lambda *_args, **_kwargs: holiday)
    monkeypatch.setattr(staff_views, "_parse_checkin_reminder_date", lambda *_args, **_kwargs: target_date)
    monkeypatch.setattr(staff_views, "_build_missing_checkin_recipients", lambda *_args, **_kwargs: [SimpleNamespace(id=11, fullname="Test User", line_id="line-11")])

    pushes = []
    monkeypatch.setattr(staff_views, "line_bot_api", SimpleNamespace(push_message=lambda **kwargs: pushes.append(kwargs)))
    monkeypatch.setattr(staff_views, "jsonify", lambda payload: SimpleNamespace(get_json=lambda: payload))
    monkeypatch.setattr(
        staff_views,
        "request",
        SimpleNamespace(
            method="POST",
            values=SimpleNamespace(get=lambda key, default=None: {"date": "26/06/2026"}.get(key, default)),
        ),
    )

    response = staff_views.line_remind_missing_checkin.__wrapped__()
    payload = response.get_json()

    assert payload["message"] == "success"
    assert payload["recipient_count"] == 0
    assert payload["sent_count"] == 0
    assert payload["failed_count"] == 0
    assert payload["holiday_name"] == "Holiday"
    assert pushes == []


def test_login_scan_routes_delegate_to_shared_handler(staff_views, monkeypatch):
    calls = []

    def fake_handler(template_name, *, note):
        calls.append((template_name, note))
        return f"rendered:{template_name}:{note}"

    monkeypatch.setattr(staff_views, "_handle_login_scan_request", fake_handler)
    monkeypatch.setattr(staff_views, "request", SimpleNamespace(method="GET"))

    assert staff_views.login_scan.__wrapped__() == "rendered:staff/login_scan.html:qrcode"
    assert staff_views.login_scan_gj.__wrapped__() == "rendered:staff/login_scan_gj.html:gj"
    assert calls == [
        ("staff/login_scan.html", "qrcode"),
        ("staff/login_scan_gj.html", "gj"),
    ]


@pytest.mark.parametrize(
    ("activity", "message_prefix"),
    [
        ("checked in", "ท่านได้ทำสแกนเข้างานล่าสุดเมื่อ"),
        ("checked out", "ท่านได้ทำสแกนออกงานล่าสุดเมื่อ"),
    ],
)
def test_handle_login_scan_request_posts_shared_flow(staff_views, monkeypatch, activity, message_prefix):
    person = SimpleNamespace(
        fullname="Test User",
        staff_account=SimpleNamespace(line_id="line-1"),
    )
    query = SimpleNamespace(
        filters=[],
        filter_by=lambda **kwargs: query.filters.append(kwargs) or query,
        first=lambda: person,
    )
    monkeypatch.setattr(staff_views, "StaffPersonalInfo", SimpleNamespace(query=query))

    captured = {}

    def fake_create_work_login_record(staff_account, now, lat, long, *, qrcode_exp_datetime, note):
        captured["staff_account"] = staff_account
        captured["now"] = now
        captured["lat"] = lat
        captured["long"] = long
        captured["qrcode_exp_datetime"] = qrcode_exp_datetime
        captured["note"] = note
        return SimpleNamespace(id=1), activity, 3

    pushed = []
    monkeypatch.setattr(staff_views, "_create_work_login_record", fake_create_work_login_record)
    monkeypatch.setattr(staff_views, "line_bot_api", SimpleNamespace(push_message=lambda **kwargs: pushed.append(kwargs)))
    monkeypatch.setattr(staff_views, "TextSendMessage", lambda text: SimpleNamespace(text=text))
    monkeypatch.setattr(staff_views, "jsonify", lambda payload, status=None: SimpleNamespace(get_json=lambda: payload, payload=payload, status=status))
    monkeypatch.setattr(
        staff_views,
        "request",
        SimpleNamespace(
            method="POST",
            get_json=lambda: {
                "data": {
                    "lat": "13.1",
                    "long": "100.1",
                    "enName": "Test User",
                    "qrCodeExpDateTime": "26/06/2026 08:00:00",
                }
            },
        ),
    )

    response = staff_views._handle_login_scan_request("staff/login_scan.html", note="qrcode")
    payload = response.get_json()

    assert query.filters == [{"en_firstname": "Test", "en_lastname": "User"}]
    assert captured["staff_account"] is person.staff_account
    assert captured["lat"] == "13.1"
    assert captured["long"] == "100.1"
    assert captured["note"] == "qrcode"
    assert captured["qrcode_exp_datetime"].tzinfo is not None
    assert payload["message"] == "success"
    assert payload["activity"] == activity
    assert payload["name"] == "Test User"
    assert payload["numScans"] == 3
    assert payload["time"]
    assert pushed and pushed[0]["to"] == "line-1"
    expected_local_time = captured["now"].astimezone(pytz.timezone("Asia/Bangkok")).strftime(
        "%d/%m/%Y %H:%M:%S"
    )
    assert pushed[0]["messages"].text == f"{message_prefix} {expected_local_time}"


@pytest.mark.parametrize("clock", ["checkin", "checkout"])
@pytest.mark.parametrize("debug", [False, True])
def test_clock_request_emails_all_active_approvers(staff_views, monkeypatch, clock, debug):
    from flask import Flask

    app = Flask(__name__)
    app.debug = debug
    query = _FakeQuery()
    query.rows = [
        SimpleNamespace(
            approver_account_id=account_id,
            account=SimpleNamespace(id=account_id, email=email, line_id=None),
            is_active=True,
            notified_by_line=False,
        )
        for account_id, email in [(29, "first"), (30, "second"), (29, "first")]
    ]
    monkeypatch.setattr(staff_views, "StaffWorkFromHomeApprover", SimpleNamespace(
        query=query, id=SimpleNamespace(asc=lambda: None),
    ), raising=False)

    class FakeRequest:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self.id = 5051

        @staticmethod
        def generate_date_id(value):
            return value.strftime("%Y%m%d")

    monkeypatch.setattr(staff_views, "StaffRequestWorkLogin", FakeRequest)
    session = _FakeSession()
    monkeypatch.setattr(staff_views, "db", SimpleNamespace(session=session))
    monkeypatch.setattr(staff_views, "current_user", SimpleNamespace(
        id=42, personal_info=SimpleNamespace(fullname="Requester"),
    ))
    links = []
    def fake_url_for(endpoint, **kwargs):
        links.append((endpoint, kwargs))
        return "/clockin-clockout/approved/5051"
    monkeypatch.setattr(staff_views, "url_for", fake_url_for)
    monkeypatch.setattr(staff_views, "flash", lambda *args: None)
    sent = []
    monkeypatch.setattr(staff_views, "send_mail", lambda recipients, title, body: sent.append((recipients, body)))

    with app.test_request_context("/", method="POST", data={
        "clock": clock, "reason": "Missed scan", "workdatetime": "01/01/2020 08:30",
    }):
        staff_views.request_for_clockin_clockout.__wrapped__()

    assert query.filters == [{"staff_account_id": 42, "is_active": True}]
    assert [recipients for recipients, body in sent] == (
        [] if debug else [["first@mahidol.ac.th"], ["second@mahidol.ac.th"]]
    )
    assert all("/clockin-clockout/approved/5051" in body for recipients, body in sent)
    assert links[0][0] == "staff.approved_for_clockin_clockout"
    assert links[0][1]["request_id"] == 5051
    assert session.added[0].approver_id == 29
    assert session.commits == 1


@pytest.mark.parametrize("approver_id", [29, 30])
def test_each_active_approver_can_open_emailed_request(staff_views, monkeypatch, approver_id):
    clock_request = SimpleNamespace(id=5051, staff_account_id=42, approver_id=29)
    monkeypatch.setattr(staff_views, "StaffRequestWorkLogin", SimpleNamespace(
        query=SimpleNamespace(get_or_404=lambda request_id: clock_request),
    ))
    query = _FakeQuery()
    query.rows = [SimpleNamespace(approver_account_id=approver_id)]
    monkeypatch.setattr(staff_views, "StaffWorkFromHomeApprover", SimpleNamespace(query=query), raising=False)
    monkeypatch.setattr(staff_views, "current_user", SimpleNamespace(id=approver_id))
    monkeypatch.setattr(staff_views, "request", SimpleNamespace(method="GET", args={}))
    monkeypatch.setattr(staff_views, "render_template", lambda template, **context: context)

    context = staff_views.approved_for_clockin_clockout.__wrapped__(5051)

    assert context["can_approve"] is True
    if approver_id != 29:
        assert query.filters == [{
            "staff_account_id": 42, "approver_account_id": approver_id, "is_active": True,
        }]


@pytest.mark.parametrize("decision", ["yes", "no"])
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_clock_decision_redirects_to_scoped_request_list(staff_views, monkeypatch, decision, method):
    clock_request = SimpleNamespace(
        id=5051, staff_account_id=42, approver_id=29,
        approved_at=None, cancelled_at=None, date_id=20261030,
        work_datetime=datetime(2026, 10, 30, 1), is_checkin=True,
        staff=SimpleNamespace(line_id=None, email="requester"),
    )
    query = _FakeQuery()
    query.get_or_404 = lambda request_id: clock_request
    query.populate_existing = lambda: query
    query.with_for_update = lambda: query
    query.one = lambda: clock_request
    def forbid_unfiltered_list():
        pytest.fail("Approval must not load every user's requests")
    query.all = forbid_unfiltered_list
    monkeypatch.setattr(staff_views, "StaffRequestWorkLogin", SimpleNamespace(query=query))

    class Login:
        query = _FakeQuery()

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    monkeypatch.setattr(staff_views, "StaffWorkLogin", Login)
    monkeypatch.setattr(staff_views, "current_user", SimpleNamespace(id=29, fullname="Approver"))
    monkeypatch.setattr(staff_views, "current_app", SimpleNamespace(debug=False))
    monkeypatch.setattr(staff_views, "request", SimpleNamespace(
        method=method, args={"approved": decision}, form={"approved": decision}, headers={},
    ))
    monkeypatch.setattr(staff_views, "db", SimpleNamespace(session=_FakeSession()))
    monkeypatch.setattr(staff_views, "flash", lambda *args: None)
    monkeypatch.setattr(staff_views, "send_mail", lambda *args: None)
    monkeypatch.setattr(staff_views, "_refresh_daily_attendance_after_record", lambda record: None)
    monkeypatch.setattr(staff_views, "url_for", lambda endpoint, **kwargs: endpoint)
    monkeypatch.setattr(staff_views, "redirect", lambda target: ("redirect", target))

    assert staff_views.approved_for_clockin_clockout.__wrapped__(5051) == (
        "redirect", "staff.list_for_clockin_clockout",
    )
    assert bool(clock_request.approved_at) == (decision == "yes")
    assert bool(clock_request.cancelled_at) == (decision == "no")


@pytest.mark.parametrize("closed_field", ["approved_at", "cancelled_at", "existing_login"])
@pytest.mark.parametrize("decision", ["yes", "no"])
def test_closed_clock_request_cannot_be_processed_again(staff_views, monkeypatch, closed_field, decision):
    clock_request = SimpleNamespace(
        id=5051, staff_account_id=42, approver_id=29,
        approved_at=None, cancelled_at=None,
    )
    query = _FakeQuery()
    query.get_or_404 = lambda request_id: clock_request
    query_steps = []
    def populate_existing():
        query_steps.append('refresh')
        return query
    def with_for_update():
        query_steps.append('lock')
        return query
    def locked_request():
        # Another transaction completed after the initial request was loaded.
        assert query_steps == ['refresh', 'lock']
        if closed_field != 'existing_login':
            setattr(clock_request, closed_field, datetime(2026, 10, 28))
        return clock_request
    query.populate_existing = populate_existing
    query.with_for_update = with_for_update
    query.one = locked_request
    login_query = _FakeQuery()
    if closed_field == 'existing_login':
        login_query.rows = [SimpleNamespace(id=370010, request_id=5051)]
    monkeypatch.setattr(staff_views, "StaffWorkLogin", SimpleNamespace(query=login_query))
    monkeypatch.setattr(staff_views, "StaffRequestWorkLogin", SimpleNamespace(query=query))
    monkeypatch.setattr(staff_views, "current_user", SimpleNamespace(id=29))
    monkeypatch.setattr(staff_views, "request", SimpleNamespace(method="POST", form={"approved": decision}))
    monkeypatch.setattr(staff_views, "flash", lambda *args: None)
    monkeypatch.setattr(staff_views, "url_for", lambda *args, **kwargs: "/request/5051")
    monkeypatch.setattr(staff_views, "redirect", lambda target: target)
    session = _FakeSession()
    monkeypatch.setattr(staff_views, "db", SimpleNamespace(session=session))

    assert staff_views.approved_for_clockin_clockout.__wrapped__(5051) == "/request/5051"
    assert session.added == []
    assert session.commits == 0
    if closed_field == 'existing_login':
        assert login_query.filters == [{"request_id": 5051}]


def test_location_frequencies_counts_scans_by_location_and_scopes_dates(staff_views):
    tz = pytz.timezone('Asia/Bangkok')
    def record(staff_id=7, note='salaya', scans=1, day=2, source='scan', end=None):
        return SimpleNamespace(
            staff_id=staff_id, note=note, num_scans=scans, record_source=source,
            start_datetime=tz.localize(datetime(2026, 7, day, 8)), end_datetime=end,
        )
    records = [
        record(), record(scans=2), record(note='gj', scans=2),
        record(note='qrcode'), record(note=None),
        record(staff_id=99), record(day=1), record(source='approved_request'),
        record(source='hr_manual'),
        record(note='opd', end=tz.localize(datetime(2026, 7, 2, 17))),
    ]
    result = staff_views._login_location_frequencies(records, {7}, date(2026, 7, 2), date(2026, 7, 2))
    by_name = {item['name']: item for item in result}
    assert by_name['ศาลายา'] == {'name': 'ศาลายา', 'checkins': 1, 'checkouts': 1, 'total': 2}
    assert by_name['ศูนย์การแพทย์กาญจนาภิเษก']['checkouts'] == 1
    assert by_name['ไม่ระบุสถานที่']['checkins'] == 2
    assert by_name['สถานเวชศาสตร์ชันสูตร (ศิริราช)']['total'] == 2
    assert sum(item['total'] for item in result) == 7
    assert staff_views._login_location_frequencies([], {7}, date(2026, 7, 2), date(2026, 7, 2)) == []


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('modes', [['system'], ['average'], ['system', 'average'], []])
def test_save_personal_checkin_reminder(staff_views, monkeypatch, existing, modes):
    from werkzeug.datastructures import MultiDict
    query = _FakeQuery()
    setting = SimpleNamespace(staff_id=42, reminder_time=None)
    query.rows = [setting] if existing else []
    model = Mock(side_effect=lambda **kw: SimpleNamespace(reminder_time=None, **kw))
    model.query = query
    monkeypatch.setattr(staff_views, 'StaffCheckinReminderSetting', model, raising=False)
    monkeypatch.setattr(staff_views, 'current_user', SimpleNamespace(id=42))
    monkeypatch.setattr(staff_views, 'request', SimpleNamespace(form=MultiDict([
        ('enabled', 'on' if modes else ''), ('weekdays', '4'),
        ('weekdays', '0'), ('weekdays', '0'), ('staff_id', '999'),
    ] + [('reminder_modes', mode) for mode in modes])))
    monkeypatch.setattr(staff_views, 'flash', Mock())
    monkeypatch.setattr(staff_views, 'url_for', lambda endpoint: '/report')
    monkeypatch.setattr(staff_views, 'redirect', lambda url: url)
    assert staff_views.save_checkin_reminder_settings.__wrapped__() == '/report'
    saved = setting if existing else staff_views.db.session.added[-1]
    assert saved.staff_id == 42
    assert saved.enabled is bool(modes)
    assert saved.system_reminder is ('system' in modes)
    assert saved.average_reminder is ('average' in modes)
    assert saved.reminder_time.hour == 8 and saved.reminder_time.minute == 29
    assert saved.weekdays == '0,4'
    assert query.filters == [{'staff_id': 42}]
    assert staff_views.db.session.commits == 1


@pytest.mark.parametrize('modes,days', [([], ['0']), (['invalid'], ['0']), (['system'], []), (['average'], ['7'])])
def test_reject_invalid_checkin_reminder(staff_views, monkeypatch, modes, days):
    from werkzeug.datastructures import MultiDict
    from werkzeug.exceptions import BadRequest
    form = MultiDict([('enabled', 'on')] + [('reminder_modes', mode) for mode in modes] + [('weekdays', day) for day in days])
    monkeypatch.setattr(staff_views, 'request', SimpleNamespace(form=form))
    with pytest.raises(BadRequest):
        staff_views.save_checkin_reminder_settings.__wrapped__()
    assert staff_views.db.session.commits == 0


@pytest.mark.parametrize('preferences,expected', [
    (None, True),
    (dict(enabled=False, system_reminder=True, average_reminder=False, weekdays='4'), False),
    (dict(enabled=True, system_reminder=True, average_reminder=False, weekdays='4'), True),
    (dict(enabled=True, system_reminder=False, average_reminder=True, weekdays='4'), True),
    (dict(enabled=True, system_reminder=True, average_reminder=True, weekdays='4'), True),
    (dict(enabled=True, system_reminder=False, average_reminder=False, weekdays='4'), False),
    (dict(enabled=True, system_reminder=True, average_reminder=False, weekdays='0'), False),
])
@pytest.mark.parametrize('academic', [False, True, None])
def test_standard_checkin_reminder_respects_preferences(staff_views, monkeypatch, preferences, expected, academic):
    account = SimpleNamespace(id=42, email='alice', line_id='line-42',
                              personal_info=SimpleNamespace(academic_staff=academic))
    monkeypatch.setattr(staff_views, 'StaffAccount', SimpleNamespace(get_active_accounts=lambda: [account]))
    query = _FakeQuery()
    query.rows = [SimpleNamespace(staff_id=42, calculated_for=None, sample_days=0, average_checkin_time=None, **preferences)] if preferences is not None else []
    monkeypatch.setattr(staff_views, 'StaffCheckinReminderSetting', SimpleNamespace(query=query))
    recipients = staff_views._build_missing_checkin_recipients(date(2026, 11, 13), records=[])
    if academic is True and preferences is None:
        expected = False
    assert recipients == ([account] if expected else [])
    # Today's attendance always suppresses the reminder, including the default.
    assert staff_views._build_missing_checkin_recipients(
        date(2026, 11, 13), records=[SimpleNamespace(staff_id=42, date_id='20261113')]
    ) == []


@pytest.fixture
def personalized_reminder_setup(staff_views, monkeypatch):
    from datetime import time
    account = SimpleNamespace(id=42, email='alice', line_id='line-42', personal_info=SimpleNamespace(academic_staff=False))
    setting = SimpleNamespace(staff_id=42, enabled=True, system_reminder=False, average_reminder=True,
        weekdays='0,1,2,3,4', sample_days=10, calculated_for=date(2026, 11, 13),
        average_checkin_time=time(8, 12), reminder_time=time(8, 15))
    query = _FakeQuery()
    query.rows = [setting]
    monkeypatch.setattr(staff_views, 'StaffAccount', SimpleNamespace(get_active_accounts=lambda: [account]))
    monkeypatch.setattr(staff_views, 'StaffCheckinReminderSetting', SimpleNamespace(query=query))
    monkeypatch.setattr(staff_views, '_get_holiday_for_date', lambda _date: None)
    monkeypatch.setattr(staff_views, 'external_url', lambda endpoint: 'https://example.test/staff/geo-checkin')
    deliver = Mock(return_value='sent')
    monkeypatch.setattr(staff_views, '_deliver_checkin_reminder', deliver)
    return setting, deliver


@pytest.mark.parametrize('clock,expected', [((7, 55), 0), ((8, 10), 0), ((8, 15), 1), ((8, 20), 1), ((9, 0), 1), ((9, 5), 0)])
def test_personalized_sender_window(staff_views, personalized_reminder_setup, clock, expected):
    setting, deliver = personalized_reminder_setup
    stamp = staff_views.tz.localize(datetime(2026, 11, 13, *clock, 20))
    summary = staff_views.send_personalized_checkin_reminders(now=stamp)
    assert summary['sent_count'] == expected
    assert deliver.call_count == expected
    if expected:
        assert deliver.call_args.args[2] == 'average'
        assert deliver.call_args.args[3] == setting.reminder_time
        assert 'วันนี้อาจยุ่งจนลืมลงเวลา' in deliver.call_args.args[4].text


def test_personalized_preview_and_standard_split(staff_views, personalized_reminder_setup):
    _, deliver = personalized_reminder_setup
    stamp = staff_views.tz.localize(datetime(2026, 11, 13, 8, 15))
    summary = staff_views.send_personalized_checkin_reminders(now=stamp, dry_run=True)
    assert summary['recipient_count'] == 1
    assert summary['sent_count'] == 0
    assert summary['recipients'] == [dict(staff_id=42, time='08:15:00')]
    deliver.assert_not_called()
    assert staff_views._build_missing_checkin_recipients(stamp.date(), records=[]) == []


@pytest.mark.parametrize('reason', ['holiday', 'weekend', 'checked_in', 'leave_or_wfh', 'special_wfh'])
def test_personalized_sender_suppresses_ineligible_staff(staff_views, monkeypatch, personalized_reminder_setup, reason):
    setting, deliver = personalized_reminder_setup
    stamp = staff_views.tz.localize(datetime(2026, 11, 13, 8, 15))
    if reason == 'holiday':
        monkeypatch.setattr(staff_views, '_get_holiday_for_date', lambda _date: object())
    elif reason == 'weekend':
        stamp = stamp.replace(day=14)
        setting.calculated_for = stamp.date()
    elif reason == 'checked_in':
        staff_views.StaffWorkLogin.query.rows = [SimpleNamespace(staff_id=42, date_id='20261113')]
    elif reason == 'leave_or_wfh':
        monkeypatch.setattr(staff_views, '_checkin_reminder_excused_staff_ids', lambda _date: {42})
    else:
        staff_views.StaffSpecialWorkFromHomeDay.query.rows = [SimpleNamespace(staff=[SimpleNamespace(id=42)])]
    assert staff_views.send_personalized_checkin_reminders(now=stamp)['sent_count'] == 0
    deliver.assert_not_called()


def test_personalized_rechecks_attendance_before_sending(staff_views, monkeypatch, personalized_reminder_setup):
    _, deliver = personalized_reminder_setup
    monkeypatch.setattr(staff_views.StaffWorkLogin.query, 'first', lambda: object())
    stamp = staff_views.tz.localize(datetime(2026, 11, 13, 8, 15))
    result = staff_views.send_personalized_checkin_reminders(now=stamp)
    assert result['skipped_count'] == 1
    deliver.assert_not_called()


def test_personalized_message_for_early_staff(staff_views):
    from datetime import time
    staff_views.external_url = lambda endpoint: 'https://example.test/checkin'
    message = staff_views._personalized_checkin_reminder_message(SimpleNamespace(average_checkin_time=time(7, 20)))
    assert 'ก่อนช่วงนี้' in message.text
    assert 'https://example.test/checkin' in message.text



def test_checkin_reminders_only_exclude_approved_leave_and_wfh(staff_views):
    staff_views.StaffLeaveRequest.query.rows = [
        SimpleNamespace(staff_account_id=42, get_approved=True),
        SimpleNamespace(staff_account_id=43, get_approved=False),
    ]
    staff_views.StaffWorkFromHomeRequest.query.rows = [
        SimpleNamespace(staff_account_id=44, get_approved=True),
        SimpleNamespace(staff_account_id=45, get_approved=False),
    ]
    assert staff_views._checkin_reminder_excused_staff_ids(date(2026, 11, 13)) == {42, 44}
