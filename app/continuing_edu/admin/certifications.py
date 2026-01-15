from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.main import db
from app.staff.models import StaffAccount
from ..models import (
    EventEntity,
    EventCertificateManager,
    MemberRegistration,
    RegisterPayment,
    RegisterPaymentStatus,
    RegistrationStatus,
    MemberCertificateStatus,
)
from ..certificate_utils import issue_certificate as issue_certificate_util, reset_certificate as reset_certificate_util, can_issue_certificate
from ..status_utils import get_registration_status, get_certificate_status


cert_bp = Blueprint('continuing_edu_admin_certificates', __name__, url_prefix='/continuing_edu/admin/certificates')


def _get_admin():
    from ..admin.views import get_current_admin  # avoid circular import
    return get_current_admin()


def _ensure_manager(admin: StaffAccount, event_id: int) -> bool:
    allow_all = request.args.get('all', '').lower() in ('1', 'true')
    if allow_all:
        return True
    managers = EventCertificateManager.query.filter_by(event_entity_id=event_id).all()
    if not managers:
        return True
    return any(m.staff_id == admin.id for m in managers)


@cert_bp.route('/')
def index():
    admin = _get_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    events = EventEntity.query.order_by(EventEntity.created_at.desc()).all()
    return render_template('continueing_edu/admin/certificates_index.html', events=events, logged_in_admin=admin)


@cert_bp.route('/event/<int:event_id>')
def event(event_id):
    admin = _get_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    event = EventEntity.query.get_or_404(event_id)
    if not _ensure_manager(admin, event_id):
        flash('You do not have access to manage certificates for this event.', 'danger')
        return redirect(url_for('.index'))
    registrations = MemberRegistration.query.filter_by(event_entity_id=event.id).order_by(MemberRegistration.registration_date.asc()).all()
    payments_map = {}
    member_ids = [r.member_id for r in registrations]
    if member_ids:
        payments = (RegisterPayment.query
                    .filter(RegisterPayment.event_entity_id == event.id,
                            RegisterPayment.member_id.in_(member_ids))
                    .order_by(RegisterPayment.id.desc())
                    .all())
        for pay in payments:
            if pay.member_id not in payments_map:
                payments_map[pay.member_id] = pay
    registration_statuses = RegistrationStatus.query.order_by(RegistrationStatus.name_en.asc()).all()
    certificate_statuses = MemberCertificateStatus.query.order_by(MemberCertificateStatus.name_en.asc()).all()
    return render_template(
        'continueing_edu/admin/certificates_event.html',
        event=event,
        registrations=registrations,
        payments_map=payments_map,
        registration_statuses=registration_statuses,
        certificate_statuses=certificate_statuses,
        logged_in_admin=admin,
        can_issue_certificate=can_issue_certificate,
    )


@cert_bp.route('/event/<int:event_id>/registrations/<int:reg_id>/update', methods=['POST'])
def update_registration(event_id, reg_id):
    admin = _get_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    if not _ensure_manager(admin, event_id):
        flash('You do not have access to manage certificates for this event.', 'danger')
        return redirect(url_for('.event', event_id=event_id))
    reg = MemberRegistration.query.filter_by(id=reg_id, event_entity_id=event_id).first_or_404()
    action = request.form.get('action')
    if action == 'issue_certificate':
        force = request.form.get('force') in ('1', 'true', 'on', 'yes')
        if not can_issue_certificate(reg) and not force:
            flash('Cannot issue certificate yet.', 'warning')
            return redirect(url_for('.event', event_id=event_id))
        reg.completed_at = reg.completed_at or reg.started_at or reg.registration_date
        reg.status_id = get_registration_status('completed', 'completed', 'สำเร็จแล้ว', 'is-success').id
        reg.assessment_passed = True
        issue_certificate_util(reg, lang=request.args.get('lang', 'en'), base_url=request.url_root)
        flash('Certificate issued.', 'success')
    elif action == 'reset_certificate':
        reset_certificate_util(reg)
        flash('Certificate reset.', 'info')
    elif action == 'update_statuses':
        reg_status_id = request.form.get('registration_status_id')
        cert_status_id = request.form.get('certificate_status_id')
        if reg_status_id:
            reg.status_id = int(reg_status_id)
        if cert_status_id:
            reg.certificate_status_id = int(cert_status_id)
        db.session.add(reg)
        db.session.commit()
        flash('Statuses updated.', 'success')
    return redirect(url_for('.event', event_id=event_id))
