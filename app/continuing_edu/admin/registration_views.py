"""
Registration Management Views for Continuing Education Admin
"""
from flask import render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required
from sqlalchemy import or_, and_, func, desc
from sqlalchemy.orm import joinedload
import csv
import io
from datetime import datetime, timezone

from app.continuing_edu.admin.views import admin_bp
from app.continuing_edu.admin.decorators import admin_required, get_current_staff, can_manage_registrations
from app.continuing_edu.models import (
    MemberRegistration,
    Member,
    EventEntity,
    RegistrationStatus,
    MemberType,
    EventRegistrationFee,
    db
)


@admin_bp.route('/registrations')
@login_required
@admin_required
def list_registrations():
    """List all registrations with filtering and search"""
    staff = get_current_staff()
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    
    # Filters
    status_filter = request.args.get('status', '')
    event_id = request.args.get('event_id', type=int)
    member_id = request.args.get('member_id', type=int)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search_query = request.args.get('q', '')
    
    # Base query with eager loading
    query = MemberRegistration.query.options(
        joinedload(MemberRegistration.member),
        joinedload(MemberRegistration.event_entity),
        joinedload(MemberRegistration.status_ref)
    )
    
    # Apply filters
    if status_filter:
        status = RegistrationStatus.query.filter(
            func.lower(RegistrationStatus.name_en) == status_filter.lower()
        ).first()
        if status:
            query = query.filter(MemberRegistration.status_id == status.id)
    
    if event_id:
        query = query.filter(MemberRegistration.event_entity_id == event_id)
    
    if member_id:
        query = query.filter(MemberRegistration.member_id == member_id)
    
    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            query = query.filter(MemberRegistration.registration_date >= date_from_dt)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            query = query.filter(MemberRegistration.registration_date <= date_to_dt)
        except ValueError:
            pass
    
    # Search in member name, email, or event title
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.join(Member).join(EventEntity).filter(
            or_(
                Member.full_name_th.ilike(search_pattern),
                Member.full_name_en.ilike(search_pattern),
                Member.email.ilike(search_pattern),
                Member.username.ilike(search_pattern),
                EventEntity.title_th.ilike(search_pattern),
                EventEntity.title_en.ilike(search_pattern)
            )
        )
    
    # Order by most recent first
    query = query.order_by(desc(MemberRegistration.registration_date))
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    registrations = pagination.items
    
    # Get all events for filter dropdown
    events = EventEntity.query.order_by(EventEntity.title_en).all()
    
    # Get all registration statuses
    statuses = RegistrationStatus.query.all()
    
    # Statistics
    stats = {
        'total': MemberRegistration.query.count(),
        'pending': MemberRegistration.query.join(RegistrationStatus).filter(
            func.lower(RegistrationStatus.name_en) == 'pending'
        ).count(),
        'confirmed': MemberRegistration.query.join(RegistrationStatus).filter(
            func.lower(RegistrationStatus.name_en) == 'confirmed'
        ).count(),
        'cancelled': MemberRegistration.query.join(RegistrationStatus).filter(
            func.lower(RegistrationStatus.name_en) == 'cancelled'
        ).count(),
    }
    
    return render_template(
        'continueing_edu/admin/registrations/list.html',
        registrations=registrations,
        pagination=pagination,
        events=events,
        statuses=statuses,
        stats=stats,
        filters={
            'status': status_filter,
            'event_id': event_id,
            'member_id': member_id,
            'date_from': date_from,
            'date_to': date_to,
            'search': search_query,
        }
    )


@admin_bp.route('/registrations/<int:registration_id>')
@login_required
@admin_required
def view_registration(registration_id):
    """View detailed information about a specific registration"""
    registration = MemberRegistration.query.options(
        joinedload(MemberRegistration.member).joinedload(Member.organization),
        joinedload(MemberRegistration.member).joinedload(Member.occupation),
        joinedload(MemberRegistration.member).joinedload(Member.addresses),
        joinedload(MemberRegistration.event_entity).joinedload(EventEntity.category),
        joinedload(MemberRegistration.event_entity).joinedload(EventEntity.speakers),
        joinedload(MemberRegistration.status_ref),
        joinedload(MemberRegistration.certificate_status_ref)
    ).get_or_404(registration_id)
    
    # Get registration fees for this event
    fees = EventRegistrationFee.query.filter_by(
        event_entity_id=registration.event_entity_id
    ).all()
    
    # Get payments related to this registration
    payments = registration.payments
    
    # Get all registration statuses for dropdown
    statuses = RegistrationStatus.query.all()
    
    return render_template(
        'continueing_edu/admin/registrations/detail.html',
        registration=registration,
        fees=fees,
        payments=payments,
        statuses=statuses
    )


