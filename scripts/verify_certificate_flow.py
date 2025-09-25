"""Utility script to verify the certificate workflow for Continuing Education events.

Usage:
    python scripts/verify_certificate_flow.py [--event EVENT_ID]

This script requires the FLASK app context. Ensure relevant environment variables are set.
"""

import argparse
from datetime import datetime, timezone
from typing import Optional

from flask import current_app

from app.main import app, db
from app.continuing_edu.models import (
    EventEntity,
    EventCertificateManager,
    MemberRegistration,
    RegisterPayment,
    RegisterPaymentStatus,
)
from app.continuing_edu.status_utils import get_registration_status, get_certificate_status
from app.continuing_edu.certificate_utils import issue_certificate, can_issue_certificate, reset_certificate


def _ensure_certificate_manager(event: EventEntity) -> None:
    if EventCertificateManager.query.filter_by(event_entity_id=event.id).count() == 0:
        staff = event.staff or event.staff_id and event.staff
        if staff:
            db.session.add(EventCertificateManager(event_entity_id=event.id, staff_id=staff.id))
            db.session.commit()
            current_app.logger.info("Assigned %s as certificate manager", staff.email)


def _ensure_payment_approved(member_id: int, event_id: int) -> None:
    pending = RegisterPaymentStatus.query.filter((RegisterPaymentStatus.register_payment_status_code == 'approved') |
                                                 (RegisterPaymentStatus.name_en == 'approved')).first()
    pay = RegisterPayment.query.filter_by(member_id=member_id, event_entity_id=event_id).first()
    if not pay:
        pay = RegisterPayment(member_id=member_id,
                              event_entity_id=event_id,
                              payment_amount=0,
                              payment_status_id=pending.id if pending else None)
    else:
        if pending:
            pay.payment_status_id = pending.id
    db.session.add(pay)
    db.session.commit()


def verify_workflow(event_id: Optional[int] = None) -> None:
    event = EventEntity.query.filter_by(event_type='course').first() if event_id is None else EventEntity.query.get(event_id)
    if not event:
        current_app.logger.error('No event found to test with.')
        return

    current_app.logger.info('Using event %s (#%s)', event.title_en, event.id)
    _ensure_certificate_manager(event)

    reg = (MemberRegistration.query
           .filter_by(event_entity_id=event.id)
           .order_by(MemberRegistration.registration_date.asc())
           .first())
    if not reg:
        current_app.logger.error('No registrations for event %s', event.id)
        return

    current_app.logger.info('Using registration #%s for member %s', reg.id, reg.member.username)

    reg.status_id = get_registration_status('in_progress', 'in_progress', 'กำลังเรียน', 'is-info').id
    reg.started_at = reg.started_at or datetime.now(timezone.utc)
    reg.completed_at = datetime.now(timezone.utc)
    reg.assessment_passed = True
    reg.certificate_status_id = get_certificate_status('pending', 'รอดำเนินการ', 'is-info').id
    db.session.add(reg)
    db.session.commit()

    _ensure_payment_approved(reg.member_id, event.id)

    if can_issue_certificate(reg):
        issue_certificate(reg, lang='en')
        current_app.logger.info('Certificate issued successfully. URL: %s', reg.certificate_url)
    else:
        current_app.logger.warning('Certificate could not be issued automatically. Payment or assessment missing.')

    # Demonstrate reset
    reset_certificate(reg)
    current_app.logger.info('Certificate reset complete.')


+def main():
+    parser = argparse.ArgumentParser(description='Verify CE certificate workflow')
+    parser.add_argument('--event', type=int, help='Event ID to test with (defaults to first course)')
+    args = parser.parse_args()
+    with app.app_context():
+        verify_workflow(args.event)
+
+
+if __name__ == '__main__':
+    main()
