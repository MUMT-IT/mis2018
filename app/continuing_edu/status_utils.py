from __future__ import annotations

from typing import Optional

from .models import db, CERegistrationStatus, CEMemberCertificateStatus


def get_registration_status(code: str, name_en: str, name_th: str, css_badge: Optional[str] = None) -> CERegistrationStatus:
    """Fetch (or create) a registration status by code or English name."""
    query = CERegistrationStatus.query
    if code:
        query = query.filter((CERegistrationStatus.registration_status_code == code))
    else:
        query = query.filter(CERegistrationStatus.name_en == name_en)
    status = query.first()
    if status:
        return status
    status = CERegistrationStatus(
        name_en=name_en,
        name_th=name_th,
        registration_status_code=code,
        css_badge=css_badge
    )
    db.session.add(status)
    db.session.commit()
    return status


def get_certificate_status(name_en: str, name_th: Optional[str] = None, css_badge: Optional[str] = None) -> CEMemberCertificateStatus:
    """Fetch (or create) a member certificate status by English name."""
    status = CEMemberCertificateStatus.query.filter_by(name_en=name_en).first()
    if status:
        return status
    status = CEMemberCertificateStatus(
        name_en=name_en,
        name_th=name_th or name_en,
        css_badge=css_badge
    )
    db.session.add(status)
    db.session.commit()
    return status

