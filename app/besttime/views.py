from calendar import calendar
from collections import defaultdict, namedtuple

from flask import render_template, request, redirect, url_for
from flask_login import login_required, current_user
import arrow

from app.besttime import besttime_bp
from app.besttime.forms import BestTimePollMessageForm, BestTimePollForm, BestTimePollVoteForm
from app.besttime.models import *

from zoneinfo import ZoneInfo
import datetime


VoteHour = namedtuple('VoteHour', ['start', 'end'])

BKK_TZ = ZoneInfo('Asia/Bangkok')

vote_hours = [VoteHour(datetime.time(9, 0, 0, tzinfo=BKK_TZ),
                       datetime.time(12, 0, 0, tzinfo=BKK_TZ)),
              VoteHour(datetime.time(13, 0, 0, tzinfo=BKK_TZ),
                       datetime.time(16, 0, 0, tzinfo=BKK_TZ)),
              ]


@besttime_bp.route('/')
def index():
    return render_template('besttime/poll-list.html')


@besttime_bp.route('/view/<int:poll_id>')
@login_required
def view_results(poll_id):
    vote_summary = defaultdict(list)
    for slot in BestTimeDateTimeSlot.query.filter_by(poll_id=poll_id):
        for vote in slot.poll_votes:
            vote_summary[slot].append(vote.voter.name)
    return render_template('besttime/poll-results.html', votes=vote_summary)


@besttime_bp.route('/messages/<int:poll_id>', methods=["GET", "POST"])
@login_required
def leave_message(poll_id):
    poll = BestTimePoll.query.get(poll_id)
    form = BestTimePollMessageForm()
    if form.validate_on_submit():
        message = BestTimePollMessage(poll_id=poll_id)
        form.populate_obj(message)
        message.voter_id = current_user.id
        message.created_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(message)
        db.session.commit()
        return redirect(url_for('besttime.index'))
    else:
        print(form.errors)
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
            for user in form.invitees.data:
                invitation = BestTimePollVote(voter=user, poll=poll, role='committee')
                db.session.add(invitation)
            for _form_field in form.datetime_slots:
                for t in _form_field.time_slots.data:
                    _start, _end = t.split('#')[1].split(' - ')
                    _start = _form_field.date.data.strftime('%Y-%m-%d') + ' ' + _start
                    _end = _form_field.date.data.strftime('%Y-%m-%d') + ' ' + _end
                    _start_datetime = datetime.datetime.strptime(_start, '%Y-%m-%d %H:%M').astimezone(tz=BKK_TZ)
                    _end_datetime = datetime.datetime.strptime(_end, '%Y-%m-%d %H:%M').astimezone(tz=BKK_TZ)
                    ds = BestTimeMasterDateTimeSlot.query.filter_by(start=_start_datetime,
                                                            end=_end_datetime,
                                                            poll=poll).first()
                    if not ds:
                        ds = BestTimeMasterDateTimeSlot(start=_start_datetime, end=_end_datetime, poll=poll)
                    db.session.add(ds)
            poll.created_at = datetime.datetime.now().astimezone(tz=BKK_TZ)
            db.session.add(poll)
            db.session.commit()
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
                choices = [dt for dt in [(_form_field.date.data.strftime('%Y-%m-%d') + '#09:00 - 12:00', '09:00 - 12:00'),
                                         (_form_field.date.data.strftime('%Y-%m-%d') + '#13:00 - 16:00', '13:00 - 16:00')]]
                _form_field.time_slots.choices = choices
                # Preselect all choices so that the users will only need to uncheck the choice that is not good for them.
                for h in vote_hours:
                    hour_text = f'#{h.start.strftime("%H:%M")} - {h.end.strftime("%H:%M")}'
                    hour_display = f'{h.start.strftime("%H:%M")} - {h.end.strftime("%H:%M")}'
                    if poll_id:
                        start = datetime.datetime.combine(_form_field.date.data, h.start)
                        end = datetime.datetime.combine(_form_field.date.data, h.end)
                        _slot = BestTimeMasterDateTimeSlot.query.filter_by(start=start, end=end, poll_id=poll_id).first()
                        if _slot:
                            selected.append((_form_field.date.data.strftime('%Y-%m-%d') + hour_text, hour_display))
                    else:
                        selected.append((_form_field.date.data.strftime('%Y-%m-%d') + hour_text, hour_display))
                _form_field.time_slots.data = [dt[0] for dt in selected]

        return str(form.datetime_slots)

        return render_template('besttime/datetime_slots_preview.html', form=form)
    else:
        return ''


