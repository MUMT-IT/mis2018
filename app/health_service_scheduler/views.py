# -*- coding:utf-8 -*-
from datetime import datetime

import gspread
import os
from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_cors import cross_origin
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, FlexContainer, BubbleContainer, \
    BoxComponent, ImageComponent, MessageAction, TextComponent, ButtonComponent, URIAction, CarouselContainer, \
    ImagemapSendMessage, BaseSize, ImagemapAction, MessageImagemapAction, ImagemapArea, URIImagemapAction, \
    SeparatorComponent, FillerComponent
from oauth2client.service_account import ServiceAccountCredentials
from pandas import DataFrame
from sqlalchemy import extract

from models import *
from forms import *
from . import health_service_blueprint as hs
from app.main import csrf, app
from pytz import timezone
from flask_login import login_required, current_user
from linebot import (LineBotApi, WebhookHandler)
from ..main import db, json_keyfile

localtz = timezone('Asia/Bangkok')

LINE_MESSAGE_API_ACCESS_TOKEN_2 = os.environ.get('LINE_MESSAGE_API_ACCESS_TOKEN_2')
LINE_MESSAGE_API_CLIENT_SECRET_2 = os.environ.get('LINE_MESSAGE_API_CLIENT_SECRET_2')

line_bot_mumthealth = LineBotApi(LINE_MESSAGE_API_ACCESS_TOKEN_2)
handler_mumthealth = WebhookHandler(LINE_MESSAGE_API_CLIENT_SECRET_2)

scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']


def get_credential(json_keyfile):
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scope)
    return gspread.authorize(credentials)


@hs.route('/')
@login_required
def index():
    return render_template('health_service_scheduler/index.html')


@hs.route('/sites/add', methods=['GET', 'POST'])
@login_required
def add_site():
    form = ServiceSiteForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            site = HealthServiceSite()
            form.populate_obj(site)
            db.session.add(site)
            db.session.commit()
            flash(u'New site has been added.', 'success')
            return redirect(url_for('health_service_scheduler.get_sites'))
        else:
            for field, err in form.errors:
                flash(u'{}:{}'.format(field, err), 'danger')
    return render_template('health_service_scheduler/site_form.html', form=form)


@hs.route('/sites')
@login_required
def get_sites():
    sites = HealthServiceSite.query.all()
    return render_template('health_service_scheduler/sites.html', sites=sites)


@hs.route('/services')
@login_required
def get_services():
    services = HealthServiceService.query.all()
    return render_template('health_service_scheduler/services.html', services=services)


@hs.route('/services/add', methods=['GET', 'POST'])
@login_required
def add_service():
    form = ServiceForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            service = HealthServiceService()
            form.populate_obj(service)
            db.session.add(service)
            db.session.commit()
            flash(u'New service has been added.', 'success')
            return redirect(url_for('health_service_scheduler.get_services'))
        else:
            for field, err in form.errors:
                flash(u'{}:{}'.format(field, err), 'danger')
    return render_template('health_service_scheduler/service_form.html', form=form)


@hs.route('/slots/add', methods=['GET', 'POST'])
@login_required
def add_slot():
    form = ServiceSlotForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            slot = HealthServiceTimeSlot()
            form.populate_obj(slot)
            start = localtz.localize(slot.start)
            end = localtz.localize(slot.end)
            if start >= end:
                flash(u'ช่วงเวลาไม่ถูกต้อง กรุณาเลือกช่วงเวลาใหม่', 'danger')
            else:
                slot.start = start
                slot.end = end
                slot.created_at = datetime.now(localtz).astimezone(localtz)
                slot.created_by = current_user
                db.session.add(slot)
                db.session.commit()
                flash(u'New time slot has been added.', 'success')
                return redirect(url_for('health_service_scheduler.show_slots'))
        else:
            for field, err in form.errors:
                flash(u'{}:{}'.format(field, err), 'danger')
    return render_template('health_service_scheduler/slot_form.html', form=form)


@hs.route('/slots')
@login_required
def show_slots():
    mode = request.args.get('mode', 'agendaWeek')
    return render_template('health_service_scheduler/slots.html', mode=mode)


