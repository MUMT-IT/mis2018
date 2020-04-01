from flask import request, url_for, render_template, redirect, jsonify, flash
from . import smartclass_scheduler_blueprint as smartclass
from .models import SmartClassOnlineAccount, SmartClassOnlineAccountEvent, SmartClassResourceType
from .forms import SmartClassOnlineAccountEventForm
from app.main import db
import arrow
from datetime import datetime
from pytz import timezone

localtz = timezone('Asia/Bangkok')


@smartclass.route('/')
def index():
    resources = SmartClassResourceType.query.all()
    return render_template('smartclass_scheduler/index.html', resources=resources)


@smartclass.route('/resources/<int:resource_type_id>')
def list_resources(resource_type_id):
    accounts = SmartClassOnlineAccount.query.all()
    return render_template('smartclass_scheduler/online_accounts.html',
                           accounts=accounts,
                           resource_type_id=resource_type_id)


@smartclass.route('/api/resources/<int:resource_type_id>/events')
def get_events(resource_type_id):
    events = SmartClassOnlineAccountEvent.query.filter(
        SmartClassOnlineAccountEvent.account.has(resource_type_id=resource_type_id)
    )
    event_data = []
    for evt in events:
        if not evt.cancelled_at:
            event_data.append({
                'id': evt.id,
                'start': evt.start.astimezone(localtz).isoformat(),
                'end': evt.end.astimezone(localtz).isoformat(),
                'title': evt.title,
                'account': evt.account.name,
                'occupancy': evt.occupancy,
                'resourceId': evt.account.id,
                'resourceType': str(evt.account.resource_type)
            })
    return jsonify(event_data)


@smartclass.route('/api/resources')
def get_resources():
    accounts = SmartClassOnlineAccount.query.all()
    account_data = []
    for a in accounts:
        account_data.append({
            'id': a.id,
            'resource_type': str(a.resource_type),
            'title': a.name,
        })

    return jsonify(account_data)


@smartclass.route('/event/new', methods=['GET', 'POST'])
def add_event():
    account_id = request.args.get('account_id')
    account = SmartClassOnlineAccount.query.get(int(account_id))
    if not account:
        return 'Account not found.'

    form = SmartClassOnlineAccountEventForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_event = SmartClassOnlineAccountEvent()
            form.populate_obj(new_event)
            # probably not needed, but to make sure
            new_event.start = arrow.get(new_event.start, 'Asia/Bangkok').datetime
            new_event.end = arrow.get(new_event.end, 'Asia/Bangkok').datetime
            new_event.account = account
            db.session.add(new_event)
            db.session.commit()
            flash('The new request has been submitted.', 'success')
            return redirect(url_for('smartclass_scheduler.list_resources',
                                    resource_type_id=account.resource_type.id))

    return render_template('smartclass_scheduler/add_online_account_event.html',
                           form=form,
                           account_id=account_id)


@smartclass.route('/events/<int:event_id>')
def show_event_detail(event_id):
    event = SmartClassOnlineAccountEvent.query.get(event_id)
    return render_template('smartclass_scheduler/online_account_event_detail.html', event=event)


@smartclass.route('/event/<int:event_id>/edit', methods=['GET', 'POST'])
def edit_event(event_id):
    event = SmartClassOnlineAccountEvent.query.get(event_id)
    form = SmartClassOnlineAccountEventForm(obj=event)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(event)
            # need to convert a naive to a timezone-aware datetime
            event.start = arrow.get(event.start, 'Asia/Bangkok').datetime
            event.end = arrow.get(event.end, 'Asia/Bangkok').datetime
            db.session.add(event)
            db.session.commit()
            flash('The event has been updated.', 'success')
            return redirect(url_for('smartclass_scheduler.show_event_detail', event_id=event.id))
    return render_template('smartclass_scheduler/edit_online_account_event.html', form=form, event=event)


@smartclass.route('/event/<int:event_id>/cancel')
def cancel_event(event_id):
    event = SmartClassOnlineAccountEvent.query.get(event_id)
    if event:
        event.cancelled_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(event)
        db.session.commit()
        flash('The event has been cancelled.', 'success')
        return redirect(url_for('smartclass_scheduler.list_resources',
                                resource_type_id=event.account.resource_type.id))
    else:
        flash('Resource not found.', 'warning')
        return redirect(url_for('smartclass_scheduler.list_resources',
                                resource_type_id=event.account.resource_type.id))
