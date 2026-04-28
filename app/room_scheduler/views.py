import calendar
import dateutil.parser
import arrow
import os
import pytz
from datetime import datetime, timedelta
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


def _ics_escape(value):
    if not value:
        return ''
    return str(value).replace('\\', '\\\\').replace(';', r'\;').replace(',', r'\,').replace('\n', r'\n')


def _ics_timestamp(dt):
    return dt.astimezone(pytz.utc).strftime('%Y%m%dT%H%M%SZ')


def _ics_param_escape(value):
    if not value:
        return ''
    return str(value).replace('\\', '\\\\').replace(';', r'\;').replace(',', r'\,').replace('"', r'\"')


def build_room_event_ics(events, method='REQUEST'):
    if not events:
        return None

    timestamp = _ics_timestamp(arrow.now('Asia/Bangkok').datetime)
    lines = [
        'BEGIN:VCALENDAR',
        'PRODID:-//MUMT-MIS//Room Scheduler//EN',
        'VERSION:2.0',
        'CALSCALE:GREGORIAN',
        f'METHOD:{method}',
    ]
    system_mail = os.getenv('MAIL_USERNAME') or 'no-reply@mt.mahidol.ac.th'

    for event in events:
        start_dt = event.start if event.start.tzinfo else localtz.localize(event.start)
        end_dt = event.end if event.end.tzinfo else localtz.localize(event.end)
        room_name = f'{event.room.number} {event.room.location}'
        organizer = event.creator or current_user
        organizer_email = system_mail
        organizer_name = _ics_param_escape('MUMT-MIS')
        description_parts = []
        if event.note:
            description_parts.append(event.note)
        description_parts.append(f'Room: {room_name}')
        if getattr(organizer, 'fullname', None):
            description_parts.append(f'Booked by: {organizer.fullname}')
        description = _ics_escape('\n'.join(description_parts))

        lines.extend([
            'BEGIN:VEVENT',
            f'UID:room-event-{event.id}@mt.mahidol.ac.th',
            f'DTSTAMP:{timestamp}',
            f'DTSTART:{_ics_timestamp(start_dt)}',
            f'DTEND:{_ics_timestamp(end_dt)}',
            f'SUMMARY:{_ics_escape(event.title)}',
            f'LOCATION:{_ics_escape(room_name)}',
            f'DESCRIPTION:{description}',
            'STATUS:CONFIRMED',
            'TRANSP:OPAQUE',
            'SEQUENCE:0',
            f'ORGANIZER;CN={organizer_name}:MAILTO:{organizer_email}',
        ])
        attendees = {}
        for participant in event.participants or []:
            if not getattr(participant, 'email', None):
                continue
            attendee_email = f'{participant.email}@mahidol.ac.th'
            attendees[attendee_email.lower()] = _ics_param_escape(getattr(participant, 'fullname', participant.email))

        for attendee_email, attendee_name in attendees.items():
            lines.append(
                f'ATTENDEE;CN={attendee_name};CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:MAILTO:{attendee_email}'
            )
        lines.append('END:VEVENT')

    lines.append('END:VCALENDAR')
    return '\r\n'.join(lines).encode('utf-8')


def send_mail(recp, title, message, attachments=None):
    message = Message(subject=title, body=message, recipients=recp)
    for attachment in attachments or []:
        message.attach(
            filename=attachment['filename'],
            data=attachment['data'],
            content_type=attachment['content_type'],
            headers=attachment.get('headers'),
        )
    mail.send(message)


def create_event(startdatetime, enddatetime, repeat_end, master_id, room_id, form):
    event = RoomEvent()
    form.populate_obj(event)
    event.datetime = DateTimeRange(lower=startdatetime, upper=enddatetime, bounds='[]')
    event.start = startdatetime
    event.end = enddatetime
    event.repeat_end = repeat_end
    event.created_at = arrow.now('Asia/Bangkok').datetime
    event.creator = current_user
    event.room_id = room_id
    event.master_id = master_id
    if request.form.getlist('groups'):
        for group_id in request.form.getlist('groups'):
            group = StaffGroupDetail.query.get(group_id)
            for g in group.group_members:
                event.participants.append(g.staff)
    db.session.add(event)
    db.session.commit()
    return event


def _collect_booking_series(event):
    master_id = event.master_id or event.id
    events = RoomEvent.query.filter(
        or_(RoomEvent.master_id == master_id, RoomEvent.id == master_id)
    ).order_by(RoomEvent.start).all()
    return events or [event]


