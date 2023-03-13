# -*- coding:utf-8 -*-
import os

import dateutil
import requests
from flask import render_template, jsonify, request, url_for, flash, redirect
from . import instrumentsbp as instruments
from models import *
from .forms import InstrumentsBookingForm
from ..procurement.models import ProcurementDetail

from google.oauth2.service_account import Credentials

if os.environ.get('FLASK_ENV') == 'development':
    CALENDAR_ID = 'cl05me2rhh57a5n3i76nqao7ng@group.calendar.google.com'
else:
    CALENDAR_ID = 'anatjgngk7bcv9kte15p38l7mg@group.calendar.google.com'

service_account_info = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
credentials = Credentials.from_service_account_info(service_account_info)


@instruments.route('/api/instruments')
def get_instruments():
    instruments = ProcurementDetail.query.all()
    resources = []
    for ins in instruments:
        resources.append({
            'id': ins.id,
            'title': ins.title,
            'businessHours': {
                'start': ins.business_hour_start.strftime('%H:%M'),
                'end': ins.business_hour_end.strftime('%H:%M'),
            }
        })
    return jsonify(resources)


@instruments.route('/api/events')
def get_events():
    start = request.args.get('start')
    end = request.args.get('end')
    if start:
        start = dateutil.parser.isoparse(start)
    if end:
        end = dateutil.parser.isoparse(end)
    events = InstrumentsBooking.query.filter(InstrumentsBooking.start >= start) \
        .filter(InstrumentsBooking.end <= end)
    all_events = []
    for event in events:
        if event.is_closed:
            text_color = '#ffffff'
            bg_color = '#066b02'
            border_color = '#ffffff'
        elif event.cancelled_at:
            text_color = '#ffffff'
            bg_color = '#ff6666'
            border_color = '#ffffff'
        else:
            text_color = '#000000'
            bg_color = '#f0f0f5'
            border_color = '#ffffff'
        evt = event.to_dict()
        evt['borderColor'] = border_color
        evt['backgroundColor'] = bg_color
        evt['textColor'] = text_color
        all_events.append(evt)
    return jsonify(all_events)


@instruments.route('/index')
def index_of_instruments():
    return render_template('instruments/index.html', list_type='default')


@instruments.route('/events/<list_type>')
def event_instruments_list(list_type='timelineDay'):
    return render_template('instruments/event_list.html', list_type=list_type)


@instruments.route('/events/<int:event_id>', methods=['POST', 'GET'])
def show_event_detail(event_id=None):
    tz = pytz.timezone('Asia/Bangkok')
    if event_id:
        event = InstrumentsBooking.query.get(event_id)
        if event:
            event.start = event.start.astimezone(tz)
            event.end = event.end.astimezone(tz)
            return render_template('instruments/event_detail.html', event=event)
    else:
        return 'No event ID specified.'


@instruments.route('/events/new')
def new_event():
    return render_template('instruments/new_event.html')


@instruments.route('/list', methods=['POST', 'GET'])
def instruments_list():
    erp_code = request.form.get('erp_code', None)
    if erp_code:
        procurements = ProcurementDetail.query.filter_by(erp_code=erp_code)
    else:
        procurements = []
    return render_template('instruments/instruments_list.html', procurements=procurements)


@instruments.route('instruments_list/reserve/all', methods=['GET', 'POST'])
def view_all_instruments_to_reserve():
    return render_template('instruments/view_all_instruments_to_reserve.html')


@instruments.route('api/instruments_list/reserve/all')
def get_instruments_to_reserve():
    query = ProcurementDetail.query.filter_by(is_instruments=True)
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ProcurementDetail.erp_code.ilike(u'%{}%'.format(search)),
        ProcurementDetail.procurement_no.ilike(u'%{}%'.format(search)),
        ProcurementDetail.name.ilike(u'%{}%'.format(search))
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        item_data['reserve'] = '<a href="{}" class="button is-small is-rounded is-info is-outlined">จอง</a>'.format(
            url_for('instruments.instruments_reserve', procurement_no=item.procurement_no))
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementDetail.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@instruments.route('/reserve/<string:procurement_no>', methods=['GET', 'POST'])
def instruments_reserve(procurement_no):
    procurement = ProcurementDetail.query.filter_by(procurement_no=procurement_no).first()
    form = InstrumentsBookingForm()
    if form.validate_on_submit():
        reservation = InstrumentsBooking()
        form.populate_obj(reservation)
        db.session.add(reservation)
        db.session.commit()
        return redirect(url_for('instruments.index'))
    else:
        for err in form.errors.values():
            flash(', '.join(err), 'danger')
    return render_template('instruments/reserve_form.html', form=form, procurement=procurement)