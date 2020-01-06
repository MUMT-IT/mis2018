# -*- coding: utf-8 -*-
import os
import requests
from flask import request, url_for, jsonify
from calendar import Calendar
from . import linebot_bp as line
from app.auth.views import line_bot_api, handler
from datetime import datetime
from app.main import csrf, app
from linebot.exceptions import InvalidSignatureError
from linebot.models import (MessageEvent, TextMessage, TextSendMessage)


@line.route('/message/callback', methods=['POST'])
@csrf.exempt
def line_message_callback():
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        # abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    c = Calendar()
    if event.message.text == 'events':
        today = datetime.today().date()
        this_week = []
        for week in c.monthdatescalendar(today.year, today.month):
            if today in week:
                this_week = [d.strftime('%Y-%m-%d') for d in week]
                break
        events = requests.get(url_for('event.fetch_global_events', _external=True))
        all_events = []
        for evt in events.json():
            if evt.get('start') in this_week:
                all_events.append(u'วันที่:{}\nกิจกรรม:{}\nสถานที่:{}' \
                                  .format(evt.get('start'),
                                          evt.get('title', ''),
                                          evt.get('location', ''),
                                          ))
        if all_events:
            all_events.append(u'ดูปฏิทินที่ {}'.format(url_for('event.list_global_events', _external=True)))
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=u'\n'.join(all_events)))
        else:
            text = u'ไม่มีกิจกรรมในสัปดาห์นี้\nดูปฏิทินที่ {}' \
                .format(url_for('event.list_global_events', _external=True))
            line_bot_api.reply_message(event.reply_token,
                                       TextSendMessage(text=text))


@line.route('/events/notification')
def notify_events():
    c = Calendar()
    today = datetime.today().date().strftime('%Y-%m-%d')
    events = requests.get('https://mumtmis.herokuapp.com/events/api/global')
    all_events = []
    for evt in events.json():
        if evt.get('start') == today:
            all_events.append(u'วันที่:{}\nกิจกรรม:{}\nสถานที่:{}'
                              .format(evt.get('start'),
                                      evt.get('title', ''),
                                      evt.get('location', ''),
                                      ))
    if all_events:
        notifications = '\n'.join(all_events)
    else:
        notifications = u'ไม่มีกิจกรรมในวันนี้'
    if os.environ.get('FLASK_ENV') == 'development':
        try:
            line_bot_api.push_message(to='U6d57844061b29c8f2a46a5ff841b28d8',
                                      messages=TextSendMessage(text=notifications))
        except:
            return jsonify({'message': 'failed to push a message.'}), 500
    else:
        try:
            line_bot_api.broadcast(
                messages=TextSendMessage(text=notifications))
            '''
            line_bot_api.push_message(to='U6d57844061b29c8f2a46a5ff841b28d8',
                                      messages=TextSendMessage(text=notifications))
            '''
        except:
            return jsonify({'message': 'failed to broadcast a message.'}), 500

    return jsonify({'message': 'success'}), 200
