# -*- coding:utf-8 -*-
from datetime import datetime
import textwrap
from collections import defaultdict
from statistics import mean

import pytz
import arrow
import os
from pandas import DataFrame
from sqlalchemy import exc
from . import pa_blueprint as pa

from app.roles import hr_permission
from app.PA.forms import *
from app.main import mail, StaffEmployment, StaffLeaveUsedQuota
from ..models import KPI

tz = pytz.timezone('Asia/Bangkok')

from flask import render_template, flash, redirect, url_for, request, make_response, current_app, jsonify, \
    send_from_directory
from flask_login import login_required, current_user
from flask_mail import Message
from dateutil.relativedelta import relativedelta


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


@pa.route('/user-performance')
@login_required
def user_performance():
    rounds = PARound.query.filter(PARound.is_closed != True).all()
    current_round = []
    for round in rounds:
        for emp in round.employments:
            if emp == current_user.personal_info.employment:
                current_round.append(round)

    return render_template('PA/user_performance.html',
                           current_round=current_round)


@pa.route('/rounds/<int:round_id>/items/add', methods=['GET', 'POST'])
@pa.route('/rounds/<int:round_id>/pa/<int:pa_id>/items/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def add_pa_item(round_id, item_id=None, pa_id=None):
    pa_round = PARound.query.get(round_id)
    categories = PAItemCategory.query.all()
    if pa_id:
        pa = PAAgreement.query.get(pa_id)
    else:
        pa = PAAgreement.query.filter_by(round_id=round_id,
                                         staff=current_user).first()
    if pa is None:
        pa = PAAgreement(round_id=round_id,
                         staff=current_user,
                         created_at=arrow.now('Asia/Bangkok').datetime)
        db.session.add(pa)
        db.session.commit()
        head_committee = PACommittee.query.filter_by(org=current_user.personal_info.org, role='ประธานกรรมการ',
                                                     round=pa.round).first()
        head_individual = PACommittee.query.filter_by(subordinate=current_user, role='ประธานกรรมการ',
                                                      round=pa.round).first()
        if head_individual:
            supervisor = StaffAccount.query.filter_by(email=head_individual.staff.email).first()
            if supervisor:
                pa.head_committee_staff_account = supervisor
                db.session.add(pa)
                db.session.commit()
        elif head_committee:
            supervisor = StaffAccount.query.filter_by(email=head_committee.staff.email).first()
            if supervisor:
                if supervisor == current_user:
                    flash('ไม่พบประธานกรรมการประเมิน PA กรุณาแจ้ง HR', 'danger')
                else:
                    pa.head_committee_staff_account = supervisor
                    db.session.add(pa)
                    db.session.commit()
        else:
            flash('ไม่พบประธานกรรมการประเมิน PA กรุณาแจ้ง HR', 'danger')
    if item_id:
        pa_item = PAItem.query.get(item_id)
        form = PAItemForm(obj=pa_item)
    else:
        pa_item = None
        form = PAItemForm()
    for kpi in pa.kpis:
        items = []
        default = None
        for item in kpi.pa_kpi_items:
            items.append((item.id, textwrap.shorten(item.goal, width=100, placeholder='...')))
            if pa_item:
                if item in pa_item.kpi_items:
                    default = item.id
        field_ = form.kpi_items_.append_entry(default)
        field_.choices = [('', 'ไม่ระบุเป้าหมาย')] + items
        field_.label = kpi.detail
        field_.obj_id = kpi.id

    if form.validate_on_submit():
        maximum = 100 - pa.total_percentage
        if item_id:
            maximum += pa_item.percentage
        if form.percentage.data == 0:
            flash('สัดส่วนภาระงานต้องมากกว่า 0', 'danger')
            return redirect(url_for('pa.add_pa_item', round_id=round_id, _anchor=''))
        if form.percentage.data > maximum:
            flash('สัดส่วนภาระงานเกิน 100%', 'danger')
            return redirect(url_for('pa.add_pa_item', round_id=round_id, _anchor=''))

        for i in range(len(pa.kpis)):
            form.kpi_items_.pop_entry()

        if not pa_item:
            pa_item = PAItem()
        form.populate_obj(pa_item)
        if not request.form.get('report'):
            new_kpi_items = []
            for e in form.kpi_items_.entries:
                if e.data:
                    kpi_item = PAKPIItem.query.get(int(e.data))
                    if kpi_item:
                        new_kpi_items.append(kpi_item)
            pa_item.kpi_items = new_kpi_items
        pa.pa_items.append(pa_item)
        pa.updated_at = arrow.now('Asia/Bangkok').datetime
        if request.form.get('strategy_activity_id'):
            activity_id = request.form.get('strategy_activity_id')
            activity = StrategyActivity.query.get(int(activity_id))
            activity.contributors.append(current_user)
            db.session.add(activity)
            pa_item.strategy_activity=activity
        if request.form.get('process_id'):
            process_id = request.form.get('process_id')
            process = Process.query.get(int(process_id))
            process.staff.append(current_user)
            db.session.add(process)
            pa_item.process = process
        db.session.add(pa_item)
        db.session.commit()
        flash('เพิ่ม/แก้ไขรายละเอียดภาระงานเรียบร้อย', 'success')
        return redirect(url_for('pa.add_pa_item', round_id=round_id, _anchor='pa_table'))
    else:
        for er in form.errors:
            flash("{}:{}".format(er, form.errors[er]), 'danger')
    if request.headers.get('HX-Request') == 'true':
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('PA/pa_item_edit.html',
                           form=form,
                           pa_round=pa_round,
                           pa=pa,
                           pa_item_id=item_id,
                           categories=categories)


@pa.route('/rounds/<int:round_id>/items/add-form', methods=['GET', 'POST'])
@pa.route('/rounds/<int:round_id>/pa/<int:pa_id>/items/<int:item_id>/edit-form', methods=['GET', 'POST'])
@login_required
def add_pa_item_form(round_id, item_id=None, pa_id=None):
    if item_id:
        pa_item = PAItem.query.get(item_id)
        form = PAItemForm(obj=pa_item)
        return render_template('PA/modals/pa_item_form_modal.html',
                               form=form, round_id=round_id, item_id=item_id, pa_id=pa_id, pa_item=pa_item)
    else:
        form = PAItemForm()
        return render_template('PA/modals/pa_item_form_modal.html',
                               form=form, round_id=round_id, item_id=item_id, pa_id=pa_id)


@pa.route('/rounds/<int:round_id>/pa/<int:pa_id>/items/<int:item_id>/edit-report-form', methods=['GET', 'POST'])
@login_required
def add_report_pa_item_form(round_id, item_id, pa_id):
    pa = PAAgreement.query.get(pa_id)
    pa_item = PAItem.query.get(item_id)
    form = PAItemForm(obj=pa_item)
    return render_template('PA/modals/pa_item_report_modal.html',
                           form=form, round_id=round_id, item_id=item_id, pa_id=pa_id, pa=pa, pa_item=pa_item)


@pa.route('/rounds/<int:round_id>/pa/<int:pa_id>/items/<int:item_id>/edit-kpi-form', methods=['GET', 'POST'])
@login_required
def add_pa_item_kpi_form(round_id, item_id, pa_id):
    pa = PAAgreement.query.get(pa_id)
    pa_item = PAItem.query.get(item_id)
    form = PAItemForm(obj=pa_item)
    for kpi in pa.kpis:
        items = []
        default = None
        for item in kpi.pa_kpi_items:
            items.append((item.id, textwrap.shorten(item.goal, width=100, placeholder='...')))
            if pa_item:
                if item in pa_item.kpi_items:
                    default = item.id
        field_ = form.kpi_items_.append_entry(default)
        field_.choices = [('', 'ไม่ระบุเป้าหมาย')] + items
        field_.label = kpi.detail
        field_.obj_id = kpi.id
    return render_template('PA/modals/pa_item_kpis_form_modal.html',
                           form=form, round_id=round_id, item_id=item_id, pa_id=pa_id, pa=pa, pa_item=pa_item)


@pa.route('/pa/edit-form/related-processes', methods=['GET'])
@login_required
def get_related_work_processes():
    category_id = request.args.get('category', type=int)
    process_id = request.args.get('process_id', type=int)
    strategy_activity_id = request.args.get('strategy_activity_id', type=int)
    category = PAItemCategory.query.get(category_id)
    if category.code == 'STRATEGY':
        items = '<option name="strategy_activity_id" value="">โปรดระบุโครงการในแผนยุทธศาสตร์</option>'
        for a in StrategyActivity.query:
            items += f'<option value="{a.id}" {"selected" if strategy_activity_id==a.id else ""}>{a}</option>'
        template = f'''<select class="js-example-basic-single" name="strategy_activity_id">{items}</select>'''
    else:
        items = '<option name="process_id" value="">โปรดระบุกระบวนการทำงาน</option>'
        for proc in Process.query:
            items += f'<option value="{proc.id}" {"selected" if process_id==proc.id else ""}>{proc}</option>'
        template = f'''<select class="js-example-basic-single" name="process_id">{items}</select>'''
    resp = make_response(template)
    resp.headers['HX-Trigger-After-Swap'] = 'initSelect2'
    return resp


@pa.route('/pa/<int:pa_id>/items/<int:pa_item_id>/delete', methods=['DELETE'])
@login_required
def delete_pa_item(pa_id, pa_item_id):
    pa_item = PAItem.query.get(pa_item_id)
    db.session.delete(pa_item)
    db.session.commit()
    resp = make_response()
    return resp


@pa.route('/pa/copy/<int:pa_id>', methods=['GET', 'POST'])
@login_required
def copy_pa(pa_id):
    all_pa = PAAgreement.query.filter_by(staff=current_user).filter(PAAgreement.id != pa_id).all()
    current_pa = PAAgreement.query.get(pa_id)
    if request.method == 'POST':
        form = request.form
        previous_pa_id = form.get('previous_pa')
        previous_pa = PAAgreement.query.filter_by(id=previous_pa_id).first()
        if previous_pa:
            for item in previous_pa.pa_items:
                new_item = PAItem(
                    category=item.category,
                    task=item.task,
                    percentage=item.percentage,
                    report='',
                    pa=current_pa
                )
                db.session.add(new_item)
            db.session.commit()
            current_pa.updated_at = arrow.now('Asia/Bangkok').datetime
            db.session.add(current_pa)
            db.session.commit()
            flash('เพิ่มภาระงาน จากรอบที่เลือกไว้เรียบร้อยแล้ว **กรุณาเพิ่มตัวชี้วัด**', 'success')
        else:
            flash('ไม่พบ PA รอบเก่าที่ต้องการ กรุณาติดต่อหน่วย IT', 'danger')
        return redirect(url_for('pa.add_pa_item', round_id=current_pa.round_id, _anchor='pa_table'))
    return render_template('PA/pa_copy_round.html', all_pa=all_pa, current_pa=current_pa)


@pa.route('/api/pa-details', methods=['POST'])
@login_required
def get_pa_detail():
    pa_id = request.form.get('previous_pa')
    pa = PAAgreement.query.get(int(pa_id))

    template = '''<table id="pa-detail-table" class="table is-fullwidth"|sort(attribute={pa.id})>
        <thead>
        <th>หมวด</th>
        <th>ภาระงาน</th>
        <th>น้ำหนัก (ร้อยละ)</th>
        <th>ผลการดำเนินการ</th>
        </thead>
    '''

    tbody = '<tbody>'
    for item in pa.pa_items:
        tbody += f'<tr><td>{item.category}</td><td>{item.task}</td><td>{item.percentage}</td><td>{item.report}</td></tr>'
    tbody += '</tbody>'
    template += tbody
    template += '''</table>'''
    return template

    # return '''
    # <table id="pa-detail-table" class="table is-fullwidth">
    # <thead>
    #     <th>ภาระงาน</th>
    #     <th>Percentage</th>
    # </thead>
    # <tbody>
    # <tr>
    # <td>{}</td>
    # <td>{}</td>
    # </tr>
    # </tbody>
    # </table>
    # '''.format(pa, pa.id)


@pa.route('/requests/<int:request_id>/delete', methods=['DELETE'])
@login_required
def delete_request(request_id):
    req = PARequest.query.get(request_id)
    if req.for_ == 'ขอรับการประเมิน':
        if req.pa.submitted_at:
            req.pa.submitted_at = None
    db.session.delete(req)
    db.session.commit()
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@pa.route('/pa/<int:pa_id>/kpis/add', methods=['GET', 'POST'])
@login_required
def add_kpi(pa_id):
    round_id = request.args.get('round_id', type=int)
    all_current_job_kpi = PAKPIJobPosition.query.filter_by(job_position=current_user.personal_info.job_position).all()
    form = PAKPIForm()
    if form.validate_on_submit():
        new_kpi = PAKPI()
        form.populate_obj(new_kpi)
        new_kpi.pa_id = pa_id
        db.session.add(new_kpi)
        db.session.commit()
        flash('เพิ่มรายละเอียดเกณฑ์การประเมินเรียบร้อย', 'success')
        return redirect(url_for('pa.add_kpi', pa_id=pa_id, round_id=round_id))
    else:
        for er in form.errors:
            flash("{}:{}".format(er, form.errors[er]), 'danger')
    return render_template('PA/add_kpi.html', form=form, round_id=round_id, pa_id=pa_id,
                           all_current_job_kpi=all_current_job_kpi)


@pa.route('/api/job-kpi-details/<int:pa_id>', methods=['POST'])
@login_required
def get_job_kpi_detail(pa_id):
    job_kpi_id = request.form.get('job_kpi')
    job_kpi = PAKPIJobPosition.query.get(int(job_kpi_id))

    template = '''<table id="job-kpi-detail-table" class="table is-fullwidth"|sort(attribute={pa.id})>
        <thead>
        <th>เกณฑ์</th>
        <th>เป้าหมาย</th>
        </thead>
    '''
    tbody = '<tbody>'
    if job_kpi.pa_kpi_job_positions:
        for item in job_kpi.pa_kpi_job_positions:
            tbody += f'<tr><td>{item.level} คะแนน</td><td>{item.goal}</td></tr>'
    else:
        tbody += f'<tr><td>ไม่มีรายละเอียดเป้าหมาย ให้ระบุเป้าหมายภายหลังจากกดปุ่มเลือกตัวชี้วัดนี้</td></tr>'
    tbody += '</tbody>'
    template += tbody
    template += '''</table>'''
    template += f'''<div class="field is-grouped is-grouped-centered">
                        <div class="control">
                            <a href="{url_for('pa.add_kpi_by_job_position', pa_id=pa_id, job_kpi_id=job_kpi_id)}"
                                                class="button">เลือกตัวชี้วัดนี้</a>
                        </div>
                    </div>'''
    return template


@pa.route('/pa/<int:pa_id>/position-kpis/<int:job_kpi_id>')
@login_required
def add_kpi_by_job_position(pa_id, job_kpi_id):
    pa = PAAgreement.query.get(pa_id)
    job_kpi = PAKPIJobPosition.query.filter_by(id=job_kpi_id).first()
    if job_kpi:
        for kpi in pa.kpis:
            if kpi.detail == job_kpi.detail:
                flash('มีตัวชี้วัดนี้แล้ว', 'warning')
                return redirect(url_for('pa.add_pa_item', round_id=pa.round_id, pa_id=pa_id))
        kpi = PAKPI(
            pa_id=pa_id,
            detail=job_kpi.detail,
            type=job_kpi.type
        )
        db.session.add(kpi)
        db.session.commit()
        for item in job_kpi.pa_kpi_job_positions:
            new_item = PAKPIItem(
                kpi_id=kpi.id,
                level=item.level,
                goal=item.goal
            )
            db.session.add(new_item)
        db.session.commit()
        if job_kpi.pa_kpi_job_positions:
            flash('เพิ่มตัวชี้วัดใหม่เรียบร้อยแล้ว', 'success')
            return redirect(url_for('pa.add_pa_item', round_id=pa.round_id, pa_id=pa_id))
        else:
            flash('เพิ่มตัวชี้วัดใหม่แล้ว กรุณาเพิ่มเป้าหมายและกดบันทึกด้านล่าง', 'success')
            return redirect(url_for('pa.edit_kpi', pa_id=pa_id, kpi_id=kpi.id, job_kpi_id=job_kpi_id))
    else:
        flash('เกิดข้อผิดพลาด ไม่พบตัวชี้วัด กรุณาติดต่อหน่วย IT', 'danger')
        return redirect(url_for('pa.add_pa_item', round_id=pa.round_id, pa_id=pa_id))


@pa.route('/<int:pa_id>/kpis/<int:kpi_id>/edit', methods=['GET', 'POST'])
@pa.route('/<int:pa_id>/kpis/<int:kpi_id>/job-kpis/<int:job_kpi_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_kpi(pa_id, kpi_id, job_kpi_id=None):
    kpi = PAKPI.query.get(kpi_id)
    pa = PAAgreement.query.get(pa_id)
    form = PAKPIForm(obj=kpi)
    if form.validate_on_submit():
        form.populate_obj(kpi)
        db.session.add(kpi)
        db.session.commit()
        flash('แก้ไขตัวชี้วัดเรียบร้อย', 'success')
        return redirect(url_for('pa.add_pa_item', round_id=pa.round_id))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('PA/add_kpi.html', form=form, round_id=pa.round_id, kpi_id=kpi_id, job_kpi_id=job_kpi_id)


@pa.route('/kpis/<int:kpi_id>/delete', methods=['DELETE'])
@login_required
def delete_kpi(kpi_id):
    kpi = PAKPI.query.get(kpi_id)
    try:
        db.session.delete(kpi)
        db.session.commit()
        flash('ลบตัวชี้วัดแล้ว', 'success')
    except exc.SQLAlchemyError:
        db.session.rollback()
        flash('ไม่สามารถลบตัวชี้วัดได้ เนื่องจากมีภาระงานที่อ้างถึง', 'danger')
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@pa.route('/staff/rounds/<int:round_id>/task/view')
@login_required
def view_pa_item(round_id):
    round = PARound.query.get(round_id)
    agreement = PAAgreement.query.all()
    return render_template('PA/view_task.html', round=round, agreement=agreement)


@pa.route('/pa/')
@login_required
def index():
    new_requests = PARequest.query.filter_by(supervisor_id=current_user.id).filter(PARequest.responded_at == None).all()
    is_head_committee = PACommittee.query.filter_by(staff=current_user, role='ประธานกรรมการ').first()
    committee = PACommittee.query.filter_by(staff=current_user).all()
    final_scoresheets = []
    pending_approved = []
    for committee in committee:
        final_scoresheet = PAScoreSheet.query.filter_by(committee_id=committee.id, is_consolidated=False,
                                                        is_final=False).all()
        for s in final_scoresheet:
            final_scoresheets.append(s)
        approved_scoresheet = PAApprovedScoreSheet.query.filter_by(committee_id=committee.id, approved_at=None).all()
        for a in approved_scoresheet:
            pending_approved.append(a)
    return render_template('PA/index.html', is_head_committee=is_head_committee, new_requests=new_requests,
                           final_scoresheets=final_scoresheets, pending_approved=pending_approved)


@pa.route('/hr/create-round', methods=['GET', 'POST'])
@login_required
@hr_permission.require()
def create_round():
    pa_round = PARound.query.all()
    employments = StaffEmployment.query.all()
    if request.method == 'POST':
        form = request.form
        start_d, end_d = form.get('dates').split(' - ')
        start = datetime.strptime(start_d, '%d/%m/%Y')
        end = datetime.strptime(end_d, '%d/%m/%Y')
        createround = PARound(
            start=start,
            end=end,
            desc=form.get('desc')
        )
        db.session.add(createround)
        db.session.commit()

        createround.employments = []
        for emp_id in form.getlist("employments"):
            employment = StaffEmployment.query.get(int(emp_id))
            createround.employments.append(employment)
            db.session.add(employment)
            db.session.commit()
        flash('เพิ่มรอบการประเมินใหม่เรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.create_round'))
    return render_template('staff/HR/PA/hr_create_round.html', pa_round=pa_round, employments=employments)


@pa.route('/hr/create-round/active/<int:round_id>', methods=['GET', 'POST'])
@login_required
@hr_permission.require()
def edit_active_round(round_id):
    pa_round = PARound.query.filter_by(id=round_id).first()
    pa_round.is_closed = False if pa_round.is_closed else True
    db.session.add(pa_round)
    db.session.commit()
    if pa_round.is_closed:
        flash('ปิดรอบ {} - {} เรียบร้อยแล้ว'.format(pa_round.start.strftime('%d/%m/%Y'),
                                                    pa_round.end.strftime('%d/%m/%Y')), 'warning')
    else:
        flash('เปิดปิดรอบ {} - {} แล้ว'.format(pa_round.start.strftime('%d/%m/%Y'),
                                                    pa_round.end.strftime('%d/%m/%Y')), 'success')
    return redirect(url_for('pa.create_round'))


@pa.route('/hr/add-committee', methods=['GET', 'POST'])
@login_required
@hr_permission.require()
def add_committee():
    form = PACommitteeForm()
    if form.validate_on_submit():
        is_committee = PACommittee.query.filter_by(staff=form.staff.data, org=form.org.data,
                                                   round=form.round.data).first()
        if form.subordinate.data:
            is_subordinate = PACommittee.query.filter_by(staff=form.staff.data, org=form.org.data,
                                                       round=form.round.data, subordinate=form.subordinate.data).first()
            if is_subordinate:
                flash('มีรายชื่อผู้ประเมิน ร่วมกับบุคคลนี้แล้ว', 'warning')
            else:
                committee = PACommittee()
                form.populate_obj(committee)
                db.session.add(committee)
                db.session.commit()
                flash('เพิ่มผู้ประเมินใหม่สำหรับทีมบริหารและหัวหน้าเรียบร้อยแล้ว', 'success')
        else:
            if is_committee:
                flash('มีรายชื่อผู้ประเมิน ร่วมกับหน่วยงานนี้แล้ว กรุณาตรวจสอบใหม่อีกครั้ง', 'warning')
            else:
                committee = PACommittee()
                form.populate_obj(committee)
                db.session.add(committee)
                db.session.commit()
                flash('เพิ่มผู้ประเมินใหม่เรียบร้อยแล้ว', 'success')
    else:
        for err in form.errors:
            flash('{}: {}'.format(err, form.errors[err]), 'danger')
    return render_template('staff/HR/PA/hr_add_committee.html', form=form)


@pa.route('/hr/committee')
@login_required
@hr_permission.require()
def show_committee():
    org_id = request.args.get('deptid', type=int)
    departments = Org.query.all()
    if org_id is None:
        committee_list = PACommittee.query.all()
    else:
        committee_list = PACommittee.query.filter_by(org_id=org_id).all()
    return render_template('staff/HR/PA/hr_show_committee.html',
                           sel_dept=org_id,
                           committee_list=committee_list,
                           departments=[{'id': d.id, 'name': d.name} for d in departments])


@pa.route('/hr/all-consensus-scoresheets', methods=['GET', 'POST'])
@login_required
@hr_permission.require()
def consensus_scoresheets_for_hr():
    if request.method == "POST":
        form = request.form
        round_id = int(form.get('round'))
        records = []
        scoresheets = PAScoreSheet.query.filter_by(is_consolidated=True, is_final=True, is_appproved=True)
        columns = [u'รอบการประเมิน', u'ประเภทการจ้าง', u'ชื่อ-นามสกุล',
                   u'สังกัด', u'Performance Score', u'Competency Score', u'คะแนนรวม', u'ระดับ']
        for scoresheet in scoresheets:
            if scoresheet.pa.round_id == round_id:
                if scoresheet.pa.performance_score and scoresheet.pa.competency_score:
                    sum_score = scoresheet.pa.performance_score + scoresheet.pa.competency_score
                    total = round(sum_score, 2)
                    if total >= 90:
                        level = 'ดีเด่น'
                    elif 80 <= total <= 89.99:
                        level = 'ดีมาก'
                    elif 70 <= total <= 79.99:
                        level = 'ดี'
                    elif 60 <= total <= 69.99:
                        level = 'พอใช้'
                    else:
                        level = 'ควรปรับปรุง'
                records.append({
                    columns[0]: u"{}".format(scoresheet.pa.round),
                    columns[1]: u"{}".format(scoresheet.pa.staff.personal_info.employment),
                    columns[2]: u"{}".format(scoresheet.pa.staff.personal_info.fullname),
                    columns[3]: u"{}".format(scoresheet.pa.staff.personal_info.org),
                    columns[4]: u"{}".format(
                        scoresheet.pa.performance_score if scoresheet.pa.performance_score else ""),
                    columns[5]: u"{}".format(scoresheet.pa.competency_score if scoresheet.pa.competency_score else ""),
                    columns[6]: u"{}".format(sum_score if sum_score else ""),
                    columns[7]: u"{}".format(level)
                })
        df = DataFrame(records, columns=columns)
        df.to_excel('pa_score.xlsx', index=False, columns=columns)
        return send_from_directory(os.getcwd(), 'pa_score.xlsx')
    else:
        all_rounds = PARound.query.all()
        rounds = PARound.query.all()
        employment_id = request.args.get('empid', type=int)
        round_id = request.args.get('roundid', type=int)
        employments = StaffEmployment.query.all()
        if employment_id is None:
            scoresheet_list = PAScoreSheet.query.filter_by(is_consolidated=True, is_final=True, is_appproved=True)
        else:
            employment_scoresheets = []
            scoresheet_list = PAScoreSheet.query.filter_by(is_consolidated=True, is_final=True, is_appproved=True).all()
            for scoresheet in scoresheet_list:
                if scoresheet.pa.staff.personal_info.employment_id == employment_id:
                    employment_scoresheets.append(scoresheet)
            scoresheet_list = employment_scoresheets
        if round_id:
            scoresheets = []
            for scoresheet in scoresheet_list:
                if scoresheet.pa.round_id == round_id:
                    scoresheets.append(scoresheet)
            scoresheet_list = scoresheets
        else:
            scoresheet_list = scoresheet_list

        return render_template('staff/HR/PA/hr_all_consensus_scores.html', all_rounds=all_rounds,
                               sel_emp=employment_id,
                               scoresheet_list=scoresheet_list,
                               employments=[{'id': e.id, 'title': e.title} for e in employments],
                               round=round_id,
                               rounds=[{'id': r.id,
                                        'round': r.desc+': '+r.start.strftime('%d/%m/%Y') + '-' + r.end.strftime('%d/%m/%Y')} for r
                                       in rounds])


@pa.route('/hr/all-consensus-scoresheetss/<int:scoresheet_id>')
@login_required
@hr_permission.require()
def detail_consensus_scoresheet_for_hr(scoresheet_id):
    consolidated_score_sheet = PAScoreSheet.query.filter_by(id=scoresheet_id).first()
    core_competency_items = PACoreCompetencyItem.query.all()
    return render_template('staff/HR/PA/hr_consensus_score_detail.html',
                           consolidated_score_sheet=consolidated_score_sheet,
                           core_competency_items=core_competency_items)


@pa.route('/pa/<int:pa_id>/requests', methods=['GET', 'POST'])
@login_required
def create_request(pa_id):
    pa = PAAgreement.query.get(pa_id)
    form = PARequestForm()
    head_committee = PACommittee.query.filter_by(org=current_user.personal_info.org, role='ประธานกรรมการ',
                                                 round=pa.round).first()
    head_individual = PACommittee.query.filter_by(subordinate=current_user, role='ประธานกรรมการ',
                                                  round=pa.round).first()
    if head_individual:
        supervisor = StaffAccount.query.filter_by(email=head_individual.staff.email).first()
    elif head_committee:
        supervisor = StaffAccount.query.filter_by(email=head_committee.staff.email).first()
    else:
        flash('ไม่พบกรรมการประเมิน กรุณาติดต่อหน่วย HR', 'warning')
        return redirect(url_for('pa.add_pa_item', round_id=pa.round_id))
    if form.validate_on_submit():
        new_request = PARequest()
        form.populate_obj(new_request)

        # Search for a pending request.
        # User must wait for the response before creating another request.
        pending_request = PARequest.query.filter_by(pa_id=pa_id, supervisor=supervisor) \
            .filter(PARequest.responded_at == None).first()
        if pending_request:
            flash('คำขอก่อนหน้านี้กำลังรอผลการอนุมัติ สามารถติดตามสถานะได้ที่'
                  ' "สถานะการประเมินภาระงาน" ซึ่งอยู่ด้านล่างของหน้าต่าง', 'warning')
            return redirect(url_for('pa.add_pa_item', round_id=pa.round_id))

        if new_request.for_ == 'ขอรับการประเมิน':
            if not pa.approved_at:
                flash('กรุณาขอรับรองภาระงานจากหัวหน้าส่วนงานก่อนทำการประเมิน', 'danger')
                return redirect(url_for('pa.add_pa_item', round_id=pa.round_id))
            elif pa.submitted_at:
                flash('ท่านได้ส่งภาระงานเพื่อขอรับการประเมินแล้ว', 'danger')
                return redirect(url_for('pa.add_pa_item', round_id=pa.round_id))
            else:
                self_scoresheet = pa.pa_score_sheet.filter(PAScoreSheet.staff_id == pa.staff.id).first()

                if not self_scoresheet or not self_scoresheet.confirm_at:
                    flash('กรุณาส่งคะแนนประเมินตนเองก่อนขอรับการประเมิน', 'warning')
                    return redirect(url_for('pa.add_pa_item', round_id=pa.round_id))

                pa.submitted_at = arrow.now('Asia/Bangkok').datetime
                db.session.add(pa)
                db.session.commit()
        elif new_request.for_ == 'ขอแก้ไข' and pa.submitted_at:
            flash('ท่านได้ส่งภาระงานเพื่อขอรับการประเมินแล้ว ไม่สามารถขอแก้ไขได้', 'danger')
            return redirect(url_for('pa.add_pa_item', round_id=pa.round_id))
        elif new_request.for_ == 'ขอรับรอง' and pa.approved_at:
            flash('ภาระงานของท่านได้รับการรับรองแล้ว', 'danger')
            return redirect(url_for('pa.add_pa_item', round_id=pa.round_id))

        if new_request.for_ == 'ขอรับรอง':
            pa_items = PAItem.query.filter_by(pa_id=pa_id).all()
            total_percentage = 0
            for item in pa_items:
                if not item.kpi_items:
                    flash('กรุณาระบุตัวชี้วัดให้ครบในทุกภาระงาน', 'danger')
                    return redirect(url_for('pa.add_pa_item', round_id=pa.round_id))
                else:
                    total_percentage += item.percentage
            if total_percentage < 100:
                flash('สัดส่วนภาระงานทั้งหมด น้อยกว่าร้อยละ 100 ', 'danger')
                return redirect(url_for('pa.add_pa_item', round_id=pa.round_id))

        new_request.pa_id = pa_id
        right_now = arrow.now('Asia/Bangkok').datetime
        new_request.created_at = right_now
        new_request.submitted_at = right_now
        new_request.supervisor = supervisor
        db.session.add(new_request)
        db.session.commit()
        req_msg = '{}ทำการขออนุมัติ{} ในระบบ PA กรุณาคลิก link เพื่อดำเนินการต่อไป {}' \
                  '\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(
            current_user.personal_info.fullname, new_request.for_,
            url_for("pa.view_request", request_id=new_request.id, _external=True))
        req_title = 'แจ้งการอนุมัติ' + new_request.for_ + 'ในระบบ PA'
        if not current_app.debug:
            send_mail([supervisor.email + "@mahidol.ac.th"], req_title, req_msg)
        else:
            print(req_msg, supervisor.email)
        flash('ส่งคำขอเรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.add_pa_item', round_id=pa.round_id))
    return render_template('PA/request_form.html', form=form, pa=pa)


