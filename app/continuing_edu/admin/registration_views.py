"""
Registration Management Views for Continuing Education Admin
"""
from flask import render_template, request, redirect, url_for, flash, jsonify, Response, current_app
from flask_login import login_required
from sqlalchemy import or_, func, desc
from sqlalchemy.orm import joinedload
import csv
import io
import json
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired, BadData

from app.continuing_edu.admin.views import admin_bp
from app.continuing_edu.admin.decorators import (
    admin_required,
    get_current_staff,
    can_manage_registrations,
    check_can_manage_registrations,
)
from app.continuing_edu.models import (
    CEMemberRegistration,
    CEMember,
    CEEventEntity,
    CERegisterPayment,
    CERegistrationStatus,
    CEMemberType,
    CEEventRegistrationFee,
    db
)

CHECKIN_QR_PREFIX = "CECHECKIN:"
CHECKIN_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 365 * 3


def _checkin_serializer():
    return URLSafeTimedSerializer(
        secret_key=current_app.config.get('SECRET_KEY'),
        salt='continuing-edu-checkin',
    )


def build_attendance_qr_payload(registration):
    token = _checkin_serializer().dumps(
        {
            'registration_id': registration.id,
            'event_id': registration.event_entity_id,
        }
    )
    return f"{CHECKIN_QR_PREFIX}{token}"


def _resolve_registration_from_payload(raw_value):
    raw = (raw_value or '').strip()
    if not raw:
        return None, None, 'empty_payload'

    if raw.isdigit():
        return int(raw), None, None

    # Supported format: CECHECKIN:<signed-token>
    if raw.startswith(CHECKIN_QR_PREFIX):
        token = raw[len(CHECKIN_QR_PREFIX):].strip()
        if not token:
            return None, None, 'invalid_token'
        try:
            payload = _checkin_serializer().loads(token, max_age=CHECKIN_TOKEN_MAX_AGE_SECONDS)
        except (BadSignature, SignatureExpired, BadData):
            return None, None, 'invalid_token'

        registration_id = payload.get('registration_id')
        event_id = payload.get('event_id')
        if not isinstance(registration_id, int):
            return None, None, 'invalid_token'
        return registration_id, event_id, None

    # Support URL payloads: ...?registration_id=123 or .../registrations/123
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        qs = parse_qs(parsed.query)
        for key in ('registration_id', 'reg_id', 'id'):
            values = qs.get(key) or []
            if values and str(values[0]).isdigit():
                return int(values[0]), None, None
        path_match = re.search(r"/registrations/(\d+)", parsed.path or '')
        if path_match:
            return int(path_match.group(1)), None, None

    # Support JSON payload: {"registration_id": 123, "event_id": 8}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        payload = None
    if isinstance(payload, dict):
        reg_val = payload.get('registration_id')
        event_val = payload.get('event_id')
        if isinstance(reg_val, int):
            return reg_val, event_val if isinstance(event_val, int) else None, None

    # Fallback: CE-REG-123 or text ending with digits.
    generic_match = re.search(r"(\d+)$", raw)
    if generic_match:
        return int(generic_match.group(1)), None, None

    return None, None, 'unsupported_payload'


def _wants_json_response():
    if request.args.get('format') == 'json':
        return True
    if request.form.get('response_format') == 'json':
        return True
    if request.is_json:
        return True
    accept = request.headers.get('Accept', '')
    return 'application/json' in accept


def _attendance_error(message, event_id=None, status_code=400, details=None):
    details = details or {}
    if _wants_json_response():
        payload = {'success': False, 'message': message}
        payload.update(details)
        return jsonify(payload), status_code

    flash(message, 'danger')
    next_url = request.form.get('next') or request.referrer
    if next_url:
        return redirect(next_url)
    return redirect(url_for('continuing_edu_admin.attendance_management', event_id=event_id))


