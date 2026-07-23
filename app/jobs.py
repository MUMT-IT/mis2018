import logging
import os
import smtplib
import traceback
from datetime import datetime, timezone
from email.message import EmailMessage

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
import pytz

logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)
BASE_URL = os.environ.get('JOBS_BASE_URL', 'https://mumtmis.herokuapp.com')
JOB_TOKEN = os.environ.get('JOB_TOKEN')


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _safe_text(text, max_len=2000):
    if text is None:
        return ''
    return str(text).strip()[:max_len]


def _collect_runtime_context():
    return {
        'dyno': os.getenv('DYNO'),
        'process_type': os.getenv('HEROKU_PROCESS_TYPE'),
        'release_version': os.getenv('HEROKU_RELEASE_VERSION'),
        'app_name': os.getenv('HEROKU_APP_NAME'),
        'hostname': os.getenv('HOSTNAME'),
    }


def _send_admin_error_email(job_name, err, response_info=None):
    recipient = os.getenv('JOB_FAILURE_EMAIL_TO')
    if not recipient:
        logger.warning('failure_email_skipped job=%s reason=missing_recipient_env', job_name)
        return

    smtp_host = os.getenv('JOB_FAILURE_SMTP_HOST') or os.getenv('MAIL_SERVER')
    smtp_port = int(os.getenv('JOB_FAILURE_SMTP_PORT') or os.getenv('MAIL_PORT') or 587)
    smtp_username = os.getenv('JOB_FAILURE_SMTP_USERNAME') or os.getenv('MAIL_USERNAME')
    smtp_password = os.getenv('JOB_FAILURE_SMTP_PASSWORD') or os.getenv('MAIL_PASSWORD')
    smtp_use_tls = (os.getenv('JOB_FAILURE_SMTP_USE_TLS', 'true').strip().lower() in {'1', 'true', 'yes', 'on'})
    smtp_from = os.getenv('JOB_FAILURE_EMAIL_FROM') or smtp_username
    if not smtp_host or not smtp_from:
        logger.warning(
            'failure_email_skipped job=%s reason=missing_smtp_config host=%s from_present=%s',
            job_name,
            bool(smtp_host),
            bool(smtp_from),
        )
        return

    exc_traceback = traceback.format_exc()
    context = _collect_runtime_context()
    body_lines = [
        f'Job Failure Alert',
        f'Job name: {job_name}',
        f'Timestamp (UTC): {_now_iso()}',
        f'Exception type: {type(err).__name__}',
        f'Exception message: {_safe_text(err, 4000)}',
        '',
        'Dyno/process context:',
        *(f'- {key}: {value}' for key, value in context.items()),
        '',
        'Traceback:',
        exc_traceback,
    ]
    if response_info:
        body_lines.extend([
            '',
            'Relevant API response:',
            f"- status_code: {response_info.get('status_code')}",
            f"- body: {_safe_text(response_info.get('body'), 4000)}",
            f"- url: {response_info.get('url')}",
        ])

    message = EmailMessage()
    message['Subject'] = f'[MUMT-MIS][Job Failure] {job_name}'
    message['From'] = smtp_from
    message['To'] = recipient
    message.set_content('\n'.join(body_lines))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            if smtp_use_tls:
                server.starttls()
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.send_message(message)
        logger.info('failure_email_sent job=%s recipient=%s', job_name, recipient)
    except Exception:
        logger.exception('failure_email_send_failed job=%s recipient=%s', job_name, recipient)


def _request_or_raise(job_name, method, url, params=None, timeout=60):
    logger.info('job_checkpoint job=%s step=http_request_start method=%s url=%s', job_name, method, url)
    response = requests.request(method=method, url=url, params=params, timeout=timeout, allow_redirects=False)
    if response.status_code >= 300:
        logger.error(
            'job_http_failed job=%s status_code=%s url=%s body=%s',
            job_name,
            response.status_code,
            response.url,
            _safe_text(response.text, 4000),
        )
        error = requests.HTTPError(f'HTTP {response.status_code} from {response.url}')
        setattr(error, 'response_info', {
            'status_code': response.status_code,
            'body': _safe_text(response.text, 4000),
            'url': response.url,
        })
        raise error
    logger.info(
        'job_checkpoint job=%s step=http_request_success status_code=%s url=%s',
        job_name,
        response.status_code,
        url,
    )
    return response


def _run_job(job_name, fn):
    logger.info('job_start job=%s timestamp_utc=%s context=%s', job_name, _now_iso(), _collect_runtime_context())
    try:
        fn()
    except Exception as err:
        response_info = getattr(err, 'response_info', None)
        logger.exception('job_failed job=%s error_type=%s error_message=%s', job_name, type(err).__name__, err)
        _send_admin_error_email(job_name=job_name, err=err, response_info=response_info)
        raise
    else:
        logger.info('job_end job=%s status=success timestamp_utc=%s', job_name, _now_iso())


def send_event_notification():
    job_name = 'send_event_notification'

    def _job():
        params = {}
        if JOB_TOKEN:
            params['job_token'] = JOB_TOKEN
        _request_or_raise(
            job_name,
            'GET',
            f'{BASE_URL}/linebot/events/notification',
            params=params or None,
            timeout=60,
        )

    _run_job(
        job_name,
        _job,
    )


