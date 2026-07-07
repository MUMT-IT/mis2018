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

try:
    from weasyprint import HTML  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    HTML = None

DEFAULT_POST_COURSE_SURVEY_URL = (
    "https://docs.google.com/forms/d/1dAFAicg5V1ZPXFUOyeyyASusxM89BxUyr3Aa6pPZpXI/viewform"
)


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


def build_satisfaction_form_name(event, lang: str = 'en') -> str:
    title = (
        (event.title_th if lang == 'th' and getattr(event, 'title_th', None) else None)
        or getattr(event, 'title_en', None)
        or getattr(event, 'title_th', None)
        or f"Event #{getattr(event, 'id', '-')}"
    )
    prefix = 'แบบประเมินความพึงพอใจ' if lang == 'th' else 'Satisfaction Survey'
    return f"{prefix}: {title}"


def get_post_course_survey_url(event=None) -> Optional[str]:
    """Resolve post-course survey URL from event override or environment."""
    event_url = getattr(event, 'post_course_survey_url', None) if event else None
    value = (event_url or os.getenv('CE_POST_COURSE_SURVEY_URL') or DEFAULT_POST_COURSE_SURVEY_URL or '').strip()
    return value or None


def requires_post_course_survey(reg: CEMemberRegistration) -> bool:
    enabled = os.getenv('CE_REQUIRE_SATISFACTION_SURVEY', '1').lower() in ('1', 'true', 'yes', 'on')
    if not enabled:
        return False
    event = reg.event_entity
    if not event:
        return False
    return getattr(event, 'event_type', None) in ('course', 'webinar')


def can_issue_certificate(reg: CEMemberRegistration) -> bool:
    """Check if a certificate can be issued (completed, assessment passed, survey done, payment approved)."""
    if not reg.completed_at or not reg.assessment_passed:
        return False
    if requires_post_course_survey(reg) and not reg.questionnaire_completed_at:
        return False
    payment = reg.member.payments
    for pay in payment:
        if pay.event_entity_id != reg.event_entity_id or not pay.payment_status_ref:
            continue
        code = (pay.payment_status_ref.register_payment_status_code or '').strip().lower()
        name = (pay.payment_status_ref.name_en or '').strip().lower()
        if code in ('approved', 'paid') or name in ('approved', 'paid'):
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
