import calendar
import datetime
import arrow
import os
from collections import namedtuple
from flask import render_template, request, redirect, url_for, current_app, make_response, flash
from flask_login import login_required, current_user
from flask_mail import Message
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
from app.auth.views import line_bot_api
from app.besttime import besttime_bp
from app.besttime.forms import BestTimePollMessageForm, BestTimePollForm, BestTimePollVoteForm, BestTimeMailForm
from app.besttime.models import *
from app.main import mail
from app.staff.views import send_mail as base_send_mail

VoteHour = namedtuple('VoteHour', ['start', 'end'])

BKK_TZ = ZoneInfo('Asia/Bangkok')

vote_hours = [VoteHour(datetime.time(9, 0, 0, tzinfo=BKK_TZ),
                       datetime.time(12, 0, 0, tzinfo=BKK_TZ)),
              VoteHour(datetime.time(13, 0, 0, tzinfo=BKK_TZ),
                       datetime.time(16, 0, 0, tzinfo=BKK_TZ)),
              ]


def _ics_escape(value):
    if not value:
        return ''
    return str(value).replace('\\', '\\\\').replace(';', r'\;').replace(',', r'\,').replace('\n', r'\n')


def _ics_param_escape(value):
    if not value:
        return ''
    return str(value).replace('\\', '\\\\').replace(';', r'\;').replace(',', r'\,').replace('"', r'\"')


