from collections import defaultdict

import dateutil.parser
import arrow
from linebot.models.flex_message import ImageComponent
import requests
from flask import request, url_for, jsonify
from calendar import Calendar

from psycopg2._range import DateTimeRange

from . import linebot_bp as line
from app.auth.views import line_bot_api, handler
from datetime import datetime
from app.main import csrf, app
from app.staff.models import StaffLeaveQuota, StaffAccount
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (MessageEvent, TextMessage, TextSendMessage, BubbleContainer, BoxComponent, TextComponent,
                            FlexSendMessage, CarouselContainer, FillerComponent, ButtonComponent, URIAction,
                            MessageAction)
import pytz

from ..room_scheduler.models import RoomEvent

tz = pytz.timezone('Asia/Bangkok')

# TODO: deduplicate this
today = datetime.today()

event_photo = '1A1GBmNKpDScuoX4P6iqr9xgVKgHW1ZDZ'
calendar_photo = '1WNKyCm3GX8ASpMG2uH4V1GMArjyCWKeB'

if today.month >= 10:
    START_FISCAL_DATE = datetime(today.year, 10, 1)
    END_FISCAL_DATE = datetime(today.year + 1, 9, 30)
else:
    START_FISCAL_DATE = datetime(today.year - 1, 10, 1)
    END_FISCAL_DATE = datetime(today.year, 9, 30)


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
    if event.message.text == 'leaves':
        line_id = event.source.user_id
        user = StaffAccount.query.filter_by(line_id=line_id).first()
        if user:
            bubbles = []
            for quota in StaffLeaveQuota.query.filter_by(employment_id=user.personal_info.employment.id):
                total_leaves = user.personal_info.get_total_leaves(leave_quota_id=quota.id,
                                                                   start_date=tz.localize(START_FISCAL_DATE),
                                                                   end_date=tz.localize(END_FISCAL_DATE))
                bubbles.append(
                    BubbleContainer(
                        body=BoxComponent(
                            layout='vertical',
                            contents=[
                                TextComponent(
                                    text=u'{}'.format(quota.leave_type),
                                    weight='bold',
                                    size='xl',
                                    wrap=True
                                ),
                                FillerComponent(
                                    flex=2,
                                ),
                                TextComponent(text=u'ใช้ไป {} วัน'.format(total_leaves), wrap=True, size='md')
                            ]
                        ),
                        footer=BoxComponent(
                            layout='vertical',
                            contents=[
                                ButtonComponent(
                                    action=URIAction(
                                        label=u'Make a request',
                                        uri='https://mumtmis.herokuapp.com'
                                    )
                                ),
                            ]
                        )
                    )
                )
            line_bot_api.reply_message(
                event.reply_token,
                FlexSendMessage(alt_text='Leaves Info', contents=CarouselContainer(contents=bubbles))
            )
    if event.message.text == 'events':
        today = datetime.today().date()
        this_week = []
        for week in c.monthdatescalendar(today.year, today.month):
            if today in week:
                this_week = [d for d in week]
                break
        events = requests.get(url_for('event.fetch_global_events', _external=True))
        bubbles = []
        for evt in events.json():
            start = dateutil.parser.parse(evt.get('start'))
            # TODO: recheck if .get file_id condition
            if evt.get('file_id'):
                event_id = evt.get('file_id')
            else:
                event_id = event_photo
            if start.date() in this_week:
                bubbles.append(
                    BubbleContainer(
                        hero=ImageComponent(
                            layout='vertical',
                            url="https://drive.google.com/uc?id={}".format(event_id),
                            size='full',
                            aspect_mode='cover',
                            aspect_ratio='20:13',
                        ),
                        body=BoxComponent(
                            layout='vertical',
                            contents=[
                                TextComponent(
                                    text=u'{}'.format(evt.get('title')),
                                    weight='bold',
                                    size='xl',
                                    wrap=True
                                ),
                                TextComponent(
                                    text=u'วันที่ {} เวลา {} น.'.format(start.strftime(u'%d/%m/%Y'),
                                                                        start.strftime('%H:%M')),
                                    wrap=True
                                ),
                                TextComponent(
                                    text=u'สถานที่ {}'.format(evt.get('location') or u'ไม่ระบุ'),
                                    wrap=True
                                ),
                            ]
                        ),
                        footer=BoxComponent(
                            layout='vertical',
                            contents=[
                                ButtonComponent(
                                    action=URIAction(
                                        label=u'ลงทะเบียนกิจกรรมนี้ (Register)',
                                        uri=evt.get('registration')
                                        # uri='https://mt.mahidol.ac.th/calendar/events/'
                                    ),
                                ),
                            ]
                        )
                    )
                )
        if bubbles:
            bubbles.append(
                BubbleContainer(
                    hero=ImageComponent(
                        layout='vertical',
                        url="https://drive.google.com/uc?id={}".format(calendar_photo),
                        size='full',
                        aspect_mode='cover',
                        aspect_ratio='20:13',
                    ),
                    body=BoxComponent(
                        layout='vertical',
                        contents=[
                            ButtonComponent(
                                action=URIAction(
                                    label=u'ดูกิจกรรม (Event Detail)',
                                    uri='https://mt.mahidol.ac.th/calendar/events/'
                                ),
                            )
                        ]
                    )
                )
            )
            line_bot_api.reply_message(
                event.reply_token,
                FlexSendMessage(alt_text='Events Info', contents=CarouselContainer(contents=bubbles))
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                FlexSendMessage(alt_text='Events Info', contents=CarouselContainer(contents=[
                    BubbleContainer(
                        body=BoxComponent(
                            layout='vertical',
                            contents=[
                                TextComponent(
                                    text=u'ไม่มีกิจกรรมในสัปดาห์นี้',
                                    weight='bold',
                                    size='xl',
                                    wrap=True
                                )
                            ]
                        ),
                        footer=BoxComponent(
                            layout='vertical',
                            contents=[
                                ButtonComponent(
                                    action=URIAction(
                                        label=u'ดูปฏิทิน (Calendar)',
                                        uri='https://mt.mahidol.ac.th/calendar/events/'
                                    )
                                ),
                            ]
                        )
                    )
                ]))
            )


