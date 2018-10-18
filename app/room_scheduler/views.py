# -*- coding: utf8 -*-

from . import roombp as room
from .models import RoomResource
from flask import render_template, jsonify, request

import google.auth
import dateutil.parser
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from ..main import json_keyfile


@room.route('/api/events')
def get_events():
    credentials, project_id = google.auth.default()
    scoped_credentials = credentials.with_scopes([
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events'
    ])
    calendar_service = build('calendar', 'v3', credentials=scoped_credentials)
    request = calendar_service.events().list(calendarId='9hur49up24fdcbicdbggvpu77k@group.calendar.google.com')
    # Loop until all pages have been processed.
    all_events = []
    while request != None:
        # Get the next page.
        response = request.execute()
        # returns a list of item objects (events).
        for event in response.get('items', []):
            # The event object is a dict object with a 'summary' key.
            start = event.get('start', None)
            if start:
                start_datetime = dateutil.parser.parse(start['dateTime'])
            end = event.get('end', None)
            if end:
                end_datetime = dateutil.parser.parse(end['dateTime'])
            evt = {
                'location': event.get('location', None),
                'title': event.get('summary', 'NO SUMMARY'),
                'description': event.get('description', ''),
                'start': start_datetime,
                'end': end_datetime,
            }
            all_events.append(evt)
        # Get the next request object by passing the previous request object to
        # the list_next method.
        request = calendar_service.events().list_next(request, response)
    return jsonify(all_events)


@room.route('/')
def index():
    return render_template('scheduler/room_main.html')


@room.route('/events/new')
def new_event():
    return render_template('scheduler/new_event.html')


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