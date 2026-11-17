import importlib
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

package = ModuleType('staff_diagnostic_tests')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'app/staff')]
sys.modules[package.__name__] = package
diagnostics = importlib.import_module('staff_diagnostic_tests.reminder_diagnostics')
DAY = date(2026, 11, 16)


def timestamp(hour, minute):
    return diagnostics.BANGKOK.localize(datetime(2026, 11, 16, hour, minute))


def snapshot(**changes):
    args = dict(account=SimpleNamespace(id=1588, is_active=True, is_retired=False, line_id='linked'),
                setting=SimpleNamespace(enabled=True, average_reminder=True, system_reminder=False,
                    weekdays='0,1,2,3,4', calculated_for=DAY, sample_days=32,
                    average_checkin_time=time(7, 55, 3), reminder_time=time(8)),
                at=timestamp(8, 0), records=[], attempts=[])
    args.update(changes)
    return args


def test_early_average_eligible_and_later_scan_ignored():
    args = snapshot(records=[SimpleNamespace(id=380576, start_datetime=timestamp(8, 19))])
    result = diagnostics.evaluate_snapshot(**args)
    assert result['eligible']
    assert result['later_scans'] == [dict(id=380576, start=timestamp(8, 19).isoformat())]
    args['at'] = timestamp(8, 20)
    result = diagnostics.evaluate_snapshot(**args)
    assert not result['eligible']
    assert [item['name'] for item in result['checks'] if not item['passed']] == ['no_prior_attendance']


@pytest.mark.parametrize('change,blocked', [
    (dict(excused=True), 'leave_or_wfh'),
    (dict(special_wfh=True), 'special_wfh'),
    (dict(holiday=SimpleNamespace(holiday_name='holiday')), 'holiday'),
    (dict(message_error='RuntimeError: PUBLIC_BASE_URL missing'), 'message_buildable'),
    (dict(at=timestamp(9, 5)), 'delivery_window'),
    (dict(setting=None), 'saved_settings'),
])
def test_explains_exclusions(change, blocked):
    result = diagnostics.evaluate_snapshot(**snapshot(**change))
    assert not result['eligible']
    assert blocked in [item['name'] for item in result['checks'] if not item['passed']]


def test_stale_average_and_missing_line_explained():
    args = snapshot()
    args['setting'].calculated_for = DAY - timedelta(days=1)
    args['account'].line_id = None
    result = diagnostics.evaluate_snapshot(**args)
    blocked = [item['name'] for item in result['checks'] if not item['passed']]
    assert 'fresh_average' in blocked and 'linked_line' in blocked


def test_delivery_attempt_cutoff_and_utc_scan():
    args = snapshot()
    args['attempts'] = [SimpleNamespace(mode='average', scheduled_time=time(8), status='sent', attempted_at=timestamp(8, 5))]
    result = diagnostics.evaluate_snapshot(**args)
    assert result['eligible'] and len(result['later_attempts']) == 1
    args['at'] = timestamp(8, 10)
    assert not diagnostics.evaluate_snapshot(**args)['eligible']
    args['attempts'] = []
    args['records'] = [SimpleNamespace(id=1, start_datetime=datetime(2026, 11, 16, 0, 55))]
    result = diagnostics.evaluate_snapshot(**args)
    assert not result['eligible']  # 00:55 UTC = 07:55 Bangkok


def test_cli_is_read_only_and_interprets_at_as_bangkok(monkeypatch):
    from flask import Flask
    from click.testing import CliRunner

    main = ModuleType('app.main')
    main.db = SimpleNamespace(session=Mock())
    views = ModuleType('staff_diagnostic_tests.views')
    views.refresh_daily_attendance = Mock()
    monkeypatch.setitem(sys.modules, 'app.main', main)
    monkeypatch.setitem(sys.modules, views.__name__, views)
    sys.modules.pop('staff_diagnostic_tests.commands', None)
    commands = importlib.import_module('staff_diagnostic_tests.commands')
    app = Flask(__name__)
    commands.register_commands(app)
    report = diagnostics.evaluate_snapshot(**snapshot(records=[SimpleNamespace(id=380576, start_datetime=timestamp(8, 19))]))
    inspect = Mock(return_value=report)
    monkeypatch.setattr(diagnostics, 'diagnose_reminder', inspect)
    with app.app_context():
        result = CliRunner().invoke(app.cli, ['staff-reminders', 'diagnose', '--staff-id', '1588', '--at', '2026-11-16 08:00'])
    assert result.exit_code == 0, result.output
    assert 'PASS time_due' in result.output
    assert 'Later attendance ignored: id=380576' in result.output
    assert 'ELIGIBLE under inspected conditions' in result.output
    assert 'No notifications sent or data changed.' in result.output
    inspect.assert_called_once_with(1588, timestamp(8, 0))
    main.db.session.commit.assert_not_called()