def _build_room_event_attachment(event):
    ics_data = build_room_event_ics(_collect_booking_series(event))
    if not ics_data:
        return []
    return [{
        'filename': f'room-booking-{event.id}.ics',
        'data': ics_data,
        'content_type': 'text/calendar; charset=utf-8; method=REQUEST',
        'headers': [('Content-Class', 'urn:content-classes:calendarmessage')],
    }]

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
            'title': u'({} {})({}) {} ({} คน): {}'.format(room.number, room.location, event.creator.fullname[:14] + '..' if len(event.creator.fullname) >= 14 else event.creator.fullname, event.title, event.occupancy, event.note),
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
    cutoff = arrow.now('Asia/Bangkok').shift(days=-30).datetime
    recent_reservations = current_user.room_reservations \
        .filter(RoomEvent.created_at >= cutoff) \
        .order_by(RoomEvent.created_at.desc())
    return render_template('scheduler/room_main.html', recent_reservations=recent_reservations)


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
        master_id = event.master_id or event.id
        if event.master_id or event.secondary:
            repeat_events = RoomEvent.query.filter(or_(RoomEvent.master_id == master_id, RoomEvent.id == master_id)).order_by(RoomEvent.start)
        else:
            repeat_events = None
        if event:
            return render_template('scheduler/event_detail.html', event=event, repeat_events=repeat_events,
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
    if not event:
        flash('ไม่พบรายการจองที่ต้องการยกเลิก', 'danger')
        return redirect(url_for('room.index'))

    event.cancelled_at = cancelled_datetime
    event.cancelled_by = current_user.id
    flash('ยกเลิกการจองห้องเรียบร้อยแล้ว', 'success')
    db.session.add(event)
    db.session.commit()

    start = localtz.localize(event.datetime.lower)
    end = localtz.localize(event.datetime.upper)
    event_time = f'{start.strftime("%d/%m/%Y %H:%M")} - {end.strftime("%d/%m/%Y %H:%M")}'
    text = f' เวลา {event_time}'
    msg = f'{event.creator.fullname} ได้ยกเลิกการจอง {event.room.number} สำหรับ {event.title} เวลา {event_time}.'
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
            message += text
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
    new_events = []
    event = RoomEvent.query.get(event_id)
    master_id = event.master_id or event.id
    old_booking = event.booking
    old_start = arrow.get(event.start, 'Asia/Bangkok').datetime
    old_end = arrow.get(event.end, 'Asia/Bangkok').datetime
    old_repeat_end = arrow.get(event.repeat_end, 'Asia/Bangkok').date() if event.repeat_end else None
    repeat_end = arrow.get(event.repeat_end, 'Asia/Bangkok').date() if event.repeat_end else None
    complaints = ComplaintRecord.query.filter(ComplaintRecord.topic.has(ComplaintTopic.code.in_(['room', 'runied'])),
                                              or_(ComplaintRecord.status.has(ComplaintStatus.code != 'completed'),
                                                  ComplaintRecord.status == None),
                                              or_(ComplaintRecord.room_id == event.room_id,
                                                  ComplaintRecord.procurement_location_id == event.room_id)).all()
    form = RoomEventForm(obj=event)
    start = localtz.localize(event.datetime.lower)
    end = localtz.localize(event.datetime.upper)
    if form.validate_on_submit():
        start = arrow.get(form.start.data, 'Asia/Bangkok')
        end = arrow.get(form.end.data, 'Asia/Bangkok')
        event_start = arrow.get(form.start.data, 'Asia/Bangkok').datetime
        event_end = arrow.get(form.end.data, 'Asia/Bangkok').datetime
        overlaps = get_overlaps(event.room.id, event_start, event_end)
        overlaps = [evt for evt in overlaps if evt.id != event_id]
        if overlaps:
            flash(f'ไม่สามารถจองได้เนื่องจากมีการจองในช่วงเวลาเดียวกัน', 'danger')
            return redirect(url_for('room.edit_detail', event_id=event_id))

        form.populate_obj(event)
        repeat_end = arrow.get(form.repeat_end.data, 'Asia/Bangkok').date() if form.repeat_end.data else None
        event.datetime = DateTimeRange(lower=event_start, upper=event_end, bounds='[]')
        event.start = event_start
        event.end = event_end
        event.updated_at = arrow.now('Asia/Bangkok').datetime
        event.updated_by = current_user.id

        if not form.is_repeat_booking.data:
            event.booking = None
            event.repeat_end = None
        else:
            event.booking = form.booking.data
            event.repeat_end = repeat_end

        if request.form.getlist('groups'):
            for group_id in request.form.getlist('groups'):
                group = StaffGroupDetail.query.get(group_id)
                for g in group.group_members:
                    event.participants.append(g.staff)
        db.session.add(event)
        if (form.is_repeat_booking.data and form.booking.data and form.repeat_end.data) and ((form.booking.data != old_booking) or (repeat_end != old_repeat_end) or (event_start != old_start)
            or (event_end != old_end)):
            db.session.commit()
            day = 7 if form.booking.data == 'ทุกสัปดาห์' else 1
            current_start = start.shift(days=day)
            current_end = end.shift(days=day)
            while (current_start.date() <= repeat_end and current_end.date() <= repeat_end):
                # if calendar.weekday(current_date.year, current_date.month, current_date.day) < 5:
                current_startdatetime = current_start.datetime
                current_enddatetime = current_end.datetime
                event_overlaps = get_overlaps(event.room_id, current_startdatetime, current_enddatetime)
                if not event_overlaps:
                    new_evts = create_event(current_startdatetime, current_enddatetime, repeat_end, master_id, event.room_id,
                                            form)
                    new_events.append(new_evts)
                current_start = current_start.shift(days=day)
                current_end = current_end.shift(days=day)
        else:
            db.session.commit()

        if event.participants and event.notify_participants:
            participant_emails = [f'{account.email}@mahidol.ac.th' for account in event.participants]
            title = f'แจ้งแก้ไขการนัดหมาย{event.category}'
            message = f'ท่านได้รับเชิญให้เข้าร่วม {event.title}'
            message += f' เวลา {event_start.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - {event_end.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}'
            message += f' ณ ห้อง {event.room.number} {event.room.location}'
            message += f'\n\nขอความอนุเคราะห์เข้าร่วมในวันและเวลาดังกล่าว'
            if not current_app.debug:
                send_mail(
                    participant_emails,
                    title,
                    message,
                    attachments=_build_room_event_attachment(event),
                )
            else:
                print(message)

        msg = (f'{event.creator.fullname} ได้แก้ไขการจองห้อง {event.room} สำหรับ {event.title} '
                   f'เวลา {event_start.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - '
                   f'{event_end.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}.')
        if event.note:
            msg += f'\nมีความต้องการเพิ่มเติมคือ {event.note}'

        if not current_app.debug:
            coordinators = []
            if event.room.coordinator:
                coordinators.append(event.room.coordinator)
            coordinators.extend(event.room.coordinators)
            sent_ids = set()
            for coord in coordinators:
                if coord and coord.line_id and coord.id not in sent_ids:
                    try:
                        line_bot_api.push_message(to=coord.line_id, messages=TextSendMessage(text=msg))
                        sent_ids.add(coord.id)
                    except LineBotApiError:
                        pass
        else:
            print(msg, event.room.coordinator)

        if new_events and new_events[0].participants and new_events[0].notify_participants:
            new_event_times = ', '.join(
                f"{arrow.get(new_event.start, 'Asia/Bangkok').datetime.astimezone(localtz).strftime('%d/%m/%Y %H:%M')} - "
                f"{arrow.get(new_event.end, 'Asia/Bangkok').datetime.astimezone(localtz).strftime('%d/%m/%Y %H:%M')}"
                for new_event in new_events
            )
            participant_emails = [f'{account.email}@mahidol.ac.th' for account in new_events[0].participants]
            msg = (f'{new_events[0].creator.fullname} ได้จองห้อง {new_events[0].room.number} สำหรับ {new_events[0].title} '
                   f'เวลา {new_event_times}.'
                   f'มีความต้องการเพิ่มเติมคือ {new_events[0].note}'
                   )
            title = f'แจ้งนัดหมาย{new_events[0].category}'
            message = f'ท่านได้รับเชิญให้เข้าร่วม {new_events[0].title}'
            message += f' เวลา {new_event_times}'
            message += f' ณ ห้อง {new_events[0].room.number} {new_events[0].room.location}'
            message += f'\n\nขอความอนุเคราะห์เข้าร่วมในวันและเวลาดังกล่าว'
            if not current_app.debug:
                if new_events[0].note:
                    for coord in new_events[0].room.coordinators:
                            try:
                                line_bot_api.push_message(to=coord.line_id, messages=TextSendMessage(text=msg))
                            except LineBotApiError:
                                pass
                send_mail(participant_emails, title, message, attachments=_build_room_event_attachment(new_events[0]))
            else:
                print(msg, [coord.line_id for coord in new_events[0].room.coordinators], new_events[0].note)
                print(message, participant_emails)


        flash(u'อัพเดตรายการเรียบร้อย', 'success')
        return redirect(url_for('room.index'))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('scheduler/reserve_form.html', event=event, form=form, room=event.room,
                           start=start, end=end, complaints=complaints, repeat_end=repeat_end)


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
            start = arrow.get(form.start.data, 'Asia/Bangkok')
            startdatetime = arrow.get(form.start.data, 'Asia/Bangkok').datetime
        else:
            start = None
            startdatetime = None

        if form.end.data:
            end = arrow.get(form.end.data, 'Asia/Bangkok')
            enddatetime = arrow.get(form.end.data, 'Asia/Bangkok').datetime
        else:
            end = None
            enddatetime = None

        if room_id and startdatetime and enddatetime:
            if get_overlaps(room_id, startdatetime, enddatetime):
                flash(f'ไม่สามารถจองได้เนื่องจากมีการจองในช่วงเวลาเดียวกัน', 'danger')
                return render_template('scheduler/reserve_form.html', room=room, form=form)

            form.populate_obj(new_event)
            repeat_end = arrow.get(form.repeat_end.data, 'Asia/Bangkok').date() if form.repeat_end.data else None
            new_event.datetime = DateTimeRange(lower=startdatetime, upper=enddatetime, bounds='[]')
            new_event.start = startdatetime
            new_event.end = enddatetime
            new_event.created_at = arrow.now('Asia/Bangkok').datetime
            new_event.creator = current_user
            new_event.room_id = room.id

            if not form.is_repeat_booking.data:
                new_event.booking = None
                new_event.repeat_end = None
            else:
                new_event.booking = form.booking.data
                new_event.repeat_end = repeat_end

            if request.form.getlist('groups'):
                for group_id in request.form.getlist('groups'):
                    group = StaffGroupDetail.query.get(group_id)
                    for g in group.group_members:
                        new_event.participants.append(g.staff)
            db.session.add(new_event)

            if form.is_repeat_booking.data and form.booking.data and form.repeat_end.data:
                db.session.commit()
                day = 7 if form.booking.data == 'ทุกสัปดาห์' else 1
                current_start = start.shift(days=day)
                current_end = end.shift(days=day)
                while (current_start.date() <= repeat_end and current_end.date() <= repeat_end):
                    # if calendar.weekday(current_date.year, current_date.month, current_date.day) < 5:
                    current_startdatetime = current_start.datetime
                    current_enddatetime = current_end.datetime
                    event_overlaps = get_overlaps(room_id, current_startdatetime, current_enddatetime)
                    if not event_overlaps:
                        create_event(current_startdatetime, current_enddatetime, repeat_end, new_event.id, room_id, form)
                    current_start = current_start.shift(days=day)
                    current_end = current_end.shift(days=day)
            else:
                db.session.commit()

            if new_event.secondary:
                event_times = ', '.join(
                    f"{arrow.get(other_event.start, 'Asia/Bangkok').datetime.astimezone(localtz).strftime('%d/%m/%Y %H:%M')} - "
                    f"{arrow.get(other_event.end, 'Asia/Bangkok').datetime.astimezone(localtz).strftime('%d/%m/%Y %H:%M')}"
                    for other_event in new_event.secondary
                    )
            else:
                event_times = None

            if new_event.participants and new_event.notify_participants:
                participant_emails = [f'{account.email}@mahidol.ac.th' for account in new_event.participants]
                title = f'แจ้งนัดหมาย{new_event.category}'
                message = f'ท่านได้รับเชิญให้เข้าร่วม {new_event.title}'
                if event_times:
                    message += f' เวลา {startdatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - {enddatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}, {event_times}'
                else:
                    message += f' เวลา {startdatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - {enddatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}'
                message += f' ณ ห้อง {room.number} {room.location}'
                message += f'\n\nขอความอนุเคราะห์เข้าร่วมในวันและเวลาดังกล่าว'
                if not current_app.debug:
                    send_mail(
                        participant_emails,
                        title,
                        message,
                        attachments=_build_room_event_attachment(new_event),
                    )
                else:
                    print(message)
            if event_times:
                msg = (f'{new_event.creator.fullname} ได้จองห้อง {room} สำหรับ {new_event.title} '
                       f'เวลา {startdatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - {enddatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}, {event_times}.'
                       f'มีความต้องการเพิ่มเติมคือ {new_event.note}'
                       )
            else:
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
    if start < end:
        overlaps = get_overlaps(room_id, start, end, session_id, session_attr)
        overlaps = [evt for evt in overlaps if evt.id != event_id]
    else:
        overlaps = None
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
