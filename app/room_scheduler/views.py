# -*- coding: utf8 -*-

import requests
import os
import pytz
from datetime import datetime
from dateutil import parser
from flask import render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from ..main import db
from . import roombp as room
from .models import RoomResource, RoomEvent, EventCategory
from ..models import IOCode

bangkok = pytz.timezone('Asia/Bangkok')

if os.environ.get('FLASK_ENV') == 'production':
    CALENDAR_ID = '9hur49up24fdcbicdbggvpu77k@group.calendar.google.com'
else:
    CALENDAR_ID = 'rsrlpk6sbr0ntbq9ukd6vkpkbc@group.calendar.google.com'

service_account_info = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
credentials = Credentials.from_service_account_info(service_account_info)


@room.route('/api/iocodes')
def get_iocodes():
    codes = []
    for code in IOCode.query.all():
        codes.append(code.to_dict())

    return jsonify(codes)


@room.route('/api/rooms')
def get_rooms():
    rooms = RoomResource.query.all()
    resources = []
    for rm in rooms:
        resources.append({
            'id': rm.number,
            'location': rm.location,
            'title': rm.number,
            'occupancy': rm.occupancy,
            'businessHours': {
                'start': rm.business_hour_start.strftime('%H:%M'),
                'end': rm.business_hour_end.strftime('%H:%M'),
            }
        })
    return jsonify(resources)


@room.route('/api/events')
def get_events():
    tz = pytz.timezone('Asia/Bangkok')
    all_events = []
    for event in RoomEvent.query.all():
        # The event object is a dict object with a 'summary' key.
        start = event.start
        end = event.end
        room = event.room
        if event.approved:
            text_color = '#ffffff'
            bg_color = '#2b8c36'
            border_color = '#ffffff'
        else:
            text_color = '#000000'
            bg_color = '#f0f0f5'
            border_color = '#ff4d4d'
        evt = {
            'location': room.number,
            'title': u'(Rm{}) {}'.format(room.number, event.title),
            'description': event.note,
            'start': start.astimezone(bangkok).isoformat(),
            'end': end.astimezone(bangkok).isoformat(),
            'resourceId': room.number,
            'status': event.approved,
            'borderColor': border_color,
            'backgroundColor': bg_color,
            'textColor': text_color,
            'id': event.id,
        }
        all_events.append(evt)
    return jsonify(all_events)


@room.route('/')
def index():
    return render_template('scheduler/room_main.html')


@room.route('/events/<list_type>')
def event_list(list_type='timelineDay'):
    return render_template('scheduler/event_list.html', list_type=list_type)


@room.route('/events/new')
def new_event():
    return render_template('scheduler/new_event.html')


@room.route('/events/<int:event_id>', methods=['POST', 'GET'])
def show_event_detail(event_id=None):
    tz = pytz.timezone('Asia/Bangkok')
    if event_id:
        event = RoomEvent.query.get(event_id)
        if event:
            event.start = event.start.astimezone(tz)
            event.end = event.end.astimezone(tz)
            return render_template(
                'scheduler/event_detail.html', event=event)
    else:
        return 'No event ID specified.'


@room.route('/events/cancel/<int:event_id>')
def cancel(event_id=None):
    if not event_id:
        return redirect(url_for('room.index'))

    tz = pytz.timezone('Asia/Bangkok')
    cancelled_datetime = tz.localize(datetime.utcnow(), is_dst=None)
    event = RoomEvent.query.get(event_id)
    event.cancelled_at = cancelled_datetime
    event.cancelled_by = 1
    db.session.add(event)
    db.session.commit()

    scoped_credentials = credentials.with_scopes([
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events'
    ])

    calendar_service = build('calendar', 'v3', credentials=scoped_credentials)
    event_ = calendar_service.events().patch(
        calendarId=event.google_calendar_id,
        eventId=event.google_event_id, body={'status': 'cancelled'}).execute()

    if event_:
        flash('Reservation ID={} has been updated.'.format(event_.get('id')))

    return redirect(url_for('room.index'))


@room.route('/events/approve/<int:event_id>')
def approve_event(event_id):
    event = RoomEvent.query.get(event_id)
    event.approved = True
    db.session.add(event)
    db.session.commit()
    flash(u'อนุมัติการจองห้องเรียบร้อยแล้ว', 'success')
    return redirect(url_for('room.index'))


