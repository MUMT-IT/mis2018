from __future__ import annotations

import importlib
import sys
import types
from datetime import datetime
from types import SimpleNamespace

import pytz


class _CapturingScheduler:
    instances = []

    def __init__(self, *args, **kwargs):
        self.added_jobs = []
        self.started = False
        _CapturingScheduler.instances.append(self)

    def add_job(self, func, *args, **kwargs):
        self.added_jobs.append((func, args, kwargs))

    def start(self):
        self.started = True


def _module(name: str, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def _import_jobs(monkeypatch):
    _CapturingScheduler.instances.clear()
    monkeypatch.setitem(sys.modules, 'apscheduler', _module('apscheduler'))
    monkeypatch.setitem(sys.modules, 'apscheduler.schedulers', _module('apscheduler.schedulers'))
    monkeypatch.setitem(
        sys.modules,
        'apscheduler.schedulers.blocking',
        _module('apscheduler.schedulers.blocking', BlockingScheduler=_CapturingScheduler),
    )
    monkeypatch.setitem(
        sys.modules,
        'requests',
        _module(
            'requests',
            request=lambda **kwargs: SimpleNamespace(status_code=200, url=kwargs['url'], text='ok'),
            get=lambda url, **kwargs: SimpleNamespace(status_code=200, url=url, text='ok'),
            HTTPError=RuntimeError,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        'app.staff.views',
        _module('app.staff.views', send_missing_checkin_reminders=lambda *_args, **_kwargs: None),
    )
    sys.modules.pop('app.jobs', None)
    return importlib.import_module('app.jobs')


def test_jobs_registers_weekday_checkin_reminder(monkeypatch):
    jobs = _import_jobs(monkeypatch)

    scheduler = jobs.scheduler
    added = [entry for entry in scheduler.added_jobs if entry[0] is jobs.send_checkin_reminder]

    assert added
    _, args, kwargs = added[0]
    assert args[0] == 'cron'
    assert kwargs['day_of_week'] == 'mon-fri'
    assert kwargs['hour'] == '8'
    assert kwargs['minute'] == '50'
    assert kwargs['timezone'] == 'Asia/Bangkok'
    assert scheduler.started is True


def test_send_checkin_reminder_uses_0850_bangkok_cutoff(monkeypatch):
    jobs = _import_jobs(monkeypatch)
    captured = []

    monkeypatch.setitem(
        sys.modules,
        'app.staff.views',
        _module('app.staff.views', send_missing_checkin_reminders=lambda cutoff_dt: captured.append(cutoff_dt)),
    )

    class FakeDatetime:
        @staticmethod
        def now(tz=None):
            dt = datetime(2026, 6, 26, 12, 0)
            if tz is None:
                return dt
            if hasattr(tz, 'localize'):
                return tz.localize(dt)
            return dt.replace(tzinfo=tz)

        @staticmethod
        def combine(date_value, time_value):
            return datetime.combine(date_value, time_value)

    monkeypatch.setattr(jobs, 'datetime', FakeDatetime)

    jobs.send_checkin_reminder()

    assert len(captured) == 1
    cutoff_dt = captured[0]
    assert cutoff_dt.tzinfo is not None
    assert cutoff_dt.astimezone(pytz.timezone('Asia/Bangkok')).strftime('%H:%M') == '08:50'
