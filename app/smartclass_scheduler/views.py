from flask import request, url_for, render_template, redirect, jsonify, flash
from . import smartclass_scheduler_blueprint as smartclass
from .models import SmartClassOnlineAccount, SmartClassOnlineAccountEvent, SmartClassResourceType
from .forms import SmartClassOnlineAccountEventForm
from app.main import db
import arrow
from dateutil import tz

localtz = tz.gettz('Asia/Bangkok')


@smartclass.route('/')
def index():
    resources = SmartClassResourceType.query.all()
    return render_template('smartclass_scheduler/index.html', resources=resources)


@smartclass.route('/zoom_accounts')
def list_online_accounts():
    accounts = SmartClassOnlineAccount.query.all()
    return render_template('smartclass_scheduler/online_accounts.html',
                           resource_type_id=1, accounts=accounts)


@smartclass.route('/api/online_account_events/<int:resource_type_id>')
def get_online_account_events(resource_type_id):
    events = SmartClassOnlineAccountEvent.query.filter(
        SmartClassOnlineAccountEvent.account.has(resource_type_id=resource_type_id)
    )
    event_data = []
    for evt in events:
        event_data.append({
            'id': evt.id,
            'start': evt.start.isoformat(),
            'end': evt.end.isoformat(),
            'title': evt.title,
            'account': evt.account.name,
            'occupancy': evt.occupancy,
            'resourceId': evt.account.id,
            'resourceType': str(evt.account.resource_type)
        })
    return jsonify(event_data)


@smartclass.route('/api/online_account_resources')
def get_online_account_resources():
    accounts = SmartClassOnlineAccount.query.all()
    account_data = []
    for a in accounts:
        account_data.append({
            'id': a.id,
            'resource_type': str(a.resource_type),
            'title': a.name,
        })

    return jsonify(account_data)


@smartclass.route('/online_accounts/event/new', methods=['GET', 'POST'])
def add_online_account_event():
    account_id = request.args.get('account_id')
    account = SmartClassOnlineAccount.query.get(int(account_id))
    if not account:
        return 'Account not found.'

    form = SmartClassOnlineAccountEventForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_event = SmartClassOnlineAccountEvent()
            form.populate_obj(new_event)
            new_event.start = new_event.start
            new_event.end = new_event.end
            new_event.account = account
            db.session.add(new_event)
            db.session.commit()
            flash('The new request has been submitted.', 'success')
            return redirect(url_for('smartclass_scheduler.zoom_accounts'))

    return render_template('smartclass_scheduler/add_online_account_event.html',
                           form=form,
                           account_id=account_id)
