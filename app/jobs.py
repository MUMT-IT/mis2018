import requests
import logging
from apscheduler.schedulers.blocking import BlockingScheduler

logging.basicConfig()


def send_event_notification():
    events = requests.get('https://mumtmis.herokuapp.com/linebot/events/notification')


def send_room_notification_today():
    events = requests.get('https://mumtmis.herokuapp.com/linebot/rooms/notification?when=today')


def send_room_notification_tomorrow():
    events = requests.get('https://mumtmis.herokuapp.com/linebot/rooms/notification?when=tomorrow')


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
                  hour='17',
                  minute='00',
                  timezone='Asia/Bangkok')
scheduler.start()