@pa.route('/head/requests')
@login_required
def all_request():
    end_round_year = set()
    all_requests = []
    for req in PARequest.query.filter_by(supervisor_id=current_user.id).filter(PARequest.submitted_at != None):
        end_year = req.pa.round.end.year
        end_round_year.add(end_year)
        delta = datetime.today().date() - req.created_at.date()
        if delta.days < 60:
            all_requests.append(req)
    current_requests = []
    for pa in PAAgreement.query.join(PARequest).filter(PARequest.supervisor_id == current_user.id and PARequest.submitted_at != None):
        if pa.round.is_closed != True:
            req_ = pa.requests.order_by(PARequest.submitted_at.desc()).first()
            current_requests.append(req_)
    return render_template('PA/head_all_request.html', all_requests=all_requests, current_requests=current_requests,
                           end_round_year=end_round_year)


@pa.route('/head/request/others_year/<int:end_round_year>')
@login_required
def all_request_others_year(end_round_year=None):
    requests = []
    all_request = PARequest.query.filter_by(supervisor_id=current_user.id).filter(PARequest.submitted_at != None).all()
    for req in all_request:
        if req.pa.round.end.year == end_round_year:
            requests.append(req)
    all_req = requests

    year_requests = []
    for pa in PAAgreement.query.filter(PARequest.supervisor_id == current_user.id and PARequest.submitted_at != None):
        if pa.round.end.year == end_round_year:
            req_ = pa.requests.order_by(PARequest.submitted_at.desc()).first()
            year_requests.append(req_)
    return render_template('PA/head_all_request_others_year.html', all_req=all_req, requests=requests,
                           end_round_year=end_round_year, year_requests=year_requests)