@hs.route('/bookings')
@login_required
def show_bookings():
    services = HealthServiceService.query.all()
    return render_template('health_service_scheduler/bookings.html', services=services)


@hs.route('/services/<int:service_id>/bookings')
@login_required
def show_bookings_by_service(service_id):
    bookings = HealthServiceBooking.query.all()
    return render_template('health_service_scheduler/service_bookings.html',
                           bookings=[booking for booking in bookings
                                     if booking.slot.service.id == service_id])

@hs.route('/bookings/<int:booking_id>')
@login_required
def show_booking_detail(booking_id):
    booking = HealthServiceBooking.query.get(booking_id)
    return render_template('health_service_scheduler/booking_detail.html',
                           booking=booking)


@hs.route('/bookings/<int:booking_id>/confirm')
@login_required
def confirm_booking(booking_id):
    booking = HealthServiceBooking.query.get(booking_id)
    booking.confirmed_at = datetime.now(localtz).astimezone(localtz)
    db.session.add(booking)
    db.session.commit()
    return redirect(url_for('health_service_scheduler.show_bookings'))


@hs.route('/api/calendar/slots')
@login_required
def get_slots_calendar_api():
    # only query events of the current year to reduce load time
    slots = HealthServiceTimeSlot.query\
        .filter(extract('year', HealthServiceTimeSlot.start) == datetime.today().year)
    slot_data = []
    for evt in slots:
        if not evt.cancelled_at:
            slot_data.append({
                'id': evt.id,
                'start': evt.start.astimezone(localtz).isoformat(),
                'end': evt.end.astimezone(localtz).isoformat(),
                'title': u'{} ({}) by {}'.format(evt.service.name,evt.quota, evt.created_by.personal_info.th_firstname),
                'quota': evt.quota,
                'resourceId': evt.site.id,
                'site': evt.site.name
            })
    return jsonify(slot_data)


@hs.route('/api/calendar/sites')
def get_sites_calendar_api():
    sites = HealthServiceSite.query.all()
    site_data = []
    for s in sites:
        site_data.append({
            'id': s.id,
            'title': s.name,
        })
    return jsonify(site_data)


@hs.route('/api/bookings/add', methods=['POST'])
@csrf.exempt
@cross_origin(support_credentials=True)
def add_booking():
    data = request.get_json()
    print(data)
    slot = HealthServiceTimeSlot.query.get(int(data.get('slotId', 0)))
    # user = HealthServiceAppUser.query.filter_by(line_id=data.get('lineId', 'abcd')).first()
    if slot and slot.is_available:
        booking = HealthServiceBooking()
        booking.slot = slot
        booking.user = HealthServiceAppUser.query.first()
        booking.created_at = datetime.now(localtz).astimezone(localtz)
        '''
        if not user:
            new_user = HealthServiceAppUser(line_id=data['lineId'])
            booking.user = new_user
        else:
            booking.user = user
        '''
        db.session.add(booking)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'failed'})


@hs.route('/message/callback', methods=['POST'])
@csrf.exempt
def line_message_callback():
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler_mumthealth.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        # abort(400)

    return 'OK', 200


