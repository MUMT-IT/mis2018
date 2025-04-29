from datetime import datetime, timedelta

import dateutil.parser
import arrow
import pytz
from dateutil import parser
from flask import render_template, jsonify, request, flash, redirect, url_for, current_app, make_response
from flask_login import login_required, current_user
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
from psycopg2.extras import DateTimeRange
from sqlalchemy import or_
from app.main import mail
from .forms import RoomEventForm
from ..auth.views import line_bot_api
from ..complaint_tracker.models import ComplaintRecord, ComplaintStatus, ComplaintTopic
from ..main import db
from . import roombp as room
from .models import RoomResource, RoomEvent, room_coordinator_assoc
from ..models import IOCode
from flask_mail import Message

from ..staff.models import StaffAccount, StaffGroupDetail

localtz = pytz.timezone('Asia/Bangkok')


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
    query = request.args.get('query', 'all')
    if query == 'coordinators':
        rooms = current_user.rooms
    else:
        rooms = RoomResource.query.all()
    resources = []
    for rm in rooms:
        if query == 'reservable':
            if not rm.availability:
                continue
        resources.append({
            'id': rm.id,
            'location': rm.location,
            'title': rm.number,
            'occupancy': rm.occupancy,
            'businessHours': {
                'start': rm.business_hour_start.strftime('%H:%M') if rm.business_hour_start else None,
                'end': rm.business_hour_end.strftime('%H:%M') if rm.business_hour_end else None,
            }
        })
    return jsonify(resources)


@room.route('/api/events')
@login_required
def get_events():
    cal_query = request.args.get('query', 'all')
    cal_start = request.args.get('start')
    cal_end = request.args.get('end')
    if cal_start:
        cal_start = parser.isoparse(cal_start)
    if cal_end:
        cal_end = parser.isoparse(cal_end)
    all_events = []
    query = RoomEvent.query.filter(RoomEvent.datetime.op('&&')(DateTimeRange(lower=cal_start, upper=cal_end, bounds='[]')))
    text_color = '#000000'
    for event in query.filter_by(cancelled_at=None):
        if cal_query == 'some' and event.room not in current_user.rooms:
            # only return event with the room coordinated by the user.
            continue

        # The event object is a dict object with a 'summary' key.
        start = localtz.localize(event.datetime.lower)
        end = localtz.localize(event.datetime.upper)
        room = event.room

        evt = {
            'location': room.location,
            'title': u'({} {}) {} ({} คน): {}'.format(room.number, room.location, event.title, event.occupancy, event.note),
            'description': event.note,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'resourceId': room.id,
            'status': event.approved,
            'borderColor': '#000000',
            'backgroundColor': room.type.color if room.type else '#fafbfc',
            'textColor': text_color,
            'id': event.id,
        }
        all_events.append(evt)
    return jsonify(all_events)


