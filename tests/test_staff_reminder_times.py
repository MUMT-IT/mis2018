"""Exercise time calculation without loading the application's integrations."""
import importlib.util
from datetime import date, datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytz

spec = importlib.util.spec_from_file_location('reminder_times', Path(__file__).resolve().parents[1] / 'app/staff/reminder_times.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
AS_OF = date(2026, 11, 13)


def scan(day, hour=8, minute=12, **changes):
    fields = dict(start_datetime=module.BANGKOK.localize(datetime.combine(day, time(hour, minute))),
                  record_source='scan', correction_type=None, request_id=None, creator_id=None)
    fields.update(changes)
    return SimpleNamespace(**fields)


@pytest.mark.parametrize('hour,minute,expected', [(7, 20, time(8)), (8, 12, time(8, 15)),
                                                (8, 45, time(8, 45)), (8, 47, time(8, 50)),
                                                (9, 15, time(9))])
def test_average_clamped_and_rounded(hour, minute, expected):
    records = [scan(AS_OF - timedelta(days=i), hour, minute) for i in range(1, 11)]
    result = module.calculate_reminder_time(records, AS_OF)
    assert result == dict(sample_days=10, average_checkin_time=time(hour, minute), reminder_time=expected)


def test_only_first_scan_each_day_and_utc_conversion():
    records = []
    for i in range(1, 11):
        day = AS_OF - timedelta(days=i)
        records.extend([scan(day, 16, 30), scan(day, 8, 10)])
    records[1].start_datetime = records[1].start_datetime.astimezone(pytz.utc).replace(tzinfo=None)
    result = module.calculate_reminder_time(records, AS_OF)
    assert result['sample_days'] == 10
    assert result['average_checkin_time'] == time(8, 10)
    assert result['reminder_time'] == time(8, 10)


def test_insufficient_history_and_window_exclusions():
    records = [scan(AS_OF - timedelta(days=i)) for i in range(1, 10)]
    records += [scan(AS_OF), scan(AS_OF - timedelta(days=57)),
                scan(AS_OF - timedelta(days=10), record_source='hr_manual'),
                scan(AS_OF - timedelta(days=11), record_source='approved_request'),
                scan(AS_OF - timedelta(days=12), request_id=3),
                scan(AS_OF - timedelta(days=13), creator_id=2),
                scan(AS_OF - timedelta(days=14), correction_type='checkout')]
    assert module.calculate_reminder_time(records, AS_OF) == dict(
        sample_days=9, average_checkin_time=None, reminder_time=time(8, 29))
    records.append(scan(AS_OF - timedelta(days=56), record_source=None))
    assert module.calculate_reminder_time(records, AS_OF)['sample_days'] == 10


def test_empty_history():
    assert module.calculate_reminder_time([], AS_OF)['reminder_time'] == time(8, 29)


@pytest.mark.parametrize('dry_run', [False, True])
def test_refresh_saves_snapshot_or_previews_without_mutation(monkeypatch, dry_run):
    import sys
    from types import ModuleType
    from unittest.mock import MagicMock

    db = SimpleNamespace(session=MagicMock())
    main = ModuleType('app.main')
    main.db = db
    models = ModuleType('app.staff.models')
    setting = SimpleNamespace(staff_id=42, reminder_time=time(8, 29))
    inactive = SimpleNamespace(staff_id=99)
    setting_model = MagicMock()
    setting_model.query.join.return_value.filter.return_value.all.return_value = [setting, inactive]
    records = [scan(AS_OF - timedelta(days=i), 8, 12) for i in range(1, 11)]
    for record in records:
        record.staff_id = 42
    login_model = MagicMock()
    login_model.start_datetime = datetime(2026, 10, 1, tzinfo=pytz.utc)
    login_model.query.filter.return_value.all.return_value = records
    models.StaffCheckinReminderSetting = setting_model
    models.StaffWorkLogin = login_model
    models.StaffAccount = SimpleNamespace(get_active_accounts=lambda: [SimpleNamespace(id=42)])
    monkeypatch.setitem(sys.modules, 'app.main', main)
    monkeypatch.setitem(sys.modules, 'app.staff.models', models)
    monkeypatch.setattr(module, '__package__', 'app.staff')
    result = module.refresh_reminder_times(AS_OF, dry_run=dry_run)
    assert len(result) == 1 and result[0]['staff_id'] == 42
    assert result[0]['reminder_time'] == time(8, 15)
    if dry_run:
        assert setting.reminder_time == time(8, 29)
        assert not hasattr(setting, 'calculated_for')
        db.session.commit.assert_not_called()
    else:
        assert setting.reminder_time == time(8, 15)
        assert setting.calculated_for == AS_OF
        assert setting.sample_days == 10
        db.session.commit.assert_called_once()