@besttime_bp.route('/edit/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def edit_poll(poll_id):
    poll = BestTimePoll.query.get(poll_id)
    form = BestTimePollForm(obj=poll)
    add_datetime_slot_choices(form, form.datetime_slots)
    form.chairman.data = BestTimePollVote.query.filter_by(poll=poll, role='chairman').first().voter
    form.invitees.data = [inv.voter for inv in BestTimePollVote.query.filter_by(poll=poll)]

    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(poll)
            for user in form.invitees.data:
                # Check for new invitees.
                if not BestTimePollVote.query.filter_by(voter=user, poll=poll).first():
                    invitation = BestTimePollVote(voter=user, poll=poll)
                    db.session.add(invitation)
            # TODO: send email to notify all invitees.
            for _form_field in form.datetime_slots:
                for t in _form_field.time_slots.data:
                    _start, _end = t.split('#')[1].split(' - ')
                    _start = _form_field.date.data.strftime('%Y-%m-%d') + ' ' + _start
                    _end = _form_field.date.data.strftime('%Y-%m-%d') + ' ' + _end
                    _start_datetime = datetime.datetime.strptime(_start, '%Y-%m-%d %H:%M').astimezone(tz=BKK_TZ)
                    _end_datetime = datetime.datetime.strptime(_end, '%Y-%m-%d %H:%M').astimezone(tz=BKK_TZ)
                    ds = BestTimeMasterDateTimeSlot.query.filter_by(start=_start_datetime,
                                                            end=_end_datetime,
                                                            poll=poll).first()
                    if not ds:
                        ds = BestTimeMasterDateTimeSlot(start=_start_datetime, end=_end_datetime, poll=poll)
                    db.session.add(ds)
            poll.modified_at = datetime.datetime.now().astimezone(tz=BKK_TZ)
            db.session.add(poll)
            db.session.commit()
            return redirect(url_for('besttime.index'))
        else:
            return f'{form.errors}'
    return render_template('besttime/poll-setup-form.html', form=form, poll_id=poll_id)


@besttime_bp.route('/delete/<int:poll_id>')
@login_required
def delete_poll(poll_id):
    poll = BestTimePoll.query.get(poll_id)
    db.session.delete(poll)
    db.session.commit()
    return redirect(url_for('besttime.index'))


@besttime_bp.route('/close/<int:poll_id>')
@login_required
def close_poll(poll_id):
    poll = BestTimePoll.query.get(poll_id)
    poll.closed_at = datetime.datetime.now().astimezone(tz=BKK_TZ)
    db.session.add(poll)
    db.session.commit()
    return redirect(url_for('besttime.index'))


@besttime_bp.route('/vote/polls/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def vote_poll(poll_id):
    poll = BestTimePoll.query.get(poll_id)
    # If the user has already voted this poll
    vote = BestTimePollVote.query.filter_by(poll_id=poll_id, voter=current_user).first()
    form = BestTimePollVoteForm()
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
                _start_datetime = datetime.datetime.strptime(_start, '%Y-%m-%d %H:%M').astimezone(tz=BKK_TZ)
                _end_datetime = datetime.datetime.strptime(_end, '%Y-%m-%d %H:%M').astimezone(tz=BKK_TZ)
                ds = BestTimeDateTimeSlot.query.filter_by(start=_start_datetime, end=_end_datetime, poll_id=poll_id).first()
                if not ds:
                    ds = BestTimeDateTimeSlot(start=_start_datetime, end=_end_datetime, poll_id=poll_id)
                vote.datetime_slots.append(ds)
                db.session.add(ds)
        vote.voted_at = datetime.datetime.now().astimezone(tz=BKK_TZ)
        db.session.add(vote)
        db.session.commit()
        return redirect(url_for('besttime.index'))

    if request.method == 'GET':
        if vote:
            voted_time_slots = [t.start.strftime('%Y-%m-%d#%H:%M - ') + t.end.strftime('%H:%M')
                                for t in vote.datetime_slots]

        dates = set()
        for slot in poll.active_master_datetime_slots.all():
            if slot.start.date() not in dates:
                form.date_time_slots.append_entry({'date': slot.start.date()})
                dates.add(slot.start.date())

        for _form_field in form.date_time_slots:
            choices = []
            for h in vote_hours:
                start = datetime.datetime.combine(_form_field.date.data, h.start)
                end = datetime.datetime.combine(_form_field.date.data, h.end)
                _slot = BestTimeMasterDateTimeSlot.query.filter_by(start=start, end=end, poll_id=poll_id).first()
                if _slot:
                    hour_text = f'#{h.start.strftime("%H:%M")} - {h.end.strftime("%H:%M")}'
                    hour_display = f'{h.start.strftime("%H:%M")} - {h.end.strftime("%H:%M")}'
                    choices.append((_form_field.date.data.strftime('%Y-%m-%d') + hour_text, hour_display))
            _form_field.time_slots.choices = choices
            _form_field.time_slots.data = []
            if vote:
                _form_field.time_slots.data = [t[0] for t in choices if t[0] in voted_time_slots]

    return render_template('besttime/poll-form.html', form=form, poll=poll)