@admin_bp.route('/attendance')
@login_required
@admin_required
@can_manage_registrations
def attendance_management():
    """Track and manage attendance for registrations."""
    staff = get_current_staff()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    event_id = request.args.get('event_id', type=int)
    checked_in = (request.args.get('checked_in') or '').strip().lower()
    search_query = (request.args.get('q') or '').strip()

    filtered_query = CEMemberRegistration.query
    if event_id:
        filtered_query = filtered_query.filter(CEMemberRegistration.event_entity_id == event_id)

    if search_query:
        search_pattern = f'%{search_query}%'
        if search_query.isdigit():
            filtered_query = filtered_query.filter(
                or_(
                    CEMemberRegistration.id == int(search_query),
                    CEMemberRegistration.member_id == int(search_query),
                    CEMemberRegistration.event_entity_id == int(search_query),
                )
            )
        else:
            filtered_query = (
                filtered_query
                .join(CEMember)
                .join(CEEventEntity)
                .filter(
                    or_(
                        CEMember.full_name_th.ilike(search_pattern),
                        CEMember.full_name_en.ilike(search_pattern),
                        CEMember.username.ilike(search_pattern),
                        CEMember.email.ilike(search_pattern),
                        CEEventEntity.title_th.ilike(search_pattern),
                        CEEventEntity.title_en.ilike(search_pattern),
                    )
                )
            )

    stats_query = filtered_query
    checked_in_condition = or_(
        CEMemberRegistration.started_at.isnot(None),
        CEMemberRegistration.attendance_count > 0,
    )

    if checked_in == 'yes':
        filtered_query = filtered_query.filter(checked_in_condition)
    elif checked_in == 'no':
        filtered_query = filtered_query.filter(~checked_in_condition)

    query = filtered_query.options(
        joinedload(CEMemberRegistration.member),
        joinedload(CEMemberRegistration.event_entity),
        joinedload(CEMemberRegistration.status_ref),
    ).order_by(
        CEMemberRegistration.event_entity_id.desc(),
        CEMemberRegistration.registration_date.desc(),
    )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    registrations = pagination.items

    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    stats = {
        'total': stats_query.count(),
        'checked_in': stats_query.filter(checked_in_condition).count(),
        'not_checked_in': stats_query.filter(~checked_in_condition).count(),
        'today_checkins': stats_query.filter(CEMemberRegistration.started_at >= start_of_day).count(),
    }

    events = (
        CEEventEntity.query
        .join(CEMemberRegistration, CEMemberRegistration.event_entity_id == CEEventEntity.id)
        .distinct()
        .order_by(CEEventEntity.created_at.desc())
        .all()
    )

    checkin_payloads = {reg.id: build_attendance_qr_payload(reg) for reg in registrations}

    return render_template(
        'continueing_edu/admin/attendance.html',
        logged_in_admin=staff,
        registrations=registrations,
        pagination=pagination,
        events=events,
        stats=stats,
        checkin_payloads=checkin_payloads,
        filters={
            'event_id': event_id,
            'checked_in': checked_in,
            'q': search_query,
            'per_page': per_page,
        },
    )


@admin_bp.route('/attendance/qrcode')
@login_required
@admin_required
@can_manage_registrations
def attendance_qrcode():
    """QR code check-in console for event attendance."""
    staff = get_current_staff()
    event_id = request.args.get('event_id', type=int)

    recent_query = (
        CEMemberRegistration.query
        .options(
            joinedload(CEMemberRegistration.member),
            joinedload(CEMemberRegistration.event_entity),
            joinedload(CEMemberRegistration.status_ref),
        )
        .filter(
            or_(
                CEMemberRegistration.started_at.isnot(None),
                CEMemberRegistration.attendance_count > 0,
            )
        )
    )
    if event_id:
        recent_query = recent_query.filter(CEMemberRegistration.event_entity_id == event_id)

    recent_checkins = (
        recent_query
        .order_by(CEMemberRegistration.started_at.desc(), CEMemberRegistration.id.desc())
        .limit(20)
        .all()
    )

    events = (
        CEEventEntity.query
        .join(CEMemberRegistration, CEMemberRegistration.event_entity_id == CEEventEntity.id)
        .distinct()
        .order_by(CEEventEntity.created_at.desc())
        .all()
    )

    return render_template(
        'continueing_edu/admin/attendance_qrcode.html',
        logged_in_admin=staff,
        event_id=event_id,
        events=events,
        recent_checkins=recent_checkins,
    )


