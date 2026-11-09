"""Initial routes for the International Relations integration."""

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, logout_user
from flask_principal import AnonymousIdentity, identity_changed
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from . import bp
from app.main import db
from .models import InternalRelationParticipant
from .permissions import (
    international_relations_admin_required,
    participant_required,
)


@bp.get('/login')
def login():
    if isinstance(
        current_user._get_current_object(),
        InternalRelationParticipant,
    ) and current_user.is_authenticated:
        return redirect(url_for('international_relations.dashboard'))
    return render_template('international_relations/login.html')


@bp.get('/google/login')
def google_login():
    return redirect(url_for(
        'auth.google_login',
        mode='international_relations',
        next=url_for('international_relations.dashboard'),
    ))


@bp.get('/admin/login')
def admin_login():
    """Send staff administrators through the host authentication flow."""
    return redirect(url_for(
        'auth.login',
        next=url_for('international_relations.admin_dashboard'),
    ))


@bp.get('/logout')
@participant_required
def logout():
    logout_user()
    session.pop('user_type', None)
    identity_changed.send(
        current_app._get_current_object(),
        identity=AnonymousIdentity(),
    )
    flash('You have been signed out.', 'success')
    return redirect(url_for('international_relations.login'))


@bp.get('/')
@bp.get('/dashboard')
@participant_required
def dashboard():
    return render_template('international_relations/dashboard.html')


@bp.post('/profile')
@participant_required
def update_profile():
    participant = current_user._get_current_object()
    field_limits = {
        'preferred_name': 100,
        'phone': 50,
        'nationality': 100,
        'home_institution': 255,
        'department': 255,
        'research_topic': 2000,
        'emergency_contact_name': 200,
        'emergency_contact_phone': 50,
    }
    values = {}
    for field, limit in field_limits.items():
        value = (request.form.get(field) or '').strip()
        if len(value) > limit:
            flash(f'{field.replace("_", " ").title()} is too long.', 'danger')
            return redirect(url_for('international_relations.dashboard', _anchor='profile'))
        values[field] = value or None

    for field, value in values.items():
        setattr(participant, field, value)
    db.session.commit()
    flash('Your participant profile has been updated.', 'success')
    return redirect(url_for('international_relations.dashboard', _anchor='profile'))


@bp.get('/admin')
@international_relations_admin_required
def admin_dashboard():
    migration_required = False
    try:
        participants = InternalRelationParticipant.query.order_by(
            InternalRelationParticipant.last_login_at.desc().nullslast(),
            InternalRelationParticipant.created_at.desc(),
        ).all()
    except SQLAlchemyError:
        current_app.logger.exception(
            'Unable to load International Relations participants. '
            'The module migration may not have been applied.'
        )
        db.session.rollback()
        participants = []
        migration_required = True

    active_count = sum(participant.is_active for participant in participants)
    profile_count = sum(
        bool(participant.first_name and participant.last_name)
        for participant in participants
    )
    return render_template(
        'international_relations/admin/dashboard.html',
        participants=participants,
        migration_required=migration_required,
        summary={
            'total': len(participants),
            'active': active_count,
            'inactive': len(participants) - active_count,
            'complete_profiles': profile_count,
        },
    )


@bp.post('/admin/participants/<int:participant_id>/status')
@international_relations_admin_required
def admin_participant_status(participant_id):
    participant = InternalRelationParticipant.query.get_or_404(participant_id)
    action = (request.form.get('action') or '').strip().lower()
    if action not in {'activate', 'deactivate'}:
        flash('Invalid participant status action.', 'danger')
        return redirect(url_for('international_relations.admin_dashboard'))

    participant.is_active_account = action == 'activate'
    db.session.commit()
    flash(
        f'{participant.email} has been {"activated" if participant.is_active else "deactivated"}.',
        'success',
    )
    return redirect(url_for('international_relations.admin_dashboard'))