@pa.route('/head/request/<int:request_id>/detail')
@login_required
def view_request(request_id):
    categories = PAItemCategory.query.all()
    req = PARequest.query.get(request_id)
    return render_template('PA/head_respond_request.html', categories=categories, req=req)


@pa.route('/head/request/<int:request_id>', methods=['GET', 'POST'])
@login_required
def respond_request(request_id):
    # TODO: protect button assign committee in template when created committees list(in paagreement)
    req = PARequest.query.get(request_id)
    if request.method == 'POST':
        form = request.form
        req.status = form.get('approval')
        if req.status == 'อนุมัติ':
            if req.for_ == 'ขอรับรอง':
                req.pa.approved_at = arrow.now('Asia/Bangkok').datetime
            elif req.for_ == 'ขอแก้ไข':
                req.pa.approved_at = None
        else:
            if req.for_ == 'ขอรับการประเมิน':
                req.pa.submitted_at = None
        req.responded_at = arrow.now('Asia/Bangkok').datetime
        req.supervisor_comment = form.get('supervisor_comment')
        db.session.add(req)
        db.session.commit()
        flash('ดำเนินการเรียบร้อยแล้ว', 'success')

        req_msg = '{} {}คำขอในระบบ PA ท่านแล้ว รายละเอียดกรุณาคลิก link {}' \
                  '\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(
            current_user.personal_info.fullname, req.status,
            url_for("pa.add_pa_item", round_id=req.pa.round_id, pa_id=req.pa_id, _external=True))
        req_title = 'แจ้งผลคำขอ PA'
        if not current_app.debug:
            send_mail([req.pa.staff.email + "@mahidol.ac.th"], req_title, req_msg)
        else:
            print(req_msg, req.pa.staff.email)
    return redirect(url_for('pa.view_request', request_id=request_id))


@pa.route('/head/create-scoresheet/<int:pa_id>', methods=['GET', 'POST'])
@login_required
def create_scoresheet(pa_id):
    pa = PAAgreement.query.filter_by(id=pa_id).first()
    committee = PACommittee.query.filter_by(round=pa.round, role='ประธานกรรมการ', subordinate=pa.staff).first()
    if not committee:
        committee = PACommittee.query.filter_by(org=pa.staff.personal_info.org, role='ประธานกรรมการ',
                                                round=pa.round).first()
        if not committee:
            flash('ไม่สามารถสร้าง scoresheet ได้ กรุณาติดต่อหน่วยIT', 'warning')
            return redirect(request.referrer)
    scoresheet = PAScoreSheet.query.filter_by(pa=pa, committee_id=committee.id, is_consolidated=False).first()
    if not scoresheet:
        create_score_sheet = PAScoreSheet(
            pa_id=pa_id,
            committee_id=committee.id
        )
        db.session.add(create_score_sheet)
        db.session.commit()

        pa_item = PAItem.query.filter_by(pa_id=pa_id).all()
        for item in pa_item:
            for kpi_item in item.kpi_items:
                create_score_sheet_item = PAScoreSheetItem(
                    score_sheet_id=create_score_sheet.id,
                    item_id=item.id,
                    kpi_item_id=kpi_item.id
                )
                db.session.add(create_score_sheet_item)
                db.session.commit()
        return redirect(url_for('pa.all_performance', scoresheet_id=create_score_sheet.id))
    else:
        return redirect(url_for('pa.all_performance', scoresheet_id=scoresheet.id))


@pa.route('/create-scoresheet/<int:pa_id>/self-evaluation', methods=['GET', 'POST'])
@login_required
def create_scoresheet_for_self_evaluation(pa_id):
    pa = PAAgreement.query.get(pa_id)
    pa_items = PAItem.query.filter_by(pa_id=pa_id).all()
    for item in pa_items:
        if not item.kpi_items:
            flash('กรุณาระบุตัวชี้วัดให้ครบในทุกภาระงาน', 'danger')
            return redirect(url_for('pa.add_pa_item', round_id=pa.round_id))

    scoresheet = PAScoreSheet.query.filter_by(pa_id=pa_id, staff=current_user).first()
    if not scoresheet:
        scoresheet = PAScoreSheet(pa_id=pa_id, staff=current_user)
        pa_items = PAItem.query.filter_by(pa_id=pa_id).all()
        for item in pa_items:
            for kpi_item in item.kpi_items:
                scoresheet_item = PAScoreSheetItem(
                    item_id=item.id,
                    kpi_item_id=kpi_item.id
                )
                db.session.add(scoresheet_item)
                scoresheet.score_sheet_items.append(scoresheet_item)
        db.session.add(scoresheet)
        db.session.commit()
    return redirect(url_for('pa.rate_performance',
                            scoresheet_id=scoresheet.id,
                            for_self='true')
                    )


@pa.route('/head/confirm-send-scoresheet/<int:pa_id>', methods=['GET', 'POST'])
@login_required
def confirm_send_scoresheet_for_committee(pa_id):
    pa = PAAgreement.query.get(pa_id)
    if pa.committees:
        committee = PACommittee.query.filter_by(round=pa.round, subordinate=pa.staff).filter(
            PACommittee.staff != current_user).all()
        if not committee:
            committee = PACommittee.query.filter_by(round=pa.round, org=pa.staff.personal_info.org).filter(
                PACommittee.staff != current_user).all()
        for c in pa.committees:
            scoresheet = PAScoreSheet.query.filter_by(pa_id=pa_id, committee_id=c.id).first()
            is_confirm = True if scoresheet else False
        return render_template('PA/head_confirm_send_scoresheet.html', pa=pa, committee=committee,
                               is_confirm=is_confirm)
    else:
        flash('กรุณาระบุกลุ่มผู้ประเมินก่อนส่งแบบประเมินไปยังกรรรมการ (ปุ่ม กรรมการ)', 'warning')
        return redirect(url_for('pa.all_approved_pa'))


@pa.route('/head/create-scoresheet/<int:pa_id>/for-committee', methods=['GET', 'POST'])
@login_required
def create_scoresheet_for_committee(pa_id):
    pa = PAAgreement.query.get(pa_id)
    mails = []
    if pa.committees:
        for c in pa.committees:
            scoresheet = PAScoreSheet.query.filter_by(pa_id=pa_id, committee_id=c.id).first()
            if not scoresheet:
                create_scoresheet = PAScoreSheet(
                    pa_id=pa_id,
                    committee_id=c.id
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
            mails.append(c.staff.email + "@mahidol.ac.th")
        req_title = 'แจ้งคำขอเข้ารับการประเมินการปฏิบัติงาน(PA)'
        req_msg = '{} ขอรับการประเมิน PA กรุณาดำเนินการตาม Link ที่แนบมานี้ {}' \
                  '\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(pa.staff.personal_info.fullname,
                                                                                       url_for("pa.index",
                                                                                               _external=True))
        if not current_app.debug:
            send_mail(mails, req_title, req_msg)
        else:
            print(req_msg, pa.staff.personal_info.fullname)
        flash('ส่งการประเมินไปยังกลุ่มผู้ประเมินเรียบร้อยแล้ว', 'success')
    else:
        flash('กรุณาระบุกลุ่มผู้ประเมินก่อนส่งแบบประเมินไปยังกรรรมการ (ปุ่ม กรรมการ)', 'warning')
    return redirect(url_for('pa.all_approved_pa'))


