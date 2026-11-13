import importlib.util
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
import pytz

spec = importlib.util.spec_from_file_location('reminder_delivery', Path(__file__).resolve().parents[1] / 'app/staff/reminder_delivery.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
TODAY = date(2026, 11, 13)


def setting(**changes):
    data = dict(enabled=True, system_reminder=False, average_reminder=True,
                weekdays='0,1,2,3,4', sample_days=10, calculated_for=TODAY,
                average_checkin_time=time(8, 12), reminder_time=time(8, 15))
    data.update(changes)
    return SimpleNamespace(**data)


def now(clock):
    return pytz.timezone('Asia/Bangkok').localize(datetime.combine(TODAY, clock))


@pytest.mark.parametrize('clock,expected', [(time(7, 59), False), (time(8, 10), False),
    (time(8, 15), True), (time(8, 20), True), (time(9, 0, 30), True), (time(9, 1), False)])
def test_personalized_due_window(clock, expected):
    assert bool(delivery.reminder_due(setting(), TODAY, 'average', now(clock))) is expected


@pytest.mark.parametrize('changes', [dict(sample_days=9), dict(calculated_for=TODAY-timedelta(days=1)),
    dict(calculated_for=None), dict(average_checkin_time=None), dict(reminder_time=time(7, 30))])
def test_fallback_only_uses_standard_sender(changes):
    preferences = setting(**changes)
    assert delivery.reminder_due(preferences, TODAY, 'system')
    assert not delivery.reminder_due(preferences, TODAY, 'average', now(time(8, 30)))


def test_system_defaults_and_selected_modes():
    assert delivery.reminder_due(None, TODAY)
    assert not delivery.reminder_due(None, TODAY, 'average', now(time(8, 30)))
    assert not delivery.reminder_due(setting(), TODAY, 'system')
    assert delivery.reminder_due(setting(system_reminder=True), TODAY, 'system')
    for changes in [dict(enabled=False), dict(weekdays='0'), dict(average_reminder=False)]:
        assert not delivery.reminder_due(setting(**changes), TODAY, 'average', now(time(8, 30)))


@pytest.fixture
def ledger(monkeypatch):
    from sqlalchemy import create_engine, Column, Integer, Date, Time, String, DateTime, UniqueConstraint
    from sqlalchemy.orm import declarative_base, sessionmaker

    base = declarative_base()

    class Row(base):
        __tablename__ = 'staff_checkin_reminder_delivery'
        id = Column(Integer, primary_key=True)
        staff_id = Column(Integer, nullable=False)
        work_date = Column(Date, nullable=False)
        mode = Column(String(10), nullable=False)
        scheduled_time = Column(Time, nullable=False)
        status = Column(String(10), nullable=False)
        attempted_at = Column(DateTime(timezone=True), nullable=False)
        __table_args__ = (UniqueConstraint('staff_id', 'work_date', 'mode'),
                          UniqueConstraint('staff_id', 'work_date', 'scheduled_time'))

    engine = create_engine('sqlite://')
    base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    Row.query = session.query(Row)
    main = ModuleType('app.main')
    main.db = SimpleNamespace(session=session)
    models = ModuleType('app.staff.models')
    models.StaffCheckinReminderDelivery = Row
    monkeypatch.setitem(sys.modules, 'app.main', main)
    monkeypatch.setitem(sys.modules, 'app.staff.models', models)
    monkeypatch.setattr(delivery, '__package__', 'app.staff')
    yield session, Row
    session.close()
    engine.dispose()


def test_repeated_and_coincident_attempts_are_deduplicated(ledger):
    session, row = ledger
    account = SimpleNamespace(id=42, line_id='line-42')
    push = Mock()
    assert delivery.deliver_once(account, TODAY, 'average', time(8, 15), 'hello', push) == 'sent'
    assert delivery.deliver_once(account, TODAY, 'average', time(8, 20), 'hello', push) == 'skipped'
    assert delivery.deliver_once(account, TODAY, 'system', time(8, 15), 'hello', push) == 'skipped'
    assert delivery.deliver_once(account, TODAY, 'system', time(8, 29), 'hello', push) == 'sent'
    assert delivery.deliver_once(account, TODAY, 'system', time(8, 29), 'hello', push) == 'skipped'
    assert push.call_count == 2
    assert [r.status for r in session.query(row).all()] == ['sent', 'sent']
    assert delivery.deliver_once(account, TODAY + timedelta(days=1), 'average', time(8, 15), 'hello', push) == 'sent'


def test_ambiguous_failure_is_not_automatically_retried(ledger):
    session, row = ledger
    account = SimpleNamespace(id=42, line_id='line-42')
    push = Mock(side_effect=TimeoutError('unknown delivery outcome'))
    assert delivery.deliver_once(account, TODAY, 'average', time(8, 15), 'hello', push) == 'failed'
    assert session.query(row).one().status == 'failed'
    assert delivery.deliver_once(account, TODAY, 'average', time(8, 15), 'hello', push) == 'skipped'
    push.assert_called_once()


def test_claim_survives_crash_before_push(ledger):
    assert delivery.claim_delivery(42, TODAY, 'average', time(8, 15)) is not None
    assert delivery.claim_delivery(42, TODAY, 'average', time(8, 15)) is None
