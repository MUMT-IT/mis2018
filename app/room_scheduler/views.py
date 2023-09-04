# -*- coding: utf8 -*-

import dateutil.parser
import arrow
import pytz
from dateutil import parser
from flask import render_template, jsonify, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from linebot.models import TextSendMessage
from sqlalchemy import and_

from app.main import mail
from .forms import RoomEventForm
from ..auth.views import line_bot_api
from ..main import db
from . import roombp as room
from .models import RoomResource, RoomEvent
from ..models import IOCode
from flask_mail import Message


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


@room.route('/api/iocodes')
@login_required
def get_iocodes():
    codes = []
    for code in IOCode.query.all():
        codes.append(code.to_dict())

    return jsonify(codes)


@room.route('/api/rooms')
@login_required
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
@login_required
def get_events():
    cal_start = request.args.get('start')
    cal_end = request.args.get('end')
    if cal_start:
        cal_start = parser.isoparse(cal_start)
    if cal_end:
        cal_end = parser.isoparse(cal_end)
    all_events = []
    for event in RoomEvent.query.filter(RoomEvent.start >= cal_start) \
            .filter(RoomEvent.end <= cal_end).filter_by(cancelled_at=None):
        # The event object is a dict object with a 'summary' key.
        start = event.start
        end = event.end
        room = event.room
        text_color = '#ffffff'
        bg_color = '#2b8c36'
        border_color = '#ffffff'
        evt = {
            'location': room.number,
            'title': u'(Rm{}) {}'.format(room.number, event.title),
            'description': event.note,
            'start': start.astimezone(pytz.timezone('Asia/Bangkok')).isoformat(),
            'end': end.astimezone(pytz.timezone('Asia/Bangkok')).isoformat(),
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
@login_required
def event_list(list_type='timelineDay'):
    return render_template('scheduler/event_list.html', list_type=list_type)


@room.route('/events/new')
@login_required
def new_event():
    return render_template('scheduler/new_event.html')


@room.route('/events/<int:event_id>', methods=['POST', 'GET'])
@login_required
def show_event_detail(event_id=None):
    if event_id:
        event = RoomEvent.query.get(event_id)
        if event:
            event.start = event.start.astimezone(pytz.timezone('Asia/Bangkok'))
            event.end = event.end.astimezone(pytz.timezone('Asia/Bangkok'))
            return render_template(
                'scheduler/event_detail.html', event=event)
    else:
        return 'No event ID specified.'


@room.route('/events/cancel/<int:event_id>')
@login_required
def cancel(event_id=None):
    if not event_id:
        return redirect(url_for('room.index'))

    cancelled_datetime = arrow.now('Asia/Bangkok').datetime
    event = RoomEvent.query.get(event_id)
    event.cancelled_at = cancelled_datetime
    event.cancelled_by = current_user.id
    db.session.add(event)
    db.session.commit()
    msg = f'{event.creator} ได้ยกเลิกการจอง {room} สำหรับ {event.title} เวลา {event.start} - {event.end}.'
    if not current_app.debug:
        if event.room.coordinator and event.room.coordinator.line_id:
            line_bot_api.push_message(to=event.room.coordinator.line_id,
                                      messages=TextSendMessage(text=msg))
    else:
        print(msg, event.room.coordinator)

    return redirect(url_for('room.index'))


@room.route('/events/approve/<int:event_id>')
@login_required
def approve_event(event_id):
    event = RoomEvent.query.get(event_id)
    event.approved = True
    event.approved_by = current_user.id
    event.approved_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(event)
    db.session.commit()
    flash(u'อนุมัติการจองห้องเรียบร้อยแล้ว', 'success')
    return redirect(url_for('room.index'))


@room.route('/events/edit/<int:event_id>', methods=['POST', 'GET'])
@login_required
def edit_detail(event_id):
    event = RoomEvent.query.get(event_id)
    form = RoomEventForm(obj=event)
    if form.validate_on_submit():
        event_start = arrow.get(form.start.data, 'Asia/Bangkok').datetime
        event_end = arrow.get(form.end.data, 'Asia/Bangkok').datetime
        if get_overlaps(event.room.id, event_start, event_end):
            flash(f'ไม่สามารถจองได้เนื่องจากมีการจองในช่วงเวลาเดียวกัน', 'danger')
            return redirect(url_for('room.edit_detail', event_id=event_id))

        form.populate_obj(event)
        event.updated_at = arrow.now('Asia/Bangkok').datetime
        event.updated_by = current_user.id
        db.session.add(event)
        db.session.commit()
        flash(u'อัพเดตรายการเรียบร้อย', 'success')
        return redirect(url_for('room.index'))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('scheduler/reserve_form.html', event=event, form=form, room=event.room)


@room.route('/list', methods=['POST', 'GET'])
@login_required
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
@login_required
def room_reserve(room_id):
    form = RoomEventForm()
    room = RoomResource.query.get(room_id)
    if form.validate_on_submit():
        new_event = RoomEvent()
        if form.start.data:
            startdatetime = arrow.get(form.start.data, 'Asia/Bangkok').datetime
        else:
            startdatetime = None
        if form.end.data:
            enddatetime = arrow.get(form.end.data, 'Asia/Bangkok').datetime
        else:
            enddatetime = None

        if room_id and startdatetime and enddatetime:
            if get_overlaps(room_id, startdatetime, enddatetime):
                flash(f'ไม่สามารถจองได้เนื่องจากมีการจองในช่วงเวลาเดียวกัน', 'danger')
                return render_template('scheduler/reserve_form.html', room=room, form=form)

            form.populate_obj(new_event)
            new_event.start = startdatetime
            new_event.end = enddatetime
            new_event.created_at = arrow.now('Asia/Bangkok').datetime
            new_event.creator = current_user
            new_event.room_id = room.id
            db.session.add(new_event)
            db.session.commit()

            if new_event.participants and new_event.notify_participants:
                participant_emails = [f'{account.email}@mahidol.ac.th' for account in new_event.participants]
                title = f'แจ้งนัดหมาย{new_event.category}'
                message = f'ท่านได้รับเชิญให้เข้าร่วม {new_event.title}'
                message += f' เวลา {new_event.start.strftime("%d/%m/%Y %H:%M")} - {new_event.end.strftime("%d/%m/%Y %H:%M")}'
                message += f' ณ ห้อง {room.number} {room.location}'
                message += f'\n\nขอความอนุเคราะห์เข้าร่วมในวันและเวลาดังกล่าว'
                send_mail(participant_emails, title, message)
                print('The email has been sent to the participants.')

            msg = f'{new_event.creator.fullname} ได้จองห้อง {room} สำหรับ {new_event.title} เวลา {new_event.start.strftime("%d/%m/%Y %H:%M")} - {new_event.end.strftime("%d/%m/%Y %H:%M")}.'
            if not current_app.debug:
                if room.coordinator and room.coordinator.line_id:
                    line_bot_api.push_message(to=room.coordinator.line_id, messages=TextSendMessage(text=msg))
            else:
                print(msg, room.coordinator)
            flash(u'บันทึกการจองห้องเรียบร้อยแล้ว', 'success')
            return redirect(url_for('room.show_event_detail', event_id=new_event.id))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')

    if room:
        return render_template('scheduler/reserve_form.html', room=room, form=form)
    else:
        flash('Room not found.', 'danger')


@room.route('/api/admin/events')
@login_required
def get_room_event_list():
    room_query = request.args.get('query', 'all')
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = RoomEvent.query.order_by(RoomEvent.start.desc())
    # search filter
    search = request.args.get('search[value]')
    room = RoomResource.query.filter_by(number=search).first()
    if room_query == 'some':
        query = query.filter(RoomEvent.room.has(coordinator=current_user))
    if search:
        query = query.filter(db.or_(
            RoomEvent.room.has(RoomEvent.room == room),
            RoomEvent.title.like(f'%{search}%')
        ))
    total_filtered = query.count()
    query = query.offset(start).limit(length)

    return {
        'data': [d.to_dict() for d in query],
        'recordsFiltered': total_filtered,
        'recordsTotal': RoomEvent.query.count(),
        'draw': request.args.get('draw', type=int),
    }


@room.route('/events')
@login_required
def room_event_list():
    return render_template('scheduler/room_event_list.html')


def get_overlaps(room_id, start, end, session_id=None, session_attr=None):
    query = RoomEvent.query.filter_by(room_id=room_id)
    if not session_id:
        # check for inner overlaps
        overlaps = query.filter(start >= RoomEvent.start, end <= RoomEvent.end).count()

        # check for outer overlaps
        overlaps += query.filter(and_(start <= RoomEvent.start,
                                      end > RoomEvent.start,
                                      end <= RoomEvent.end)).count()

        overlaps += query.filter(and_(start >= RoomEvent.start,
                                      end >= RoomEvent.end,
                                      start < RoomEvent.end)).count()
    else:
        # check for inner overlaps
        overlaps = query.filter(start >= RoomEvent.start,
                                end <= RoomEvent.end,
                                session_id != getattr(RoomEvent, session_attr)).count()

        # check for outer overlaps
        overlaps += query.filter(and_(start <= RoomEvent.start,
                                      end > RoomEvent.start,
                                      session_id != getattr(RoomEvent, session_attr),
                                      end <= RoomEvent.end)).count()

        overlaps += query.filter(and_(start >= RoomEvent.start,
                                      end >= RoomEvent.end,
                                      session_id != getattr(RoomEvent, session_attr),
                                      start < RoomEvent.end)).count()
    return overlaps


@room.route('/api/room-availability')
@login_required
def check_room_availability():
    session_attr = request.args.get('session_attr')
    session_id = request.args.get('session_id', type=int)
    room_id = request.args.get('room', type=int)
    start = request.args.get('start')
    end = request.args.get('end')
    start = dateutil.parser.isoparse(start)
    end = dateutil.parser.isoparse(end)
    if get_overlaps(room_id, start, end, session_id, session_attr):
        return '<span class="tag is-danger">ห้องไม่ว่าง/จองซ้อน</span>'
    else:
        return '<span class="tag is-success">ห้องว่าง</span>'