@pa.route('/head/assign-committee/<int:pa_id>', methods=['GET', 'POST'])
@login_required
def assign_committee(pa_id):
    pa = PAAgreement.query.filter_by(id=pa_id).first()
    committee = PACommittee.query.filter_by(round=pa.round, subordinate=pa.staff).filter(
        PACommittee.staff != current_user).all()
    if not committee:
        committee = PACommittee.query.filter_by(round=pa.round, org=pa.staff.personal_info.org).filter(
            PACommittee.staff != current_user).all()
    if request.method == 'POST':
        form = request.form
        pa.committees = []
        for c_id in form.getlist("commitees"):
            committee = PACommittee.query.get(int(c_id))
            pa.committees.append(committee)
            db.session.add(committee)
            db.session.commit()
        flash('บันทึกกลุ่มผู้ประเมินเรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.all_approved_pa'))
    return render_template('PA/head_assign_committee.html', pa=pa, committee=committee)


@pa.route('/head/all-approved-pa')
@login_required
def all_approved_pa():
    end_round_year = set()
    pa_requests = PARequest.query.filter_by(supervisor=current_user, for_='ขอรับการประเมิน', status='อนุมัติ'
                                            ).filter(PARequest.responded_at != None).all()
    pa_request = []
    for p in pa_requests:
        end_year = p.pa.round.end.year
        end_round_year.add(end_year)
        if p.pa.round.is_closed != True:
            pa_request.append(p)

    pa_list = []
    pa_query = PAAgreement.query.filter_by(head_committee_staff_account=current_user).all()
    for pa in pa_query:
        if pa.round.is_closed != True:
            committee = PACommittee.query.filter_by(round=pa.round, role='ประธานกรรมการ', subordinate=pa.staff).first()
            if not committee:
                committee = PACommittee.query.filter_by(org=pa.staff.personal_info.org, role='ประธานกรรมการ',
                                                        round=pa.round).first()

            committee_id = committee.id

            is_final_head_scoresheet = False
            is_head_scoresheet = False
            head_scoresheet = PAScoreSheet.query.filter_by(pa=pa, is_consolidated=False, staff_id=None).filter(
                PAScoreSheet.committee_id == committee_id).first()
            if head_scoresheet:
                is_head_scoresheet = True
                if head_scoresheet.is_final:
                    is_final_head_scoresheet = True
            is_final_consolidated_head_scoresheet = False
            consolidated_head_scoresheet = PAScoreSheet.query.filter_by(pa=pa, is_consolidated=True).filter(
                PAScoreSheet.committee_id == committee_id).first()
            if consolidated_head_scoresheet:
                if consolidated_head_scoresheet.is_final:
                    is_final_consolidated_head_scoresheet = True

            is_committee = False
            is_confirm = False
            is_already_approved = False
            if pa.committees:
                is_committee = True
                committee = PACommittee.query.filter_by(round=pa.round, subordinate=pa.staff).filter(
                    PACommittee.staff != current_user).all()
                if not committee:
                    committee = PACommittee.query.filter_by(round=pa.round, org=pa.staff.personal_info.org).filter(
                        PACommittee.staff != current_user).all()
                for c in pa.committees:
                    scoresheet = PAScoreSheet.query.filter_by(pa_id=pa.id, committee_id=c.id).first()
                    is_confirm = True if scoresheet else False
                scoresheet = PAScoreSheet.query.filter_by(pa_id=pa.id, is_consolidated=True, is_final=True).first()
                if scoresheet:
                    already_approved_scoresheet = PAApprovedScoreSheet.query.filter_by(score_sheet_id=scoresheet.id,
                                                                                        committee_id=c.id).first()
                    if already_approved_scoresheet:
                        is_already_approved = True
            is_send_hr = True if pa.performance_score else False
            is_inform = True if pa.inform_score_at else False

            record = {}
            record["id"] = pa.id
            record["staff"] = pa.staff.fullname
            record["round"] = pa.round
            record["is_committee"] = is_committee
            record["is_confirm"] = is_confirm
            record["is_send_hr"] = is_send_hr
            record["is_inform"] = is_inform
            record["is_already_approved"] = is_already_approved
            record["is_head_scoresheet"] = is_head_scoresheet
            record["is_final_head_scoresheet"] = is_final_head_scoresheet
            record["is_final_consolidated_head_scoresheet"] = is_final_consolidated_head_scoresheet
            record["committees"] = [committees.staff.fullname for committees in pa.committees]
            pa_list.append(record)

    return render_template('PA/head_all_approved_pa.html', pa_request=pa_request, end_round_year=end_round_year,
                                pa_list=pa_list)


@pa.route('/head/all-approved-pa/others_year/<int:end_round_year>')
@login_required
def all_approved_others_year(end_round_year=None):
    pa_requests = PARequest.query.filter_by(supervisor=current_user, for_='ขอรับการประเมิน', status='อนุมัติ'
                                            ).filter(PARequest.responded_at != None).all()
    pa_request = []
    for p in pa_requests:
        if p.pa.round.end.year == end_round_year:
            pa_request.append(p)

    pa_list = []
    pa_query = PAAgreement.query.filter_by(head_committee_staff_account=current_user).all()
    for pa in pa_query:
        if pa.round.end.year == end_round_year:
            committee = PACommittee.query.filter_by(round=pa.round, role='ประธานกรรมการ', subordinate=pa.staff).first()
            if not committee:
                committee = PACommittee.query.filter_by(org=pa.staff.personal_info.org, role='ประธานกรรมการ',
                                                        round=pa.round).first()

            committee_id = committee.id

            is_final_head_scoresheet = False
            is_head_scoresheet = False
            head_scoresheet = PAScoreSheet.query.filter_by(pa=pa, is_consolidated=False, staff_id=None).filter(
                PAScoreSheet.committee_id == committee_id).first()
            if head_scoresheet:
                is_head_scoresheet = True
                if head_scoresheet.is_final:
                    is_final_head_scoresheet = True
            is_final_consolidated_head_scoresheet = False
            consolidated_head_scoresheet = PAScoreSheet.query.filter_by(pa=pa, is_consolidated=True).filter(
                PAScoreSheet.committee_id == committee_id).first()
            if consolidated_head_scoresheet:
                if consolidated_head_scoresheet.is_final:
                    is_final_consolidated_head_scoresheet = True

            is_committee = False
            is_confirm = False
            is_already_approved = False
            if pa.committees:
                is_committee = True
                committee = PACommittee.query.filter_by(round=pa.round, subordinate=pa.staff).filter(
                    PACommittee.staff != current_user).all()
                if not committee:
                    committee = PACommittee.query.filter_by(round=pa.round, org=pa.staff.personal_info.org).filter(
                        PACommittee.staff != current_user).all()
                for c in pa.committees:
                    scoresheet = PAScoreSheet.query.filter_by(pa_id=pa.id, committee_id=c.id).first()
                    is_confirm = True if scoresheet else False
                scoresheet = PAScoreSheet.query.filter_by(pa_id=pa.id, is_consolidated=True, is_final=True).first()
                if scoresheet:
                    already_approved_scoresheet = PAApprovedScoreSheet.query.filter_by(score_sheet_id=scoresheet.id,
                                                                                       committee_id=c.id).first()
                    if already_approved_scoresheet:
                        is_already_approved = True
            is_send_hr = True if pa.performance_score else False
            is_inform = True if pa.inform_score_at else False

            record = {}
            record["id"] = pa.id
            record["staff"] = pa.staff.fullname
            record["round"] = pa.round
            record["is_committee"] = is_committee
            record["is_confirm"] = is_confirm
            record["is_send_hr"] = is_send_hr
            record["is_inform"] = is_inform
            record["is_already_approved"] = is_already_approved
            record["is_head_scoresheet"] = is_head_scoresheet
            record["is_final_head_scoresheet"] = is_final_head_scoresheet
            record["is_final_consolidated_head_scoresheet"] = is_final_consolidated_head_scoresheet
            record["committees"] = [committees.staff.fullname for committees in pa.committees]
            pa_list.append(record)
    return render_template('PA/head_all_approved_others_year.html', pa_request=pa_request,
                           end_round_year=end_round_year, pa_list=pa_list)


@pa.route('/head/all-approved-pa/summary-scoresheet/<int:pa_id>', methods=['GET', 'POST'])
@login_required
def summary_scoresheet(pa_id):
    # TODO: fixed position of item
    pa = PAAgreement.query.filter_by(id=pa_id).first()
    committee = PACommittee.query.filter_by(round=pa.round, role='ประธานกรรมการ', subordinate=pa.staff).first()
    if not committee:
        committee = PACommittee.query.filter_by(org=pa.staff.personal_info.org, role='ประธานกรรมการ',
                                                round=pa.round).first()
        if not committee:
            flash('ไม่พบรายการสรุป scoresheet กรุณาติดต่อหน่วย IT', 'warning')
            return redirect(request.referrer)
    core_competency_items = PACoreCompetencyItem.query.all()
    consolidated_score_sheet = PAScoreSheet.query.filter_by(pa_id=pa_id, is_consolidated=True).filter(
        PACommittee.staff == current_user).first()
    if consolidated_score_sheet:
        score_sheet_items = PAScoreSheetItem.query.filter_by(score_sheet_id=consolidated_score_sheet.id).all()
    else:
        consolidated_score_sheet = PAScoreSheet(
            pa_id=pa_id,
            committee_id=committee.id,
            is_consolidated=True
        )
        db.session.add(consolidated_score_sheet)
        db.session.commit()

        pa_items = PAItem.query.filter_by(pa_id=pa_id).all()
        for item in pa_items:
            for kpi_item in item.kpi_items:
                consolidated_score_sheet_item = PAScoreSheetItem(
                    score_sheet_id=consolidated_score_sheet.id,
                    item_id=item.id,
                    kpi_item_id=kpi_item.id
                )
                db.session.add(consolidated_score_sheet_item)
                db.session.commit()
        for core_item in PACoreCompetencyItem.query.all():
            core_scoresheet_item = PACoreCompetencyScoreItem(
                score_sheet_id=consolidated_score_sheet.id,
                item_id=core_item.id,
            )
            db.session.add(core_scoresheet_item)
            db.session.commit()
        score_sheet_items = PAScoreSheetItem.query.filter_by(score_sheet_id=consolidated_score_sheet.id).all()
    approved_scoresheets = PAApprovedScoreSheet.query.filter_by(score_sheet_id=consolidated_score_sheet.id).all()
    if approved_scoresheets:
        for approve in approved_scoresheets:
            if not approve.approved_at:
                is_approved = False
                break;
            else:
                is_approved = True
    else:
        is_approved = None
    if request.method == 'POST':
        form = request.form
        for field, value in form.items():
            if field.startswith('pa-item-'):
                pa_item_id, kpi_item_id = field.split('-')[-2:]
                scoresheet_item = consolidated_score_sheet.score_sheet_items \
                    .filter_by(item_id=int(pa_item_id), kpi_item_id=int(kpi_item_id)).first()
                scoresheet_item.score = float(value) if value else None
                db.session.add(scoresheet_item)
            if field.startswith('core-'):
                core_scoresheet_id = field.split('-')[-1]
                core_scoresheet_item = consolidated_score_sheet.competency_score_items \
                    .filter_by(item_id=int(core_scoresheet_id)).first()
                core_scoresheet_item.score = float(value) if value else None
                db.session.add(core_scoresheet_item)
        consolidated_score_sheet.updated_at = arrow.now('Asia/Bangkok').datetime
        db.session.commit()
        flash('บันทึกผลค่าเฉลี่ยเรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.summary_scoresheet', pa_id=pa_id))
    return render_template('PA/head_summary_score.html',
                           score_sheet_items=score_sheet_items,
                           consolidated_score_sheet=consolidated_score_sheet,
                           approved_scoresheets=approved_scoresheets, core_competency_items=core_competency_items,
                           is_approved=is_approved)


@pa.route('/confirm-score/<int:scoresheet_id>')
@login_required
def confirm_score(scoresheet_id):
    for_self = request.args.get('for_self')
    next_url = request.args.get('next_url')
    scoresheet = PAScoreSheet.query.filter_by(id=scoresheet_id).first()
    scoresheet.is_final = True
    scoresheet.confirm_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(scoresheet)
    db.session.commit()
    flash('บันทึกคะแนนเรียบร้อยแล้ว', 'success')
    return redirect(url_for('pa.rate_performance',
                            next_url=next_url,
                            scoresheet_id=scoresheet_id,
                            for_self=for_self))


@pa.route('/confirm-final-score/<int:scoresheet_id>')
@login_required
def confirm_final_score(scoresheet_id):
    scoresheet = PAScoreSheet.query.filter_by(id=scoresheet_id).first()
    scoresheet.is_final = True
    scoresheet.confirm_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(scoresheet)
    db.session.commit()
    flash('บันทึกคะแนนเรียบร้อยแล้ว', 'success')
    return redirect(url_for('pa.summary_scoresheet', pa_id=scoresheet.pa_id))