def _ics_timestamp(dt):
    return dt.astimezone(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def build_besttime_slot_ics(slot):
    organizer_email = os.getenv('MAIL_USERNAME') or 'no-reply@mt.mahidol.ac.th'
    organizer_name = _ics_param_escape('MUMT-MIS')
    description_parts = []
    if slot.poll.desc:
        description_parts.append(slot.poll.desc)
    description_parts.append(f'Poll: {slot.poll.title}')
    if getattr(slot.poll.creator, 'fullname', None):
        description_parts.append(f'Created by: {slot.poll.creator.fullname}')
    description = _ics_escape('\n'.join(description_parts))
    lines = [
        'BEGIN:VCALENDAR',
        'PRODID:-//MUMT-MIS//BestTime//EN',
        'VERSION:2.0',
        'CALSCALE:GREGORIAN',
        'METHOD:REQUEST',
        'BEGIN:VEVENT',
        f'UID:besttime-slot-{slot.id}@mt.mahidol.ac.th',
        f'DTSTAMP:{_ics_timestamp(arrow.now("Asia/Bangkok").datetime)}',
        f'DTSTART:{_ics_timestamp(slot.start)}',
        f'DTEND:{_ics_timestamp(slot.end)}',
        f'SUMMARY:{_ics_escape(slot.poll.title)}',
        f'DESCRIPTION:{description}',
        'STATUS:CONFIRMED',
        'TRANSP:OPAQUE',
        'SEQUENCE:0',
        f'ORGANIZER;CN={organizer_name}:MAILTO:{organizer_email}',
    ]
    attendees = {}
    for invitation in slot.poll.invitations:
        voter = invitation.voter
        if not getattr(voter, 'email', None):
            continue
        attendee_email = f'{voter.email}@mahidol.ac.th'
        attendees[attendee_email.lower()] = _ics_param_escape(getattr(voter, 'fullname', voter.email))

    for attendee_email, attendee_name in attendees.items():
        lines.append(
            f'ATTENDEE;CN={attendee_name};CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:MAILTO:{attendee_email}'
        )

    lines.extend([
        'END:VEVENT',
        'END:VCALENDAR',
    ])
    return '\r\n'.join(lines).encode('utf-8')


def send_mail_with_attachments(recp, title, message, attachments=None):
    email_message = Message(subject=title, body=message, recipients=recp)
    for attachment in attachments or []:
        email_message.attach(
            filename=attachment['filename'],
            data=attachment['data'],
            content_type=attachment['content_type'],
            headers=attachment.get('headers'),
        )
    mail.send(email_message)


def send_mail_to_voters(poll, message, title, attachments=None):
    recipients = [f'{c.voter.email}@mahidol.ac.th' for c in poll.invitations]
    if current_app.debug:
        print(f'Mail sent to {recipients}. Message: {message}')
    else:
        if attachments:
            send_mail_with_attachments(recp=recipients, title=title, message=message, attachments=attachments)
        else:
            base_send_mail(recp=recipients, title=title, message=message)


def send_mail_to_unvoted_users(poll, message, title, attachments=None):
    recipients = [f'{c.voter.email}@mahidol.ac.th' for c in poll.invitations if not c.voted_at]
    if current_app.debug:
        print(f'Mail sent to {recipients}. Message: {message}')
    else:
        if attachments:
            send_mail_with_attachments(recp=recipients, title=title, message=message, attachments=attachments)
        else:
            base_send_mail(recp=recipients, title=title, message=message)


@besttime_bp.route('/')
def index():
    tab = request.args.get('tab')
    return render_template('besttime/poll-list.html', tab=tab)


@besttime_bp.route('/view/<int:poll_id>')
@login_required
def view_results(poll_id):
    tab = request.args.get('tab')
    slots = BestTimeDateTimeSlot.query.filter_by(poll_id=poll_id)
    return render_template('besttime/poll-results.html', slots=slots, tab=tab)


@besttime_bp.route('/messages/<int:poll_id>', methods=["GET", "POST"])
@login_required
def leave_message(poll_id):
    tab = request.args.get('tab')
    poll = BestTimePoll.query.get(poll_id)
    form = BestTimePollMessageForm()
    if request.method == "POST":
        if form.validate_on_submit():
            message = BestTimePollMessage(poll_id=poll_id)
            form.populate_obj(message)
            message.voter_id = current_user.id
            message.created_at = arrow.now('Asia/Bangkok').datetime
            db.session.add(message)
            db.session.commit()
            template = f'''
                        <article class="media">
                            <div class="media-content">
                                <div class="tag is-large is-light is-warning">
                                    {message.message}
                                </div>
                                <br/>
                                <p>
                                    <strong><small>{message.voter.fullname}</small></strong> <small>{message.created_at.astimezone(BKK_TZ).strftime('%d/%m/%Y %H:%M:%S')}</small>
                                </p>
                            </div>
                        </article>
            '''
            return template
        else:
            print(form.errors)
            resp = make_response()
            resp.headers["HX-Swap"] = "none"
            return resp

    return render_template('besttime/poll-message-form.html', poll=poll, form=form, tab=tab)


def add_datetime_slot_choices(form, datetime_slot_field):
    for _form_field in datetime_slot_field:
        choices = [dt for dt in
                   [(_form_field.date.data.strftime('%Y-%m-%d') + '#09:00 - 12:00', '09:00 - 12:00'),
                    (_form_field.date.data.strftime('%Y-%m-%d') + '#13:00 - 16:00', '13:00 - 16:00')]]
        _form_field.time_slots.choices = choices


@besttime_bp.route('/new', methods=['GET', 'POST'])
@login_required
def add_poll():
    tab = request.args.get('tab')
    form = BestTimePollForm()
    if request.method == 'POST':
        add_datetime_slot_choices(form, form.datetime_slots)
        if form.validate_on_submit():
            poll = BestTimePoll(creator=current_user)
            form.populate_obj(poll)
            chair_invitation = BestTimePollVote(voter=form.chairman.data, poll=poll, role='chairman')
            db.session.add(chair_invitation)
            for voter in form.invitees.data:
                if voter != form.chairman.data:
                    invitation = BestTimePollVote(voter=voter, poll=poll, role='committee')
                    db.session.add(invitation)
            for _form_field in form.datetime_slots:
                for t in _form_field.time_slots.data:
                    _start, _end = t.split('#')[1].split(' - ')
                    _start = _form_field.date.data.strftime('%Y-%m-%d') + ' ' + _start
                    _end = _form_field.date.data.strftime('%Y-%m-%d') + ' ' + _end
                    _start_datetime = datetime.datetime.strptime(_start, '%Y-%m-%d %H:%M')
                    _end_datetime = datetime.datetime.strptime(_end, '%Y-%m-%d %H:%M')
                    _start_datetime = _start_datetime.replace(tzinfo=BKK_TZ)
                    _end_datetime = _end_datetime.replace(tzinfo=BKK_TZ)
                    ds = BestTimeMasterDateTimeSlot(start=_start_datetime, end=_end_datetime, poll=poll)
                    db.session.add(ds)
            poll.created_at = arrow.now('Asia/Bangkok').datetime
            poll.start_date = None
            poll.end_date = None
            db.session.add(poll)
            db.session.commit()
            url = url_for('besttime.vote_poll', poll_id=poll.id, tab='voter', _external=True)
            msg = ('คำเชิญเลือกวันที่สะดวกสำหรับร่วมประชุม {}\n'
                   'กรุณาดำเนินการภายในวันที่ {}\n'
                   'คลิกลิ้งค์เพื่อดำเนินการ\n'
                   '{}'.format(poll.title, poll.vote_date_span, url)
                   )
            title = f'MUMT-MIS: ขอเชิญเลือกวันเพื่อประชุม {poll.title}'
            message = f'''
            เรียนกรรมการ
            
            ขอเชิญท่านเลือกวันที่สะดวกสำหรับร่วมประชุม {poll.title} ภายในวันที่ {poll.vote_date_span} โดยคลิกที่ลิงค์ด้านล่าง
            
            {url}
            
            ขอแสดงความนับถือ
            
            {poll.creator.fullname}
            '''
            send_mail_to_voters(poll=poll, title=title, message=message)
            if not current_app.debug:
                for c in poll.invitations:
                    try:
                        line_bot_api.push_message(to=c.voter.line_id, messages=TextSendMessage(text=msg))
                    except LineBotApiError:
                        pass
            else:
                print('msg', msg, 'user', [c.voter.line_id for c in poll.invitations])
            return redirect(url_for('besttime.index', tab=tab))
        else:
            return f'{form.errors}'
    return render_template('besttime/poll-setup-form.html', form=form, poll_id=None, tab=tab)


@besttime_bp.route('/api/preview_master_datetime_slots', methods=['POST'])
@login_required
def preview_master_datetime_slots():
    form = BestTimePollForm()
    poll_id = request.args.get('poll_id')
    start_date = form.start_date.data
    # end_date = form.end_date.data

    if start_date or poll_id:
        dates = set()
        date_set = set()
        for slot in form.datetime_slots:
            if slot.date.data:
                dates.add(slot.date.data)
        if start_date:
            dates.add(start_date)
        if poll_id:
            datetime_slots = BestTimeMasterDateTimeSlot.query.filter_by(poll_id=poll_id)
            date_set = set([datetime_slot.start.date() for datetime_slot in datetime_slots])
            dates.update(date_set)
        while len(form.datetime_slots) > 0:
            form.datetime_slots.pop_entry()
        for date in sorted(dates):
            form.datetime_slots.append_entry({'date': date})
        for _form_field in form.datetime_slots:
            selected = []
            choices = [dt for dt in
                        [(_form_field.date.data.strftime('%Y-%m-%d') + '#09:00 - 12:00', '09:00 - 12:00'),
                        (_form_field.date.data.strftime('%Y-%m-%d') + '#13:00 - 16:00', '13:00 - 16:00')]]
            _form_field.time_slots.choices = choices
            for h in vote_hours:
                hour_text = f'#{h.start.strftime("%H:%M")} - {h.end.strftime("%H:%M")}'
                hour_display = f'{h.start.strftime("%H:%M")} - {h.end.strftime("%H:%M")}'
                if poll_id:
                    start = datetime.datetime.combine(_form_field.date.data, h.start, tzinfo=BKK_TZ)
                    end = datetime.datetime.combine(_form_field.date.data, h.end, tzinfo=BKK_TZ)
                    _slot = BestTimeMasterDateTimeSlot.query \
                        .filter(BestTimeMasterDateTimeSlot.start == start,
                                BestTimeMasterDateTimeSlot.end == end,
                                BestTimeMasterDateTimeSlot.poll_id == poll_id).first()
                    if _slot:
                        selected.append((_form_field.date.data.strftime('%Y-%m-%d') + hour_text, hour_display))
                    elif _form_field.date.data not in date_set:
                        selected.append((_form_field.date.data.strftime('%Y-%m-%d') + hour_text, hour_display))
                else:
                    selected.append((_form_field.date.data.strftime('%Y-%m-%d') + hour_text, hour_display))

            _form_field.time_slots.data = [dt[0] for dt in selected]
        return render_template('besttime/datetime_slots_preview.html', form=form)
    else:
        return ''


# @besttime_bp.route('/api/preview-master-datetime-slots', methods=['POST'])
# @login_required
# def preview_master_datetime_slots():
#     form = BestTimePollForm()
#     poll_id = request.args.get('poll_id')
#     start_date = form.start_date.data
#     end_date = form.end_date.data
#
#     while len(form.datetime_slots) > 0:
#         form.datetime_slots.pop_entry()
#
#     if (start_date and end_date) and start_date < end_date:
#         current = start_date
#         delta = datetime.timedelta(days=1)
#
#         while current <= end_date:
#             if calendar.weekday(current.year, current.month, current.day) < 5:
#                 form.datetime_slots.append_entry({'date': current})
#             current += delta
#             for _form_field in form.datetime_slots:
#                 selected = []
#                 choices = [dt for dt in
#                            [(_form_field.date.data.strftime('%Y-%m-%d') + '#09:00 - 12:00', '09:00 - 12:00'),
#                             (_form_field.date.data.strftime('%Y-%m-%d') + '#13:00 - 16:00', '13:00 - 16:00')]]
#                 _form_field.time_slots.choices = choices
#                 # Preselect all choices so that the users will only need to uncheck the choice that is not good for them.
#                 for h in vote_hours:
#                     hour_text = f'#{h.start.strftime("%H:%M")} - {h.end.strftime("%H:%M")}'
#                     hour_display = f'{h.start.strftime("%H:%M")} - {h.end.strftime("%H:%M")}'
#                     if poll_id:
#                         start = datetime.datetime.combine(_form_field.date.data, h.start, tzinfo=BKK_TZ)
#                         end = datetime.datetime.combine(_form_field.date.data, h.end, tzinfo=BKK_TZ)
#                         _slot = BestTimeMasterDateTimeSlot.query \
#                             .filter(BestTimeMasterDateTimeSlot.start == start,
#                                     BestTimeMasterDateTimeSlot.end == end,
#                                     BestTimeMasterDateTimeSlot.poll_id == poll_id).first()
#                         if _slot:
#                             selected.append((_form_field.date.data.strftime('%Y-%m-%d') + hour_text, hour_display))
#                     else:
#                         selected.append((_form_field.date.data.strftime('%Y-%m-%d') + hour_text, hour_display))
#                 _form_field.time_slots.data = [dt[0] for dt in selected]
#
#         return render_template('besttime/datetime_slots_preview.html', form=form)
#     else:
#         return ''


@besttime_bp.route('/edit/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def edit_poll(poll_id):
    tab = request.args.get('tab')
    poll = BestTimePoll.query.get(poll_id)
    old_vote_start_date = arrow.get(poll.vote_start_date, 'Asia/Bangkok').date()
    old_vote_end_date = arrow.get(poll.vote_end_date, 'Asia/Bangkok').date()
    if request.method == 'GET':
        form = BestTimePollForm(obj=poll)
        form.chairman.data = BestTimePollVote.query.filter_by(poll=poll, role='chairman').first().voter
        form.invitees.data = [inv.voter for inv in BestTimePollVote.query.filter_by(poll=poll)
                              if inv.voter != form.chairman.data]
    else:
        form = BestTimePollForm()

    add_datetime_slot_choices(form, form.datetime_slots)

    if request.method == 'POST':
        if form.validate_on_submit():
            invitations = [i.voter for i in poll.invitations]
            chairman = poll.get_chairman()
            form.populate_obj(poll)
            for invitee in form.invitees.data:
                if not BestTimePollVote.query.filter_by(voter=invitee, poll=poll).first():
                    invitation = BestTimePollVote(voter=invitee, poll=poll)
                    db.session.add(invitation)
            for voter in invitations:
                # Check for removed voters
                if voter not in form.invitees.data and voter != chairman:
                    vote = BestTimePollVote.query.filter_by(voter=voter, poll=poll).first()
                    if vote:
                        db.session.delete(vote)

            poll.master_datetime_slots = []
            for _form_field in form.datetime_slots:
                for t in _form_field.time_slots.data:
                    _start, _end = t.split('#')[1].split(' - ')
                    _start = _form_field.date.data.strftime('%Y-%m-%d') + ' ' + _start
                    _end = _form_field.date.data.strftime('%Y-%m-%d') + ' ' + _end
                    _start_datetime = datetime.datetime.strptime(_start, '%Y-%m-%d %H:%M')
                    _end_datetime = datetime.datetime.strptime(_end, '%Y-%m-%d %H:%M')
                    _start_datetime = _start_datetime.replace(tzinfo=BKK_TZ)
                    _end_datetime = _end_datetime.replace(tzinfo=BKK_TZ)
                    ds = BestTimeMasterDateTimeSlot.query \
                        .filter(BestTimeMasterDateTimeSlot.start == _start_datetime,
                                BestTimeMasterDateTimeSlot.end == _end_datetime,
                                BestTimeMasterDateTimeSlot.poll_id == poll.id).first()
                    if not ds:
                        ds = BestTimeMasterDateTimeSlot(start=_start_datetime, end=_end_datetime, poll=poll)
                    db.session.add(ds)
            poll.modified_at = arrow.now('Asia/Bangkok').datetime
            poll.start_date = None
            poll.end_date = None
            db.session.add(poll)
            db.session.commit()
            new_vote_start_date = arrow.get(poll.vote_start_date, 'Asia/Bangkok').date()
            new_vote_end_date = arrow.get(poll.vote_end_date, 'Asia/Bangkok').date()
            url = url_for('besttime.vote_poll', poll_id=poll.id, tab='voter', _external=True)
            if (old_vote_start_date != new_vote_start_date) or (old_vote_end_date != new_vote_end_date):
                msg = ('โพลสำรวจวันประชุม {} มีการขยายระยะเวลาสำรวจวันประชุม\n'
                       'กรุณาดำเนินการภายในวันที่ {}\n'
                       'คลิกลิ้งค์เพื่อดำเนินการ\n'
                       '{}'.format(poll.title, poll.vote_date_span, url)
                       )
                title = f'MUMT-MIS: แจ้งขยายระยะเวลาโพลสำรวจวันเพื่อประชุม {poll.title}'
                message = f'''
                            เรียนกรรมการ

                            เนื่องจากมีการขยายระยะเวลาสำรวจวันประชุมจึง
                            ขอความกรุณาท่านเลือกวันที่สะดวกสำหรับร่วมประชุม {poll.title} ภายในวันที่ {poll.vote_date_span} โดยคลิกที่ลิงค์ด้านล่าง

                            {url}

                            ด้วยความเคารพ

                            {poll.creator.fullname}
                            '''
                send_mail_to_unvoted_users(poll=poll, title=title, message=message)
                if not current_app.debug:
                    for c in poll.invitations:
                        if not c.voted_at:
                            try:
                                line_bot_api.push_message(to=c.voter.line_id, messages=TextSendMessage(text=msg))
                            except LineBotApiError:
                                pass
                else:
                    print('msg', msg, 'user', [c.voter.line_id for c in poll.invitations if not c.voted_at])
            else:
                msg = ('โพลสำรวจวันประชุม {} มีการเปลี่ยนแปลง\n'
                       'กรุณาดำเนินการภายในวันที่ {}\n'
                       'คลิกลิ้งค์เพื่อดำเนินการ\n'
                       '{}'.format(poll.title, poll.vote_date_span, url)
                       )
                title = f'MUMT-MIS: แจ้งเปลี่ยนแปลงโพลสำรวจวันเพื่อประชุม {poll.title}'
                message = f'''
                เรียนกรรมการ
    
                เนื่องจากมีการเปลี่ยนแปลงโพลสำรวจวันประชุมจึง
                ขอความกรุณาท่านเลือกวันที่สะดวกสำหรับร่วมประชุม {poll.title} ภายในวันที่ {poll.vote_date_span} โดยคลิกที่ลิงค์ด้านล่าง
    
                {url}
    
                ด้วยความเคารพ
    
                {poll.creator.fullname}
                '''
                send_mail_to_voters(poll=poll, title=title, message=message)
                if not current_app.debug:
                    for c in poll.invitations:
                        try:
                            line_bot_api.push_message(to=c.voter.line_id, messages=TextSendMessage(text=msg))
                        except LineBotApiError:
                            pass
                else:
                    print('msg', msg, 'user', [c.voter.line_id for c in poll.invitations])
            return redirect(url_for('besttime.index', tab=tab))
        else:
            return f'{form.errors}'
    return render_template('besttime/poll-setup-form.html', form=form, poll_id=poll_id, tab=tab)


@besttime_bp.route('/delete/<int:poll_id>', methods=['DELETE'])
@login_required
def delete_poll(poll_id):
    tab = request.args.get('tab')
    poll = BestTimePoll.query.get(poll_id)
    db.session.delete(poll)
    db.session.commit()
    flash(f'ลบแบบสำรวจเรียบร้อยแล้ว', 'success')
    resp = make_response()
    resp.headers['HX-Redirect'] = url_for('besttime.index', tab=tab)
    return resp


@besttime_bp.route('/close/<int:poll_id>')
@login_required
def close_poll(poll_id):
    tab = request.args.get('tab')
    poll = BestTimePoll.query.get(poll_id)
    poll.closed_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(poll)
    db.session.commit()
    return redirect(url_for('besttime.index', tab=tab))


@besttime_bp.route('/vote/polls/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def vote_poll(poll_id):
    tab = request.args.get('tab')
    poll = BestTimePoll.query.get(poll_id)
    today = arrow.now('Asia/Bangkok').date()
    if today < poll.vote_start_date or today > poll.vote_end_date:
        flash('ขณะนี้ไม่อยู่ในช่วงระยะเวลาการโหวตของแบบสำรวจ กรุณาตรวจสอบวันที่เปิดโหวตอีกครั้ง', 'danger')
        return redirect(url_for('besttime.index', tab=tab))
    elif poll.closed_at:
        flash('แบบสำรวจนี้ปิดการโหวตแล้ว', 'warning')
        return redirect(url_for('besttime.index', tab=tab))
    # If the user has already voted this poll
    vote = BestTimePollVote.query.filter_by(poll_id=poll_id, voter=current_user).first()
    form = BestTimePollVoteForm()
    message_form = BestTimePollMessageForm()
    if request.method == 'POST':
        if not vote:
            vote = BestTimePollVote(poll=poll, voter=current_user)
        else:
            vote.datetime_slots = []
        for _form_field in form.date_time_slots:
            for t in _form_field.time_slots.data:
                _start, _end = t.split('#')[1].split(' - ')
                _start = _form_field.date.data.strftime('%Y-%m-%d') + ' ' + _start
                _end = _form_field.date.data.strftime('%Y-%m-%d') + ' ' + _end
                _start_datetime = datetime.datetime.strptime(_start, '%Y-%m-%d %H:%M')
                _end_datetime = datetime.datetime.strptime(_end, '%Y-%m-%d %H:%M')
                _start_datetime = _start_datetime.replace(tzinfo=BKK_TZ)
                _end_datetime = _end_datetime.replace(tzinfo=BKK_TZ)
                ds = BestTimeDateTimeSlot.query \
                    .filter(BestTimeDateTimeSlot.start == _start_datetime,
                            BestTimeDateTimeSlot.end == _end_datetime,
                            BestTimeDateTimeSlot.poll_id == poll_id).first()
                if not ds:
                    ds = BestTimeDateTimeSlot(start=_start_datetime, end=_end_datetime, poll_id=poll_id)
                vote.datetime_slots.append(ds)
                db.session.add(ds)
        vote.voted_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(vote)
        db.session.commit()
        if poll.is_completed:
            url = url_for('besttime.view_results', poll_id=poll.id, tab=tab, _external=True)
            if poll.has_valid_slots:
                msg = ('ขณะนี้กรรมการได้โหวตเพื่อประชุม {} ครบแล้ว\n'
                       'กรุณาดำเนินการพิจารณาผลการโหวตเพื่อนัดประชุมต่อไป\n'
                       'คลิกลิ้งค์เพื่อดำเนินการ\n'
                       '{}'.format(poll.title, url)
                       )
                title = f'MUMT-MIS: แจ้งพิจาณาผลการโหวตเพื่อประชุม {poll.title}'
                message = f'''
                เรียนกรรมการ

                บัดนี้กรรมการได้โหวตเพื่อประชุม {poll.title} ครบแล้ว ขอเชิญท่านพิจารณาผลการโหวตเพื่อนัดประชุมต่อไปโดยคลิกที่ลิงค์ด้านล่าง

                {url}

                ด้วยความเคารพ

                {poll.creator.fullname}
                '''
                recipients = [f'{poll.creator.email}@mahidol.ac.th']
            else:
                msg = ('ขณะนี้กรรมการได้โหวตเพื่อประชุม {} ครบแล้ว แต่ไม่มีช่วงเวลาที่เหมาะสม\n'
                       'กรุณาดำเนินการพิจารณาแก้ไขโพลเพื่อโหวตเพิ่มเติม\n'
                       'คลิกลิ้งค์เพื่อดำเนินการ\n'
                       '{}'.format(poll.title, url)
                       )
                title = f'MUMT-MIS: แจ้งพิจาณาผลการโหวตเพื่อประชุม {poll.title}'
                message = f'''
                เรียนกรรมการ

                บัดนี้กรรมการได้โหวตเพื่อประชุม {poll.title} ครบแล้ว แต่ไม่มีช่วงเวลาที่เหมาะสม จึงขอเชิญท่านพิจารณาแก้ไขโพลเพื่อโหวตเพิ่มเติม โดยคลิกที่ลิงค์ด้านล่าง

                {url}

                ด้วยความเคารพ

                {poll.creator.fullname}
                '''
                recipients = [f'{poll.creator.email}@mahidol.ac.th']
            if current_app.debug:
                print(f'Line sent to {poll.creator.line_id}. Message: {msg}')
                print(f'Mail sent to {recipients}. Message: {message}')
            else:
                send_mail(recp=recipients, title=title, message=message)
                try:
                    line_bot_api.push_message(to=poll.creator.line_id, messages=TextSendMessage(text=msg))
                except LineBotApiError:
                    pass

        return redirect(url_for('besttime.index', tab=tab))

    if request.method == 'GET':
        if vote:
            voted_time_slots = [t.start.astimezone(BKK_TZ).strftime('%Y-%m-%d#%H:%M - ')
                                + t.end.astimezone(BKK_TZ).strftime('%H:%M')
                                for t in vote.datetime_slots]

        dates = set()
        for slot in poll.master_datetime_slots:
            if slot.start.astimezone(BKK_TZ).date() not in dates:
                form.date_time_slots.append_entry({'date': slot.start.astimezone(BKK_TZ).date()})
                dates.add(slot.start.date())

        for _form_field in form.date_time_slots:
            choices = []
            for h in vote_hours:
                start = datetime.datetime.combine(_form_field.date.data, h.start, tzinfo=BKK_TZ)
                end = datetime.datetime.combine(_form_field.date.data, h.end, tzinfo=BKK_TZ)
                _slot = BestTimeMasterDateTimeSlot.query \
                    .filter(BestTimeMasterDateTimeSlot.start == start,
                            BestTimeMasterDateTimeSlot.end == end,
                            BestTimeMasterDateTimeSlot.poll_id == poll_id).first()
                if _slot:
                    hour_text = f'#{h.start.strftime("%H:%M")} - {h.end.strftime("%H:%M")}'
                    hour_display = f'{h.start.strftime("%H:%M")} - {h.end.strftime("%H:%M")}'
                    choices.append((_form_field.date.data.strftime('%Y-%m-%d') + hour_text, hour_display))
            _form_field.time_slots.choices = choices
            _form_field.time_slots.data = []
            if vote:
                _form_field.time_slots.data = [t[0] for t in choices if t[0] in voted_time_slots]

    return render_template('besttime/poll-form.html', form=form, poll=poll, tab=tab, message_form=message_form)


@besttime_bp.route('/vote/<int:slot_id>/mail', methods=['GET', 'POST'])
def send_mail_to_committee(slot_id):
    tab = request.args.get('tab')
    slot = BestTimeDateTimeSlot.query.get(slot_id)
    form = BestTimeMailForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            old_slot = BestTimeDateTimeSlot.query.filter_by(is_best=True).first()
            if old_slot:
                old_slot.is_best = False
                db.session.add(old_slot)
            slot.is_best = True
            slot.poll.closed_at = arrow.now('Asia/Bangkok').datetime
            db.session.add(slot)
            db.session.commit()
            msg = 'ขอแจ้งสรุปวันประชุม "{}" โดยกำหนดเป็นวันที่ {}'.format(slot.poll.title, slot)
            title = f'แจ้งสรุปวันประชุมจากผลการโหวต {slot.poll.title}'
            send_mail_to_voters(
                slot.poll,
                form.message.data,
                title,
                attachments=[{
                    'filename': f'besttime-poll-{slot.poll.id}-slot-{slot.id}.ics',
                    'data': build_besttime_slot_ics(slot),
                    'content_type': 'text/calendar; charset=utf-8; method=REQUEST',
                    'headers': [('Content-Class', 'urn:content-classes:calendarmessage')],
                }],
            )
            if not current_app.debug:
                for c in slot.poll.invitations:
                    try:
                        line_bot_api.push_message(to=c.voter.line_id, messages=TextSendMessage(text=msg))
                    except LineBotApiError:
                        pass
            else:
                print('msg', msg, 'user', [c.voter.line_id for c in slot.poll.invitations])
            flash(f'ส่งอีเมลเพื่อแจ้งกรรมการเรียบร้อย', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    form.message.data = f'''เรียนกรรมการทุกท่าน\n\nขอแจ้งสรุปวันประชุม {slot.poll.title} เป็นวันที่ {slot}\n\nขอแสดงความนับถือ\n\n{slot.poll.creator.fullname}'''
    return render_template('besttime/modals/mail_form.html',
                           form=form, slot_id=slot_id, poll=slot.poll, tab=tab)