@line.route('/events/notification')
def notify_events():
    start = arrow.now('Asia/Bangkok')
    end = start.shift(hours=+8)
    for evt in RoomEvent.query.filter(RoomEvent.datetime.op('&&')
                                          (DateTimeRange(lower=start.datetime,
                                                         upper=end.datetime, bounds='[]'))):
        for par in evt.participants:
            if par.line_id:
                try:
                    message = 'คุณได้รับเชิญเข้าร่วม{} ({})\nห้อง {}\nเวลา {} - {}'.format(
                        evt.title,
                        evt.category,
                        evt.room.number,
                        tz.localize(evt.datetime.lower).strftime('%H:%M'),
                        tz.localize(evt.datetime.upper).strftime('%H:%M'),
                    )
                    line_bot_api.push_message(to=par.line_id,
                                              messages=TextSendMessage(text=message))
                except LineBotApiError as e:
                    return jsonify({'message': str(e)})
    return jsonify({'message': 'success'}), 200


@line.route('/rooms/notification')
def notify_room_booking():
    when = request.args.get('when', 'today')

    start = arrow.now('Asia/Bangkok')
    if when == 'tomorrow':
        start = start.shift(hours=+15)

    end = start.shift(hours=+8)
    coords = defaultdict(list)
    for evt in RoomEvent.query \
            .filter(RoomEvent.datetime.op('&&')
                        (DateTimeRange(lower=start.datetime, upper=end.datetime, bounds='[]'))) \
            .filter(RoomEvent.cancelled_at == None):
        for co in evt.room.coordinators:
            coords[co].append((evt.room.number, evt.datetime))

    for co in coords:
        if when == 'today':
            message = 'รายการจองห้องที่ท่านดูแลในวันนี้:\n'
        elif when == 'tomorrow':
            message = 'รายการจองห้องที่ท่านดูแลในวันพรุ่งนี้:\n'

        if co.line_id:
            try:
                for room_number, datetime in coords[co]:
                    message += 'ห้อง {} เวลา {} - {}\n'.format(
                    room_number,
                    tz.localize(datetime.lower).strftime('%H:%M'),
                    tz.localize(datetime.upper).strftime('%H:%M'),
                )
                line_bot_api.push_message(to=co.line_id,
                                          messages=TextSendMessage(text=message))
            except LineBotApiError as e:
                return jsonify({'message': str(e)})

    return jsonify({'message': 'success'}), 200
