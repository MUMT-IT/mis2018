"""Read-only reminder eligibility inspection using current persisted settings."""
from datetime import datetime, time

import pytz

from .reminder_delivery import has_personalized_time, reminder_due

BANGKOK = pytz.timezone('Asia/Bangkok')


def local_time(stamp):
    if stamp is None:
        return None
    if stamp.tzinfo is None:
        stamp = pytz.utc.localize(stamp)
    return stamp.astimezone(BANGKOK)


def evaluate_snapshot(account, setting, at, records, attempts, holiday=None,
                      excused=False, special_wfh=False, message_error=None):
    at = local_time(at)
    target_date = at.date()
    checks = []

    def check(name, passed, detail):
        checks.append(dict(name=name, passed=bool(passed), detail=str(detail)))

    check('weekday', target_date.weekday() < 5, target_date.strftime('%A'))
    check('delivery_window', time(8) <= at.time().replace(second=0, microsecond=0) <= time(9),
          '08:00–09:00 Asia/Bangkok')
    check('holiday', holiday is None, getattr(holiday, 'holiday_name', 'none'))
    check('active_account', account.is_active and not account.is_retired,
          'active={}, retired={}'.format(account.is_active, account.is_retired))
    check('linked_line', bool(account.line_id), 'linked' if account.line_id else 'not linked')
    check('saved_settings', setting is not None, 'personalized reminders require saved settings')
    if setting is not None:
        check('enabled', setting.enabled, setting.enabled)
        check('average_selected', setting.average_reminder, setting.average_reminder)
        check('selected_weekday', str(target_date.weekday()) in setting.weekdays.split(','), setting.weekdays)
        check('fresh_average', has_personalized_time(setting, target_date),
              'average={}, reminder={}, sample_days={}, calculated_for={}'.format(
                  setting.average_checkin_time, setting.reminder_time, setting.sample_days, setting.calculated_for))
        check('time_due', reminder_due(setting, target_date, 'average', at), setting.reminder_time)
    earlier_scans = []
    later_scans = []
    for record in records:
        stamp = local_time(record.start_datetime)
        item = dict(id=record.id, start=stamp.isoformat() if stamp else 'unknown')
        # Undated records still suppress delivery in the live sender.
        (earlier_scans if stamp is None or stamp <= at else later_scans).append(item)
    check('no_prior_attendance', not earlier_scans, earlier_scans or 'none at/before inspected time')
    check('leave_or_wfh', not excused, 'approved leave/WFH' if excused else 'none')
    check('special_wfh', not special_wfh, special_wfh)
    blocking_attempts = []
    later_attempts = []
    for attempt in attempts:
        stamp = local_time(attempt.attempted_at)
        item = dict(mode=attempt.mode, scheduled_time=str(attempt.scheduled_time),
                    status=attempt.status, attempted_at=stamp.isoformat() if stamp else 'unknown')
        blocks = attempt.mode == 'average' or (setting and attempt.scheduled_time == setting.reminder_time)
        if stamp is not None and stamp > at:
            later_attempts.append(item)
        elif blocks:
            blocking_attempts.append(item)
    check('no_previous_attempt', not blocking_attempts, blocking_attempts or 'none')
    check('message_buildable', message_error is None, message_error or 'no message construction error')
    return dict(staff_id=account.id, at=at.isoformat(), checks=checks,
                eligible=all(item['passed'] for item in checks),
                later_scans=later_scans, later_attempts=later_attempts)


def diagnose_reminder(staff_id, at=None):
    from .models import (StaffAccount, StaffCheckinReminderSetting, StaffWorkLogin,
                         StaffCheckinReminderDelivery, StaffSpecialWorkFromHomeDay)
    from .views import (_get_holiday_for_date, _checkin_reminder_excused_staff_ids,
                        _personalized_checkin_reminder_message)

    at = local_time(at or datetime.now(BANGKOK))
    target_date = at.date()
    account = StaffAccount.query.filter_by(id=staff_id).first()
    if account is None:
        raise ValueError('Staff account {} does not exist.'.format(staff_id))
    setting = StaffCheckinReminderSetting.query.filter_by(staff_id=staff_id).first()
    records = StaffWorkLogin.query.filter_by(staff_id=staff_id, date_id=target_date.strftime('%Y%m%d')).all()
    attempts = StaffCheckinReminderDelivery.query.filter_by(staff_id=staff_id, work_date=target_date).all()
    special = StaffSpecialWorkFromHomeDay.query.filter_by(work_date=target_date).first()
    message_error = None
    if setting and has_personalized_time(setting, target_date):
        try:
            _personalized_checkin_reminder_message(setting)
        except Exception as exc:
            message_error = '{}: {}'.format(type(exc).__name__, exc)
    return evaluate_snapshot(
        account, setting, at, records, attempts,
        holiday=_get_holiday_for_date(target_date),
        excused=staff_id in _checkin_reminder_excused_staff_ids(target_date),
        special_wfh=bool(special and any(staff.id == staff_id for staff in special.staff)),
        message_error=message_error,
    )
