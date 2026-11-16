"""Check duplicate-entry validation without unrelated application imports."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def load_function(name, scope):
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'app/staff/views.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<checkin-validation>', 'exec'), scope)
    return scope[name]


@pytest.mark.parametrize('rows,expected', [
    ([], False),
    ([SimpleNamespace(start_datetime=object(), correction_type=None)], True),
    ([SimpleNamespace(start_datetime=object(), correction_type='checkin')], True),
    ([SimpleNamespace(start_datetime=object(), correction_type='checkout')], False),
    ([SimpleNamespace(start_datetime=None, correction_type=None)], False),
])
def test_existing_checkin(rows, expected):
    query = Mock()
    query.filter_by.return_value.all.return_value = rows
    fn = load_function('_has_existing_checkin', {'StaffWorkLogin': SimpleNamespace(query=query)})
    assert fn(42, '20261112') is expected
    query.filter_by.assert_called_once_with(staff_id=42, date_id='20261112')


def test_request_rejected_before_creating_duplicate():
    from datetime import datetime
    import pytz
    flash = Mock()
    existing = Mock(return_value=True)
    model = Mock()
    model.generate_date_id.return_value = '20200101'
    fn = load_function('request_for_clockin_clockout', dict(
        request=SimpleNamespace(method='POST', form={
            'clock': 'checkin', 'reason': 'Earlier entry', 'workdatetime': '01/01/2020 06:00',
        }), datetime=datetime, tz=pytz.timezone('Asia/Bangkok'),
        StaffRequestWorkLogin=model, current_user=SimpleNamespace(id=42),
        _has_existing_checkin=existing, flash=flash,
        redirect=lambda url: url, url_for=lambda endpoint: endpoint,
    ))
    assert fn() == 'staff.show_time_report'
    existing.assert_called_once_with(42, '20200101')
    model.assert_not_called()
    flash.assert_called_once()
