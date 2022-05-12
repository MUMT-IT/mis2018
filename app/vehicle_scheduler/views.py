# -*- coding: utf-8 -*-
import os

import dateutil
import requests
from flask_login import login_required

from . import vehiclebp as vehicle
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from googleapiclient.discovery import build
from flask import jsonify, render_template, redirect, flash, url_for, request, abort
from models import *
from .forms import VehicleBookingForm
from ..models import Org, IOCode
from google.oauth2.service_account import Credentials

if os.environ.get('FLASK_ENV') == 'development':
    CALENDAR_ID = 'cl05me2rhh57a5n3i76nqao7ng@group.calendar.google.com'
else:
    CALENDAR_ID = 'anatjgngk7bcv9kte15p38l7mg@group.calendar.google.com'

service_account_info = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
credentials = Credentials.from_service_account_info(service_account_info)


@vehicle.route('/api/vehicles')
@login_required
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
@login_required
def get_events():
    start = request.args.get('start')
    end = request.args.get('end')
    if start:
        start = dateutil.parser.isoparse(start)
    if end:
        end = dateutil.parser.isoparse(end)
    events = VehicleBooking.query.filter(VehicleBooking.start >= start) \
        .filter(VehicleBooking.end <= end)
    all_events = []
    for event in events:
        if event.cancelled_at:
            text_color = '#ffffff'
            bg_color = '#ff6666'
            border_color = '#ffffff'
        elif event.approved:
            text_color = '#ffffff'
            bg_color = '#2b8c36'
            border_color = '#ffffff'
        elif event.closed:
            bg_color = '#003366'
            border_color = '#000000'
        else:
            text_color = '#000000'
            bg_color = '#f0f0f5'
            border_color = '#ff4d4d'
        evt = event.to_dict()
        evt['borderColor'] = border_color
        evt['backgroundColor'] = bg_color
        evt['textColor'] = text_color
        all_events.append(evt)
    return jsonify(all_events)


@vehicle.route('/')
@login_required
def index():
    return render_template('scheduler/vehicle_main.html')


@vehicle.route('/trip')
@login_required
def trip():
    vehicles = VehicleResource.query.all()
    return render_template(
        'scheduler/vehicle_list_trip.html',
        vehicles=vehicles)


@vehicle.route('/events/<list_type>')
@login_required
def event_list(list_type='timelineDay'):
    return render_template('scheduler/vehicle_event_list.html', list_type=list_type)


@vehicle.route('/events/<int:event_id>', methods=['POST', 'GET'])
@login_required
def show_event_detail(event_id=None):
    tz = pytz.timezone('Asia/Bangkok')
    if event_id:
        event = VehicleBooking.query.get(event_id)
        if event:
            event.start = event.start.astimezone(tz)
            event.end = event.end.astimezone(tz)
            return render_template(
                'scheduler/vehicle_event_detail.html', event=event)
    else:
        return 'No event ID specified.'


@vehicle.route('/events/new')
@login_required
def new_event():
    return render_template('scheduler/vehicle_new_event.html')


@vehicle.route('/list', methods=['POST', 'GET'])
@login_required
def vehicle_list():
    if request.method == 'GET':
        vehicles = VehicleResource.query.all()
    else:
        vehicle_license = request.form.get('license', None)
        passengers = request.form.get('occupancy', 0)
        if vehicle_license:
            vehicles = VehicleResource.query.filter_by(license=vehicle_license)
        elif passengers > 0:
            vehicles = VehicleResource.query.filter(VehicleResource.occupancy >= passengers)
        else:
            vehicles = []

    return render_template('scheduler/vehicle_list.html', vehicles=vehicles)


@vehicle.route('/reserve/<license>', methods=['GET', 'POST'])
@login_required
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
                flash(u'ระบุวันและเวลาเริ่มต้นสิ้นสุดไม่ถูกต้อง', 'warning')
            else:
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
                db.session.add(reservation)
                db.session.commit()

                return redirect(url_for('vehicle.index'))
    if license:
        vehicle = VehicleResource.query.filter_by(license=license).first()
        if vehicle:
            timeslots = []
            for i in range(1, 24):
                for j in [0, 30]:
                    timeslots.append('{:02}:{:02}'.format(i, j))
            orgs = Org.query.all()
            return render_template('scheduler/vehicle_reserve_form.html',
                                   vehicle=vehicle, timeslots=timeslots, orgs=orgs)


@vehicle.route('/events/approve/<int:event_id>')
@login_required
def approve_event(event_id):
    if event_id:
        event = VehicleBooking.query.get(event_id)
        if not event.approved:
            event.approved = True
            db.session.add(event)
            db.session.commit()

        flash(u'รายการจองหมายเลข {} ได้รับการอนุมัติแล้ว'.format(event_id), 'success')
    else:
        flash(u'ไม่พบรายการจองหมายเลข {}'.format(event_id), 'warning')

    return redirect(url_for('vehicle.index'))


@vehicle.route('/events/edit/<int:event_id>', methods=['POST', 'GET'])
@login_required
def edit_detail(event_id=None):
    event = VehicleBooking.query.get(int(event_id))
    form = VehicleBookingForm(obj=event)
    if not event:
        return abort(404, u'ไม่พบรายการที่ท่านต้องการ')

    if form.validate_on_submit():
        form.populate_obj(event)
        db.session.add(event)
        db.session.commit()

        return redirect(url_for('vehicle.show_event_detail', event_id=event.id))
    else:
        flash(form.errors, 'danger')

    print(form.start.data)
    return render_template('scheduler/vehicle_event_edit.html', form=form, event=event)


@vehicle.route('/events/cancel/<int:event_id>')
@login_required
def cancel(event_id):
    event = VehicleBooking.query.get(event_id)
    if event:
        if not event.init_milage and not event.end_milage:
            tz = pytz.timezone('Asia/Bangkok')
            cancelled_datetime = tz.localize(datetime.utcnow())
            event.cancelled_at = cancelled_datetime
            db.session.add(event)
            db.session.commit()
            update_event = {'status': 'cancelled'}
            scoped_credentials = credentials.with_scopes([
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/calendar.events'
            ])
            calendar_service = build('calendar', 'v3',
                                     credentials=scoped_credentials)
            event_ = calendar_service.events().patch(
                calendarId=event.google_calendar_id,
                eventId=event.google_event_id, body=update_event).execute()
            flash('The booking no.{} has been cancelled.'.format(event.id))
        else:
            flash('The booking no.{} cannot be cancelled.'.format(event.id))
    else:
        flash('The booking no.{} not found.'.format(event.id))
    return redirect(url_for('vehicle.index'))
