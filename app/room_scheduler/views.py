# -*- coding: utf8 -*-

import requests
import os
import pytz
from datetime import datetime
from flask import render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from ..main import db
from . import roombp as room
from .models import RoomResource, RoomEvent, EventCategory
from ..models import IOCode

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
        codes.append({
            'id': code.id,
            'costCenter': u'{}'.format(code.cost_center.id),
            'name': u'{}'.format(code.name),
            'org': u'{}'.format(code.org.name),
            'mission': u'{}'.format(code.mission.name)
        })

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
    # credentials, project_id = google.auth.default()
    scoped_credentials = credentials.with_scopes([
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events'
    ])
    calendar_service = build('calendar', 'v3', credentials=scoped_credentials)
    request = calendar_service.events().list(
        calendarId='{}'.format(CALENDAR_ID))
    # Loop until all pages have been processed.
    all_events = []
    while request != None:
        # Get the next page.
        response = request.execute()
        # returns a list of item objects (events).
        for event in response.get('items', []):
            # The event object is a dict object with a 'summary' key.
            start = event.get('start', None)
            end = event.get('end', None)
            extended_properties = event.get('extendedProperties', {}).get('private', {})
            room_no = extended_properties.get('room_no', '')
            status = event.get('status')
            if status == 'confirmed':
                text_color = '#ffffff'
                bg_color = '#2b8c36'
                border_color = '#ffffff'
            else:
                text_color = '#000000'
                bg_color = '#f0f0f5'
                border_color = '#ff4d4d'
            evt = {
                'location': event.get('location', None),
                'title': u'(Rm{}) {}'.format(room_no, event.get('summary', 'NO SUMMARY')),
                'description': event.get('description', ''),
                'start': start['dateTime'],
                'end': end['dateTime'],
                'resourceId': room_no,
                'status': status,
                'borderColor': border_color,
                'backgroundColor': bg_color,
                'textColor': text_color,
                'id': extended_properties.get('event_id', None),
            }
            all_events.append(evt)
        # Get the next request object by passing the previous request object to
        # the list_next method.
        request = calendar_service.events().list_next(request, response)
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


@room.route('/events/edit/<int:event_id>', methods=['POST', 'GET'])
def edit_detail(event_id=None):
    tz = pytz.timezone('Asia/Bangkok')
    if request.method == 'POST':
        event_id = request.form.get('event_id')
        category_id = request.form.get('category_id')
        event = RoomEvent.query.get(int(event_id))
        title = request.form.get('title', '')
        startdate = request.form.get('startdate')
        enddate = request.form.get('enddate')
        starttime = request.form.get('starttime')
        endtime = request.form.get('endtime')
        desc = request.form.get('request', '')
        occupancy = request.form.get('occupancy', 0)
        refreshment = request.form.get('refreshment', 0)
        approved = request.form.get('approved')
        note = request.form.get('note', '')
        if startdate and starttime:
            startdatetime = datetime.strptime(
                '{} {}'.format(startdate, starttime), '%Y-%m-%d %H:%M:%S')
            startdatetime = tz.localize(startdatetime, is_dst=None)
        else:
            startdatetime = None
        if enddate and endtime:
            enddatetime = datetime.strptime(
                '{} {}'.format(enddate, endtime), '%Y-%m-%d %H:%M:%S')
            enddatetime = tz.localize(enddatetime, is_dst=None)
        else:
            enddatetime = None

        event.category_id = int(category_id)
        if title:
            event.title = title
        event.start = startdatetime
        event.end = enddatetime
        event.occupancy = occupancy
        event.refreshment = refreshment
        event.note = note
        event.updated_at=tz.localize(datetime.utcnow())
        event.approved = True if approved=='yes' else False
        db.session.add(event)
        db.session.commit()

        status = 'confirmed' if event.approved else 'tentative'

        update_event = {
            'summary': title if title else event.title,
            'description': desc,
            'status': status,
            'start': {
                'dateTime': startdatetime.isoformat(),
                'timeZone': 'Asia/Bangkok',
            },
            'end': {
                'dateTime': enddatetime.isoformat(),
                'timeZone': 'Asia/Bangkok',
            },
            'extendedProperties': {
                'private': {
                    'event_id': event.id,
                    'room_no': event.room.number,
                    'iocode': event.iocode_id,
                    'occupancy': occupancy,
                    'extra_items': event.extra_items,
                    'approved': approved,
                    'refreshment': refreshment,
                }
            }
        }
        # credentials, project_id = google.auth.default()
        scoped_credentials = credentials.with_scopes([
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events'
        ])
        calendar_service = build('calendar', 'v3', credentials=scoped_credentials)
        event_ = calendar_service.events().patch(
            calendarId=event.google_calendar_id,
            eventId=event.google_event_id, body=update_event).execute()
        if event_:
            flash('Reservation ID={} has been updated.'.format(event_.get('id')))

        return redirect(url_for('room.index'))

    if event_id:
        event = RoomEvent.query.get(event_id)
        categories = EventCategory.query.all()
        if event:
            event.start = event.start.astimezone(tz)
            event.end = event.end.astimezone(tz)
            return render_template('scheduler/event_edit.html',
                        event=event, categories=categories)
    else:
        return 'No room ID specified.'


