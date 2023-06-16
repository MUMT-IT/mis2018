
from . import pa_blueprint as pa
from flask import render_template, flash, redirect, url_for, make_response, request
from flask_login import login_required, current_user

from .forms import *
from .models import PAAgreement, PAItem


@pa.route('/user-performance')
@login_required
def user_performance():
    staff_personal = PAAgreement.query.all()
    rounds = PARound.query.all()
    return render_template('pa/user_performance.html', staff_personal=staff_personal,
                           name=current_user, rounds=rounds)


@pa.route('/staff/rounds/<int:round_id>/tasks/add', methods=['GET', 'POST'])
@login_required
def add_task_detail(round_id):
    round = PARound.query.get(round_id)
    form = PAItemForm()
    if form.validate_on_submit():
        new_task = PAItem()
        form.populate_obj(new_task)
        new_task.staff_id = current_user.id
        db.session.add(new_task)
        db.session.commit()
        flash('เพิ่มรายละเอียดภาระงานเรียบร้อย', 'success')
    else:
        for er in form.errors:
            flash("{}:{}".format(er, form.errors[er]), 'danger')
    return render_template('pa/task_detail_edit.html', form=form, round=round)


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


@pa.route('/staff/rounds/<int:round_id>/kpi-item/add', methods=['GET', 'POST'])
@login_required
def add_kpi_item_detail(round_id):
    round = PARound.query.get(round_id)
    form = PAKPIItemForm()
    if form.validate_on_submit():
        new_kpi_item = PAKPIItem()
        form.populate_obj(new_kpi_item)
        # new_kpi_item.kpi_id = kpi_id
        db.session.add(new_kpi_item)
        db.session.commit()
        flash('เพิ่มรายละเอียดเกณฑ์การประเมินเรียบร้อย', 'success')
    else:
        for er in form.errors:
            flash("{}:{}".format(er, form.errors[er]), 'danger')
    return render_template('pa/kpi_item_detail.html', form=form, round=round)


@pa.route('/staff/rounds/<int:round_id>/task/view')
@login_required
def view_task_detail(round_id):
    round = PARound.query.get(round_id)
    agreement = PAAgreement.query.all()
    return render_template('pa/view_task.html', round=round, agreement=agreement)

