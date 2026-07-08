from __future__ import annotations

import importlib
import os
import sys
import types
from datetime import datetime
from types import SimpleNamespace

import pytest
import pytz


def _install_import_stubs(monkeypatch):
    os.environ.setdefault("DATABASE_URL", "postgres://user:pass@localhost/dbname")
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    requests_stub = types.ModuleType("requests")
    requests_stub.get = lambda *_args, **_kwargs: SimpleNamespace(json=lambda: {})
    monkeypatch.setitem(sys.modules, "requests", requests_stub)

    main = types.ModuleType("app.main")
    main.app = SimpleNamespace(config={})
    main.db = SimpleNamespace(session=None)
    main.func = SimpleNamespace(timezone=lambda *_args, **_kwargs: None)
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
    monkeypatch.setitem(sys.modules, "app.staff.models", staff_models)

    forms = types.ModuleType("app.ot.forms")
    forms.pytz = pytz
    forms.StaffAccount = object()
    forms.Org = object()
    forms.OtPaymentAnnounce = object()
    forms.OtCompensationRate = object()
    forms.OtTimeSlot = object()
    forms.OtDocumentApproval = object()
    forms.OtJobRole = object()
    forms.OtRecord = object()
    forms.OtShift = object()
    forms.time_slots = []
    forms.create_ot_record_form = lambda *_args, **_kwargs: object
    forms.get_compensation_rates_for_timeslot = lambda *_args, **_kwargs: []
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
    drive.GoogleDrive = object
    monkeypatch.setitem(sys.modules, "pydrive.drive", drive)

    sys.modules.pop("app.ot.views", None)


@pytest.fixture
def ot_views(monkeypatch):
    _install_import_stubs(monkeypatch)
    views = importlib.import_module("app.ot.views")
    monkeypatch.setattr(views, "_is_external_account", lambda: False)
    return views


def _bangkok_dt(year, month, day, hour, minute):
    tz = pytz.timezone("Asia/Bangkok")
    return tz.localize(datetime(year, month, day, hour, minute))


def _make_record(*, record_id, start_dt, end_dt):
    time_slot = SimpleNamespace(start=start_dt.time(), end=end_dt.time())
    compensation = SimpleNamespace(time_slot=time_slot)
    return SimpleNamespace(
        id=record_id,
        canceled_at=None,
        start_datetime=start_dt,
        end_datetime=end_dt,
        compensation=compensation,
    )


def test_overlapping_helper_allows_touching_boundaries(ot_views):
    existing = _make_record(
        record_id=1,
        start_dt=_bangkok_dt(2026, 3, 1, 18, 0),
        end_dt=_bangkok_dt(2026, 3, 1, 22, 0),
    )

    assert not ot_views._has_overlapping_ot_record(
        [existing],
        _bangkok_dt(2026, 3, 1, 22, 0),
        _bangkok_dt(2026, 3, 1, 23, 0),
    )


def test_overlapping_helper_still_rejects_true_overlap(ot_views):
    existing = _make_record(
        record_id=1,
        start_dt=_bangkok_dt(2026, 3, 1, 18, 0),
        end_dt=_bangkok_dt(2026, 3, 1, 22, 0),
    )

    assert ot_views._has_overlapping_ot_record(
        [existing],
        _bangkok_dt(2026, 3, 1, 21, 0),
        _bangkok_dt(2026, 3, 1, 23, 0),
    )
