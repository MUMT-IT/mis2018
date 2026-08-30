from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.main import db
from . import dynamic_forms_bp as dynamic_forms
from .forms import DynamicFormCreateForm, DynamicFormFieldForm, create_assignment_form
from .models import DynamicForm, DynamicFormVersion, DynamicFormField, DynamicFormOption, DynamicFormAssignment


@dynamic_forms.route('/')
@login_required
def index():
    forms = DynamicForm.query.order_by(DynamicForm.name.asc()).all()
    return render_template('dynamic_forms/index.html', forms=forms)


@dynamic_forms.route('/new', methods=['GET', 'POST'])
@login_required
def create():
    form = DynamicFormCreateForm()
    if form.validate_on_submit():
        dynamic_form = DynamicForm(name=form.name.data, description=form.description.data,
                                   status=form.status.data,
                                   created_by=current_user)
        version = DynamicFormVersion(version=1, status=form.status.data, created_by=current_user)
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
    if form.validate_on_submit():
        form.populate_obj(dynamic_form)
        if dynamic_form.versions:
            latest_version = dynamic_form.versions[-1]
            latest_version.status = dynamic_form.status
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
    if form.validate_on_submit():
        field = DynamicFormField(version=version, key=form.key.data, label=form.label.data,
                                 field_type=form.field_type.data, required=form.required.data,
                                 display_order=form.display_order.data, help_text=form.help_text.data)
        for index, line in enumerate((form.options.data or '').splitlines(), 1):
            value, _, label = line.partition('|')
            if value.strip():
                field.options.append(DynamicFormOption(value=value.strip(), label=(label.strip() or value.strip()), display_order=index))
        db.session.add(field)
        db.session.commit()
        flash('Field added.', 'success')
        return redirect(url_for('dynamic_forms.edit_version', version_id=version.id))
    return render_template('dynamic_forms/form_edit.html', form=form,
                           dynamic_form=version.form, version=version)


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
    db.session.delete(assignment)
    db.session.commit()
    flash('Evaluation form detached.', 'success')
    return redirect(request.referrer or url_for('dynamic_forms.index'))
