from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired

from flask import Blueprint, render_template, request, session, redirect, url_for, flash, Response
from app.staff.models import StaffAccount
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_required, current_user

from app.continuing_edu.admin.decorators import (
    admin_required,
    get_current_staff,
    require_event_role,
    can_manage_registrations,
    can_manage_payments,
    can_issue_receipts,
    can_manage_certificates,
    get_staff_permissions,
    filter_events_by_permission
)

from app.continuing_edu.models import (
    EventEntity,
    Member,
    RegisterPayment,
    RegisterPaymentStatus,
    RegisterPaymentReceipt,
    MemberRegistration,
    MemberType,
    RegistrationStatus,
    EntityCategory,
    MemberCertificateStatus,
    EventSpeaker,
    SpeakerProfile,
    EventAgenda,
    EventMaterial,
    EventRegistrationFee,
    EventEditor,
    EventRegistrationReviewer,
    EventPaymentApprover,
    EventReceiptIssuer,
    EventCertificateManager,
)
from sqlalchemy import func
import datetime
import calendar
from collections import OrderedDict
import os
from app.main import db, mail
from sqlalchemy.orm import joinedload

try:
    from weasyprint import HTML
except Exception:  # pragma: no cover - optional dependency
    HTML = None
from app.continuing_edu.status_utils import get_registration_status, get_certificate_status
from app.continuing_edu.certificate_utils import (
    issue_certificate as issue_certificate_util,
    reset_certificate as reset_certificate_util,
    can_issue_certificate,
    build_certificate_context,
)

# Blueprint definition (imported by __init__.py and main.py)
admin_bp = Blueprint('continuing_edu_admin', __name__, url_prefix='/continuing_edu/admin')


def _parse_date_arg(value: str, *, end: bool = False):
    """Parse YYYY-MM-DD into timezone-aware datetime in UTC."""
    if not value:
        return None
    try:
        dt = datetime.datetime.strptime(value, '%Y-%m-%d')
        if end:
            dt += datetime.timedelta(days=1)
        return dt.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None

class EventCreateStep1Form(FlaskForm):
    event_type = SelectField('Event Type', choices=[('course', 'Course'), ('webinar', 'Webinar')], validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired()])
    submit = SubmitField('Next')

@admin_bp.route('/events/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_event():
    staff = get_current_staff()
    print(staff)
    form = EventCreateStep1Form()
    if form.validate_on_submit():
        # Create EventEntity row with minimal info
        event = EventEntity(event_type=form.event_type.data, title_en=form.title.data, staff_id=staff.id)
        db.session.add(event)
        db.session.commit()
        
        # Automatically assign creator to ALL roles for this event
        editor = EventEditor(event_entity_id=event.id, staff_id=staff.id)
        registration_reviewer = EventRegistrationReviewer(event_entity_id=event.id, staff_id=staff.id)
        payment_approver = EventPaymentApprover(event_entity_id=event.id, staff_id=staff.id)
        receipt_issuer = EventReceiptIssuer(event_entity_id=event.id, staff_id=staff.id)
        certificate_manager = EventCertificateManager(event_entity_id=event.id, staff_id=staff.id)
        
        db.session.add_all([editor, registration_reviewer, payment_approver, receipt_issuer, certificate_manager])
        db.session.commit()
        
        flash('Event created successfully. You have been assigned all roles for this event.', 'success')
        # Redirect to edit page with tabs for further info
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id))
    return render_template('continueing_edu/admin/event_create_step1.html', form=form, logged_in_admin=staff)

@admin_bp.route('/events/<int:event_id>/edit', methods=['GET'])
@login_required
@require_event_role('editor')
def edit_event(event_id):
    staff = get_current_staff()
    event = EventEntity.query.get_or_404(event_id)

    # Load related data for all tabs
    speakers = EventSpeaker.query.filter_by(event_entity_id=event.id).all()
    agendas = EventAgenda.query.filter_by(event_entity_id=event.id).order_by(EventAgenda.order.asc()).all()
    materials = EventMaterial.query.filter_by(event_entity_id=event.id).order_by(EventMaterial.order.asc()).all()
    fees = EventRegistrationFee.query.filter_by(event_entity_id=event.id).all()
    # Staff list for role assignments
    staff_list = StaffAccount.query.all()
    member_types = MemberType.query.order_by(MemberType.name_en.asc()).all()

    # Current staff role assignments
    editors = EventEditor.query.filter_by(event_entity_id=event.id).all()
    registration_reviewers = EventRegistrationReviewer.query.filter_by(event_entity_id=event.id).all()
    payment_approvers = EventPaymentApprover.query.filter_by(event_entity_id=event.id).all()
    receipt_issuers = EventReceiptIssuer.query.filter_by(event_entity_id=event.id).all()
    certificate_managers = EventCertificateManager.query.filter_by(event_entity_id=event.id).all()

    # Speaker pool (existing speakers from any event) for reuse
    speakers_pool = SpeakerProfile.query.filter_by(is_active=True).order_by(SpeakerProfile.name_en.asc()).all()

    active_tab = request.args.get('tab', 'general')

    registrations = []
    payments_map = {}
    registration_statuses = []
    certificate_statuses = []
    if active_tab == 'certificates':
        if not can_manage_certificates(event.id):
            flash('You do not have permission to manage certificates for this event.', 'danger')
            return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id))
        registrations = MemberRegistration.query.filter_by(event_entity_id=event.id).order_by(MemberRegistration.registration_date.asc()).all()
        member_ids = [r.member_id for r in registrations]
        if member_ids:
            payments = (RegisterPayment.query
                        .filter(RegisterPayment.event_entity_id == event.id,
                                RegisterPayment.member_id.in_(member_ids))
                        .order_by(RegisterPayment.id.desc())
                        .all())
            for pay in payments:
                existing = payments_map.get(pay.member_id)
                if not existing:
                    payments_map[pay.member_id] = pay
        registration_statuses = RegistrationStatus.query.order_by(RegistrationStatus.name_en.asc()).all()
        certificate_statuses = MemberCertificateStatus.query.order_by(MemberCertificateStatus.name_en.asc()).all()

    return render_template(
        'continueing_edu/admin/event_edit_tabs.html',
        event=event,
        speakers=speakers,
        agendas=agendas,
        materials=materials,
        fees=fees,
        staff_list=staff_list,
        member_types=member_types,
        speakers_pool=speakers_pool,
        editors=editors,
        registration_reviewers=registration_reviewers,
        payment_approvers=payment_approvers,
        receipt_issuers=receipt_issuers,
        certificate_managers=certificate_managers,
        active_tab=active_tab,
        logged_in_admin=staff,
        registrations=registrations,
        payments_map=payments_map,
        registration_statuses=registration_statuses,
        certificate_statuses=certificate_statuses,
        can_issue_certificate=can_issue_certificate,
    )