@room.route('/')
@login_required
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
            return render_template('scheduler/event_detail.html', event=event,
                                   event_start=localtz.localize(event.datetime.lower),
                                   event_end=localtz.localize(event.datetime.upper),
                                   )
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
    start = localtz.localize(event.datetime.lower)
    end = localtz.localize(event.datetime.upper)
    msg = f'{event.creator.fullname} ได้ยกเลิกการจอง {event.room.number} สำหรับ {event.title} เวลา {start.strftime("%d/%m/%Y %H:%M")} - {end.strftime("%d/%m/%Y %H:%M")}.'
    if not current_app.debug:
        if event.note:
            for coord in event.room.coordinators:
                try:
                    line_bot_api.push_message(to=coord.line_id, messages=TextSendMessage(text=msg))
                except LineBotApiError:
                    pass
        if event.participants and event.notify_participants:
            participant_emails = [f'{account.email}@mahidol.ac.th' for account in event.participants]
            title = f'แจ้งยกเลิกการนัดหมาย{event.category}'
            message = f'ขอแจ้งยกเลิกคำเชิญเข้าร่วม {event.title}'
            message += f' เวลา {start.strftime("%d/%m/%Y %H:%M")} - {end.strftime("%d/%m/%Y %H:%M")}'
            message += f' ณ ห้อง {event.room.number} {event.room.location}'
            message += f'\n\nขออภัยในความไม่สะดวก'
            send_mail(participant_emails, title, message)
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
    complaints = ComplaintRecord.query.filter(ComplaintRecord.topic.has(ComplaintTopic.code.in_(['room', 'runied'])),
                                              or_(ComplaintRecord.status.has(ComplaintStatus.code != 'completed'),
                                                  ComplaintRecord.status == None),
                                              or_(ComplaintRecord.room_id == event.room_id,
                                                  ComplaintRecord.procurement_location_id == event.room_id)).all()
    form = RoomEventForm(obj=event)
    start = localtz.localize(event.datetime.lower)
    end = localtz.localize(event.datetime.upper)
    if form.validate_on_submit():
        event_start = arrow.get(form.start.data, 'Asia/Bangkok').datetime
        event_end = arrow.get(form.end.data, 'Asia/Bangkok').datetime
        overlaps = get_overlaps(event.room.id, event_start, event_end)
        overlaps = [evt for evt in overlaps if evt.id != event_id]
        if overlaps:
            flash(f'ไม่สามารถจองได้เนื่องจากมีการจองในช่วงเวลาเดียวกัน', 'danger')
            return redirect(url_for('room.edit_detail', event_id=event_id))

        form.populate_obj(event)
        event.datetime = DateTimeRange(lower=event_start, upper=event_end, bounds='[]')
        print(event.datetime)
        event.updated_at = arrow.now('Asia/Bangkok').datetime
        event.updated_by = current_user.id
        if request.form.getlist('groups'):
            for group_id in request.form.getlist('groups'):
                group = StaffGroupDetail.query.get(group_id)
                for g in group.group_members:
                    event.participants.append(g.staff)
        db.session.add(event)
        db.session.commit()
        if event.participants and event.notify_participants:
            participant_emails = [f'{account.email}@mahidol.ac.th' for account in event.participants]
            title = f'แจ้งแก้ไขการนัดหมาย{event.category}'
            message = f'ท่านได้รับเชิญให้เข้าร่วม {event.title}'
            message += f' เวลา {event_start.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - {event_end.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}'
            message += f' ณ ห้อง {event.room.number} {event.room.location}'
            message += f'\n\nขอความอนุเคราะห์เข้าร่วมในวันและเวลาดังกล่าว'
            if not current_app.debug:
                send_mail(participant_emails, title, message)
            else:
                print(message)
        msg = f'{event.creator.fullname} ได้แก้ไขการจองห้อง {event.room} สำหรับ {event.title} เวลา {event_start.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - {event_end.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}.'
        if not current_app.debug:
            if event.room.coordinator and event.room.coordinator.line_id:
                try:
                    line_bot_api.push_message(to=event.room.coordinator.line_id,
                                              messages=TextSendMessage(text=msg))
                except LineBotApiError:
                    pass
        else:
            print(msg, event.room.coordinator)
        flash(u'อัพเดตรายการเรียบร้อย', 'success')
        return redirect(url_for('room.index'))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('scheduler/reserve_form.html', event=event, form=form, room=event.room,
                           start=start, end=end, complaints=complaints)


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
            if rooms:
                return render_template('scheduler/partials/room_list.html', rooms=rooms)
            else:
                return ''

    return render_template('scheduler/room_list.html', rooms=rooms)


@room.route('/reserve/<room_id>', methods=['GET', 'POST'])
@login_required
def room_reserve(room_id):
    form = RoomEventForm()
    room = RoomResource.query.get(room_id)
    complaints = ComplaintRecord.query.filter(ComplaintRecord.topic.has(ComplaintTopic.code.in_(['room', 'runied'])),
                                              or_(ComplaintRecord.status.has(ComplaintStatus.code!='completed'),
                                                  ComplaintRecord.status==None),
                                              or_(ComplaintRecord.room_id==room_id, ComplaintRecord.procurement_location_id==room_id)).all()
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
            new_event.datetime = DateTimeRange(lower=startdatetime, upper=enddatetime, bounds='[]')
            new_event.start = startdatetime
            new_event.end = enddatetime
            new_event.created_at = arrow.now('Asia/Bangkok').datetime
            new_event.creator = current_user
            new_event.room_id = room.id
            if request.form.getlist('groups'):
                for group_id in request.form.getlist('groups'):
                    group = StaffGroupDetail.query.get(group_id)
                    for g in group.group_members:
                        new_event.participants.append(g.staff)
            db.session.add(new_event)
            db.session.commit()
            # TODO: alert by Line for the same-day booking
            if new_event.participants and new_event.notify_participants:
                participant_emails = [f'{account.email}@mahidol.ac.th' for account in new_event.participants]
                title = f'แจ้งนัดหมาย{new_event.category}'
                message = f'ท่านได้รับเชิญให้เข้าร่วม {new_event.title}'
                message += f' เวลา {startdatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - {enddatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}'
                message += f' ณ ห้อง {room.number} {room.location}'
                message += f'\n\nขอความอนุเคราะห์เข้าร่วมในวันและเวลาดังกล่าว'
                if not current_app.debug:
                    send_mail(participant_emails, title, message)
                else:
                    print(message)

            msg = (f'{new_event.creator.fullname} ได้จองห้อง {room} สำหรับ {new_event.title} '
                   f'เวลา {startdatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - {enddatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}.'
                   f'มีความต้องการเพิ่มเติมคือ {new_event.note}'
                   )
            if not current_app.debug:
                if new_event.note:
                    for coord in room.coordinators:
                        try:
                            line_bot_api.push_message(to=coord.line_id, messages=TextSendMessage(text=msg))
                        except LineBotApiError:
                            pass
            else:
                print(msg, room.coordinators, new_event.note)
            flash(u'บันทึกการจองห้องเรียบร้อยแล้ว', 'success')
            return redirect(url_for('room.show_event_detail', event_id=new_event.id))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')

    if room:
        return render_template('scheduler/reserve_form.html',
                               room=room, complaints=complaints, form=form)
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
        query = query.join(RoomResource).join(room_coordinator_assoc).join(StaffAccount).filter_by(email=current_user.email)
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