@pa.route('/head/consensus-scoresheets/send-to-hr/<int:pa_id>')
@login_required
def send_consensus_scoresheets_to_hr(pa_id):
    consolidated_score_sheet = PAScoreSheet.query.filter_by(pa_id=pa_id, is_consolidated=True).filter(
        PACommittee.staff == current_user).first()
    if consolidated_score_sheet:
        scoresheet = PAScoreSheet.query.filter_by(id=consolidated_score_sheet.id).first()
    else:
        flash('ไม่พบคะแนนสรุป กรุณาสรุปผลคะแนนและรับรองผล ก่อนการส่งคะแนนไปยัง HR', 'warning')
        return redirect(request.referrer)

    pa_approved = PAApprovedScoreSheet.query.filter_by(score_sheet=scoresheet).all()
    if not pa_approved:
        flash('กรุณาส่งขอรับรองคะแนนยังคณะกรรมการ ก่อนส่งผลคะแนนไปยัง HR', 'warning')
        return redirect(request.referrer)
    for approved in pa_approved:
        if not approved.approved_at:
            flash('จำเป็นต้องมีการรับรองผลโดยคณะกรรมการทั้งหมด ก่อนส่งผลคะแนนไปยัง HR', 'warning')
            return redirect(request.referrer)
    pa_agreement = PAAgreement.query.filter_by(id=scoresheet.pa_id).first()
    if pa_agreement.performance_score:
        flash('ส่งคะแนนเรียบร้อยแล้ว', 'success')
    else:
        scoresheet.is_appproved = True
        db.session.add(scoresheet)
        db.session.commit()

        net_total = 0
        for pa_item in scoresheet.pa.pa_items:
            try:
                total_score = pa_item.total_score(scoresheet)
                net_total += total_score
            except ZeroDivisionError:
                flash('คะแนนไม่สมบูรณ์ กรุณาตรวจสอบความถูกต้อง', 'danger')
        if net_total > 0:
            performance_net_score = round(((net_total * 80) / 1000), 2)
            pa_agreement.performance_score = performance_net_score
            pa_agreement.competency_score = scoresheet.competency_net_score()
            db.session.add(pa_agreement)
            db.session.commit()

            pa = scoresheet.pa
            pa.evaluated_at = arrow.now('Asia/Bangkok').datetime
            db.session.add(pa)
            db.session.commit()
            flash('ส่งคะแนนไปยัง hr เรียบร้อยแล้ว', 'success')
    return redirect(request.referrer)


@pa.route('/head/consensus-scoresheets/calculate-score/<int:pa_id>', methods=["POST"])
@login_required
def calculate_total_score(pa_id):
    form = request.form
    performance_scores = defaultdict(list)
    core_competency_scores = []
    for field, value in form.items():
        if field.startswith('pa'):
            pa_item_id, kpi_item_id = field.split('-')[2:]
            pa_item = PAItem.query.get(pa_item_id)
            performance_scores[pa_item].append(float(value))
        elif field.startswith('core'):
            core_competency_scores.append(float(value) * 10)
    net_score = 0
    for pa_item, values in performance_scores.items():
        net_score += float(pa_item.percentage) * mean(values)
    performance_net_score = ((net_score * 80) / 1000)
    core_competency_scores = sum(core_competency_scores)
    competency_net_score = (core_competency_scores / 700) * 20
    return f'''<span class="box"><h2 class="title is-size-5">คะแนนภาระงาน = {round(performance_net_score, 2)}</h2>
    <h2 class="title is-size-5">คะแนนสมรรถนะหลัก = {round(competency_net_score, 2)}</h2>
    <h2 class="title is-size-4">คะแนนรวม = {round(performance_net_score + competency_net_score, 2)}</h2>
    </span>
    '''


@pa.route('/head/all-approved-pa/send_comment/<int:pa_id>', methods=['GET', 'POST'])
@login_required
def send_evaluation_comment(pa_id):
    consolidated_score_sheet = PAScoreSheet.query.filter_by(pa_id=pa_id, is_consolidated=True, is_final=True).filter(
        PACommittee.staff == current_user).first()
    pa = PAAgreement.query.filter_by(id=pa_id).first()
    if consolidated_score_sheet and pa.performance_score:
        consolidated_score_sheet = PAScoreSheet.query.filter_by(id=consolidated_score_sheet.id).first()
    else:
        flash('ไม่พบคะแนนสรุป กรุณาสรุปผลคะแนนและรับรองผล ก่อนส่งคะแนนไปยังผู้รับการประเมิน', 'warning')
        return redirect(request.referrer)

    core_competency_items = PACoreCompetencyItem.query.all()
    if request.method == 'POST':
        form = request.form
        consolidated_score_sheet.strengths = form.get('strengths')
        consolidated_score_sheet.weaknesses = form.get('weaknesses')
        db.session.add(consolidated_score_sheet)
        pa = PAAgreement.query.filter_by(id=consolidated_score_sheet.pa_id).first()
        pa.inform_score_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(pa)
        db.session.commit()

        req_msg = '{} แจ้งผลประเมินการปฏิบัติงานให้แก่ท่านแล้ว กรุณาคลิก link เพื่อดำเนินการรับทราบผล {}' \
                  '\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(
            current_user.personal_info.fullname,
            url_for("pa.accept_overall_score", pa_id=pa.id, _external=True))
        req_title = 'แจ้งผลประเมิน PA'
        if not current_app.debug:
            send_mail([pa.staff.email + "@mahidol.ac.th"], req_title, req_msg)
        else:
            print(req_msg, pa.staff.email)
        flash('แจ้งผลประเมินการปฏิบัติงานให้ผู้รับการประเมินทราบ เรียบร้อยแล้ว', 'success')
    return render_template('PA/head_evaluation_comment.html',
                           consolidated_score_sheet=consolidated_score_sheet,
                           core_competency_items=core_competency_items)


@pa.route('/head/all-pa/score')
@login_required
def all_pa_score():
    rounds = PARound.query.all()
    round_id = request.args.get('roundid', type=int)
    if round_id is None:
        all_pa = PAAgreement.query.filter_by(head_committee_staff_account=current_user).all()
    else:
        all_pa = PAAgreement.query.filter_by(round_id=round_id, head_committee_staff_account=current_user).all()
    pa_agreement = []
    pa_score = []
    excellent_score = 0
    verygood_score = 0
    good_score = 0
    fair_score = 0
    poor_score = 0
    for pa in all_pa:
        scoresheet = PAScoreSheet.query.filter_by(pa=pa, is_consolidated=True).first()
        if scoresheet:
            net_total = 0
            for pa_item in scoresheet.pa.pa_items:
                try:
                    total_score = pa_item.total_score(scoresheet)
                    net_total += total_score
                except ZeroDivisionError:
                    flash('คะแนนไม่สมบูรณ์ กรุณาตรวจสอบความถูกต้อง', 'danger')
            if net_total > 0:
                performance_net_score = round(((net_total * 80) / 1000), 2)
                record = {}
                record["id"] = pa.id
                record["performance_score"] = performance_net_score
                record["competency_score"] = scoresheet.competency_net_score()
                total = performance_net_score + scoresheet.competency_net_score()
                total = round(total, 2)
                record["total"] = total
                record["is_final"] = scoresheet.is_final
                record["round_desc"] = pa.round.desc
                record["round"] = pa.round
                record["name"] = pa.staff.fullname

                if total >= 90:
                    level = 'ดีเด่น'
                    excellent_score += 1
                elif 80 <= total <= 89.99:
                    level = 'ดีมาก'
                    verygood_score += 1
                elif 70 <= total <= 79.99:
                    level = 'ดี'
                    good_score += 1
                elif 60 <= total <= 69.99:
                    level = 'พอใช้'
                    fair_score += 1
                else:
                    level = 'ควรปรับปรุง'
                    poor_score += 1
                record["level"] = level
                pa_agreement.append(record)
    score = {}
    score["excellent_score"] = excellent_score
    score["verygood_score"] = verygood_score
    score["good_score"] = good_score
    score["fair_score"] = fair_score
    score["poor_score"] = poor_score
    pa_score.append(score)
    return render_template('PA/head_all_score.html', round_id=round_id, pa_agreement=pa_agreement,
                           rounds=[{'id': r.id, 'round': r.desc+':'+r.start.strftime('%d/%m/%Y')+'-'+r.end.strftime('%d/%m/%Y')}
                                   for r in rounds], pa_score=pa_score)


@pa.route('/overall-score/<int:pa_id>')
@login_required
def accept_overall_score(pa_id):
    consolidated_score_sheet = PAScoreSheet.query.filter_by(pa_id=pa_id, is_consolidated=True).filter(
        PAAgreement.inform_score_at != None).first()
    if consolidated_score_sheet:
        consolidated_score_sheet = PAScoreSheet.query.filter_by(id=consolidated_score_sheet.id).first()
    else:
        flash('ยังไม่พบข้อมูลผลการประเมิน กรุณาติดต่อผู้บังคับบัญชาชั้นต้น', 'warning')
        return redirect(request.referrer)

    core_competency_items = PACoreCompetencyItem.query.all()
    return render_template('PA/overall_score.html',
                           consolidated_score_sheet=consolidated_score_sheet,
                           core_competency_items=core_competency_items)


@pa.route('/overall-score/<int:pa_id>/accept/<int:scoresheet_id>')
@login_required
def stamp_accept_score(pa_id, scoresheet_id):
    pa = PAAgreement.query.get(pa_id)
    pa.accept_score_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(pa)
    db.session.commit()
    flash('บันทึกข้อมูล การรับทราบผลประเมินเรียบร้อยแล้ว', 'success')

    consolidated_score_sheet = PAScoreSheet.query.filter_by(id=scoresheet_id).first()
    core_competency_items = PACoreCompetencyItem.query.all()
    return render_template('PA/overall_score.html',
                           consolidated_score_sheet=consolidated_score_sheet,
                           core_competency_items=core_competency_items)


@pa.route('/eva/rate_performance/<int:scoresheet_id>', methods=['GET', 'POST'])
@login_required
def rate_performance(scoresheet_id):
    for_self = request.args.get('for_self', 'false')
    scoresheet = PAScoreSheet.query.get(scoresheet_id)
    pa = PAAgreement.query.get(scoresheet.pa_id)
    committee = PACommittee.query.filter_by(round=pa.round, role='ประธานกรรมการ', subordinate=pa.staff).first()
    if not committee:
        committee = PACommittee.query.filter_by(org=pa.staff.personal_info.org, role='ประธานกรรมการ',
                                                round=pa.round).first()
        if not committee:
            flash('ไม่พบรายการให้คะแนน scoresheet กรุณาติดต่อหน่วย IT', 'warning')
            return redirect(request.referrer)
    total_percentage = 0
    for item in scoresheet.pa.pa_items:
        if not item.kpi_items:
            flash('ตัวชี้วัดไม่ครบ กรุณาติดต่อผู้รับการประเมินเพื่อปรับให้สมบูรณ์ก่อนเริ่มการประเมิน', 'danger')
            return redirect(url_for('pa.all_performance', scoresheet_id=scoresheet_id))
        else:
            total_percentage += item.percentage
    if total_percentage < 100:
        flash(
            'สัดส่วนภาระงานทั้งหมด น้อยกว่าร้อยละ 100 กรุณาติดต่อผู้รับการประเมินเพื่อปรับให้สมบูรณ์ก่อนเริ่มการประเมิน',
            'danger')
        return redirect(url_for('pa.all_performance', scoresheet_id=scoresheet_id))
    head_scoresheet = PAScoreSheet.query.filter_by(pa=pa, committee=committee, is_consolidated=False).first()
    self_scoresheet = pa.pa_score_sheet.filter(PAScoreSheet.staff_id == pa.staff.id).first()
    core_competency_items = PACoreCompetencyItem.query.all()
    if for_self == 'true':
        next_url = url_for('pa.add_pa_item', round_id=pa.round_id)
    else:
        next_url = ''

    if request.method == 'POST':
        form = request.form
        for field, value in form.items():
            if field.startswith('pa-item-'):
                scoresheet_item_id = field.split('-')[-1]
                scoresheet_item = PAScoreSheetItem.query.get(scoresheet_item_id)
                scoresheet_item.score = float(value) if value else None
                db.session.add(scoresheet_item)
            if field.startswith('core-'):
                comp_item_id = field.split('-')[-1]
                score_item = PACoreCompetencyScoreItem.query.filter_by(item_id=int(comp_item_id),
                                                                       score_sheet_id=scoresheet.id).first()
                if score_item is None:
                    score_item = PACoreCompetencyScoreItem(item_id=comp_item_id,
                                                           score=float(value) if value else None,
                                                           score_sheet_id=scoresheet.id)
                else:
                    score_item.score = float(value) if value else None
                db.session.add(score_item)
        scoresheet.updated_at = arrow.now('Asia/Bangkok').datetime
        db.session.commit()
        flash('บันทึกผลการประเมินแล้ว', 'success')
    return render_template('PA/eva_rate_performance.html',
                           scoresheet=scoresheet,
                           head_scoresheet=head_scoresheet,
                           self_scoresheet=self_scoresheet,
                           next_url=next_url,
                           core_competency_items=core_competency_items,
                           for_self=for_self)


@pa.route('/eva/all_performance/<int:scoresheet_id>')
@login_required
def all_performance(scoresheet_id):
    scoresheet = PAScoreSheet.query.filter_by(id=scoresheet_id).first()
    is_head_committee = PACommittee.query.filter_by(staff=current_user, role='ประธานกรรมการ').first()
    return render_template('PA/eva_all_performance.html', scoresheet=scoresheet, is_head_committee=is_head_committee)


