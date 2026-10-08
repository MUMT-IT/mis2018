from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.main import db
from . import dynamic_forms_bp as dynamic_forms
from .forms import (DynamicFormCreateForm, DynamicFormDeleteForm, DynamicFormFieldForm,
                    DynamicFormPassingScoreForm, create_assignment_form)
from .models import DynamicForm, DynamicFormVersion, DynamicFormField, DynamicFormOption, DynamicFormAssignment


def _populate_dynamic_field(field, form):
    field.key = form.key.data
    field.label = form.label.data
    field.field_type = form.field_type.data
    field.required = form.required.data
    field.display_order = form.display_order.data
    field.help_text = form.help_text.data
    field.config = {
        'scorable': form.scorable.data,
        'max_score': float(form.max_score.data) if form.max_score.data is not None else None,
        'weight': float(form.weight.data) if form.weight.data is not None else None,
    }
    field.options.clear()
    for index, line in enumerate((form.options.data or '').splitlines(), 1):
        value, _, label = line.partition('|')
        if value.strip():
            field.options.append(DynamicFormOption(
                value=value.strip(), label=(label.strip() or value.strip()),
                display_order=index))


@dynamic_forms.route('/')
@login_required
def index():
    forms = DynamicForm.query.order_by(DynamicForm.name.asc()).all()
    return render_template('dynamic_forms/index.html', forms=forms,
                           delete_form=DynamicFormDeleteForm())


@dynamic_forms.route('/<int:form_id>/delete', methods=['POST'])
@login_required
def delete(form_id):
    form = DynamicFormDeleteForm()
    if not form.validate_on_submit():
        flash('Invalid removal request. Please try again.', 'danger')
        return redirect(url_for('dynamic_forms.index'))
    dynamic_form = DynamicForm.query.get_or_404(form_id)
    assignment_count = sum(len(version.assignments) for version in dynamic_form.versions)
    submission_count = sum(len(version.submissions) for version in dynamic_form.versions)
    if assignment_count or submission_count:
        flash('ไม่สามารถลบแบบฟอร์มนี้ได้: มีการผูกใช้งาน {} รายการ และคำตอบ {} รายการ กรุณาเปลี่ยนสถานะเป็น Archived'.format(
            assignment_count, submission_count), 'warning')
        return redirect(url_for('dynamic_forms.index'))
    db.session.delete(dynamic_form)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('ไม่สามารถลบแบบฟอร์มที่มีข้อมูลอ้างอิงอยู่ได้', 'warning')
    else:
        flash('Form removed.', 'success')
    return redirect(url_for('dynamic_forms.index'))


@dynamic_forms.route('/new', methods=['GET', 'POST'])
@login_required
def create():
    form = DynamicFormCreateForm()
    if form.validate_on_submit():
        dynamic_form = DynamicForm(name=form.name.data, description=form.description.data,
                                   status=form.status.data,
                                   created_by=current_user)
        version = DynamicFormVersion(
            version=1, status=form.status.data, created_by=current_user,
            passing_percentage=form.passing_percentage.data)
        dynamic_form.versions.append(version)
        db.session.add(dynamic_form)
        db.session.commit()
        return redirect(url_for('dynamic_forms.edit_version', version_id=version.id))
    return render_template('dynamic_forms/form_edit.html', form=form, dynamic_form=None, version=None)


