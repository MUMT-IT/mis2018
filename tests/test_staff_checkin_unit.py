from __future__ import annotations

import importlib
import sys
import types
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytz


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
    )
    monkeypatch.setitem(sys.modules, "app.staff.forms", staff_forms_mod)

    staff_models_mod = _module(
        "app.staff.models",
        db=SimpleNamespace(session=_FakeSession()),
        StaffWorkLogin=None,
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

    sys.modules.pop("app.staff.views", None)


@pytest.fixture
def staff_views(monkeypatch):
    _install_import_stubs(monkeypatch)
    views = importlib.import_module("app.staff.views")
    return views


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
    ("start_time", "end_time", "expected_hours"),
    [
        ((7, 30), (17, 30), 8.0),
        ((8, 30), (16, 30), 8.0),
        ((9, 15), (18, 45), 8.0),
        ((9, 15), (15, 0), 5.8),
        ((6, 30), (7, 30), 0.0),
        ((18, 0), (19, 0), 1.0),
    ],
)
def test_calculate_work_hours_starts_at_eight_and_caps_total(
    staff_views, start_time, end_time, expected_hours
):
    tz = pytz.timezone("Asia/Bangkok")
    start_dt = tz.localize(datetime(2026, 6, 26, *start_time))
    end_dt = tz.localize(datetime(2026, 6, 26, *end_time))

    assert staff_views._calculate_work_hours(start_dt, end_dt) == expected_hours


def test_calculate_work_hours_requires_checkout(staff_views):
    start_dt = pytz.timezone("Asia/Bangkok").localize(datetime(2026, 6, 26, 8, 0))

    assert staff_views._calculate_work_hours(start_dt, None) is None


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


def test_handle_login_scan_request_posts_shared_flow(staff_views, monkeypatch):
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
        return SimpleNamespace(id=1), "checked in", 3

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
    assert payload["activity"] == "checked in"
    assert payload["name"] == "Test User"
    assert payload["numScans"] == 3
    assert payload["time"]
    assert pushed and pushed[0]["to"] == "line-1"