@room.route('/list', methods=['POST', 'GET'])
def room_list():
    if request.method=='GET':
        rooms = RoomResource.query.all()
    else:
        room_number = request.form.get('room_number', None)
        users = request.form.get('users', 0)
        if room_number:
            rooms = RoomResource.query.filter_by(number=room_number)
        elif users > 0:
            rooms = RoomResource.query.filter(RoomResource.occupancy>=users)
        else:
            rooms = []

    return render_template('scheduler/room_list.html', rooms=rooms)


@room.route('/reserve/<room_id>', methods=['GET', 'POST'])
def room_reserve(room_id):
    if request.method=='POST':
        room_no = request.form.get('number', None)
        location = request.form.get('location', None)
        category_id = request.form.get('category_id', None)
        desc = request.form.get('desc', None)
        startdate = request.form.get('startdate', None)
        starttime = request.form.get('starttime', None)
        enddate = request.form.get('enddate', None)
        endtime = request.form.get('endtime', None)
        title = request.form.get('title', ''),
        iocode_id = request.form.get('iocode', None)
        food = request.form.get('food', 0)
        participants = request.form.get('participants', 0)
        extra_items = request.form.get('extra_items', '')
        if extra_items:
            extra_items = extra_items.split('|')[:-1]

        room = RoomResource.query.get(room_id)
        iocode = IOCode.query.get(iocode_id)

        tz = pytz.timezone('Asia/Bangkok')
        if startdate and starttime:
            startdatetime = datetime.strptime(
                '{} {}'.format(startdate, starttime), '%Y-%m-%d %H:%M')
            startdatetime = tz.localize(startdatetime, is_dst=None)
        else:
            startdatetime = None
        if enddate and endtime:
            enddatetime = datetime.strptime(
                '{} {}'.format(enddate, endtime), '%Y-%m-%d %H:%M')
            enddatetime = tz.localize(enddatetime, is_dst=None)
        else:
            enddatetime = None

        if iocode and room and startdate \
                and starttime and enddate and endtime:
            approval_needed = True if room.availability_id==3 else False

            new_event = RoomEvent(room_id=room.id, iocode_id=iocode.id,
                                  start=startdatetime, end=enddatetime,
                                  created_at=tz.localize(datetime.utcnow()),
                                  title=title, extra_items=extra_items,
                                  request=desc, refreshment=int(food),
                                  occupancy=int(participants),
                                  approved=approval_needed,
                                  category_id=int(category_id),
                                  )

            db.session.add(new_event)
            db.session.commit()

            if startdatetime and enddatetime:
                timedelta = enddatetime - startdatetime
                if timedelta.days < 0 or timedelta.seconds == 0:
                    flash('Date or time is invalid.')
                else:
                    event = {
                        'summary': title,
                        'location': room_no,
                        'sendUpdates': 'all',
                        'status': 'tentative',
                        'description': desc,
                        'start': {
                            'dateTime': startdatetime.isoformat(),
                            'timeZone': 'Asia/Bangkok',
                        },
                        'end': {
                            'dateTime': enddatetime.isoformat(),
                            'timeZone': 'Asia/Bangkok',
                        },
                        'extendedProperties': {
                            'private': {
                                'event_id': new_event.id,
                                'room_no': room_no,
                                'iocode': new_event.iocode_id,
                                'occupancy': new_event.occupancy,
                                'extra_items': new_event.extra_items,
                                'approved': new_event.approved,
                                'refreshment': new_event.refreshment,
                            }
                        }
                    }
                    # credentials, project_id = google.auth.default()
                    scoped_credentials = credentials.with_scopes([
                        'https://www.googleapis.com/auth/calendar',
                        'https://www.googleapis.com/auth/calendar.events'
                    ])
                    calendar_service = build('calendar', 'v3', credentials=scoped_credentials)
                    event = calendar_service.events().insert(
                        calendarId=CALENDAR_ID,
                        body=event).execute()
                    if event:
                        new_event.google_event_id = event.get('id')
                        new_event.google_calendar_id = CALENDAR_ID
                        db.session.add(new_event)
                        db.session.commit()
                        flash('Reservation has been made. {}'.format(event.get('id')))
                    return redirect(url_for('room.index'))

    if room_id:
        room = RoomResource.query.get(room_id)
        categories = EventCategory.query.all()
        if room:
            timeslots = []
            for i in range(8,19):
                for j in [0, 30]:
                    timeslots.append('{:02}:{:02}'.format(i,j))
            return render_template('scheduler/reserve_form.html',
                        room=room, timeslots=timeslots, categories=categories)

