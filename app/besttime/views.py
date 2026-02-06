import calendar
import datetime
from collections import namedtuple

import arrow
from flask import render_template, request, redirect, url_for, current_app, make_response, flash
from flask_login import login_required, current_user

from app.besttime import besttime_bp
from app.besttime.forms import BestTimePollMessageForm, BestTimePollForm, BestTimePollVoteForm, BestTimeMailForm
from app.besttime.models import *
from app.staff.views import send_mail

VoteHour = namedtuple('VoteHour', ['start', 'end'])

BKK_TZ = ZoneInfo('Asia/Bangkok')

vote_hours = [VoteHour(datetime.time(9, 0, 0, tzinfo=BKK_TZ),
                       datetime.time(12, 0, 0, tzinfo=BKK_TZ)),
              VoteHour(datetime.time(13, 0, 0, tzinfo=BKK_TZ),
                       datetime.time(16, 0, 0, tzinfo=BKK_TZ)),
              ]


def send_mail_to_voters(poll, message, title):
    recipients = [f'{c.voter.email}@mahidol.ac.th' for c in poll.invitations]
    if current_app.debug:
        print(f'Mail sent to {recipients}. Message: {message}')
    else:
        send_mail(recp=recipients, title=title, message=message)


@besttime_bp.route('/')
def index():
    return render_template('besttime/poll-list.html')


@besttime_bp.route('/view/<int:poll_id>')
@login_required
def view_results(poll_id):
    slots = BestTimeDateTimeSlot.query.filter_by(poll_id=poll_id)
    return render_template('besttime/poll-results.html', slots=slots)


@besttime_bp.route('/messages/<int:poll_id>', methods=["GET", "POST"])
@login_required
def leave_message(poll_id):
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

    return render_template('besttime/poll-message-form.html', poll=poll, form=form)


def add_datetime_slot_choices(form, datetime_slot_field):
    for _form_field in datetime_slot_field:
        choices = [dt for dt in
                   [(_form_field.date.data.strftime('%Y-%m-%d') + '#09:00 - 12:00', '09:00 - 12:00'),
                    (_form_field.date.data.strftime('%Y-%m-%d') + '#13:00 - 16:00', '13:00 - 16:00')]]
        _form_field.time_slots.choices = choices


@besttime_bp.route('/new', methods=['GET', 'POST'])
@login_required
def add_poll():
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
            db.session.add(poll)
            db.session.commit()
            url = url_for('besttime.vote_poll', poll_id=poll.id, _external=True)
            title = f'MUMT-MIS: ขอเชิญเลือกวันเพื่อประชุม {poll.title}'
            message = f'''
            เรียนกรรมการ
            
            ขอเชิญท่านเลือกวันที่สะดวกสำหรับร่วมประชุม {poll.title} ภายในวันที่ {poll.date_span} โดยคลิกที่ลิงค์ด้านล่าง
            
            {url}
            
            ขอแสดงความนับถือ
            
            {poll.creator.fullname}
            '''
            send_mail_to_voters(poll=poll, title=title, message=message)
            return redirect(url_for('besttime.index'))
        else:
            return f'{form.errors}'
    return render_template('besttime/poll-setup-form.html', form=form)


@besttime_bp.route('/api/preview-master-datetime-slots', methods=['POST'])
@login_required
def preview_master_datetime_slots():
    form = BestTimePollForm()
    poll_id = request.args.get('poll_id')
    start_date = form.start_date.data
    end_date = form.end_date.data

    while len(form.datetime_slots) > 0:
        form.datetime_slots.pop_entry()

    if (start_date and end_date) and start_date < end_date:
        current = start_date
        delta = datetime.timedelta(days=1)

        while current <= end_date:
            if calendar.weekday(current.year, current.month, current.day) < 5:
                form.datetime_slots.append_entry({'date': current})
            current += delta
            for _form_field in form.datetime_slots:
                selected = []
                choices = [dt for dt in
                           [(_form_field.date.data.strftime('%Y-%m-%d') + '#09:00 - 12:00', '09:00 - 12:00'),
                            (_form_field.date.data.strftime('%Y-%m-%d') + '#13:00 - 16:00', '13:00 - 16:00')]]
                _form_field.time_slots.choices = choices
                # Preselect all choices so that the users will only need to uncheck the choice that is not good for them.
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
                    else:
                        selected.append((_form_field.date.data.strftime('%Y-%m-%d') + hour_text, hour_display))
                _form_field.time_slots.data = [dt[0] for dt in selected]

        return render_template('besttime/datetime_slots_preview.html', form=form)
    else:
        return ''


