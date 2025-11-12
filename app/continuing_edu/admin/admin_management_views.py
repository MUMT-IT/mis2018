"""
Admin management views for continuing education.
Allows super admins to manage who has access to the continuing_edu admin area.
"""
from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required

from app.continuing_edu.admin import admin_bp
from app.continuing_edu.admin.decorators import admin_required
from app.main import db
from app.staff.models import Role, StaffAccount

#@admin_bp.route('/settings/member_types', methods=['GET', 'POST'])
@admin_bp.route('/settings/administrators', methods=['GET'])
@login_required
@admin_required
def settings_administrators():
    """List all staff who have continuing_edu_admin role."""
    from app.continuing_edu.admin.decorators import get_current_staff
    
    staff = get_current_staff()

    print(staff)
    
    # Get the continuing_edu_admin role
    role = Role.query.filter_by(
        role_need='continuing_edu_admin',
        action_need=None,
        resource_id=None
    ).first()

    #print(role)
    
    if not role:
        flash('Continuing education admin role not found. Please run setup script.', 'danger')
        return redirect(url_for('continuing_edu_admin.dashboard'))
    
    # Get all staff with this role
    admins = StaffAccount.query.join(StaffAccount.roles).filter(Role.id == role.id).all()
    
    # Get all active staff for adding new admins
    all_staff = StaffAccount.get_active_accounts()
    
    # Filter out staff who already have the role
    available_staff = [s for s in all_staff if role not in s.roles]
    
    return render_template(
        'continueing_edu/admin/settings_administrators.html',
        admins=admins,
        available_staff=available_staff,
        role=role,
        logged_in_admin=staff
    )


@admin_bp.route('/settings/administrators/add', methods=['POST'])
@login_required
@admin_required
def settings_administrators_add():
    """Add continuing_edu_admin role to a staff member."""
    staff_id = request.form.get('staff_id', type=int)
    
    if not staff_id:
        flash('Please select a staff member.', 'warning')
        return redirect(url_for('continuing_edu_admin.settings_administrators'))
    
    staff = StaffAccount.query.get_or_404(staff_id)
    role = Role.query.filter_by(
        role_need='continuing_edu_admin',
        action_need=None,
        resource_id=None
    ).first()
    
    if not role:
        flash('Role not found. Please run setup script.', 'danger')
        return redirect(url_for('continuing_edu_admin.settings_administrators'))
    
    if role in staff.roles:
        flash(f'{staff.fullname} already has admin access.', 'info')
    else:
        staff.roles.append(role)
        db.session.commit()
        flash(f'Added {staff.fullname} as continuing education administrator.', 'success')
    
    return redirect(url_for('continuing_edu_admin.settings_administrators'))


@admin_bp.route('/settings/administrators/<int:staff_id>/remove', methods=['POST'])
@login_required
@admin_required
def settings_administrators_remove(staff_id):
    """Remove continuing_edu_admin role from a staff member."""
    staff = StaffAccount.query.get_or_404(staff_id)
    role = Role.query.filter_by(
        role_need='continuing_edu_admin',
        action_need=None,
        resource_id=None
    ).first()
    
    if not role:
        flash('Role not found.', 'danger')
        return redirect(url_for('continuing_edu_admin.settings_administrators'))
    
    if role not in staff.roles:
        flash(f'{staff.fullname} does not have admin access.', 'info')
    else:
        staff.roles.remove(role)
        db.session.commit()
        flash(f'Removed admin access from {staff.fullname}.', 'warning')
    
    return redirect(url_for('continuing_edu_admin.settings_administrators'))
