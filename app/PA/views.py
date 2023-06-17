# -*- coding:utf-8 -*-
import datetime
import pytz
from sqlalchemy import and_
from . import pa_blueprint as pa

from flask_login import login_required, current_user
from flask import render_template, request, redirect, url_for, flash
from app.PA.models import *
from app.roles import hr_permission, manager_permission
from ..models import Org
from app.PA.forms import PACommitteeForm, PARequestForm, create_rate_performance_form

tz = pytz.timezone('Asia/Bangkok')

@pa.route('/pa/')
@login_required
def index():
    return render_template('pa/index.html', hr_permission=hr_permission, manager_permission=manager_permission)


@pa.route('/hr/create-round', methods=['GET', 'POST'])
@login_required
def create_round():
    pa_round = PARound.query.all()
    if request.method == 'POST':
        form = request.form
        start_d, end_d = form.get('dates').split(' - ')
        start = datetime.datetime.strptime(start_d, '%d/%m/%Y')
        end = datetime.datetime.strptime(end_d, '%d/%m/%Y')
        createround = PARound(
            start=tz.localize(start),
            end=tz.localize(end)
        )
        db.session.add(createround)
        db.session.commit()
        flash('เพิ่มรอบการประเมินใหม่เรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.create_round'))
    return render_template('pa/hr_create_round.html', pa_round=pa_round)


@pa.route('/hr/add-committee', methods=['GET', 'POST'])
@login_required
def add_commitee():
    form = PACommitteeForm()
    if form.validate_on_submit():
        commitee = PACommittee()
        form.populate_obj(commitee)
        db.session.add(commitee)
        db.session.commit()
        flash('เพิ่มผู้ประเมินใหม่เรียบร้อยแล้ว', 'success')
    else:
        for err in form.errors:
            flash('{}: {}'.format(err, form.errors[err]), 'danger')
    return render_template('pa/hr_add_committee.html', form=form)


@pa.route('/hr/committee', methods=['GET', 'POST'])
@login_required
def show_commitee():
    #TODO: org filter
    org_id = request.args.get('deptid')
    departments = Org.query.all()
    if org_id is None:
        committee_list = PACommittee.query.all()
    else:
        committee_list = PACommittee.query.filter(PACommittee.has(org_id=org_id))
    return render_template('pa/hr_show_committee.html',
                           sel_dept=org_id, committee_list=committee_list,
                           departments=[{'id': d.id, 'name': d.name} for d in departments])


@pa.route('/head/requests')
@login_required
def all_request():
    all_req = PARequest.query.filter_by(supervisor_id=current_user.id).filter(PARequest.submitted_at!=None).all()
    return render_template('pa/head_all_request.html', all_req=all_req)


@pa.route('/head/request/<int:request_id>', methods=['GET', 'POST'])
@login_required
def respond_request(request_id):
    req = PARequest.query.get(request_id)
    form = PARequestForm(obj=req)
    #TODO: for_ required
    if form.validate_on_submit():
        form.populate_obj(req)
        req.responded_at = datetime.datetime.now(tz)
        db.session.add(req)
        db.session.commit()
        flash('บันทึกผลเรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.all_request'))
    else:
        for err in form.errors:
            flash('{}: {}'.format(err, form.errors[err]), 'danger')
    return render_template('pa/head_respond_request.html', form=form, req=req)


@pa.route('/eva/head/all_performance/<int:scoresheet_id>')
@login_required
def all_performance(scoresheet_id):
    scoresheet = PAScoreSheet.query.filter_by(id=scoresheet_id).first()
    return render_template('pa/eva_all_performance.html', scoresheet=scoresheet)


@pa.route('/eva/rate_performance/<int:scoresheet_id>', methods=['GET', 'POST'])
@login_required
def rate_performance(scoresheet_id):
    scoresheet = PAScoreSheet.query.get(scoresheet_id)
    #TODO: get score of each item
    if request.method == 'POST':
        form = request.form
        score = form.get('score')
        print (score)
    return render_template('pa/eva_rate_performance.html', scoresheet=scoresheet)


