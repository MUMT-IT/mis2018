from flask import render_template, make_response, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.main import db
from app.meeting_planner import meeting_planner
from app.meeting_planner.forms import MeetingEventForm
from app.meeting_planner.models import MeetingEvent, MeetingInvitation
from app.staff.models import StaffPersonalInfo
from pytz import timezone

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
        for event_form in form.events:
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
    form.events.append_entry()
    event_form = form.events[-1]
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
    form.events.pop_entry()
    resp = ''
    for event_form in form.events:
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
    if len(form.events.entries) == 0:
        resp = '<p>ไม่มีการใช้ห้องสำหรับกิจกรรม</p>'
    resp = make_response(resp)
    return resp
