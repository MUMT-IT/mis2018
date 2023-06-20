# -*- coding:utf-8 -*-
import datetime
import pytz
import arrow
from sqlalchemy import and_
from . import pa_blueprint as pa

from app.roles import hr_permission, manager_permission
from app.PA.forms import *

tz = pytz.timezone('Asia/Bangkok')

from flask import render_template, flash, redirect, url_for, make_response, request
from flask_login import login_required, current_user


@pa.route('/user-performance')
@login_required
def user_performance():
    staff_personal = PAAgreement.query.all()
    rounds = PARound.query.all()
    return render_template('pa/user_performance.html', staff_personal=staff_personal,
                           name=current_user, rounds=rounds)


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
            items.append((item.id, item.goal))
            if pa_item:
                if item in pa_item.kpi_items:
                    default = item.id
        field_ = form.kpi_items_.append_entry(default)
        field_.choices = [('', 'ไม่ระบุเป้าหมาย')] + items
        field_.label = kpi.detail

    if form.validate_on_submit():
        for i in range(len(pa.kpis)):
            form.kpi_items_.pop_entry()

        if not pa_item:
            pa_item = PAItem()
        form.populate_obj(pa_item)
        new_kpi_items = []
        for e in form.kpi_items_.entries:
            if e.data:
                kpi_item = PAKPIItem.query.get(int(e.data))
                if kpi_item:
                    new_kpi_items.append(kpi_item)
        pa_item.kpi_items = new_kpi_items
        pa.pa_items.append(pa_item)
        db.session.add(pa_item)
        db.session.commit()
        flash('เพิ่มรายละเอียดภาระงานเรียบร้อย', 'success')
        return redirect(url_for('pa.add_pa_item', round_id=round_id))
    else:
        for er in form.errors:
            flash("{}:{}".format(er, form.errors[er]), 'danger')
    return render_template('pa/pa_item_edit.html',
                           form=form,
                           pa_round=pa_round,
                           pa=pa,
                           pa_item_id=item_id,
                           categories=categories)


@pa.route('/staff/items/add', methods=['POST', 'GET'])
def add_tasks():
    form = PAItemForm()
    form.items.append_entry()
    task_form = form.items[-1]
    form_text = '<table class="table is-bordered is-fullwidth is-narrow">'
    form_text += '''
    <div id={}>
        <div class="field">
            <label class="label">{}</label>
            <div class="control">
                {}
            </div>
        </div>
        <div class="field">
            <label class="label">{}</label>
                {}
        </div>
        <div class="field">
            <label class="label">{}</label>
            <div class="control">
                {}
            </div>
        </div>
    </div>
    '''.format(task_form.task,
               task_form.percentage.label,
               task_form.percentage(class_="input", placeholder="%"),
               task_form.type.label, task_form.type(),
               task_form.detail.label, task_form.detail(class_="textarea")
               )
    resp = make_response(form_text)
    resp.headers['HX-Trigger-After-Swap'] = 'initSelect2Input'
    return resp


# @pa.route('/tasks/<int:item_id>')
# @login_required
# def delete_task(item_id):
#     task = PAItem.query.get(item_id)
#     staff_id = task.task.id
#     if task:
#         db.session.delete(task)
#         db.session.commit()
#         flash(u'ลบรายการเรียบร้อยแล้ว', 'success')
#     else:
#         flash(u'ไม่พบรายการ', 'warning')
#     return redirect(url_for('pa.show_task_detail', staff_id=staff_id))


@pa.route('/pa/<int:pa_id>/kpis/add', methods=['GET', 'POST'])
@login_required
def add_kpi(pa_id):
    round_id = request.args.get('round_id', type=int)
    form = PAKPIForm()
    if form.validate_on_submit():
        new_kpi = PAKPI()
        form.populate_obj(new_kpi)
        new_kpi.pa_id = pa_id
        db.session.add(new_kpi)
        db.session.commit()
        flash('เพิ่มรายละเอียดเกณฑ์การประเมินเรียบร้อย', 'success')
        return redirect(url_for('pa.add_kpi'), pa_id=pa_id)
    else:
        for er in form.errors:
            flash("{}:{}".format(er, form.errors[er]), 'danger')
    return render_template('pa/add_kpi.html', form=form, round_id=round_id, pa_id=pa_id)


@pa.route('/staff/rounds/<int:round_id>/task/view')
@login_required
def view_pa_item(round_id):
    round = PARound.query.get(round_id)
    agreement = PAAgreement.query.all()
    return render_template('pa/view_task.html', round=round, agreement=agreement)


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
    # TODO: org filter
    org_id = request.args.get('deptid')
    departments = Org.query.all()
    if org_id is None:
        committee_list = PACommittee.query.all()
    else:
        committee_list = PACommittee.query.filter(PACommittee.has(org_id=org_id))
    return render_template('pa/hr_show_committee.html',
                           sel_dept=org_id, committee_list=committee_list,
                           departments=[{'id': d.id, 'name': d.name} for d in departments])