# Login/logout now handled by main MIS system via @login_required

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    staff = get_current_staff()
    print(staff)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    current_date = now_utc.astimezone().strftime('%A %d %B %Y')

    # Summary counts & momentum
    course_count = EventEntity.query.filter_by(event_type='course').count()
    webinar_count = EventEntity.query.filter_by(event_type='webinar').count()
    member_count = Member.query.count()
    registration_count = MemberRegistration.query.count()
    payment_sum = RegisterPayment.query.with_entities(func.coalesce(func.sum(RegisterPayment.payment_amount), 0)).scalar() or 0

    last_30_days = now_utc - datetime.timedelta(days=30)
    registrations_30d = MemberRegistration.query.filter(MemberRegistration.registration_date >= last_30_days).count()
    payments_30d = RegisterPayment.query.filter(RegisterPayment.payment_date >= last_30_days).count()
    new_members_30d = Member.query.filter(Member.created_at >= last_30_days).count()

    # Payment status distribution
    payment_status_rows = (
        db.session.query(
            RegisterPaymentStatus.name_en,
            func.count(RegisterPayment.id),
            func.coalesce(func.sum(RegisterPayment.payment_amount), 0)
        )
        .outerjoin(RegisterPayment, RegisterPayment.payment_status_id == RegisterPaymentStatus.id)
        .group_by(RegisterPaymentStatus.id)
        .order_by(RegisterPaymentStatus.name_en.asc())
        .all()
    )
    payment_status_summary = [
        {
            'label': row[0] or 'Unknown',
            'count': row[1] or 0,
            'amount': float(row[2] or 0)
        }
        for row in payment_status_rows
    ]

    # Member type breakdown
    member_type_rows = (
        db.session.query(
            MemberType.name_en,
            func.count(Member.id)
        )
        .outerjoin(Member, Member.member_type_id == MemberType.id)
        .group_by(MemberType.id)
        .order_by(func.count(Member.id).desc())
        .all()
    )
    member_type_breakdown = [
        {
            'label': row[0] or 'Unspecified',
            'count': row[1] or 0
        }
        for row in member_type_rows
    ]

    unspecified_members = Member.query.filter(Member.member_type_id.is_(None)).count()
    if unspecified_members:
        # avoid duplicating label if already present without explicit name
        if not any(item['label'] == 'Unspecified' for item in member_type_breakdown):
            member_type_breakdown.append({'label': 'Unspecified', 'count': unspecified_members})
        else:
            for item in member_type_breakdown:
                if item['label'] == 'Unspecified':
                    item['count'] += unspecified_members
                    break

    # Recent activity
    recent_registrations = (
        MemberRegistration.query
        .order_by(MemberRegistration.registration_date.desc())
        .limit(8)
        .all()
    )
    recent_payments = (
        RegisterPayment.query
        .order_by(RegisterPayment.payment_date.desc())
        .limit(8)
        .all()
    )

    # Monthly registrations (last 12 months)
    months = []
    year = now_utc.year
    month = now_utc.month
    for _ in range(12):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    months = list(reversed(months))

    first_month_year, first_month = months[0]
    month_start = datetime.datetime(first_month_year, first_month, 1, tzinfo=datetime.timezone.utc)
    monthly_regs = OrderedDict()
    for y, m in months:
        label = f"{calendar.month_abbr[m]} {str(y)[-2:]}"
        monthly_regs[(y, m)] = {'label': label, 'count': 0}

    registrations_for_chart = (
        MemberRegistration.query
        .filter(MemberRegistration.registration_date >= month_start)
        .with_entities(MemberRegistration.registration_date)
        .all()
    )
    for (reg_date,) in registrations_for_chart:
        if not reg_date:
            continue
        if reg_date.tzinfo is None:
            reg_dt = reg_date.replace(tzinfo=datetime.timezone.utc)
        else:
            reg_dt = reg_date.astimezone(datetime.timezone.utc)
        key = (reg_dt.year, reg_dt.month)
        if key in monthly_regs:
            monthly_regs[key]['count'] += 1

    monthly_registration_labels = [item['label'] for item in monthly_regs.values()]
    monthly_registration_counts = [item['count'] for item in monthly_regs.values()]

    # Average payment approval time
    approval_rows = (
        RegisterPayment.query
        .filter(RegisterPayment.approval_date.isnot(None), RegisterPayment.payment_date.isnot(None))
        .with_entities(RegisterPayment.payment_date, RegisterPayment.approval_date)
        .all()
    )
    total_seconds = 0
    approvals_count = 0
    for payment_date, approval_date in approval_rows:
        pay_dt = payment_date
        appr_dt = approval_date
        if pay_dt.tzinfo is None:
            pay_dt = pay_dt.replace(tzinfo=datetime.timezone.utc)
        if appr_dt.tzinfo is None:
            appr_dt = appr_dt.replace(tzinfo=datetime.timezone.utc)
        delta = (appr_dt - pay_dt).total_seconds()
        if delta >= 0:
            total_seconds += delta
            approvals_count += 1
    avg_payment_approval_hours = round(total_seconds / approvals_count / 3600, 2) if approvals_count else None

    # Popular events (top 5 by registrations)
    registration_counts = dict(
        db.session.query(
            MemberRegistration.event_entity_id,
            func.count(MemberRegistration.id)
        ).group_by(MemberRegistration.event_entity_id).all()
    )
    top_event_ids = [event_id for event_id, _ in sorted(registration_counts.items(), key=lambda item: item[1], reverse=True)[:5]]
    popular_events = []
    if top_event_ids:
        events = EventEntity.query.filter(EventEntity.id.in_(top_event_ids)).all()
        events_map = {event.id: event for event in events}
        payment_totals = dict(
            db.session.query(
                RegisterPayment.event_entity_id,
                func.coalesce(func.sum(RegisterPayment.payment_amount), 0)
            ).group_by(RegisterPayment.event_entity_id).all()
        )
        for event_id in top_event_ids:
            event = events_map.get(event_id)
            if not event:
                continue
            popular_events.append({
                'id': event.id,
                'title': event.title_en or event.title_th or f"Event #{event.id}",
                'event_type': event.event_type,
                'registrations': registration_counts.get(event_id, 0),
                'revenue': float(payment_totals.get(event_id, 0))
            })

    # Popular course categories (top 5)
    category_rows = (
        db.session.query(
            EntityCategory.name_en,
            func.count(MemberRegistration.id)
        )
        .join(EventEntity, EventEntity.category_id == EntityCategory.id)
        .join(MemberRegistration, MemberRegistration.event_entity_id == EventEntity.id)
        .group_by(EntityCategory.id)
        .order_by(func.count(MemberRegistration.id).desc())
        .limit(5)
        .all()
    )
    popular_categories = [
        {
            'label': row[0] or 'Uncategorized',
            'count': row[1] or 0
        }
        for row in category_rows
    ]

    # Top engaged members (registrations)
    top_members_rows = (
        db.session.query(
            Member.id,
            Member.full_name_en,
            Member.username,
            func.count(MemberRegistration.id).label('reg_count')
        )
        .join(MemberRegistration, MemberRegistration.member_id == Member.id)
        .group_by(Member.id)
        .order_by(func.count(MemberRegistration.id).desc())
        .limit(5)
        .all()
    )
    top_members = [
        {
            'name': row[1] or row[2] or f"Member #{row[0]}",
            'registrations': row[3]
        }
        for row in top_members_rows
    ]

    # Latest courses for operational overview
    latest_courses = (
        EventEntity.query
        .filter_by(event_type='course')
        .order_by(EventEntity.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        'continueing_edu/admin/dashboard.html',
        logged_in_admin=staff,
        current_date=current_date,
        course_count=course_count,
        webinar_count=webinar_count,
        member_count=member_count,
        registration_count=registration_count,
        payment_sum=payment_sum,
        registrations_30d=registrations_30d,
        payments_30d=payments_30d,
        new_members_30d=new_members_30d,
        payment_status_summary=payment_status_summary,
        member_type_breakdown=member_type_breakdown,
        recent_registrations=recent_registrations,
        recent_payments=recent_payments,
        monthly_registration_labels=monthly_registration_labels,
        monthly_registration_counts=monthly_registration_counts,
        avg_payment_approval_hours=avg_payment_approval_hours,
        popular_events=popular_events,
        popular_categories=popular_categories,
        top_members=top_members,
        latest_courses=latest_courses,
    )


@admin_bp.route('/reports/registrations')
@login_required
@admin_required
def registrations_report():
    staff = get_current_staff()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    start_raw = request.args.get('start')
    end_raw = request.args.get('end')
    event_type = (request.args.get('event_type') or '').strip()
    status_raw = (request.args.get('status_id') or '').strip()

    start_dt = _parse_date_arg(start_raw)
    end_dt = _parse_date_arg(end_raw, end=True)

    filters = []
    if start_dt:
        filters.append(MemberRegistration.registration_date >= start_dt)
    if end_dt:
        filters.append(MemberRegistration.registration_date < end_dt)
    if event_type:
        filters.append(EventEntity.event_type == event_type)

    status_id = None
    if status_raw:
        try:
            status_id = int(status_raw)
            filters.append(MemberRegistration.status_id == status_id)
        except ValueError:
            status_id = None

    base_query = (
        MemberRegistration.query
        .join(Member)
        .join(EventEntity)
        .options(
            joinedload(MemberRegistration.member),
            joinedload(MemberRegistration.event_entity),
            joinedload(MemberRegistration.status_ref),
            joinedload(MemberRegistration.certificate_status_ref),
        )
        .filter(*filters)
    )

    pagination = base_query.order_by(MemberRegistration.registration_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    registrations = pagination.items

    total_count = base_query.count()
    unique_members = base_query.with_entities(func.count(func.distinct(MemberRegistration.member_id))).scalar() or 0

    status_breakdown_rows = (
        db.session.query(
            RegistrationStatus.name_en,
            func.count(MemberRegistration.id)
        )
        .join(MemberRegistration)
        .join(EventEntity)
        .filter(*filters)
        .group_by(RegistrationStatus.id)
        .order_by(func.count(MemberRegistration.id).desc())
        .all()
    )
    status_breakdown = [{'label': row[0], 'count': row[1]} for row in status_breakdown_rows]

    event_breakdown_rows = (
        db.session.query(
            EventEntity.event_type,
            func.count(MemberRegistration.id)
        )
        .join(MemberRegistration, MemberRegistration.event_entity_id == EventEntity.id)
        .filter(*filters)
        .group_by(EventEntity.event_type)
        .order_by(func.count(MemberRegistration.id).desc())
        .all()
    )
    event_breakdown = [{'label': row[0], 'count': row[1]} for row in event_breakdown_rows]

    top_events_rows = (
        db.session.query(
            EventEntity.title_en,
            EventEntity.title_th,
            func.count(MemberRegistration.id)
        )
        .join(MemberRegistration, MemberRegistration.event_entity_id == EventEntity.id)
        .filter(*filters)
        .group_by(EventEntity.id)
        .order_by(func.count(MemberRegistration.id).desc())
        .limit(5)
        .all()
    )
    top_events = [
        {
            'title': title_en or title_th or 'Unnamed Event',
            'count': count
        }
        for title_en, title_th, count in top_events_rows
    ]

    registration_statuses = RegistrationStatus.query.order_by(RegistrationStatus.name_en.asc()).all()
    available_event_types = [row[0] for row in db.session.query(EventEntity.event_type).distinct().order_by(EventEntity.event_type).all() if row[0]]

    return render_template(
        'continueing_edu/admin/reports/registrations_report.html',
        logged_in_admin=staff,
        registrations=registrations,
        pagination=pagination,
        total_count=total_count,
        unique_members=unique_members,
        status_breakdown=status_breakdown,
        event_breakdown=event_breakdown,
        top_events=top_events,
        registration_statuses=registration_statuses,
        available_event_types=available_event_types,
        selected_event_type=event_type,
        selected_status_id=status_raw,
        start_value=start_raw,
        end_value=end_raw,
    )


@admin_bp.route('/reports/payments')
@login_required
@admin_required
def payments_report():
    staff = get_current_staff()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    start_raw = request.args.get('start')
    end_raw = request.args.get('end')
    event_type = (request.args.get('event_type') or '').strip()
    status_raw = (request.args.get('status_id') or '').strip()

    start_dt = _parse_date_arg(start_raw)
    end_dt = _parse_date_arg(end_raw, end=True)

    filters = []
    if start_dt:
        filters.append(RegisterPayment.payment_date >= start_dt)
    if end_dt:
        filters.append(RegisterPayment.payment_date < end_dt)
    if event_type:
        filters.append(EventEntity.event_type == event_type)

    status_id = None
    if status_raw:
        try:
            status_id = int(status_raw)
            filters.append(RegisterPayment.payment_status_id == status_id)
        except ValueError:
            status_id = None

    base_query = (
        RegisterPayment.query
        .join(Member)
        .join(EventEntity)
        .join(RegisterPaymentStatus)
        .options(
            joinedload(RegisterPayment.member),
            joinedload(RegisterPayment.event_entity),
            joinedload(RegisterPayment.payment_status_ref),
            joinedload(RegisterPayment.receipt),
        )
        .filter(*filters)
    )

    pagination = base_query.order_by(RegisterPayment.payment_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    payments = pagination.items

    total_payments = base_query.count()
    total_amount = base_query.with_entities(func.coalesce(func.sum(RegisterPayment.payment_amount), 0)).scalar() or 0

    status_breakdown_rows = (
        db.session.query(
            RegisterPaymentStatus.name_en,
            func.count(RegisterPayment.id),
            func.coalesce(func.sum(RegisterPayment.payment_amount), 0)
        )
        .join(RegisterPayment)
        .join(EventEntity)
        .filter(*filters)
        .group_by(RegisterPaymentStatus.id)
        .order_by(func.count(RegisterPayment.id).desc())
        .all()
    )
    status_breakdown = [
        {
            'label': row[0],
            'count': row[1],
            'amount': float(row[2] or 0)
        }
        for row in status_breakdown_rows
    ]

    event_breakdown_rows = (
        db.session.query(
            EventEntity.title_en,
            EventEntity.title_th,
            func.coalesce(func.sum(RegisterPayment.payment_amount), 0)
        )
        .join(RegisterPayment)
        .filter(*filters)
        .group_by(EventEntity.id)
        .order_by(func.coalesce(func.sum(RegisterPayment.payment_amount), 0).desc())
        .limit(5)
        .all()
    )
    top_revenue_events = [
        {
            'title': title_en or title_th or 'Unnamed Event',
            'amount': float(amount or 0)
        }
        for title_en, title_th, amount in event_breakdown_rows
    ]

    payment_statuses = RegisterPaymentStatus.query.order_by(RegisterPaymentStatus.name_en.asc()).all()
    available_event_types = [row[0] for row in db.session.query(EventEntity.event_type).distinct().order_by(EventEntity.event_type).all() if row[0]]

    average_ticket = float(total_amount / total_payments) if total_payments else 0

    return render_template(
        'continueing_edu/admin/reports/payments_report.html',
        logged_in_admin=staff,
        payments=payments,
        pagination=pagination,
        total_payments=total_payments,
        total_amount=total_amount,
        average_ticket=average_ticket,
        status_breakdown=status_breakdown,
        top_revenue_events=top_revenue_events,
        payment_statuses=payment_statuses,
        available_event_types=available_event_types,
        selected_event_type=event_type,
        selected_status_id=status_raw,
        start_value=start_raw,
        end_value=end_raw,
    )


@admin_bp.route('/reports/courses')
@login_required
@admin_required
def courses_report():
    staff = get_current_staff()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    event_type = (request.args.get('event_type') or 'course').strip()
    category_raw = (request.args.get('category_id') or '').strip()
    start_raw = request.args.get('start')
    end_raw = request.args.get('end')

    start_dt = _parse_date_arg(start_raw)
    end_dt = _parse_date_arg(end_raw, end=True)

    filters = []
    if event_type:
        filters.append(EventEntity.event_type == event_type)
    if category_raw:
        try:
            filters.append(EventEntity.category_id == int(category_raw))
        except ValueError:
            category_raw = ''
    if start_dt:
        filters.append(EventEntity.created_at >= start_dt)
    if end_dt:
        filters.append(EventEntity.created_at < end_dt)

    events_query = EventEntity.query.filter(*filters)

    pagination = events_query.order_by(EventEntity.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    events = pagination.items

    # Aggregate metrics for filtered events
    reg_metrics_rows = (
        db.session.query(
            MemberRegistration.event_entity_id,
            func.count(MemberRegistration.id),
            func.count(func.distinct(MemberRegistration.member_id))
        )
        .join(EventEntity, MemberRegistration.event_entity_id == EventEntity.id)
        .filter(*filters)
        .group_by(MemberRegistration.event_entity_id)
        .all()
    )
    reg_counts = {row[0]: {'registrations': row[1], 'unique_members': row[2]} for row in reg_metrics_rows}

    payment_metrics_rows = (
        db.session.query(
            RegisterPayment.event_entity_id,
            func.coalesce(func.sum(RegisterPayment.payment_amount), 0),
            func.count(RegisterPayment.id)
        )
        .join(EventEntity, RegisterPayment.event_entity_id == EventEntity.id)
        .filter(*filters)
        .group_by(RegisterPayment.event_entity_id)
        .all()
    )
    payment_totals = {row[0]: {'amount': float(row[1] or 0), 'payments': row[2]} for row in payment_metrics_rows}

    events_data = []
    for event in events:
        reg_info = reg_counts.get(event.id, {'registrations': 0, 'unique_members': 0})
        pay_info = payment_totals.get(event.id, {'amount': 0.0, 'payments': 0})
        events_data.append({
            'event': event,
            'registrations': reg_info['registrations'],
            'unique_members': reg_info['unique_members'],
            'payments': pay_info['payments'],
            'amount': pay_info['amount'],
        })

    total_events = events_query.count()
    total_registrations = sum(item['registrations'] for item in events_data)
    total_amount = sum(item['amount'] for item in events_data)

    categories = EntityCategory.query.order_by(EntityCategory.name_en.asc()).all()
    available_event_types = [row[0] for row in db.session.query(EventEntity.event_type).distinct().order_by(EventEntity.event_type).all() if row[0]]

    return render_template(
        'continueing_edu/admin/reports/courses_report.html',
        logged_in_admin=staff,
        events_data=events_data,
        pagination=pagination,
        total_events=total_events,
        total_registrations=total_registrations,
        total_amount=total_amount,
        categories=categories,
        available_event_types=available_event_types,
        selected_event_type=event_type,
        selected_category_id=category_raw,
        start_value=start_raw,
        end_value=end_raw,
    )


@admin_bp.route('/reports/members')
@login_required
@admin_required
def members_report():
    staff = get_current_staff()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    q = (request.args.get('q') or '').strip()
    member_type_raw = (request.args.get('member_type_id') or '').strip()
    verified = (request.args.get('is_verified') or '').strip()
    start_raw = request.args.get('start')
    end_raw = request.args.get('end')

    start_dt = _parse_date_arg(start_raw)
    end_dt = _parse_date_arg(end_raw, end=True)

    members_query = Member.query
    if q:
        like = f"%{q}%"
        members_query = members_query.filter(
            (Member.username.ilike(like)) |
            (Member.email.ilike(like)) |
            (Member.full_name_en.ilike(like)) |
            (Member.full_name_th.ilike(like))
        )
    if member_type_raw:
        try:
            members_query = members_query.filter(Member.member_type_id == int(member_type_raw))
        except ValueError:
            member_type_raw = ''
    if verified in ('0', '1'):
        members_query = members_query.filter(Member.is_verified == (verified == '1'))
    if start_dt:
        members_query = members_query.filter(Member.created_at >= start_dt)
    if end_dt:
        members_query = members_query.filter(Member.created_at < end_dt)

    pagination = members_query.order_by(Member.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    members = pagination.items

    member_ids = [m.id for m in members]

    reg_counts = {}
    reg_last = {}
    payment_sums = {}
    payment_last = {}

    if member_ids:
        reg_counts = dict(
            db.session.query(
                MemberRegistration.member_id,
                func.count(MemberRegistration.id)
            )
            .filter(MemberRegistration.member_id.in_(member_ids))
            .group_by(MemberRegistration.member_id)
            .all()
        )
        reg_last = dict(
            db.session.query(
                MemberRegistration.member_id,
                func.max(MemberRegistration.registration_date)
            )
            .filter(MemberRegistration.member_id.in_(member_ids))
            .group_by(MemberRegistration.member_id)
            .all()
        )
        payment_sums = dict(
            db.session.query(
                RegisterPayment.member_id,
                func.coalesce(func.sum(RegisterPayment.payment_amount), 0)
            )
            .filter(RegisterPayment.member_id.in_(member_ids))
            .group_by(RegisterPayment.member_id)
            .all()
        )
        payment_last = dict(
            db.session.query(
                RegisterPayment.member_id,
                func.max(RegisterPayment.payment_date)
            )
            .filter(RegisterPayment.member_id.in_(member_ids))
            .group_by(RegisterPayment.member_id)
            .all()
        )

    members_data = []
    for member in members:
        members_data.append({
            'member': member,
            'registrations': reg_counts.get(member.id, 0),
            'last_registration': reg_last.get(member.id),
            'payments_total': float(payment_sums.get(member.id, 0) or 0),
            'last_payment': payment_last.get(member.id),
        })

    total_members = members_query.count()
    total_registrations = sum(item['registrations'] for item in members_data)
    total_payments = sum(item['payments_total'] for item in members_data)

    member_types = MemberType.query.order_by(MemberType.name_en.asc()).all()

    return render_template(
        'continueing_edu/admin/reports/members_report.html',
        logged_in_admin=staff,
        members_data=members_data,
        pagination=pagination,
        total_members=total_members,
        total_registrations=total_registrations,
        total_payments=total_payments,
        member_types=member_types,
        q=q,
        member_type_id=member_type_raw,
        verified=verified,
        start_value=start_raw,
        end_value=end_raw,
    )


@admin_bp.route('/certificates')
@login_required
@admin_required
def certificates_index():
    staff = get_current_staff()

    events = EventEntity.query.order_by(EventEntity.created_at.desc()).all()
    event_ids = [e.id for e in events]

    reg_counts = {}
    issued_counts = {}
    pending_counts = {}
    if event_ids:
        reg_counts = dict(
            db.session.query(
                MemberRegistration.event_entity_id,
                func.count(MemberRegistration.id)
            )
            .filter(MemberRegistration.event_entity_id.in_(event_ids))
            .group_by(MemberRegistration.event_entity_id)
            .all()
        )
        issued_counts = dict(
            db.session.query(
                MemberRegistration.event_entity_id,
                func.count(MemberRegistration.id)
            )
            .filter(
                MemberRegistration.event_entity_id.in_(event_ids),
                MemberRegistration.certificate_issued_date.isnot(None)
            )
            .group_by(MemberRegistration.event_entity_id)
            .all()
        )
        pending_counts = dict(
            db.session.query(
                MemberRegistration.event_entity_id,
                func.count(MemberRegistration.id)
            )
            .join(MemberRegistration.certificate_status_ref)
            .filter(
                MemberRegistration.event_entity_id.in_(event_ids),
                MemberCertificateStatus.name_en.ilike('%pending%')
            )
            .group_by(MemberRegistration.event_entity_id)
            .all()
        )

    events_data = []
    for event in events:
        total_regs = reg_counts.get(event.id, 0)
        issued = issued_counts.get(event.id, 0)
        pending = pending_counts.get(event.id, 0)
        events_data.append({
            'event': event,
            'total_regs': total_regs,
            'issued': issued,
            'pending': pending,
        })

    return render_template(
        'continueing_edu/admin/certificates_index.html',
        logged_in_admin=staff,
        events_data=events_data,
    )


@admin_bp.route('/certificates/event/<int:event_id>')
@login_required
@admin_required
def certificates_event_detail(event_id):
    staff = get_current_staff()

    event = EventEntity.query.get_or_404(event_id)

    registrations = (
        MemberRegistration.query
        .filter_by(event_entity_id=event_id)
        .options(
            joinedload(MemberRegistration.member),
            joinedload(MemberRegistration.status_ref),
            joinedload(MemberRegistration.certificate_status_ref),
        )
        .order_by(MemberRegistration.registration_date.desc())
        .all()
    )

    member_ids = [reg.member_id for reg in registrations]
    payments_map = {}
    if member_ids:
        payments = (
            RegisterPayment.query
            .filter(RegisterPayment.event_entity_id == event_id, RegisterPayment.member_id.in_(member_ids))
            .order_by(RegisterPayment.payment_date.desc())
            .all()
        )
        for payment in payments:
            if payment.member_id not in payments_map:
                payments_map[payment.member_id] = payment

    return render_template(
        'continueing_edu/admin/certificates_event.html',
        logged_in_admin=staff,
        event=event,
        registrations=registrations,
        payments_map=payments_map,
    )


@admin_bp.route('/certificates/registration/<int:reg_id>/pdf')
@login_required
@admin_required
def certificates_registration_pdf(reg_id):
    staff = get_current_staff()

    reg = MemberRegistration.query.get_or_404(reg_id)
    event_id = reg.event_entity_id
    lang = request.args.get('lang', 'en')

    if reg.certificate_url:
        url = reg.certificate_presigned_url()
        if url:
            return redirect(url)
        return redirect(reg.certificate_url)

    if HTML is None:
        flash('PDF rendering library is not available on this server.', 'danger')
        return redirect(url_for('continuing_edu_admin.certificates_event_detail', event_id=event_id))

    context = build_certificate_context(reg, lang=lang, base_url=request.url_root)
    html = render_template('continueing_edu/certificate_pdf.html', **context)
    pdf = HTML(string=html, base_url=request.url_root).write_pdf()
    filename = f"certificate_{reg.member_id}_{event_id}.pdf"
    return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': f'inline; filename="{filename}"'})

@admin_bp.route('/events')
@login_required
@admin_required
def manage_events():
    staff = get_current_staff()
    events = EventEntity.query.order_by(EventEntity.created_at.desc()).all()
    return render_template('continueing_edu/admin/events.html', logged_in_admin=staff, events=events)


@admin_bp.route('/progress')
@login_required
@admin_required
def progress_index():
    staff = get_current_staff()
    events = EventEntity.query.order_by(EventEntity.created_at.desc()).all()
    # Build simple stats per event
    stats = {}
    for e in events:
        regs = MemberRegistration.query.filter_by(event_entity_id=e.id).all()
        started = len([r for r in regs if r.started_at])
        completed = len([r for r in regs if r.completed_at])
        issued = len([r for r in regs if r.certificate_issued_date])
        stats[e.id] = {
            'registrations': len(regs),
            'started': started,
            'completed': completed,
            'cert_issued': issued,
        }
    return render_template('continueing_edu/admin/progress_index.html', logged_in_admin=staff, events=events, stats=stats)


@admin_bp.route('/promotions')
@login_required
@admin_required
def promotions_index():
    staff = get_current_staff()
    events = EventEntity.query.order_by(EventEntity.created_at.desc()).all()
    return render_template('continueing_edu/admin/promotions_index.html', logged_in_admin=staff, events=events)


# -----------------------------
# Members Management (CRUD)
# -----------------------------
@admin_bp.route('/members')
@login_required
@admin_required
def members_index():
    staff = get_current_staff()
    q = request.args.get('q', '').strip()
    member_type_id = request.args.get('member_type_id')
    is_verified = request.args.get('is_verified')
    received_news = request.args.get('received_news')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = Member.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Member.username.ilike(like)) |
            (Member.email.ilike(like)) |
            (Member.full_name_en.ilike(like)) |
            (Member.full_name_th.ilike(like))
        )
    if member_type_id:
        try:
            query = query.filter_by(member_type_id=int(member_type_id))
        except Exception:
            pass
    if is_verified in ('0', '1'):
        query = query.filter_by(is_verified=(is_verified == '1'))
    if received_news in ('0', '1'):
        query = query.filter_by(received_news=(received_news == '1'))

    pagination = query.order_by(Member.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    members = pagination.items
    member_types = MemberType.query.order_by(MemberType.name_en.asc()).all()
    return render_template('continueing_edu/admin/members.html',
                           logged_in_admin=staff,
                           members=members,
                           pagination=pagination,
                           q=q,
                           member_type_id=str(member_type_id) if member_type_id else '',
                           is_verified=is_verified or '',
                           received_news=received_news or '',
                           member_types=member_types)


@admin_bp.route('/members/create', methods=['GET', 'POST'])
@login_required
@admin_required
def members_create():
    staff = get_current_staff()
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip() or None
        password = request.form.get('password', '').strip()
        member_type_id = request.form.get('member_type_id') or None
        full_name_en = request.form.get('full_name_en') or None
        full_name_th = request.form.get('full_name_th') or None
        phone_no = request.form.get('phone_no') or None
        address = request.form.get('address') or None
        is_verified = request.form.get('is_verified') == 'on'
        received_news = request.form.get('received_news') == 'on'

        # Basic validations
        if not username:
            flash('Username is required.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_create'))
        if Member.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_create'))
        if email and Member.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_create'))
        if not password:
            flash('Password is required.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_create'))

        try:
            member = Member(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                member_type_id=int(member_type_id) if member_type_id else None,
                full_name_en=full_name_en,
                full_name_th=full_name_th,
                phone_no=phone_no,
                address=address,
                is_verified=is_verified,
                received_news=received_news,
            )
            db.session.add(member)
            db.session.commit()
            flash('Member created.', 'success')
            return redirect(url_for('continuing_edu_admin.members_index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating member: {e}', 'danger')

    member_types = MemberType.query.order_by(MemberType.name_en.asc()).all()
    return render_template('continueing_edu/admin/member_form.html',
                           logged_in_admin=staff,
                           member=None,
                           member_types=member_types,
                           form_action=url_for('continuing_edu_admin.members_create'))


@admin_bp.route('/members/<int:member_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def members_edit(member_id):
    staff = get_current_staff()
    member = Member.query.get_or_404(member_id)
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip() or None
        password = request.form.get('password', '').strip()
        member_type_id = request.form.get('member_type_id') or None
        full_name_en = request.form.get('full_name_en') or None
        full_name_th = request.form.get('full_name_th') or None
        phone_no = request.form.get('phone_no') or None
        address = request.form.get('address') or None
        is_verified = request.form.get('is_verified') == 'on'
        received_news = request.form.get('received_news') == 'on'

        if not username:
            flash('Username is required.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_edit', member_id=member.id))
        # Ensure username/email uniqueness
        if username != member.username and Member.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_edit', member_id=member.id))
        if email and email != member.email and Member.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_edit', member_id=member.id))

        try:
            member.username = username
            member.email = email
            if password:
                member.password_hash = generate_password_hash(password)
            member.member_type_id = int(member_type_id) if member_type_id else None
            member.full_name_en = full_name_en
            member.full_name_th = full_name_th
            member.phone_no = phone_no
            member.address = address
            member.is_verified = is_verified
            member.received_news = received_news
            db.session.add(member)
            db.session.commit()
            flash('Member updated.', 'success')
            return redirect(url_for('continuing_edu_admin.members_index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating member: {e}', 'danger')

    member_types = MemberType.query.order_by(MemberType.name_en.asc()).all()
    return render_template('continueing_edu/admin/member_form.html',
                           logged_in_admin=staff,
                           member=member,
                           member_types=member_types,
                           form_action=url_for('continuing_edu_admin.members_edit', member_id=member.id))


@admin_bp.route('/members/<int:member_id>/delete', methods=['POST'])
@login_required
@admin_required
def members_delete(member_id):
    staff = get_current_staff()
    member = Member.query.get_or_404(member_id)
    try:
        db.session.delete(member)
        db.session.commit()
        flash('Member deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete member: {e}', 'danger')
    return redirect(url_for('continuing_edu_admin.members_index'))


# -----------------------------
# General Settings: Member Types
# -----------------------------
@admin_bp.route('/settings/member_types', methods=['GET', 'POST'])
@login_required
@admin_required
def settings_member_types():
    staff = get_current_staff()
    if request.method == 'POST':
        name_en = request.form.get('name_en', '').strip()
        name_th = request.form.get('name_th', '').strip()
        code = request.form.get('code', '').strip() or None
        if not name_en or not name_th:
            flash('Both English and Thai names are required.', 'danger')
        else:
            mt = MemberType(name_en=name_en, name_th=name_th, member_type_code=code)
            db.session.add(mt)
            try:
                db.session.commit()
                flash('Member type added.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {e}', 'danger')
        return redirect(url_for('continuing_edu_admin.settings_member_types'))
    mtypes = MemberType.query.order_by(MemberType.name_en.asc()).all()
    return render_template('continueing_edu/admin/settings_member_types.html', logged_in_admin=staff, items=mtypes)


@admin_bp.route('/settings/member_types/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def settings_member_types_edit(item_id):
    staff = get_current_staff()
    mt = MemberType.query.get_or_404(item_id)
    if request.method == 'POST':
        mt.name_en = request.form.get('name_en', mt.name_en)
        mt.name_th = request.form.get('name_th', mt.name_th)
        code = request.form.get('code', '').strip() or None
        mt.member_type_code = code
        db.session.add(mt)
        try:
            db.session.commit()
            flash('Member type updated.', 'success')
            return redirect(url_for('continuing_edu_admin.settings_member_types'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')
    return render_template('continueing_edu/admin/settings_member_types_form.html', logged_in_admin=staff, item=mt)


@admin_bp.route('/settings/member_types/<int:item_id>/delete', methods=['POST'])
@login_required
@admin_required
def settings_member_types_delete(item_id):
    staff = get_current_staff()
    mt = MemberType.query.get_or_404(item_id)
    try:
        db.session.delete(mt)
        db.session.commit()
        flash('Member type deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete: {e}', 'danger')
    return redirect(url_for('continuing_edu_admin.settings_member_types'))


# -----------------------------
# General Settings: Registration Statuses
# -----------------------------
@admin_bp.route('/settings/registration_statuses', methods=['GET', 'POST'])
@login_required
@admin_required
def settings_registration_statuses():
    staff = get_current_staff()
    if request.method == 'POST':
        name_en = request.form.get('name_en', '').strip()
        name_th = request.form.get('name_th', '').strip()
        code = request.form.get('code', '').strip() or None
        css_badge = request.form.get('css_badge', '').strip() or None
        if not name_en or not name_th:
            flash('Both English and Thai names are required.', 'danger')
        else:
            st = RegistrationStatus(name_en=name_en, name_th=name_th, css_badge=css_badge,
                                    registration_status_code=code)
            db.session.add(st)
            try:
                db.session.commit()
                flash('Registration status added.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {e}', 'danger')
        return redirect(url_for('continuing_edu_admin.settings_registration_statuses'))
    items = RegistrationStatus.query.order_by(RegistrationStatus.name_en.asc()).all()
    return render_template('continueing_edu/admin/settings_registration_statuses.html', logged_in_admin=staff, items=items)


@admin_bp.route('/settings/registration_statuses/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def settings_registration_statuses_edit(item_id):
    staff = get_current_staff()
    st = RegistrationStatus.query.get_or_404(item_id)
    if request.method == 'POST':
        st.name_en = request.form.get('name_en', st.name_en)
        st.name_th = request.form.get('name_th', st.name_th)
        st.css_badge = request.form.get('css_badge', st.css_badge)
        st.registration_status_code = request.form.get('code', '').strip() or None
        db.session.add(st)
        try:
            db.session.commit()
            flash('Registration status updated.', 'success')
            return redirect(url_for('continuing_edu_admin.settings_registration_statuses'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')
    return render_template('continueing_edu/admin/settings_registration_statuses_form.html', logged_in_admin=staff, item=st)


@admin_bp.route('/settings/registration_statuses/<int:item_id>/delete', methods=['POST'])
@login_required
@admin_required
def settings_registration_statuses_delete(item_id):
    staff = get_current_staff()
    st = RegistrationStatus.query.get_or_404(item_id)
    try:
        db.session.delete(st)
        db.session.commit()
        flash('Registration status deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete: {e}', 'danger')
    return redirect(url_for('continuing_edu_admin.settings_registration_statuses'))


# -----------------------------
# General Settings: Payment Statuses
# -----------------------------
@admin_bp.route('/settings/payment_statuses', methods=['GET', 'POST'])
@login_required
@admin_required
def settings_payment_statuses():
    staff = get_current_staff()
    if request.method == 'POST':
        name_en = request.form.get('name_en', '').strip()
        name_th = request.form.get('name_th', '').strip()
        code = request.form.get('code', '').strip() or None
        css_badge = request.form.get('css_badge', '').strip() or None
        if not name_en or not name_th:
            flash('Both English and Thai names are required.', 'danger')
        else:
            st = RegisterPaymentStatus(name_en=name_en, name_th=name_th, css_badge=css_badge,
                                       register_payment_status_code=code)
            db.session.add(st)
            try:
                db.session.commit()
                flash('Payment status added.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {e}', 'danger')
        return redirect(url_for('continuing_edu_admin.settings_payment_statuses'))
    items = RegisterPaymentStatus.query.order_by(RegisterPaymentStatus.name_en.asc()).all()
    return render_template('continueing_edu/admin/settings_payment_statuses.html', logged_in_admin=staff, items=items)


@admin_bp.route('/settings/payment_statuses/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def settings_payment_statuses_edit(item_id):
    staff = get_current_staff()
    st = RegisterPaymentStatus.query.get_or_404(item_id)
    if request.method == 'POST':
        st.name_en = request.form.get('name_en', st.name_en)
        st.name_th = request.form.get('name_th', st.name_th)
        st.css_badge = request.form.get('css_badge', st.css_badge)
        st.register_payment_status_code = request.form.get('code', '').strip() or None
        db.session.add(st)
        try:
            db.session.commit()
            flash('Payment status updated.', 'success')
            return redirect(url_for('continuing_edu_admin.settings_payment_statuses'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')
    return render_template('continueing_edu/admin/settings_payment_statuses_form.html', logged_in_admin=staff, item=st)


@admin_bp.route('/settings/payment_statuses/<int:item_id>/delete', methods=['POST'])
@login_required
@admin_required
def settings_payment_statuses_delete(item_id):
    staff = get_current_staff()
    st = RegisterPaymentStatus.query.get_or_404(item_id)
    try:
        db.session.delete(st)
        db.session.commit()
        flash('Payment status deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete: {e}', 'danger')
    return redirect(url_for('continuing_edu_admin.settings_payment_statuses'))


# -----------------------------
# General Settings: Entity Categories
# -----------------------------
@admin_bp.route('/settings/entity_categories', methods=['GET', 'POST'])
@login_required
@admin_required
def settings_entity_categories():
    staff = get_current_staff()
    if request.method == 'POST':
        name_en = request.form.get('name_en', '').strip()
        name_th = request.form.get('name_th', '').strip()
        code = request.form.get('code', '').strip() or None
        description = request.form.get('description', '').strip()
        if not name_en or not name_th:
            flash('Both English and Thai names are required.', 'danger')
        else:
            cat = EntityCategory(name_en=name_en, name_th=name_th, description=description, entity_category_code=code)
            db.session.add(cat)
            try:
                db.session.commit()
                flash('Entity category added.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {e}', 'danger')
        return redirect(url_for('continuing_edu_admin.settings_entity_categories'))
    items = EntityCategory.query.order_by(EntityCategory.name_en.asc()).all()
    return render_template('continueing_edu/admin/settings_entity_categories.html', logged_in_admin=staff, items=items)


@admin_bp.route('/settings/entity_categories/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def settings_entity_categories_edit(item_id):
    staff = get_current_staff()
    cat = EntityCategory.query.get_or_404(item_id)
    if request.method == 'POST':
        cat.name_en = request.form.get('name_en', cat.name_en)
        cat.name_th = request.form.get('name_th', cat.name_th)
        cat.description = request.form.get('description', cat.description)
        cat.entity_category_code = request.form.get('code', '').strip() or None
        db.session.add(cat)
        try:
            db.session.commit()
            flash('Entity category updated.', 'success')
            return redirect(url_for('continuing_edu_admin.settings_entity_categories'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')
    return render_template('continueing_edu/admin/settings_entity_categories_form.html', logged_in_admin=staff, item=cat)


@admin_bp.route('/settings/entity_categories/<int:item_id>/delete', methods=['POST'])
@login_required
@admin_required
def settings_entity_categories_delete(item_id):
    staff = get_current_staff()
    cat = EntityCategory.query.get_or_404(item_id)
    try:
        db.session.delete(cat)
        db.session.commit()
        flash('Entity category deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete: {e}', 'danger')
    return redirect(url_for('continuing_edu_admin.settings_entity_categories'))


@admin_bp.route('/events/<int:event_id>/notify', methods=['GET','POST'])
@login_required
@admin_required
def event_notify(event_id):
    staff = get_current_staff()
    event = EventEntity.query.get_or_404(event_id)
    # Audience filters
    only_optin = (request.values.get('only_optin', '1') in ('1','true','yes','on'))
    only_verified = (request.values.get('only_verified', '1') in ('1','true','yes','on'))
    member_type_ids = request.values.getlist('member_type_id')
    # Build recipients query
    q = Member.query
    if only_optin:
        q = q.filter_by(received_news=True)
    if only_verified:
        q = q.filter_by(is_verified=True)
    if member_type_ids:
        try:
            ids = [int(i) for i in member_type_ids]
            q = q.filter(Member.member_type_id.in_(ids))
        except Exception:
            pass
    q = q.filter(Member.email.isnot(None))
    recipients = [m.email for m in q.all()]

    # Build event link
    try:
        if event.event_type == 'course':
            link = url_for('continuing_edu.course_detail', course_id=event.id, lang='en', _external=True)
        else:
            link = url_for('continuing_edu.webinar_detail', webinar_id=event.id, lang='en', _external=True)
    except Exception:
        link = ''

    subject_default = f"[CE] New Event: {event.title_en or event.title_th or 'Event'}"
    email_html_tpl = (
        "<div style=\"font-family:Arial,sans-serif;font-size:14px;color:#333;\">"
        "<h2 style=\"margin:0 0 8px 0;\">{{ event.title_en or event.title_th }}</h2>"
        "{% set img = event.cover_presigned_url() or event.poster_presigned_url() or event.image_url %}"
        "{% if img %}<div style=\"margin:10px 0;\"><img src=\"{{ img }}\" style=\"max-width:100%;height:auto;\"></div>{% endif %}"
        "{% if event.description_en %}<h3>About (EN)</h3><p>{{ event.description_en }}</p>{% endif %}"
        "{% if event.description_th %}<hr><h3>รายละเอียด (TH)</h3><p>{{ event.description_th }}</p>{% endif %}"
        "{% if link %}<p style=\"margin-top:16px;\"><a href=\"{{ link }}\" style=\"background:#4f46e5;color:#fff;padding:10px 16px;text-decoration:none;border-radius:4px;\">View / Register</a></p>{% endif %}"
        "<p style=\"color:#888;font-size:12px;margin-top:24px;\">You receive this because you opted in. Update preferences to unsubscribe.</p>"
        "</div>"
    )

    if request.method == 'GET':
        # Preview inline using a small template string to avoid filesystem writes
        from flask import render_template_string
        subject = request.values.get('subject', subject_default)
        recipients_count = len(recipients)
        if recipients_count == 0:
            flash('No recipients matched the selected filters.', 'warning')
            return redirect(url_for('continuing_edu_admin.manage_events'))
        html_preview = render_template_string(email_html_tpl, event=event, link=link)
        # Render a minimal preview page with filters
        page_tpl = (
            "{% extends 'continueing_edu/admin/base.html' %}{% block content %}"
            "<div class=container><h1 class=\"title is-3\">Notify Subscribers: {{ event.title_en or event.title_th }}</h1>"
            "<form method=GET class=\"box\">"
            "<div class=\"field\"><label class=label>Subject</label><input class=input name=subject value=\"{{ subject }}\"></div>"
            "<div class=\"field is-grouped\">"
            "<label class=\"checkbox\"><input type=checkbox name=only_optin {% if only_optin %}checked{% endif %}> Only opted-in</label>"
            "<label class=\"checkbox ml-4\"><input type=checkbox name=only_verified {% if only_verified %}checked{% endif %}> Only verified</label>"
            "</div>"
            "<div class=\"field\"><label class=label>Member Types</label><div class=select multiple><select multiple name=member_type_id>"
            "{% for mt in MemberType.query.order_by(MemberType.name_en.asc()).all() %}"
            "<option value=\"{{ mt.id }}\" {% if mt.id|string in member_type_ids %}selected{% endif %}>{{ mt.name_en }} / {{ mt.name_th }}</option>"
            "{% endfor %}"
            "</select></div></div>"
            "<div class=\"field is-grouped\"><div class=control>"
            "<button class=\"button is-link\" type=submit>Update Preview</button>"
            "</div>"
            "<div class=control><form method=POST><input type=hidden name=subject value=\"{{ subject }}\">"
            "{% for mtid in member_type_ids %}<input type=hidden name=member_type_id value=\"{{ mtid }}\">{% endfor %}"
            "<input type=hidden name=only_optin value=\"{{ 1 if only_optin else 0 }}\"><input type=hidden name=only_verified value=\"{{ 1 if only_verified else 0 }}\">"
            "<button class=\"button is-primary\" type=submit onclick=\"return confirm('Send to '+{{ recipients_count }}+' recipients?')\">Send Notification</button></form></div>"
            "<div class=control><a class=\"button\" href=\"{{ url_for('continuing_edu_admin.manage_events') }}\">Cancel</a></div></div>"
            "</form>"
            "<hr><h2 class=\"title is-5\">Preview ({{ recipients_count }} recipients)</h2><div class=box style=\"max-width:860px;\">{{ html_preview|safe }}</div></div>"
            "{% endblock %}"
        )
        return render_template_string(page_tpl, event=event, subject=subject, html_preview=html_preview,
                                      recipients_count=recipients_count, only_optin=only_optin, only_verified=only_verified,
                                      member_type_ids=member_type_ids, MemberType=MemberType)
    else:
        subject = request.form.get('subject') or subject_default
        if not recipients:
            flash('No recipients matched the selected filters.', 'warning')
            return redirect(url_for('continuing_edu_admin.manage_events'))
        from flask_mail import Message
        sent = 0
        chunk_size = 50
        from flask import render_template_string
        for i in range(0, len(recipients), chunk_size):
            chunk = recipients[i:i+chunk_size]
            try:
                html_body = render_template_string(email_html_tpl, event=event, link=link)
                msg = Message(subject=subject, recipients=chunk)
                msg.body = f"New event: {event.title_en or event.title_th}\n{link}"
                msg.html = html_body
                mail.send(msg)
                sent += len(chunk)
            except Exception as e:
                flash(f'Error sending to some recipients: {e}', 'danger')
                break
        flash(f'Notification sent to {sent} subscribers.', 'success')
        return redirect(url_for('continuing_edu_admin.manage_events'))


# -----------------------------
# Admin Payments Review
# -----------------------------
@admin_bp.route('/payments')
@login_required
@admin_required
def payments_index():
    staff = get_current_staff()
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = RegisterPayment.query
    if status:
        # Prefer code match, fallback to name_en for backward compatibility
        st = RegisterPaymentStatus.query.filter_by(register_payment_status_code=status).first()
        if not st:
            st = RegisterPaymentStatus.query.filter_by(name_en=status).first()
        if st:
            query = query.filter_by(payment_status_id=st.id)
    if q:
        like = f"%{q}%"
        query = query.join(Member, RegisterPayment.member).join(EventEntity, RegisterPayment.event_entity).filter(
            (Member.username.ilike(like)) | (Member.email.ilike(like)) | (EventEntity.title_en.ilike(like))
        )
    # Date range filter
    from datetime import datetime, timedelta
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(RegisterPayment.payment_date >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            query = query.filter(RegisterPayment.payment_date <= end_dt)
        except ValueError:
            pass

    pagination = query.order_by(RegisterPayment.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    payments = pagination.items
    statuses = RegisterPaymentStatus.query.order_by(RegisterPaymentStatus.name_en.asc()).all()
    # Totals summary
    total_amount = sum([p.payment_amount or 0 for p in payments])
    total_count = len(payments)
    status_counts = {}
    for p in payments:
        key = (p.payment_status_ref.name_en if p.payment_status_ref else 'N/A')
        status_counts[key] = status_counts.get(key, 0) + 1
    return render_template(
        'continueing_edu/admin/payments.html',
        payments=payments,
        statuses=statuses,
        current_status=status,
        q=q,
        start_date=start_date,
        end_date=end_date,
        pagination=pagination,
        per_page=per_page,
        total_amount=total_amount,
        total_count=total_count,
        status_counts=status_counts,
        logged_in_admin=staff,
    )


@admin_bp.route('/payments/<int:payment_id>/receipt')
@login_required
@admin_required
def payment_receipt(payment_id):
    staff = get_current_staff()
    pay = RegisterPayment.query.get_or_404(payment_id)
    rc = pay.receipt
    if not rc:
        flash('No receipt issued for this payment.', 'warning')
        return redirect(url_for('continuing_edu_admin.payments_index'))
    member = pay.member
    return render_template('continueing_edu/receipt.html', receipt=rc, payment=pay, member=member, texts={}, current_lang='en')


def _set_payment_status(pay: RegisterPayment, status_en: str, staff_id: int):
    # status_en now treated as code; fallback to name_en
    st = RegisterPaymentStatus.query.filter_by(register_payment_status_code=status_en).first()
    if not st:
        st = RegisterPaymentStatus.query.filter_by(name_en=status_en).first()
    from datetime import datetime
    if st:
        pay.payment_status_id = st.id
    pay.approved_by_staff_id = staff_id
    pay.approval_date = datetime.utcnow()
    db.session.add(pay)
    # Auto-issue receipt on approval
    if status_en == 'approved' and not pay.receipt:
        number = f"RCPT-{datetime.utcnow().strftime('%Y%m%d')}-{pay.id}"
        receipt = RegisterPaymentReceipt(register_payment_id=pay.id, receipt_number=number, issued_by_staff_id=staff_id)
        db.session.add(receipt)
    db.session.commit()


@admin_bp.route('/payments/<int:payment_id>/approve', methods=['POST'])
@login_required
@require_event_role('payment_approver')
def payment_approve(payment_id):
    staff = get_current_staff()
    pay = RegisterPayment.query.get_or_404(payment_id)
    _set_payment_status(pay, 'approved', staff.id)
    flash('Payment approved.', 'success')
    return redirect(url_for('continuing_edu_admin.payments_index'))


@admin_bp.route('/payments/<int:payment_id>/reject', methods=['POST'])
@login_required
@require_event_role('payment_approver')
def payment_reject(payment_id):
    staff = get_current_staff()
    pay = RegisterPayment.query.get_or_404(payment_id)
    _set_payment_status(pay, 'rejected', staff.id)
    flash('Payment rejected.', 'warning')
    return redirect(url_for('continuing_edu_admin.payments_index'))


@admin_bp.route('/payments/export')
@login_required
@admin_required
def payments_export_csv():
    staff = get_current_staff()
    from datetime import datetime, timedelta
    import csv
    from io import StringIO
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    query = RegisterPayment.query
    if status:
        st = RegisterPaymentStatus.query.filter_by(name_en=status).first()
        if st:
            query = query.filter_by(payment_status_id=st.id)
    if q:
        like = f"%{q}%"
        query = query.join(Member, RegisterPayment.member).join(EventEntity, RegisterPayment.event_entity).filter(
            (Member.username.ilike(like)) | (Member.email.ilike(like)) | (EventEntity.title_en.ilike(like))
        )
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(RegisterPayment.payment_date >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            query = query.filter(RegisterPayment.payment_date <= end_dt)
        except ValueError:
            pass
    rows = query.order_by(RegisterPayment.id.desc()).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Member','Email','Event','Amount','Status','Payment Date','Proof URL','Receipt Number'])
    for p in rows:
        writer.writerow([
            p.id,
            p.member.username if p.member else '',
            p.member.email if p.member else '',
            p.event_entity.title_en if p.event_entity else '',
            p.payment_amount or 0,
            p.payment_status_ref.name_en if p.payment_status_ref else '',
            p.payment_date,
            p.payment_proof_url or '',
            p.receipt.receipt_number if p.receipt else '',
        ])
    from flask import make_response
    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename="payments_export.csv"'
    return resp


@admin_bp.route('/bootstrap_defaults')
@login_required
@admin_required
def bootstrap_defaults():
    staff = get_current_staff()
    created = []
    # Seed RegisterPaymentStatus values
    for name_en, name_th, badge in [
        ('pending', 'รอดำเนินการ', 'is-light'),
        ('submitted', 'ส่งหลักฐานแล้ว', 'is-info'),
        ('approved', 'อนุมัติแล้ว', 'is-success'),
        ('rejected', 'ปฏิเสธ', 'is-danger'),
    ]:
        s = RegisterPaymentStatus.query.filter_by(name_en=name_en).first()
        if not s:
            s = RegisterPaymentStatus(name_en=name_en, name_th=name_th, css_badge=badge,
                                      register_payment_status_code=name_en)
            db.session.add(s)
            created.append(f'RegisterPaymentStatus:{name_en}')
        elif not s.register_payment_status_code:
            s.register_payment_status_code = name_en
            db.session.add(s)
    # Seed RegistrationStatus values
    for name_en, name_th, badge in [
        ('registered', 'ลงทะเบียนแล้ว', 'is-info'),
        ('in_progress', 'กำลังเรียน', 'is-warning'),
        ('completed', 'สำเร็จแล้ว', 'is-success'),
        ('cancelled', 'ยกเลิก', 'is-light'),
    ]:
        s = RegistrationStatus.query.filter_by(name_en=name_en).first()
        if not s:
            s = RegistrationStatus(name_en=name_en, name_th=name_th, css_badge=badge,
                                   registration_status_code=name_en)
            db.session.add(s)
            created.append(f'RegistrationStatus:{name_en}')
        elif not s.registration_status_code:
            s.registration_status_code = name_en
            db.session.add(s)
    # Seed MemberCertificateStatus values
    for name_en, name_th, badge in [
        ('issued', 'ออกแล้ว', 'is-success'),
        ('not_applicable', 'ไม่เกี่ยวข้อง', 'is-light'),
        ('pending', 'รอดำเนินการ', 'is-info'),
    ]:
        if not MemberCertificateStatus.query.filter_by(name_en=name_en).first():
            s = MemberCertificateStatus(name_en=name_en, name_th=name_th, css_badge=badge)
            db.session.add(s)
            created.append(f'MemberCertificateStatus:{name_en}')
    db.session.commit()
    flash('Bootstrapped defaults: ' + (', '.join(created) if created else 'nothing to add'), 'success')
    return redirect(url_for('continuing_edu_admin.dashboard'))


# -----------------------------
# General Info Tab Handlers
# -----------------------------
@admin_bp.route('/events/<int:event_id>/update_general', methods=['POST'])
@login_required
@admin_required
def update_event_general(event_id):
    staff = get_current_staff()
    event = EventEntity.query.get_or_404(event_id)

    # Basic fields; extend as needed
    title_en = request.form.get('title_en')
    if not title_en:
        flash('Title (EN) is required.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='general'))
    event.title_en = title_en
    event.title_th = request.form.get('title_th') or event.title_th
    event.description_en = request.form.get('description_en')
    event.description_th = request.form.get('description_th')
    event.location_en = request.form.get('location_en')
    event.location_th = request.form.get('location_th')
    event.duration_en = request.form.get('duration_en')
    event.duration_th = request.form.get('duration_th')
    event.format_en = request.form.get('format_en')
    event.format_th = request.form.get('format_th')
    # Handle image uploads (file upload only)
    poster_file = request.files.get('poster_image_file')
    cover_file = request.files.get('cover_image_file')
    delete_poster = request.form.get('delete_poster') == '1'
    delete_cover = request.form.get('delete_cover') == '1'

    import time
    from werkzeug.utils import secure_filename

    # Lazy import to avoid circular imports at module import time
    from app.main import allowed_file, s3, S3_BUCKET_NAME
    
    # Handle poster image
    old_poster = event.poster_image_url
    if poster_file and allowed_file(poster_file.filename):
        # Delete old poster if it exists in S3
        if old_poster and not old_poster.startswith('http'):
            try:
                s3.delete_object(Bucket=S3_BUCKET_NAME, Key=old_poster)
            except Exception as e:
                print(f"Warning: Could not delete old poster {old_poster}: {e}")
        
        # Upload new poster
        filename = secure_filename(poster_file.filename)
        ext = filename.rsplit('.', 1)[-1].lower()
        key = f"continuing_edu/events/{event.id}/poster_{int(time.time())}.{ext}"
        file_data = poster_file.read()
        content_type = poster_file.mimetype or 'application/octet-stream'
        s3.put_object(Bucket=S3_BUCKET_NAME, Key=key, Body=file_data, ContentType=content_type)
        event.poster_image_url = key
    elif delete_poster and old_poster:
        # User checked delete without uploading new file
        if not old_poster.startswith('http'):
            try:
                s3.delete_object(Bucket=S3_BUCKET_NAME, Key=old_poster)
            except Exception as e:
                print(f"Warning: Could not delete old poster {old_poster}: {e}")
        event.poster_image_url = None

    # Handle cover image
    old_cover = event.cover_image_url
    if cover_file and allowed_file(cover_file.filename):
        # Delete old cover if it exists in S3
        if old_cover and not old_cover.startswith('http'):
            try:
                s3.delete_object(Bucket=S3_BUCKET_NAME, Key=old_cover)
            except Exception as e:
                print(f"Warning: Could not delete old cover {old_cover}: {e}")
        
        # Upload new cover
        filename = secure_filename(cover_file.filename)
        ext = filename.rsplit('.', 1)[-1].lower()
        key = f"continuing_edu/events/{event.id}/cover_{int(time.time())}.{ext}"
        file_data = cover_file.read()
        content_type = cover_file.mimetype or 'application/octet-stream'
        s3.put_object(Bucket=S3_BUCKET_NAME, Key=key, Body=file_data, ContentType=content_type)
        event.cover_image_url = key
    elif delete_cover and old_cover:
        # User checked delete without uploading new file
        if not old_cover.startswith('http'):
            try:
                s3.delete_object(Bucket=S3_BUCKET_NAME, Key=old_cover)
            except Exception as e:
                print(f"Warning: Could not delete old cover {old_cover}: {e}")
        event.cover_image_url = None
    event.certificate_name_en = request.form.get('certificate_name_en')
    event.certificate_name_th = request.form.get('certificate_name_th')
    ce_val = request.form.get('continue_education_score')
    if ce_val is not None and ce_val != '':
        try:
            ce_num = float(ce_val)
            if ce_num < 0 or ce_num > 1000:
                raise ValueError('out_of_range')
            event.continue_education_score = ce_num
        except Exception:
            flash('CE Score must be a number between 0 and 1000.', 'danger')
            return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='general'))

    # Early bird period
    eb_start = request.form.get('early_bird_start')
    eb_end = request.form.get('early_bird_end')
    from_date = _parse_dt(eb_start) if eb_start else None
    to_date = _parse_dt(eb_end) if eb_end else None
    if from_date and to_date and to_date <= from_date:
        flash('Early bird end must be after start.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='general'))
    event.early_bird_start = from_date
    event.early_bird_end = to_date

    db.session.add(event)
    db.session.commit()
    flash('General information updated.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='general'))


# -----------------------------
# Speakers Tab Handlers
# -----------------------------
@admin_bp.route('/events/<int:event_id>/speakers/add', methods=['POST'])
@login_required
@admin_required
def add_event_speaker(event_id):
    staff = get_current_staff()
    event = EventEntity.query.get_or_404(event_id)

    required = ['title_en','title_th','name_th','name_en','email','phone','institution_th','institution_en']
    missing = [f for f in required if not (request.form.get(f) and request.form.get(f).strip())]
    if missing:
        flash('Missing required speaker fields: ' + ', '.join(missing), 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))

    sp = EventSpeaker(
        event_entity_id=event.id,
        title_en=request.form.get('title_en', ''),
        title_th=request.form.get('title_th', ''),
        name_th=request.form.get('name_th', ''),
        name_en=request.form.get('name_en', ''),
        email=request.form.get('email', ''),
        phone=request.form.get('phone', ''),
        position_th=request.form.get('position_th'),
        position_en=request.form.get('position_en'),
        institution_th=request.form.get('institution_th', ''),
        institution_en=request.form.get('institution_en', ''),
        image_url=request.form.get('image_url'),
        bio_th=request.form.get('bio_th'),
        bio_en=request.form.get('bio_en'),
    )
    db.session.add(sp)
    db.session.commit()
    flash('Speaker added.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='speakers'))


@admin_bp.route('/events/<int:event_id>/speakers/attach', methods=['POST'])
@login_required
@admin_required
def attach_existing_speaker(event_id):
    staff = get_current_staff()
    src_id = request.form.get('speaker_id')
    if not src_id:
        flash('Please select a speaker to attach.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))
    src = SpeakerProfile.query.get(src_id)
    if not src:
        flash('Speaker not found.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))

    # Prevent duplicate by email within the same event
    dup = EventSpeaker.query.filter_by(event_entity_id=event_id, email=src.email).first()
    if dup:
        flash('This speaker already exists for the event.', 'warning')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))

    new_sp = EventSpeaker(
        event_entity_id=event_id,
        title_en=src.title_en,
        title_th=src.title_th,
        name_th=src.name_th,
        name_en=src.name_en,
        email=src.email,
        phone=src.phone,
        position_th=src.position_th,
        position_en=src.position_en,
        institution_th=src.institution_th,
        institution_en=src.institution_en,
        image_url=src.image_url,
        bio_th=src.bio_th,
        bio_en=src.bio_en,
    )
    db.session.add(new_sp)
    db.session.commit()
    flash('Speaker attached to event.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))


# -----------------------------
# Admin SpeakerProfile Management
# -----------------------------
@admin_bp.route('/speakers')
@login_required
@admin_required
def speakers_index():
    staff = get_current_staff()
    q = request.args.get('q', '').strip()
    query = SpeakerProfile.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (SpeakerProfile.name_en.ilike(like)) |
            (SpeakerProfile.name_th.ilike(like)) |
            (SpeakerProfile.email.ilike(like)) |
            (SpeakerProfile.institution_en.ilike(like)) |
            (SpeakerProfile.institution_th.ilike(like))
        )
    profiles = query.order_by(SpeakerProfile.name_en.asc()).all()
    return render_template('continueing_edu/admin/speakers_list.html', profiles=profiles, q=q, logged_in_admin=staff)


@admin_bp.route('/speakers/<int:profile_id>')
@login_required
@admin_required
def speakers_view(profile_id):
    staff = get_current_staff()
    sp = SpeakerProfile.query.get_or_404(profile_id)
    return render_template('continueing_edu/admin/speakers_profile.html', profile=sp, logged_in_admin=staff)


@admin_bp.route('/speakers/new', methods=['GET', 'POST'])
@login_required
@admin_required
def speakers_new():
    staff = get_current_staff()
    if request.method == 'POST':
        required = ['title_en','title_th','name_en','name_th','email','institution_en','institution_th']
        missing = [f for f in required if not (request.form.get(f) and request.form.get(f).strip())]
        if missing:
            flash('Missing required fields: ' + ', '.join(missing), 'danger')
            return render_template('continueing_edu/admin/speakers_form.html', mode='new', data=request.form, logged_in_admin=staff)
        if SpeakerProfile.query.filter_by(email=request.form.get('email')).first():
            flash('Email already exists in speaker profiles.', 'danger')
            return render_template('continueing_edu/admin/speakers_form.html', mode='new', data=request.form, logged_in_admin=staff)

        sp = SpeakerProfile(
            title_en=request.form.get('title_en'),
            title_th=request.form.get('title_th'),
            name_en=request.form.get('name_en'),
            name_th=request.form.get('name_th'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            position_en=request.form.get('position_en'),
            position_th=request.form.get('position_th'),
            institution_en=request.form.get('institution_en'),
            institution_th=request.form.get('institution_th'),
            image_url=request.form.get('image_url'),
            bio_en=request.form.get('bio_en'),
            bio_th=request.form.get('bio_th'),
            is_active=True,
        )
        db.session.add(sp)
        db.session.commit()
        flash('Speaker profile created.', 'success')
        return redirect(url_for('continuing_edu_admin.speakers_index'))

    return render_template('continueing_edu/admin/speakers_form.html', mode='new', data=None, logged_in_admin=staff)


@admin_bp.route('/speakers/<int:profile_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def speakers_edit(profile_id):
    staff = get_current_staff()
    sp = SpeakerProfile.query.get_or_404(profile_id)
    if request.method == 'POST':
        # Basic validation
        email = request.form.get('email')
        if not email:
            flash('Email is required.', 'danger')
            return render_template('continueing_edu/admin/speakers_form.html', mode='edit', data=sp, logged_in_admin=staff)
        exists = SpeakerProfile.query.filter(SpeakerProfile.email == email, SpeakerProfile.id != sp.id).first()
        if exists:
            flash('Another profile already uses this email.', 'danger')
            return render_template('continueing_edu/admin/speakers_form.html', mode='edit', data=sp, logged_in_admin=staff)

        # Update fields
        for field in ['title_en','title_th','name_en','name_th','email','phone','position_en','position_th','institution_en','institution_th','image_url','bio_en','bio_th']:
            setattr(sp, field, request.form.get(field))
        sp.is_active = bool(request.form.get('is_active'))
        db.session.add(sp)
        db.session.commit()
        flash('Speaker profile updated.', 'success')
        return redirect(url_for('continuing_edu_admin.speakers_index'))

    return render_template('continueing_edu/admin/speakers_form.html', mode='edit', data=sp, logged_in_admin=staff)


@admin_bp.route('/speakers/<int:profile_id>/delete', methods=['POST'])
@login_required
@admin_required
def speakers_delete(profile_id):
    staff = get_current_staff()
    sp = SpeakerProfile.query.get_or_404(profile_id)
    db.session.delete(sp)
    db.session.commit()
    flash('Speaker profile deleted.', 'success')
    return redirect(url_for('continuing_edu_admin.speakers_index'))


@admin_bp.route('/events/<int:event_id>/speakers/<int:speaker_id>/update', methods=['POST'])
@login_required
@admin_required
def update_event_speaker(event_id, speaker_id):
    staff = get_current_staff()
    sp = EventSpeaker.query.filter_by(id=speaker_id, event_entity_id=event_id).first_or_404()
    for field in [
        'title_en','title_th','name_th','name_en','email','phone','position_th','position_en',
        'institution_th','institution_en','image_url','bio_th','bio_en']:
        if field in request.form:
            setattr(sp, field, request.form.get(field))
    db.session.add(sp)
    db.session.commit()
    flash('Speaker updated.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))


@admin_bp.route('/events/<int:event_id>/speakers/<int:speaker_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_event_speaker(event_id, speaker_id):
    staff = get_current_staff()
    sp = EventSpeaker.query.filter_by(id=speaker_id, event_entity_id=event_id).first_or_404()
    db.session.delete(sp)
    db.session.commit()
    flash('Speaker deleted.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))


# -----------------------------
# Agenda Tab Handlers
# -----------------------------
def _parse_dt(val):
    # Expect input type datetime-local: 'YYYY-MM-DDTHH:MM'
    if not val:
        return None
    try:
        return datetime.datetime.strptime(val, '%Y-%m-%dT%H:%M')
    except Exception:
        return None


@admin_bp.route('/events/<int:event_id>/agendas/add', methods=['POST'])
@login_required
@admin_required
def add_event_agenda(event_id):
    staff = get_current_staff()
    event = EventEntity.query.get_or_404(event_id)
    title_en = request.form.get('title_en', '')
    title_th = request.form.get('title_th', '')
    st = _parse_dt(request.form.get('start_time'))
    et = _parse_dt(request.form.get('end_time'))
    if not title_en or not title_th or not st or not et:
        flash('Agenda title and start/end time are required.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='agenda'))
    if et <= st:
        flash('Agenda end time must be after start time.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='agenda'))

    ag = EventAgenda(
        event_entity_id=event.id,
        title_th=title_th,
        title_en=title_en,
        description_th=request.form.get('description_th'),
        description_en=request.form.get('description_en'),
        start_time=st,
        end_time=et,
        order=int(request.form.get('order') or 0),
    )
    db.session.add(ag)
    db.session.commit()
    flash('Agenda item added.', 'success')
    if request.headers.get('HX-Request'):
        return _render_agenda_partial(event.id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='agenda'))


@admin_bp.route('/events/<int:event_id>/agendas/<int:agenda_id>/update', methods=['POST'])
@login_required
@admin_required
def update_event_agenda(event_id, agenda_id):
    staff = get_current_staff()
    ag = EventAgenda.query.filter_by(id=agenda_id, event_entity_id=event_id).first_or_404()
    ag.title_th = request.form.get('title_th', ag.title_th)
    ag.title_en = request.form.get('title_en', ag.title_en)
    ag.description_th = request.form.get('description_th')
    ag.description_en = request.form.get('description_en')
    st = _parse_dt(request.form.get('start_time'))
    et = _parse_dt(request.form.get('end_time'))
    # Validate only if provided
    if st and et and et <= st:
        flash('Agenda end time must be after start time.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='agenda'))
    if st:
        ag.start_time = st
    if et:
        ag.end_time = et
    ag.order = int(request.form.get('order') or ag.order or 0)
    db.session.add(ag)
    db.session.commit()
    flash('Agenda item updated.', 'success')
    if request.headers.get('HX-Request'):
        return _render_agenda_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='agenda'))


@admin_bp.route('/events/<int:event_id>/agendas/<int:agenda_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_event_agenda(event_id, agenda_id):
    staff = get_current_staff()
    ag = EventAgenda.query.filter_by(id=agenda_id, event_entity_id=event_id).first_or_404()
    db.session.delete(ag)
    db.session.commit()
    flash('Agenda item deleted.', 'success')
    if request.headers.get('HX-Request'):
        return _render_agenda_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='agenda'))


# -----------------------------
# Materials Tab Handlers
# -----------------------------
@admin_bp.route('/events/<int:event_id>/materials/add', methods=['POST'])
@login_required
@admin_required
def add_event_material(event_id):
    staff = get_current_staff()
    event = EventEntity.query.get_or_404(event_id)
    title_en = request.form.get('title_en')
    title_th = request.form.get('title_th')
    url = request.form.get('material_url')
    if not title_en or not title_th or not url:
        flash('Material title (EN/TH) and URL are required.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='materials'))
    mt = EventMaterial(
        event_entity_id=event.id,
        order=int(request.form.get('order') or 0),
        title_th=request.form.get('title_th', ''),
        title_en=request.form.get('title_en', ''),
        description_th=request.form.get('description_th'),
        description_en=request.form.get('description_en'),
        material_url=request.form.get('material_url', ''),
    )
    db.session.add(mt)
    db.session.commit()
    flash('Material added.', 'success')
    if request.headers.get('HX-Request'):
        return _render_materials_partial(event.id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='materials'))


@admin_bp.route('/events/<int:event_id>/materials/<int:material_id>/update', methods=['POST'])
@login_required
@admin_required
def update_event_material(event_id, material_id):
    staff = get_current_staff()
    mt = EventMaterial.query.filter_by(id=material_id, event_entity_id=event_id).first_or_404()
    mt.order = int(request.form.get('order') or mt.order or 0)
    mt.title_th = request.form.get('title_th', mt.title_th)
    mt.title_en = request.form.get('title_en', mt.title_en)
    mt.description_th = request.form.get('description_th')
    mt.description_en = request.form.get('description_en')
    mt.material_url = request.form.get('material_url', mt.material_url)
    db.session.add(mt)
    db.session.commit()
    flash('Material updated.', 'success')
    if request.headers.get('HX-Request'):
        return _render_materials_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='materials'))


@admin_bp.route('/events/<int:event_id>/materials/<int:material_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_event_material(event_id, material_id):
    staff = get_current_staff()
    mt = EventMaterial.query.filter_by(id=material_id, event_entity_id=event_id).first_or_404()
    db.session.delete(mt)
    db.session.commit()
    flash('Material deleted.', 'success')
    if request.headers.get('HX-Request'):
        return _render_materials_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='materials'))


# -----------------------------
# Registration Fees Tab Handlers
# -----------------------------
@admin_bp.route('/events/<int:event_id>/fees/add', methods=['POST'])
@login_required
@admin_required
def add_event_fee(event_id):
    staff = get_current_staff()
    event = EventEntity.query.get_or_404(event_id)
    member_type_id = request.form.get('member_type_id')
    price = request.form.get('price')
    if not member_type_id or not price:
        flash('Member type and price are required.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='fees'))
    try:
        price_val = float(price)
        if price_val < 0:
            raise ValueError('negative')
    except Exception:
        flash('Price must be a positive number.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='fees'))
    early = request.form.get('early_bird_price')
    early_val = None
    if early is not None and early != '':
        try:
            early_val = float(early)
            if early_val < 0:
                raise ValueError('negative')
        except Exception:
            flash('Early bird price must be a positive number.', 'danger')
            return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='fees'))
    fee = EventRegistrationFee(event_entity_id=event.id, member_type_id=int(member_type_id), price=price_val, early_bird_price=early_val)
    db.session.add(fee)
    try:
        db.session.commit()
        flash('Registration fee added.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding fee: {e}', 'danger')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='fees'))


# -----------------------------
# HTMX Partials and Ordering
# -----------------------------
def _render_agenda_partial(event_id):
    event = EventEntity.query.get_or_404(event_id)
    agendas = EventAgenda.query.filter_by(event_entity_id=event.id).order_by(EventAgenda.order.asc()).all()
    return render_template('continueing_edu/admin/_agenda_list.html', event=event, agendas=agendas)


def _render_materials_partial(event_id):
    event = EventEntity.query.get_or_404(event_id)
    materials = EventMaterial.query.filter_by(event_entity_id=event.id).order_by(EventMaterial.order.asc()).all()
    return render_template('continueing_edu/admin/_materials_list.html', event=event, materials=materials)


@admin_bp.route('/events/<int:event_id>/agendas/partial')
@login_required
@admin_required
def agendas_partial(event_id):
    return _render_agenda_partial(event_id)


@admin_bp.route('/events/<int:event_id>/materials/partial')
@login_required
@admin_required
def materials_partial(event_id):
    return _render_materials_partial(event_id)


def _swap_order(queryset, current, direction):
    # direction: 'up' or 'down'
    if direction == 'up':
        neighbor = next((x for x in reversed(queryset) if x.order < current.order), None)
    else:
        neighbor = next((x for x in queryset if x.order > current.order), None)
    if not neighbor:
        return False
    current.order, neighbor.order = neighbor.order, current.order
    db.session.add(current)
    db.session.add(neighbor)
    db.session.commit()
    return True


@admin_bp.route('/events/<int:event_id>/agendas/<int:agenda_id>/move', methods=['POST'])
@login_required
@admin_required
def move_agenda(event_id, agenda_id):
    direction = request.form.get('direction', 'up')
    agendas = EventAgenda.query.filter_by(event_entity_id=event_id).order_by(EventAgenda.order.asc()).all()
    ag = next((a for a in agendas if a.id == agenda_id), None)
    if ag:
        _swap_order(agendas, ag, direction)
    if request.headers.get('HX-Request'):
        return _render_agenda_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='agenda'))


@admin_bp.route('/events/<int:event_id>/materials/<int:material_id>/move', methods=['POST'])
@login_required
@admin_required
def move_material(event_id, material_id):
    direction = request.form.get('direction', 'up')
    materials = EventMaterial.query.filter_by(event_entity_id=event_id).order_by(EventMaterial.order.asc()).all()
    mt = next((m for m in materials if m.id == material_id), None)
    if mt:
        _swap_order(materials, mt, direction)
    if request.headers.get('HX-Request'):
        return _render_materials_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='materials'))


@admin_bp.route('/events/<int:event_id>/agendas/reorder', methods=['POST'])
@login_required
@admin_required
def reorder_agendas(event_id):
    order_ids = []
    if request.is_json:
        data = request.get_json(silent=True) or {}
        order_ids = data.get('order', [])
    else:
        # Accept order[]=id1&order[]=id2 ... or comma-separated 'order'
        order_ids = request.form.getlist('order[]') or request.form.get('order', '').split(',')
    try:
        order_ids = [int(i) for i in order_ids if str(i).strip()]
    except Exception:
        order_ids = []

    agendas = {a.id: a for a in EventAgenda.query.filter_by(event_entity_id=event_id).all()}
    order = 1
    for aid in order_ids:
        ag = agendas.get(aid)
        if ag:
            ag.order = order
            db.session.add(ag)
            order += 1
    db.session.commit()
    if request.headers.get('HX-Request'):
        return _render_agenda_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='agenda'))


@admin_bp.route('/events/<int:event_id>/materials/reorder', methods=['POST'])
@login_required
@admin_required
def reorder_materials(event_id):
    order_ids = []
    if request.is_json:
        data = request.get_json(silent=True) or {}
        order_ids = data.get('order', [])
    else:
        order_ids = request.form.getlist('order[]') or request.form.get('order', '').split(',')
    try:
        order_ids = [int(i) for i in order_ids if str(i).strip()]
    except Exception:
        order_ids = []

    materials = {m.id: m for m in EventMaterial.query.filter_by(event_entity_id=event_id).all()}
    order = 1
    for mid in order_ids:
        mt = materials.get(mid)
        if mt:
            mt.order = order
            db.session.add(mt)
            order += 1
    db.session.commit()
    if request.headers.get('HX-Request'):
        return _render_materials_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='materials'))


@admin_bp.route('/events/<int:event_id>/fees/<int:fee_id>/update', methods=['POST'])
@login_required
@admin_required
def update_event_fee(event_id, fee_id):
    staff = get_current_staff()
    fee = EventRegistrationFee.query.filter_by(id=fee_id, event_entity_id=event_id).first_or_404()
    if 'member_type_id' in request.form:
        fee.member_type_id = int(request.form.get('member_type_id'))
    if 'price' in request.form:
        fee.price = float(request.form.get('price'))
    if 'early_bird_price' in request.form:
        ebp = request.form.get('early_bird_price')
        fee.early_bird_price = float(ebp) if ebp not in (None, '') else None
    db.session.add(fee)
    db.session.commit()
    flash('Registration fee updated.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='fees'))


@admin_bp.route('/events/<int:event_id>/fees/<int:fee_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_event_fee(event_id, fee_id):
    staff = get_current_staff()
    fee = EventRegistrationFee.query.filter_by(id=fee_id, event_entity_id=event_id).first_or_404()
    db.session.delete(fee)
    db.session.commit()
    flash('Registration fee deleted.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='fees'))


# -----------------------------
# Staff Roles Tab Handlers
# -----------------------------
def _add_staff_role(model_cls, event_id, staff_id):
    exists = model_cls.query.filter_by(event_entity_id=event_id, staff_id=staff_id).first()
    if not exists:
        db.session.add(model_cls(event_entity_id=event_id, staff_id=staff_id))


def _is_certificate_manager(admin: StaffAccount, event_id: int) -> bool:
    allow_all = os.getenv('CE_ALLOW_ALL_ADMINS_CERT', '0').lower() in ('1', 'true', 'yes')
    if allow_all:
        return True
    managers = EventCertificateManager.query.filter_by(event_entity_id=event_id).all()
    if not managers:
        return True
    return any(m.staff_id == admin.id for m in managers)


def _remove_staff_role(model_cls, role_id, event_id):
    rec = model_cls.query.filter_by(id=role_id, event_entity_id=event_id).first_or_404()
    db.session.delete(rec)


@admin_bp.route('/events/<int:event_id>/roles/update', methods=['POST'])
@login_required
@admin_required
def update_event_roles(event_id):
    staff = get_current_staff()

    # Add roles from selects (single add per submit)
    to_add_type = request.form.get('role_type')
    staff_id = request.form.get('staff_id')
    if to_add_type and staff_id:
        staff_id = int(staff_id)
        if to_add_type == 'editor':
            _add_staff_role(EventEditor, event_id, staff_id)
        elif to_add_type == 'registration_reviewer':
            _add_staff_role(EventRegistrationReviewer, event_id, staff_id)
        elif to_add_type == 'payment_approver':
            _add_staff_role(EventPaymentApprover, event_id, staff_id)
        elif to_add_type == 'receipt_issuer':
            _add_staff_role(EventReceiptIssuer, event_id, staff_id)
        elif to_add_type == 'certificate_manager':
            _add_staff_role(EventCertificateManager, event_id, staff_id)
        db.session.commit()
        flash('Role assignment updated.', 'success')

    # Handle removals (if present)
    for key, val in request.form.items():
        if key.startswith('remove_role_'):
            parts = val.split(':')  # e.g., 'editor:5'
            if len(parts) == 2:
                role_name, rid = parts[0], int(parts[1])
                if role_name == 'editor':
                    _remove_staff_role(EventEditor, rid, event_id)
                elif role_name == 'registration_reviewer':
                    _remove_staff_role(EventRegistrationReviewer, rid, event_id)
                elif role_name == 'payment_approver':
                    _remove_staff_role(EventPaymentApprover, rid, event_id)
                elif role_name == 'receipt_issuer':
                    _remove_staff_role(EventReceiptIssuer, rid, event_id)
                elif role_name == 'certificate_manager':
                    _remove_staff_role(EventCertificateManager, rid, event_id)
    db.session.commit()
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='roles'))


@admin_bp.route('/events/<int:event_id>/registrations/<int:reg_id>/update', methods=['POST'])
@login_required
@require_event_role('certificate_manager')
def update_registration_certificate(event_id, reg_id):
    staff = get_current_staff()

    reg = MemberRegistration.query.filter_by(id=reg_id, event_entity_id=event_id).first_or_404()
    action = request.form.get('action')
    lang = request.args.get('lang', 'en')
    message = None

    if action == 'mark_started':
        if not reg.started_at:
            reg.started_at = datetime.datetime.now(datetime.timezone.utc)
        status = get_registration_status('in_progress', 'in_progress', 'กำลังเรียน', 'is-info')
        reg.status_id = status.id
        message = 'Marked as started.'

    elif action == 'mark_completed':
        if not reg.completed_at:
            reg.completed_at = datetime.datetime.now(datetime.timezone.utc)
        status = get_registration_status('completed', 'completed', 'สำเร็จแล้ว', 'is-success')
        reg.status_id = status.id
        reg.assessment_passed = request.form.get('passed') in ('1', 'true', 'on', 'yes')
        pending_status = get_certificate_status('pending', 'รอดำเนินการ', 'is-info')
        reg.certificate_status_id = pending_status.id
        message = 'Marked as completed.'

    elif action == 'set_assessment':
        reg.assessment_passed = request.form.get('passed') in ('1', 'true', 'on', 'yes')
        message = 'Assessment flag updated.'

    elif action == 'update_statuses':
        reg_status_id = request.form.get('registration_status_id')
        cert_status_id = request.form.get('certificate_status_id')
        if reg_status_id:
            reg.status_id = int(reg_status_id)
        if cert_status_id:
            reg.certificate_status_id = int(cert_status_id)
        message = 'Statuses updated.'

    elif action == 'reset_certificate':
        reset_certificate_util(reg)
        flash('Certificate reset to pending.', 'info')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='certificates'))

    elif action == 'issue_certificate':
        force = request.form.get('force') in ('1', 'true', 'on', 'yes')
        if not can_issue_certificate(reg) and not force:
            flash('Cannot issue certificate: ensure completion, assessment passed, and payment approved (or use force).', 'warning')
            return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='certificates'))
        if not reg.completed_at:
            reg.completed_at = datetime.datetime.now(datetime.timezone.utc)
        status = get_registration_status('completed', 'completed', 'สำเร็จแล้ว', 'is-success')
        reg.status_id = status.id
        reg.assessment_passed = True
        issue_certificate_util(reg, lang=lang, base_url=request.url_root)
        flash('Certificate issued.', 'success')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='certificates'))

    if action not in ('reset_certificate', 'issue_certificate'):
        db.session.add(reg)
        db.session.commit()
        if message:
            flash(message, 'success')

    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='certificates'))