@pa.route('/eva/create-consensus-scoresheets/<int:pa_id>')
@login_required
def create_consensus_scoresheets(pa_id):
    pa = PAAgreement.query.filter_by(id=pa_id).first()
    scoresheet = PAScoreSheet.query.filter_by(pa_id=pa_id, is_consolidated=True, is_final=True).first()
    if not scoresheet:
        flash('ยังไม่มีข้อมูลคะแนนสรุปจากคณะกรรมการ กรุณาดำเนินการใส่คะแนนและยืนยันผล', 'warning')
    else:
        if pa.committees:
            mails = []
            for c in pa.committees:
                already_approved_scoresheet = PAApprovedScoreSheet.query.filter_by(score_sheet_id=scoresheet.id,
                                                                                   committee_id=c.id).first()
                if not already_approved_scoresheet:
                    create_approvescore = PAApprovedScoreSheet(
                        score_sheet_id=scoresheet.id,
                        committee_id=c.id
                    )
                    db.session.add(create_approvescore)
                    db.session.commit()
                    mails.append(c.staff.email + "@mahidol.ac.th")

            req_title = 'แจ้งขอรับรองผลการประเมิน PA'
            req_msg = 'กรุณาดำเนินการรับรองคะแนนการประเมินของ {} ตาม Link ที่แนบมานี้ {} หากมีข้อแก้ไข กรุณาติดต่อผู้บังคับบัญชาขั้นต้นโดยตรง' \
                      '\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(
                pa.staff.personal_info.fullname,
                url_for("pa.consensus_scoresheets", _external=True))
            if not current_app.debug and mails:
                send_mail(mails, req_title, req_msg)
            else:
                print(req_msg)
            flash('ส่งคำขอรับรองผลการประเมินไปยังกลุ่มกรรมการเรียบร้อยแล้ว', 'success')
        else:
            flash('ไม่พบกลุ่มกรรมการ กรุณาเพิ่มกรรมการก่อนส่งขอรับรองคะแนน', 'danger')
    return redirect(url_for('pa.summary_scoresheet', pa_id=pa.id))


@pa.route('/eva/consensus-scoresheets')
@login_required
def consensus_scoresheets():
    committee = PACommittee.query.filter_by(staff=current_user).all()
    approved_scoresheets = []
    for committee in committee:
        approved_scoresheet = PAApprovedScoreSheet.query.filter_by(committee_id=committee.id).all()
        for s in approved_scoresheet:
            approved_scoresheets.append(s)
    if not committee:
        flash('สำหรับคณะกรรมการประเมิน PA เท่านั้น ขออภัยในความไม่สะดวก', 'warning')
        return redirect(url_for('pa.index'))
    return render_template('PA/eva_consensus_scoresheet.html', approved_scoresheets=approved_scoresheets)


@pa.route('/eva/consensus-scoresheets/<int:approved_id>', methods=['GET', 'POST'])
@login_required
def detail_consensus_scoresheet(approved_id):
    approve_scoresheet = PAApprovedScoreSheet.query.filter_by(id=approved_id).first()
    consolidated_score_sheet = PAScoreSheet.query.filter_by(id=approve_scoresheet.score_sheet_id).first()
    core_competency_items = PACoreCompetencyItem.query.all()
    if request.method == 'POST':
        approve_scoresheet.approved_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(approve_scoresheet)
        db.session.commit()
        flash('บันทึกการอนุมัติเรียบร้อยแล้ว', 'success')

        approve_title = 'แจ้งสถานะรับรองผลการประเมิน PA จากกรรมการ'
        approve_msg = '{} ดำเนินการรับรองคะแนนการประเมินของ {} เรียบร้อยแล้ว' \
                      '\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(
            approve_scoresheet.committee.staff.personal_info.fullname,
            consolidated_score_sheet.pa.staff.personal_info.fullname)
        if not current_app.debug:
            send_mail([consolidated_score_sheet.committee.staff.email + "@mahidol.ac.th"], approve_title, approve_msg)
        else:
            print(approve_msg, consolidated_score_sheet.committee.staff.email)
        return redirect(url_for('pa.consensus_scoresheets'))
    return render_template('PA/eva_consensus_scoresheet_detail.html', consolidated_score_sheet=consolidated_score_sheet,
                           approve_scoresheet=approve_scoresheet, core_competency_items=core_competency_items)


@pa.route('/eva/all-scoresheet')
@login_required
def all_scoresheet():
    committee = PACommittee.query.filter_by(staff=current_user).all()
    scoresheets = []
    end_round_year = set()
    for committee in committee:
        scoresheet = PAScoreSheet.query.filter_by(committee_id=committee.id, is_consolidated=False).all()
        for s in scoresheet:
            end_year = s.pa.round.end.year
            end_round_year.add(end_year)
            if s.pa.round.is_closed != True:
                scoresheets.append(s)
    if not committee:
        flash('สำหรับคณะกรรมการประเมิน PA เท่านั้น ขออภัยในความไม่สะดวก', 'warning')
        return redirect(url_for('pa.index'))
    return render_template('PA/eva_all_scoresheet.html', scoresheets=scoresheets, end_round_year=end_round_year)


@pa.route('/eva/all-scoresheet/year/<int:end_round_year>')
@login_required
def all_scoresheet_others_year(end_round_year=None):
    committee = PACommittee.query.filter_by(staff=current_user).all()
    scoresheets = []
    for committee in committee:
        scoresheet = PAScoreSheet.query.filter_by(committee_id=committee.id, is_consolidated=False).all()
        for s in scoresheet:
            if s.pa.round.end.year == end_round_year:
                scoresheets.append(s)
    return render_template('PA/eva_all_scoresheet_others_year.html', scoresheets=scoresheets,
                           end_round_year=end_round_year)


@pa.route('/eva/rate_core_competency/<int:scoresheet_id>', methods=['GET', 'POST'])
@pa.route('/eva/<int:pa_id>/rate_core_competency', methods=['GET', 'POST'])
@login_required
def rate_core_competency(pa_id=None, scoresheet_id=None):
    next_url = request.args.get('next_url')
    for_self = request.args.get('for_self', 'false')
    pa = PAAgreement.query.get(pa_id)
    if pa_id:
        scoresheet = PAScoreSheet.query.filter_by(
            staff=current_user,
            pa_id=pa_id
        ).first()
    elif scoresheet_id:
        scoresheet = PAScoreSheet.query.get(scoresheet_id)

    if not scoresheet and for_self == 'true':
        scoresheet = PAScoreSheet(
            staff=current_user,
            pa_id=pa_id
        )

    if request.method == 'POST':
        for field, value in request.form.items():
            if field.startswith('item-'):
                comp_item_id = field.split('-')[-1]
                score_item = PACoreCompetencyScoreItem.query.filter_by(item_id=int(comp_item_id),
                                                                       score_sheet_id=scoresheet.id).first()
                if score_item is None:
                    score_item = PACoreCompetencyScoreItem(item_id=comp_item_id,
                                                           score=float(value) if value else None,
                                                           score_sheet_id=scoresheet.id)
                else:
                    score_item.score = float(value) if value else None
                db.session.add(score_item)
        pa.updated_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(pa)
        db.session.commit()
        flash('บันทึกผลการประเมินเรียบร้อย', 'success')
        if next_url:
            return redirect(next_url)
    core_competency_items = PACoreCompetencyItem.query.all()
    return render_template('PA/eva_core_competency.html',
                           core_competency_items=core_competency_items,
                           scoresheet=scoresheet,
                           next_url=next_url,
                           for_self=for_self)


@pa.route('/hr')
@login_required
@hr_permission.require()
def hr_index():
    return render_template('staff/HR/PA/pa_index.html')


@pa.route('/hr/all-scoresheets')
@login_required
@hr_permission.require()
def scoresheets_for_hr():
    scoresheets = PAScoreSheet.query.filter(PAScoreSheet.staff == None).all()
    self_scoresheets = PAScoreSheet.query.filter(PAScoreSheet.staff != None).all()
    return render_template('staff/HR/PA/hr_all_scoresheets.html',
                           scoresheets=scoresheets, self_scoresheets=self_scoresheets)


@pa.route('/hr/all-scoresheets/edit-status/<int:scoresheet_id>')
@login_required
@hr_permission.require()
def edit_confirm_scoresheet(scoresheet_id):
    scoresheet = PAScoreSheet.query.get(scoresheet_id)
    scoresheet.is_final = False
    scoresheet.is_appproved = False
    scoresheet.confirm_at = None
    if scoresheet.pa.performance_score:
        scoresheet.pa.performance_score = None
        scoresheet.pa.competency_score = None
        scoresheet.pa.inform_score_at = None
        scoresheet.pa.accept_score_at = None
        scoresheet.pa.evaluated_at = None
    db.session.add(scoresheet)
    if scoresheet.committee:
        approved_records = PAApprovedScoreSheet.query.filter_by(score_sheet_id=scoresheet_id).all()
        if approved_records:
            for approve in approved_records:
                approve.approved_at = None
        flash(
            'แก้ไขสถานะคะแนนของผู้ประเมิน: {} ผู้รับการประเมิน: {} เป็น"ไม่ยืนยัน" และลบการรับรองผลของกรรมการเรียบร้อยแล้ว'.format(
                scoresheet.committee.staff.personal_info.fullname, scoresheet.pa.staff.personal_info.fullname),
            'success')
    else:
        flash('แก้ไขสถานะคะแนนประเมินตนเอง {} เป็น"ไม่ยืนยัน" เรียบร้อยแล้ว'.format(
            scoresheet.pa.staff.personal_info.fullname), 'success')
    db.session.commit()
    return redirect(url_for('pa.scoresheets_for_hr'))


@pa.route('/hr/all-pa')
@login_required
@hr_permission.require()
def all_pa():
    pa = PAAgreement.query.all()
    return render_template('staff/HR/PA/hr_all_pa.html', pa=pa)


@pa.route('/rounds/<int:round_id>/pa/<int:pa_id>')
@login_required
def pa_detail(round_id, pa_id):
    pa_round = PARound.query.get(round_id)
    categories = PAItemCategory.query.all()
    if pa_id:
        pa = PAAgreement.query.get(pa_id)
    else:
        pa = PAAgreement.query.filter_by(round_id=round_id,
                                         staff=current_user).first()

    for kpi in pa.kpis:
        items = []
        for item in kpi.pa_kpi_items:
            items.append((item.id, item.goal))
    return render_template('staff/HR/PA/pa_detail.html',
                           pa_round=pa_round,
                           pa=pa,
                           categories=categories)


@pa.route('/hr/kpi-by-job-position', methods=['GET', 'POST'])
@login_required
@hr_permission.require()
def kpi_by_job_position():
    kpis = PAKPIJobPosition.query.all()
    form = PAKPIJobPositionForm()
    if form.validate_on_submit():
        kpi_job_position = PAKPIJobPosition()
        form.populate_obj(kpi_job_position)
        db.session.add(kpi_job_position)
        db.session.commit()
        flash('เพิ่มตัวชี้วัดใหม่เรียบร้อยแล้ว', 'success')
    else:
        for err in form.errors:
            flash('{}: {}'.format(err, form.errors[err]), 'danger')

    job_id = request.args.get('jobid', type=int)
    positions = StaffJobPosition.query.all()
    if job_id is None:
        job_kpi_list = PAKPIJobPosition.query.all()
    else:
        job_kpi_list = PAKPIJobPosition.query.filter_by(job_position_id=job_id).all()

    return render_template('staff/HR/PA/kpi_by_job_position.html', kpis=kpis,
                           job_id=job_id,
                           job_kpi_list=job_kpi_list,
                           positions=[{'id': p.id, 'name': p.th_title} for p in positions],
                           form=form)


@pa.route('/hr/kpi-by-job-position/item/<int:job_kpi_id>', methods=['GET', 'POST'])
@login_required
def add_kpi_job_position_item(job_kpi_id):
    job_kpi_items = PAKPIItemJobPosition.query.filter_by(job_kpi_id=job_kpi_id).all()
    job_kpi = PAKPIJobPosition.query.filter_by(id=job_kpi_id).first()
    form = PAKPIItemJobPositionForm()
    if form.validate_on_submit():
        job_kpi_item = PAKPIItemJobPosition()
        form.populate_obj(job_kpi_item)
        job_kpi_item.job_kpi_id = job_kpi_id
        db.session.add(job_kpi_item)
        db.session.commit()
        flash('เพิ่มเป้าหมายเรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.add_kpi_job_position_item', job_kpi_id=job_kpi_id))
    else:
        for err in form.errors:
            flash('{}: {}'.format(err, form.errors[err]), 'danger')
    return render_template('staff/HR/PA/kpi_by_job_detail.html', job_kpi_items=job_kpi_items, job_kpi=job_kpi,
                           form=form)


@pa.route('/hr/all-kpis-all-items')
@login_required
@hr_permission.require()
def all_kpi_all_item():
    kpis = PAKPI.query.all()
    items = PAItem.query.all()
    return render_template('staff/HR/PA/all_kpi_all_item.html', kpis=kpis, items=items)


@pa.route('/api/leave-used-quota/<int:staff_id>')
@login_required
def get_leave_used_quota(staff_id):
    leaves = []
    for used_quota in StaffLeaveUsedQuota.query.filter_by(staff_account_id=staff_id).all():
        leaves.append({
            'id': used_quota.id,
            'fiscal_year': used_quota.fiscal_year,
            'used_days': used_quota.used_days,
            'pending_days': used_quota.pending_days,
            'quota_days': used_quota.quota_days,
            'leave_type': used_quota.leave_type.type_
        })
    return jsonify(leaves)


@pa.route('/fc')
@login_required
def fc_result():
    if current_user.personal_info.academic_staff:
        flash('สำหรับบุคลากรสายสนับสนุน ขออภัยในความไม่สะดวก', 'warning')
        return redirect(url_for('staff.index'))
    else:
        all_result = PAFunctionalCompetencyEvaluation.query.filter_by(staff_account_id=current_user.id).all()
    return render_template('PA/fc_all_result.html', all_result=all_result)


