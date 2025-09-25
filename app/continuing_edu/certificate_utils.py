from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Optional

from flask import render_template

from .models import (
    db,
    MemberRegistration,
    MemberCertificateStatus,
)
from .status_utils import get_certificate_status

try:
    from weasyprint import HTML  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    HTML = None


def ensure_certificate_status(name_en: str, name_th: Optional[str] = None, css_badge: Optional[str] = None) -> MemberCertificateStatus:
    return get_certificate_status(name_en=name_en, name_th=name_th, css_badge=css_badge)


def can_issue_certificate(reg: MemberRegistration) -> bool:
    """Check if a certificate can be issued (completed, assessment passed, payment approved)."""
    if not reg.completed_at or not reg.assessment_passed:
        return False
    payment = reg.member.payments
    for pay in payment:
        if pay.event_entity_id == reg.event_entity_id and pay.payment_status_ref and (
            pay.payment_status_ref.register_payment_status_code == 'approved' or pay.payment_status_ref.name_en == 'approved'
        ):
            return True
    return False


def issue_certificate(reg: MemberRegistration, lang: str = 'en', base_url: Optional[str] = None) -> MemberRegistration:
    """Issue a certificate for the given registration."""
    issued = ensure_certificate_status('issued', 'ออกแล้ว', 'is-success')
    reg.certificate_status_id = issued.id
    reg.certificate_issued_date = datetime.now(timezone.utc)

    if HTML is not None:
        event = reg.event_entity
        member = reg.member
        html = render_template(
            'continueing_edu/certificate_pdf.html',
            reg=reg,
            event=event,
            member=member,
            current_lang=lang,
        )
        pdf_bytes = HTML(string=html, base_url=base_url).write_pdf()
        fname = f"cert_{reg.member_id}_{reg.event_entity_id}_{int(time.time())}.pdf"
        storage = os.getenv('CE_CERT_STORAGE', 'disk').lower()
        _delete_certificate_file(reg)
        if storage == 's3' and os.getenv('BUCKETEER_BUCKET_NAME'):
            try:
                from app.main import s3, S3_BUCKET_NAME
                key = f"continuing_edu/certificates/{fname}"
                s3.put_object(Bucket=S3_BUCKET_NAME, Key=key, Body=pdf_bytes, ContentType='application/pdf')
                reg.certificate_url = key
            except Exception:
                storage = 'disk'
        if storage != 's3':
            os.makedirs(os.path.join('static', 'certificates'), exist_ok=True)
            path = os.path.join('static', 'certificates', fname)
            with open(path, 'wb') as f:
                f.write(pdf_bytes)
            reg.certificate_url = '/' + path

    db.session.add(reg)
    db.session.commit()
    return reg


def reset_certificate(reg: MemberRegistration) -> None:
    """Reset certificate data back to pending state."""
    pending = ensure_certificate_status('pending', 'รอดำเนินการ', 'is-info')
    reg.certificate_status_id = pending.id
    reg.certificate_issued_date = None
    _delete_certificate_file(reg)
    reg.certificate_url = None
    db.session.add(reg)
    db.session.commit()


def _delete_certificate_file(reg: MemberRegistration) -> None:
    value = reg.certificate_url
    if not value:
        return
    storage = os.getenv('CE_CERT_STORAGE', 'disk').lower()
    try:
        if storage == 's3' and not _is_http(value):
            from app.main import s3, S3_BUCKET_NAME
            s3.delete_object(Bucket=S3_BUCKET_NAME, Key=value)
        else:
            path = value.lstrip('/') if value.startswith('/') else value
            if os.path.exists(path):
                os.remove(path)
    except Exception:
        pass


def _is_http(value: str) -> bool:
    return value.startswith('http://') or value.startswith('https://') or value.startswith('//')