def send_room_notification_today():
    job_name = 'send_room_notification_today'

    def _job():
        params = {'when': 'today'}
        if JOB_TOKEN:
            params['job_token'] = JOB_TOKEN
        _request_or_raise(
            job_name,
            'GET',
            f'{BASE_URL}/linebot/rooms/notification',
            params=params,
            timeout=60,
        )

    _run_job(
        job_name,
        _job,
    )


def send_room_notification_tomorrow():
    job_name = 'send_room_notification_tomorrow'

    def _job():
        params = {'when': 'tomorrow'}
        if JOB_TOKEN:
            params['job_token'] = JOB_TOKEN
        _request_or_raise(
            job_name,
            'GET',
            f'{BASE_URL}/linebot/rooms/notification',
            params=params,
            timeout=60,
        )

    _run_job(
        job_name,
        _job,
    )


def send_complaint_summary_report():
    job_name = 'send_complaint_summary_report'

    def _job():
        params = {'send': 'true'}
        if JOB_TOKEN:
            params['job_token'] = JOB_TOKEN
        _request_or_raise(
            job_name,
            'GET',
            f'{BASE_URL}/complaint-tracker/admin/email-unfinished-summary',
            params=params,
            timeout=60,
        )

    _run_job(job_name, _job)


def send_line_reminder_no_status_today():
    job_name = 'send_line_reminder_no_status_today'

    def _job():
        params = {'send': 'true'}
        if JOB_TOKEN:
            params['job_token'] = JOB_TOKEN
        response = requests.get(
            f'{BASE_URL}/complaint-tracker/admin/line-remind-no-status-today',
            params=params,
            timeout=60,
        )
        logger.info(
            'job_checkpoint job=%s step=line_reminder_http_response status_code=%s',
            job_name,
            response.status_code,
        )
        if response.status_code == 404:
            logger.info('job_checkpoint job=%s step=no_unattended_records message=%s', job_name, _safe_text(response.text))
            return
        if response.status_code >= 400:
            logger.error(
                'job_http_failed job=%s status_code=%s url=%s body=%s',
                job_name,
                response.status_code,
                response.url,
                _safe_text(response.text, 4000),
            )
            error = requests.HTTPError(f'HTTP {response.status_code} from {response.url}')
            setattr(error, 'response_info', {
                'status_code': response.status_code,
                'body': _safe_text(response.text, 4000),
                'url': response.url,
            })
            raise error

    _run_job(job_name, _job)


def send_service_admin_monthly_overdue_summary():
    job_name = 'send_service_admin_monthly_overdue_summary'

    def _job():
        params = {'send': 'true'}
        if JOB_TOKEN:
            params['job_token'] = JOB_TOKEN
        _request_or_raise(
            job_name,
            'GET',
            f'{BASE_URL}/service_admin/admin/monthly-overdue-summary',
            params=params,
            timeout=90,
        )

    _run_job(job_name, _job)


def send_academic_services_weekly_overdue_invoice_reminder():
    job_name = 'send_academic_services_weekly_overdue_invoice_reminder'

    def _job():
        params = {'send': 'true'}
        if JOB_TOKEN:
            params['job_token'] = JOB_TOKEN
        _request_or_raise(
            job_name,
            'GET',
            f'{BASE_URL}/academic_services/admin/weekly-overdue-invoice-reminder',
            params=params,
            timeout=90,
        )

    _run_job(job_name, _job)


def send_checkin_reminder():
    job_name = 'send_checkin_reminder'

    def _job():
        bangkok = pytz.timezone('Asia/Bangkok')
        params = {'date': datetime.now(bangkok).strftime('%d/%m/%Y')}
        if JOB_TOKEN:
            params['job_token'] = JOB_TOKEN
        _request_or_raise(
            job_name,
            'POST',
            f'{BASE_URL}/staff/admin/line-remind-missing-checkin',
            params=params,
            timeout=60,
        )

    _run_job(job_name, _job)


scheduler = BlockingScheduler()
scheduler.add_job(send_event_notification,
                  'cron', day_of_week='mon-fri',
                  hour='8',
                  minute='00',
                  timezone='Asia/Bangkok')
scheduler.add_job(send_room_notification_today,
                  'cron', day_of_week='mon-fri',
                  hour='7',
                  minute='00',
                  timezone='Asia/Bangkok')
scheduler.add_job(send_room_notification_tomorrow,
                  'cron', day_of_week='mon-fri',
                  hour='15',
                  minute='00',
                  timezone='Asia/Bangkok')
scheduler.add_job(send_complaint_summary_report,
                  'cron', day_of_week='mon',
                  hour='9',
                  minute='00',
                  timezone='Asia/Bangkok')
scheduler.add_job(send_line_reminder_no_status_today,
                  'cron', day_of_week='mon-fri',
                  hour='15',
                  minute='00',
                  timezone='Asia/Bangkok')
scheduler.add_job(send_service_admin_monthly_overdue_summary,
                  'cron', day='1',
                  hour='9',
                  minute='00',
                  timezone='Asia/Bangkok')
scheduler.add_job(send_academic_services_weekly_overdue_invoice_reminder,
                  'cron', day_of_week='mon',
                  hour='9',
                  minute='15',
                  timezone='Asia/Bangkok')
scheduler.add_job(send_checkin_reminder,
                  'cron', day_of_week='mon-fri',
                  hour='8',
                  minute='50',
                  timezone='Asia/Bangkok')
scheduler.start()
