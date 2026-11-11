"""Check calendar messages without loading unrelated application integrations."""
import ast
import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import arrow
import pytz
from flask import Flask


def calendar_scope():
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'app/room_scheduler/views.py').read_text())
    names = {'_event_rooms', '_room_names', '_ics_escape', '_ics_timestamp',
             '_ics_param_escape', 'build_room_event_ics', '_build_room_event_attachment', 'cancel'}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    for node in nodes:
        node.decorator_list = []
    scope = dict(os=os, arrow=arrow, pytz=pytz, localtz=pytz.timezone('Asia/Bangkok'))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<room-calendar>', 'exec'), scope)
    return scope


def booking(event_id=42):
    return SimpleNamespace(
        id=event_id, start=datetime(2026, 11, 12, 9), end=datetime(2026, 11, 12, 10),
        title='Team meeting', note='', creator=SimpleNamespace(fullname='Booker'),
        booked_rooms=[SimpleNamespace(number='101', location='Building A')],
        participants=[SimpleNamespace(email='attendee', fullname='Attendee')], cancelled_at=None,
    )


def test_cancellation_matches_invitation_and_increases_sequence():
    scope = calendar_scope()
    event = booking()
    invitation = scope['build_room_event_ics']([event]).decode()
    cancellation = scope['build_room_event_ics']([event], method='CANCEL').decode()
    for line in invitation.splitlines():
        if line.startswith(('UID:', 'ORGANIZER;', 'DTSTART:', 'DTEND:', 'ATTENDEE;')):
            assert line in cancellation.splitlines()
    assert 'METHOD:REQUEST' in invitation
    assert 'STATUS:CONFIRMED' in invitation
    assert 'SEQUENCE:0' in invitation
    assert 'METHOD:CANCEL' in cancellation
    assert 'STATUS:CANCELLED' in cancellation
    assert 'SEQUENCE:1' in cancellation


def test_cancel_attachment_only_contains_selected_date():
    scope = calendar_scope()
    scope['_collect_booking_series'] = Mock(return_value=[booking(), booking(43)])
    attachment = scope['_build_room_event_attachment'](booking(), method='CANCEL')[0]
    scope['_collect_booking_series'].assert_not_called()
    assert attachment['content_type'] == 'text/calendar; charset=utf-8; method=CANCEL'
    assert b'UID:room-event-42@' in attachment['data']
    assert b'UID:room-event-43@' not in attachment['data']


def test_series_invitation_preserves_cancelled_date_status():
    scope = calendar_scope()
    cancelled = booking()
    cancelled.cancelled_at = datetime(2026, 11, 11)
    scope['_collect_booking_series'] = Mock(return_value=[cancelled, booking(43)])
    data = scope['_build_room_event_attachment'](booking(43))[0]['data'].decode()
    events = data.split('BEGIN:VEVENT')[1:]
    assert 'STATUS:CANCELLED' in events[0]
    assert 'STATUS:CONFIRMED' in events[1]


def test_cancel_route_sends_calendar_attachment():
    scope = calendar_scope()
    event = booking()
    event.datetime = SimpleNamespace(lower=event.start, upper=event.end)
    event.room = event.booked_rooms[0]
    event.category = 'Meeting'
    event.notify_participants = True
    event.master_id = None
    app = Flask(__name__)
    scope.update(
        RoomEvent=SimpleNamespace(query=SimpleNamespace(get=Mock(return_value=event))),
        current_user=SimpleNamespace(id=7), current_app=app,
        db=SimpleNamespace(session=Mock()), flash=Mock(), send_mail=Mock(),
        redirect=lambda url: url, url_for=lambda endpoint: endpoint,
    )
    with app.test_request_context('/'):
        from flask import request
        scope['request'] = request
        assert scope['cancel'](42) == 'room.index'
    args, kwargs = scope['send_mail'].call_args
    assert args[0] == ['attendee@mahidol.ac.th']
    assert event.cancelled_by == 7
    scope['db'].session.commit.assert_called_once()
    assert b'METHOD:CANCEL' in kwargs['attachments'][0]['data']
