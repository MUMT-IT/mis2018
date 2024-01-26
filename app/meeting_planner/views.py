import datetime
from typing import Union

import arrow
import pytz
from flask import (render_template, make_response, request,
                   redirect, url_for, flash, jsonify, current_app)
from flask_login import login_required, current_user
from app.meeting_planner import meeting_planner
from app.meeting_planner.forms import *
from app.meeting_planner.models import *
from app.staff.models import StaffPersonalInfo
from app.main import mail
from flask_mail import Message
from sqlalchemy import select

localtz = pytz.timezone('Asia/Bangkok')


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


@meeting_planner.route('/')
@login_required
def index():
    return render_template('meeting_planner/index.html')


@meeting_planner.route('/meetings/new', methods=['GET', 'POST'])
@meeting_planner.route('/meetings/new_meeting/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def create_meeting(poll_id=None):
    if poll_id:
        MeetingEventForm = create_new_meeting(poll_id)
        form = MeetingEventForm()
        start = form.start.data.astimezone(localtz).isoformat() if form.start.data else None
        end = form.end.data.astimezone(localtz).isoformat() if form.end.data else None
    else:
        MeetingEventForm = create_new_meeting()
        form = MeetingEventForm()
        start = form.start.data.astimezone(localtz).isoformat() if form.start.data else None
        end = form.end.data.astimezone(localtz).isoformat() if form.end.data else None
    if poll_id:
        poll = MeetingPoll.query.filter_by(id=poll_id).first()
        for p in poll.poll_result:
            form.start.data = p.item.start
            form.end.data = p.item.end
        form.title.data = poll.poll_name
        form.participant.data = poll.participants
    if form.validate_on_submit():
        form.start.data = arrow.get(form.start.data, 'Asia/Bangkok').datetime
        form.end.data = arrow.get(form.end.data, 'Asia/Bangkok').datetime
        for event_form in form.meeting_events:
            if event_form.room.data:
                event_form.start.data = form.start.data
                event_form.end.data = form.end.data
                event_form.title.data = f'ประชุม{form.title.data}'
        new_meeting = MeetingEvent()
        form.populate_obj(new_meeting)
        if poll_id:
            for staff_id in form.participant.data:
                staff = StaffPersonalInfo.query.get(staff_id.id)
                invitation = MeetingInvitation(staff_id=staff.staff_account.id,
                                               created_at=new_meeting.start,
                                               meeting=new_meeting)
                new_meeting.poll_id = poll_id
                db.session.add(invitation)
        else:
            for staff_id in request.form.getlist('participants'):
                staff = StaffPersonalInfo.query.get(int(staff_id))
                invitation = MeetingInvitation(staff_id=staff.staff_account.id,
                                               created_at=new_meeting.start,
                                               meeting=new_meeting)
                db.session.add(invitation)
        new_meeting.creator = current_user
        db.session.commit()
        if form.notify_participants.data:
            meeting_invitation_link = url_for('meeting_planner.show_invitation_detail',
                                              meeting_id=new_meeting.id, _external=True)
            message = f'''
            ขอเรียนเชิญเข้าร่วมประชุม{invitation.meeting.title}
            ในวันที่ {form.start.data.strftime('%d/%m/%Y %H:%M')} - {form.end.data.strftime('%d/%m/%Y %H:%M')}
            {invitation.meeting.rooms} 

            ลิงค์การประชุมออนไลน์
            {invitation.meeting.meeting_url or 'ไม่มี'}

            กรุณาตอบรับการประชุมในลิงค์ด้านล่าง

            {meeting_invitation_link}
            '''
            if not current_app.debug:
                send_mail([invitation.staff.email + '@mahidol.ac.th' for invitation in new_meeting.invitations],
                          title=f'MUMT-MIS: เชิญเข้าร่วมประชุม{invitation.meeting.title}',
                          message=message)
            else:
                print(message)
        flash('บันทึกข้อมูลการประชุมแล้ว', 'success')
        return redirect(url_for('meeting_planner.index'))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('meeting_planner/meeting_form.html', form=form, poll_id=poll_id, start=start
                           , end=end)


@meeting_planner.route('/api/meeting_planner/add_event', methods=['POST'])
@login_required
def add_room_event():
    MeetingEventForm = create_new_meeting()
    form = MeetingEventForm()
    form.meeting_events.append_entry()
    event_form = form.meeting_events[-1]
    template = u"""
    <div id="{}">
        <div class="field">
            <label class="label">{}</label>
            {}
            <span id="availability-{}"></span>
        </div>
        <div class="field">
            <label class="label">{}</label>
            <div class="control">
            {}
            </div>
        </div>
    <div>
    """
    resp = template.format(event_form.name,
                           event_form.room.label,
                           event_form.room(class_="js-example-basic-single"),
                           event_form.room.name,
                           event_form.request.label,
                           event_form.request(class_="input"),
                           )
    resp = make_response(resp)
    resp.headers['HX-Trigger-After-Swap'] = 'activateSelect2js'
    return resp


@meeting_planner.route('/api/meeting_planner/remove_event', methods=['DELETE'])
@login_required
def remove_room_event():
    MeetingEventForm = create_new_meeting()
    form = MeetingEventForm()
    form.meeting_events.pop_entry()
    resp = ''
    for event_form in form.meeting_events:
        template = u"""
        <div id="{}" hx-preserve>
            <div class="field">
                <label class="label">{}</label>
                {}
                <span id="availability-{}"></span>
            </div>
            <div class="field">
                <label class="label">{}</label>
                <div class="control">
                {}
                </div>
            </div>
        </div>
        """.format(event_form.name,
                   event_form.room.label,
                   event_form.room(class_="js-example-basic-single"),
                   event_form.room.name,
                   event_form.request.label,
                   event_form.request(class_="input")
                   )
        resp += template
    if len(form.meeting_events.entries) == 0:
        resp = '<p>ไม่มีการใช้ห้องสำหรับกิจกรรม</p>'
    resp = make_response(resp)
    return resp


@meeting_planner.route('/api/meeting_planner/add_agenda', methods=['POST'])
@login_required
def add_agenda():
    MeetingEventForm = create_new_meeting()
    form = MeetingEventForm()
    form.agendas.append_entry()
    agenda_form = form.agendas[-1]
    template = u"""
        <div id="{}">
            <div class="field">
                <div class="label">{}</div>
                <div class="select">
                    {}
                </div>
            </div>
            <div class="field">
                <label class="label">{}</label>
                <div class="control">
                    {}
                </div>
            </div>
            <div class="field">
                <label class="label">{}</label>
                <div class="control">
                {}
                </div>
            </div>
        </div>
    """
    resp = template.format(agenda_form.id,
                           agenda_form.group.label,
                           agenda_form.group(),
                           agenda_form.number.label,
                           agenda_form.number(class_='input'),
                           agenda_form.detail.label,
                           agenda_form.detail(class_='textarea'),
                           )
    resp = make_response(resp)
    return resp


@meeting_planner.route('/api/meeting_planner/add_agenda', methods=['DELETE'])
@login_required
def remove_agenda():
    MeetingEventForm = create_new_meeting()
    form = MeetingEventForm()
    form.agendas.pop_entry()
    resp = ''
    for agenda_form in form.agendas:
        template = u"""
            <div id="{}">
                <div class="field">
                    <div class="label">{}</div>
                    <div class="select">
                        {}
                    </div>
                </div>
                <div class="field">
                    <label class="label">{}</label>
                    <div class="control">
                        {}
                    </div>
                </div>
                <div class="field">
                    <label class="label">{}</label>
                    <div class="control">
                    {}
                    </div>
                </div>
            </div>
        """
        resp += template.format(agenda_form.id,
                                agenda_form.group.label,
                                agenda_form.group(),
                                agenda_form.number.label,
                                agenda_form.number(class_='input'),
                                agenda_form.detail.label,
                                agenda_form.detail(class_='textarea'),
                                )
    resp = make_response(resp)
    return resp


@meeting_planner.route('/invitations/<int:invitation_id>/rsvp', methods=['PATCH'])
@login_required
def respond(invitation_id):
    response = request.args.get('response')
    keep = request.args.get('keep', 'false')
    invitation = MeetingInvitation.query.get(invitation_id)
    if invitation.meeting.cancelled_at is None:
        invitation.response = response
        invitation.responded_at = arrow.now('Asia/Bangkok').datetime
        if invitation.response == 'เข้าร่วม':
            invitation.note = ''
            resp = '<i class="fas fa-circle-check has-text-success"></i>'
            if keep == 'false':
                resp += f'<div id="target-{invitation.id}" hx-swap-oob="true"></div>'
        elif invitation.response == 'ไม่เข้าร่วม':
            add_note_to_response_url = url_for('meeting_planner.add_note_to_response',
                                               invitation_id=invitation.id,
                                               keep=keep)
            resp = '<i class="fas fa-times-circle has-text-danger"></i>'
            resp += (f'<div id="note-target-{invitation.id}" hx-swap-oob="true">'
                     f'<form hx-patch="{add_note_to_response_url}">'
                     f'<input type="text" placeholder="โปรดระบุเหตุผล" value="{invitation.note}" '
                     f'name="note" class="input is-small">'
                     f'<input class="tag is-small" type="submit" value="Send">'
                     f'<button class="tag is-small" hx=get={add_note_to_response_url}>Cancel</button>'
                     f'</form></div>'
                     )
            '''
            if keep == 'false':
                resp += f'<div id="target-{invitation.id}" hx-swap-oob="true"></div>'
            '''
        else:
            invitation.note = ''
            resp = '<i class="fas fa-question-circle"></i>'
            if keep == 'false':
                resp += f'<div id="target-{invitation.id}" hx-swap-oob="true"></div>'
        db.session.add(invitation)
        db.session.commit()
        resp += f'<span id="response-time-{invitation_id}" hx-swap-oob="true">{invitation.responded_at.strftime("%d/%m/%Y %H:%M:%S")}</span>'
        resp = make_response(resp)
        return resp
    return f'<div id="target-{invitation.id}" hx-swap-oob="true"></div>'


@meeting_planner.route('/api/invitations/<int:invitation_id>/note', methods=['GET', 'PATCH'])
@login_required
def add_note_to_response(invitation_id):
    keep = request.args.get('keep', 'false')
    if request.method == 'PATCH':
        invitation = MeetingInvitation.query.get(invitation_id)
        invitation.note = request.form.get('note')
        db.session.add(invitation)
        db.session.commit()
        if keep == 'true':
            return f'<div id="note-target-{invitation_id}" hx-swap-oob="true"></div>'
        else:
            return f'<div id="target-{invitation_id}" hx-swap-oob="true"></div>'

    return f'<div id="target-{invitation_id}" hx-swap-oob="true"></div>'


@meeting_planner.route('/api/invitations/<int:invitation_id>/detail')
@login_required
def invitation_detail(invitation_id):
    invite = MeetingInvitation.query.get(invitation_id)
    return f'''
    <nav class="level is-mobile">
        <div class="level-left">
            <a class="level-item" hx-target="#left-icon-{invite.id}" hx-patch="{url_for('meeting_planner.respond', invitation_id=invite.id, response='เข้าร่วม')}">
                <span class="tag is-success">เข้าร่วม</span>
            </a>
            <a class="level-item" hx-target="#left-icon-{invite.id}" hx-patch="{url_for('meeting_planner.respond', invitation_id=invite.id, response='ไม่เข้าร่วม')}">
                <span class="tag is-danger">ไม่เข้าร่วม</span>
            </a>
            <a class="level-item" hx-target="#left-icon-{invite.id}" hx-patch="{url_for('meeting_planner.respond', invitation_id=invite.id, response='ไม่แน่ใจ')}">
                <span class="tag is-light">ไม่แน่ใจ</span>
            </a>
        </div>
    </nav>
    '''


@meeting_planner.route('/meetings')
@login_required
def list_meetings():
    return render_template('meeting_planner/meetings.html')


@meeting_planner.route('/invitations')
@login_required
def list_invitations():
    cat = request.args.get('cat', 'new')
    now = arrow.now('Asia/Bangkok').datetime
    return render_template('meeting_planner/meeting_invitations.html', cat=cat, now=now)


@meeting_planner.route('/api/meetings')
@login_required
def get_meetings():
    data = []
    for meeting in MeetingEvent.query.filter_by(creator=current_user).order_by(MeetingEvent.created_at.desc()):
        d_ = meeting.to_dict()
        view_meeting_url = url_for('meeting_planner.detail_meeting', meeting_id=d_['id'])
        d_['action'] = f'<a class="tag" href={view_meeting_url}>view</a>'
        data.append(d_)
    return jsonify({'data': data})


@meeting_planner.route('/meetings/<int:meeting_id>/detail', methods=['GET', 'POST'])
@login_required
def detail_meeting(meeting_id):
    form = MeetingAgendaForm()
    if form.validate_on_submit():
        agenda = MeetingAgenda()
        form.populate_obj(agenda)
        agenda.meeting_id = meeting_id
        db.session.add(agenda)
        db.session.commit()
        flash('เพิ่มหัวข้อใหม่แล้ว', 'success')
    meeting = MeetingEvent.query.get(meeting_id)
    return render_template('meeting_planner/meeting_detail.html', meeting=meeting, form=form)


@meeting_planner.route('/meetings/<int:meeting_id>/detail-member')
@login_required
def detail_meeting_member(meeting_id):
    meeting = MeetingEvent.query.get(meeting_id)
    return render_template('meeting_planner/meeting_detail_member.html', meeting=meeting)


@meeting_planner.route('/api/invitations/<int:invitation_id>/notify')
@login_required
def notify_participant(invitation_id):
    invitation = MeetingInvitation.query.get(invitation_id)
    meeting_invitation_link = url_for('meeting_planner.show_invitation_detail',
                                      _external=True,
                                      meeting_id=invitation.meeting.id)
    start = arrow.get(invitation.meeting.start, 'Asia/Bangkok').datetime
    end = arrow.get(invitation.meeting.end, 'Asia/Bangkok').datetime
    message = f'''
    ขอเรียนเชิญเข้าร่วมประชุม{invitation.meeting.title}
    ในวันที่ {start.strftime('%d/%m/%Y %H:%M')} - {end.strftime('%d/%m/%Y %H:%M')}
    {invitation.meeting.rooms}

    ลิงค์การประชุมออนไลน์
    {invitation.meeting.meeting_url}

    กรุณาตอบรับการประชุมในลิงค์ด้านล่าง

    {meeting_invitation_link}
    '''
    if not current_app.debug:
        send_mail([invitation.staff.email + '@mahidol.ac.th'],
                  title=f'MUMT-MIS: เชิญเข้าร่วมประชุม{invitation.meeting.title}',
                  message=message)
    else:
        print(message)
    resp = make_response()
    resp.headers['HX-Trigger-After-Swap'] = 'notifyAlert'
    return resp


@meeting_planner.route('/api/meeting_planner/topics/<int:topic_id>/edit', methods=['GET', 'POST', 'DELETE'])
@login_required
def edit_topic_form(topic_id):
    topic = MeetingAgenda.query.get(topic_id)
    form = MeetingAgendaForm(obj=topic)
    if request.method == 'GET':
        template = '''
        <tr>
            <td style="width: 10%">{}</td>
            <td>{}
            <hr>
            <label class="label">มติที่ประชุม</label>{}</td>
            <td style="width: 10%">
                <a class="button is-success is-outlined"
                    hx-post="{}" hx-include="closest tr">
                    <span class="icon"><i class="fas fa-save"></i></span>
                </a>
            </td>
        </tr>
        '''.format(form.number(class_="input"),
                   form.detail(class_="textarea"),
                   form.consensus(class_="textarea"),
                   url_for('meeting_planner.edit_topic_form', topic_id=topic.id),
                   )
    if request.method == 'POST':
        topic.number = request.form.get('number')
        topic.detail = request.form.get('detail')
        topic.consensus = request.form.get('consensus')
        db.session.add(topic)
        db.session.commit()
        template = '''
        <tr>
            <td style="width: 10%">{}</td>
            <td>
            {}
            <hr>
            <label class="label">มติที่ประชุม</label>
            <p class="notification">{}</p>
            </td>
            <td style="width: 10%">
                <div class="field has-addons">
                    <div class="control">
                        <a class="button is-light is-outlined"
                           hx-get="{}">
                            <span class="icon">
                               <i class="fas fa-pencil has-text-dark"></i>
                            </span>
                        </a>
                    </div>
                    <div class="control">
                        <a class="button is-light is-outlined">
                            <span class="icon">
                                <i class="fas fa-trash-alt has-text-danger"></i>
                            </span>
                        </a>
                    </div>
                </div>
            </td>
        </tr>
        '''.format(topic.number,
                   topic.detail,
                   topic.consensus,
                   url_for('meeting_planner.edit_topic_form', topic_id=topic.id),
                   )
    if request.method == 'DELETE':
        db.session.delete(topic)
        db.session.commit()
        template = ""

    resp = make_response(template)
    return resp


@meeting_planner.route('/api/meeting_planner/invites/<int:invite_id>', methods=['PATCH', 'DELETE'])
@login_required
def checkin_member(invite_id):
    invite = MeetingInvitation.query.get(invite_id)
    if request.method == 'PATCH':
        invite.joined_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(invite)
        db.session.commit()
        template = '''
        <a class="button is-success" hx-delete="{}" hx-target="#checkin-{}">
            <span class="icon">
                <i class="fa-solid fa-user-check"></i>
            </span>
        </a>
        <span class="tag">{}</span>
        '''.format(url_for('meeting_planner.checkin_member', invite_id=invite.id),
                   invite.id,
                   invite.joined_at.strftime('%d/%m/%Y %H:%M:%S')
                   )

    if request.method == 'DELETE':
        invite.joined_at = None
        db.session.add(invite)
        db.session.commit()
        template = '''
        <a class="button is-light" hx-put="{}" hx-target="#checkin-{}">
            <span class="icon">
                <i class="fa-solid fa-user-clock"></i>
            </span>
        </a>
        '''.format(url_for('meeting_planner.checkin_member', invite_id=invite.id),
                   invite.id)
    resp = make_response(template)
    return resp


@meeting_planner.route('/meetings/<int:meeting_id>/invitation-detail')
def show_invitation_detail(meeting_id=None):
    meeting = MeetingEvent.query.get(meeting_id)
    return render_template('meeting_planner/meeting_invitation_detail.html', meeting=meeting)


@meeting_planner.route('/meetings/<int:meeting_id>/respond', methods=['GET', 'PATCH'])
@login_required
def respond_invitation_detail(meeting_id=None):
    meeting = MeetingEvent.query.get(meeting_id)
    invite = current_user.invitations.filter_by(meeting_event_id=meeting_id).first()

    if request.method == 'GET':
        if invite:
            return render_template('meeting_planner/meeting_invitation_detail.html',
                                   invite=invite, meeting=meeting)
    if request.method == 'PATCH':
        response = request.args.get('response')
        if invite.meeting.cancelled_at is None:
            invite.response = response
            invite.responded_at = arrow.now('Asia/Bangkok').datetime
            if invite.response == 'เข้าร่วม':
                invite.note = ''
                resp = f'''
                <div id="respond-target" hx-swap-oob="true">
                    <i class="fas fa-circle-check has-text-success"></i>
                </div>
                '''
            elif invite.response == 'ไม่เข้าร่วม':
                add_note_to_response_url = url_for('meeting_planner.add_note_to_response', invitation_id=invite.id)
                resp = '''
                <div id="respond-target" hx-swap-oob="true">
                    <i class="fas fa-times-circle has-text-danger"></i>
                </div>
                '''
                resp += f'<div id="note-target" hx-swap-oob="true">' \
                        f'<form hx-patch="{add_note_to_response_url}">' \
                        f'<input type="text" placeholder="โปรดระบุเหตุผล" value="{invite.note}"' \
                        f' name="note" class="input is-small">' \
                        f'<input class="tag is-light" type="submit" value="Send">' \
                        f'<button hx-get="{add_note_to_response_url}" class"tag">Cancel</button>' \
                        f'</form></div>'
            else:
                invite.note = ''
                resp = f'''
                <div id="respond-target" hx-swap-oob="true">
                    <i class="fas fa-question-circle"></i>
                </div>
                '''
            db.session.add(invite)
            db.session.commit()
            return resp


@meeting_planner.route('/meetings/poll/list')
@login_required
def list_poll():
    polls = MeetingPoll.query.filter_by(user=current_user)
    return render_template('meeting_planner/meeting_poll_creator.html', polls=polls)


@meeting_planner.route('/meetings/poll/new', methods=['GET', 'POST'])
@meeting_planner.route('/meetings/poll/edit/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def edit_poll(poll_id=None):
    if poll_id:
        poll = MeetingPoll.query.get(poll_id)
        form = MeetingPollForm(obj=poll)
        start_vote = poll.start_vote.astimezone(localtz) if poll.start_vote else None
        close_vote = poll.close_vote.astimezone(localtz) if poll.close_vote else None
        for item in poll.poll_items:
            start = item.start.astimezone(localtz) if item.start else None
            end = item.end.astimezone(localtz) if item.end else None
    else:
        form = MeetingPollForm()
        start_vote = form.start_vote.data.astimezone(localtz) if form.start_vote.data else None
        close_vote = form.close_vote.data.astimezone(localtz) if form.close_vote.data else None
        start = form.poll_items[-1].start.data.astimezone(localtz) if form.poll_items[-1].start.data else None
        end = form.poll_items[-1].end.data.astimezone(localtz) if form.poll_items[-1].end.data else None

    if form.validate_on_submit():
        if poll_id is None:
            poll = MeetingPoll()

        form.populate_obj(poll)
        poll.start_vote = arrow.get(form.start_vote.data, 'Asia/Bangkok').datetime
        poll.close_vote = arrow.get(form.close_vote.data, 'Asia/Bangkok').datetime
        poll.user = current_user
        for item in form.groups.data:
            for i in item.group_members:
                poll.participants.append(i.staff)
        db.session.add(poll)
        db.session.commit()
        if poll_id is None:
            vote_link = url_for('meeting_planner.list_poll_participant', _external=True)
            title = 'แจ้งนัดหมายสำรวจวันเวลาประชุม'
            message = f'''ขอเรียนเชิญท่านทำการร่วมสำรวจวันและเวลาที่สะดวกเข้าร่วมประชุม{poll.poll_name} ภายในวันที่ {poll.start_vote.strftime('%d/%m/%Y')} เวลา {poll.start_vote.strftime('%H:%M')} - วันที่ {poll.close_vote.strftime('%d/%m/%Y')} เวลา {poll.close_vote.strftime('%H:%M')}\n\n'''
            message += f'''จึงเรียนมาเพื่อขอความอนุเคราะห์ให้ท่านทำการสำรวจภายในวันและเวลาดังกล่าว\n\n\n'''
            message += f'''ลิงค์สำหรับการเข้าสำรวจวันและเวลาที่สะดวกเข้าร่วมการประชุม\n'''
            message += f'''{vote_link}'''
            send_mail([p.email + '@mahidol.ac.th' for p in poll.participants], title, message)
            flash('บันทึกข้อมูลสำเร็จ.', 'success')
            return redirect(url_for('meeting_planner.list_poll'))
        else:
            vote_link = url_for('meeting_planner.list_poll_participant', _external=True)
            title = 'แจ้งแก้ไขการนัดหมายสำรวจวันเวลาประชุม'
            message = f'''ขอเรียนเชิญท่านทำการร่วมสำรวจวันและเวลาที่สะดวกเข้าร่วมประชุม{poll.poll_name} ภายในวันที่ {poll.start_vote.strftime('%d/%m/%Y')} เวลา {poll.start_vote.strftime('%H:%M')} - วันที่ {poll.close_vote.strftime('%d/%m/%Y')} เวลา {poll.close_vote.strftime('%H:%M')}\n\n'''
            message += f'''จึงเรียนมาเพื่อขอความอนุเคราะห์ให้ท่านทำการสำรวจภายในวันและเวลาดังกล่าว\n\n\n'''
            message += f'''ลิงค์สำหรับการเข้าสำรวจวันและเวลาที่สะดวกเข้าร่วมการประชุม\n'''
            message += f'''{vote_link}'''
            send_mail([p.email + '@mahidol.ac.th' for p in poll.participants], title, message)
            flash('แก้ไขข้อมูลสำเร็จ.', 'success')
            return redirect(url_for('meeting_planner.detail_poll', poll_id=poll_id))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('meeting_planner/meeting_new_poll.html', form=form, start_vote=start_vote,
                           close_vote=close_vote, start=start, end=end, poll_id=poll_id)


@meeting_planner.route('/api/meeting_planner/add_poll_item', methods=['POST'])
@login_required
def add_poll_item():
    form = MeetingPollForm()
    form.poll_items.append_entry()
    item_form = form.poll_items[-1]
    # item_form.start.data = arrow.get(request.form.get('start')).datetime
    # item_form.end.data = arrow.get(request.form.get('end')).datetime
    template = """
        <div id="{}">
            <div class="field">
                <label class="label">{}</label>
                <div class="control">
                    {}
                </div>
            </div>
            <div class="field">
                <label class="label">{}</label>
                <div class="control">
                    {}
                </div>
            </div>
        </div>
    """
    resp = template.format(item_form.id,
                           item_form.start.label,
                           item_form.start(class_='input'),
                           item_form.end.label,
                           item_form.end(class_='input')
                           )
    resp = make_response(resp)
    resp.headers['HX-Trigger-After-Swap'] = 'activateDateRangePickerEvent'
    return resp


@meeting_planner.route('/api/meeting_planner/remove_poll_item', methods=['DELETE'])
@login_required
def remove_poll_item():
    form = MeetingPollForm()
    form.poll_items.pop_entry()
    resp = ''
    for item_form in form.poll_items:
        template = """
            <div id="{}">
                <div class="field">
                    <label class="label">{}</label>
                    <div class="control">
                        {}
                    </div>
                </div>
                <div class="field">
                    <label class="label">{}</label>
                    <div class="control">
                        {}
                    </div>
                </div>
            </div>
        """
        resp += template.format(item_form.id,
                                item_form.start.label,
                                item_form.start(class_='input'),
                                item_form.end.label,
                                item_form.end(class_='input')
                                )
    resp = make_response(resp)
    return resp


@meeting_planner.route('/meetings/poll/delete/<int:poll_id>')
@login_required
def delete_poll(poll_id):
    if poll_id:
        poll = MeetingPoll.query.get(poll_id)
        statement = select(meeting_poll_participant_assoc).filter_by(poll_id=poll_id)
        poll_participant_id = db.session.execute(statement).first()[0]
        poll_participant = MeetingPollItemParticipant.query.filter_by(poll_participant_id=poll_participant_id).first()
        if poll_participant:
            db.session.delete(poll_participant)
            db.session.commit()
            db.session.delete(poll)
        else:
            db.session.delete(poll)
        db.session.commit()
        title = 'แจ้งยกเลิกการนัดหมายสำรวจวันเวลาประชุม'
        message = f'''ขอแจ้งยกเลิกคำเชิญการร่วมสำรวจวันและเวลาที่สะดวกเข้าร่วมประชุม{poll.poll_name} ในวันที่ {poll.start_vote.strftime('%d/%m/%Y')} เวลา {poll.start_vote.strftime('%H:%M')} - วันที่ {poll.close_vote.strftime('%d/%m/%Y')} เวลา {poll.close_vote.strftime('%H:%M')}\n\n'''
        message += f'''ขออภัยในความไม่สะดวก'''
        send_mail([p.email + '@mahidol.ac.th' for p in poll.participants], title, message)
        flash(u'The poll has been removed.')
        return redirect(url_for('meeting_planner.list_poll', poll_id=poll_id))


@meeting_planner.route('/meetings/poll/detail/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def detail_poll(poll_id):
    poll = MeetingPoll.query.get(poll_id)
    date_time_now = arrow.now('Asia/Bangkok').datetime
    MeetingPollResultForm = create_meeting_poll_result_form(poll_id)
    form = MeetingPollResultForm()
    if form.validate_on_submit():
        result = MeetingPollResult()
        form.populate_obj(result)
        result.poll_id = poll_id
        db.session.add(result)
        db.session.commit()
        flash('สรุปวัน-เวลาการประชุมสำเร็จ', 'success')
    voted = set()
    for item in poll.poll_items:
        for voter in item.voters:
            voted.add(voter.participant)
    return render_template('meeting_planner/meeting_detail_poll.html', poll=poll, voted=voted,
                           date_time_now=date_time_now, form=form)


@meeting_planner.route('/meetings/poll/list_poll_participant')
@login_required
def list_poll_participant():
    tab = request.args.get('tab', 'new')
    date_time_now = arrow.now('Asia/Bangkok').datetime
    return render_template('meeting_planner/meeting_poll_participant.html', date_time_now=date_time_now
                           , tab=tab)


@meeting_planner.route('/meetings/poll/add_vote/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def add_vote(poll_id):
    poll = MeetingPoll.query.get(poll_id)
    statement = select(meeting_poll_participant_assoc).filter_by(staff_id=current_user.id, poll_id=poll_id)
    poll_participant_id = db.session.execute(statement).first()[0]
    if request.method == 'POST':
        form = request.form
        for item in poll.poll_items:
            poll_participant = item.voters.filter_by(poll_participant_id=poll_participant_id).first()
            if str(item.id) in form.getlist('check_vote'):
                if not poll_participant:
                    item.voters.append(MeetingPollItemParticipant(poll_participant_id=poll_participant_id))
            else:
                if poll_participant:
                    db.session.delete(poll_participant)
            db.session.add(item)
        db.session.commit()
        return redirect(url_for('meeting_planner.list_poll_participant'))
    return render_template('meeting_planner/meeting_add_vote.html', poll=poll,
                           poll_participant_id=poll_participant_id)


@meeting_planner.route('/meetings/poll/show_vote/<int:poll_id>')
@login_required
def show_vote(poll_id):
    poll = MeetingPoll.query.get(poll_id)
    statement = select(meeting_poll_participant_assoc).filter_by(staff_id=current_user.id, poll_id=poll_id)
    poll_participant_id = db.session.execute(statement).first()[0]
    return render_template('meeting_planner/modal/show_vote_modal.html', poll=poll,
                           poll_participant_id=poll_participant_id)


@meeting_planner.route('/meetings/poll/show_participant_votes/<int:poll_item_id>')
@login_required
def show_participant_vote(poll_item_id):
    poll_item = MeetingPollItem.query.get(poll_item_id)
    voters = poll_item.voters.join(meeting_poll_participant_assoc).join(StaffAccount)
    return render_template('meeting_planner/modal/show_participant_vote_modal.html',
                           poll_item=poll_item, voters=voters)


@meeting_planner.route('/meetings/poll/detail_member/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def detail_poll_member(poll_id):
    poll = MeetingPoll.query.get(poll_id)
    date_time_now = arrow.now('Asia/Bangkok').datetime
    voted = set()
    for item in poll.poll_items:
        for voter in item.voters:
            voted.add(voter.participant)
    return render_template('meeting_planner/meeting_detail_poll_member.html', poll=poll, voted=voted,
                           date_time_now=date_time_now)


@meeting_planner.route('meeting/poll/notify/<int:poll_id>/<int:participant_id>')
@login_required
def notify_poll_participant(poll_id, participant_id):
    poll = MeetingPoll.query.get(poll_id)
    for p in poll.participants:
        if p.id == participant_id:
            vote_link = url_for('meeting_planner.list_poll_participant', _external=True)
            title = 'แจ้งนัดหมายสำรวจวันเวลาประชุม'
            message = f'''ขอเรียนเชิญท่านทำการร่วมสำรวจวันและเวลาที่สะดวกเข้าร่วมประชุม{poll.poll_name} ภายในวันที่ {poll.start_vote.strftime('%d/%m/%Y')} เวลา {poll.start_vote.strftime('%H:%M')} - วันที่ {poll.close_vote.strftime('%d/%m/%Y')} เวลา {poll.close_vote.strftime('%H:%M')}\n\n'''
            message += f'''จึงเรียนมาเพื่อขอความอนุเคราะห์ให้ท่านทำการสำรวจภายในวันและเวลาดังกล่าว\n\n\n'''
            message += f'''ลิงค์สำหรับการเข้าสำรวจวันและเวลาที่สะดวกเข้าร่วมการประชุม\n'''
            message += f'''{vote_link}'''
            send_mail([p.email + '@mahidol.ac.th'], title, message)
            resp = make_response()
            resp.headers['HX-Trigger-After-Swap'] = 'notifyAlert'
            return resp