import requests
import logging
import os
from apscheduler.schedulers.blocking import BlockingScheduler

logging.basicConfig()
logger = logging.getLogger(__name__)
BASE_URL = os.environ.get('JOBS_BASE_URL', 'https://mumtmis.herokuapp.com')
JOB_TOKEN = os.environ.get('JOB_TOKEN')


def send_event_notification():
    events = requests.get('https://mumtmis.herokuapp.com/linebot/events/notification')


def send_room_notification_today():
    events = requests.get('https://mumtmis.herokuapp.com/linebot/rooms/notification?when=today')


def send_room_notification_tomorrow():
    events = requests.get('https://mumtmis.herokuapp.com/linebot/rooms/notification?when=tomorrow')


def send_complaint_summary_report():
    params = {'send': 'true'}
    if JOB_TOKEN:
        params['job_token'] = JOB_TOKEN
    requests.get(
        f'{BASE_URL}/complaint-tracker/admin/email-unfinished-summary',
        params=params,
        timeout=60,
    )


def send_line_reminder_no_status_today():
    params = {'send': 'true'}
    if JOB_TOKEN:
        params['job_token'] = JOB_TOKEN
    response = requests.get(
        f'{BASE_URL}/complaint-tracker/admin/line-remind-no-status-today',
        params=params,
        timeout=60,
    )
    if response.status_code == 404:
        logger.info('No unattended complaint jobs for Line reminder.')
    elif response.status_code >= 400:
        logger.warning(
            'Line reminder request failed with status %s: %s',
            response.status_code,
            response.text[:500],
        )


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
scheduler.start()