@admin_bp.route('/registrations/<int:registration_id>/update_status', methods=['POST'])
@login_required
@admin_required
@can_manage_registrations
def update_registration_status(registration_id):
    """Update registration status"""
    registration = MemberRegistration.query.get_or_404(registration_id)
    
    new_status_id = request.form.get('status_id', type=int)
    notes = request.form.get('notes', '').strip()
    
    if not new_status_id:
        flash('Please select a status', 'danger')
        return redirect(url_for('continuing_edu_admin.view_registration', registration_id=registration_id))
    
    # Verify status exists
    new_status = RegistrationStatus.query.get(new_status_id)
    if not new_status:
        flash('Invalid status selected', 'danger')
        return redirect(url_for('continuing_edu_admin.view_registration', registration_id=registration_id))
    
    old_status_name = registration.status_ref.name_en if registration.status_ref else 'Unknown'
    
    # Update status
    registration.status_id = new_status_id
    
    # TODO: Add status change history/log if needed
    
    db.session.commit()
    
    flash(f'Registration status updated from {old_status_name} to {new_status.name_en}', 'success')
    
    # TODO: Send notification email to member about status change
    
    return redirect(url_for('continuing_edu_admin.view_registration', registration_id=registration_id))


@admin_bp.route('/registrations/<int:registration_id>/update_attendance', methods=['POST'])
@login_required
@admin_required
@can_manage_registrations
def update_attendance(registration_id):
    """Update attendance information"""
    registration = MemberRegistration.query.get_or_404(registration_id)
    
    attendance_count = request.form.get('attendance_count', type=int)
    total_hours = request.form.get('total_hours_attended', type=float)
    
    if attendance_count is not None:
        registration.attendance_count = max(0, attendance_count)
    
    if total_hours is not None:
        registration.total_hours_attended = max(0.0, total_hours)
    
    db.session.commit()
    
    flash('Attendance information updated successfully', 'success')
    return redirect(url_for('continuing_edu_admin.view_registration', registration_id=registration_id))


@admin_bp.route('/registrations/<int:registration_id>/update_scores', methods=['POST'])
@login_required
@admin_required
@can_manage_registrations
def update_test_scores(registration_id):
    """Update pre/post test scores"""
    registration = MemberRegistration.query.get_or_404(registration_id)
    
    pre_test_score = request.form.get('pre_test_score', type=float)
    post_test_score = request.form.get('post_test_score', type=float)
    assessment_passed = request.form.get('assessment_passed') == 'true'
    
    if pre_test_score is not None:
        registration.pre_test_score = max(0.0, min(100.0, pre_test_score))
    
    if post_test_score is not None:
        registration.post_test_score = max(0.0, min(100.0, post_test_score))
    
    registration.assessment_passed = assessment_passed
    
    db.session.commit()
    
    flash('Test scores updated successfully', 'success')
    return redirect(url_for('continuing_edu_admin.view_registration', registration_id=registration_id))