@room.route('/events/edit/<int:event_id>', methods=['POST', 'GET'])
def edit_detail(event_id):
    tz = pytz.timezone('Asia/Bangkok')
    if request.method == 'POST':
        event_id = request.form.get('event_id')
        category_id = request.form.get('category_id')
        event = RoomEvent.query.get(int(event_id))
        title = request.form.get('title', '')
        startdt = request.form.get('startdate')
        enddt = request.form.get('enddate')
        iocode_id = request.form.get('iocode')
        desc = request.form.get('request', '')
        occupancy = request.form.get('occupancy', 0)
        refreshment = request.form.get('refreshment', 0)
        note = request.form.get('note', '')
        extra_items = request.form.get('extra_items', '')
        if extra_items:
            extra_items = extra_items.split('|')[:-1]

        if iocode_id:
            iocode_id = int(iocode_id)

        event.category_id = int(category_id)
        if title:
            event.title = title
        if startdt:
            startdatetime = parser.isoparse(startdt)
            startdatetime = startdatetime.astimezone(bangkok)
        else:
            startdatetime = None
        if enddt:
            enddatetime = parser.isoparse(enddt)
            enddatetime = enddatetime.astimezone(bangkok)
        else:
            enddatetime = None
        event.start = startdatetime
        event.end = enddatetime
        event.occupancy = occupancy
        event.refreshment = int(refreshment)
        event.iocode_id = iocode_id
        event.request = desc
        event.extra_items = extra_items
        event.note = note
        event.updated_at = tz.localize(datetime.utcnow())
        db.session.add(event)
        db.session.commit()

        flash('Reservation has been updated.', 'success')
        return redirect(url_for('room.index'))

    if event_id:
        event = RoomEvent.query.get(event_id)
        categories = EventCategory.query.all()
        if event:
            event.start = event.start.astimezone(tz)
            event.end = event.end.astimezone(tz)
            event.extra_items = event.extra_items.split('|') if event.extra_items else []
            return render_template('scheduler/event_edit.html',
                                   iocode=event.iocode.to_dict(),
                                   event=event, categories=categories)
    else:
        return 'No room ID specified.'


@room.route('/list', methods=['POST', 'GET'])
def room_list():
    if request.method == 'GET':
        rooms = RoomResource.query.all()
    else:
        room_number = request.form.get('room_number', None)
        users = request.form.get('users', 0)
        if room_number:
            rooms = RoomResource.query.filter(RoomResource.number.like('%{}%'.format(room_number)))
        else:
            rooms = []
        if request.headers.get('HX-Request') == 'true':
            return render_template('scheduler/partials/room_list.html', rooms=rooms)

    return render_template('scheduler/room_list.html', rooms=rooms)


@room.route('/reserve/<room_id>', methods=['GET', 'POST'])
def room_reserve(room_id):
    if request.method == 'POST':
        category_id = request.form.get('category_id', None)
        startdt = request.form.get('startdate', None)
        enddt = request.form.get('enddate', None)
        title = request.form.get('title', ''),
        participants = request.form.get('participants', 0)

        room = RoomResource.query.get(room_id)
        tz = pytz.timezone('Asia/Bangkok')
        if startdt:
            startdatetime = parser.isoparse(startdt)
            startdatetime = startdatetime.astimezone(bangkok)
        else:
            startdatetime = None
        if enddt:
            enddatetime = parser.isoparse(enddt)
            enddatetime = enddatetime.astimezone(bangkok)
        else:
            enddatetime = None

        if room_id and startdatetime and enddatetime:
            approval_needed = True if room.availability_id == 3 else False

            new_event = RoomEvent(room_id=room.id,
                                  start=startdatetime,
                                  end=enddatetime,
                                  created_at=tz.localize(datetime.utcnow()),
                                  title=title,
                                  occupancy=int(participants),
                                  approved=approval_needed,
                                  category_id=int(category_id))

            db.session.add(new_event)
            db.session.commit()
            flash('Reservation has been made.')
            return redirect(url_for('room.index'))

    if room_id:
        room = RoomResource.query.get(room_id)
        categories = EventCategory.query.all()
        if room:
            return render_template('scheduler/reserve_form.html',
                                   room=room, categories=categories)
