# -*- coding:utf-8 -*-
import pytz
from dateutil import parser
from flask import render_template, jsonify, request, url_for, flash, redirect
from flask_login import current_user, login_required
from . import instrumentsbp as instruments
from app.models import *
from app.instruments.forms import InstrumentsBookingForm
from app.procurement.models import ProcurementDetail
from .models import InstrumentsBooking
from datetime import datetime

tz = pytz.timezone('Asia/Bangkok')


@instruments.route('/api/instruments')
def get_instruments():
    instruments = ProcurementDetail.query.filter_by(is_instruments=True)
    resources = []
    for instrument in instruments:
        resources.append({
            'id': instrument.id,
            'title': instrument.name
        })
        print(resources)
    return jsonify(resources)


@instruments.route('/api/bookings')
def get_bookings():
    start = request.args.get('start')
    end = request.args.get('end')
    if start:
        start = parser.isoparse(start)
    if end:
        end = parser.isoparse(end)
    all_bookings = []
    for booking in InstrumentsBooking.query.filter(InstrumentsBooking.start.between(start, end)):
        start = booking.start
        end = booking.end
        if booking.start:
            text_color = '#ffffff'
            bg_color = '#2b8c36'
            border_color = '#ffffff'
        else:
            text_color = '#000000'
            bg_color = '#f0f0f5'
            border_color = '#ff4d4d'
        book = {
            'title': booking.title,
            'start': start.astimezone(tz).isoformat(),
            'end': end.astimezone(tz).isoformat(),
            'resourceId': booking.detail_id,
            'borderColor': border_color,
            'backgroundColor': bg_color,
            'textColor': text_color,
            'id': booking.id,
        }
        all_bookings.append(book)
    return jsonify(all_bookings)


@instruments.route('/index')
@login_required
def index_of_instruments():
    return render_template('instruments/index.html', list_type='default')


@instruments.route('/bookings/<list_type>')
@login_required
def booking_instruments_list(list_type='timelineDay'):
    return render_template('instruments/booking_list.html', list_type=list_type)


@instruments.route('/bookings/<int:booking_id>', methods=['POST', 'GET'])
@login_required
def show_booking_detail(booking_id=None):
    tz = pytz.timezone('Asia/Bangkok')
    if booking_id:
        booking = InstrumentsBooking.query.get(booking_id)
        if booking:
            booking.start = booking.start.astimezone(tz)
            booking.end = booking.end.astimezone(tz)
            return render_template('instruments/booking_detail.html', booking=booking)
    else:
        return 'No booking ID specified.'


@instruments.route('/bookings/<int:booking_id>', methods=['POST', 'GET'])
@login_required
def show_booking_detail(booking_id=None):
    tz = pytz.timezone('Asia/Bangkok')
    if booking_id:
        booking = InstrumentsBooking.query.get(booking_id)
        if booking:
            booking.start = booking.start.astimezone(tz)
            booking.end = booking.end.astimezone(tz)
            return render_template('instruments/booking_detail.html', booking=booking)
    else:
        return 'No booking ID specified.'


@instruments.route('instruments_list/reserve/all', methods=['GET', 'POST'])
@login_required
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
        if item.current_record:
            item_data['location'] = item.current_record.location
        else:
            item_data['location'] = None
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementDetail.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@instruments.route('/reserve/<string:procurement_no>', methods=['GET', 'POST'])
@login_required
def instruments_reserve(procurement_no):
    procurement = ProcurementDetail.query.filter_by(procurement_no=procurement_no).first()
    form = InstrumentsBookingForm()
    if form.validate_on_submit():
        reservation = InstrumentsBooking()
        reservation.created_by = current_user.id
        reservation.created_at = tz.localize(datetime.utcnow())
        reservation.detail_id = procurement.id
        form.populate_obj(reservation)
        db.session.add(reservation)
        db.session.commit()
        return redirect(url_for('instruments.show_booking_detail', booking_id=reservation.id))
    else:
        for err in form.errors.values():
            flash(', '.join(err), 'danger')
    return render_template('instruments/reserve_form.html', form=form, procurement=procurement)


@instruments.route('/reserve/edit/<int:booking_id>', methods=['POST', 'GET'])
@login_required
def edit_detail(booking_id):
    booking = InstrumentsBooking.query.get(booking_id)
    form = InstrumentsBookingForm(obj=booking)
    if form.validate_on_submit():
        form.populate_obj(booking)
        booking.start = form.start.data.astimezone(tz)
        booking.end = form.end.data.astimezone(tz)
        booking.updated_at = datetime.utcnow().astimezone(tz)
        booking.updated_by = current_user.id
        db.session.add(booking)
        db.session.commit()
        flash(u'อัพเดตรายการเรียบร้อย', 'success')
        return redirect(url_for('instruments.show_booking_detail', booking_id=booking.id))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('instruments/reserve_form.html', booking=booking, form=form)


@instruments.route('/reserve/cancel/<int:booking_id>')
@login_required
def cancel(booking_id=None):
    if not booking_id:
        return redirect(url_for('instruments.index_of_instruments'))
    booking = InstrumentsBooking.query.get(booking_id)
    booking.cancelled_at = tz.localize(datetime.utcnow())
    booking.cancelled_by = current_user.id
    db.session.add(booking)
    db.session.commit()
    return redirect(url_for('instruments.index_of_instruments'))