@admin_bp.route('/registrations/<int:registration_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_registration(registration_id):
    """Delete a registration (with confirmation)"""
    registration = MemberRegistration.query.get_or_404(registration_id)
    
    member_name = registration.member.full_name_en or registration.member.username
    event_title = registration.event_entity.title_en
    
    db.session.delete(registration)
    db.session.commit()
    
    flash(f'Registration for {member_name} in "{event_title}" has been deleted', 'success')
    return redirect(url_for('continuing_edu_admin.list_registrations'))


@admin_bp.route('/registrations/bulk')
@login_required
@admin_required
@can_manage_registrations
def bulk_actions():
    """Bulk actions page for registrations"""
    # Get events for dropdown
    events = EventEntity.query.order_by(EventEntity.title_en).all()
    statuses = RegistrationStatus.query.all()
    
    return render_template(
        'continueing_edu/admin/registrations/bulk.html',
        events=events,
        statuses=statuses
    )


@admin_bp.route('/registrations/bulk/update_status', methods=['POST'])
@login_required
@admin_required
@can_manage_registrations
def bulk_update_status():
    """Bulk update registration status"""
    registration_ids = request.form.getlist('registration_ids[]', type=int)
    new_status_id = request.form.get('status_id', type=int)
    
    if not registration_ids:
        flash('No registrations selected', 'warning')
        return redirect(url_for('continuing_edu_admin.bulk_actions'))
    
    if not new_status_id:
        flash('Please select a status', 'warning')
        return redirect(url_for('continuing_edu_admin.bulk_actions'))
    
    # Verify status exists
    new_status = RegistrationStatus.query.get(new_status_id)
    if not new_status:
        flash('Invalid status selected', 'danger')
        return redirect(url_for('continuing_edu_admin.bulk_actions'))
    
    # Update all selected registrations
    updated_count = MemberRegistration.query.filter(
        MemberRegistration.id.in_(registration_ids)
    ).update(
        {MemberRegistration.status_id: new_status_id},
        synchronize_session=False
    )
    
    db.session.commit()
    
    flash(f'Updated {updated_count} registrations to status: {new_status.name_en}', 'success')
    return redirect(url_for('continuing_edu_admin.bulk_actions'))


@admin_bp.route('/registrations/export')
@login_required
@admin_required
def export_registrations():
    """Export registrations to CSV"""
    # Get filters from request
    status_filter = request.args.get('status', '')
    event_id = request.args.get('event_id', type=int)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Build query (same as list_registrations but without pagination)
    query = MemberRegistration.query.options(
        joinedload(MemberRegistration.member),
        joinedload(MemberRegistration.event_entity),
        joinedload(MemberRegistration.status_ref)
    )
    
    if status_filter:
        status = RegistrationStatus.query.filter(
            func.lower(RegistrationStatus.name_en) == status_filter.lower()
        ).first()
        if status:
            query = query.filter(MemberRegistration.status_id == status.id)
    
    if event_id:
        query = query.filter(MemberRegistration.event_entity_id == event_id)
    
    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            query = query.filter(MemberRegistration.registration_date >= date_from_dt)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            query = query.filter(MemberRegistration.registration_date <= date_to_dt)
        except ValueError:
            pass
    
    registrations = query.order_by(desc(MemberRegistration.registration_date)).all()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Registration ID',
        'Member ID',
        'Member Name (EN)',
        'Member Name (TH)',
        'Email',
        'Phone',
        'Event ID',
        'Event Title (EN)',
        'Event Type',
        'Registration Date',
        'Status',
        'Attendance Count',
        'Hours Attended',
        'Pre-Test Score',
        'Post-Test Score',
        'Assessment Passed',
        'Certificate Status'
    ])
    
    # Write data
    for reg in registrations:
        writer.writerow([
            reg.id,
            reg.member_id,
            reg.member.full_name_en or '',
            reg.member.full_name_th or '',
            reg.member.email or '',
            reg.member.phone_no or '',
            reg.event_entity_id,
            reg.event_entity.title_en or '',
            reg.event_entity.event_type or '',
            reg.registration_date.strftime('%Y-%m-%d %H:%M:%S') if reg.registration_date else '',
            reg.status_ref.name_en if reg.status_ref else '',
            reg.attendance_count or 0,
            reg.total_hours_attended or 0.0,
            reg.pre_test_score or '',
            reg.post_test_score or '',
            'Yes' if reg.assessment_passed else 'No' if reg.assessment_passed is False else '',
            reg.certificate_status_ref.name_en if reg.certificate_status_ref else ''
        ])
    
    # Create response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=registrations_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        }
    )


@admin_bp.route('/events/<int:event_id>/registrations')
@login_required
@admin_required
def event_registrations(event_id):
    """List all registrations for a specific event"""
    event = EventEntity.query.get_or_404(event_id)
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Query registrations for this event
    query = MemberRegistration.query.filter_by(event_entity_id=event_id).options(
        joinedload(MemberRegistration.member),
        joinedload(MemberRegistration.status_ref)
    ).order_by(desc(MemberRegistration.registration_date))
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    registrations = pagination.items
    
    # Statistics for this event
    stats = {
        'total': query.count(),
        'pending': query.join(RegistrationStatus).filter(
            func.lower(RegistrationStatus.name_en) == 'pending'
        ).count(),
        'confirmed': query.join(RegistrationStatus).filter(
            func.lower(RegistrationStatus.name_en) == 'confirmed'
        ).count(),
        'cancelled': query.join(RegistrationStatus).filter(
            func.lower(RegistrationStatus.name_en) == 'cancelled'
        ).count(),
    }
    
    return render_template(
        'continueing_edu/admin/registrations/event_registrations.html',
        event=event,
        registrations=registrations,
        pagination=pagination,
        stats=stats
    )
