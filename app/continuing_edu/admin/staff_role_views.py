"""
Staff role management views for continuing education events.
Allows admins to assign event-specific roles to staff members.
"""
from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required
from sqlalchemy import and_

from app.continuing_edu.admin import admin_bp
from app.continuing_edu.admin.decorators import admin_required, get_current_staff, require_event_role
from app.continuing_edu.models import (
    Event, EventEditor, EventRegistrationReviewer, 
    EventPaymentApprover, EventReceiptIssuer, EventCertificateManager
)
from app.main import db
from app.staff.models import StaffAccount


@admin_bp.route('/settings/staff')
@login_required
@admin_required
def settings_staff_roles():
    """
    Main page for managing event-specific staff roles.
    Shows all events and staff assignments.
    """
    staff = get_current_staff()
    
    # Get all active events
    events = Event.query.order_by(Event.start_datetime.desc()).limit(50).all()
    
    # Get all active staff
    all_staff = StaffAccount.get_active_accounts()
    
    return render_template(
        'continueing_edu/admin/settings_staff_roles.html',
        events=events,
        all_staff=all_staff,
        logged_in_admin=staff
    )


@admin_bp.route('/events/<int:event_id>/staff-roles')
@login_required
@require_event_role('editor')  # Only event editors can manage roles
def event_staff_roles(event_id):
    """
    Manage staff role assignments for a specific event.
    """
    staff = get_current_staff()
    event = Event.query.get_or_404(event_id)
    
    # Get current role assignments
    editors = EventEditor.query.filter_by(event_id=event_id).all()
    registration_reviewers = EventRegistrationReviewer.query.filter_by(event_id=event_id).all()
    payment_approvers = EventPaymentApprover.query.filter_by(event_id=event_id).all()
    receipt_issuers = EventReceiptIssuer.query.filter_by(event_id=event_id).all()
    certificate_managers = EventCertificateManager.query.filter_by(event_id=event_id).all()
    
    # Get all active staff for assignment
    all_staff = StaffAccount.get_active_accounts()
    
    return render_template(
        'continueing_edu/admin/event_staff_roles.html',
        event=event,
        editors=editors,
        registration_reviewers=registration_reviewers,
        payment_approvers=payment_approvers,
        receipt_issuers=receipt_issuers,
        certificate_managers=certificate_managers,
        all_staff=all_staff,
        logged_in_admin=staff
    )


@admin_bp.route('/events/<int:event_id>/staff-roles/add', methods=['POST'])
@login_required
@require_event_role('editor')
def event_staff_roles_add(event_id):
    """
    Add a staff member to a specific role for an event.
    """
    event = Event.query.get_or_404(event_id)
    
    staff_id = request.form.get('staff_id', type=int)
    role_type = request.form.get('role_type')
    
    if not staff_id or not role_type:
        flash('กรุณาเลือกเจ้าหน้าที่และประเภทสิทธิ์', 'warning')
        return redirect(url_for('continuing_edu_admin.event_staff_roles', event_id=event_id))
    
    staff = StaffAccount.query.get_or_404(staff_id)
    
    # Check if already has this role
    role_model = {
        'editor': EventEditor,
        'registration_reviewer': EventRegistrationReviewer,
        'payment_approver': EventPaymentApprover,
        'receipt_issuer': EventReceiptIssuer,
        'certificate_manager': EventCertificateManager
    }.get(role_type)
    
    if not role_model:
        flash('ประเภทสิทธิ์ไม่ถูกต้อง', 'danger')
        return redirect(url_for('continuing_edu_admin.event_staff_roles', event_id=event_id))
    
    # Check if already assigned
    existing = role_model.query.filter_by(
        event_id=event_id,
        staff_id=staff_id
    ).first()
    
    if existing:
        flash(f'{staff.fullname} มีสิทธิ์นี้อยู่แล้ว', 'info')
    else:
        new_role = role_model(
            event_id=event_id,
            staff_id=staff_id
        )
        db.session.add(new_role)
        db.session.commit()
        
        role_names = {
            'editor': 'จัดการคอร์ส',
            'registration_reviewer': 'ตรวจสอบการลงทะเบียน',
            'payment_approver': 'อนุมัติการชำระเงิน',
            'receipt_issuer': 'ออกใบเสร็จ',
            'certificate_manager': 'จัดการใบประกาศนียบัตร'
        }
        
        flash(f'เพิ่ม {staff.fullname} เป็น {role_names.get(role_type)} สำหรับ {event.title_th}', 'success')
    
    return redirect(url_for('continuing_edu_admin.event_staff_roles', event_id=event_id))


@admin_bp.route('/events/<int:event_id>/staff-roles/<int:assignment_id>/remove', methods=['POST'])
@login_required
@require_event_role('editor')
def event_staff_roles_remove(event_id, assignment_id):
    """
    Remove a staff member's role assignment for an event.
    """
    event = Event.query.get_or_404(event_id)
    
    role_type = request.form.get('role_type')
    
    role_model = {
        'editor': EventEditor,
        'registration_reviewer': EventRegistrationReviewer,
        'payment_approver': EventPaymentApprover,
        'receipt_issuer': EventReceiptIssuer,
        'certificate_manager': EventCertificateManager
    }.get(role_type)
    
    if not role_model:
        flash('ประเภทสิทธิ์ไม่ถูกต้อง', 'danger')
        return redirect(url_for('continuing_edu_admin.event_staff_roles', event_id=event_id))
    
    assignment = role_model.query.get_or_404(assignment_id)
    
    # Prevent removing last editor
    if role_type == 'editor':
        editor_count = EventEditor.query.filter_by(event_id=event_id).count()
        if editor_count <= 1:
            flash('ไม่สามารถลบผู้จัดการคนสุดท้ายได้', 'danger')
            return redirect(url_for('continuing_edu_admin.event_staff_roles', event_id=event_id))
    
    staff_name = assignment.staff.fullname
    db.session.delete(assignment)
    db.session.commit()
    
    flash(f'ลบสิทธิ์ของ {staff_name} แล้ว', 'warning')
    
    return redirect(url_for('continuing_edu_admin.event_staff_roles', event_id=event_id))
