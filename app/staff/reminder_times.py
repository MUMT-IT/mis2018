"""Daily check-in averages; calculating times never sends notifications."""
from datetime import datetime, time, timedelta
from math import ceil

import pytz

BANGKOK = pytz.timezone('Asia/Bangkok')


def calculate_reminder_time(records, as_of):
    """Use first real scans from the 56 complete local days before as_of."""
    first_by_day = {}
    start = as_of - timedelta(days=56)
    for record in records:
        if (record.record_source not in (None, '', 'scan')
                or record.correction_type or record.request_id or record.creator_id):
            continue
        stamp = record.start_datetime
        if stamp is None:
            continue
        # Database timestamps are UTC; legacy naive timestamps follow that convention.
        if stamp.tzinfo is None:
            stamp = pytz.utc.localize(stamp)
        stamp = stamp.astimezone(BANGKOK)
        day = stamp.date()
        if start <= day < as_of:
            first_by_day[day] = min(first_by_day.get(day, stamp), stamp)
    count = len(first_by_day)
    if count < 10:
        return dict(sample_days=count, average_checkin_time=None, reminder_time=time(8, 29))
    seconds = sum(s.hour * 3600 + s.minute * 60 + s.second for s in first_by_day.values()) / count
    average_seconds = min(round(seconds), 86399)
    average = time(average_seconds // 3600, (average_seconds % 3600) // 60, average_seconds % 60)
    slot = ceil(max(8 * 3600, min(9 * 3600, seconds)) / 300) * 300
    return dict(sample_days=count, average_checkin_time=average,
                reminder_time=time(slot // 3600, (slot % 3600) // 60))


def refresh_reminder_times(as_of=None, dry_run=False):
    from app.main import db
    from .models import StaffAccount, StaffCheckinReminderSetting, StaffWorkLogin

    as_of = as_of or datetime.now(BANGKOK).date()
    start = BANGKOK.localize(datetime.combine(as_of - timedelta(days=56), time.min))
    end = BANGKOK.localize(datetime.combine(as_of, time.min))
    settings = (StaffCheckinReminderSetting.query.join(StaffAccount)
                .filter(StaffCheckinReminderSetting.enabled.is_(True),
                        StaffCheckinReminderSetting.average_reminder.is_(True)).all())
    active_ids = {account.id for account in StaffAccount.get_active_accounts()}
    settings = [setting for setting in settings if setting.staff_id in active_ids]
    grouped = {}
    if settings:
        records = StaffWorkLogin.query.filter(
            StaffWorkLogin.staff_id.in_([setting.staff_id for setting in settings]),
            StaffWorkLogin.start_datetime >= start,
            StaffWorkLogin.start_datetime < end,
        ).all()
        for record in records:
            grouped.setdefault(record.staff_id, []).append(record)
    summaries = []
    for setting in settings:
        result = calculate_reminder_time(grouped.get(setting.staff_id, []), as_of)
        summaries.append(dict(staff_id=setting.staff_id, **result))
        if not dry_run:
            for key, value in result.items():
                setattr(setting, key, value)
            setting.calculated_for = as_of
    if not dry_run:
        db.session.commit()
    return summaries
