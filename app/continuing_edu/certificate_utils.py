import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from flask import current_app

from .models import (
    db,
    CEMemberRegistration,
    CEMemberCertificateStatus,
)
from .status_utils import get_certificate_status


def _resolve_static_base(base_url: Optional[str]) -> str:
    """Resolve an absolute path for static assets in certificate templates."""
    try:
        static_url_path = (current_app.static_url_path or '/static').lstrip('/')
        static_folder = current_app.static_folder
    except RuntimeError:
        static_url_path = 'static'
        static_folder = os.path.join(os.getcwd(), 'app', 'static')

    if base_url:
        normalized = base_url if base_url.endswith('/') else base_url + '/'
        if normalized.startswith(('http://', 'https://', 'file://')):
            return urljoin(normalized, f"{static_url_path.rstrip('/')}/")
    if static_folder:
        return Path(static_folder).resolve().as_uri().rstrip('/') + '/'
    return '/static/'


def build_certificate_context(reg: CEMemberRegistration, lang: str = 'en', base_url: Optional[str] = None) -> dict:
    """Prepare template context for certificate rendering with absolute static asset paths."""
    return {
        'reg': reg,
        'event': reg.event_entity,
        'member': reg.member,
        'current_lang': lang,
        'certificate_static_base': _resolve_static_base(base_url),
    }


def ensure_certificate_status(name_en: str, name_th: Optional[str] = None, css_badge: Optional[str] = None) -> CEMemberCertificateStatus:
    return get_certificate_status(name_en=name_en, name_th=name_th, css_badge=css_badge)


def can_issue_certificate(reg: CEMemberRegistration) -> bool:
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


def issue_certificate(reg: CEMemberRegistration, lang: str = 'en', base_url: Optional[str] = None) -> CEMemberRegistration:
    """Mark a certificate as issued.

    The application now renders certificate HTML directly instead of generating PDFs.
    """
    issued = ensure_certificate_status('issued', 'ออกแล้ว', 'is-success')
    reg.certificate_status_id = issued.id
    reg.certificate_issued_date = datetime.now(timezone.utc)

    db.session.add(reg)
    db.session.commit()
    return reg


def reset_certificate(reg: CEMemberRegistration) -> None:
    """Reset certificate data back to pending state."""
    pending = ensure_certificate_status('pending', 'รอดำเนินการ', 'is-info')
    reg.certificate_status_id = pending.id
    reg.certificate_issued_date = None
    _delete_certificate_file(reg)
    reg.certificate_url = None
    db.session.add(reg)
    db.session.commit()


def _delete_certificate_file(reg: CEMemberRegistration) -> None:
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