@pa.route('/head/create-scoresheet/<int:pa_id>', methods=['GET', 'POST'])
@login_required
def create_scoresheet(pa_id):
    scoresheet = PAScoreSheet.query.filter_by(pa_id=pa_id).filter(PACommittee.staff == current_user).first()
    if not scoresheet:
        create_scoresheet = PAScoreSheet(
            pa_id=pa_id,
            evaluator_id=current_user.id
        )
        db.session.add(create_scoresheet)
        db.session.commit()

        pa_item = PAItem.query.filter_by(pa_id=pa_id).all()
        for item in pa_item:
            for kpi_item in item.kpi_items:
                create_scoresheet_item = PAScoreSheetItem(
                        score_sheet_id=create_scoresheet.id,
                        item_id=item.id,
                        kpi_item_id=kpi_item.id
                    )
                db.session.add(create_scoresheet_item)
                db.session.commit()
        return redirect(url_for('pa.all_performance', scoresheet_id=create_scoresheet.id))
    else:
        return render_template('pa/eva_all_performance.html', scoresheet=scoresheet)


@pa.route('/head/create-scoresheet/<int:pa_id>/for-committee', methods=['GET', 'POST'])
@login_required
def create_scoresheet_for_committee(pa_id):
    pa = PAAgreement.query.get(pa_id)
    for c in pa.committees:
        scoresheet = PAScoreSheet.query.filter_by(pa_id=pa_id,evaluator_id=c.staff_account_id).first()
        if not scoresheet:
            create_scoresheet = PAScoreSheet(
                pa_id=pa_id,
                evaluator_id=c.staff_account_id
            )
            db.session.add(create_scoresheet)
            db.session.commit()
            pa_item = PAItem.query.filter_by(pa_id=pa_id).all()
            for item in pa_item:
                for kpi_item in item.kpi_items:
                    create_scoresheet_item = PAScoreSheetItem(
                        score_sheet_id=create_scoresheet.id,
                        item_id=item.id,
                        kpi_item_id=kpi_item.id
                    )
                    db.session.add(create_scoresheet_item)
                    db.session.commit()
        flash('มีการเพิ่มผู้ประเมินเรียบร้อยแล้ว', 'success')
    flash('ส่งการประเมินไปยังกลุ่มผู้ประเมินเรียบร้อยแล้ว', 'success')
    return redirect(url_for('pa.all_approved_pa'))


@pa.route('/head/assign-committee/<int:pa_id>', methods=['GET', 'POST'])
@login_required
def assign_committee(pa_id):
    pa = PAAgreement.query.filter_by(id=pa_id).first()
    committee = PACommittee.query.filter_by(round_id=pa.round_id, org=pa.staff.personal_info.org).filter(
        PACommittee.staff != current_user).all()
    if request.method == 'POST':
        form = request.form
        pa.committees = []
        for evaluator_id in form.getlist("commitees"):
            evaluator = PACommittee.query.get(int(evaluator_id))
            pa.committees.append(evaluator)
            db.session.add(evaluator)
            db.session.commit()
        flash('บันทึกกลุ่มผู้ประเมินเรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.all_approved_pa'))
    return render_template('pa/head_assign_committee.html', pa=pa, committee=committee)


@pa.route('/head/all-approved-pa')
@login_required
def all_approved_pa():
    pa = PAAgreement.query.filter(and_(PARequest.submitted_at is not None,
                                       PARequest.for_ == 'ขอรับการประเมิน')).all()
    return render_template('pa/head_all_approved_pa.html', pa=pa)


@pa.route('/eva/all-scoresheet')
@login_required
def all_scoresheet():
    scoresheets = PAScoreSheet.query.filter_by(evaluator=current_user).all()
    return render_template('pa/eva_all_scoresheet.html', scoresheets=scoresheets)