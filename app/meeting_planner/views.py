from flask import render_template, make_response, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.main import db
from app.meeting_planner import meeting_planner
from app.meeting_planner.forms import MeetingEventForm
from app.meeting_planner.models import MeetingEvent, MeetingInvitation
from app.room_scheduler.models import RoomEvent
from app.staff.models import StaffPersonalInfo
from pytz import timezone
import arrow

tz = timezone('Asia/Bangkok')


@meeting_planner.route('/')
@login_required
def index():
    return render_template('meeting_planner/index.html')


@meeting_planner.route('/meetings/new', methods=['GET', 'POST'])
@login_required
def create_meeting():
    form = MeetingEventForm()
    if form.validate_on_submit():
        form.start.data = form.start.data.astimezone(tz)
        form.end.data = form.end.data.astimezone(tz)
        for event_form in form.meeting_events:
            if event_form.room.data:
                event_form.start.data = form.start.data
                event_form.end.data = form.end.data
                event_form.title.data = f'ประชุม{form.title.data}'
        new_meeting = MeetingEvent()
        form.populate_obj(new_meeting)
        for staff_id in request.form.getlist('participants'):
            staff = StaffPersonalInfo.query.get(int(staff_id))
            invitation = MeetingInvitation(staff_id=staff.staff_account.id,
                                           created_at=new_meeting.start,
                                           meeting=new_meeting)
            db.session.add(invitation)
        new_meeting.creator = current_user
        db.session.commit()
        flash('บันทึกข้อมูลการประชุมแล้ว', 'success')
        return redirect(url_for('meeting_planner.index'))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('meeting_planner/meeting_form.html', form=form)


@meeting_planner.route('/api/meeting_planner/add_event', methods=['POST'])
@login_required
def add_room_event():
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


@meeting_planner.route('/invitations/<int:invitation_id>/rsvp')
@login_required
def respond(invitation_id):
    response = request.args.get('response')
    invitation = MeetingInvitation.query.get(invitation_id)
    if invitation.meeting.cancelled_at is None:
        invitation.response = response
        invitation.responded_at = arrow.now('Asia/Bangkok').datetime
        if invitation.response == 'เข้าร่วม':
            invitation.note = ''
            resp = f'<div id="target-{invitation.id}" hx-swap-oob="true"></div>'
            resp += '<i class="fa-sharp fa-regular fa-circle-check has-text-success"></i>'
        elif invitation.response == 'ไม่เข้าร่วม':
            add_note_to_response_url = url_for('meeting_planner.add_note_to_response', invitation_id=invitation.id)
            resp = f'<div id="target-{invitation.id}" hx-swap-oob="true"><form hx-get="{add_note_to_response_url}"><input type="text" placeholder="โปรดระบุเหตุผล" value="{invitation.note}" name="note" class="input"><input class="button is-small is-white" type="submit" value="Send"></form></div>'
            resp += '<i class="fa-solid fa-hand has-text-danger"></i>'
        else:
            invitation.note = ''
            resp = f'<div id="target-{invitation.id}" hx-swap-oob="true"></div>'
            resp += '<i class="fa-solid fa-hourglass-start"></i>'
        db.session.add(invitation)
        db.session.commit()
        return resp
    return f'<div id="target-{invitation.id}" hx-swap-oob="true"></div>'


@meeting_planner.route('/api/invitations/<int:invitation_id>/note', methods=['GET'])
@login_required
def add_note_to_response(invitation_id):
    invitation = MeetingInvitation.query.get(invitation_id)
    invitation.note = request.args.get('note')
    print(request.args.get('note'))
    db.session.add(invitation)
    db.session.commit()
    return f'<div id="target-{invitation.id}" hx-swap-oob="true"></div>'


@meeting_planner.route('/api/invitations/<int:invitation_id>/detail')
@login_required
def invitation_detail(invitation_id):
    invite = MeetingInvitation.query.get(invitation_id)
    return f'''
    <nav class="level is-mobile">
        <div class="level-left">
            <a class="level-item" hx-target="#left-icon-{invite.id}" hx-get="{url_for('meeting_planner.respond', invitation_id=invite.id, response='เข้าร่วม')}">
                <span class="tag is-success">เข้าร่วม</span>
            </a>
            <a class="level-item" hx-target="#left-icon-{invite.id}" hx-get="{url_for('meeting_planner.respond', invitation_id=invite.id, response='ไม่เข้าร่วม')}">
                <span class="tag is-danger">ไม่เข้าร่วม</span>
            </a>
            <a class="level-item" hx-target="#left-icon-{invite.id}" hx-get="{url_for('meeting_planner.respond', invitation_id=invite.id, response='ไม่แน่ใจ')}">
                <span class="tag is-light">ไม่แน่ใจ</span>
            </a>
        </div>
    </nav>
    '''


@meeting_planner.route('/meetings')
@login_required
def list_meetings():
    return render_template('meeting_planner/meetings.html')


@meeting_planner.route('/api/meetings')
@login_required
def get_meetings():
    data = []
    for meeting in MeetingEvent.query.filter_by(creator=current_user).order_by(MeetingEvent.created_at.desc()):
        d_ = meeting.to_dict()
        view_meeting_url = url_for('meeting_planner.list_meetings')
        d_['action'] = f'<a class="tag" href={view_meeting_url}>view</a>'
        data.append(d_)
    return jsonify({'data': data})
