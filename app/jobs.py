import os
import requests
import logging
from apscheduler.schedulers.blocking import BlockingScheduler

logging.basicConfig()


def send_event_notification():
    events = requests.get('https://mumtmis.herokuapp.com/line/events/notification')


scheduler = BlockingScheduler()
scheduler.add_job(send_event_notification,
                  'cron', day_of_week='mon-fri',
                  hour='10',
                  minute='45',
                  timezone='Asia/Bangkok')
scheduler.start()
