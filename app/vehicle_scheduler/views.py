# -*- coding: utf-8 -*-
from . import vehiclebp as vehicle
import pytz
from sqlalchemy.exc import SQLAlchemyError
import google.auth
from datetime import datetime
from googleapiclient.discovery import build
from flask import jsonify, render_template, redirect, flash, url_for, request
from models import *
from ..models import Org, IOCode


CALENDAR_ID = 'anatjgngk7bcv9kte15p38l7mg@group.calendar.google.com'

@vehicle.route('/api/vehicles')
def get_vehicles():
    vehicles = VehicleResource.query.all()
    resources = []
    for vh in vehicles:
        resources.append({
            'id': vh.license,
            'title': vh.license,
            'occupancy': vh.occupancy,
            'businessHours': {
                'start': vh.business_hour_start.strftime('%H:%M'),
                'end': vh.business_hour_end.strftime('%H:%M'),
            }
        })
    return jsonify(resources)


@vehicle.route('/api/events')
def get_events():
    tz = pytz.timezone('Asia/Bangkok')
    credentials, project_id = google.auth.default()
    scoped_credentials = credentials.with_scopes([
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events'
    ])
    calendar_service = build('calendar', 'v3', credentials=scoped_credentials)
    request = calendar_service.events().list(calendarId=CALENDAR_ID)
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
            license = extended_properties.get('license', None)
            org_id = extended_properties.get('orgId', None)
            if org_id:
                org = Org.query.get(int(org_id))
                org = org.name
            else:
                org = None
            status = event.get('status', 'confirmed')
            evt = {
                'license': license,
                'org': org,
                'title': u'{}: {}'.format(license, event.get('summary', 'NO SUMMARY')),
                'description': event.get('description', ''),
                'start': start['dateTime'],
                'end': end['dateTime'],
                'resourceId': license,
                'status': status,
                'borderColor': '#2b8c36' if status=='confirmed' else '#f44242'
            }
            all_events.append(evt)
        # Get the next request object by passing the previous request object to
        # the list_next method.
        request = calendar_service.events().list_next(request, response)
    return jsonify(all_events)


@vehicle.route('/')
def index():
    return render_template('scheduler/vehicle_main.html')

@vehicle.route('/trip')
def trip():
    vehicles = VehicleResource.query.all()
    return render_template(
                'scheduler/vehicle_list_trip.html',
                vehicles=vehicles)


@vehicle.route('/events/<list_type>')
def event_list(list_type='timelineDay'):
    return render_template('scheduler/vehicle_event_list.html', list_type=list_type)


@vehicle.route('/events/new')
def new_event():
    return render_template('scheduler/vehicle_new_event.html')


@vehicle.route('/list', methods=['POST', 'GET'])
def vehicle_list():
    if request.method=='GET':
        vehicles = VehicleResource.query.all()
    else:
        vehicle_license = request.form.get('license', None)
        passengers = request.form.get('occupancy', 0)
        if vehicle_license:
            vehicles = VehicleResource.query.filter_by(license=vehicle_license)
        elif passengers > 0:
            vehicles = VehicleResource.query.filter(VehicleResource.occupancy>=passengers)
        else:
            vehicles = []

    return render_template('scheduler/vehicle_list.html', vehicles=vehicles)


@vehicle.route('/reserve/<license>', methods=['GET', 'POST'])
def vehicle_reserve(license):
    if request.method == 'POST':
        license = request.form.get('license', None)
        iocode_id = request.form.get('iocode', None)
        if iocode_id:
            iocode = IOCode.query.get(iocode_id) 
        else:
            iocode = None

        destination = request.form.get('destination', None)
        desc = request.form.get('desc', None)
        num_passengers = request.form.get('num_passengers', 0)
        distance = request.form.get('distance', None)
        startdate = request.form.get('startdate', None)
        starttime = request.form.get('starttime', None)
        enddate = request.form.get('enddate', None)
        endtime = request.form.get('endtime', None)
        title = request.form.get('title', None)
        org_id = request.form.get('org', None)
        if org_id:
            org = Org.query.get(int(org_id))
        else:
            org = None
        vehicle = VehicleResource.query.filter_by(license=license).first()
        if not vehicle:
            flash('Vehicle with license plate="{}" not found.'.format(license))
            return redirect(url_for('vehicle.index'))
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

        if startdatetime and enddatetime and license and org:
            timedelta = enddatetime - startdatetime
            if timedelta.days < 0 or timedelta.seconds == 0:
                flash('Date or time is invalid.')
            else:
                event = {
                    'summary': title,
                    'location': destination,
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
                            'license': license,
                            'destination': destination,
                            'distance': distance,
                            'orgId': org_id,
                            'iocode': iocode_id,
                        }
                    }
                }
                print(event)
                reservation = VehicleBooking(
                    vehicle=vehicle,
                    title=title,
                    start=startdatetime,
                    end=enddatetime,
                    destination=destination,
                    distance=distance,
                    iocode=iocode,
                    org=org,
                    num_passengers=num_passengers,
                    approved=False,
                    desc=desc,
                )
                credentials, project_id = google.auth.default()
                scoped_credentials = credentials.with_scopes([
                    'https://www.googleapis.com/auth/calendar',
                    'https://www.googleapis.com/auth/calendar.events'
                ])
                calendar_service = build('calendar', 'v3',
                                            credentials=scoped_credentials)
                event = calendar_service.events().insert(
                    calendarId=CALENDAR_ID,
                    body=event).execute()
                if event:
                    reservation.google_event_id = event.get('id')
                    reservation.google_calendar_id = CALENDAR_ID
                    try:
                        db.session.add(reservation)
                        db.session.commit()
                    except SQLAlchemyError as e:
                        db.session.rollback()
                        flash('Reservation failed; cannot save data to the database.')
                    else:
                        flash('Reservation has been made. {}'.format(event.get('id')))
                else:
                    flash('Reservation failed; cannot save data to Google calendar.')
                return redirect(url_for('vehicle.index'))
    if license:
        vehicle = VehicleResource.query.filter_by(license=license).first()
        if vehicle:
            timeslots = []
            for i in range(1,24):
                for j in [0, 30]:
                    timeslots.append('{:02}:{:02}'.format(i,j))
            orgs = Org.query.all()
            return render_template('scheduler/vehicle_reserve_form.html',
                                   vehicle=vehicle, timeslots=timeslots, orgs=orgs)