@dynamic_forms.route('/<int:form_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(form_id):
    dynamic_form = DynamicForm.query.get_or_404(form_id)
    form = DynamicFormCreateForm(obj=dynamic_form)
    latest_version = dynamic_form.versions[-1] if dynamic_form.versions else None
    if request.method == 'GET' and latest_version:
        form.passing_percentage.data = latest_version.passing_percentage
    if form.validate_on_submit():
        dynamic_form.name = form.name.data
        dynamic_form.description = form.description.data
        dynamic_form.status = form.status.data
        if latest_version:
            latest_version.status = dynamic_form.status
            latest_version.passing_percentage = form.passing_percentage.data
            if dynamic_form.status == 'Published' and latest_version.published_at is None:
                latest_version.published_at = db.func.now()
        db.session.commit()
        flash('Form updated.', 'success')
        return redirect(url_for('dynamic_forms.index'))
    return render_template('dynamic_forms/form_edit.html', form=form,
                           dynamic_form=dynamic_form, version=None)


@dynamic_forms.route('/versions/<int:version_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_version(version_id):
    version = DynamicFormVersion.query.get_or_404(version_id)
    form = DynamicFormFieldForm()
    passing_form = DynamicFormPassingScoreForm(obj=version)
    if form.validate_on_submit():
        field = DynamicFormField(version=version)
        _populate_dynamic_field(field, form)
        db.session.add(field)
        db.session.commit()
        flash('Field added.', 'success')
        return redirect(url_for('dynamic_forms.edit_version', version_id=version.id))
    return render_template('dynamic_forms/form_edit.html', form=form,
                           dynamic_form=version.form, version=version,
                           passing_form=passing_form)


@dynamic_forms.route('/versions/<int:version_id>/passing-score', methods=['POST'])
@login_required
def update_passing_score(version_id):
    version = DynamicFormVersion.query.get_or_404(version_id)
    form = DynamicFormPassingScoreForm()
    if form.validate_on_submit():
        version.passing_percentage = form.passing_percentage.data
        db.session.commit()
        flash('Passing percentage updated.', 'success')
    else:
        for errors in form.errors.values():
            for error in errors:
                flash(error, 'danger')
    return redirect(url_for('dynamic_forms.edit_version', version_id=version.id))


@dynamic_forms.route('/fields/<int:field_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_field(field_id):
    field = DynamicFormField.query.get_or_404(field_id)
    form = DynamicFormFieldForm(obj=field)
    if request.method == 'GET':
        config = field.config or {}
        form.scorable.data = bool(config.get('scorable'))
        form.max_score.data = config.get('max_score')
        form.weight.data = config.get('weight')
        form.options.data = '\n'.join(
            '{}|{}'.format(option.value, option.label)
            for option in field.options)
    if form.validate_on_submit():
        _populate_dynamic_field(field, form)
        db.session.commit()
        flash('Field updated.', 'success')
        return redirect(url_for('dynamic_forms.edit_version',
                                version_id=field.version_id))
    return render_template('dynamic_forms/form_edit.html', form=form,
                           dynamic_form=field.version.form,
                           version=field.version, editing_field=field,
                           passing_form=DynamicFormPassingScoreForm(
                               obj=field.version))


@dynamic_forms.route('/assign/<subject_type>/<int:subject_id>', methods=['POST'])
@login_required
def assign(subject_type, subject_id):
    form = create_assignment_form()()
    if form.validate_on_submit():
        assignment = DynamicFormAssignment(version=form.version.data,
                                           subject_type=subject_type,
                                           subject_id=subject_id,
                                           assigned_by=current_user)
        db.session.add(assignment)
        db.session.commit()
        flash('Evaluation form assigned.', 'success')
    return redirect(request.referrer or url_for('dynamic_forms.index'))


@dynamic_forms.route('/assignments/<int:assignment_id>/delete', methods=['POST'])
@login_required
def unassign(assignment_id):
    assignment = DynamicFormAssignment.query.get_or_404(assignment_id)
    from app.eduqa.models import EduQAEvaluationBundleItem
    if EduQAEvaluationBundleItem.query.filter_by(assignment_id=assignment.id).first():
        flash('แบบประเมินนี้ใช้ในชุดแบบประเมิน จึงยังไม่สามารถถอดออกได้', 'warning')
        return redirect(request.referrer or url_for('dynamic_forms.index'))
    db.session.delete(assignment)
    db.session.commit()
    flash('Evaluation form detached.', 'success')
    return redirect(request.referrer or url_for('dynamic_forms.index'))
