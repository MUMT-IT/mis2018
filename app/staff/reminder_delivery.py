"""Durable at-most-once reminder attempts, shared by both delivery schedules."""
import logging
from datetime import datetime, time

import pytz

logger = logging.getLogger(__name__)


def has_personalized_time(setting, target_date):
    return (setting.calculated_for == target_date and setting.sample_days >= 10
            and setting.average_checkin_time is not None
            and time(8) <= setting.reminder_time <= time(9))


def reminder_due(setting, target_date, mode='system', now=None):
    if setting is None:
        return mode == 'system'
    if (not setting.enabled or str(target_date.weekday()) not in setting.weekdays.split(',')):
        return False
    if mode == 'system':
        return setting.system_reminder or (
            setting.average_reminder and not has_personalized_time(setting, target_date))
    if mode != 'average':
        raise ValueError('Unknown reminder mode')
    return (setting.average_reminder and has_personalized_time(setting, target_date)
            and now is not None and time(8) <= now.time().replace(second=0, microsecond=0) <= time(9)
            and setting.reminder_time <= now.time())


def claim_delivery(staff_id, target_date, mode, scheduled_time):
    from sqlalchemy.exc import IntegrityError
    from app.main import db
    from .models import StaffCheckinReminderDelivery

    # Reserve under database unique constraints, including when schedulers overlap.
    # The savepoint isolates a duplicate claim without losing other session state.
    try:
        with db.session.begin_nested():
            attempt = StaffCheckinReminderDelivery(
                staff_id=staff_id, work_date=target_date, mode=mode,
                scheduled_time=scheduled_time, status='sending', attempted_at=datetime.now(pytz.utc))
            db.session.add(attempt)
            db.session.flush()
    except IntegrityError as exc:
        code = getattr(exc.orig, 'pgcode', None) or getattr(exc.orig, 'sqlstate', None)
        if code == '23505' or getattr(exc.orig, 'sqlite_errorcode', None) == 2067:
            return None
        raise
    delivery_id = attempt.id
    # Persist before contacting LINE, so a crash cannot trigger a duplicate attempt.
    db.session.commit()
    return delivery_id


def finish_delivery(delivery_id, status):
    from app.main import db
    from .models import StaffCheckinReminderDelivery

    StaffCheckinReminderDelivery.query.filter_by(id=delivery_id).update(dict(status=status))
    db.session.commit()


def deliver_once(account, target_date, mode, scheduled_time, message, push):
    delivery_id = claim_delivery(account.id, target_date, mode, scheduled_time)
    if delivery_id is None:
        return 'skipped'
    try:
        push(to=account.line_id, messages=message)
    except Exception:
        # A timeout can mean LINE accepted the message. Retain the claim rather
        # than automatically retrying an ambiguous outcome and sending twice.
        finish_delivery(delivery_id, 'failed')
        logger.exception('checkin_reminder_failed staff_id=%s date=%s mode=%s',
                         account.id, target_date, mode)
        return 'failed'
    finish_delivery(delivery_id, 'sent')
    return 'sent'