@besttime_bp.route('/edit/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def edit_poll(poll_id):
    poll = BestTimePoll.query.get(poll_id)
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
                # Check for new invitees.
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
            db.session.add(poll)
            db.session.commit()
            url = url_for('besttime.vote_poll', poll_id=poll.id, _external=True)
            title = f'MUMT-MIS: แจ้งเปลี่ยนแปลงโพลสำรวจวันเพื่อประชุม {poll.title}'
            message = f'''
            เรียนกรรมการ

            เนื่องจากมีการเปลี่ยนแปลงโพลสำรวจวันประชุมจึง
            ขอความกรุณาท่านเลืิอกวันที่สะดวกสำหรับร่วมประชุม {poll.title} ภายในวันที่ {poll.date_span} โดยคลิกที่ลิงค์ด้านล่าง

            {url}

            ด้วยความเคารพ

            {poll.creator.fullname}
            '''
            send_mail_to_voters(poll=poll, title=title, message=message)
            return redirect(url_for('besttime.index'))
        else:
            return f'{form.errors}'
    return render_template('besttime/poll-setup-form.html', form=form, poll_id=poll_id)


@besttime_bp.route('/delete/<int:poll_id>', methods=['DELETE'])
@login_required
def delete_poll(poll_id):
    poll = BestTimePoll.query.get(poll_id)
    db.session.delete(poll)
    db.session.commit()
    flash(f'ลบแบบสำรวจเรียบร้อยแล้ว', 'success')
    resp = make_response()
    resp.headers['HX-Redirect'] = url_for('besttime.index')
    return resp


@besttime_bp.route('/close/<int:poll_id>')
@login_required
def close_poll(poll_id):
    poll = BestTimePoll.query.get(poll_id)
    poll.closed_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(poll)
    db.session.commit()
    return redirect(url_for('besttime.index'))


@besttime_bp.route('/vote/polls/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def vote_poll(poll_id):
    poll = BestTimePoll.query.get(poll_id)
    today = arrow.now('Asia/Bangkok').date()
    if today < poll.vote_start_date or today > poll.vote_end_date:
        flash('ขณะนี้ไม่อยู่ในช่วงระยะเวลาการโหวตของแบบสำรวจ กรุณาตรวจสอบวันที่เปิดโหวตอีกครั้ง', 'danger')
        return redirect(url_for('besttime.index'))
    elif poll.closed_at:
        flash('แบบสำรวจนี้ปิดการโหวตแล้ว', 'warning')
        return redirect(url_for('besttime.index'))
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
            url = url_for('besttime.view_results', poll_id=poll.id, _external=True)
            if poll.has_valid_slots:
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
                print(f'Mail sent to {recipients}. Message: {message}')
            else:
                send_mail(recp=recipients, title=title, message=message)

        return redirect(url_for('besttime.index'))

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

    return render_template('besttime/poll-form.html', form=form, poll=poll, message_form=message_form)


@besttime_bp.route('/vote/<int:slot_id>/mail', methods=['GET', 'POST'])
def send_mail_to_committee(slot_id):
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
            title = f'แจ้งสรุปวันประชุมจากผลการโหวต {slot.poll.title}'
            send_mail_to_voters(slot.poll, form.message.data, title)
            flash(f'ส่งอีเมลเพื่อแจ้งกรรมการเรียบร้อย', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    form.message.data = f'''เรียนกรรมการทุกท่าน\n\nขอแจ้งสรุปวันประชุม {slot.poll.title} เป็นวันที่ {slot}\n\nขอแสดงความนับถือ\n\n{slot.poll.creator.fullname}'''
    return render_template('besttime/modals/mail_form.html',
                           form=form, slot_id=slot_id, poll=slot.poll)