@admin_bp.route('/attendance/checkin', methods=['POST'])
@login_required
@admin_required
def attendance_checkin():
    """Mark attendance from QR payload or registration id."""
    staff = get_current_staff()
    if not staff:
        return _attendance_error('Staff account not found.', status_code=403)

    event_filter_id = request.form.get('event_id', type=int)
    registration_id = request.form.get('registration_id', type=int)
    qr_data = (request.form.get('qr_data') or '').strip()

    embedded_event_id = None
    if not registration_id and qr_data:
        registration_id, embedded_event_id, parse_error = _resolve_registration_from_payload(qr_data)
        if parse_error:
            return _attendance_error(
                'QR payload format is invalid. Please scan a valid attendance QR code.',
                event_id=event_filter_id,
                details={'error_code': parse_error},
            )

    if not registration_id:
        return _attendance_error('Registration ID is required.', event_id=event_filter_id)

    registration = (
        CEMemberRegistration.query
        .options(
            joinedload(CEMemberRegistration.member),
            joinedload(CEMemberRegistration.event_entity),
            joinedload(CEMemberRegistration.status_ref),
        )
        .get(registration_id)
    )
    if not registration:
        return _attendance_error(
            f'Registration #{registration_id} not found.',
            event_id=event_filter_id,
            status_code=404,
        )

    if not check_can_manage_registrations(staff.id, registration.event_entity_id):
        return _attendance_error(
            'You do not have permission to check in this registration.',
            event_id=event_filter_id,
            status_code=403,
        )

    if event_filter_id and registration.event_entity_id != event_filter_id:
        return _attendance_error(
            'Scanned registration does not belong to selected event.',
            event_id=event_filter_id,
        )

    if embedded_event_id and registration.event_entity_id != embedded_event_id:
        return _attendance_error(
            'QR payload does not match registration event.',
            event_id=event_filter_id,
        )

    status_name = (registration.status_ref.name_en or '').strip().lower() if registration.status_ref else ''
    if 'cancel' in status_name:
        return _attendance_error(
            'This registration is cancelled and cannot be checked in.',
            event_id=event_filter_id,
        )

    hours_to_add = request.form.get('hours', type=float)
    increment_count = request.form.get('increment_count') == '1'

    now = datetime.now(timezone.utc)
    already_checked_in = bool(registration.started_at) or (registration.attendance_count or 0) > 0

    if not registration.started_at:
        registration.started_at = now
    if not already_checked_in:
        registration.attendance_count = max(1, registration.attendance_count or 0)
    elif increment_count:
        registration.attendance_count = (registration.attendance_count or 0) + 1

    if hours_to_add is not None and hours_to_add > 0:
        registration.total_hours_attended = float(registration.total_hours_attended or 0.0) + hours_to_add

    db.session.commit()

    member_name = (
        registration.member.full_name_th
        or registration.member.full_name_en
        or registration.member.username
        or f'Member #{registration.member_id}'
    )
    event_title = (
        registration.event_entity.title_th
        or registration.event_entity.title_en
        or f'Event #{registration.event_entity_id}'
    )

    if already_checked_in and not increment_count:
        message = f'{member_name} already checked in.'
    else:
        message = f'Checked in {member_name} successfully.'

    payload = {
        'success': True,
        'message': message,
        'already_checked_in': already_checked_in,
        'registration_id': registration.id,
        'member_name': member_name,
        'member_email': registration.member.email,
        'event_id': registration.event_entity_id,
        'event_title': event_title,
        'attendance_count': registration.attendance_count or 0,
        'total_hours_attended': float(registration.total_hours_attended or 0.0),
        'checked_in_at': registration.started_at.isoformat() if registration.started_at else None,
    }

    if _wants_json_response():
        return jsonify(payload)

    flash(payload['message'], 'success' if not already_checked_in else 'info')
    next_url = request.form.get('next') or request.referrer
    if next_url:
        return redirect(next_url)
    return redirect(url_for('continuing_edu_admin.attendance_management', event_id=event_filter_id or registration.event_entity_id))


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
    query = CEMemberRegistration.query.options(
        joinedload(CEMemberRegistration.member),
        joinedload(CEMemberRegistration.event_entity),
        joinedload(CEMemberRegistration.status_ref)
    )
    
    # Apply filters
    if status_filter:
        status = CERegistrationStatus.query.filter(
            func.lower(CERegistrationStatus.name_en) == status_filter.lower()
        ).first()
        if status:
            query = query.filter(CEMemberRegistration.status_id == status.id)
    
    if event_id:
        query = query.filter(CEMemberRegistration.event_entity_id == event_id)
    
    if member_id:
        query = query.filter(CEMemberRegistration.member_id == member_id)
    
    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            query = query.filter(CEMemberRegistration.registration_date >= date_from_dt)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            query = query.filter(CEMemberRegistration.registration_date <= date_to_dt)
        except ValueError:
            pass
    
    # Search in member name, email, or event title
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.join(CEMember).join(CEEventEntity).filter(
            or_(
                CEMember.full_name_th.ilike(search_pattern),
                CEMember.full_name_en.ilike(search_pattern),
                CEMember.email.ilike(search_pattern),
                CEMember.username.ilike(search_pattern),
                CEEventEntity.title_th.ilike(search_pattern),
                CEEventEntity.title_en.ilike(search_pattern)
            )
        )
    
    # Order by most recent first
    query = query.order_by(desc(CEMemberRegistration.registration_date))
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    registrations = pagination.items
    
    # Get all events for filter dropdown
    events = CEEventEntity.query.order_by(CEEventEntity.title_en).all()
    
    # Get all registration statuses
    statuses = CERegistrationStatus.query.all()
    
    # Statistics
    stats = {
        'total': CEMemberRegistration.query.count(),
        'pending': CEMemberRegistration.query.join(CERegistrationStatus).filter(
            func.lower(CERegistrationStatus.name_en) == 'pending'
        ).count(),
        'confirmed': CEMemberRegistration.query.join(CERegistrationStatus).filter(
            func.lower(CERegistrationStatus.name_en) == 'confirmed'
        ).count(),
        'cancelled': CEMemberRegistration.query.join(CERegistrationStatus).filter(
            func.lower(CERegistrationStatus.name_en) == 'cancelled'
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
    registration = CEMemberRegistration.query.options(
        joinedload(CEMemberRegistration.member).joinedload(CEMember.organization),
        joinedload(CEMemberRegistration.member).joinedload(CEMember.occupation),
        joinedload(CEMemberRegistration.member).joinedload(CEMember.addresses),
        joinedload(CEMemberRegistration.event_entity).joinedload(CEEventEntity.category),
        joinedload(CEMemberRegistration.event_entity).joinedload(CEEventEntity.speakers),
        joinedload(CEMemberRegistration.status_ref),
        joinedload(CEMemberRegistration.certificate_status_ref)
    ).get_or_404(registration_id)
    
    # Get registration fees for this event
    fees = CEEventRegistrationFee.query.filter_by(
        event_entity_id=registration.event_entity_id
    ).all()
    
    # Get payments related to this registration (by member + event)
    payments = CERegisterPayment.query.filter_by(
        member_id=registration.member_id,
        event_entity_id=registration.event_entity_id
    ).order_by(CERegisterPayment.payment_date.desc()).all()
    
    # Get all registration statuses for dropdown
    statuses = CERegistrationStatus.query.all()
    
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
    registration = CEMemberRegistration.query.get_or_404(registration_id)
    
    new_status_id = request.form.get('status_id', type=int)
    notes = request.form.get('notes', '').strip()
    
    if not new_status_id:
        flash('Please select a status', 'danger')
        return redirect(url_for('continuing_edu_admin.view_registration', registration_id=registration_id))
    
    # Verify status exists
    new_status = CERegistrationStatus.query.get(new_status_id)
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
    registration = CEMemberRegistration.query.get_or_404(registration_id)
    
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
    registration = CEMemberRegistration.query.get_or_404(registration_id)
    
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
    registration = CEMemberRegistration.query.get_or_404(registration_id)
    
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
    events = CEEventEntity.query.order_by(CEEventEntity.title_en).all()
    statuses = CERegistrationStatus.query.all()
    
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
    new_status = CERegistrationStatus.query.get(new_status_id)
    if not new_status:
        flash('Invalid status selected', 'danger')
        return redirect(url_for('continuing_edu_admin.bulk_actions'))
    
    # Update all selected registrations
    updated_count = CEMemberRegistration.query.filter(
        CEMemberRegistration.id.in_(registration_ids)
    ).update(
        {CEMemberRegistration.status_id: new_status_id},
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
    query = CEMemberRegistration.query.options(
        joinedload(CEMemberRegistration.member),
        joinedload(CEMemberRegistration.event_entity),
        joinedload(CEMemberRegistration.status_ref)
    )
    
    if status_filter:
        status = CERegistrationStatus.query.filter(
            func.lower(CERegistrationStatus.name_en) == status_filter.lower()
        ).first()
        if status:
            query = query.filter(CEMemberRegistration.status_id == status.id)
    
    if event_id:
        query = query.filter(CEMemberRegistration.event_entity_id == event_id)
    
    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            query = query.filter(CEMemberRegistration.registration_date >= date_from_dt)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            query = query.filter(CEMemberRegistration.registration_date <= date_to_dt)
        except ValueError:
            pass
    
    registrations = query.order_by(desc(CEMemberRegistration.registration_date)).all()
    
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
    event = CEEventEntity.query.get_or_404(event_id)
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Query registrations for this event
    query = CEMemberRegistration.query.filter_by(event_entity_id=event_id).options(
        joinedload(CEMemberRegistration.member),
        joinedload(CEMemberRegistration.status_ref)
    ).order_by(desc(CEMemberRegistration.registration_date))
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    registrations = pagination.items
    
    # Statistics for this event
    stats = {
        'total': query.count(),
        'pending': query.join(CERegistrationStatus).filter(
            func.lower(CERegistrationStatus.name_en) == 'pending'
        ).count(),
        'confirmed': query.join(CERegistrationStatus).filter(
            func.lower(CERegistrationStatus.name_en) == 'confirmed'
        ).count(),
        'cancelled': query.join(CERegistrationStatus).filter(
            func.lower(CERegistrationStatus.name_en) == 'cancelled'
        ).count(),
    }
    
    return render_template(
        'continueing_edu/admin/registrations/event_registrations.html',
        event=event,
        registrations=registrations,
        pagination=pagination,
        stats=stats
    )