@pa.route('/fc/detail/<int:evaluation_id>')
@login_required
def fc_details(evaluation_id):
    evaluation = PAFunctionalCompetencyEvaluation.query.filter_by(id=evaluation_id).first()
    emp_period = relativedelta(evaluation.round.end, evaluation.staff.personal_info.employed_date)
    org_head = Org.query.filter_by(head=evaluation.staff.email).first()

    focus_evaluation_results = []
    for eva_indicator in evaluation.evaluation_eva_indicator:
        if eva_indicator.indicator.level:
            if eva_indicator.indicator.level.period:
                if emp_period.years >= int(eva_indicator.indicator.level.period):
                    if eva_indicator.criterion_id == 1 or eva_indicator.criterion_id == 2:
                        focus_evaluation_results.append(eva_indicator)
        else:
            if org_head:
                if eva_indicator.criterion_id == 1 or eva_indicator.criterion_id == 2:
                    focus_evaluation_results.append(eva_indicator)

    return render_template('PA/fc_details.html', evaluation=evaluation, emp_period=emp_period,
                                org_head=org_head, focus_evaluation_results=focus_evaluation_results)


@pa.route('/pa/fc')
@login_required
def fc_all_evaluation():
    all_evaluation = PAFunctionalCompetencyEvaluation.query.filter_by(evaluator_account_id=current_user.id).filter(
        PAFunctionalCompetencyRound.is_closed != True).all()

    return render_template('PA/fc_all_evaluation.html', all_evaluation=all_evaluation)


@pa.route('/pa/fc/evaluate/<int:evaluation_id>', methods=['GET', 'POST'])
@login_required
def evaluate_fc(evaluation_id):
    evaluation = PAFunctionalCompetencyEvaluation.query.filter_by(id=evaluation_id).first()
    criteria = PAFunctionalCompetencyCriteria.query.all()
    emp_period = relativedelta(evaluation.round.end, evaluation.staff.personal_info.employed_date)
    is_evaluation_indicator = PAFunctionalCompetencyEvaluationIndicator.query.filter_by(
        evaluation_id=evaluation_id).first()
    org_head = Org.query.filter_by(head=evaluation.staff.email).first()
    if not is_evaluation_indicator:
        if org_head:
            all_competency = PAFunctionalCompetency.query.filter_by(
                job_position_id=None).all()
        else:
            all_competency = PAFunctionalCompetency.query.filter_by(
                job_position_id=evaluation.staff.personal_info.job_position_id).all()
        for fc in all_competency:
            indicators = PAFunctionalCompetencyIndicator.query.filter_by(function_id=fc.id).all()
            for indicator in indicators:
                create_evaluation_indicator = PAFunctionalCompetencyEvaluationIndicator(
                    evaluation_id=evaluation_id,
                    indicator_id=indicator.id
                )
                db.session.add(create_evaluation_indicator)
        db.session.commit()

    if request.method == 'POST':
        form = request.form
        for field, value in form.items():
            if field.startswith('evaluation-'):
                evaluation_indicator_id = field.split('-')[-1]
                evaluation_indicator = PAFunctionalCompetencyEvaluationIndicator.query.get(int(evaluation_indicator_id))
                evaluation_indicator.criterion_id = value if value else None
                db.session.add(evaluation_indicator)
        evaluation.updated_at = arrow.now('Asia/Bangkok').datetime
        db.session.commit()
        flash('บันทึกผลการประเมินแล้ว', 'success')
    return render_template('PA/fc_evaluate_performance.html', criteria=criteria, evaluation=evaluation,
                           emp_period=emp_period, org_head=org_head)


@pa.route('/pa/fc/evaluate/<int:evaluation_id>/confirm', methods=['GET', 'POST'])
@login_required
def evaluate_fc_confirm(evaluation_id):
    evaluation = PAFunctionalCompetencyEvaluation.query.filter_by(id=evaluation_id).first()
    evaluation.confirm_at = arrow.now('Asia/Bangkok').datetime
    db.session.commit()
    flash('confirm ผลการประเมินแล้ว', 'success')
    return redirect(url_for('pa.fc_all_evaluation'))


@pa.route('/hr/fc')
@login_required
@hr_permission.require()
def hr_fc_index():
    return render_template('staff/HR/PA/fc_index.html')


@pa.route('/hr/fc/add', methods=['GET', 'POST'])
@login_required
def add_fc():
    form = PAFCForm()
    if form.validate_on_submit():
        functional = PAFunctionalCompetency()
        form.populate_obj(functional)
        db.session.add(functional)
        db.session.commit()
        flash('เพิ่ม functional competency ใหม่เรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.add_fc'))
    else:
        for err in form.errors:
            flash('{}: {}'.format(err, form.errors[err]), 'danger')

    job_id = request.args.get('jobid', type=int)
    positions = StaffJobPosition.query.all()
    if job_id is None:
        fc_list = PAFunctionalCompetency.query.all()
    else:
        fc_list = PAFunctionalCompetency.query.filter_by(job_position_id=job_id).all()

    return render_template('staff/HR/PA/fc_add_employment.html',
                           job_id=job_id,
                           fc_list=fc_list,
                           positions=[{'id': p.id, 'name': p.th_title} for p in positions],
                           form=form)


@pa.route('/hr/fc/add/indicator/<int:job_position_id>', methods=['GET', 'POST'])
@login_required
def add_fc_indicator(job_position_id):
    FCIndicatorForm = create_fc_indicator_form(job_position_id)
    form = FCIndicatorForm()

    if form.validate_on_submit():
        functional = PAFunctionalCompetencyIndicator()
        form.populate_obj(functional)
        db.session.add(functional)
        db.session.commit()
        flash('เพิ่มตัวชี้วัดใหม่เรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.add_fc_indicator'))
    else:
        for err in form.errors:
            flash('{}: {}'.format(err, form.errors[err]), 'danger')

    indicators = []
    for i in PAFunctionalCompetency.query.filter_by(job_position_id=job_position_id).all():
        indicator = PAFunctionalCompetencyIndicator.query.filter_by(function_id=i.id).all()
        for ind in indicator:
            indicators.append(ind)
    fc = PAFunctionalCompetency.query.filter_by(job_position_id=job_position_id).first()
    return render_template('staff/HR/PA/fc_indicator.html', indicators=indicators, fc=fc, form=form)


@pa.route('/hr/fc/add/indicator/mc/<int:function_id>', methods=['GET', 'POST'])
@login_required
def add_mc_indicator(function_id):
    indicators = PAFunctionalCompetencyIndicator.query.filter_by(function_id=function_id).all()
    form = PAFCIndicatorForm()
    if form.validate_on_submit():
        functional = PAFunctionalCompetencyIndicator(
            function_id=function_id
        )
        form.populate_obj(functional)
        db.session.add(functional)
        db.session.commit()
        flash('เพิ่มตัวชี้วัดใหม่เรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.add_mc_indicator', function_id=function_id))
    else:
        for err in form.errors:
            flash('{}: {}'.format(err, form.errors[err]), 'danger')
    return render_template('staff/HR/PA/fc_indicator.html', indicators=indicators, form=form)


@pa.route('/hr/fc/add-round', methods=['GET', 'POST'])
@login_required
@hr_permission.require()
def add_fc_round():
    fc_round = PAFunctionalCompetencyRound.query.all()
    if request.method == 'POST':
        form = request.form
        start_d, end_d = form.get('dates').split(' - ')
        start = datetime.strptime(start_d, '%d/%m/%Y')
        end = datetime.strptime(end_d, '%d/%m/%Y')
        createround = PAFunctionalCompetencyRound(
            start=start,
            end=end,
            desc=form.get('desc')
        )
        db.session.add(createround)
        db.session.commit()

        flash('เพิ่มรอบการประเมิน Functional Competency ใหม่เรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.add_fc_round'))
    return render_template('staff/HR/PA/fc_add_round.html', fc_round=fc_round)


@pa.route('/hr/add-round/close/<int:round_id>', methods=['GET', 'POST'])
@login_required
@hr_permission.require()
def close_fc_round(round_id):
    fc_round = PAFunctionalCompetencyRound.query.filter_by(id=round_id).first()
    fc_round.is_closed = False if fc_round.is_closed else True
    db.session.add(fc_round)
    db.session.commit()
    if fc_round.is_closed:
        flash('ปิดรอบ {} - {} เรียบร้อยแล้ว'.format(fc_round.start.strftime('%d/%m/%Y'),
                                                    fc_round.end.strftime('%d/%m/%Y')), 'warning')
    else:
        flash('เปิดปิดรอบ {} - {} แล้ว'.format(fc_round.start.strftime('%d/%m/%Y'),
                                                    fc_round.end.strftime('%d/%m/%Y')), 'warning')
    return redirect(url_for('pa.add_fc_round'))


@pa.route('/hr/fc/evaluator')
@login_required
@hr_permission.require()
def fc_evaluator():
    fc_evaluator = PAFunctionalCompetencyEvaluation.query.all()
    return render_template('staff/HR/PA/fc_evaluator.html', fc_evaluator=fc_evaluator)


@pa.route('/hr/fc/evaluator/<int:evaluation_id>')
@login_required
@hr_permission.require()
def fc_evaluation_detail(evaluation_id):
    evaluation = PAFunctionalCompetencyEvaluation.query.filter_by(id=evaluation_id).first()
    emp_period = relativedelta(evaluation.round.end, evaluation.staff.personal_info.employed_date)
    org_head = Org.query.filter_by(head=evaluation.staff.email).first()

    focus_evaluation_results = []
    for eva_indicator in evaluation.evaluation_eva_indicator:
        if eva_indicator.indicator.level:
            if eva_indicator.indicator.level.period:
                if emp_period.years >= int(eva_indicator.indicator.level.period):
                    if eva_indicator.criterion_id == 1 or eva_indicator.criterion_id == 2:
                        focus_evaluation_results.append(eva_indicator)
        else:
            if org_head:
                if eva_indicator.criterion_id == 1 or eva_indicator.criterion_id == 2:
                    focus_evaluation_results.append(eva_indicator)

    return render_template('staff/HR/PA/fc_evaluation.html', evaluation=evaluation, emp_period=emp_period,
                                org_head=org_head, focus_evaluation_results=focus_evaluation_results)


@pa.route('/hr/fc/copy-pa-committee', methods=['GET', 'POST'])
@login_required
@hr_permission.require()
def copy_pa_committee():
    all_pa_round = PARound.query.all()
    fc_rounds = PAFunctionalCompetencyRound.query.all()
    if request.method == 'POST':
        form = request.form
        pa_round_id = form.get('pa_round')
        fc_round_id = form.get('fc_round')
        pa_committee = PACommittee.query.filter_by(round_id=pa_round_id, role='ประธานกรรมการ').all()
        for committee in pa_committee:
            evaluator_account_id = committee.staff_account_id
            if not committee.org.staff:
                fc_evaluator = PAFunctionalCompetencyEvaluation.query.filter_by(
                    staff_account_id=committee.subordinate_account_id,
                    evaluator_account_id=evaluator_account_id,
                    round_id=fc_round_id).first()
                if not fc_evaluator:
                    staff_account = StaffAccount.query.filter_by(id=committee.subordinate_account_id).first()
                    if staff_account.personal_info.academic_staff != True:
                        evaluator = PAFunctionalCompetencyEvaluation(
                            staff_account_id=committee.subordinate_account_id,
                            evaluator_account_id=evaluator_account_id,
                            round_id=fc_round_id
                        )
                        db.session.add(evaluator)
                    if committee.subordinate_account_id != evaluator_account_id:
                        idp = IDP(
                            staff_account_id=committee.subordinate_account_id,
                            approver_account_id=evaluator_account_id,
                            round_id=fc_round_id
                        )
                        db.session.add(idp)
            else:
                for staff in committee.org.staff:
                    staff_account = StaffAccount.query.filter_by(personal_id=staff.id).first()
                    staff_account_id = staff_account.id
                    fc_evaluator = PAFunctionalCompetencyEvaluation.query.filter_by(staff_account_id=staff_account_id,
                                                                                    evaluator_account_id=evaluator_account_id,
                                                                                    round_id=fc_round_id).first()
                    if not fc_evaluator:
                        if staff_account.personal_info.retired != True:
                            is_subordinate = PACommittee.query.filter_by(subordinate_account_id=staff_account_id,
                                                                     round_id=pa_round_id).first()
                            if not is_subordinate:
                                if staff_account_id != evaluator_account_id:
                                    if staff_account.personal_info.academic_staff != True:
                                        new_evaluator = PAFunctionalCompetencyEvaluation(
                                            staff_account_id=staff_account_id,
                                            evaluator_account_id=evaluator_account_id,
                                            round_id=fc_round_id
                                        )
                                        db.session.add(new_evaluator)
                                    idp = IDP(
                                        staff_account_id=staff_account_id,
                                        approver_account_id=evaluator_account_id,
                                        round_id=fc_round_id
                                    )
                                    db.session.add(idp)
        db.session.commit()
        flash('เพิ่มผู้ประเมินใหม่แล้ว', 'success')
        return redirect(url_for('pa.fc_evaluator'))
    return render_template('staff/HR/PA/fc_add_evaluator.html', all_pa_round=all_pa_round, fc_rounds=fc_rounds)


