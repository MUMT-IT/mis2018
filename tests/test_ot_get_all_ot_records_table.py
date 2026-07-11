import importlib
import os
import sys
import types
from datetime import datetime, date, timedelta
from types import SimpleNamespace

import pytest
import pytz
from flask import Flask


class DummyExpr:
    def __ge__(self, other):
        return self

    def __le__(self, other):
        return self


class DummyField:
    def op(self, _operator):
        return lambda _other: DummyExpr()

    def has(self, **_kwargs):
        return DummyExpr()


class FakeLoginQuery:
    def __init__(self, logins):
        self._logins = list(logins)
        self._staff_id = None

    def filter(self, *_args, **_kwargs):
        return self

    def filter_by(self, **kwargs):
        self._staff_id = kwargs.get("staff_id")
        return self

    def order_by(self, *_args):
        items = self._logins
        if self._staff_id is not None:
            items = [login for login in items if login.staff_id == self._staff_id]
        return sorted(items, key=lambda login: login.start_datetime)


class FakeShiftQuery:
    def __init__(self, shifts):
        self._shifts = list(shifts)

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args):
        return sorted(self._shifts, key=lambda shift: shift.datetime.lower)


def _install_import_stubs(monkeypatch):
    os.environ.setdefault("DATABASE_URL", "postgres://user:pass@localhost/dbname")
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "https://example.com/key.json")

    requests_stub = types.ModuleType("requests")
    requests_stub.get = lambda *_args, **_kwargs: SimpleNamespace(json=lambda: {})
    monkeypatch.setitem(sys.modules, "requests", requests_stub)

    main = types.ModuleType("app.main")
    main.app = Flask("test")
    main.db = SimpleNamespace(session=None)
    main.func = SimpleNamespace(timezone=lambda *_args, **_kwargs: DummyExpr())
    main.StaffPersonalInfo = object()
    main.StaffSpecialGroup = object()
    main.StaffShiftSchedule = object()
    main.StaffWorkLogin = object()
    main.StaffLeaveRequest = object()
    monkeypatch.setitem(sys.modules, "app.main", main)

    models = types.ModuleType("app.models")
    models.Org = object()
    monkeypatch.setitem(sys.modules, "app.models", models)

    staff_models = types.ModuleType("app.staff.models")
    staff_models.StaffAccount = object()
    staff_models.Role = object()
    monkeypatch.setitem(sys.modules, "app.staff.models", staff_models)

    forms = types.ModuleType("app.ot.forms")
    forms.pytz = pytz
    forms.OtPaymentAnnounceForm = object
    forms.OtCompensationRateForm = object
    forms.OtTimeSlotForm = object
    forms.OtDocumentApprovalForm = object
    forms.DateTimeRange = lambda lower=None, upper=None, bounds=None: SimpleNamespace(
        lower=lower,
        upper=upper,
        bounds=bounds,
    )
    forms.time_slots = []
    forms.create_ot_record_form = lambda *_args, **_kwargs: object
    forms.OtScheduleItemForm = object
    forms.OtScheduleForm = object
    monkeypatch.setitem(sys.modules, "app.ot.forms", forms)

    roles = types.ModuleType("app.roles")

    class Perm:
        def union(self, _other):
            return self

        def require(self):
            def decorator(fn):
                return fn

            return decorator

    roles.secretary_permission = Perm()
    roles.manager_permission = Perm()
    monkeypatch.setitem(sys.modules, "app.roles", roles)

    auth = types.ModuleType("pydrive.auth")

    class FakeCred:
        @classmethod
        def from_json_keyfile_dict(cls, _keyfile_dict, _scopes):
            return object()

    class FakeGA:
        def __init__(self, *_args, **_kwargs):
            self.credentials = None

    auth.ServiceAccountCredentials = FakeCred
    auth.GoogleAuth = FakeGA
    monkeypatch.setitem(sys.modules, "pydrive.auth", auth)

    drive = types.ModuleType("pydrive.drive")

    class FakeGD:
        def __init__(self, *_args, **_kwargs):
            pass

    drive.GoogleDrive = FakeGD
    monkeypatch.setitem(sys.modules, "pydrive.drive", drive)

    sys.modules.pop("app.ot.views", None)


