from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace


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


def _import_jobs(monkeypatch, requests_module=None):
    _CapturingScheduler.instances.clear()
    monkeypatch.setitem(sys.modules, 'apscheduler', _module('apscheduler'))
    monkeypatch.setitem(sys.modules, 'apscheduler.schedulers', _module('apscheduler.schedulers'))
    monkeypatch.setitem(
        sys.modules,
        'apscheduler.schedulers.blocking',
        _module('apscheduler.schedulers.blocking', BlockingScheduler=_CapturingScheduler),
    )
    if requests_module is None:
        requests_module = _module(
            'requests',
            request=lambda **kwargs: SimpleNamespace(status_code=200, url=kwargs['url'], text='ok'),
            get=lambda url, **kwargs: SimpleNamespace(status_code=200, url=url, text='ok'),
            HTTPError=RuntimeError,
        )
    monkeypatch.setitem(sys.modules, 'requests', requests_module)
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


def test_send_checkin_reminder_posts_tokenized_request(monkeypatch):
    monkeypatch.setenv('JOB_TOKEN', 'test-job-token')
    monkeypatch.setenv('JOBS_BASE_URL', 'https://example.test')

    captured = {}

    def request(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(status_code=200, url=kwargs['url'], text='ok')

    requests_module = _module(
        'requests',
        request=request,
        get=lambda url, **kwargs: SimpleNamespace(status_code=200, url=url, text='ok'),
        HTTPError=RuntimeError,
    )
    jobs = _import_jobs(monkeypatch, requests_module=requests_module)

    jobs.send_checkin_reminder()

    assert captured['method'] == 'POST'
    assert captured['url'] == 'https://example.test/staff/admin/line-remind-missing-checkin'
    assert 'date' in captured['params']
    assert captured['params']['job_token'] == 'test-job-token'
