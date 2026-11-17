"""Exercise the revocation transaction without importing unrelated app integrations."""
import ast
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from werkzeug.exceptions import BadRequest, Conflict
from flask import abort


def revoke_function():
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'app/staff/views.py').read_text())
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == 'hr_revoke_checkin_request')
    node.decorator_list = []
    return compile(ast.Module(body=[node], type_ignores=[]), '<revocation>', 'exec')


@pytest.mark.parametrize('state', ['approved', 'pending', 'cancelled', 'blank_reason'])
def test_hr_revocation_transaction(state):
    approved_at = datetime(2026, 11, 10, 4, tzinfo=timezone.utc)
    record = SimpleNamespace(approved_at=approved_at if state != 'pending' else None,
                             cancelled_at=approved_at if state == 'cancelled' else None,
                             work_datetime=approved_at, staff_account_id=42, approver_id=29)
    query = Mock()
    query.filter_by.return_value = query
    query.populate_existing.return_value = query
    query.with_for_update.return_value = query
    query.first_or_404.return_value = record
    login = SimpleNamespace(start_datetime=approved_at, end_datetime=None)
    login_query = Mock()
    login_query.filter_by.return_value.all.return_value = [login]
    session = Mock()
    refresh = Mock()
    events = []
    session.flush.side_effect = lambda: events.append('flush')
    refresh.side_effect = lambda *args, **kwargs: events.append('refresh')
    session.commit.side_effect = lambda: events.append('commit')
    scope = dict(request=SimpleNamespace(form={'reason': '  ' if state == 'blank_reason' else 'Wrong date'}),
                 abort=abort, StaffRequestWorkLogin=SimpleNamespace(query=query),
                 StaffWorkLogin=SimpleNamespace(query=login_query), current_user=SimpleNamespace(id=7),
                 datetime=datetime, pytz=SimpleNamespace(utc=timezone.utc),
                 _to_bangkok=lambda value: value, db=SimpleNamespace(session=session),
                 _notify_checkin_request_revoked=Mock(return_value=[]),
                 refresh_daily_attendance=refresh, flash=Mock(), redirect=lambda value: value,
                 url_for=lambda value: value)
    exec(revoke_function(), scope)
    if state != 'approved':
        with pytest.raises(BadRequest if state == 'blank_reason' else Conflict):
            scope['hr_revoke_checkin_request'](123)
        session.delete.assert_not_called()
        session.commit.assert_not_called()
        scope['_notify_checkin_request_revoked'].assert_not_called()
        return
    assert scope['hr_revoke_checkin_request'](123) == 'staff.hr_checkin_requests'
    scope['_notify_checkin_request_revoked'].assert_called_once_with(record)
    assert record.approved_at is None
    assert record.revoked_approved_at == approved_at
    assert record.approver_id == 29
    assert record.revoked_by_id == 7
    assert record.revocation_reason == 'Wrong date'
    assert record.cancelled_at is not None
    session.delete.assert_called_once_with(login)
    login_query.filter_by.assert_called_once_with(request_id=123)
    refresh.assert_called_once_with(approved_at.date(), staff_ids=[42])
    assert events == ['flush', 'refresh', 'commit']


@pytest.mark.parametrize('failure', [None, 'email', 'LINE'])
def test_revocation_notifies_both_parties_and_isolates_channel_failures(failure):
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'app/staff/views.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == '_notify_checkin_request_revoked')
    requester = SimpleNamespace(id=42, fullname='Requester', email='requester', line_id='U42')
    approver = SimpleNamespace(id=29, fullname='Approver', email='approver@example.org', line_id='U29')
    record = SimpleNamespace(id=123, staff=requester, approver=approver, is_checkin=False,
                             work_datetime=datetime(2026, 11, 10), revocation_reason='Wrong time')
    send_mail, push = Mock(), Mock()
    if failure == 'email':
        send_mail.side_effect = [RuntimeError('offline'), None]
    if failure == 'LINE':
        push.side_effect = [RuntimeError('offline'), None]
    scope = dict(current_user=SimpleNamespace(fullname='HR Officer'),
                 current_app=SimpleNamespace(debug=False, logger=Mock()),
                 _format_bangkok_datetime=lambda value: '10/11/2026 09:00',
                 send_mail=send_mail, line_bot_api=SimpleNamespace(push_message=push),
                 TextSendMessage=lambda text: text)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<notifications>', 'exec'), scope)
    assert scope['_notify_checkin_request_revoked'](record) == ([failure] if failure else [])
    assert [call.args[0] for call in send_mail.call_args_list] == [
        ['requester@mahidol.ac.th'], ['approver@example.org']]
    assert [call.kwargs['to'] for call in push.call_args_list] == ['U42', 'U29']
    message = send_mail.call_args_list[0].args[2]
    assert 'ตามคำร้องขอของพนักงานผู้ยื่นคำขอ' in message
    assert 'หากพนักงานไม่ได้ร้องขอให้เพิกถอน' in message
    assert 'ทันที' in message
    for text in ['Requester', 'Approver', 'HR Officer', 'Wrong time', 'ออกงาน']:
        assert text in message
    assert all(call.kwargs['messages'] == message for call in push.call_args_list)