@handler_mumthealth.add(MessageEvent, message=TextMessage)
def handle_message(event):
    if event.message.text == 'packages':
        gc = get_credential(json_keyfile)
        sheetkey = '15uhQm6tkd69dEthC-Vc9tb-Orsjnywlw85GOBsZgxmY'
        sh = gc.open_by_key(sheetkey)
        ws = sh.worksheet('packages')
        df = DataFrame(ws.get_all_records())
        bubbles = []
        for idx, row in df.iterrows():
            bubbles.append(
                BubbleContainer(
                    hero=ImageComponent(
                        layout='vertical',
                        url="https://drive.google.com/uc?id={}".format(row['cover']),
                        size='full',
                        aspect_mode='cover',
                        aspect_ratio='20:13',
                        action=MessageAction(
                            label='Test List',
                            text='Tests will be shown here in the future.'
                        )
                    ),
                    body=BoxComponent(
                        layout='vertical',
                        contents=[
                            TextComponent(
                                text=row['title'],
                                weight='bold',
                                size='xl',
                                wrap=True
                            ),
                            TextComponent( text=row['description'], wrap=True, color='#cfcecc')
                    ]
                    ),
                    footer=BoxComponent(
                        layout='vertical',
                        contents=[
                            ButtonComponent(
                                MessageAction(
                                    label='รายการตรวจ',
                                    text=row['code']
                                )
                            )
                        ]
                    )
                )
            )
        line_bot_mumthealth.reply_message(event.reply_token, FlexSendMessage(
            alt_text='Health Packages', contents=CarouselContainer(contents=bubbles)))
    elif event.message.text == 'health-services':
        imageUrl = '1Z63x6wA08ATfWr1SgBCkMhiMbD3h2lhP'
        line_bot_mumthealth.reply_message(
            event.reply_token,
            ImagemapSendMessage(
                base_url='https://drive.google.com/uc?id={}&_ignored='.format(imageUrl),
                alt_text='Health Services',
                base_size=BaseSize(width=1040, height=1040),
                actions=[
                    MessageImagemapAction(
                        text='packages', area=ImagemapArea(x=122, y=123, width=381, height=305)),
                    URIImagemapAction(
                        link_uri='https://liff.line.me/1655424321-ovYzaqOz',
                        area=ImagemapArea(x=124, y=430, width=377, height=301)
                    ),
                    MessageImagemapAction(
                        text='Available soon..', area=ImagemapArea(x=126, y=734, width=374, height=302)),
                    MessageImagemapAction(
                        text='Available soon..', area=ImagemapArea(x=507, y=125, width=435, height=301)),
                    MessageImagemapAction(
                        text='Available soon..', area=ImagemapArea(x=508, y=431, width=434, height=299)),
                    ]
            )
        )
    elif event.message.text.startswith('pkg'):
        gc = get_credential(json_keyfile)
        sheetkey = '15uhQm6tkd69dEthC-Vc9tb-Orsjnywlw85GOBsZgxmY'
        sh = gc.open_by_key(sheetkey)
        ws = sh.worksheet('tests')
        df = DataFrame(ws.get_all_records())
        bubbles = []
        total = 0
        for idx, row in df.iterrows():
            if row['package'] == event.message.text:
                total += row['price']
                bubbles.append(
                    BubbleContainer(
                        body=BoxComponent(
                            layout='vertical',
                            contents=[
                                TextComponent(
                                    text=row['test'],
                                    weight='bold',
                                    size='xl',
                                    wrap=True,
                                    align='center',
                                ),
                                TextComponent(text=row['description'], wrap=True, gravity='center'),
                                FillerComponent(
                                    flex=2
                                ),
                                TextComponent(text=u'{} บาท'.format(row['price']),
                                              wrap=True,
                                              weight='bold',
                                              size='xl',
                                              gravity='bottom',
                                              color='#4287f5',
                                              align='center')
                            ]
                        )
                    )
                )
        if len(bubbles) > 0:
            bubbles.append(BubbleContainer(
                body=BoxComponent(
                    layout='vertical',
                    contents=[
                        FillerComponent(
                            flex=2,
                        ),
                        TextComponent(
                            text='รวม {} บาท'.format(total),
                            weight='bold',
                            size='xl',
                            gravity='center',
                            align='center',
                            color='#4287f5'
                        )
                    ]
                ),
                footer=BoxComponent(
                    layout='vertical',
                    contents=[
                        ButtonComponent(
                            action=URIAction(
                                label=u'นัดหมายเพื่อรับบริการ',
                                uri='https://liff.line.me/1655713713-L9yW3XWK'
                            )
                        ),
                        ButtonComponent(
                            action=MessageAction(
                                label=u'ข้อมูลเพิ่มเติม',
                                text='Here you go!'
                            )
                        )
                    ]
                )
            ))
            line_bot_mumthealth.reply_message(event.reply_token, FlexSendMessage(
                alt_text='Health Packages', contents=CarouselContainer(contents=bubbles)))
    else:
        line_bot_mumthealth.reply_message(
            event.reply_token,
            TextSendMessage(text='Sorry, this feature will be available soon.'.format(event.message.text))
        )


@hs.route('/test')
def test():
    return request.url