@pa.route('/pa/<int:pa_id>/requests', methods=['GET', 'POST'])
def create_request(pa_id):
    pa = PAAgreement.query.get(pa_id)
    form = PARequestForm()
    supervisor_email = current_user.personal_info.org.head or current_user.personal_info.org.parent.head
    supervisor = StaffAccount.query.filter_by(email=supervisor_email).first()
    if form.validate_on_submit():
        new_request = PARequest()
        form.populate_obj(new_request)
        new_request.pa_id = pa_id
        right_now = arrow.now('Asia/Bangkok').datetime
        new_request.created_at = right_now
        new_request.submitted_at = right_now
        new_request.supervisor = supervisor
        db.session.add(new_request)
        db.session.commit()
        flash('ส่งคำขอเรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.add_pa_item', round_id=pa.round_id))
    return render_template('PA/request_form.html', form=form, pa=pa)


@pa.route('/head/requests')
@login_required
def all_request():
    all_req = PARequest.query.filter_by(supervisor_id=current_user.id).filter(PARequest.submitted_at != None).all()
    # all_req = PARequest.query.filter_by(supervisor_id=current_user.id).all()
    return render_template('pa/head_all_request.html', all_req=all_req)


@pa.route('/head/request/<int:request_id>/detail')
@login_required
def view_request(request_id):
    categories = PAItemCategory.query.all()
    req = PARequest.query.get(request_id)
    return render_template('PA/head_respond_request.html',
                           categories=categories, req=req)


@pa.route('/head/request/<int:request_id>', methods=['GET', 'POST'])
@login_required
def respond_request(request_id):
    req = PARequest.query.get(request_id)
    if request.method == 'POST':
        form = request.form
        req.status = form.get('approval')
        if req.for_ == 'ขอรับรอง':
            req.pa.approved_at = arrow.now('Asia/Bangkok').datetime
        elif req.for_ == 'ขอแก้ไข':
            req.pa.approved_at = None
        req.responded_at = arrow.now('Asia/Bangkok').datetime
        req.supervisor_comment = form.get('supervisor_comment')
        db.session.add(req)
        db.session.commit()
        flash('ดำเนินการอนุมัติเรียบร้อยแล้ว', 'success')
    return redirect(url_for('pa.all_request'))


@pa.route('/cmte/all_pa_agreement', methods=['GET', 'POST'])
@login_required
def all_pa_agreement():
    # pa = PAAgreement.query.filter(and_(PARequest.submitted_at !='',PARequest.for_=='ขอรับการประเมิน')).all()
    pa = PAAgreement.query.all()
    return render_template('pa/cmte_all_pa_agreement.html', pa=pa)


@pa.route('/cmte/head/all_performance/<int:scoresheet_id>', methods=['GET', 'POST'])
@login_required
def all_performance(scoresheet_id):
    scoresheet = PAScoreSheet.query.filter_by(id=scoresheet_id).first()
    return render_template('pa/cmte_all_performance.html', scoresheet=scoresheet)


@pa.route('/cmte/head/all_performance/<int:pa_id>/item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def rate_performance(pa_id, item_id):
    pa_item = PAItem.query.filter_by(id=item_id).first()
    ScoreItemForm = create_rate_performance_form(pa_id)
    # TODO: check case duplicate attend
    form = ScoreItemForm()
    if form.validate_on_submit():
        score_item = PAScoreSheetItem()
        form.populate_obj(score_item)
    return render_template('pa/cmte_rate_performance.html', form=form, pa_item=pa_item, pa_id=pa_id)


@pa.route('/cmte/all-scoresheet', methods=['GET', 'POST'])
@login_required
def all_scoresheet():
    # evaluator = PAScoreSheet.query.filter(PACommittee.org_id).all()
    pa = PAAgreement.query.filter(and_(PARequest.submitted_at != '',
                                       PARequest.for_ == 'ขอรับการประเมิน')).all()
    return render_template('pa/cmte_all_scoresheet.html', pa=pa)


@pa.route('/head/create-scoresheet/<int:pa_id>', methods=['GET', 'POST'])
@login_required
def create_scoresheet(pa_id):
    # scoresheet = PAScoreSheet.query.filter_by(pa_id=pa_id, committee_id=current_user.id).first()
    scoresheet = PAScoreSheet.query.all()
    return render_template('pa/cmte_all_performance.html', scoresheet=scoresheet)
    # if not scoresheet:
    #     create_scoresheet = PAScoreSheet(
    #         pa_id=pa_id,
    #         committee_id=current_user.id
    #     )
    #     db.session.add(create_scoresheet)
    #     db.session.commit()
    #
    #     pa_kpi = PAKPI.query.filter_by(pa_id=pa_id).all()
    #     for kpi in pa_kpi:
    #         pa_item = PAItem.query.filter_by(pa_id=pa_id).all()
    #         for item in pa_item:
    #             create_scoresheet_item = PAScoreSheetItem(
    #                 score_sheet_id=create_scoresheet.id,
    #                 item_id=item.id,
    #                 kpi_id=kpi.id
    #             )
    #             db.session.add(create_scoresheet_item)
    #             db.session.commit()
    #     return render_template('pa/all_performance.html', pa_id=pa_id)
    # else:
    #     return render_template('pa/all_performance.html', scoresheet_id=scoresheet.id)
