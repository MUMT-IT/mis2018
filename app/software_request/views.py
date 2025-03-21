import arrow
from flask import render_template, redirect, flash, url_for, jsonify, request
from flask_login import login_required, current_user
from app.software_request import software_request
from app.software_request.forms import SoftwareRequestDetailForm
from app.software_request.models import *


@software_request.route('/')
@login_required
def index():
    return render_template('software_request/index.html')


@software_request.route('/request/index')
@login_required
def request_index():
    return render_template('software_request/request_index.html')


@software_request.route('/condition')
def condition_for_service_request():
    return render_template('software_request/condition_page.html')


@software_request.route('/request/add')
def create_request():
    form = SoftwareRequestDetailForm()
    if form.validate_on_submit():
        detail = SoftwareRequestDetail()
        form.populate_obj(detail)
        detail.created_date = arrow.now('Asia/Bangkok').datetime
        detail.created_id = current_user.id
        db.session.add(detail)
        db.session.commit()
        flash('ส่งคำขอสำเร็จ', 'success')
        return redirect(url_for('software_request.index'))
    return render_template('software_request/create_request.html', form=form)


@software_request.route('/api/system', methods=['GET'])
@login_required
def get_systems():
    search_term = request.args.get('term', '')
    key = request.args.get('key', 'id')
    results = []
    systems = SoftwareRequestSystem.query.all()
    for system in systems:
        if search_term in system.system:
            index_ = getattr(system, key) if hasattr(system, key) else getattr(system.system, key)
            results.append({
                "id": index_,
                "text": system.system
            })
    return jsonify({'results': results})


@software_request.route('/admin/request/update')
def update_request():
    return render_template('software_request/update_request.html')