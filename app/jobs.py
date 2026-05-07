import requests
import logging
import os
from apscheduler.schedulers.blocking import BlockingScheduler

logging.basicConfig()
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
scheduler.start()
