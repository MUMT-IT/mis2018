from collections import defaultdict
import os

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


def _mask_line_id(line_id):
    if not line_id:
        return None
    if len(line_id) <= 6:
        return '***'
    return f'{line_id[:3]}***{line_id[-3:]}'


def _is_valid_scheduler_request():
    configured_token = os.environ.get('JOB_TOKEN')
    if not configured_token:
        return True
    request_token = request.values.get('job_token')
    return bool(request_token and request_token == configured_token)


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


# External scheduler endpoint: called by background jobs and should not be
# protected with @login_required.
@line.route('/events/notification')
def notify_events():
    if not _is_valid_scheduler_request():
        return jsonify({'message': 'forbidden'}), 403
    app.logger.info('line_notify_events_start')
    try:
        start = arrow.now('Asia/Bangkok')
        end = start.shift(hours=+8)
        events = RoomEvent.query \
            .filter(RoomEvent.datetime.op('&&')(DateTimeRange(lower=start.datetime, upper=end.datetime, bounds='[]'))) \
            .filter(RoomEvent.cancelled_at == None).all()
        app.logger.info('line_notify_events_checkpoint events_in_window=%s', len(events))

        sent_count = 0
        failed_count = 0
        for evt in events:
            for par in evt.participants:
                if not par.line_id:
                    continue
                try:
                    message = 'คุณได้รับเชิญเข้าร่วม{} ({})\nห้อง {}\nเวลา {} - {}'.format(
                        evt.title,
                        evt.category,
                        evt.room.number,
                        tz.localize(evt.datetime.lower).strftime('%H:%M'),
                        tz.localize(evt.datetime.upper).strftime('%H:%M'),
                    )
                    app.logger.info(
                        'line_notify_events_push_start event_id=%s line_id=%s',
                        evt.id,
                        _mask_line_id(par.line_id),
                    )
                    line_bot_api.push_message(to=par.line_id, messages=TextSendMessage(text=message))
                    sent_count += 1
                except LineBotApiError:
                    failed_count += 1
                    app.logger.exception(
                        'line_notify_events_push_failed event_id=%s line_id=%s',
                        evt.id,
                        _mask_line_id(par.line_id),
                    )

        app.logger.info(
            'line_notify_events_end sent_count=%s failed_count=%s',
            sent_count,
            failed_count,
        )
        if failed_count:
            return jsonify({'message': 'partial_failure', 'sent': sent_count, 'failed': failed_count}), 500
        return jsonify({'message': 'success', 'sent': sent_count}), 200
    except Exception:
        app.logger.exception('line_notify_events_unhandled_error')
        return jsonify({'message': 'internal_error'}), 500


# External scheduler endpoint: called by background jobs and should not be
# protected with @login_required.
@line.route('/rooms/notification')
def notify_room_booking():
    if not _is_valid_scheduler_request():
        return jsonify({'message': 'forbidden'}), 403
    when = request.args.get('when', 'today')
    app.logger.info('line_notify_rooms_start when=%s', when)

    try:
        start = arrow.now('Asia/Bangkok')
        if when == 'tomorrow':
            start = start.shift(hours=+15)
        end = start.shift(hours=+8)
        coords = defaultdict(list)
        events = RoomEvent.query \
            .filter(RoomEvent.datetime.op('&&')
                        (DateTimeRange(lower=start.datetime, upper=end.datetime, bounds='[]'))) \
            .filter(RoomEvent.cancelled_at == None).all()
        app.logger.info('line_notify_rooms_checkpoint events_in_window=%s', len(events))

        for evt in events:
            for co in evt.room.coordinators:
                coords[co].append((evt.room.number, evt.datetime,
                                   evt.creator.personal_info.fullname, evt.comment))

        sent_count = 0
        failed_count = 0
        for co in coords:
            if when == 'today':
                message = 'รายการจองห้องที่ท่านดูแลในวันนี้:\n'
            elif when == 'tomorrow':
                message = 'รายการจองห้องที่ท่านดูแลในวันพรุ่งนี้:\n'
            else:
                message = f'รายการจองห้องที่ท่านดูแล ({when}):\n'
            for room_number, datetime, creator, comment in coords[co]:
                start_time = tz.localize(datetime.lower).strftime("%H:%M")
                end_time = tz.localize(datetime.upper).strftime('%H:%M')
                message += f'ห้อง {room_number} เวลา {start_time} - {end_time} ผู้จอง {creator} ' + (f'({comment})' if comment else '') + '\n'
            if co.line_id:
                try:
                    app.logger.info('line_notify_rooms_push_start line_id=%s', _mask_line_id(co.line_id))
                    line_bot_api.push_message(to=co.line_id, messages=TextSendMessage(text=message))
                    sent_count += 1
                except LineBotApiError:
                    failed_count += 1
                    app.logger.exception('line_notify_rooms_push_failed line_id=%s', _mask_line_id(co.line_id))

        app.logger.info(
            'line_notify_rooms_end when=%s recipients=%s sent_count=%s failed_count=%s',
            when,
            len(coords),
            sent_count,
            failed_count,
        )
        if failed_count:
            return jsonify({'message': 'partial_failure', 'sent': sent_count, 'failed': failed_count}), 500
        return jsonify({'message': 'success', 'sent': sent_count}), 200
    except Exception:
        app.logger.exception('line_notify_rooms_unhandled_error when=%s', when)
        return jsonify({'message': 'internal_error'}), 500