@pytest.fixture
def ot_views(monkeypatch):
    _install_import_stubs(monkeypatch)
    views = importlib.import_module("app.ot.views")
    monkeypatch.setattr(views, "_is_external_account", lambda: False)
    monkeypatch.setattr(views, "url_for", lambda *_args, **kwargs: f"/staff/{kwargs['staff_id']}")
    monkeypatch.setattr(views, "humanized_work_time", lambda minutes: f"{minutes:.0f}m")
    return views


def _bangkok_dt(year, month, day, hour, minute):
    tz = pytz.timezone("Asia/Bangkok")
    return tz.localize(datetime(year, month, day, hour, minute))


def _make_record(
    *,
    staff_id,
    fullname,
    sap_id,
    shift_start,
    shift_end,
    rate=100.0,
    per_period=False,
    time_slot="OT-A",
    position="Technician",
):
    class Record:
        pass

    staff = SimpleNamespace(fullname=fullname, personal_info=SimpleNamespace(sap_id=sap_id))
    compensation = SimpleNamespace(
        per_period=per_period,
        time_slot=time_slot,
        rate=rate,
        ot_job_role=SimpleNamespace(role=position),
        work_at_org=SimpleNamespace(display_name="Main Plant"),
    )
    shift = SimpleNamespace(datetime=SimpleNamespace(lower=shift_start, upper=shift_end))
    record = Record()
    record.id = 9001
    record.staff_account_id = staff_id
    record.staff = staff
    record.compensation = compensation
    record.shift = shift
    record.total_shift_minutes = int((shift_end - shift_start).total_seconds() // 60)
    record.calculate_total_pay = lambda work_minutes: round(work_minutes * rate / 60.0, 2)
    return record


def _make_login(staff_id, login_id, start_dt, end_dt=None):
    return SimpleNamespace(
        staff_id=staff_id,
        id=login_id,
        start_datetime=start_dt,
        end_datetime=end_dt,
    )


def _expected_pay(minutes, rate):
    return round(minutes * rate / 60.0, 2)


def _call_unwrapped_view(view):
    while hasattr(view, "__wrapped__"):
        view = view.__wrapped__
    return view


@pytest.mark.parametrize(
    "scenario,logins,expected",
    [
        (
            "early_checkin_late_checkout",
            [_make_login(101, 1, _bangkok_dt(2024, 1, 2, 8, 45), _bangkok_dt(2024, 1, 2, 17, 15))],
            {"late_minutes": 0, "early_minutes": 0, "work_minutes": 480, "checkins": "2024-01-02T08:45:00+07:00", "checkouts": "2024-01-02T17:15:00+07:00"},
        ),
        (
            "early_checkin_only",
            [_make_login(101, 2, _bangkok_dt(2024, 1, 2, 8, 45), None)],
            {
                "late_minutes": 0,
                "early_minutes": 0,
                "work_minutes": None,
                "checkins": "2024-01-02T08:45:00+07:00",
                "checkouts": None,
                "missing_checkout": True,
            },
        ),
        (
            "early_checkout",
            [_make_login(101, 3, _bangkok_dt(2024, 1, 2, 9, 0), _bangkok_dt(2024, 1, 2, 16, 45))],
            {"late_minutes": 0, "early_minutes": 15, "work_minutes": 465, "checkins": "2024-01-02T09:00:00+07:00", "checkouts": "2024-01-02T16:45:00+07:00"},
        ),
        (
            "late_checkin_late_checkout",
            [_make_login(101, 4, _bangkok_dt(2024, 1, 2, 9, 15), _bangkok_dt(2024, 1, 2, 17, 20))],
            {"late_minutes": 15, "early_minutes": 0, "work_minutes": 465, "checkins": "2024-01-02T09:15:00+07:00", "checkouts": "2024-01-02T17:20:00+07:00"},
        ),
        (
            "late_checkin_early_checkout",
            [_make_login(101, 5, _bangkok_dt(2024, 1, 2, 9, 15), _bangkok_dt(2024, 1, 2, 16, 45))],
            {"late_minutes": 15, "early_minutes": 15, "work_minutes": 450, "checkins": "2024-01-02T09:15:00+07:00", "checkouts": "2024-01-02T16:45:00+07:00"},
        ),
    ],
)
def test_get_all_ot_records_table_calculates_all_time_variants(ot_views, scenario, logins, expected):
    shift_start = date(2024, 1, 2)
    shift_record = _make_record(
        staff_id=101,
        fullname="Jane Doe",
        sap_id="SAP-101",
        shift_start=datetime(2024, 1, 2, 9, 0),
        shift_end=datetime(2024, 1, 2, 17, 0),
        rate=120.0,
    )
    shifts = [SimpleNamespace(datetime=SimpleNamespace(lower=shift_record.shift.datetime.lower, upper=shift_record.shift.datetime.upper), records=[shift_record])]

    ot_views.StaffWorkLogin = SimpleNamespace(
        query=FakeLoginQuery(logins),
        start_datetime=DummyField(),
    )
    ot_views.OtShift = SimpleNamespace(
        query=FakeShiftQuery(shifts),
        datetime=DummyField(),
        timeslot=DummyField(),
    )

    app = Flask("test")
    with app.test_request_context(
        "/app/api?start=2024-01-02T00:00:00%2B07:00&end=2024-01-02T23:59:59%2B07:00"
    ):
        response = _call_unwrapped_view(ot_views.get_all_ot_records_table)(announcement_id=7)

    payload = response.get_json()
    assert len(payload["data"]) == 1
    row = payload["data"][0]

    assert row["fullname"] == "Jane Doe"
    assert row["late_minutes"] == expected["late_minutes"]
    assert row["early_minutes"] == expected["early_minutes"]
    assert row["work_minutes"] == expected["work_minutes"]
    assert row["late_checkin_display"] == (f'{expected["late_minutes"]}m' if expected["late_minutes"] else None)
    assert row["early_checkout_display"] == (f'{expected["early_minutes"]}m' if expected["early_minutes"] else None)
    assert row["work_minutes_display"] == (f'{expected["work_minutes"]}m' if expected["work_minutes"] else None)
    assert row["checkins"] == expected["checkins"]
    assert row["checkouts"] == expected["checkouts"]
    assert row["payment"] == (_expected_pay(expected["work_minutes"], 120.0) if expected["work_minutes"] else None)
    assert row["missing_checkout"] == expected.get("missing_checkout", False)


def test_get_all_ot_records_table_includes_staff_without_any_checkins(ot_views):
    shift_record = _make_record(
        staff_id=202,
        fullname="No Checkin",
        sap_id="SAP-202",
        shift_start=datetime(2024, 1, 2, 9, 0),
        shift_end=datetime(2024, 1, 2, 17, 0),
    )
    shifts = [SimpleNamespace(datetime=SimpleNamespace(lower=shift_record.shift.datetime.lower, upper=shift_record.shift.datetime.upper), records=[shift_record])]

    ot_views.StaffWorkLogin = SimpleNamespace(
        query=FakeLoginQuery([]),
        start_datetime=DummyField(),
    )
    ot_views.OtShift = SimpleNamespace(
        query=FakeShiftQuery(shifts),
        datetime=DummyField(),
        timeslot=DummyField(),
    )

    app = Flask("test")
    with app.test_request_context(
        "/app/api?start=2024-01-02T00:00:00%2B07:00&end=2024-01-02T23:59:59%2B07:00"
    ):
        response = _call_unwrapped_view(ot_views.get_all_ot_records_table)(announcement_id=7)

    payload = response.get_json()
    assert len(payload["data"]) == 1
    row = payload["data"][0]
    assert row["fullname"] == "No Checkin"
    assert row["checkins"] is None
    assert row["checkouts"] is None
    assert row["late_minutes"] is None
    assert row["early_minutes"] is None
    assert row["work_minutes"] is None
    assert row["late_checkin_display"] is None
    assert row["early_checkout_display"] is None
    assert row["work_minutes_display"] is None


def test_get_all_ot_records_table_handles_midnight_split(ot_views):
    ot_views.timedelta = timedelta

    shift_record = _make_record(
        staff_id=303,
        fullname="Night Shift",
        sap_id="SAP-303",
        shift_start=datetime(2024, 1, 2, 23, 0),
        shift_end=datetime(2024, 1, 3, 2, 0),
        rate=120.0,
    )
    shifts = [
        SimpleNamespace(
            datetime=SimpleNamespace(lower=shift_record.shift.datetime.lower, upper=shift_record.shift.datetime.upper),
            records=[shift_record],
        )
    ]
    logins = [
        _make_login(303, 11, _bangkok_dt(2024, 1, 2, 23, 30), None),
        _make_login(303, 12, _bangkok_dt(2024, 1, 3, 2, 15), None),
    ]

    ot_views.StaffWorkLogin = SimpleNamespace(
        query=FakeLoginQuery(logins),
        start_datetime=DummyField(),
    )
    ot_views.OtShift = SimpleNamespace(
        query=FakeShiftQuery(shifts),
        datetime=DummyField(),
        timeslot=DummyField(),
    )

    app = Flask("test")
    with app.test_request_context(
        "/app/api?start=2024-01-02T00:00:00%2B07:00&end=2024-01-03T23:59:59%2B07:00"
    ):
        response = _call_unwrapped_view(ot_views.get_all_ot_records_table)(announcement_id=7)

    payload = response.get_json()
    assert len(payload["data"]) == 1
    row = payload["data"][0]

    assert row["checkins"] == "2024-01-02T23:30:00+07:00"
    assert row["checkouts"] == "2024-01-03T00:00:00+07:00"
    assert row["late_minutes"] == 30.0
    assert row["early_minutes"] == 120.0
    assert row["work_minutes"] == 30.0
    assert row["late_checkin_display"] == "30m"
    assert row["early_checkout_display"] == "120m"
    assert row["work_minutes_display"] == "30m"


def test_get_all_ot_records_table_reuses_one_complete_pair_across_three_shifts(ot_views):
    shift_one = _make_record(
        staff_id=414,
        fullname="Three Shift Staff",
        sap_id="SAP-414",
        shift_start=datetime(2024, 1, 1, 8, 0),
        shift_end=datetime(2024, 1, 1, 16, 0),
        rate=100.0,
    )
    shift_two = _make_record(
        staff_id=414,
        fullname="Three Shift Staff",
        sap_id="SAP-414",
        shift_start=datetime(2024, 1, 1, 16, 0),
        shift_end=datetime(2024, 1, 2, 0, 0),
        rate=100.0,
    )
    shift_three = _make_record(
        staff_id=414,
        fullname="Three Shift Staff",
        sap_id="SAP-414",
        shift_start=datetime(2024, 1, 2, 0, 0),
        shift_end=datetime(2024, 1, 2, 8, 0),
        rate=100.0,
    )
    shifts = [
        SimpleNamespace(
            datetime=SimpleNamespace(lower=shift_one.shift.datetime.lower, upper=shift_one.shift.datetime.upper),
            records=[shift_one],
        ),
        SimpleNamespace(
            datetime=SimpleNamespace(lower=shift_two.shift.datetime.lower, upper=shift_two.shift.datetime.upper),
            records=[shift_two],
        ),
        SimpleNamespace(
            datetime=SimpleNamespace(lower=shift_three.shift.datetime.lower, upper=shift_three.shift.datetime.upper),
            records=[shift_three],
        ),
    ]
    logins = [
        _make_login(414, 33, _bangkok_dt(2024, 1, 1, 8, 0), _bangkok_dt(2024, 1, 2, 8, 0)),
    ]

    ot_views.StaffWorkLogin = SimpleNamespace(
        query=FakeLoginQuery(logins),
        start_datetime=DummyField(),
    )
    ot_views.OtShift = SimpleNamespace(
        query=FakeShiftQuery(shifts),
        datetime=DummyField(),
        timeslot=DummyField(),
    )

    app = Flask("test")
    with app.test_request_context(
        "/app/api?start=2024-01-01T00:00:00%2B07:00&end=2024-01-02T23:59:59%2B07:00"
    ):
        response = _call_unwrapped_view(ot_views.get_all_ot_records_table)(announcement_id=7)

    payload = response.get_json()
    assert len(payload["data"]) == 3
    first_row, second_row, third_row = payload["data"]

    assert first_row["checkins"] == "2024-01-01T08:00:00+07:00"
    assert first_row["checkouts"] == "2024-01-02T08:00:00+07:00"
    assert first_row["work_minutes"] == 480

    assert second_row["checkins"] == "2024-01-01T08:00:00+07:00"
    assert second_row["checkouts"] == "2024-01-02T08:00:00+07:00"
    assert second_row["work_minutes"] == 480

    assert third_row["checkins"] == "2024-01-01T08:00:00+07:00"
    assert third_row["checkouts"] == "2024-01-02T08:00:00+07:00"
    assert third_row["work_minutes"] == 480


def test_get_all_ot_records_table_pays_full_for_per_period_staff(ot_views):
    shift_record = _make_record(
        staff_id=404,
        fullname="Per Period Staff",
        sap_id="SAP-404",
        shift_start=datetime(2024, 1, 2, 9, 0),
        shift_end=datetime(2024, 1, 2, 17, 0),
        rate=150.0,
        per_period=True,
    )
    shifts = [
        SimpleNamespace(
            datetime=SimpleNamespace(lower=shift_record.shift.datetime.lower, upper=shift_record.shift.datetime.upper),
            records=[shift_record],
        )
    ]
    logins = [
        _make_login(404, 21, _bangkok_dt(2024, 1, 2, 9, 20), None),
        _make_login(404, 22, _bangkok_dt(2024, 1, 2, 16, 40), None),
    ]

    ot_views.StaffWorkLogin = SimpleNamespace(
        query=FakeLoginQuery(logins),
        start_datetime=DummyField(),
    )
    ot_views.OtShift = SimpleNamespace(
        query=FakeShiftQuery(shifts),
        datetime=DummyField(),
        timeslot=DummyField(),
    )

    app = Flask("test")
    with app.test_request_context(
        "/app/api?start=2024-01-02T00:00:00%2B07:00&end=2024-01-02T23:59:59%2B07:00"
    ):
        response = _call_unwrapped_view(ot_views.get_all_ot_records_table)(announcement_id=7)

    payload = response.get_json()
    assert len(payload["data"]) == 1
    row = payload["data"][0]

    assert row["checkins"] == "2024-01-02T09:20:00+07:00"
    assert row["checkouts"] == "2024-01-02T16:40:00+07:00"
    assert row["late_minutes"] == 0
    assert row["early_minutes"] == 0
    assert row["work_minutes"] == 480
    assert row["late_checkin_display"] is None
    assert row["early_checkout_display"] is None
    assert row["work_minutes_display"] == "480m"
    assert row["payment"] == _expected_pay(480, 150.0)


def test_get_all_ot_records_table_does_not_pay_open_per_period_shift(ot_views):
    shift_record = _make_record(
        staff_id=411,
        fullname="Open Period Staff",
        sap_id="SAP-411",
        shift_start=datetime(2024, 1, 2, 9, 0),
        shift_end=datetime(2024, 1, 2, 17, 0),
        rate=150.0,
        per_period=True,
    )
    shifts = [
        SimpleNamespace(
            datetime=SimpleNamespace(lower=shift_record.shift.datetime.lower, upper=shift_record.shift.datetime.upper),
            records=[shift_record],
        )
    ]
    logins = [
        _make_login(411, 23, _bangkok_dt(2024, 1, 2, 9, 20), None),
    ]

    ot_views.StaffWorkLogin = SimpleNamespace(
        query=FakeLoginQuery(logins),
        start_datetime=DummyField(),
    )
    ot_views.OtShift = SimpleNamespace(
        query=FakeShiftQuery(shifts),
        datetime=DummyField(),
        timeslot=DummyField(),
    )

    app = Flask("test")
    with app.test_request_context(
        "/app/api?start=2024-01-02T00:00:00%2B07:00&end=2024-01-02T23:59:59%2B07:00"
    ):
        response = _call_unwrapped_view(ot_views.get_all_ot_records_table)(announcement_id=7)

    payload = response.get_json()
    assert len(payload["data"]) == 1
    row = payload["data"][0]
    assert row["checkins"] == "2024-01-02T09:20:00+07:00"
    assert row["checkouts"] is None
    assert row["late_minutes"] == 0
    assert row["early_minutes"] == 0
    assert row["work_minutes"] is None
    assert row["payment"] is None


def test_get_all_ot_records_table_keeps_row_when_late_checkin_exceeds_limit(ot_views):
    shift_record = _make_record(
        staff_id=505,
        fullname="Too Late",
        sap_id="SAP-505",
        shift_start=datetime(2024, 1, 2, 9, 0),
        shift_end=datetime(2024, 1, 2, 17, 0),
        rate=100.0,
    )
    shifts = [
        SimpleNamespace(
            datetime=SimpleNamespace(lower=shift_record.shift.datetime.lower, upper=shift_record.shift.datetime.upper),
            records=[shift_record],
        )
    ]
    logins = [
        _make_login(505, 31, _bangkok_dt(2024, 1, 2, 9, 46), _bangkok_dt(2024, 1, 2, 17, 0)),
    ]

    ot_views.StaffWorkLogin = SimpleNamespace(
        query=FakeLoginQuery(logins),
        start_datetime=DummyField(),
    )
    ot_views.OtShift = SimpleNamespace(
        query=FakeShiftQuery(shifts),
        datetime=DummyField(),
        timeslot=DummyField(),
    )

    app = Flask("test")
    with app.test_request_context(
        "/app/api?start=2024-01-02T00:00:00%2B07:00&end=2024-01-02T23:59:59%2B07:00"
    ):
        response = _call_unwrapped_view(ot_views.get_all_ot_records_table)(announcement_id=7)

    payload = response.get_json()
    assert len(payload["data"]) == 1
    row = payload["data"][0]
    assert row["fullname"] == "Too Late"
    assert row["checkins"] is None
    assert row["checkouts"] is None
    assert row["late_minutes"] is None
    assert row["early_minutes"] is None
    assert row["payment"] is None


def test_get_all_ot_records_table_ignores_midnight_checkout_as_fake_checkin(ot_views):
    overnight_shift = _make_record(
        staff_id=606,
        fullname="Overnight Staff",
        sap_id="SAP-606",
        shift_start=datetime(2024, 1, 2, 23, 0),
        shift_end=datetime(2024, 1, 3, 2, 0),
        rate=100.0,
    )
    followup_shift = _make_record(
        staff_id=606,
        fullname="Overnight Staff",
        sap_id="SAP-606",
        shift_start=datetime(2024, 1, 3, 2, 15),
        shift_end=datetime(2024, 1, 3, 4, 0),
        rate=100.0,
    )
    shifts = [
        SimpleNamespace(
            datetime=SimpleNamespace(lower=overnight_shift.shift.datetime.lower, upper=overnight_shift.shift.datetime.upper),
            records=[overnight_shift],
        ),
        SimpleNamespace(
            datetime=SimpleNamespace(lower=followup_shift.shift.datetime.lower, upper=followup_shift.shift.datetime.upper),
            records=[followup_shift],
        ),
    ]
    logins = [
        _make_login(606, 41, _bangkok_dt(2024, 1, 2, 23, 30), None),
        _make_login(606, 42, _bangkok_dt(2024, 1, 3, 2, 15), None),
    ]

    ot_views.StaffWorkLogin = SimpleNamespace(
        query=FakeLoginQuery(logins),
        start_datetime=DummyField(),
    )
    ot_views.OtShift = SimpleNamespace(
        query=FakeShiftQuery(shifts),
        datetime=DummyField(),
        timeslot=DummyField(),
    )

    app = Flask("test")
    with app.test_request_context(
        "/app/api?start=2024-01-02T00:00:00%2B07:00&end=2024-01-03T23:59:59%2B07:00"
    ):
        response = _call_unwrapped_view(ot_views.get_all_ot_records_table)(announcement_id=7)

    payload = response.get_json()
    assert len(payload["data"]) == 2
    overnight_row = payload["data"][0]
    followup_row = payload["data"][1]
    assert overnight_row["id"] == 9001
    assert overnight_row["start"] == "2024-01-02T23:00:00+07:00"
    assert overnight_row["checkins"] == "2024-01-02T23:30:00+07:00"
    assert overnight_row["checkouts"] == "2024-01-03T00:00:00+07:00"
    assert followup_row["id"] == 9001
    assert followup_row["start"] == "2024-01-03T02:15:00+07:00"
    assert followup_row["checkins"] is None
    assert followup_row["checkouts"] is None


def test_get_all_ot_records_table_keeps_one_row_for_multiple_login_pairs(ot_views):
    shift_record = _make_record(
        staff_id=707,
        fullname="Split Shift Staff",
        sap_id="SAP-707",
        shift_start=datetime(2024, 1, 2, 9, 0),
        shift_end=datetime(2024, 1, 2, 17, 0),
        rate=100.0,
    )
    shifts = [
        SimpleNamespace(
            datetime=SimpleNamespace(lower=shift_record.shift.datetime.lower, upper=shift_record.shift.datetime.upper),
            records=[shift_record],
        )
    ]
    logins = [
        _make_login(707, 51, _bangkok_dt(2024, 1, 2, 9, 5), _bangkok_dt(2024, 1, 2, 12, 0)),
        _make_login(707, 52, _bangkok_dt(2024, 1, 2, 13, 0), _bangkok_dt(2024, 1, 2, 17, 10)),
    ]

    ot_views.StaffWorkLogin = SimpleNamespace(
        query=FakeLoginQuery(logins),
        start_datetime=DummyField(),
    )
    ot_views.OtShift = SimpleNamespace(
        query=FakeShiftQuery(shifts),
        datetime=DummyField(),
        timeslot=DummyField(),
    )

    app = Flask("test")
    with app.test_request_context(
        "/app/api?start=2024-01-02T00:00:00%2B07:00&end=2024-01-02T23:59:59%2B07:00"
    ):
        response = _call_unwrapped_view(ot_views.get_all_ot_records_table)(announcement_id=7)

    payload = response.get_json()
    assert len(payload["data"]) == 1
    row = payload["data"][0]
    assert row["checkins"] == "2024-01-02T09:05:00+07:00"
    assert row["checkouts"] == "2024-01-02T12:00:00+07:00"
    assert row["late_minutes"] == 5.0
    assert row["early_minutes"] == 300.0


def test_get_all_ot_records_table_accepts_exact_shift_boundaries(ot_views):
    shift_record = _make_record(
        staff_id=808,
        fullname="Boundary Staff",
        sap_id="SAP-808",
        shift_start=datetime(2024, 1, 2, 9, 0),
        shift_end=datetime(2024, 1, 2, 17, 0),
        rate=100.0,
    )
    shifts = [
        SimpleNamespace(
            datetime=SimpleNamespace(lower=shift_record.shift.datetime.lower, upper=shift_record.shift.datetime.upper),
            records=[shift_record],
        )
    ]
    logins = [
        _make_login(808, 61, _bangkok_dt(2024, 1, 2, 9, 0), _bangkok_dt(2024, 1, 2, 17, 0)),
    ]

    ot_views.StaffWorkLogin = SimpleNamespace(
        query=FakeLoginQuery(logins),
        start_datetime=DummyField(),
    )
    ot_views.OtShift = SimpleNamespace(
        query=FakeShiftQuery(shifts),
        datetime=DummyField(),
        timeslot=DummyField(),
    )

    app = Flask("test")
    with app.test_request_context(
        "/app/api?start=2024-01-02T00:00:00%2B07:00&end=2024-01-02T23:59:59%2B07:00"
    ):
        response = _call_unwrapped_view(ot_views.get_all_ot_records_table)(announcement_id=7)

    payload = response.get_json()
    assert len(payload["data"]) == 1
    row = payload["data"][0]
    assert row["checkins"] == "2024-01-02T09:00:00+07:00"
    assert row["checkouts"] == "2024-01-02T17:00:00+07:00"
    assert row["late_minutes"] == 0
    assert row["early_minutes"] == 0
    assert row["work_minutes"] == 480
    assert row["payment"] == _expected_pay(480, 100.0)


def test_get_all_ot_records_table_keeps_zero_duration_staff_visible(ot_views):
    shift_record = _make_record(
        staff_id=809,
        fullname="Zero Duration Staff",
        sap_id="SAP-809",
        shift_start=datetime(2024, 1, 2, 9, 0),
        shift_end=datetime(2024, 1, 2, 17, 0),
        rate=100.0,
    )
    shifts = [
        SimpleNamespace(
            datetime=SimpleNamespace(lower=shift_record.shift.datetime.lower, upper=shift_record.shift.datetime.upper),
            records=[shift_record],
        )
    ]
    logins = [
        _make_login(809, 71, _bangkok_dt(2024, 1, 2, 10, 0), _bangkok_dt(2024, 1, 2, 10, 0)),
    ]

    ot_views.StaffWorkLogin = SimpleNamespace(
        query=FakeLoginQuery(logins),
        start_datetime=DummyField(),
    )
    ot_views.OtShift = SimpleNamespace(
        query=FakeShiftQuery(shifts),
        datetime=DummyField(),
        timeslot=DummyField(),
    )

    app = Flask("test")
    with app.test_request_context(
        "/app/api?start=2024-01-02T00:00:00%2B07:00&end=2024-01-02T23:59:59%2B07:00"
    ):
        response = _call_unwrapped_view(ot_views.get_all_ot_records_table)(announcement_id=7)

    payload = response.get_json()
    assert len(payload["data"]) == 1
    row = payload["data"][0]
    assert row["fullname"] == "Zero Duration Staff"
    assert row["checkins"] is None
    assert row["checkouts"] is None
    assert row["late_minutes"] is None
    assert row["early_minutes"] is None
    assert row["payment"] is None


def test_get_all_ot_records_table_keeps_staff_visible_without_checkins(ot_views):
    shift_record = _make_record(
        staff_id=810,
        fullname="No Checkin Staff",
        sap_id="SAP-810",
        shift_start=datetime(2024, 1, 2, 9, 0),
        shift_end=datetime(2024, 1, 2, 17, 0),
        rate=100.0,
    )
    shifts = [
        SimpleNamespace(
            datetime=SimpleNamespace(lower=shift_record.shift.datetime.lower, upper=shift_record.shift.datetime.upper),
            records=[shift_record],
        )
    ]

    ot_views.StaffWorkLogin = SimpleNamespace(
        query=FakeLoginQuery([]),
        start_datetime=DummyField(),
    )
    ot_views.OtShift = SimpleNamespace(
        query=FakeShiftQuery(shifts),
        datetime=DummyField(),
        timeslot=DummyField(),
    )

    app = Flask("test")
    with app.test_request_context(
        "/app/api?start=2024-01-02T00:00:00%2B07:00&end=2024-01-02T23:59:59%2B07:00"
    ):
        response = _call_unwrapped_view(ot_views.get_all_ot_records_table)(announcement_id=7)

    payload = response.get_json()
    assert len(payload["data"]) == 1
    row = payload["data"][0]
    assert row["fullname"] == "No Checkin Staff"
    assert row["checkins"] is None
    assert row["checkouts"] is None
    assert row["payment"] is None


def test_get_all_ot_records_table_formats_download_rows_as_strings(ot_views, monkeypatch):
    captured = {}

    def fake_write_ot_report_workbook(writer, df, format):
        captured["df"] = df.copy()
        df.to_excel(writer, index=False)

    monkeypatch.setattr(ot_views, "write_ot_report_workbook", fake_write_ot_report_workbook)

    shift_record = _make_record(
        staff_id=910,
        fullname="Download Staff",
        sap_id="SAP-910",
        shift_start=datetime(2024, 1, 2, 9, 0),
        shift_end=datetime(2024, 1, 2, 17, 0),
        rate=100.0,
    )
    shifts = [
        SimpleNamespace(
            datetime=SimpleNamespace(lower=shift_record.shift.datetime.lower, upper=shift_record.shift.datetime.upper),
            records=[shift_record],
        )
    ]
    logins = [
        _make_login(910, 81, _bangkok_dt(2024, 1, 2, 9, 10), _bangkok_dt(2024, 1, 2, 16, 50)),
    ]

    ot_views.StaffWorkLogin = SimpleNamespace(
        query=FakeLoginQuery(logins),
        start_datetime=DummyField(),
    )
    ot_views.OtShift = SimpleNamespace(
        query=FakeShiftQuery(shifts),
        datetime=DummyField(),
        timeslot=DummyField(),
    )

    app = Flask("test")
    with app.test_request_context(
        "/app/api?start=2024-01-02T00:00:00%2B07:00&end=2024-01-02T23:59:59%2B07:00&download=yes&format=timesheet"
    ):
        response = _call_unwrapped_view(ot_views.get_all_ot_records_table)(announcement_id=7)

    assert response.status_code == 200
    assert "01-2024_ot_timesheet_all.xlsx" in response.headers.get("Content-Disposition", "")
    assert captured["df"].iloc[0]["start"] == "2024-01-02 09:00:00"
    assert captured["df"].iloc[0]["end"] == "2024-01-02 17:00:00"
    assert captured["df"].iloc[0]["checkins"] == "2024-01-02 09:10:00"
    assert captured["df"].iloc[0]["checkouts"] == "2024-01-02 16:50:00"