@pa.route('/api/pa-committee', methods=['POST'])
@login_required
@hr_permission.require()
def get_pa_committee():
    print(request.form)
    pa_round_id = request.form.get('pa_round')
    pa_committee = PACommittee.query.filter_by(round_id=pa_round_id, role='ประธานกรรมการ').all()

    template = '''<table id="pa-committee-table" class="table is-fullwidth")>
        <thead>
        <th>ผู้ประเมิน</th>
        <th>ผู้ถูกรับการประเมิน(กรณีหัวหน้า)</th>
        <th>ผู้ถูกรับการประเมิน</th>
        <th>หน่วยงาน</th>
        </thead>
    '''

    tbody = '<tbody>'
    for committee in pa_committee:
        tbody += f'<tr><td>{committee.staff.fullname}</td>'
        if committee.subordinate:
            tbody += f'<td>{committee.subordinate.fullname}</td>'
        else:
            tbody += f'<td></td>'
        tbody += f'<td>'
        for staff in committee.org.staff:
            tbody += f'{staff}/'
        tbody += f'</td>'
        tbody += f'<td>{committee.org}</td></tr>'
    tbody += '</tbody>'
    template += tbody
    template += '''</table>'''
    return template
  

@pa.route('/idp')
@login_required
def idp():
    all_idp = IDP.query.filter_by(staff=current_user).all()
    return render_template('PA/idp_info.html',
                           all_idp=all_idp)


@pa.route('/idp/details/<int:idp_id>', methods=['GET', 'POST'])
@pa.route('/idp/details/<int:idp_id>/edit/<int:idp_item_id>', methods=['GET', 'POST'])
@login_required
def idp_details(idp_id, idp_item_id=None):
    idp = IDP.query.filter_by(id=idp_id).first()
    idp_items = IDPItem.query.filter_by(idp_id=idp_id).all()
    budget = 0
    for item in idp_items:
        if item.budget:
            budget += item.budget
    if idp.staff.personal_info.academic_staff:
        over_budget = True if budget > 15000 else False
    else:
        over_budget = True if budget > 10000 else False
    if not idp_item_id:
        form = IDPItemForm()
    else:
        idp_item = IDPItem.query.get(idp_item_id)
        form = IDPItemForm(obj=idp_item)
    if form.validate_on_submit():
        idp_item = IDPItem.query.get(idp_item_id)
        if idp_item_id is None:
            idp_item = IDPItem()
            idp_item.idp_id = idp_id
        form.populate_obj(idp_item)
        idp_item.is_success = True if request.form.get('is_success') == 'yes' else False
        db.session.add(idp_item)
        db.session.commit()
        flash('เพิ่มข้อมูล IDP เรียบร้อยแล้ว', 'success')
    else:
        for er in form.errors:
            flash("{}:{}".format(er, form.errors[er]), 'danger')
    if request.headers.get('HX-Request') == 'true':
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('PA/idp_details.html',
                           idp_items=idp_items, idp=idp, over_budget=over_budget)


@pa.route('/idp/modal/<int:idp_id>', methods=['GET', 'POST'])
@pa.route('/idp/modal/<int:idp_id>/item/<int:idp_item_id>', methods=['GET', 'POST'])
@login_required
def idp_modal(idp_id, idp_item_id=None):
    if idp_item_id:
        idp_item = IDPItem.query.get(idp_item_id)
        form = IDPItemForm(obj=idp_item)
    else:
        form = IDPItemForm()
    return render_template('PA/idp_modal.html', form=form, idp_id=idp_id, idp_item_id=idp_item_id)


@pa.route('/idp/modal/<int:idp_id>/item/<int:idp_item_id>/report', methods=['GET', 'POST'])
@login_required
def idp_report_modal(idp_id, idp_item_id):
    idp_item = IDPItem.query.get(idp_item_id)
    form = IDPItemForm(obj=idp_item)
    return render_template('PA/idp_report_modal.html', form=form, idp_id=idp_id, idp_item_id=idp_item_id)


@pa.route('/idp/<int:idp_id>/items/<int:idp_item_id>/delete', methods=['DELETE'])
@login_required
def delete_idp_item(idp_id, idp_item_id):
    item = IDPItem.query.get(idp_item_id)
    db.session.delete(item)
    db.session.commit()
    resp = make_response()
    return resp


@pa.route('/idp/send-request/<int:idp_id>', methods=['GET', 'POST'])
@login_required
def idp_send_request(idp_id):
    form = IDPRequestForm()
    idp = IDP.query.filter_by(id=idp_id).first()
    if form.validate_on_submit():
        new_request = IDPRequest()
        form.populate_obj(new_request)

        pending_request = IDPRequest.query.filter_by(idp_id=idp_id).filter(IDPRequest.responded_at == None).first()
        if pending_request:
            flash('คำขอก่อนหน้านี้กำลังรอผลการอนุมัติ สามารถติดตามสถานะได้ที่'
                  ' "สถานะการประเมินภาระงาน" ซึ่งอยู่ด้านล่างของหน้าต่าง', 'warning')
            return redirect(url_for('pa.idp_details', idp_id=idp_id))

        if new_request.for_ == 'ขอรับการประเมิน':
            if not idp.approved_at:
                flash('กรุณาขอรับรอง IDP ก่อนขอรับการประเมิน', 'danger')
                return redirect(url_for('pa.idp_details', idp_id=idp_id))
            elif idp.submitted_at:
                flash('ท่านได้ส่งขอรับการประเมินแล้ว', 'warning')
                return redirect(url_for('pa.idp_details', idp_id=idp_id))
            else:
                idp.submitted_at = arrow.now('Asia/Bangkok').datetime
                db.session.add(idp)
                db.session.commit()
        elif new_request.for_ == 'ขอแก้ไข' and idp.submitted_at:
            flash('ท่านได้ส่งภาระงานเพื่อขอรับการประเมินแล้ว ไม่สามารถขอแก้ไขได้', 'danger')
            return redirect(url_for('pa.idp_details', idp_id=idp_id))
        elif new_request.for_ == 'ขอแก้ไข' and not idp.approved_at:
            flash('ท่านสามารถแก้ไขได้โดยไม่ต้องส่งคำขอ', 'warning')
            return redirect(url_for('pa.idp_details', idp_id=idp_id))
        elif new_request.for_ == 'ขอรับรอง' and idp.approved_at:
            flash('IDPของท่านได้รับการรับรองแล้ว', 'warning')
            return redirect(url_for('pa.idp_details', idp_id=idp_id))

        new_request.idp = idp
        new_request.approver = idp.approver
        new_request.submitted_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(new_request)
        db.session.commit()

        req_msg = '{}ส่งคำ{} IDP ในระบบ MIS กรุณาคลิก link เพื่อดำเนินการต่อไป {}' \
                  '\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(
                    idp.staff.fullname, new_request.for_, url_for("pa.idp_all_requests", _external=True))
        req_title = 'แจ้งการส่ง IDP'
        if not current_app.debug:
            send_mail([idp.approver.email + "@mahidol.ac.th"], req_title, req_msg)
        else:
            print(req_msg, idp.approver.email)
        flash('ส่งแผน IDP ไปยังผู้บังคับบัญชาชั้นต้นเรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.idp_details', idp_id=idp_id))
    return render_template('PA/idp_request_form.html', form=form, idp=idp)


@pa.route('/idp/deleted-request/<int:req_id>', methods=['DELETE'])
@login_required
def idp_delete_request(req_id):
    idp_req = IDPRequest.query.filter_by(id=req_id).first()
    flash('ลบคำขอ{} เรียบร้อย'.format(idp_req.for_), 'success')
    db.session.delete(idp_req)
    db.session.commit()
    idp = IDP.query.filter_by(id=idp_req.idp_id).first()
    req_msg = '{}ยกเลิกคำ{} IDP แล้ว' \
              '\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(idp.staff.fullname, idp_req.for_)
    req_title = 'แจ้งการส่ง IDP'
    if not current_app.debug:
        send_mail([idp.approver.email + "@mahidol.ac.th"], req_title, req_msg)
    else:
        print(req_msg, idp.approver.email)
    resp = make_response()
    return resp


@pa.route('/idp/head/all-requests')
@login_required
def idp_all_requests():
    all_requests = IDPRequest.query.filter_by(approver=current_user).join(IDP).filter(
                                        PAFunctionalCompetencyRound.is_closed != True).all()
    all_reviews = IDP.query.filter_by(approver=current_user).join(PAFunctionalCompetencyRound).filter(
        PAFunctionalCompetencyRound.is_closed != True, IDP.submitted_at != None).all()
    all_idp = IDP.query.filter_by(approver=current_user).join(PAFunctionalCompetencyRound).filter(
                                        PAFunctionalCompetencyRound.is_closed != True).all()
    current_requests = []
    for idp in IDP.query.join(IDPRequest).filter(IDPRequest.approver_id == current_user.id):
        if idp.round.is_closed != True:
            req_ = idp.idp_request.order_by(IDPRequest.submitted_at.desc()).first()
            current_requests.append(req_)
    return render_template('PA/idp_all_requests.html', all_requests=all_requests, all_idp=all_idp,
                            current_requests=current_requests, all_reviews=all_reviews)


@pa.route('/idp/head/request/<int:request_id>', methods=['GET', 'POST'])
@login_required
def idp_respond_request(request_id):
    req = IDPRequest.query.get(request_id)
    budget = 0
    for item in req.idp.idp_item:
        if item.budget:
            budget += item.budget
    if req.idp.staff.personal_info.academic_staff:
        over_budget = True if budget > 15000 else False
    else:
        over_budget = True if budget > 10000 else False
    if request.method == 'POST':
        form = request.form
        req.status = form.get('approval')
        if req.status == 'อนุมัติ':
            if req.for_ == 'ขอรับรอง':
                req.idp.approved_at = arrow.now('Asia/Bangkok').datetime
            elif req.for_ == 'ขอแก้ไข':
                req.idp.approved_at = None
        else:
            if req.for_ == 'ขอรับการประเมิน':
                req.idp.submitted_at = None

        req.responded_at = arrow.now('Asia/Bangkok').datetime
        req.supervisor_comment = form.get('supervisor_comment')
        db.session.add(req)
        db.session.commit()

        req_msg = '{} {}คำขอ{}ของท่านในระบบ IDP' \
                  '\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(
                    current_user.personal_info.fullname, req.status,req.for_)
        req_title = 'แจ้งผลคำขอ IDP'
        if not current_app.debug:
            send_mail([req.idp.staff.email + "@mahidol.ac.th"], req_title, req_msg)
        else:
            print(req_msg, req.idp.staff.email)
        if req.for_ == 'ขอรับการประเมิน' and req.status == 'อนุมัติ':
            flash('กรุณาให้ข้อเสนอแนะ', 'warning')
            return redirect(url_for('pa.idp_review', idp_id=req.idp_id))
        else:
            flash('ดำเนินการเรียบร้อยแล้ว', 'success')
    return render_template('PA/idp_request.html', req=req, over_budget=over_budget)


@pa.route('/idp/head/request/<int:idp_id>/review', methods=['GET', 'POST'])
@login_required
def idp_review(idp_id):
    idp = IDP.query.get(idp_id)
    req = idp.idp_request.order_by(desc(IDPRequest.id)).first()
    if req and req.for_ == 'ขอรับการประเมิน':
        if req.status == 'อนุมัติ':
            form = IDPForm(obj=idp)
        else:
            flash('คำขอรับการประเมิน ยังไม่ได้รับการอนุมัติ', 'danger')
            return redirect(url_for('pa.idp_all_requests'))
    else:
        flash('ไม่พบคำขอรับการประเมิน', 'danger')
        return redirect(url_for('pa.idp_all_requests'))
    if form.validate_on_submit():
        form.populate_obj(idp)
        idp.evaluated_at = arrow.now('Asia/Bangkok').datetime
        success = 0
        n = 0
        for item in idp.idp_item:
            if item.is_success:
                success += 1
            n += 1
        achievement_percentage = (success/n)*100
        idp.achievement_percentage = achievement_percentage
        db.session.add(idp)
        db.session.commit()

        req_msg = 'ผู้บังคับบัญชาขั้นต้นได้ประเมินผล IDP ของท่านเรียบร้อยแล้ว ' \
                  'กรุณากดรับทราบผลการประเมิน IDP ในระบบ {}' \
                  '\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(
                   url_for("pa.idp_details", idp_id=idp_id, _external=True))
        req_title = 'แจ้งการประเมิน IDP กรุณาดำเนินการ'
        if not current_app.debug:
            send_mail([idp.staff.email + "@mahidol.ac.th"], req_title, req_msg)
        else:
            print(req_msg, idp.staff.email)

        flash('ดำเนินการเรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.idp_all_requests'))
    return render_template('PA/idp_review_result.html', form=form, idp=idp)


@pa.route('/idp/request/<int:idp_id>/accept', methods=['GET', 'POST'])
@login_required
def idp_accept_result(idp_id):
    idp = IDP.query.get(idp_id)
    idp.accepted_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(idp)
    db.session.commit()
    flash('รับทราบผล IDP แล้ว', 'success')
    return redirect(url_for('pa.idp_details', idp_id=idp_id))


@pa.route('/hr/idp')
@login_required
@hr_permission.require()
def hr_idp_index():
    return render_template('staff/HR/PA/idp_index.html')


@pa.route('/hr/idp/all')
@login_required
@hr_permission.require()
def hr_all_idp():
    all_idp = IDP.query.all()
    return render_template('staff/HR/PA/idp_all.html', all_idp=all_idp)


@pa.route('/hr/idp/detail/<int:idp_id>')
@login_required
@hr_permission.require()
def hr_idp_detail(idp_id):
    idp = IDP.query.filter_by(id=idp_id).first()
    return render_template('staff/HR/PA/idp_detail_each_person.html', idp=idp)


@pa.route('/hr/idp/improvement')
@login_required
@hr_permission.require()
def hr_idp_improvement():
    all_idp_item = IDPItem.query.all()
    return render_template('staff/HR/PA/idp_improvement.html', all_idp_item=all_idp_item)