@room.route('/coordinators')
@login_required
def room_event_list():
    today = datetime.today()
    enddate = today + timedelta(days=7)
    _daterange = DateTimeRange(lower=today, upper=enddate, bounds='[]')
    query = RoomEvent.query.filter(RoomEvent.datetime.op('&&')(_daterange)).filter_by(cancelled_at=None)
    for event in query:
        if event.note:
            flash(f'ห้อง{event.room} เวลา{event.start.astimezone(pytz.timezone("Asia/Bangkok")).strftime("%d/%m %H:%M")} ต้องการ{event.note}', 'warning')
    return render_template('scheduler/room_event_list.html')


@room.route('/coordinators/remove/<int:room_id>', methods=['DELETE'])
@login_required
def remove_coordinated_room(room_id):
    room = RoomResource.query.get(room_id)
    current_user.rooms.remove(room)
    db.session.add(current_user)
    db.session.commit()
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


def get_overlaps(room_id, start, end, session_id=None, session_attr=None, no_cancellation=True):
    query = RoomEvent.query.filter_by(room_id=room_id)
    events = set()
    for evt in query.filter(RoomEvent.datetime.op('&&')(DateTimeRange(lower=start, upper=end, bounds='[]'))):
        events.add(evt)
    if no_cancellation:
        return set([e for e in events if e.cancelled_at is None])
    return events


@room.route('/api/room-availability')
@login_required
def check_room_availability():
    session_attr = request.args.get('session_attr')
    session_id = request.args.get('session_id', type=int)
    room_id = request.args.get('room', type=int)
    event_id = request.args.get('event_id', type=int)
    start = request.args.get('start')
    end = request.args.get('end')
    start = dateutil.parser.isoparse(start).astimezone(pytz.timezone('Asia/Bangkok'))
    end = dateutil.parser.isoparse(end).astimezone(pytz.timezone('Asia/Bangkok'))
    overlaps = get_overlaps(room_id, start, end, session_id, session_attr)
    overlaps = [evt for evt in overlaps if evt.id != event_id]
    if overlaps:
        temp = '<span class="tag is-warning">{}-{} {}</span>'
        template = '<span class="tag is-danger">ห้องไม่ว่าง</span>'
        template += '<span id="overlaps" hx-swap-oob="true" class="tags">'
        template += ''.join([temp.format(localtz.localize(evt.datetime.lower).strftime('%H:%M'),
                                         localtz.localize(evt.datetime.upper).strftime('%H:%M'),
                                         evt.title) for evt in overlaps])
        template += '</span>'
    else:
        template = '<span class="tag is-success">ห้องว่าง</span>'
        template += '<span id="overlaps" hx-swap-oob="true" class="tags"></span>'
    resp = make_response(template)
    return resp


@room.route('/api/room-availability/clear')
@login_required
def clear_status():
    template = '<span id="overlaps" hx-swap-oob="true" class="tags"></span>'
    resp = make_response(template)
    return resp


@room.route('/<int:room_id>/scan-qrcode/view', methods=['GET', 'POST'])
def view_feature_after_scan_qrcode_room(room_id):
    room = RoomResource.query.get(room_id)
    return render_template('scheduler/view_feature_after_scan_qrcode_room.html', room=room)