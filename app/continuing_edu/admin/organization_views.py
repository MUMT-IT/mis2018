from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required

from app.continuing_edu.admin import admin_bp
from app.continuing_edu.admin.decorators import admin_required, get_current_staff
from app.main import db
from app.continuing_edu.models import Organization, OrganizationType


@admin_bp.route('/organizations')
@login_required
@admin_required
def organizations_list():
    staff = get_current_staff()
    org_types = OrganizationType.query.order_by(OrganizationType.name_en.asc()).all()
    orgs = Organization.query.order_by(Organization.name.asc()).all()
    return render_template('continueing_edu/admin/organizations.html', org_types=org_types, orgs=orgs, logged_in_admin=staff)


@admin_bp.route('/organizations/create', methods=['GET', 'POST'])
@login_required
@admin_required
def organizations_create():
    staff = get_current_staff()
    if request.method == 'POST':
        name = request.form.get('name')
        org_type_id = request.form.get('organization_type_id')
        if not name:
            flash('Organization name required', 'warning')
            return redirect(url_for('continuing_edu_admin.organizations_create'))
        if org_type_id:
            try:
                org_type_id = int(org_type_id)
            except Exception:
                org_type_id = None
        org = Organization(name=name.strip(), organization_type_id=org_type_id, is_user_defined=True)
        db.session.add(org)
        db.session.commit()
        flash('Organization created', 'success')
        return redirect(url_for('continuing_edu_admin.organizations_list'))

    org_types = OrganizationType.query.order_by(OrganizationType.name_en.asc()).all()
    return render_template('continueing_edu/admin/organization_form.html', org_types=org_types, org=None, logged_in_admin=staff)


@admin_bp.route('/organizations/<int:org_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def organizations_edit(org_id):
    staff = get_current_staff()
    org = Organization.query.get_or_404(org_id)
    if request.method == 'POST':
        name = request.form.get('name')
        org_type_id = request.form.get('organization_type_id')
        org.name = name.strip() if name else org.name
        try:
            org.organization_type_id = int(org_type_id) if org_type_id else None
        except Exception:
            org.organization_type_id = None
        db.session.commit()
        flash('Organization updated', 'success')
        return redirect(url_for('continuing_edu_admin.organizations_list'))

    org_types = OrganizationType.query.order_by(OrganizationType.name_en.asc()).all()
    return render_template('continueing_edu/admin/organization_form.html', org_types=org_types, org=org, logged_in_admin=staff)


@admin_bp.route('/organizations/<int:org_id>/delete', methods=['POST'])
@login_required
@admin_required
def organizations_delete(org_id):
    org = Organization.query.get_or_404(org_id)
    db.session.delete(org)
    db.session.commit()
    flash('Organization deleted', 'warning')
    return redirect(url_for('continuing_edu_admin.organizations_list'))
