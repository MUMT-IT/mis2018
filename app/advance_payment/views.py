import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy import extract
from sqlalchemy.exc import IntegrityError
from functools import wraps
import re
from types import SimpleNamespace
from flask import (
    after_this_request,
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template as _render_template,
    request,
    session,
    send_file,
    url_for,
)
from flask_login import current_user, login_required as flask_login_required
from app.roles import (
    cash_management_coordinator_permission,
    finance_permission,
    secretary_permission,
)
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from .borrowing_ticket_eligibility import calculate_borrowing_ticket_eligibility
from .forms import BorrowingTicketForm, FundRequestForm, BankAccountInfoForm
from .models import db, BankAccountInfo, BorrowingTicket, Document, ParcelReturnDetail, PettyCashClaimDetail, PettyCashClaimItem, PettyCashClaimProofFile, ReturnDetail, ReturnReceiptItem, ReturnProofFile, StaffAccount, ClosingDocument, PettyCashSetting, FundRequest, FundRequestItem, document_petty_claim_association, document_return_association
from .email_utils import generate_notification_email_content
from . import advance_payment as bp, thai_date
from app.models import CostCenter, IOCode, Org, ProductCode
from app.staff.models import StaffHeadPosition, StaffPersonalInfo
from app.staff.views import get_all_employees
from app.docs_query.models import DocsQueryDocument, DocsQueryTag


def _upload_root():
    return current_app.config.get(
        "UPLOAD_FOLDER",
        os.path.join(current_app.root_path, "static", "uploads"),
    )


def render_template(template_name, *args, **kwargs):
    """Render AdvancePayment templates without changing every route call."""
    if isinstance(template_name, str) and "/" not in template_name:
        template_name = f"advance_payment/{template_name}"
    kwargs.setdefault("advance_payment_user", current_user)
    kwargs.setdefault("advance_payment_role", _current_module_role())
    return _render_template(template_name, *args, **kwargs)


def _validation_error_response(message, status_code=422):
    """Return a non-navigating validation response for AJAX form submissions."""
    return jsonify(ok=False, message=message), status_code


def _validation_redirect_response(message, location=None):
    """Return validation errors without navigating away from the submitted page."""
    return _validation_error_response(message)

COORDINATOR_ROLE = "cash_management_coordinator"
SECRETARY_ROLE = "secretary"
ADVANCE_PAYMENT_SYSTEM = "advance_payment"
PETTY_CASH_SYSTEM = "petty_cash"
FINANCE_SYSTEM = "finance"
AVAILABLE_SYSTEMS = (FINANCE_SYSTEM, PETTY_CASH_SYSTEM, ADVANCE_PAYMENT_SYSTEM)
FUND_REQUEST_FORM_PETTY_CASH = "petty_cash"
FUND_REQUEST_FORM_INTEREST = "interest"
FUND_REQUEST_FORM_BORROWING_TICKET = "borrowing"
FUND_REQUEST_NUMBERED_STATUSES = {"อนุมัติแล้ว", "เบิกเงินแล้ว", "ส่งเบิกครบแล้ว", "เคลียร์ยอดสำเร็จ"}
FUND_REQUEST_STATUS_STEPS = ["อนุมัติแล้ว", "ส่งเบิกครบแล้ว", "เคลียร์ยอดสำเร็จ"]
RETURN_DETAIL_BOUNCED_STATUS = "ฎีกาถูกตีกลับจากกองคลัง"

from .pdf_utils import (
    generate_fnar02_pdf,
    generate_fund_request_pdf,
    generate_petty_claim,
    generate_ticket_return,
    generate_petty_cash_monthly_report_pdf,
    append_petty_cash_monthly_attachments,
    summarize_petty_cash_month,
)

INTEREST_PERIOD_MONTH_LABELS = {
    "06": "มิถุนายน",
    "12": "ธันวาคม",
}

BANK_ACCOUNT_TYPE_LABELS = {
    "petty_cash": "เงินสดย่อย",
    "cash_advance": "เงินยืม",
}

MODULE_ROLE_LABELS = {
    FINANCE_SYSTEM: "ฝ่ายการเงิน",
    PETTY_CASH_SYSTEM: "ระบบเงินสดย่อย",
    ADVANCE_PAYMENT_SYSTEM: "ระบบเงินทดรองจ่าย",
}

def convert_to_fiscal_year(date):
    if date.month in [10, 11, 12]:
        return date.year + 1
    else:
        return date.year


def _get_fiscal_year_date_range(value):
    """Return the fiscal year number and its inclusive Gregorian date range."""
    fiscal_year = convert_to_fiscal_year(value)
    return (
        fiscal_year,
        date(fiscal_year - 1, 10, 1),
        date(fiscal_year, 9, 30),
    )


def _current_petty_cash_fiscal_year():
    return convert_to_fiscal_year(datetime.now().date())


def _petty_cash_budget_zero():
    return Decimal("0.00")

def _is_coordinator_role(role):
    return role == COORDINATOR_ROLE


def _is_petty_cash_role(role):
    return role == SECRETARY_ROLE


def _dashboard_endpoint_for_role(role):
    role = role or _current_module_role()
    if _selected_system() == PETTY_CASH_SYSTEM:
        return "advance_payment.staff_fund_request_history"
    if role == FINANCE_SYSTEM:
        return "advance_payment.finance_dashboard"
    return "advance_payment.coordinator_dashboard"


def _dashboard_party_label(role):
    if _is_coordinator_role(role):
        return "ผู้ประสานงาน"
    if _is_petty_cash_role(role):
        return "ผู้ดูแลเงินสดย่อย"
    return "ผู้ใช้งาน"


def _bank_account_type_label(record_type):
    return BANK_ACCOUNT_TYPE_LABELS.get((record_type or "").strip(), "ไม่พบข้อมูลประเภท")


def _normalize_lookup_value(value):
    return re.sub(r"\s+", "", str(value or "").strip()).lower()


def _normalize_interest_period_value(period_value):
    normalized = (period_value or "").strip()
    if not normalized:
        return ""

    short_match = re.fullmatch(r"(\d{2})/(\d{4})", normalized)
    if short_match:
        month_code, year_be = short_match.groups()
        if month_code in INTEREST_PERIOD_MONTH_LABELS:
            return f"{month_code}/{year_be}"
        return normalized

    long_match = re.search(r"(มิถุนายน|ธันวาคม)\s*พ\.?ศ\.?\s*(\d{4})", normalized)
    if long_match:
        month_name, year_be = long_match.groups()
        month_code = {label: code for code, label in INTEREST_PERIOD_MONTH_LABELS.items()}.get(month_name)
        if month_code:
            return f"{month_code}/{year_be}"

    return normalized


def _format_interest_period_label(period_value):
    normalized = _normalize_interest_period_value(period_value)
    short_match = re.fullmatch(r"(\d{2})/(\d{4})", normalized)
    if short_match:
        month_code, year_be = short_match.groups()
        month_name = INTEREST_PERIOD_MONTH_LABELS.get(month_code)
        if month_name:
            return f"{month_name} พ.ศ. {year_be}"
    return normalized


def _get_staff_org(staff):
    if not staff:
        return None

    personal_info = getattr(staff, "personal_info", None)
    org = getattr(personal_info, "org", None)
    return org


def _get_staff_department_name(staff, default=None):
    org = _get_staff_org(staff)
    if org and getattr(org, "name", None):
        return org.name
    return default or getattr(staff, "department", None) or default


def _fund_request_requester_name(fund_request, default=""):
    requester = _get_user_by_id(getattr(fund_request, "requester_id", None))
    ticket = getattr(fund_request, "borrowing_ticket", None)
    return (getattr(ticket, "borrower_name", None) if ticket else None) or getattr(requester, "name", None) or default


def _fund_request_requester_position(fund_request, default=""):
    requester = _get_user_by_id(getattr(fund_request, "requester_id", None))
    return getattr(requester, "position", None) or default


def _fund_request_department_name(fund_request, default="ไม่ระบุหน่วยงาน"):
    org = getattr(fund_request, "org", None)
    if org is None:
        org = db.session.query(Org).get(getattr(fund_request, "org_id", None))
    return getattr(org, "name", None) or default


def _fund_request_account_number(fund_request, default=""):
    ticket = getattr(fund_request, "borrowing_ticket", None)
    if ticket and getattr(ticket, "account_number", None):
        return ticket.account_number
    org_id = getattr(fund_request, "org_id", None)
    setting = None
    if org_id:
        setting = (
            db.session.query(PettyCashSetting)
            .filter_by(org_id=org_id, fiscal_year=_current_petty_cash_fiscal_year(), valid=True)
            .first()
        )
    if setting is None:
        legacy_org = _resolve_org_by_department_name(_fund_request_department_name(fund_request, ""))
        if legacy_org:
            setting = (
                db.session.query(PettyCashSetting)
                .filter_by(org_id=legacy_org.id, fiscal_year=_current_petty_cash_fiscal_year(), valid=True)
                .first()
            )
    return getattr(setting, "account_number", None) or default


def _bank_account_search_info(account):
    if not account:
        return "", ""

    account_name = getattr(account, "thai_name", None) or getattr(account, "name", None) or ""
    account_number = getattr(account, "account_number", None) or ""
    return account_name, account_number


def _org_search_info(org):
    if not org:
        return None, "", ""

    return getattr(org, "id", None), getattr(org, "name", None) or getattr(org, "en_name", None) or "", getattr(org, "display_name", None) or getattr(org, "name", None) or getattr(org, "en_name", None) or ""


def _resolve_org_by_department_name(dept_name):
    normalized = _normalize_lookup_value(dept_name)
    if not normalized:
        return None

    query = db.session.query(Org)
    raw_name = str(dept_name or "").strip()
    if raw_name.isdigit():
        org = query.filter_by(id=int(raw_name)).first()
        if org:
            return org

    for org in query.all():
        org_names = [
            _normalize_lookup_value(getattr(org, "name", None)),
            _normalize_lookup_value(getattr(org, "en_name", None)),
        ]
        if normalized in org_names:
            return org
        if any(candidate and (normalized in candidate or candidate in normalized) for candidate in org_names):
            return org

    return None


def _fund_request_org_filter(query, org, legacy_department_name=None):
    """Scope fund requests by their normalized organization foreign key."""
    if org and getattr(org, "id", None):
        return query.filter(FundRequest.org_id == org.id)
    return query.filter(False)


def _org_account_controller(org):
    if not org:
        return None

    # Use the staff_account_id explicitly selected in petty-cash settings.
    setting = (
        db.session.query(PettyCashSetting)
        .filter_by(org_id=org.id, fiscal_year=_current_petty_cash_fiscal_year(), valid=True)
        .first()
    )
    custodian_id = getattr(setting, "custodian_id", None) if setting else None
    controller = db.session.query(StaffAccount).filter_by(id=custodian_id).first() if custodian_id else None
    if controller:
        return {
            "name": getattr(controller, "name", "") or getattr(controller, "fullname", "") or getattr(controller, "email", ""),
            "position": getattr(controller, "position", "") or "ไม่พบข้อมูลตำแหน่ง",
            "email": getattr(controller, "email", ""),
        }

    return None


def _get_staff_accounts_from_directory():
    """Load active staff from the staff directory before any module filtering."""
    response = get_all_employees()
    payload = response.get_json(silent=True) or {}
    employee_ids = [
        employee.get("id")
        for employee in payload.get("results", [])
        if employee.get("id") is not None
    ]
    if not employee_ids:
        return []

    accounts = (
        db.session.query(StaffAccount)
        .filter(StaffAccount.personal_id.in_(employee_ids))
        .all()
    )
    accounts_by_personal_id = {account.personal_id: account for account in accounts}
    return [
        accounts_by_personal_id[personal_id]
        for personal_id in employee_ids
        if personal_id in accounts_by_personal_id
    ]


def _get_coordinator_dashboard_users(staff):
    """Return dashboard borrower choices, scoped for secretary users."""
    users = _get_staff_accounts_from_directory()
    if _current_module_role() != SECRETARY_ROLE:
        return users

    secretary_org = _get_staff_org(staff)
    if secretary_org is None:
        secretary_setting = _resolve_petty_cash_setting(staff)
        secretary_org = getattr(secretary_setting, "org", None) if secretary_setting else None

    org_id = getattr(secretary_org, "id", None)
    if org_id is None:
        return [staff]

    return [
        user
        for user in users
        if getattr(getattr(user, "personal_info", None), "org_id", None) == org_id
    ]


def _serialize_org_department(org):
    if not org:
        return None

    staff_members = []
    org_id = getattr(org, "id", None)
    for staff in _get_staff_accounts_from_directory():
        if not staff:
            continue
        personal_info = getattr(staff, "personal_info", None)
        if getattr(personal_info, "org_id", None) != org_id:
            continue
        staff_members.append(
            {
                "id": getattr(staff, "id", None),
                "name": getattr(staff, "name", None) or getattr(staff, "fullname", None) or getattr(staff, "email", ""),
                "position": getattr(staff, "position", "") or "ไม่พบข้อมูลตำแหน่ง",
                "email": getattr(staff, "email", ""),
                "department": getattr(org, "name", "") or "",
            }
        )

    controller = _org_account_controller(org)

    # Head-of-department data is maintained in staff_head_positions. Use the
    # latest position assigned to this organization as the source of truth.
    head_position_record = (
        StaffHeadPosition.query
        .filter_by(org_id=org.id)
        .order_by(StaffHeadPosition.id.desc())
        .first()
    )
    head_account = getattr(head_position_record, "staff", None) if head_position_record else None
    head_identifier = (getattr(org, "head", None) or "").strip()
    if head_account is None and head_identifier:
        head_account = StaffAccount.query.filter_by(email=head_identifier).first()

    head_name = (
        getattr(head_account, "name", None)
        or getattr(head_account, "fullname", None)
        or head_identifier
    )
    head_position = getattr(head_position_record, "position", None) or "ไม่พบข้อมูลตำแหน่ง"
    return {
        "org_id": org.id,
        "department_code": getattr(org, "en_name", None) or f"ORG-{org.id}",
        "department_name": org.name,
        "telephone_number": getattr(org, "phone_number", None) or "",
        "head_of_department": {
            "name": head_name or ".......................................................",
            "position": head_position,
            "email": "",
        },
        "account_controller": controller or {
            "name": ".......................................................",
            "position": "ไม่พบข้อมูลตำแหน่ง",
            "email": "",
        },
        "staff_members": staff_members,
    }


def _available_module_roles(staff):
    """Return the only roles that grant elevated access in this module."""
    if staff is None:
        return []

    role_names = {
        getattr(role, "role_need", None)
        for role in getattr(staff, "roles", []) or []
    }
    direct_role = getattr(staff, "role", None)
    if direct_role:
        role_names.add(direct_role)
    return [
        role
        for role in (COORDINATOR_ROLE, SECRETARY_ROLE, FINANCE_SYSTEM)
        if role in role_names
    ]


def _default_module_role(staff):
    roles = _available_module_roles(staff)
    if roles:
        return roles[0]
    return None


def _set_selected_system(system):
    if system is not None:
        session["advance_payment_system"] = system


def _current_module_user():
    """Return the Flask-Login user; never authenticate from the session."""
    return current_user if current_user.is_authenticated else None


def _module_user_from_session():
    """Backward-compatible name; authentication still comes only from Flask-Login."""
    return _current_module_user()


def _ensure_module_role(staff, requested_role):
    if requested_role not in AVAILABLE_SYSTEMS:
        return None, "กรุณาเลือกระบบที่ต้องการใช้งาน"

    available_roles = set(_available_module_roles(staff))
    if requested_role == FINANCE_SYSTEM:
        role_names = {
            getattr(role, "role_need", None)
            for role in getattr(staff, "roles", []) or []
        }
        if getattr(staff, "role", None) != FINANCE_SYSTEM and FINANCE_SYSTEM not in role_names:
            return None, "บัญชีนี้ไม่มีสิทธิ์ใช้งานฝ่ายการเงิน"
        return requested_role, None

    return requested_role, None


def _selected_system():
    return session.get("advance_payment_system")


def _current_user_id():
    return current_user.id if current_user.is_authenticated else None


def _current_module_role():
    """Return the role selected for this Advance Payment session."""
    if not current_user.is_authenticated:
        return None

    selected_system = _selected_system()
    available_roles = set(_available_module_roles(current_user))
    if selected_system == FINANCE_SYSTEM:
        return FINANCE_SYSTEM if FINANCE_SYSTEM in available_roles else None
    if selected_system == PETTY_CASH_SYSTEM and SECRETARY_ROLE in available_roles:
        return SECRETARY_ROLE
    if selected_system == ADVANCE_PAYMENT_SYSTEM and COORDINATOR_ROLE in available_roles:
        return COORDINATOR_ROLE
    if selected_system == ADVANCE_PAYMENT_SYSTEM and SECRETARY_ROLE in available_roles:
        return SECRETARY_ROLE
    return selected_system if selected_system in AVAILABLE_SYSTEMS else None


def module_role_required(permission, role, system):
    """Require both the selected module context and the user's permission."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if _selected_system() != system or _current_module_role() != role:
                abort(403)
            return view_func(*args, **kwargs)

        return flask_login_required(permission.require()(wrapped))

    return decorator


def module_system_required(systems):
    """Require login and access through one of the selected module systems."""
    allowed_systems = {systems} if isinstance(systems, str) else set(systems)

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if _selected_system() not in allowed_systems:
                abort(403)
            return view_func(*args, **kwargs)

        return flask_login_required(wrapped)

    return decorator


def _is_current_coordinator():
    return (
        current_user.is_authenticated
        and _current_module_role() == COORDINATOR_ROLE
    )


def _can_use_coordinator_dashboard():
    return (
        current_user.is_authenticated
        and _selected_system() == ADVANCE_PAYMENT_SYSTEM
        and _current_module_role() in {COORDINATOR_ROLE, SECRETARY_ROLE}
    )


def _is_current_secretary(user=None, setting=None):
    """Require a current secretary role and the account's custodian assignment."""
    if _selected_system() != PETTY_CASH_SYSTEM:
        return False
    if user is None:
        user = _module_user_from_session()
    if not user or SECRETARY_ROLE not in _available_module_roles(user):
        return False
    if setting is None:
        setting = _resolve_petty_cash_setting(user)
    return bool(
        setting
        and getattr(setting, "id", None)
        and getattr(setting, "valid", False)
        and getattr(setting, "fiscal_year", None) == _current_petty_cash_fiscal_year()
        and getattr(user, "id", None) is not None
        and user.id == getattr(setting, "custodian_id", None)
    )


def _get_user_by_id(user_id):
    if not user_id:
        return None
    return db.session.query(StaffAccount).get(user_id)


@bp.app_template_global()
def finance_last_edit(records):
    """Summarize only the displayed records, and only in the finance view."""
    if _current_module_role() != FINANCE_SYSTEM:
        return None
    latest = max(
        (record for record in records if getattr(record, "last_edited_at", None)),
        key=lambda record: (record.last_edited_at, record.last_edited_by_id or 0),
        default=None,
    )
    if latest is None:
        return {"edited_at": None}
    editor = _get_user_by_id(latest.last_edited_by_id)
    return {
        "edited_at": latest.last_edited_at,
        "editor_id": latest.last_edited_by_id,
        "editor_name": (
            (getattr(editor, "fullname", None) or getattr(editor, "email", None))
            if editor else None
        ),
    }


def _get_borrowing_ticket_by_id(ticket_id):
    if not ticket_id:
        return None
    return db.session.query(BorrowingTicket).get(ticket_id)


def _can_submit_return_detail(user_id, borrowing_ticket):
    if not user_id or not borrowing_ticket:
        return False

    if user_id in {borrowing_ticket.creator_id, borrowing_ticket.borrower_id}:
        return True

    current_user = _get_user_by_id(user_id)
    borrower = _get_user_by_id(getattr(borrowing_ticket, "borrower_id", None))
    current_org = _get_staff_org(current_user)
    borrower_org = _get_staff_org(borrower)
    return bool(
        current_org
        and borrower_org
        and getattr(current_org, "id", None) == getattr(borrower_org, "id", None)
    )


def _get_fund_request_by_id(fund_request_id):
    if not fund_request_id:
        return None
    return db.session.query(FundRequest).get(fund_request_id)


def _attach_borrowing_ticket_people(ticket):
    if not ticket:
        return None

    ticket.creator_user = _get_user_by_id(getattr(ticket, "creator_id", None))
    ticket.borrower_user = _get_user_by_id(getattr(ticket, "borrower_id", None))
    return ticket


def _attach_fund_request_people(fund_request):
    if not fund_request:
        return None

    fund_request.requester_user = _get_user_by_id(getattr(fund_request, "requester_id", None))
    return fund_request


def _attach_petty_cash_setting_people(setting):
    if not setting:
        return None

    setting.custodian_user = _get_user_by_id(getattr(setting, "custodian_id", None))
    return setting


def _attach_fund_request_ticket(fund_request):
    if not fund_request:
        return None

    fund_request.borrowing_ticket = _get_borrowing_ticket_by_id(getattr(fund_request, "borrowing_ticket_id", None))
    return fund_request


def _attach_parcel_return_context(parcel_return):
    if not parcel_return:
        return None

    ticket = _get_borrowing_ticket_by_id(getattr(parcel_return, "ticket_id", None))
    fund_request = _get_fund_request_by_id(getattr(parcel_return, "fund_request_id", None))
    parcel_return.borrowing_ticket = ticket
    parcel_return.fund_request = fund_request

    if ticket:
        borrower_user = _get_user_by_id(getattr(ticket, "borrower_id", None))
        parcel_return.display_ticket_number = ticket.number if ticket.number is not None else (ticket.aip_ref_no or "-")
        parcel_return.display_borrower_name = ticket.borrower_name or getattr(borrower_user, "name", "") or "-"
        parcel_return.display_ticket_id = ticket.id
        parcel_return.display_subject_name = ticket.borrowing_ticket_name or "-"
    elif fund_request:
        requester_user = _get_user_by_id(getattr(fund_request, "requester_id", None))
        parcel_return.display_ticket_number = fund_request.ticket_number or getattr(fund_request, "id", None) or "-"
        parcel_return.display_borrower_name = _fund_request_requester_name(fund_request, "-")
        parcel_return.display_ticket_id = getattr(fund_request, "borrowing_ticket_id", None)
        parcel_return.display_subject_name = fund_request.purpose or "-"
    else:
        parcel_return.display_ticket_number = "-"
        parcel_return.display_borrower_name = "-"
        parcel_return.display_ticket_id = None
        parcel_return.display_subject_name = "-"

    return parcel_return


def _attach_petty_cash_claim_context(claim):
    if not claim:
        return None

    claim.user = _get_user_by_id(getattr(claim, "user_id", None))
    claim.setting = db.session.query(PettyCashSetting).get(getattr(claim, "petty_cash_setting_id", None))
    claim.fund_request = db.session.query(FundRequest).get(getattr(claim, "fund_request_id", None))

    if claim.setting:
        _attach_petty_cash_setting_people(claim.setting)
    if claim.fund_request:
        _attach_fund_request_people(claim.fund_request)
        _attach_fund_request_ticket(claim.fund_request)

    _prepare_document_display_list(claim.documents)
    return claim


def _claim_has_only_category_six(claim):
    """Return true for claims that contain only the internal transfer category."""
    items = getattr(claim, "items", [])
    return bool(items) and all(int(item.category_type or 0) == 6 for item in items)


def _get_finance_visible_claim(claim_id):
    """Load a claim that finance is allowed to process."""
    claim = db.session.query(PettyCashClaimDetail).get(claim_id)
    if not claim or _claim_has_only_category_six(claim):
        abort(404)
    return claim


def _get_bank_account_dropdown_options():
    bank_accounts = (
        db.session.query(BankAccountInfo)
        .filter(BankAccountInfo.closed_at.is_(None))
        .order_by(
            BankAccountInfo.thai_name.asc(),
            BankAccountInfo.account_number.asc(),
        )
        .all()
    )

    options = []
    for account in bank_accounts:
        account_number = (account.account_number or "").strip()
        thai_name = (account.thai_name or "").strip()
        if not account_number:
            continue

        label = account_number
        if thai_name:
            label = f"{account_number} - {thai_name}"

        options.append(
            {
                "id": account.id,
                "value": account_number,
                "label": label,
            }
        )

    return options


def _get_bank_account_info(*, bank_account_info_id=None, account_number=None):
    query = db.session.query(BankAccountInfo).filter(BankAccountInfo.closed_at.is_(None))

    if bank_account_info_id:
        try:
            bank_account_info_id = int(bank_account_info_id)
        except (TypeError, ValueError):
            bank_account_info_id = None
        if bank_account_info_id:
            record = query.filter_by(id=bank_account_info_id).first()
            if record:
                return record

    normalized_account_number = (account_number or "").strip()
    if normalized_account_number:
        return query.filter_by(account_number=normalized_account_number).first()

    return None


def _resolve_petty_cash_setting(user, fiscal_year=None):
    if not user:
        return None

    current_fiscal_year = fiscal_year if fiscal_year is not None else _current_petty_cash_fiscal_year()
    setting = getattr(user, "petty_cash_setting", None)
    if setting and getattr(setting, "valid", False) and getattr(setting, "fiscal_year", None) == current_fiscal_year:
        return setting

    user_id = getattr(user, "id", None)
    user_name_candidates = {
        _normalize_lookup_value(getattr(user, "name", None)),
        _normalize_lookup_value(getattr(user, "fullname", None)),
        _normalize_lookup_value(getattr(user, "email", None)),
    }
    user_name_candidates.discard("")

    org = _get_staff_org(user)
    org_names = []
    if org:
        org_name = (getattr(org, "name", "") or "").strip()
        org_en_name = (getattr(org, "en_name", "") or "").strip()
        if org_name:
            org_names.append(org_name)
        if org_en_name and org_en_name not in org_names:
            org_names.append(org_en_name)

    query = db.session.query(PettyCashSetting).filter(
        PettyCashSetting.valid == True,
        PettyCashSetting.fiscal_year == current_fiscal_year,
    )

    if user_id:
        setting = query.filter(PettyCashSetting.custodian_id == user_id).first()
        if setting:
            return setting

    for setting in query.all():
        custodian_name = _normalize_lookup_value(getattr(setting, "custodian_name", None))
        if custodian_name and custodian_name in user_name_candidates:
            return setting

    if org:
        setting = query.filter_by(org_id=org.id).first()
        if setting:
            return setting

    department_name = (getattr(user, "department", "") or "").strip()
    if department_name:
        department_org = _resolve_org_by_department_name(department_name)
        if department_org:
            setting = query.filter_by(org_id=department_org.id).first()
            if setting:
                return setting

    normalized_candidates = [*org_names, department_name]
    normalized_candidates = [value for value in normalized_candidates if value]
    if normalized_candidates:
        settings = query.all()
        for setting in settings:
            setting_department = _normalize_lookup_value(getattr(setting, "department_name", None))
            if not setting_department:
                continue
            for candidate in normalized_candidates:
                normalized_candidate = _normalize_lookup_value(candidate)
                if not normalized_candidate:
                    continue
                if (
                    setting_department == normalized_candidate
                    or setting_department in normalized_candidate
                    or normalized_candidate in setting_department
                ):
                    return setting

    return SimpleNamespace(
        id=None,
        fiscal_year=current_fiscal_year,
        budget=_petty_cash_budget_zero(),
        department_name=department_name or "ไม่ระบุหน่วยงาน",
        account_number="",
        custodian_name=getattr(user, "name", "") or "",
        staff=user,
        valid=False,
    )


def _calculate_petty_cash_balance_summary(setting, *, user_id=None):
    current_fiscal_year = _current_petty_cash_fiscal_year()
    setting_budget = getattr(setting, "budget", 0) or 0
    setting_valid = bool(getattr(setting, "valid", False))
    setting_year = getattr(setting, "fiscal_year", None)
    if not setting_valid or setting_year != current_fiscal_year:
        return {
            "total_claims": 0,
            "total_fund_requests": 0,
            "total_amount": 0.0,
            "total_spent": 0.0,
            "remaining_budget": 0.0,
            "initial_budget": 0.0,
        }

    initial_budget = float(setting_budget)
    setting_org = getattr(setting, "org", None)
    if setting_org is None:
        setting_org = _resolve_org_by_department_name(getattr(setting, "department_name", ""))
    department_name = (getattr(setting_org, "name", "") or getattr(setting, "department_name", "") or "").strip()
    setting_id = getattr(setting, "id", None)

    approved_fund_requests = []
    if getattr(setting_org, "id", None):
        approved_fund_requests = _fund_request_org_filter(
            db.session.query(FundRequest), setting_org, department_name
        ).all()
        approved_fund_requests = [
            fund_request
            for fund_request in approved_fund_requests
            if (fund_request.status or "").strip() not in {
                "ปฏิเสธ",
                "ยกเลิก",
                "กำลังดำเนินการ",
                "เบิกเงินแล้ว",
            }
            and getattr(fund_request, "request_date", None)
            and convert_to_fiscal_year(fund_request.request_date) == current_fiscal_year
        ]

    total_fund_expenses = sum(float(fund_request.amount or 0) for fund_request in approved_fund_requests)

    approved_claims = []
    if setting_id:
        approved_claims = (
            db.session.query(PettyCashClaimDetail)
            .filter(PettyCashClaimDetail.petty_cash_setting_id == setting_id)
            .all()
        )
    elif user_id:
        approved_claims = (
            db.session.query(PettyCashClaimDetail)
            .filter(PettyCashClaimDetail.user_id == user_id)
            .all()
        )

    approved_claims = [
        claim
        for claim in approved_claims
        if (claim.status or "").strip() not in {"ฉบับร่าง", "ปฏิเสธ", "ถูกปฏิเสธ", "ยกเลิก"}
        and getattr(claim, "created_at", None)
        and convert_to_fiscal_year(claim.created_at.date()) == current_fiscal_year
    ]

    total_claim_incomes = 0.0
    for claim in approved_claims:
        claim_status = (claim.status or "").strip()
        # Replenish expenses only after transfer, retaining the credit when
        # a transferred claim is subsequently marked complete.
        is_transferred = claim_status in {"โอนคืนเงินสดย่อย", "โอนเงินสดย่อยสำเร็จ"} or (
            claim_status == "เสร็จสิ้นกระบวนการ"
            and bool(getattr(claim, "transferred_at", None))
        )
        for item in claim.items:
            # cat_6 is money returned directly to the unit on submission.
            if is_transferred or int(item.category_type or 0) == 6:
                total_claim_incomes += float(item.amount or 0)

    running_balance = initial_budget - total_fund_expenses + total_claim_incomes
    remaining_budget = max(0.0, running_balance)

    return {
        "total_claims": len(approved_claims),
        "total_fund_requests": len(approved_fund_requests),
        "total_amount": running_balance,
        "total_spent": total_fund_expenses,
        "remaining_budget": remaining_budget,
        "initial_budget": initial_budget,
    }


def _get_approved_borrowing_tickets_for_setting(setting):
    if not setting or not getattr(setting, "account_number", None):
        return []

    return (
        db.session.query(BorrowingTicket)
        .filter(
            BorrowingTicket.account_number == setting.account_number,
            BorrowingTicket.approved_at.isnot(None),
            ~db.session.query(FundRequest.id).filter(
                FundRequest.borrowing_ticket_id == BorrowingTicket.id,
            ).exists(),
        )
        .order_by(BorrowingTicket.approved_at.asc(), BorrowingTicket.created_at.asc())
        .all()
    )


def _fund_request_number_base_date(fund_request, reference_date=None):
    for candidate in (reference_date, getattr(fund_request, "request_date", None), getattr(fund_request, "created_at", None)):
        coerced = _coerce_date(candidate)
        if coerced:
            return coerced
    return datetime.now().date()


def _assign_fund_request_ticket_number(fund_request, reference_date=None):
    org_id = getattr(fund_request, "org_id", None)
    if not org_id:
        legacy_department_name = (getattr(fund_request, "department_name", "") or "").strip()
        legacy_org = _resolve_org_by_department_name(legacy_department_name)
        org_id = getattr(legacy_org, "id", None)
        if org_id:
            fund_request.org_id = org_id
    if not org_id:
        return None

    base_date = _fund_request_number_base_date(fund_request, reference_date=reference_date)
    fiscal_year, year_start, year_end = _get_fiscal_year_date_range(base_date)
    buddhist_year = fiscal_year + 543

    # The sequence belongs to this organization and fiscal year only. Count
    # every already-numbered request so pending requests reserve their number.
    issued_query = db.session.query(func.count(FundRequest.id)).filter(
        FundRequest.org_id == org_id,
        FundRequest.request_date >= year_start,
        FundRequest.request_date <= year_end,
        func.trim(func.coalesce(FundRequest.ticket_number, "")) != "",
    )
    if getattr(fund_request, "id", None):
        issued_query = issued_query.filter(FundRequest.id != fund_request.id)
    issued_count = issued_query.scalar() or 0

    ticket_number = f"{issued_count + 1}/{buddhist_year}"
    fund_request.ticket_number = ticket_number
    return ticket_number

@bp.before_request
def recheck_overdue_and_upcoming_statuses():
    g.advance_payment_finance_actor_id = None
    if not current_user.is_authenticated:
        return

    user_id = current_user.id
    if _current_module_role() == FINANCE_SYSTEM and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        g.advance_payment_finance_actor_id = current_user.id

    today = datetime.now().date()

    query = db.session.query(BorrowingTicket).filter(
        BorrowingTicket.status != "ปฏิเสธ",
        BorrowingTicket.status != "กำลังส่งคำขอ",
        BorrowingTicket.status != "เคลียร์ยอดแล้ว"
    )

    if _current_module_role() == COORDINATOR_ROLE:
        query = query.filter(BorrowingTicket.creator_id == user_id)

    tickets = query.all()

    for ticket in tickets:
        if ticket.last_notified_date == today:
            continue

        days_remaining = (ticket.due_date - today).days

        notification_type = None

        if days_remaining < 0:
            if ticket.last_notified_type != "overdue":
                notification_type = "overdue"

        elif days_remaining in [15, 10, 5, 3]:
            current_type = str(days_remaining)
            if ticket.last_notified_type != current_type:
                notification_type = current_type

        if notification_type:
            is_overdue = (notification_type == "overdue")
            is_upcoming = not is_overdue

            _send_notification_email(ticket, extra_ctx={
                "is_overdue": is_overdue,
                "is_upcoming": is_upcoming,
                "days_remaining": days_remaining
            })

            ticket.last_notified_type = notification_type
            ticket.last_notified_date = today

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()

def _coerce_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _receipt_requires_additional_document(receipt_date):
    if not receipt_date:
        return False
    return (datetime.now().date() - receipt_date).days > 10


def _calculate_due_date(end_date):
    project_end_date = _coerce_date(end_date)
    if project_end_date is None:
        return None
    return project_end_date + timedelta(days=15)


def _docs_query_view_url(file_id):
    if not file_id:
        return None
    return f"https://drive.google.com/file/d/{file_id}/view"


def _docs_query_download_url(file_id):
    if not file_id:
        return None
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def _docs_query_document_tag_names(document):
    return [
        tag.name
        for tag in getattr(document, "tags", []) or []
        if getattr(tag, "name", "").strip()
    ]


def _docs_query_document_status_label(document):
    status = (getattr(document, "status", "") or "").strip()
    if status == "processed":
        label = "พร้อมใช้งาน"
        if getattr(document, "is_expired", False):
            return f"{label} / หมดอายุ"
        return label
    if status == "processing":
        return "กำลังประมวลผล"
    if status == "failed":
        return "ประมวลผลล้มเหลว"
    return "รอประมวลผล"


def _docs_query_document_status_class(document):
    status = (getattr(document, "status", "") or "").strip()
    if status == "processed":
        return "bg-success text-white" if not getattr(document, "is_expired", False) else "bg-danger text-white"
    if status == "processing":
        return "bg-info text-white"
    if status == "failed":
        return "bg-danger text-white"
    return "bg-secondary text-white"


def _resolve_docs_query_document(identifier=None, title=None):
    candidates = []
    for value in (identifier, title):
        cleaned_value = (str(value).strip() if value is not None else "")
        if cleaned_value:
            candidates.append(cleaned_value)

    if not candidates:
        return None

    query = db.session.query(DocsQueryDocument).options(joinedload(DocsQueryDocument.tags))

    for candidate in candidates:
        document = query.filter(DocsQueryDocument.drive_file_id == candidate).first()
        if document is not None:
            return document

    for candidate in candidates:
        normalized_candidate = candidate.lower()
        document = query.filter(func.lower(func.trim(DocsQueryDocument.document_title)) == normalized_candidate).first()
        if document is not None:
            return document
        document = query.filter(func.lower(func.trim(DocsQueryDocument.filename)) == normalized_candidate).first()
        if document is not None:
            return document

    return None


def _attach_document_source_context(document):
    if not document:
        return None

    source_document = _resolve_docs_query_document(
        getattr(document, "file_path", None),
        getattr(document, "title", None),
    )
    if source_document is None:
        return document

    document.file_id = source_document.drive_file_id
    document.download_url = _docs_query_download_url(source_document.drive_file_id)
    document.view_url = _docs_query_view_url(source_document.drive_file_id)
    document.url = document.view_url
    document.document_type = source_document.document_type or getattr(document, "document_type", None)
    document.note = source_document.note or getattr(document, "note", None)
    document.summary = source_document.summary or getattr(document, "summary", None)
    document.tags = _docs_query_document_tag_names(source_document)
    document.status = source_document.status
    document.status_label = _docs_query_document_status_label(source_document)
    document.status_class = _docs_query_document_status_class(source_document)
    document.is_expired = bool(source_document.is_expired)
    return document


def _prepare_document_display_list(documents):
    prepared_documents = []
    for document in documents or []:
        prepared_documents.append(_attach_document_source_context(document))
    return prepared_documents


def _sync_document_from_docs_query(source_document):
    if source_document is None:
        return None

    canonical_title = (
        source_document.document_title
        or source_document.filename
        or source_document.drive_file_id
    )
    view_url = _docs_query_view_url(source_document.drive_file_id)
    download_url = _docs_query_download_url(source_document.drive_file_id)

    document = (
        db.session.query(Document)
        .filter(
            or_(
                Document.file_path == view_url,
                Document.title == canonical_title,
            )
        )
        .first()
    )

    if document is None:
        document = Document(
            title=canonical_title,
            file_path=view_url or download_url or "#",
            created_at=datetime.now(),
        )
        db.session.add(document)
        db.session.flush()
    else:
        document.title = canonical_title
        document.file_path = view_url or download_url or document.file_path

    document.download_url = download_url
    document.view_url = view_url
    document.file_id = source_document.drive_file_id
    document.status = source_document.status
    document.summary = source_document.summary
    document.document_type = source_document.document_type
    document.note = source_document.note
    document.tags = _docs_query_document_tag_names(source_document)
    document.is_expired = bool(source_document.is_expired)
    return document


def _get_or_create_document(title=None, source_document=None):
    cleaned_title = (title or "").strip()
    if source_document is None:
        source_document = _resolve_docs_query_document(title=cleaned_title)

    if source_document is not None:
        return _sync_document_from_docs_query(source_document)

    if not cleaned_title:
        return None

    document = db.session.query(Document).filter_by(title=cleaned_title).first()
    # TODO: รอหาโซลูชั่นใหม่
    if document is None:
        dummy_file_path = f"/static/dummy_documents/{secure_filename(cleaned_title)}.pdf"
        document = Document(
            title=cleaned_title,
            file_path=dummy_file_path,
            created_at=datetime.now(),
        )
        db.session.add(document)
        db.session.flush()
    return document


def _resolve_document_reference(reference=None, title=None):
    reference_id = None
    reference_title = title

    if isinstance(reference, dict):
        reference_id = reference.get("id") or reference.get("file_id") or reference.get("drive_file_id")
        reference_title = reference.get("title") or reference.get("document_title") or reference.get("name") or reference_title
    elif reference is not None:
        reference_title = str(reference).strip() or reference_title

    source_document = _resolve_docs_query_document(reference_id, reference_title)
    resolved_title = (
        getattr(source_document, "document_title", None)
        or getattr(source_document, "filename", None)
        or (reference_title or "").strip()
    )
    return source_document, resolved_title


def _replace_documents_from_references(association_table, association_key, target_id, references):
    db.session.execute(
        association_table.delete().where(
            getattr(association_table.c, association_key) == target_id
        )
    )

    seen_document_ids = set()
    for reference in references or []:
        source_document, resolved_title = _resolve_document_reference(reference)
        document = _get_or_create_document(resolved_title, source_document=source_document)
        if document is None or document.id in seen_document_ids:
            continue
        seen_document_ids.add(document.id)
        db.session.execute(
            association_table.insert().values(
                document_id=document.id,
                **{association_key: target_id},
            )
        )


def _replace_return_detail_documents(return_detail, references):
    _replace_documents_from_references(
        document_return_association,
        "return_id",
        return_detail.id,
        references,
    )


def _replace_claim_detail_documents(claim_detail, references):
    _replace_documents_from_references(
        document_petty_claim_association,
        "claim_id",
        claim_detail.id,
        references,
    )


def _list_cash_mng_documents(search_query=None, limit=None):
    query = (
        db.session.query(DocsQueryDocument)
        .options(joinedload(DocsQueryDocument.tags))
    )

    cleaned_query = (search_query or "").strip()
    if cleaned_query:
        pattern = f"%{cleaned_query.lower()}%"
        query = query.filter(
            or_(
                func.lower(func.coalesce(DocsQueryDocument.document_title, "")).like(pattern),
                func.lower(func.coalesce(DocsQueryDocument.filename, "")).like(pattern),
                func.lower(func.coalesce(DocsQueryDocument.document_type, "")).like(pattern),
                func.lower(func.coalesce(DocsQueryDocument.note, "")).like(pattern),
                func.lower(func.coalesce(DocsQueryDocument.summary, "")).like(pattern),
                DocsQueryDocument.tags.any(func.lower(DocsQueryTag.name).like(pattern)),
            )
        )

    query = query.order_by(
        DocsQueryDocument.updated_at.desc(),
        DocsQueryDocument.created_at.desc(),
        DocsQueryDocument.id.desc(),
    )
    if limit:
        query = query.limit(limit)

    documents = []
    for source_document in query.all():
        documents.append({
            "id": source_document.drive_file_id,
            "file_id": source_document.drive_file_id,
            "title": source_document.document_title or source_document.filename or source_document.drive_file_id,
            "document_type": source_document.document_type or "",
            "note": source_document.note or "",
            "summary": source_document.summary or "",
            "tags": _docs_query_document_tag_names(source_document),
            "status": source_document.status or "pending",
            "status_label": _docs_query_document_status_label(source_document),
            "status_class": _docs_query_document_status_class(source_document),
            "is_expired": bool(source_document.is_expired),
            "file_path": _docs_query_download_url(source_document.drive_file_id),
            "download_url": _docs_query_download_url(source_document.drive_file_id),
            "view_url": _docs_query_view_url(source_document.drive_file_id),
            "url": _docs_query_view_url(source_document.drive_file_id),
            "document_title": source_document.document_title or source_document.filename or source_document.drive_file_id,
            "filename": source_document.filename or "",
        })
    return documents


def _download_cash_mng_document(file_id):
    source_document = _resolve_docs_query_document(file_id)
    if source_document is None:
        abort(404)
    return redirect(_docs_query_download_url(source_document.drive_file_id))


def _send_notification_email(target_object, object_type="ticket", extra_ctx=None):
    if extra_ctx is None:
        extra_ctx = {}

    if object_type == "ticket":
        borrower = db.session.query(StaffAccount).filter_by(email=target_object.borrower_email).first()
        creator = db.session.query(StaffAccount).filter_by(id=target_object.creator_id).first()
        extra_ctx["recipient_emails"] = [
            target_object.borrower_email,
            creator.email if creator else None,
        ]
        extra_ctx["borrower_name"] = (
            target_object.borrower_name
            or (borrower.name if borrower else None)
            or target_object.borrower_email
            or "ผู้รับบริการ"
        )

        totals = _calculate_ticket_return_totals(target_object.id)
        extra_ctx["remaining_amount"] = totals["remaining_amount"]
        extra_ctx["is_overdue"] = target_object.due_date < datetime.now().date() if target_object.due_date else False

    elif object_type == "return":
        ticket = db.session.query(BorrowingTicket).filter_by(id=target_object.ticket_id).first()
        extra_ctx["ticket"] = ticket
        if ticket:
            borrower = db.session.query(StaffAccount).filter_by(email=ticket.borrower_email).first()
            creator = db.session.query(StaffAccount).filter_by(id=ticket.creator_id).first()
            extra_ctx["recipient_emails"] = [
                ticket.borrower_email,
                creator.email if creator else None,
            ]
            extra_ctx["borrower_name"] = (
                ticket.borrower_name
                or (borrower.name if borrower else None)
                or ticket.borrower_email
                or "ผู้รับบริการ"
            )
    elif object_type == "petty_claim":
        requester = db.session.query(StaffAccount).filter_by(id=getattr(target_object, "user_id", None)).first()
        setting = db.session.query(PettyCashSetting).get(getattr(target_object, "petty_cash_setting_id", None))
        custodian = db.session.query(StaffAccount).filter_by(id=getattr(setting, "custodian_id", None)).first() if setting else None

        extra_ctx["recipient_emails"] = [
            requester.email if requester else None,
            custodian.email if custodian else None,
        ]
        extra_ctx["requester_name"] = (
            (requester.name if requester else None)
            or getattr(target_object, "requester_name", None)
            or "ผู้ขอเบิก"
        )
        extra_ctx["fund_request"] = getattr(target_object, "fund_request", None)
        extra_ctx["claim_name"] = (
            getattr(target_object.fund_request, "purpose", None)
            if getattr(target_object, "fund_request", None)
            else None
        ) or (setting.department_name if setting else None) or "รายการเบิกเงินสดย่อย"
    elif object_type == "parcel_return":
        ticket = db.session.query(BorrowingTicket).filter_by(id=target_object.ticket_id).first() if getattr(target_object, "ticket_id", None) else None
        fund_request = db.session.query(FundRequest).filter_by(id=getattr(target_object, "fund_request_id", None)).first() if getattr(target_object, "fund_request_id", None) else None
        extra_ctx["ticket"] = ticket
        extra_ctx["fund_request"] = fund_request
        if ticket:
            borrower = db.session.query(StaffAccount).filter_by(email=ticket.borrower_email).first()
            creator = db.session.query(StaffAccount).filter_by(id=ticket.creator_id).first()
            extra_ctx["recipient_emails"] = [
                ticket.borrower_email,
                creator.email if creator else None,
            ]
            extra_ctx["borrower_name"] = (
                ticket.borrower_name
                or (borrower.name if borrower else None)
                or ticket.borrower_email
                or "ผู้รับบริการ"
            )
        elif fund_request:
            requester = db.session.query(StaffAccount).filter_by(id=fund_request.requester_id).first()
            extra_ctx["recipient_emails"] = [
                requester.email if requester else None,
            ]
            extra_ctx["borrower_name"] = _fund_request_requester_name(fund_request, "ผู้ขอเบิก")

    email_data = generate_notification_email_content(target_object, object_type=object_type, extra_ctx=extra_ctx)

    try:
        current_app.logger.info(
            f"ส่งข้อความไปยัง: {', '.join(email_data['to_emails']) or 'ไม่พบอีเมลผู้รับ'}"
        )
        current_app.logger.info(f"หัวข้ออีเมล: {email_data['subject']}")
        current_app.logger.info(f"เนื้อหากล่องข้อความ:\n{email_data['body']}")
        return True
    except Exception as e:
        current_app.logger.error(f"ไม่สามารถจัดส่งอีเมลแจ้งเตือนได้เนื่องจาก: {e}")
        return False

@bp.route("/finance/returns/<int:return_id>/checking", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def mark_return_checking(return_id):
    return_detail = db.session.query(ReturnDetail).get(return_id)
    if not return_detail:
        abort(404)

    return_detail.status = "กำลังตรวจสอบ"
    db.session.commit()

    _recalculate_borrowing_ticket_status(return_detail.ticket_id)
    _send_notification_email(return_detail, object_type="return")
    flash("เปลี่ยนสถานะเป็น 'กำลังตรวจสอบ' เรียบร้อยแล้ว")
    return view_return_proof_detail(return_id)

@bp.route("/finance/returns/<int:return_id>/received", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def mark_return_received(return_id):
    return_detail = db.session.query(ReturnDetail).get(return_id)
    if not return_detail:
        abort(404)

    return_detail.status = "ล้างลูกหนี้เงินยืม"
    db.session.commit()

    _recalculate_borrowing_ticket_status(return_detail.ticket_id)


    flash("เปลี่ยนสถานะเป็น 'ได้รับเงินแล้ว' และสิ้นสุดกระบวนการเรียบร้อย")
    return view_return_proof_detail(return_id)

@bp.route("/finance/returns/<int:return_id>/bounced", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def mark_return_bounced(return_id):
    return_detail = db.session.query(ReturnDetail).get(return_id)
    if not return_detail:
        abort(404)

    if not return_detail.old_document_number:
        return _validation_error_response("ไม่พบเลขฎีกาเก่า จึงยังไม่สามารถตีกลับเอกสารนี้จากกองคลังได้")

    rejection_comment = request.form.get("rejection_comment", "").strip()
    if not rejection_comment:
        return _validation_error_response("กรุณาระบุเหตุผลที่ตีกลับเอกสาร")

    existing_comment = return_detail.rejection_comment or ""
    count = existing_comment.count("ครั้งที่") + 1
    staff = current_user
    user_name = staff.name if staff else "ไม่ระบุชื่อ"
    formatted_comment = (
        f"ครั้งที่ {count}: {rejection_comment} "
        f"ผู้ตีกลับ: {user_name} เมื่อ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return_detail.rejection_comment = (
        f"{existing_comment}\n{formatted_comment}" if existing_comment else formatted_comment
    )
    return_detail.status = RETURN_DETAIL_BOUNCED_STATUS
    borrowing_ticket = db.session.query(BorrowingTicket).get(return_detail.ticket_id)
    if borrowing_ticket:
        borrowing_ticket.status = RETURN_DETAIL_BOUNCED_STATUS

    db.session.commit()
    flash("เปลี่ยนสถานะเป็น 'ฎีกาถูกตีกลับจากกองคลัง' เรียบร้อยแล้ว", "success")
    return view_return_proof_detail(return_id)

@bp.route("/finance/closing-documents/<int:closing_doc_id>/cancel", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def cancel_closing_doc(closing_doc_id):
    """Cancel the document while retaining its associations for history."""
    closing_doc = db.session.query(ClosingDocument).filter_by(id=closing_doc_id).with_for_update().first()
    if not closing_doc:
        abort(404)
    if not closing_doc.is_active:
        return _validation_error_response("ฎีกานี้ถูกยกเลิกแล้ว")

    doc_number = closing_doc.document_number
    updated_tickets = set()
    for link in closing_doc.links:
        if not link.is_active:
            continue
        record = link.record
        link.is_active = False
        if link.ticket_return_id is not None:
            record.status = "ผ่านการตรวจสอบ"
            updated_tickets.add(record.ticket_id)
        elif link.parcel_return_id is not None:
            record.status = "ได้รับเอกสารแล้ว"
            updated_tickets.add(record.ticket_id)
        else:
            record.status = "โอนเงินสดย่อยสำเร็จ"
    closing_doc.is_active = False

    # คำนวณสถานะตั๋วเงินยืมใหม่สำหรับทุกสัญญาที่เกี่ยวข้อง
    for ticket_id in updated_tickets:
        _recalculate_borrowing_ticket_status(ticket_id)

    db.session.commit()
    flash(f"ยกเลิกฎีกาเลขที่ {doc_number} เรียบร้อยแล้ว (สถานะเปลี่ยนเป็น 'ถูกยกเลิก' และคงยอดเงินประวัติไว้)", "success")
    return closing_management(
        _render_after_post=True,
        _forced_search_closing_number=doc_number,
    )

@bp.route("/finance/closing-documents/<int:closing_doc_id>/bulk-receive", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def bulk_receive_closing_doc(closing_doc_id):
    """ เปลี่ยนสถานะเอกสารทุกรายการในฎีกานี้เป็น ล้างลูกหนี้เงินยืม """
    closing_doc = db.session.query(ClosingDocument).filter_by(id=closing_doc_id).with_for_update().first()
    if not closing_doc:
        abort(404)
    if not closing_doc.is_active:
        abort(400, description="Cannot settle a cancelled closing document")

    returns_in_doc = [link.ticket_return for link in closing_doc.links
                      if link.is_active and link.ticket_return is not None
                      and link.ticket_return.status != "ล้างลูกหนี้เงินยืม"]
    parcel_in_doc = [link.parcel_return for link in closing_doc.links
                    if link.is_active and link.parcel_return is not None
                    and link.parcel_return.status != "ล้างลูกหนี้เงินยืม"]
    petty_in_doc = [link.claim for link in closing_doc.links
                   if link.is_active and link.claim is not None
                   and link.claim.status != "เสร็จสิ้นกระบวนการ"]

    if not returns_in_doc and not petty_in_doc and not parcel_in_doc:
        return _validation_error_response(
            "ไม่มีรายการเอกสารส่งใช้เงินยืม พัสดุ หรือเงินสดย่อยที่ต้องล้างลูกหนี้ในฎีกานี้เพิ่มเติม"
        )

    updated_tickets = set()
    for ret in returns_in_doc:
        ret.status = "ล้างลูกหนี้เงินยืม"
        updated_tickets.add(ret.ticket_id)

    for pr in parcel_in_doc:
        pr.status = "ล้างลูกหนี้เงินยืม"
        updated_tickets.add(pr.ticket_id)

    for petty in petty_in_doc:
        petty.status = "เสร็จสิ้นกระบวนการ"

    for ticket_id in updated_tickets:
        _recalculate_borrowing_ticket_status(ticket_id)

    closing_doc.settled_at = datetime.now(ZoneInfo("Asia/Bangkok"))
    db.session.commit()
    flash(f"เปลี่ยนสถานะรายการทั้งหมดรวมถึงเงินสดย่อยในฎีกา {closing_doc.document_number} เป็น 'ล้างลูกหนี้เงินยืม' เรียบร้อยแล้ว", "success")
    return closing_management(
        _render_after_post=True,
        _forced_search_closing_number=closing_doc.document_number,
    )

def _calculate_ticket_return_totals(ticket_id):
    cumulative_normal = (
        db.session.query(func.coalesce(func.sum(ReturnDetail.amount_spent), 0))
        .filter(
            ReturnDetail.ticket_id == ticket_id,
            ReturnDetail.status.in_(["ผ่านการตรวจสอบ", "เอกสารตั้งฎีกา", "ล้างลูกหนี้เงินยืม"])
        )
        .scalar() or 0
    )
    cumulative_parcel = (
        db.session.query(func.coalesce(func.sum(ParcelReturnDetail.amount_spent), 0))
        .filter(
            ParcelReturnDetail.ticket_id == ticket_id,
            ParcelReturnDetail.status.not_in(["รอตรวจสอบ", "ถูกปฏิเสธ", "ปฏิเสธ"])
        )
        .scalar() or 0
    )

    cumulative_total = float(cumulative_normal) + float(cumulative_parcel)

    budget = (
        db.session.query(BorrowingTicket.required_budget)
        .filter(BorrowingTicket.id == ticket_id)
        .scalar() or 0
    )

    remaining_amount = float(budget) - cumulative_total

    return {
        "cumulative_total": cumulative_total,
        "budget": float(budget),
        "remaining_amount": remaining_amount,
        "status": (
            "เคลียร์ยอดแล้ว" if cumulative_total >= budget
            else "มียอดคงค้าง" if cumulative_total > 0
            else "อนุมัติจ่ายเงิน"
        ),
    }


def _calculate_ticket_return_totals_with_parcel(ticket_id, *, exclude_return_id=None, exclude_parcel_return_id=None):
    return_query = db.session.query(func.coalesce(func.sum(ReturnDetail.amount_spent), 0)).filter(
        ReturnDetail.ticket_id == ticket_id,
    )
    if exclude_return_id:
        return_query = return_query.filter(ReturnDetail.id != exclude_return_id)

    parcel_query = db.session.query(func.coalesce(func.sum(ParcelReturnDetail.amount_spent), 0)).filter(
        ParcelReturnDetail.ticket_id == ticket_id,
    )
    if exclude_parcel_return_id:
        parcel_query = parcel_query.filter(ParcelReturnDetail.id != exclude_parcel_return_id)

    return_total = float(return_query.scalar() or 0)
    parcel_total = float(parcel_query.scalar() or 0)
    budget = float(
        db.session.query(BorrowingTicket.required_budget)
        .filter(BorrowingTicket.id == ticket_id)
        .scalar()
        or 0
    )
    combined_total = return_total + parcel_total
    return {
        "return_total": return_total,
        "parcel_total": parcel_total,
        "cumulative_total": combined_total,
        "budget": budget,
        "remaining_amount": budget - combined_total,
    }


def _calculate_fund_request_totals(fund_request_id, *, exclude_claim_id=None, exclude_parcel_return_id=None):
    claim_query = db.session.query(func.coalesce(func.sum(PettyCashClaimItem.amount), 0)).join(
        PettyCashClaimDetail,
        PettyCashClaimDetail.id == PettyCashClaimItem.claim_id,
    ).filter(
        PettyCashClaimDetail.fund_request_id == fund_request_id,
    )
    if exclude_claim_id:
        claim_query = claim_query.filter(PettyCashClaimDetail.id != exclude_claim_id)

    parcel_query = db.session.query(func.coalesce(func.sum(ParcelReturnDetail.amount_spent), 0)).filter(
        ParcelReturnDetail.fund_request_id == fund_request_id,
        ParcelReturnDetail.status.in_(["พัสดุกำลังดำเนินการ", "ได้รับเอกสารแล้ว"]),
    )
    if exclude_parcel_return_id:
        parcel_query = parcel_query.filter(ParcelReturnDetail.id != exclude_parcel_return_id)

    claim_total = float(claim_query.scalar() or 0)
    parcel_total = float(parcel_query.scalar() or 0)
    request_amount = float(
        db.session.query(FundRequest.amount)
        .filter(FundRequest.id == fund_request_id)
        .scalar()
        or 0
    )
    combined_total = claim_total + parcel_total
    return {
        "claim_total": claim_total,
        "parcel_total": parcel_total,
        "cumulative_total": combined_total,
        "request_amount": request_amount,
        "remaining_amount": request_amount - combined_total,
    }


def _format_currency_amount(amount):
    return f"{float(amount or 0):,.2f}"


def _is_over_limit(projected_total, limit_total):
    return round(float(projected_total or 0), 2) > round(float(limit_total or 0), 2)


def _redirect_with_limit_popup(location, message):
    """Return limit errors to the current page without a redirect."""
    return _validation_error_response(message)


def _is_return_amount_limit_exempt(is_cash):
    return is_cash is True


def _proof_file_validation_error(row_count, *, is_draft):
    """Validate the one-proof-file-per-row rule before saving receipt rows."""
    legacy_files = request.files.getlist("proof_file[]")
    legacy_existing_paths = request.form.getlist("existing_proof_files[]")

    for index in range(row_count):
        uploaded_files = request.files.getlist(f"proof_files_{index}[]")
        if not uploaded_files and index < len(legacy_files):
            uploaded_files = [legacy_files[index]]
        uploaded_files = [file for file in uploaded_files if file and file.filename]

        if len(uploaded_files) > 1:
            return f"แถวที่ {index + 1} แนบไฟล์หลักฐานได้ไม่เกิน 1 ไฟล์"

        existing_paths = request.form.getlist(f"existing_proof_files_{index}[]")
        if not existing_paths and index < len(legacy_existing_paths):
            existing_paths = [legacy_existing_paths[index]] if legacy_existing_paths[index] else []
        existing_paths = [path for path in existing_paths if path]

        if not is_draft and index == 0 and not uploaded_files and not existing_paths:
            return "กรุณาแนบไฟล์หลักฐานในแถวแรกก่อนส่งข้อมูล"

    return None

def _ticket_has_bounced_return(ticket_id):
    return db.session.query(ReturnDetail.id).filter(
        ReturnDetail.ticket_id == ticket_id,
        ReturnDetail.status == RETURN_DETAIL_BOUNCED_STATUS,
    ).first() is not None

def _recalculate_borrowing_ticket_status(ticket_id):
    borrowing_ticket = (
        db.session.query(BorrowingTicket).filter_by(id=ticket_id).first()
    )
    if borrowing_ticket is None:
        return None

    if _ticket_has_bounced_return(ticket_id):
        borrowing_ticket.status = RETURN_DETAIL_BOUNCED_STATUS
        db.session.commit()
        _send_notification_email(borrowing_ticket)
        return borrowing_ticket.status

    old_status = borrowing_ticket.status

    # เรียกใช้ฟังก์ชันคำนวณยอดรวมที่รวมพัสดุแล้ว
    totals = _calculate_ticket_return_totals(ticket_id)
    cumulative_total = totals["cumulative_total"]
    budget = totals["budget"]

    budget_covered = float(cumulative_total) >= float(budget) and float(budget) > 0

    new_status = old_status

    if budget_covered:
        new_status = "เคลียร์ยอดแล้ว"
        borrowing_ticket.closed_date = datetime.now().date()

    elif float(cumulative_total) > 0:
        new_status = "มียอดคงค้าง"

    else:
        if old_status in {"กำลังส่งคำขอ", "อนุมัติจ่ายเงิน", "ปฏิเสธ"}:
            new_status = old_status

    borrowing_ticket.status = new_status
    db.session.commit()

    _send_notification_email(borrowing_ticket)

    return borrowing_ticket.status

def _render_role_selection(selected_role=None, error_message=None):
    staff = _current_module_user()
    if not staff:
        return redirect(url_for("auth.login", next=url_for("advance_payment.login")))

    if request.method == "POST":
        requested_system = (request.form.get("system") or request.form.get("role") or "").strip()
        requested_system, error_message = _ensure_module_role(staff, requested_system)
        if requested_system:
            elevated_role = None
            if requested_system == ADVANCE_PAYMENT_SYSTEM and COORDINATOR_ROLE in _available_module_roles(staff):
                elevated_role = COORDINATOR_ROLE
            elif requested_system == PETTY_CASH_SYSTEM and SECRETARY_ROLE in _available_module_roles(staff):
                elevated_role = SECRETARY_ROLE
            elif requested_system == FINANCE_SYSTEM:
                elevated_role = FINANCE_SYSTEM
            _set_selected_system(requested_system)
            return redirect(url_for(_dashboard_endpoint_for_role(elevated_role)))

    return render_template(
        "index.html",
        available_roles=AVAILABLE_SYSTEMS,
        role_labels=MODULE_ROLE_LABELS,
        selected_role=selected_role,
        current_email=getattr(staff, "email", None),
        error_message=error_message,
    )


@bp.route("/", methods=["GET", "POST"])
@bp.route("/login", methods=["GET", "POST"])
def login(role=None):
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.url))

    requested_role = role or request.values.get("system") or request.values.get("role") or request.values.get("login_path")
    return _render_role_selection(selected_role=requested_role)


@bp.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    return login(role=PETTY_CASH_SYSTEM)


@bp.route("/custodian/login", methods=["GET", "POST"])
def custodian_login():
    return login(role=PETTY_CASH_SYSTEM)


@bp.route("/finance/login", methods=["GET", "POST"])
def finance_login():
    return login(role=FINANCE_SYSTEM)


@bp.route("/logout")
def logout():
    # These pops are a one-time cleanup for legacy Advance Payment sessions;
    # authentication itself is managed by Flask-Login.
    session.pop("user_id", None)
    session.pop("user_email", None)
    session.pop("user_role", None)
    session.pop("advance_payment_system", None)
    flash("ออกจากระบบ Advance Payment เรียบร้อยแล้ว")
    if current_user.is_authenticated:
        return redirect(url_for("advance_payment.login"))
    return redirect(url_for("auth.login"))

@bp.route("/coordinator/dashboard", methods=["GET", "POST"], endpoint="coordinator_dashboard")
@bp.route("/borrower/dashboard", methods=["GET", "POST"], endpoint="borrower_dashboard")
@module_system_required(ADVANCE_PAYMENT_SYSTEM)
def coordinator_dashboard():
    user_id = current_user.id
    user_role = _current_module_role()
    is_borrower_mode = (
        request.endpoint == "advance_payment.borrower_dashboard"
        or not _can_use_coordinator_dashboard()
    )
    dashboard_endpoint = (
        "advance_payment.borrower_dashboard"
        if is_borrower_mode
        else "advance_payment.coordinator_dashboard"
    )
    staff = current_user

    # ผู้ยืมเห็นเฉพาะของตัวเอง ส่วนผู้ประสานงานยังเลือกแทนคนอื่นได้
    if is_borrower_mode:
        dept_users = [staff]
    else:
        dept_users = _get_coordinator_dashboard_users(staff)
        dept_users.sort(key=lambda user: (user.email or "").lower())
    if not dept_users:
        dept_users = [staff]

    coordinator_user_ids = [user.id for user in dept_users if user.id]
    coordinator_tickets = (
        db.session.query(BorrowingTicket)
        .filter(BorrowingTicket.borrower_id.in_(coordinator_user_ids))
        .all()
        if coordinator_user_ids
        else []
    )
    tickets_by_email = {}
    for ticket in coordinator_tickets:
        tickets_by_email.setdefault((ticket.borrower_email or "").strip().lower(), []).append(ticket)

    eligibility_by_email = {}
    for user in dept_users:
        user_email = (user.email or "").strip().lower()
        eligibility_by_email[user_email] = calculate_borrowing_ticket_eligibility(
            tickets_by_email.get(user_email, []),
            user.email,
        )
        user.is_eligible = eligibility_by_email[user_email].is_eligible
        user.ineligible_reason = ", ".join(
            eligibility_by_email[user_email].blocking_statuses
        )

    # ผู้ยืมต้องเห็นสัญญาที่ผูกกับตัวเองผ่าน borrower_id
    # ผู้ประสานงานยังคงเห็นสัญญาที่ตนเป็นผู้สร้างผ่าน creator_id
    ticket_owner_column = BorrowingTicket.borrower_id if is_borrower_mode else BorrowingTicket.creator_id
    borrowing_ticket_history = (
        db.session.query(BorrowingTicket)
        .filter(ticket_owner_column == current_user.id)
        .order_by(BorrowingTicket.id.desc())
        .all()
    )

    actionable_tickets = []
    if is_borrower_mode:
        current_org_id = getattr(_get_staff_org(current_user), "id", None)
        if current_org_id:
            actionable_tickets = (
                db.session.query(BorrowingTicket)
                .join(StaffAccount, StaffAccount.id == BorrowingTicket.borrower_id)
                .join(StaffPersonalInfo, StaffPersonalInfo.id == StaffAccount.personal_id)
                .filter(
                    StaffPersonalInfo.org_id == current_org_id,
                    BorrowingTicket.status.in_(["อนุมัติจ่ายเงิน", "มียอดคงค้าง"]),
                )
                .order_by(BorrowingTicket.id.desc())
                .all()
            )

    tickets_with_return_forms = list({
        ticket.id: ticket
        for ticket in borrowing_ticket_history + actionable_tickets
    }.values())
    for ticket in tickets_with_return_forms:
        draft_detail = (
            db.session.query(ReturnDetail)
            .filter_by(ticket_id=ticket.id, status="ฉบับร่าง")
            .first()
        )
        ticket.draft_detail = draft_detail
        if draft_detail:
            ticket.draft_items = (
                db.session.query(ReturnReceiptItem)
                .filter_by(return_detail_id=draft_detail.id)
                .all()
            )
            for item in ticket.draft_items:
                item.proof_file = (
                    db.session.query(ReturnProofFile)
                    .filter_by(return_receipt_item_id=item.id)
                    .first()
                )
            ticket.draft_announcements = _prepare_document_display_list(draft_detail.documents)
        else:
            ticket.draft_items = []
            ticket.draft_announcements = []

    # ดึงรายการส่งใช้เงินยืม (ReturnDetail) ของสัญญาที่ผู้เข้าสู่ระบบเป็นผู้สร้าง
    ticket_ids = [t.id for t in borrowing_ticket_history]
    if ticket_ids:
        return_details = (
            db.session.query(ReturnDetail)
            .filter(
                ReturnDetail.ticket_id.in_(ticket_ids),
                ReturnDetail.status != "ฉบับร่าง"
            )
            .order_by(ReturnDetail.id.desc())
            .all()
        )
    else:
        return_details = []

    # รายการแยกตามผู้สร้าง ReturnDetail โดยตรง ไม่ผูกกับผู้สร้างสัญญา/ผู้ยืม
    creator_return_details = (
        db.session.query(ReturnDetail)
        .filter(
            ReturnDetail.creator_id == current_user.id,
            ReturnDetail.status != "ฉบับร่าง",
        )
        .order_by(ReturnDetail.id.desc())
        .all()
    )
    for return_detail in creator_return_details:
        numbered_descriptions = []
        for item in return_detail.receipt_items:
            desc = (item.description or "").strip()
            if desc:
                numbered_descriptions.append(desc)

        if numbered_descriptions:
            preview_items = numbered_descriptions[:3]
            if len(numbered_descriptions) > 3:
                preview_items.append("...")
            return_detail.description = ", ".join(preview_items)
        else:
            return_detail.description = return_detail.proof_reference or "-"

    rejected_followup_ticket_ids = {item.ticket_id for item in return_details if (item.status or "").strip() == "ปฏิเสธ"}
    if ticket_ids:
        rejected_followup_ticket_ids.update(
            ticket_id
            for (ticket_id,) in db.session.query(ParcelReturnDetail.ticket_id)
            .filter(
                ParcelReturnDetail.ticket_id.in_(ticket_ids),
                ParcelReturnDetail.status == "ปฏิเสธ",
            )
            .all()
            if ticket_id is not None
        )
        rejected_followup_ticket_ids.update(
            ticket_id
            for (ticket_id,) in db.session.query(FundRequest.borrowing_ticket_id)
            .join(PettyCashClaimDetail, PettyCashClaimDetail.fund_request_id == FundRequest.id)
            .filter(
                FundRequest.borrowing_ticket_id.in_(ticket_ids),
                PettyCashClaimDetail.status == "ปฏิเสธ",
            )
            .all()
            if ticket_id is not None
        )

    today_date = datetime.now().date()
    shadow_sum_debt = 0.0
    summary_days_remaining = None
    summary_overdue_days = None

    for ticket in borrowing_ticket_history:
        ticket.summary_overdue_days = None
        ticket.summary_days_remaining = None

        totals = _calculate_ticket_return_totals(ticket.id)
        ticket_display_totals = _calculate_ticket_return_totals_with_parcel(
            ticket.id,
            exclude_return_id=ticket.draft_detail.id if ticket.draft_detail else None,
        )
        ticket.parcel_return_total = ticket_display_totals["parcel_total"]
        ticket.submitted_return_total = ticket_display_totals["cumulative_total"]
        ticket_remaining = totals["remaining_amount"]
        ticket.ticket_remaining = ticket_remaining
        ticket.has_rejected_followup = ticket.id in rejected_followup_ticket_ids

        if ticket.status not in ["เอกสารตั้งฎีกา", "เคลียร์ยอดแล้ว", "ปฏิเสธ", "กำลังส่งคำขอ"]:
            shadow_sum_debt += float(ticket_remaining if ticket_remaining > 0 else 0.0)

            if ticket.due_date:
                if today_date > ticket.due_date:
                    overdue = (today_date - ticket.due_date).days
                    ticket.summary_overdue_days = overdue
                    if summary_overdue_days is None or overdue > summary_overdue_days:
                        summary_overdue_days = overdue
                else:
                    rem = (ticket.due_date - today_date).days
                    ticket.summary_days_remaining = rem
                    if summary_days_remaining is None or rem < summary_days_remaining:
                        summary_days_remaining = rem

    history_ticket_ids = {ticket.id for ticket in borrowing_ticket_history}
    for ticket in actionable_tickets:
        if ticket.id in history_ticket_ids:
            continue
        ticket_display_totals = _calculate_ticket_return_totals_with_parcel(
            ticket.id,
            exclude_return_id=ticket.draft_detail.id if ticket.draft_detail else None,
        )
        ticket.parcel_return_total = ticket_display_totals["parcel_total"]
        ticket.submitted_return_total = ticket_display_totals["cumulative_total"]
        ticket.ticket_remaining = _calculate_ticket_return_totals(ticket.id)["remaining_amount"]

    if request.method == "POST":
        post_data = request.form.copy()
        if "required_budget" in post_data:
            post_data["required_budget"] = post_data["required_budget"].replace(",", "")
        form = BorrowingTicketForm(post_data)
    else:
        form = BorrowingTicketForm(request.form)

    form.borrower_email.choices = [
        ("", f"โปรดเลือก{_dashboard_party_label(user_role)}")
    ] + [
        (user.email, user.email)
        for user in dept_users
        if user.email
    ]

    current_user_email = (current_user.email or "").strip().lower()
    current_user_eligibility = eligibility_by_email.get(current_user_email)

    # ตรวจสอบสิทธิ์เบื้องต้นของผู้ใช้งานปัจจุบัน
    # Do not lock based on the creator; the selected borrower controls eligibility.
    form_locked = bool(
        is_borrower_mode
        and current_user_eligibility is not None
        and not current_user_eligibility.is_eligible
    )

    if request.method == "POST":
        if is_borrower_mode and form_locked:
            return _validation_error_response(
                "คุณยังไม่สามารถสร้างสัญญาเงินยืมใหม่ได้ เนื่องจากมีรายการค้างที่ต้องดำเนินการก่อน"
            )

        # ผู้ยืมสร้างได้เฉพาะของตัวเอง ส่วนผู้ประสานงานเลือกแทนได้
        selected_coordinator_email = (
            (current_user.email or "").strip().lower()
            if is_borrower_mode
            else request.form.get("borrower_email", "").strip().lower()
        )
        if not selected_coordinator_email:
            return _validation_error_response(
                f"กรุณาเลือก{_dashboard_party_label(user_role)}ก่อนสร้างสัญญาเงินยืม"
            )

        coordinator_user = (
            db.session.query(StaffAccount)
            .filter_by(email=selected_coordinator_email)
            .first()
        )

        if not coordinator_user:
            return _validation_error_response(
                f"ไม่พบข้อมูล{_dashboard_party_label(user_role)}ที่ระบุในระบบ"
            )

        allowed_coordinator_emails = {
            user.email.strip().lower()
            for user in dept_users
            if user.email
        }
        if coordinator_user.email.strip().lower() not in allowed_coordinator_emails:
            return _validation_error_response(
                f"ไม่พบ{_dashboard_party_label(user_role)}ที่ระบุในระบบ"
            )

        # ตรวจสอบสิทธิ์ความสามารถในการยืมเงินของผู้ยืมจริง (Borrower) ด้วย calculate_borrowing_ticket_eligibility
        coordinator_eligibility = eligibility_by_email.get(
            (coordinator_user.email or "").strip().lower()
        )

        if not coordinator_eligibility.is_eligible:
            # หากผู้ยืมไม่ผ่านเงื่อนไข ระบบจะแจ้งเตือนและไม่อนุญาตให้สร้างสัญญา
            return _validation_error_response(
                f"ไม่สามารถสร้างสัญญาแทนได้: {coordinator_user.name} ไม่ผ่านเงื่อนไขการยืมเงินทดรองจ่าย "
                f"(สถานะที่ยังค้างอยู่: {', '.join(coordinator_eligibility.blocking_statuses)})"
            )

        if form.validate():
            # บันทึกผู้สร้างสัญญาและผู้ยืมจริงแยกกันด้วย creator_id / borrower_id
            selected_account_number = (form.account_number.data or "").strip()
            selected_bank_account = _get_bank_account_info(
                bank_account_info_id=request.form.get("bank_account_info_id"),
                account_number=selected_account_number,
            )
            if selected_bank_account:
                selected_account_number = selected_bank_account.account_number
            elif selected_account_number:
                return _validation_error_response(
                    "เลขที่บัญชีนี้ถูกปิดแล้วหรือไม่อยู่ในรายการที่เลือกได้"
                )

            if request.form.get("validation_only") == "1":
                return jsonify(ok=True)

            if selected_bank_account:
                new_ticket = BorrowingTicket(
                    creator_id=current_user.id,
                    borrower_id=coordinator_user.id,
                    borrowing_ticket_purpose=form.borrowing_ticket_purpose.data.strip(),
                    required_budget=form.required_budget.data,
                    account_number=selected_account_number,
                    bank_account_info_id=selected_bank_account.id if selected_bank_account else None,
                    borrowing_ticket_start_date=form.borrowing_ticket_start_date.data,
                    borrowing_ticket_end_date=form.borrowing_ticket_end_date.data,
                    due_date=_calculate_due_date(form.borrowing_ticket_end_date.data),
                    aip_ref_no=form.aip_ref_no.data,
                    aip_ref_date=form.aip_ref_date.data,
                    status="กำลังส่งคำขอ",
                    created_at=datetime.utcnow()
                )
                new_ticket.creator_user = current_user
                new_ticket.borrower_user = coordinator_user
                db.session.add(new_ticket)
                try:
                    db.session.flush()
                    db.session.commit()
                    db.session.refresh(new_ticket)
                except IntegrityError:
                    db.session.rollback()
                    return _validation_error_response(
                        "ไม่สามารถบันทึกสัญญาเงินยืมได้ เนื่องจากข้อมูลซ้ำหรือไม่สอดคล้องกับข้อมูลในระบบ"
                    )

                flash(f"สร้างสัญญาเงินยืมทดรองจ่ายแทน {coordinator_user.name} เรียบร้อยแล้ว", "success")
                _send_notification_email(new_ticket)
                # Render the newly-created ticket immediately instead of leaving
                # the user on the dashboard with the old form still visible.
                return verification_view(new_ticket.id)
        form_errors = "; ".join(
            ", ".join(errors)
            for errors in form.errors.values()
        )
        return _validation_error_response(form_errors or "ข้อมูลไม่ครบหรือไม่ถูกต้อง")

    dashboard_template = "borrower_dashboard.html" if is_borrower_mode else "coordinator_dashboard.html"
    bank_account_options = _get_bank_account_dropdown_options()
    bank_account_values = [option["value"] for option in bank_account_options]
    dashboard_party_label = (
        "ผู้ประสานงาน"
        if not is_borrower_mode
        else _dashboard_party_label(user_role)
    )
    dashboard_party_scope = (
        "เฉพาะหน่วยงาน"
        if user_role == SECRETARY_ROLE and not is_borrower_mode
        else "เฉพาะตัวเอง" if is_borrower_mode else "บุคลากรทั้งองค์กร"
    )

    return render_template(
        dashboard_template,
        dashboard_title="แดชบอร์ดผู้ยืม" if is_borrower_mode else f"แดชบอร์ด{dashboard_party_label}",
        dashboard_role="Borrower" if is_borrower_mode else "Coordinator",
        dashboard_party_label=dashboard_party_label,
        dashboard_party_scope=dashboard_party_scope,
        dashboard_can_choose_proxy=not is_borrower_mode,
        dashboard_is_coordinator=_can_use_coordinator_dashboard(),
        borrowing_ticket_history=borrowing_ticket_history,
        return_details=return_details,
        creator_return_details=creator_return_details,
        borrowing_ticket_form=form,
        borrowing_ticket_form_locked=form_locked,
        bank_account_options=bank_account_options,
        bank_account_values=bank_account_values,
        shadow_sum_debt=shadow_sum_debt,
        summary_days_remaining=summary_days_remaining,
        summary_overdue_days=summary_overdue_days,
        dept_users=dept_users,
        current_user=current_user,
        actionable_tickets=actionable_tickets,
        pdf_reference_options=_pdf_reference_options(),
        pdf_fiscal_year_default=convert_to_fiscal_year(datetime.now().date()),
    )

@bp.route("/coordinator/ticket/<int:ticket_id>/pdf", endpoint="coordinator_ticket_pdf")
@bp.route("/borrower/ticket/<int:ticket_id>/pdf", endpoint="borrower_ticket_pdf")
@bp.route("/coordinator/ticket/<int:ticket_id>/pdf", endpoint="export_ticket_pdf")
@module_system_required(ADVANCE_PAYMENT_SYSTEM)
def export_ticket_pdf(ticket_id):
    ticket = db.session.query(BorrowingTicket).get(ticket_id)
    if not ticket:
        abort(404)

    if _selected_system() == ADVANCE_PAYMENT_SYSTEM and (
        (not _is_current_coordinator() and ticket.borrower_id != _current_user_id())
        or (_is_current_coordinator() and ticket.creator_id != _current_user_id())
    ):
        abort(403)

    pdf_bytes = generate_fnar02_pdf(ticket)

    response = current_app.response_class(pdf_bytes, mimetype='application/pdf')
    response.headers['Content-Disposition'] = f'attachment; filename=FNAR02_Ticket_{ticket_id}.pdf'
    return response

@bp.route("/finance/dashboard")
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def finance_dashboard():
    borrowing_tickets = db.session.query(BorrowingTicket).order_by(BorrowingTicket.id.desc()).all()
    return_details = (
        db.session.query(ReturnDetail)
        .filter(ReturnDetail.status != "ฉบับร่าง")
        .order_by(ReturnDetail.id.desc())
        .all()
    )
    parcel_returns = (
        db.session.query(ParcelReturnDetail)
        .order_by(ParcelReturnDetail.id.desc())
        .all()
    )

    # -------------------------------------------------------------
    # เพิ่ม: ดึงข้อมูลรายการเบิกเงินสดย่อย (Petty Cash Claims)
    # -------------------------------------------------------------
    petty_cash_claims = (
        db.session.query(PettyCashClaimDetail)
        .order_by(PettyCashClaimDetail.id.desc())
        .all()
    )
    petty_cash_claims = [
        claim for claim in petty_cash_claims
        if not _claim_has_only_category_six(claim)
    ]

    proofed_return_count = db.session.query(ReturnDetail).filter(ReturnDetail.status == "ผ่านการตรวจสอบ").count()
    proofed_parcel_count = db.session.query(ParcelReturnDetail).filter(ParcelReturnDetail.status == "ได้รับเอกสารแล้ว").count()
    proofed_claims = (
        db.session.query(PettyCashClaimDetail)
        .filter(PettyCashClaimDetail.status == "ผ่านการตรวจสอบ")
        .all()
    )
    proofed_claim_count = sum(
        1 for claim in proofed_claims if not _claim_has_only_category_six(claim)
    )
    proofed_count = proofed_return_count + proofed_parcel_count + proofed_claim_count

    for parcel in parcel_returns:
        _attach_parcel_return_context(parcel)

    return_details_by_ticket = {}
    for item in return_details:
        return_details_by_ticket.setdefault(item.ticket_id, []).append(item)

    for return_item in return_details:
        borrowing_ticket = return_item.borrowing_ticket
        borrower_user = _get_user_by_id(getattr(borrowing_ticket, "borrower_id", None))
        return_item.borrower_name = (
            (borrowing_ticket.borrower_name or getattr(borrower_user, "name", ""))
            if borrowing_ticket else "-"
        )
        return_item.ticket_number = (
            borrowing_ticket.number
            if borrowing_ticket and borrowing_ticket.number is not None
            else (borrowing_ticket.aip_ref_no if borrowing_ticket and borrowing_ticket.aip_ref_no else "-")
        )

    for claim in petty_cash_claims:
        _attach_petty_cash_claim_context(claim)
        fund_request = claim.fund_request
        setting = claim.setting

        claim.requester_name = _fund_request_requester_name(fund_request, getattr(claim.user, "name", "-")) if fund_request else (claim.user.name if claim.user else "-")
        claim.custodian_name = (
            setting.custodian_name
            if setting and setting.custodian_name
            else (setting.custodian_user.name if setting and getattr(setting, "custodian_user", None) else "-")
        )
        claim.claim_number = (
            claim.claim_number
            or (fund_request.ticket_number if fund_request and fund_request.ticket_number else None)
            or f"PC-{claim.id}"
        )

    close_ticket_ready = {
        ticket.id: ticket.status == "เคลียร์ยอดแล้ว" and bool(return_details_by_ticket.get(ticket.id)) and all(item.status == "เอกสารตั้งฎีกา" for item in return_details_by_ticket.get(ticket.id, []))
        for ticket in borrowing_tickets
    }

    today_date = datetime.now().date()
    shadow_sum_debt = 0.0

    # ตัวแปรนับจำนวนสัญญาใกล้ครบกำหนด / เลยกำหนดส่ง
    near_due_count = 0
    overdue_count = 0

    # ==========================================
    # 1. ย้าย Logic คำนวณรอบดอกเบี้ยมาไว้นอกลูป
    # ==========================================
    current_year_be = today_date.year + 543 # ปี พ.ศ. (ex. 2569)
    if today_date.month <= 11:
        current_interest_period_key = f"06/{current_year_be}"
    else:
        current_interest_period_key = f"12/{current_year_be}"
    current_interest_period = _format_interest_period_label(current_interest_period_key)

    # ==========================================
    # 2. ลูปคำนวณตั๋วยืมคงเหลือ และนับจำนวนสัญญา
    # ==========================================
    for ticket in borrowing_tickets:
        raw_status = (ticket.status or "").strip()
        ticket.calculated_days_remaining = None
        ticket.calculated_overdue_days = None

        if ticket.due_date:
            if today_date > ticket.due_date:
                ticket.calculated_overdue_days = (today_date - ticket.due_date).days
                # ถ้ายังไม่ปิดสัญญา และเลยกำหนด ให้เพิ่มนับจำนวน
                if raw_status not in ["เอกสารตั้งฎีกา", "เคลียร์ยอดแล้ว", "ปฏิเสธ", "กำลังส่งคำขอ", "รออนุมัติสัญญา", "รอตรวจสอบ"]:
                    overdue_count += 1
            else:
                ticket.calculated_days_remaining = (ticket.due_date - today_date).days
                # ถ้าเหลือวันน้อยกว่าหรือเท่ากับ 15 วัน และยังไม่ปิดสัญญา
                if 0 <= ticket.calculated_days_remaining <= 15 and raw_status not in ["เอกสารตั้งฎีกา", "เคลียร์ยอดแล้ว", "ปฏิเสธ", "กำลังส่งคำขอ", "รอตรวจสอบ"]:
                    near_due_count += 1

        totals = _calculate_ticket_return_totals(ticket.id)
        ticket_remaining = totals["remaining_amount"]

        if raw_status not in ["เอกสารตั้งฎีกา", "เคลียร์ยอดแล้ว", "ปฏิเสธ", "กำลังส่งคำขอ", "รอตรวจสอบ"]:
            shadow_sum_debt += float(ticket_remaining if ticket_remaining > 0 else 0.0)

    # ==========================================
    # 3. ดึง PettyCashSetting ที่ active/valid
    # ==========================================
    active_settings = db.session.query(PettyCashSetting).filter(
        PettyCashSetting.valid == True,
        PettyCashSetting.fiscal_year == _current_petty_cash_fiscal_year(),
    ).all()
    for setting in active_settings:
        _attach_petty_cash_setting_people(setting)

    # ==========================================
    # 4. ดึง FundRequest (ฟอร์ม 31) มาตรวจสอบ
    # ==========================================
    approved_interest_requests = db.session.query(FundRequest).filter(
        FundRequest.form_type == FUND_REQUEST_FORM_INTEREST,
    ).all()

    matched_requests = []
    for fr in approved_interest_requests:
        if _normalize_interest_period_value(fr.period_year) == current_interest_period_key:
            matched_requests.append(fr)

    submitted_org_ids = {fr.org_id for fr in matched_requests if getattr(fr, "org_id", None)}

    pending_interest_departments = []
    for setting in active_settings:
        is_submitted = setting.org_id in submitted_org_ids
        custodian = setting.custodian_name or (setting.custodian_user.name if getattr(setting, "custodian_user", None) else None) or '-'

        dept_info = {
            "id": setting.id,
            "department_name": setting.department_name,
            "account_number": setting.account_number or '-',
            "custodian_name": custodian,
            "is_submitted": is_submitted,
            "is_pending": not is_submitted,
            "pending_period": current_interest_period,
            "status_label": "ส่งแล้ว" if is_submitted else "ค้างส่ง"
        }
        pending_interest_departments.append(dept_info)

    pending_interest_count = sum(1 for d in pending_interest_departments if d["is_pending"])

    return render_template(
        "finance_dashboard.html",
        dashboard_title="รายการรอตรวจสอบ",
        dashboard_role="Finance",
        borrowing_tickets=borrowing_tickets,
        return_details=return_details,
        parcel_returns=parcel_returns,
        petty_cash_claims=petty_cash_claims,  # <--- ส่งเพิ่ม
        return_details_by_ticket=return_details_by_ticket,
        close_ticket_ready=close_ticket_ready,
        today=today_date,
        proofed_count=proofed_count,
        shadow_sum_debt=shadow_sum_debt,
        near_due_count=near_due_count,        # <--- ส่งเพิ่ม
        overdue_count=overdue_count,          # <--- ส่งเพิ่ม
        current_interest_period=current_interest_period,
        pending_interest_departments=pending_interest_departments,
        pending_interest_count=pending_interest_count
    )

@bp.route("/finance/documents/<file_id>/download", methods=["GET"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def cash_mng_document_download(file_id):
    return _download_cash_mng_document(file_id)


@bp.route("/finance/bank-accounts", methods=["GET", "POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def finance_bank_account_registry(_render_after_post=False):
    show_editor = request.method == "POST" and not _render_after_post
    form = BankAccountInfoForm()
    form.record_type.choices = list(BANK_ACCOUNT_TYPE_LABELS.items())

    def _parse_bank_account_closed_at(raw_value):
        value = (raw_value or "").strip()
        if not value:
            return None
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return None


    if request.method == "POST" and not _render_after_post:
        if request.form.get("edit_mode") != "1":
            return _validation_error_response("กรุณากดแก้ไขข้อมูลบัญชีธนาคารก่อน")

        row_ids = request.form.getlist("record_id[]")
        row_types = request.form.getlist("record_type[]")
        row_org_ids = request.form.getlist("org_id[]")
        row_thai_names = request.form.getlist("thai_name[]")
        row_closed_ats = request.form.getlist("closed_at[]")
        row_account_numbers = request.form.getlist("account_number[]")

        errors = []
        processed = 0
        existing_accounts = db.session.query(BankAccountInfo).all()
        submitted_account_numbers = {}

        for index, (raw_id, raw_type, raw_org_id, raw_thai, raw_closed_at, raw_account) in enumerate(
            zip(row_ids, row_types, row_org_ids, row_thai_names, row_closed_ats, row_account_numbers),
            start=1,
        ):
            record_type = (raw_type or "").strip()
            org_id = int(raw_org_id) if (raw_org_id or "").strip().isdigit() else None
            thai_name = (raw_thai or "").strip()
            closed_at = _parse_bank_account_closed_at(raw_closed_at)
            account_number = (raw_account or "").strip()
            record_id = (raw_id or "").strip()
            account_digits = account_number

            if not any([record_type, org_id, thai_name, closed_at, account_number, record_id]):
                continue

            if raw_closed_at and closed_at is None:
                errors.append(f"แถวที่ {index} กรุณาระบุวันที่ปิดบัญชีให้ถูกต้อง")
                continue

            if not all([record_type, org_id, thai_name, account_number]):
                errors.append(f"แถวที่ {index} กรุณากรอกข้อมูลให้ครบทุกช่อง")
                continue

            if not re.fullmatch(r"[0-9]{10}", account_number):
                errors.append(f"แถวที่ {index} เลขที่บัญชีต้องเป็นตัวเลขติดกัน 10 หลักเท่านั้น เช่น 1234567890")
                continue

            duplicate_id = submitted_account_numbers.get(account_digits)
            if duplicate_id is not None and str(duplicate_id) != record_id:
                errors.append(f"แถวที่ {index} เลขที่บัญชีซ้ำกับข้อมูลในแบบฟอร์ม")
                continue

            duplicate_record = next(
                (
                    record for record in existing_accounts
                    if str(record.id) != record_id
                    and (record.account_number or "") == account_digits
                ),
                None,
            )
            # An unchanged row must not be reported as a duplicate of itself.
            # This also keeps legacy data (created before the unique constraint
            # was enforced) editable when another old row has the same number.
            current_record = next(
                (record for record in existing_accounts if str(record.id) == record_id),
                None,
            )
            unchanged_account_number = (
                current_record is not None
                and (current_record.account_number or "").strip() == account_digits
            )
            if duplicate_record and not unchanged_account_number:
                errors.append(f"แถวที่ {index} เลขที่บัญชีนี้มีอยู่ในระบบแล้ว")
                continue

            submitted_account_numbers[account_digits] = record_id or f"new-{index}"

            if record_id:
                record = db.session.query(BankAccountInfo).filter_by(id=int(record_id)).first()
                if record is None:
                    errors.append(f"แถวที่ {index} ไม่พบรายการเดิมสำหรับแก้ไข")
                    continue
                record.record_type = record_type
                record.org_id = org_id
                record.thai_name = thai_name
                record.closed_at = closed_at
                record.account_number = account_number
            else:
                db.session.add(
                    BankAccountInfo(
                        record_type=record_type,
                        org_id=org_id,
                        thai_name=thai_name,
                        closed_at=closed_at,
                        account_number=account_number,
                    )
                )
            processed += 1

        if errors:
            db.session.rollback()
            return _validation_error_response("; ".join(errors))
        elif processed > 0:
            db.session.commit()
            flash("บันทึกข้อมูลบัญชีธนาคารเรียบร้อยแล้ว", "success")
            return finance_bank_account_registry(_render_after_post=True)
        else:
            return _validation_error_response("ไม่มีข้อมูลที่ต้องบันทึก")

    records = (
        db.session.query(BankAccountInfo)
        .order_by(BankAccountInfo.record_type.asc(), BankAccountInfo.thai_name.asc())
        .all()
    )

    org_options = db.session.query(Org).filter(Org.name.isnot(None)).order_by(Org.name.asc()).all()

    if request.method == "POST":
        edit_rows = []
        for raw_id, raw_type, raw_org_id, raw_thai, raw_closed_at, raw_account in zip(
            request.form.getlist("record_id[]"),
            request.form.getlist("record_type[]"),
            request.form.getlist("org_id[]"),
            request.form.getlist("thai_name[]"),
            request.form.getlist("closed_at[]"),
            request.form.getlist("account_number[]"),
        ):
            edit_rows.append(
                {
                    "id": raw_id,
                    "record_type": raw_type,
                    "org_id": int(raw_org_id) if (raw_org_id or "").isdigit() else None,
                    "org_name": next(
                        (org.name for org in org_options if str(org.id) == str(raw_org_id)),
                        "",
                    ),
                    "thai_name": raw_thai,
                    "closed_at": raw_closed_at,
                    "account_number": raw_account,
                }
            )
    else:
        edit_rows = [
            {
                "id": record.id,
                "record_type": record.record_type,
                "org_id": record.org_id,
                "org_name": record.org.name if record.org else "",
                "thai_name": record.thai_name,
                "closed_at": record.closed_at,
                "account_number": record.account_number,
            }
            for record in records
        ]

    return render_template(
        "bank_account_registry.html",
        dashboard_title="จัดการข้อมูลบัญชีธนาคาร",
        dashboard_role="Finance",
        form=form,
        records=records,
        edit_rows=edit_rows,
        bank_account_type_labels=BANK_ACCOUNT_TYPE_LABELS,
        org_options=org_options,
        total_records=len(records),
        show_editor=show_editor,
    )

@bp.route("/finance/tickets", methods=["GET"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def tickets_view():
    filter_type = request.args.get("filter", "").strip()
    today_date = datetime.now().date()
    org_options = db.session.query(Org).order_by(Org.name.asc()).all()

    # Query ข้อมูลตั๋วเงินยืมทั้งหมด
    query = db.session.query(BorrowingTicket).order_by(BorrowingTicket.id.desc())
    all_tickets = query.all()

    ticket_ids = [ticket.id for ticket in all_tickets]
    rejected_followup_ticket_ids = set()
    if ticket_ids:
        rejected_followup_ticket_ids.update(
            ticket_id
            for (ticket_id,) in db.session.query(ReturnDetail.ticket_id)
            .filter(
                ReturnDetail.ticket_id.in_(ticket_ids),
                ReturnDetail.status == "ปฏิเสธ",
            )
            .all()
            if ticket_id is not None
        )
        rejected_followup_ticket_ids.update(
            ticket_id
            for (ticket_id,) in db.session.query(ParcelReturnDetail.ticket_id)
            .filter(
                ParcelReturnDetail.ticket_id.in_(ticket_ids),
                ParcelReturnDetail.status == "ปฏิเสธ",
            )
            .all()
            if ticket_id is not None
        )
        rejected_followup_ticket_ids.update(
            ticket_id
            for (ticket_id,) in db.session.query(FundRequest.borrowing_ticket_id)
            .join(PettyCashClaimDetail, PettyCashClaimDetail.fund_request_id == FundRequest.id)
            .filter(
                FundRequest.borrowing_ticket_id.in_(ticket_ids),
                PettyCashClaimDetail.status == "ปฏิเสธ",
            )
            .all()
            if ticket_id is not None
        )

    for ticket in all_tickets:
        ticket.has_rejected_followup = ticket.id in rejected_followup_ticket_ids

    ticket_summary_excluded_statuses = {
        "เอกสารตั้งฎีกา",
        "เคลียร์ยอดแล้ว",
        "ปฏิเสธ",
        "กำลังส่งคำขอ",
        "รออนุมัติสัญญา",
        "รอตรวจสอบ",
    }

    near_due_count = 0
    overdue_count = 0
    shadow_sum_debt = 0.0

    for ticket in all_tickets:
        borrower_user = getattr(ticket, "borrower_user", None)
        ticket_org = _get_staff_org(borrower_user)
        ticket.search_org_id = getattr(ticket_org, "id", None)
        ticket.search_org_name = getattr(ticket_org, "name", None) or getattr(ticket_org, "en_name", None) or ""
        ticket.search_account_name, ticket.search_account_number = _bank_account_search_info(
            getattr(ticket, "bank_account_info", None)
        )
        if not ticket.search_account_number:
            ticket.search_account_number = ticket.account_number or ""
        raw_status = (ticket.status or "").strip()
        if ticket.due_date:
            if today_date > ticket.due_date:
                if raw_status not in ticket_summary_excluded_statuses:
                    overdue_count += 1
            else:
                days_remaining = (ticket.due_date - today_date).days
                if 0 <= days_remaining <= 15 and raw_status not in ticket_summary_excluded_statuses:
                    near_due_count += 1

        if raw_status not in ticket_summary_excluded_statuses:
            shadow_sum_debt += float(ticket.required_budget or 0.0)

    # กรองข้อมูลตาม filter ที่ส่งมาจาก Dashboard
    if filter_type == "near_due":
        tickets = [
            t for t in all_tickets
            if t.status not in ticket_summary_excluded_statuses
            and t.due_date
            and 0 <= (t.due_date - today_date).days <= 15
        ]
    elif filter_type == "overdue":
        tickets = [
            t for t in all_tickets
            if t.status not in ticket_summary_excluded_statuses
            and t.due_date
            and today_date > t.due_date
        ]
    elif filter_type == "pending_debt":
        tickets = [
            t for t in all_tickets
            if t.status not in ticket_summary_excluded_statuses
        ]
    else:
        tickets = all_tickets

    # =========================================================================
    # เพิ่มส่วนนี้: คำนวณวันคงเหลือ / วันเกินกำหนด สำหรับทุก ticket ที่นำไปแสดงผล
    # =========================================================================
    for ticket in tickets:
        ticket.calculated_days_remaining = None
        ticket.calculated_overdue_days = None

        if ticket.due_date:
            if today_date > ticket.due_date:
                ticket.calculated_overdue_days = (today_date - ticket.due_date).days
            else:
                ticket.calculated_days_remaining = (ticket.due_date - today_date).days

    return render_template(
        "tickets_view.html",
        tickets=tickets,
        active_filter=filter_type,
        dashboard_role="Finance",
        near_due_count=near_due_count,
        overdue_count=overdue_count,
        shadow_sum_debt=shadow_sum_debt,
        org_options=org_options,
    )

@bp.route("/tickets/<int:ticket_id>/verification")
@module_system_required({ADVANCE_PAYMENT_SYSTEM, FINANCE_SYSTEM})
def verification_view(ticket_id):
    user_role = _current_module_role()
    if _selected_system() not in {ADVANCE_PAYMENT_SYSTEM, FINANCE_SYSTEM}:
        return redirect(url_for("advance_payment.login"))

    borrowing_ticket = (
        db.session.query(BorrowingTicket).filter_by(id=ticket_id).first()
    )
    if borrowing_ticket is None:
        abort(404)

    if _selected_system() == ADVANCE_PAYMENT_SYSTEM and not _is_current_coordinator() and borrowing_ticket.borrower_id != _current_user_id():
        abort(403)

    return_details = (
        db.session.query(ReturnDetail)
        .filter(
            ReturnDetail.ticket_id == ticket_id,
            ReturnDetail.status != "ฉบับร่าง"
        )
        .order_by(ReturnDetail.id.desc())
        .all()
    )
    parcel_returns = (
        db.session.query(ParcelReturnDetail)
        .filter_by(ticket_id=ticket_id)
        .order_by(ParcelReturnDetail.id.desc())
        .all()
    )

    for return_detail in return_details:
        numbered_descriptions = []
        for item in return_detail.receipt_items:
            desc = (item.description or "").strip()
            if desc:
                numbered_descriptions.append(f"{desc}")

        if numbered_descriptions:
            preview_items = numbered_descriptions[:3]
            if len(numbered_descriptions) > 3:
                preview_items.append("...")
            return_detail.description = ", ".join(preview_items)
        else:
            return_detail.description = return_detail.proof_reference or "-"

    borrowing_ticket.parcel_returns = parcel_returns

    summary = _calculate_ticket_return_totals(ticket_id)
    notifications = None

    proof_files = (
        db.session.query(ReturnProofFile)
        .join(ReturnDetail, ReturnDetail.id == ReturnProofFile.return_detail_id)
        .filter(ReturnDetail.ticket_id == ticket_id)
        .order_by(ReturnProofFile.id.desc())
        .all()
    )
    proof_files_dict = {}
    for proof_file in proof_files:
        proof_files_dict.setdefault(proof_file.return_detail_id, []).append(proof_file)

    return render_template(
        "verification.html",
        borrowing_ticket=borrowing_ticket,
        return_details=return_details,
        parcel_returns=parcel_returns,
        summary=summary,
        notifications=notifications,
        proof_files_dict=proof_files_dict,
        today=datetime.now().date(),
    )

def _create_parcel_return_record(*, ticket_id=None, fund_request_id=None, amount, items_description, sent_date, status="รอตรวจสอบ"):
    parcel_return = ParcelReturnDetail(
        ticket_id=ticket_id,
        fund_request_id=fund_request_id,
        amount_spent=amount,
        items_description=items_description,
        sent_date=sent_date,
        status=status,
        created_at=datetime.now(),
    )
    db.session.add(parcel_return)
    db.session.commit()
    _send_notification_email(parcel_return, object_type="parcel_return")
    if ticket_id:
        _recalculate_borrowing_ticket_status(ticket_id)
    if fund_request_id:
        _recalculate_fund_request_submission_status(fund_request_id)
    return parcel_return


def _recalculate_fund_request_submission_status(fund_request_id):
    fund_request = db.session.query(FundRequest).get(fund_request_id)
    if not fund_request:
        return None

    fund_request_status = (fund_request.status or "").strip()
    if fund_request_status not in {
        "อนุมัติแล้ว",
        "ส่งเบิกแล้ว",
        "ส่งเบิกครบแล้ว",
        "เบิกเงินสำเร็จ",
        "เคลียร์ยอดสำเร็จ",
    }:
        return fund_request.status

    claims = (
        db.session.query(PettyCashClaimDetail)
        .filter(
            PettyCashClaimDetail.fund_request_id == fund_request_id,
            PettyCashClaimDetail.status != "ฉบับร่าง",
        )
        .all()
    )

    # total_amount intentionally excludes cat_6. Add its transfer-back amount
    # separately so a claim made only from cat_6 can close the fund request.
    claim_total = sum(float(claim.total_amount or 0) for claim in claims)
    claim_total += sum(
        float(item.amount or 0)
        for claim in claims
        for item in claim.items
        if int(item.category_type or 0) == 6
    )

    # A full submission is not cleared until every payable claim has actually
    # been transferred. A cat_6-only claim is already a completed return and
    # therefore does not wait for a finance transfer.
    pending_claim_transfer = any(
        any(
            int(item.category_type or 0) != 6 and float(item.amount or 0) > 0
            for item in claim.items
        )
        and (claim.status or "").strip()
        not in {"โอนเงินสดย่อยสำเร็จ", "เสร็จสิ้นกระบวนการ"}
        for claim in claims
    )

    parcel_returns = (
        db.session.query(ParcelReturnDetail)
        .filter(
            ParcelReturnDetail.fund_request_id == fund_request_id,
            ParcelReturnDetail.status.not_in(["ปฏิเสธ", "ถูกปฏิเสธ"]),
        )
        .all()
    )
    parcel_total = sum(
        float(parcel.amount_spent or 0)
        for parcel in parcel_returns
        if (parcel.status or "").strip()
        in {"พัสดุกำลังดำเนินการ", "ได้รับเอกสารแล้ว"}
    )
    parcel_not_received = any(
        (parcel.status or "").strip() != "ได้รับเอกสารแล้ว"
        for parcel in parcel_returns
    )

    combined_total = float(claim_total or 0) + float(parcel_total or 0)
    target_total = float(fund_request.amount or 0)

    if round(combined_total, 2) == round(target_total, 2) and target_total > 0:
        # A parcel return must be received before the request can be cleared.
        # While it is still being processed, the amount is already submitted,
        # but the fund request remains at the submission-complete stage.
        fund_request.status = (
            "ส่งเบิกครบแล้ว"
            if pending_claim_transfer or parcel_not_received
            else "เคลียร์ยอดสำเร็จ"
        )
    else:
        fund_request.status = "อนุมัติแล้ว"

    db.session.commit()
    return fund_request.status


@bp.route("/borrower/tickets/<int:ticket_id>/parcel-return", methods=["POST"])
@module_system_required(ADVANCE_PAYMENT_SYSTEM)
def submit_parcel_return(ticket_id):
    borrowing_ticket = db.session.query(BorrowingTicket).filter_by(id=ticket_id).first()
    if borrowing_ticket is None:
        abort(404)
    if not _can_submit_return_detail(_current_user_id(), borrowing_ticket):
        abort(403)

    amount = request.form.get("amount", "0").replace(",", "")
    items_description = request.form.get("items_description", "").strip()
    sent_date_str = request.form.get("sent_date")
    fund_request_id_raw = (request.form.get("fund_request_id") or request.args.get("fund_request_id") or "").strip()
    fund_request_id = int(fund_request_id_raw) if fund_request_id_raw.isdigit() else None

    if not items_description or not sent_date_str:
        return _validation_redirect_response(
            "กรุณากรอกรายละเอียดรายการและวันที่ส่งให้ครบถ้วน",
            url_for("advance_payment.borrower_dashboard"),
        )

    try:
        parsed_amount = float(amount or 0)
    except (TypeError, ValueError):
        return _validation_redirect_response(
            "กรุณาระบุจำนวนเงินให้ถูกต้อง",
            url_for(_dashboard_endpoint_for_role(_current_module_role())),
        )

    ticket_totals = _calculate_ticket_return_totals_with_parcel(ticket_id)
    projected_ticket_total = ticket_totals["cumulative_total"] + parsed_amount
    if _is_over_limit(projected_ticket_total, ticket_totals["budget"]):
        return _redirect_with_limit_popup(
            url_for(_dashboard_endpoint_for_role(_current_module_role())),
            (
                "ยอดรวมเอกสารส่งใช้เงินยืมและส่งคืนพัสดุจะเป็น "
                f"{_format_currency_amount(projected_ticket_total)} บาท "
                f"ซึ่งเกินวงเงิน {_format_currency_amount(ticket_totals['budget'])} บาท"
            ),
        )

    if fund_request_id:
        fund_totals = _calculate_fund_request_totals(fund_request_id)
        projected_fund_total = fund_totals["cumulative_total"] + parsed_amount
        if _is_over_limit(projected_fund_total, fund_totals["request_amount"]):
            return _redirect_with_limit_popup(
                url_for(_dashboard_endpoint_for_role(_current_module_role())),
                (
                    "ยอดรวมใบเบิกเงินสดย่อยและส่งคืนพัสดุจะเป็น "
                    f"{_format_currency_amount(projected_fund_total)} บาท "
                    f"ซึ่งเกินยอดขอเบิก {_format_currency_amount(fund_totals['request_amount'])} บาท"
                ),
            )

    sent_date = datetime.strptime(sent_date_str, "%Y-%m-%d").date()

    try:
        _create_parcel_return_record(
            ticket_id=ticket_id,
            fund_request_id=fund_request_id,
            amount=parsed_amount,
            items_description=items_description,
            sent_date=sent_date,
            status="รอตรวจสอบ",
        )
    except IntegrityError:
        db.session.rollback()
        return _validation_error_response(
            "ไม่สามารถบันทึกรายละเอียดการส่งคืนได้ เนื่องจากข้อมูลไม่สอดคล้องกับข้อมูลในระบบ"
        )

    flash("บันทึกข้อมูลการส่งคืนฝ่ายพัสดุเรียบร้อยแล้ว")
    return verification_view(ticket_id)


@bp.route("/staff/fund-request/<int:fund_request_id>/parcel-return", methods=["GET", "POST"], endpoint="submit_fund_request_parcel_return")
@module_system_required(PETTY_CASH_SYSTEM)
def submit_fund_request_parcel_return(fund_request_id):
    fund_request = db.session.query(FundRequest).filter_by(id=fund_request_id).first()
    if request.method == "GET":
        return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id))

    if fund_request is None:
        return _validation_redirect_response(
            "ไม่พบคำขอที่เลือก",
            url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id),
        )

    amount = request.form.get("amount", "0").replace(",", "")
    items_description = request.form.get("items_description", "").strip()
    sent_date_str = request.form.get("sent_date")

    if not items_description or not sent_date_str:
        return _validation_redirect_response(
            "กรุณากรอกรายละเอียดรายการและวันที่ส่งให้ครบถ้วน",
            url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id),
        )

    try:
        parsed_amount = float(amount or 0)
    except (TypeError, ValueError):
        return _validation_redirect_response(
            "กรุณาระบุจำนวนเงินให้ถูกต้อง",
            url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id),
        )

    ticket_id = getattr(fund_request, "borrowing_ticket_id", None)
    if ticket_id:
        ticket_totals = _calculate_ticket_return_totals_with_parcel(ticket_id)
        projected_ticket_total = ticket_totals["cumulative_total"] + parsed_amount
        if _is_over_limit(projected_ticket_total, ticket_totals["budget"]):
            return _redirect_with_limit_popup(
                url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id),
                (
                    "ยอดรวมเอกสารส่งใช้เงินยืมและส่งคืนพัสดุจะเป็น "
                    f"{_format_currency_amount(projected_ticket_total)} บาท "
                    f"ซึ่งเกินวงเงิน {_format_currency_amount(ticket_totals['budget'])} บาท"
                ),
            )

    fund_totals = _calculate_fund_request_totals(fund_request_id)
    projected_fund_total = fund_totals["cumulative_total"] + parsed_amount
    if _is_over_limit(projected_fund_total, fund_totals["request_amount"]):
        return _redirect_with_limit_popup(
            url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id),
            (
                "ยอดรวมใบเบิกเงินสดย่อยและส่งคืนพัสดุจะเป็น "
                f"{_format_currency_amount(projected_fund_total)} บาท "
                f"ซึ่งเกินยอดขอเบิก {_format_currency_amount(fund_totals['request_amount'])} บาท"
            ),
        )

    sent_date = datetime.strptime(sent_date_str, "%Y-%m-%d").date()

    _create_parcel_return_record(
        fund_request_id=fund_request.id,
        amount=parsed_amount,
        items_description=items_description,
        sent_date=sent_date,
        status="รอตรวจสอบ",
    )

    flash("บันทึกข้อมูลการส่งคืนฝ่ายพัสดุเรียบร้อยแล้ว")
    return submit_petty_cash_claim(
        _render_after_post=True,
        _forced_fund_request_id=fund_request_id,
    )


@bp.route("/coordinator/parcel-returns/<int:parcel_return_id>/edit", methods=["POST"], endpoint="coordinator_parcel_return_edit")
@module_role_required(cash_management_coordinator_permission, COORDINATOR_ROLE, ADVANCE_PAYMENT_SYSTEM)
def update_parcel_return(parcel_return_id):
    parcel_return = db.session.query(ParcelReturnDetail).get(parcel_return_id)
    if not parcel_return:
        abort(404)

    borrowing_ticket = db.session.query(BorrowingTicket).get(parcel_return.ticket_id)
    if borrowing_ticket and borrowing_ticket.creator_id != _current_user_id():
        abort(403)

    current_status = (parcel_return.status or "").strip()
    if current_status not in {"รอตรวจสอบ", "ปฏิเสธ"}:
        return _validation_error_response(
            "สามารถแก้ไขรายการส่งคืนพัสดุได้เฉพาะก่อนฝ่ายการเงินตรวจสอบ หรือหลังถูกปฏิเสธเท่านั้น"
        )

    amount = request.form.get("amount", "0").replace(",", "")
    items_description = request.form.get("items_description", "").strip()
    sent_date_str = request.form.get("sent_date")

    if not items_description or not sent_date_str:
        return _validation_error_response("กรุณากรอกรายละเอียดรายการและวันที่ส่งให้ครบถ้วน")

    try:
        parsed_amount = float(amount or 0)
    except (TypeError, ValueError):
        return _validation_error_response("กรุณาระบุจำนวนเงินให้ถูกต้อง")

    ticket_totals = _calculate_ticket_return_totals_with_parcel(parcel_return.ticket_id, exclude_parcel_return_id=parcel_return.id)
    projected_ticket_total = ticket_totals["cumulative_total"] + parsed_amount
    if _is_over_limit(projected_ticket_total, ticket_totals["budget"]):
        return _redirect_with_limit_popup(
            url_for(_parcel_return_history_fallback(parcel_return)),
            (
                "ยอดรวมเอกสารส่งใช้เงินยืมและส่งคืนพัสดุจะเป็น "
                f"{_format_currency_amount(projected_ticket_total)} บาท "
                f"ซึ่งเกินวงเงิน {_format_currency_amount(ticket_totals['budget'])} บาท"
            ),
        )

    if parcel_return.fund_request_id:
        fund_totals = _calculate_fund_request_totals(parcel_return.fund_request_id, exclude_parcel_return_id=parcel_return.id)
        projected_fund_total = fund_totals["cumulative_total"] + parsed_amount
        if _is_over_limit(projected_fund_total, fund_totals["request_amount"]):
            return _redirect_with_limit_popup(
                url_for(_parcel_return_history_fallback(parcel_return)),
                (
                    "ยอดรวมใบเบิกเงินสดย่อยและส่งคืนพัสดุจะเป็น "
                    f"{_format_currency_amount(projected_fund_total)} บาท "
                    f"ซึ่งเกินยอดขอเบิก {_format_currency_amount(fund_totals['request_amount'])} บาท"
                ),
            )

    parcel_return.amount_spent = parsed_amount
    parcel_return.items_description = items_description
    parcel_return.sent_date = datetime.strptime(sent_date_str, "%Y-%m-%d").date()
    parcel_return.status = "รอตรวจสอบ"
    db.session.commit()
    _send_notification_email(parcel_return, object_type="parcel_return")
    if parcel_return.fund_request_id:
        _recalculate_fund_request_submission_status(parcel_return.fund_request_id)

    _recalculate_borrowing_ticket_status(parcel_return.ticket_id)

    flash("แก้ไขรายการส่งคืนพัสดุเรียบร้อยแล้ว", "success")
    return verification_view(parcel_return.ticket_id)

@bp.route("/finance/parcel-returns/<int:parcel_return_id>/proofed", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def mark_parcel_proofed(parcel_return_id):
    parcel_return = db.session.query(ParcelReturnDetail).get(parcel_return_id)
    if not parcel_return:
        abort(404)

    current_status = (parcel_return.status or "").strip()
    if current_status in {"ได้รับเอกสารแล้ว", "เอกสารตั้งฎีกา"}:
        return _validation_error_response("รายการนี้ผ่านขั้นตอนตรวจสอบแล้ว")

    if current_status not in {"รอตรวจสอบ", "กำลังตรวจสอบ"}:
        return _validation_error_response("ต้องอยู่ในสถานะรอตรวจสอบก่อนจึงจะยืนยันการมีอยู่ของเอกสารพัสดุได้")

    parcel_return.status = "พัสดุกำลังดำเนินการ"
    db.session.commit()
    _send_notification_email(parcel_return, object_type="parcel_return")
    if parcel_return.fund_request_id:
        _recalculate_fund_request_submission_status(parcel_return.fund_request_id)

    _recalculate_borrowing_ticket_status(parcel_return.ticket_id)
    flash("ยืนยันการมีอยู่ของเอกสารส่งคืนพัสดุเรียบร้อยแล้ว", "success")
    if parcel_return.ticket_id:
        return verification_view(parcel_return.ticket_id)
    return submit_petty_cash_claim(
        _render_after_post=True,
        _forced_fund_request_id=parcel_return.fund_request_id,
    )


@bp.route("/finance/parcel-returns/<int:parcel_return_id>/received", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def mark_parcel_received(parcel_return_id):
    parcel_return = db.session.query(ParcelReturnDetail).get(parcel_return_id)
    if not parcel_return:
        abort(404)

    current_status = (parcel_return.status or "").strip()
    if current_status not in {"พัสดุกำลังดำเนินการ", "กำลังตรวจสอบ"}:
        return _validation_error_response("ต้องยืนยันการมีอยู่ของเอกสารส่งคืนพัสดุก่อนรับเอกสารจริง")

    parcel_return.status = "ได้รับเอกสารแล้ว"
    db.session.commit()
    _send_notification_email(parcel_return, object_type="parcel_return")
    if parcel_return.fund_request_id:
        _recalculate_fund_request_submission_status(parcel_return.fund_request_id)

    _recalculate_borrowing_ticket_status(parcel_return.ticket_id)

    flash("เปลี่ยนสถานะพัสดุเป็น 'ได้รับเอกสารแล้ว' เรียบร้อย")
    if parcel_return.ticket_id:
        return verification_view(parcel_return.ticket_id)
    return submit_petty_cash_claim(
        _render_after_post=True,
        _forced_fund_request_id=parcel_return.fund_request_id,
    )


@bp.route("/finance/parcel-returns/<int:parcel_return_id>/reject", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def reject_parcel_return(parcel_return_id):
    parcel_return = db.session.query(ParcelReturnDetail).get(parcel_return_id)
    if not parcel_return:
        abort(404)

    current_status = (parcel_return.status or "").strip()
    if current_status in {"ได้รับเอกสารแล้ว", "เอกสารตั้งฎีกา"}:
        return _validation_error_response("ไม่สามารถปฏิเสธรายการที่รับเอกสารแล้วหรือปิดรายการแล้วได้")

    new_comment = request.form.get("rejection_comment", "").strip()

    if new_comment:
        existing_comment = parcel_return.rejection_comment or ""
        count = existing_comment.count("ครั้งที่") + 1
        staff = current_user
        user_name = staff.name if staff else "ไม่ระบุชื่อ"
        formatted_new_comment = (
            f"ครั้งที่ {count}: {new_comment} "
            f"ผู้ปฏิเสธ: {user_name} เมื่อ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        if existing_comment:
            parcel_return.rejection_comment = f"{existing_comment}\n{formatted_new_comment}"
        else:
            parcel_return.rejection_comment = formatted_new_comment

    parcel_return.status = "ปฏิเสธ"
    db.session.commit()
    _send_notification_email(parcel_return, object_type="parcel_return")
    if parcel_return.fund_request_id:
        _recalculate_fund_request_submission_status(parcel_return.fund_request_id)

    _recalculate_borrowing_ticket_status(parcel_return.ticket_id)
    flash("ปฏิเสธรายการส่งคืนพัสดุเรียบร้อยแล้ว", "success")
    if parcel_return.ticket_id:
        return verification_view(parcel_return.ticket_id)
    return submit_petty_cash_claim(
        _render_after_post=True,
        _forced_fund_request_id=parcel_return.fund_request_id,
    )

@bp.route("/api/documents/suggest", methods=["GET"])
@flask_login_required
def suggest_documents():
    q = request.args.get("q", "").strip()
    # เปิดช่องค้นหาโดยไม่พิมพ์อะไร ให้แสดงเอกสารทั้งหมดก่อน
    # ส่วนการค้นหาด้วยข้อความยังจำกัดผลลัพธ์ไว้เพื่อไม่ให้รายการยาวเกินไป
    docs = _list_cash_mng_documents(search_query=q, limit=20 if q else None)
    return jsonify([
        {
            "id": doc["file_id"] or doc["id"],
            "title": doc["title"],
            "document_type": doc["document_type"],
            "note": doc["note"],
            "summary": doc["summary"],
            "tags": doc["tags"],
            "file_path": doc["download_url"],
            "download_url": doc["download_url"],
            "url": doc["view_url"],
            "status": doc["status"],
        }
        for doc in docs
    ])

@bp.route("/coordinator/tickets/returns", methods=["POST"], endpoint="coordinator_ticket_returns")
@bp.route("/borrower/tickets/returns", methods=["POST"], endpoint="borrower_ticket_returns")
@bp.route("/coordinator/tickets/returns", methods=["POST"], endpoint="submit_return_details")
@module_system_required(ADVANCE_PAYMENT_SYSTEM)
def submit_return_details():
    ticket_id = request.form.get("ticket_id") or request.args.get("ticket_id")
    if not ticket_id:
        return _validation_error_response("กรุณาระบุเอกสารสัญญาเงินยืมที่ต้องการส่งหลักฐาน")

    borrowing_ticket = db.session.query(BorrowingTicket).filter_by(id=ticket_id).first()
    if borrowing_ticket is None:
        abort(404)

    current_user_id = _current_user_id()
    if not _can_submit_return_detail(current_user_id, borrowing_ticket):
        abort(403)

    if borrowing_ticket.status in {"เคลียร์ยอดแล้ว", "เอกสารตั้งฎีกา", "ปฏิเสธ"}:
        return _validation_error_response("ไม่สามารถดำเนินการสำหรับสัญญาเงินยืมที่มีสถานะนี้ได้")

    action = request.form.get("action", "submit")
    is_draft = (action == "draft")

    parcel_amount_raw = (request.form.get("amount") or "").replace(",", "").strip()
    parcel_items_description = (request.form.get("items_description") or "").strip()
    parcel_sent_date_raw = (request.form.get("sent_date") or "").strip()
    has_parcel_data = any((parcel_amount_raw, parcel_items_description, parcel_sent_date_raw))
    parcel_amount = None
    parcel_sent_date = None

    if not is_draft and has_parcel_data:
        if not parcel_amount_raw or not parcel_items_description or not parcel_sent_date_raw:
            return _validation_error_response("กรุณากรอกข้อมูลส่งคืนฝ่ายพัสดุให้ครบถ้วน")
        try:
            parcel_amount = float(parcel_amount_raw)
            parcel_sent_date = datetime.strptime(parcel_sent_date_raw, "%Y-%m-%d").date()
            if parcel_amount < 0:
                raise ValueError
        except (TypeError, ValueError):
            return _validation_error_response("กรุณาระบุข้อมูลส่งคืนฝ่ายพัสดุให้ถูกต้อง")

    if not is_draft and not has_parcel_data and not request.form.getlist("receipt_date[]"):
        return _validation_error_response(
            "กรุณาเพิ่มข้อมูลส่งคืนฝ่ายพัสดุหรือรายละเอียดใบเสร็จอย่างน้อย 1 รายการ"
        )

    receipt_dates = request.form.getlist("receipt_date[]")
    store_names = request.form.getlist("store_name[]")
    descriptions = request.form.getlist("description[]")
    amounts = request.form.getlist("amount[]")
    has_receipt_data = any(
        value.strip()
        for values in (receipt_dates, store_names, descriptions, amounts)
        for value in values
        if value
    ) or any(
        file_storage and file_storage.filename
        for file_storage in request.files.values()
    )
    if not is_draft and not has_receipt_data:
        receipt_dates = []
        store_names = []
        descriptions = []
        amounts = []

    if not is_draft and not has_receipt_data and not has_parcel_data:
        return _validation_error_response("กรุณาเพิ่มรายละเอียดใบเสร็จอย่างน้อย 1 รายการ")

    if not is_draft and not has_receipt_data and parcel_amount is not None:
        try:
            _create_parcel_return_record(
                ticket_id=ticket_id,
                fund_request_id=None,
                amount=parcel_amount,
                items_description=parcel_items_description,
                sent_date=parcel_sent_date,
                status="รอตรวจสอบ",
            )
        except IntegrityError:
            db.session.rollback()
            return _validation_error_response(
                "ไม่สามารถบันทึกรายละเอียดการส่งคืนได้ เนื่องจากข้อมูลไม่สอดคล้องกับข้อมูลในระบบ"
            )
        db.session.commit()
        flash("บันทึกข้อมูลการส่งคืนฝ่ายพัสดุเรียบร้อยแล้ว", "success")
        return verification_view(ticket_id)

    # ถ้ามีฉบับร่างเดิมอยู่แล้ว การ submit รอบนี้จะ "แทนที่" รายการเดิม
    # ดังนั้นต้องตัดฉบับร่างออกจากยอดที่ใช้เช็คเพดาน ไม่เช่นนั้นจะนับซ้ำ
    existing_draft = (
        db.session.query(ReturnDetail)
        .filter_by(ticket_id=ticket_id, creator_id=current_user_id, status="ฉบับร่าง")
        .first()
    )
    exclude_return_id = existing_draft.id if existing_draft else None

    parsed_rows = []
    total_amount_spent = 0.0
    old_receipt_count = 0

    for i in range(len(receipt_dates)):
        r_date_raw = receipt_dates[i]
        r_date = _coerce_date(r_date_raw) if r_date_raw else None
        if not is_draft and not r_date:
            return _validation_error_response("ทุกแถวของรายการใบเสร็จต้องระบุวันที่ที่ถูกต้อง")

        try:
            amt = float((amounts[i] or "0").replace(",", "")) if i < len(amounts) else 0.0
            if amt < 0:
                raise ValueError
        except (TypeError, ValueError):
            if not is_draft:
                return _validation_error_response("ทุกแถวของรายการใบเสร็จต้องระบุจำนวนเงินที่ถูกต้อง")
            amt = 0.0

        description = descriptions[i].strip() if i < len(descriptions) else ""
        store_name = store_names[i].strip() if i < len(store_names) else ""
        if not is_draft and (not store_name or not description):
            return _validation_error_response(
                f"รายการที่ {i + 1} ต้องระบุชื่อร้านค้าและรายละเอียดรายการให้ครบถ้วน"
            )
        is_cash = request.form.get(f"is_cash_{i}") == "true"
        if not is_draft and amt > 100000 and not _is_return_amount_limit_exempt(is_cash):
            return _validation_error_response(
                f"รายการที่ {i + 1} มียอดเกิน 100,000 บาท กรุณาแก้ไขก่อนส่งเบิก"
            )

        if not is_draft and _receipt_requires_additional_document(r_date):
            old_receipt_count += 1

        total_amount_spent += amt
        parsed_rows.append(
            {
                "receipt_date": r_date,
                "store_name": store_name,
                "description": description,
                "is_cash": is_cash,
                "amount": amt,
            }
        )

    proof_file_error = _proof_file_validation_error(len(parsed_rows), is_draft=is_draft)
    if proof_file_error:
        return _validation_error_response(proof_file_error)

    if not is_draft:
        ticket_totals = _calculate_ticket_return_totals_with_parcel(ticket_id, exclude_return_id=exclude_return_id)
        projected_total = ticket_totals["cumulative_total"] + total_amount_spent + (parcel_amount or 0)
        if _is_over_limit(projected_total, ticket_totals["budget"]):
            return _redirect_with_limit_popup(
                url_for(_dashboard_endpoint_for_role(_current_module_role())),
                (
                    "ยอดรวมเอกสารส่งใช้เงินยืมและส่งคืนพัสดุจะเป็น "
                    f"{_format_currency_amount(projected_total)} บาท "
                    f"ซึ่งเกินวงเงิน {_format_currency_amount(ticket_totals['budget'])} บาท"
                ),
            )

    if existing_draft:
        old_items = db.session.query(ReturnReceiptItem).filter_by(return_detail_id=existing_draft.id).all()
        for oi in old_items:
            db.session.query(ReturnProofFile).filter_by(return_receipt_item_id=oi.id).delete()
        db.session.query(ReturnReceiptItem).filter_by(return_detail_id=existing_draft.id).delete()
        return_detail = existing_draft
    else:
        return_detail = ReturnDetail(
            ticket_id=ticket_id,
            creator_id=current_user_id,
            proof_reference="Itemized Details Stored",
            created_at=datetime.now(),
        )
        db.session.add(return_detail)
        db.session.flush()

    if return_detail.creator_id is None:
        return_detail.creator_id = current_user_id

    return_detail.status = "ฉบับร่าง" if is_draft else "รอตรวจสอบ"
    db.session.flush()

    legacy_uploaded_files = request.files.getlist("proof_files[]")
    legacy_existing_file_paths = request.form.getlist("existing_proof_files[]")
    legacy_existing_file_names = request.form.getlist("existing_proof_filenames[]")

    for i, row in enumerate(parsed_rows):
        receipt_obj = ReturnReceiptItem(
            return_detail_id=return_detail.id,
            receipt_date=row["receipt_date"],
            store_name=row["store_name"],
            description=row["description"],
            is_cash=row["is_cash"],
            amount=row["amount"]
        )
        db.session.add(receipt_obj)
        db.session.flush()

        uploaded_files = request.files.getlist(f"proof_files_{i}[]")
        if not uploaded_files and i < len(legacy_uploaded_files):
            uploaded_files = [legacy_uploaded_files[i]]

        for file_storage in uploaded_files:
            if not file_storage or not file_storage.filename:
                continue
            original_filename = os.path.basename(file_storage.filename)
            if not original_filename:
                continue

            upload_folder = os.path.join(_upload_root(), str(ticket_id))
            os.makedirs(upload_folder, exist_ok=True)
            proof_path = f"uploads/{ticket_id}/{original_filename}"
            file_storage.save(os.path.join(upload_folder, original_filename))

            proof_file_record = ReturnProofFile(
                return_detail_id=return_detail.id,
                return_receipt_item_id=receipt_obj.id,
                proof_reference=proof_path,
                filename=original_filename,
                created_at=datetime.now()
            )
            db.session.add(proof_file_record)

        existing_file_paths = request.form.getlist(f"existing_proof_files_{i}[]")
        existing_file_names = request.form.getlist(f"existing_proof_filenames_{i}[]")
        if not existing_file_paths and i < len(legacy_existing_file_paths):
            existing_file_paths = [legacy_existing_file_paths[i]] if legacy_existing_file_paths[i] else []
            existing_file_names = [legacy_existing_file_names[i] if i < len(legacy_existing_file_names) else "receipt"]
        for file_index, existing_file_path in enumerate(existing_file_paths):
            if existing_file_path:
                proof_file_record = ReturnProofFile(
                    return_detail_id=return_detail.id,
                    return_receipt_item_id=receipt_obj.id,
                    proof_reference=existing_file_path,
                    filename=existing_file_names[file_index] if file_index < len(existing_file_names) else "receipt"
                )
                db.session.add(proof_file_record)

    return_detail.amount_spent = total_amount_spent
    announcement_ids = request.form.getlist("announcement_ids[]")
    announcement_titles = request.form.getlist("announcement_titles[]")
    announcement_references = []
    for index, title in enumerate(announcement_titles):
        cleaned_title = (title or "").strip()
        cleaned_id = (announcement_ids[index] if index < len(announcement_ids) else "").strip()
        if cleaned_title or cleaned_id:
            announcement_references.append({
                "id": cleaned_id,
                "title": cleaned_title,
            })
    _replace_return_detail_documents(return_detail, announcement_references)

    if parcel_amount is not None:
        _create_parcel_return_record(
            ticket_id=ticket_id,
            fund_request_id=None,
            amount=parcel_amount,
            items_description=parcel_items_description,
            sent_date=parcel_sent_date,
            status="รอตรวจสอบ",
        )

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _validation_error_response(
            "ไม่สามารถบันทึกรายละเอียดการส่งคืนได้ เนื่องจากข้อมูลไม่สอดคล้องกับข้อมูลในระบบ"
        )

    if not is_draft and old_receipt_count > 0:
        flash(
            f"พบ {old_receipt_count} รายการที่มีใบเสร็จเกิน 10 วัน กรุณาเตรียมเอกสารเพิ่มเติมประกอบการยื่น แต่ยังสามารถส่งได้",
            "warning",
        )

    if is_draft:
        flash("บันทึกฉบับร่างเรียบร้อยแล้ว", "success")
    else:
        borrowing_ticket.status = _recalculate_borrowing_ticket_status(ticket_id)
        _send_notification_email(return_detail, object_type="return")
        db.session.commit()
        flash("ส่งหลักฐานเอกสารส่งใช้เงินยืมเรียบร้อยแล้ว", "success")

    return view_return_proof_detail(return_detail.id)

@bp.app_template_filter('filter_actionable_tickets')
def filter_actionable_tickets(tickets):
    actionable_statuses = {"อนุมัติจ่ายเงิน", "มียอดคงค้าง",}
    return [
        t
        for t in tickets
        if (t.status or "").strip().lower() in actionable_statuses or (t.status or "").strip() in actionable_statuses
    ]

@bp.route("/proof-file/<int:file_id>/edit-inline", methods=["POST"])
@flask_login_required
def edit_receipt_item_inline(file_id):
    source = (request.form.get("source") or "").strip().lower()
    proof_file = None
    receipt_item = None
    is_claim = False

    if source == "petty_claim":
        is_claim = True
        receipt_item_id = request.form.get("receipt_item_id", type=int)
        receipt_item = db.session.query(PettyCashClaimItem).get(receipt_item_id) if receipt_item_id else None
        if receipt_item:
            proof_file = getattr(receipt_item, "proof_file", None) or (
                receipt_item.proof_files[0] if getattr(receipt_item, "proof_files", None) else None
            )
        else:
            proof_file = db.session.query(PettyCashClaimProofFile).get(file_id)
            if not proof_file:
                receipt_item = db.session.query(PettyCashClaimItem).get(file_id)
    elif source in {"return", "return_detail"}:
        receipt_item_id = request.form.get("receipt_item_id", type=int)
        receipt_item = db.session.query(ReturnReceiptItem).get(receipt_item_id) if receipt_item_id else None
        if receipt_item:
            proof_file = getattr(receipt_item, "proof_file", None) or (
                receipt_item.proof_files[0] if getattr(receipt_item, "proof_files", None) else None
            )
        else:
            proof_file = db.session.query(ReturnProofFile).get(file_id)
            if not proof_file:
                receipt_item = db.session.query(ReturnReceiptItem).get(file_id)
    else:
        # Fallback สำหรับลิงก์เก่าที่ยังไม่ได้ส่ง source มา
        proof_file = db.session.query(ReturnProofFile).get(file_id)
        if proof_file:
            is_claim = False
        else:
            proof_file = db.session.query(PettyCashClaimProofFile).get(file_id)
            if proof_file:
                is_claim = True

        if not proof_file:
            receipt_item = db.session.query(PettyCashClaimItem).get(file_id)
            if receipt_item:
                is_claim = True
                proof_file = getattr(receipt_item, "proof_file", None) or (
                    receipt_item.proof_files[0] if getattr(receipt_item, "proof_files", None) else None
                )
            else:
                receipt_item = db.session.query(ReturnReceiptItem).get(file_id)
                if receipt_item:
                    proof_file = getattr(receipt_item, "proof_file", None) or (
                        receipt_item.proof_files[0] if getattr(receipt_item, "proof_files", None) else None
                    )

    # หากค้นหาทั้งหมดแล้วยังไม่พบข้อมูล
    if not proof_file and not receipt_item:
        abort(404)

    # 4. ดึงข้อมูล Master และตรวจสอบสิทธิ์/สถานะ
    if is_claim:
        claim_detail_id = (
            getattr(receipt_item, 'claim_id', None) or
            getattr(receipt_item, 'claim_detail_id', None) or
            (receipt_item.claim_detail.id if hasattr(receipt_item, 'claim_detail') and receipt_item.claim_detail else None)
        ) if receipt_item else getattr(proof_file, 'claim_id', getattr(proof_file, 'claim_detail_id', None))

        claim_detail = db.session.query(PettyCashClaimDetail).get(claim_detail_id)

        if not claim_detail:
            abort(404)

        if claim_detail.status.lower() not in ["รอตรวจสอบ", "ปฏิเสธ", "ฉบับร่าง", "รอยืนยันการแก้ไข"]:
            return _validation_error_response("ไม่สามารถแก้ไขได้ เนื่องจากสถานะเอกสารถูกเปลี่ยนแปลงไปแล้ว")

        if not receipt_item and proof_file:
            receipt_item = getattr(proof_file, "claim_item", None)
    else:
        return_detail_id = receipt_item.return_detail_id if receipt_item else proof_file.return_detail_id
        return_detail = db.session.query(ReturnDetail).get(return_detail_id)

        if not return_detail:
            abort(404)

        borrowing_ticket = db.session.query(BorrowingTicket).get(return_detail.ticket_id)
        if not borrowing_ticket:
            abort(404)

        if _selected_system() == ADVANCE_PAYMENT_SYSTEM and (
            (not _is_current_coordinator() and borrowing_ticket.borrower_id != _current_user_id())
            or (_is_current_coordinator() and borrowing_ticket.creator_id != _current_user_id())
        ):
            abort(403)

        if return_detail.status.lower() not in ["รอตรวจสอบ", "ปฏิเสธ", "ฉบับร่าง", "รอยืนยันการแก้ไข", RETURN_DETAIL_BOUNCED_STATUS.lower()]:
            return _validation_error_response("ไม่สามารถแก้ไขได้ เนื่องจากสถานะเอกสารถูกเปลี่ยนแปลงไปแล้ว")

        if not receipt_item and proof_file:
            receipt_item = getattr(proof_file, "receipt_item", None)

    # Keep the first save as a real change-detection step.  The item must not
    # move to a new workflow state when the submitted values are identical.
    submitted_receipt_date = _coerce_date(request.form.get("receipt_date")) if request.form.get("receipt_date") else None
    submitted_store_name = request.form.get("store_name", "").strip()
    submitted_description = request.form.get("description", "").strip()
    submitted_amount = Decimal(request.form.get("amount", "0").replace(",", ""))
    uploaded_file = request.files.get("proof_file")
    has_new_file = bool(uploaded_file and uploaded_file.filename)

    current_amount = Decimal(str(receipt_item.amount or 0)) if receipt_item else Decimal("0")
    has_changes = bool(receipt_item) and any((
        receipt_item.receipt_date != submitted_receipt_date,
        hasattr(receipt_item, "store_name") and (receipt_item.store_name or "") != submitted_store_name,
        (receipt_item.description or "") != submitted_description,
        current_amount != submitted_amount,
        has_new_file,
    ))
    if not has_changes:
        return _validation_error_response("ไม่มีการเปลี่ยนแปลงข้อมูล โปรดทำการแก้ไขก่อนบันทึก")

    # ==========================================
    # 5. อัปเดตข้อมูลรายละเอียด และ ตรวจสอบอายุใบเสร็จ
    # ==========================================
    receipt_is_old = False  # ตัวแปรสถานะตรวจสอบอายุใบเสร็จเกิน 10 วัน

    if receipt_item:
        if hasattr(receipt_item, "store_name"):
            receipt_item.store_name = submitted_store_name

        receipt_item.description = request.form.get("description", "").strip()

        receipt_date_str = request.form.get("receipt_date")
        if receipt_date_str:
            parsed_date = _coerce_date(receipt_date_str)
            receipt_item.receipt_date = parsed_date

            # --- [เพิ่มส่วนการตรวจสอบอายุใบเสร็จ] ---
            if _receipt_requires_additional_document(parsed_date):
                receipt_is_old = True

        amount_str = request.form.get("amount")
        if amount_str:
            parsed_item_amount = float(amount_str.replace(",", ""))
            if not _is_return_amount_limit_exempt(getattr(receipt_item, "is_cash", False)) and parsed_item_amount > 100000:
                return _validation_error_response("รายการนี้มียอดเกิน 100,000 บาท กรุณาแก้ไขก่อนส่งเบิก")
            receipt_item.amount = parsed_item_amount

    if is_claim:
        total_spent_for_claim = sum(float(i.amount or 0) for i in claim_detail.items)
        if claim_detail.fund_request_id:
            fund_totals = _calculate_fund_request_totals(claim_detail.fund_request_id, exclude_claim_id=claim_detail.id)
            projected_total = fund_totals["cumulative_total"] + total_spent_for_claim
            if _is_over_limit(projected_total, fund_totals["request_amount"]):
                db.session.rollback()
                return _redirect_with_limit_popup(
                    url_for("advance_payment.petty_cash_claim_detail", claim_id=claim_detail.id),
                    (
                        "ยอดรวมใบเบิกเงินสดย่อยและส่งคืนพัสดุจะเป็น "
                        f"{_format_currency_amount(projected_total)} บาท "
                        f"ซึ่งเกินยอดขอเบิก {_format_currency_amount(fund_totals['request_amount'])} บาท"
                    ),
                )
    else:
        total_spent_for_return = sum(float(i.amount or 0) for i in return_detail.receipt_items)
        ticket_totals = _calculate_ticket_return_totals_with_parcel(return_detail.ticket_id, exclude_return_id=return_detail.id)
        projected_total = ticket_totals["cumulative_total"] + total_spent_for_return
        if _is_over_limit(projected_total, ticket_totals["budget"]):
            db.session.rollback()
            return _redirect_with_limit_popup(
                url_for("advance_payment.view_return_proof_detail", return_id=return_detail.id),
                (
                    "ยอดรวมเอกสารส่งใช้เงินยืมและส่งคืนพัสดุจะเป็น "
                    f"{_format_currency_amount(projected_total)} บาท "
                    f"ซึ่งเกินวงเงิน {_format_currency_amount(ticket_totals['budget'])} บาท"
                ),
            )

    # 6. จัดการอัปโหลดไฟล์ใหม่ (ถ้ามีการแนบไฟล์)
    if uploaded_file and uploaded_file.filename != "":
        user_id = _current_user_id()
        original_filename = os.path.basename(uploaded_file.filename)
        if not original_filename:
            return _validation_error_response("ไม่พบชื่อไฟล์หลักฐานที่อัปโหลด")

        user_upload_dir = os.path.join(_upload_root(), str(user_id or "claim"))
        os.makedirs(user_upload_dir, exist_ok=True)
        uploaded_file.save(os.path.join(user_upload_dir, original_filename))

        if proof_file:
            proof_file.proof_reference = f"uploads/{user_id or 'claim'}/{original_filename}"
            if hasattr(proof_file, "original_filename"):
                proof_file.original_filename = uploaded_file.filename
            elif hasattr(proof_file, "filename"):
                proof_file.filename = uploaded_file.filename
            proof_file.created_at = datetime.now()
        elif receipt_item:
            # An item can be edited before it has an uploaded proof file.
            # Create the record so the new image is shown after redirect.
            if is_claim:
                proof_file = PettyCashClaimProofFile(
                    claim_id=claim_detail.id,
                    claim_item_id=receipt_item.id,
                    proof_reference=f"uploads/{user_id or 'claim'}/{original_filename}",
                    filename=uploaded_file.filename,
                    created_at=datetime.now(),
                )
            else:
                proof_file = ReturnProofFile(
                    return_detail_id=return_detail.id,
                    return_receipt_item_id=receipt_item.id,
                    proof_reference=f"uploads/{user_id or 'claim'}/{original_filename}",
                    filename=uploaded_file.filename,
                    created_at=datetime.now(),
                )
            db.session.add(proof_file)

    # ==========================================
    # 7. บันทึกข้อมูลและแจ้งเตือน Warning หากใบเสร็จเกิน 10 วัน
    # ==========================================
    # created_at ของรายการใช้เป็นวันที่แก้ไขล่าสุดด้วย เมื่อมีการเปลี่ยนแปลงจริงเท่านั้น.
    receipt_item.created_at = datetime.now()

    if is_claim:
        claim_detail.status = "รอยืนยันการแก้ไข"
        claim_detail.total_amount = total_spent_for_claim

        db.session.commit()
        if claim_detail.fund_request_id:
            _recalculate_fund_request_submission_status(claim_detail.fund_request_id)

        # แจ้งเตือนเรื่องใบเสร็จเกิน 10 วัน (ถ้ามี)
        if receipt_is_old:
            flash("ใบเสร็จมีอายุเกิน 10 วัน กรุณาจัดทำเอกสารขออนุมัติเบิกจ่ายล่าช้าประกอบการยื่นเพิ่มเติม", "warning")

        flash("แก้ไขข้อมูลแล้ว กรุณาตรวจสอบและกดยืนยันการแก้ไขเพื่อส่งกลับไปตรวจสอบ", "success")
        return petty_cash_claim_detail(claim_detail.id)
    else:
        return_detail.status = "รอยืนยันการแก้ไข"
        return_detail.amount_spent = total_spent_for_return

        db.session.commit()

        if receipt_is_old:
            flash("ใบเสร็จมีอายุเกิน 10 วัน กรุณาเตรียมเอกสารเพิ่มเติมประกอบการยื่น", "warning")

        flash("แก้ไขข้อมูลแล้ว กรุณาตรวจสอบและกดยืนยันการแก้ไขเพื่อส่งกลับไปตรวจสอบ", "success")
        return view_return_proof_detail(return_detail.id)


@bp.route("/finance/returns/<int:return_id>/confirm-edit", methods=["POST"])
@flask_login_required
def confirm_return_edit(return_id):
    if _selected_system() == FINANCE_SYSTEM:
        abort(403)
    return_detail = db.session.query(ReturnDetail).get(return_id)
    if not return_detail:
        abort(404)
    borrowing_ticket = db.session.query(BorrowingTicket).get(return_detail.ticket_id)
    if not borrowing_ticket:
        abort(404)
    if _selected_system() == ADVANCE_PAYMENT_SYSTEM and (
        (not _is_current_coordinator() and borrowing_ticket.borrower_id != _current_user_id())
        or (_is_current_coordinator() and borrowing_ticket.creator_id != _current_user_id())
    ):
        abort(403)
    if (return_detail.status or "").strip().lower() != "รอยืนยันการแก้ไข":
        return _validation_error_response("รายการนี้ไม่มีการแก้ไขที่รอการยืนยัน")

    return_detail.status = "รอตรวจสอบ"
    db.session.commit()
    _recalculate_borrowing_ticket_status(return_detail.ticket_id)
    _send_notification_email(return_detail, object_type="return")
    flash("ยืนยันการแก้ไขเรียบร้อยแล้ว และส่งรายการกลับไปรอตรวจสอบ", "success")
    return view_return_proof_detail(return_detail.id)

@bp.route("/coordinator/tickets/<int:ticket_id>/autosave-draft", methods=["POST"], endpoint="coordinator_autosave_draft")
@bp.route("/borrower/tickets/<int:ticket_id>/autosave-draft", methods=["POST"], endpoint="borrower_autosave_draft")
@module_system_required(ADVANCE_PAYMENT_SYSTEM)
def autosave_return_draft(ticket_id):
    ticket = db.session.query(BorrowingTicket).filter_by(id=ticket_id).first()
    if not ticket or ticket.status in {"เคลียร์ยอดแล้ว", "เอกสารตั้งฎีกา", "ปฏิเสธ"}:
        return jsonify({"success": False, "message": "ไม่สามารถบันทึกร่างได้"}), 400

    # ผู้ใช้ทั่วไปบันทึกฉบับร่างได้เฉพาะสัญญาที่ตนเป็นผู้ยืม
    if not _is_current_coordinator() and ticket.borrower_id != _current_user_id():
        abort(403)

    data = request.get_json() or {}
    items = data.get("items", [])
    announcements = data.get("announcements", [])  # <--- 1. รับค่าประกาศเพิ่มจาก JSON

    # ค้นหา ReturnDetail สถานะ Draft เดิม
    current_user_id = _current_user_id()
    existing_draft = (
        db.session.query(ReturnDetail)
        .filter_by(ticket_id=ticket_id, creator_id=current_user_id, status="ฉบับร่าง")
        .first()
    )

    if existing_draft:
        db.session.query(ReturnReceiptItem).filter_by(return_detail_id=existing_draft.id).delete()
        return_detail = existing_draft
    else:
        return_detail = ReturnDetail(
            ticket_id=ticket_id,
            creator_id=current_user_id,
            proof_reference="Itemized Details Stored",
            status="ฉบับร่าง",
        )
        db.session.add(return_detail)
        db.session.flush()

    if return_detail.creator_id is None:
        return_detail.creator_id = current_user_id

    db.session.commit()

    # บันทึกรายการใบเสร็จใหม่
    for item in items:
        r_date = _coerce_date(item.get("receipt_date"))
        amt = float(item.get("amount") or 0.0)

        receipt_obj = ReturnReceiptItem(
            return_detail_id=return_detail.id,
            receipt_date=r_date,
            store_name=(item.get("store_name") or "").strip(),
            description=(item.get("description") or "").strip(),
            is_cash=item.get("is_cash") is True,
            amount=amt
        )
        db.session.add(receipt_obj)

    # <--- 2. เพิ่มส่วนจัดการบันทึกประกาศเข้า ReturnDetail --->
    _replace_return_detail_documents(return_detail, announcements)

    db.session.commit()

    saved_time = datetime.now().strftime("%H:%M:%S")
    return jsonify({"success": True, "saved_at": saved_time})

@bp.route("/finance/returns/<int:return_id>/proofed", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def mark_return_proofed(return_id):
    return_detail = (
        db.session.query(ReturnDetail).filter_by(id=return_id).first()
    )
    if return_detail is None:
        abort(404)

    if return_detail.status == "เอกสารตั้งฎีกา":
        return _validation_error_response("ไม่สามารถย้อนกลับรายการหลักฐานเอกสารส่งใช้เงินยืมที่ปิดรายการไปแล้วได้")

    if return_detail.status == "ผ่านการตรวจสอบ":
        return _validation_error_response("รายการหลักฐานเอกสารส่งใช้เงินยืมนี้ได้รับการตรวจสอบและยืนยันแล้ว")

    return_detail.status = "ผ่านการตรวจสอบ"
    db.session.commit()

    _recalculate_borrowing_ticket_status(return_detail.ticket_id)
    _send_notification_email(return_detail, object_type="return")
    flash("ทำเครื่องหมายรายการเอกสารส่งใช้เงินยืมเป็น ผ่านการตรวจสอบ เรียบร้อยแล้ว")

    return verification_view(return_detail.ticket_id)

@bp.route("/finance/returns/<int:return_id>/reject", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def reject_return_detail(return_id):
    return_detail = (
        db.session.query(ReturnDetail).filter_by(id=return_id).first()
    )
    if return_detail is None:
        abort(404)

    if return_detail.status == "เอกสารตั้งฎีกา":
        return _validation_error_response("ไม่สามารถแก้ไขรายการหลักฐานเอกสารส่งใช้เงินยืมที่ปิดรายการไปแล้วได้")

    new_comment = request.form.get("rejection_comment", "").strip()

    if new_comment:
        existing_comment = return_detail.rejection_comment or ""
        count = existing_comment.count("ครั้งที่") + 1
        staff = current_user
        user_name = staff.name if staff else "ไม่ระบุชื่อ"
        formatted_new_comment = (
            f"ครั้งที่ {count}: {new_comment} "
            f"ผู้ปฏิเสธ: {user_name} เมื่อ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        if existing_comment:
            return_detail.rejection_comment = f"{existing_comment}\n{formatted_new_comment}"
        else:
            return_detail.rejection_comment = formatted_new_comment

    return_detail.status = "ปฏิเสธ"
    db.session.commit()

    _recalculate_borrowing_ticket_status(return_detail.ticket_id)
    _send_notification_email(return_detail, object_type="return")
    flash("ปฏิเสธรายการหลักฐานเอกสารส่งใช้เงินยืมเรียบร้อยแล้ว")

    return verification_view(return_detail.ticket_id)

@bp.route("/finance/tickets/<int:ticket_id>/approve", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def approve_borrowing_ticket(ticket_id):
    borrowing_ticket = (
        db.session.query(BorrowingTicket).filter_by(id=ticket_id).first()
    )
    if borrowing_ticket is None:
        abort(404)

    if borrowing_ticket.status != "กำลังส่งคำขอ":
        return _validation_error_response("เฉพาะสัญญาเงินยืมเงินที่ กำลังส่งคำขอ เท่านั้นที่สามารถอนุมัติได้")

    raw_number = (request.form.get("number") or "").strip()
    if not raw_number:
        return _validation_error_response("กรุณาระบุเลขที่สัญญา")

    approval_ref_no = (request.form.get("borrowing_approval_ref_no") or "").strip()
    raw_approval_date = (request.form.get("borrowing_approval_date") or "").strip()
    if not approval_ref_no:
        return _validation_error_response("กรุณาระบุเลขที่อว.อนุมัติยืมเงิน")
    try:
        approval_date = datetime.strptime(raw_approval_date, "%Y-%m-%d").date()
    except ValueError:
        return _validation_error_response("กรุณาระบุวันที่อนุมัติให้ถูกต้อง")

    # Contract numbers may contain prefixes, separators, or leading zeroes.
    number = raw_number
    borrowing_ticket.status = "อนุมัติจ่ายเงิน"
    borrowing_ticket.number = number
    borrowing_ticket.borrowing_approval_ref_no = approval_ref_no
    borrowing_ticket.borrowing_approval_date = approval_date
    borrowing_ticket.approved_at = datetime.now()
    borrowing_ticket.finance_verified = True
    db.session.commit()

    _send_notification_email(borrowing_ticket)

    flash("อนุมัติสัญญาเงินยืมเงินทดรองจ่ายและส่งอีเมลแจ้งเตือนเรียบร้อยแล้ว")

    return finance_dashboard()

@bp.route("/api/login", methods=["POST"])
def api_login():
    payload = request.get_json(silent=True) or request.form
    requested_role = (payload.get("role") or payload.get("login_path") or "").strip()
    staff = _current_module_user()
    if not staff:
        return jsonify({"ok": False, "message": "กรุณาเข้าสู่ระบบ MIS ก่อนใช้งาน Advance Payment"}), 401

    requested_role, error_message = _ensure_module_role(staff, requested_role)
    if not requested_role:
        return jsonify({"ok": False, "message": error_message or "กรุณาเลือกบทบาท"}), 401

    _set_selected_system(requested_role)
    dashboard_endpoint = _dashboard_endpoint_for_role(requested_role)

    return jsonify(
        {
            "ok": True,
            "message": "เข้าสู่ระบบสำเร็จแล้ว",
            "role": requested_role,
            "redirect_to": url_for(dashboard_endpoint),
        }
    )


@bp.route("/register", methods=["GET", "POST"])
def register():
    flash("Advance Payment ใช้บัญชี MIS ในการเข้าสู่ระบบแล้ว ไม่ต้องลงทะเบียนแยก", "info")
    return redirect(url_for("auth.login"))


@bp.route("/finance/tickets/<int:ticket_id>/reject", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def reject_borrowing_ticket(ticket_id):
    borrowing_ticket = (
        db.session.query(BorrowingTicket).filter_by(id=ticket_id).first()
    )
    if borrowing_ticket is None:
        abort(404)

    if borrowing_ticket.status != "กำลังส่งคำขอ":
        return _validation_error_response("เฉพาะสัญญาเงินยืมเงินที่ กำลังส่งคำขอ เท่านั้นที่สามารถปฏิเสธได้")

    borrowing_ticket.rejection_comment = request.form.get(
        "rejection_comment",
        ""
    ).strip()
    borrowing_ticket.finance_verified = False
    borrowing_ticket.status = "ปฏิเสธ"
    db.session.commit()
    _send_notification_email(borrowing_ticket)
    flash("ปฏิเสธสัญญาเงินยืมเงินทดรองจ่ายเรียบร้อยแล้ว")
    return finance_dashboard()

@bp.route("/finance/return-records", methods=["GET"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def return_records_history():
    org_options = db.session.query(Org).order_by(Org.name.asc()).all()
    # 1. ดึงข้อมูลประวัติหลักฐานเอกสารส่งใช้เงินยืม (ReturnDetail)
    return_records = db.session.query(ReturnDetail).filter(ReturnDetail.status != "ฉบับร่าง").all()

    processed_records = []
    for record in return_records:
        ticket = db.session.query(BorrowingTicket).filter_by(id=record.ticket_id).first()
        closing_document = record.closing_document
        borrower_user = _get_user_by_id(getattr(ticket, "borrower_id", None)) if ticket else None
        borrower_org = _get_staff_org(borrower_user)
        account_name, account_number = _bank_account_search_info(getattr(ticket, "bank_account_info", None) if ticket else None)

        processed_records.append({
            "record_type": "return",
            "id": record.id,
            "ticket_id": record.ticket_id,
            "ticket_number": f"บย. {ticket.number}" if ticket and ticket.number else "N/A",
            "borrowing_ticket_name": ticket.borrowing_ticket_name if ticket else "N/A",
            "borrower_name": (ticket.borrower_name or getattr(_get_user_by_id(getattr(ticket, "borrower_id", None)), "name", "")) if ticket else "N/A",
            "org_id": getattr(borrower_org, "id", None),
            "org_name": getattr(borrower_org, "name", None) or getattr(borrower_org, "en_name", None) or "",
            "account_name": account_name,
            "account_number": account_number or (ticket.account_number if ticket else ""),
            "amount_spent": float(record.amount_spent or 0),
            "total_amount": float(record.amount_spent or 0),
            "status": record.status,
            "created_at": record.created_at,
            "closed_at": closing_document.filing_date if closing_document else None,
            "closing_document_id": record.closing_document_id or "-",
            "closing_document_name": closing_document.document_number if closing_document else "-",
            "old_document_number": record.old_document_number or ""
        })

    # 2. ดึงข้อมูลรายการส่งคืนพัสดุ (ParcelReturnDetail)
    #    เฉพาะรายการที่ผูกกับ borrowing_ticket เท่านั้น
    parcel_records = (
        db.session.query(ParcelReturnDetail)
        .filter(ParcelReturnDetail.fund_request_id.is_(None))
        .order_by(ParcelReturnDetail.id.desc())
        .all()
    )
    for record in parcel_records:
        _attach_parcel_return_context(record)
        closing_document = record.closing_document
        ticket = getattr(record, "borrowing_ticket", None)
        fund_request = getattr(record, "fund_request", None)
        org = getattr(fund_request, "org", None) if fund_request else None
        if org is None and ticket:
            org = _get_staff_org(_get_user_by_id(getattr(ticket, "borrower_id", None)))
        account_name, account_number = _bank_account_search_info(getattr(ticket, "bank_account_info", None) if ticket else None)

        processed_records.append({
            "record_type": "parcel_return",
            "id": record.id,
            "ticket_id": record.ticket_id,
            "fund_request_id": record.fund_request_id,
            "ticket_number": (
                f"บย. {record.display_ticket_number}"
                if record.ticket_id and record.display_ticket_number not in {None, "-", "N/A"}
                else (record.display_ticket_number or "N/A")
            ),
            "borrowing_ticket_name": record.display_subject_name if getattr(record, "display_subject_name", None) else "N/A",
            "borrower_name": record.display_borrower_name if getattr(record, "display_borrower_name", None) else "N/A",
            "org_id": getattr(org, "id", None),
            "org_name": getattr(org, "name", None) or getattr(org, "en_name", None) or "",
            "account_name": account_name,
            "account_number": account_number or (ticket.account_number if ticket else ""),
            "amount_spent": float(record.amount_spent or 0),
            "total_amount": float(record.amount_spent or 0),
            "status": record.status,
            "created_at": record.created_at if hasattr(record, 'created_at') else None,
            "closed_at": closing_document.filing_date if closing_document else None,
            "closing_document_id": record.closing_document_id or "-",
            "closing_document_name": closing_document.document_number if closing_document else "-",
            "old_document_number": record.old_document_number or ""
        })

    pending_review_count = sum(
        1
        for record in processed_records
        if (record.get("status") or "").strip() in {"รอตรวจสอบ", "กำลังตรวจสอบ"}
    )
    proofed_count = sum(
        1
        for record in processed_records
        if (record.get("status") or "").strip() in {"ผ่านการตรวจสอบ", "ได้รับเอกสารแล้ว"}
    )

    return render_template(
        "advance_payment/return_records_history.html",
        records=processed_records,
        history_mode="return",
        pending_review_count=pending_review_count,
        proofed_count=proofed_count,
        org_options=org_options,
    )


@bp.route("/finance/petty-cash-claim-records", methods=["GET"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def petty_cash_claim_history():
    org_options = db.session.query(Org).order_by(Org.name.asc()).all()
    # 1. ดึงข้อมูลรายการขอเบิกเงินสดย่อย (PettyCashClaimDetail)
    claim_details = (
        db.session.query(PettyCashClaimDetail)
        .filter(PettyCashClaimDetail.status != "ฉบับร่าง")
        .order_by(PettyCashClaimDetail.created_at.desc())
        .all()
    )
    claim_details = [
        claim for claim in claim_details
        if not _claim_has_only_category_six(claim)
    ]

    processed_claims = []
    for claim in claim_details:
        _attach_petty_cash_claim_context(claim)
        closing_doc = claim.closing_document
        ticket_num = claim.fund_request.ticket_number if claim.fund_request and claim.fund_request.ticket_number else f"PC-{claim.id}"
        dept_name = (
            claim.setting.department_name
            if claim.setting
            else (_get_staff_department_name(claim.user, "ไม่ระบุ") if claim.user else "ไม่ระบุ")
        )
        org = getattr(claim.setting, "org", None) if claim.setting else None
        if org is None and getattr(claim, "fund_request", None):
            org = getattr(claim.fund_request, "org", None)
        account_name, account_number = _bank_account_search_info(getattr(claim.setting, "bank_account_info", None) if claim.setting else None)
        borrower_name = claim.user.name if claim.user else '-'

        processed_claims.append({
            "record_type": "petty_cash",
            "id": claim.id,
            "fund_request_id": claim.fund_request_id,
            "ticket_id": None,
            "ticket_number": ticket_num,
            "borrowing_ticket_name": dept_name,
            "borrower_name": borrower_name,
            "org_id": getattr(org, "id", None),
            "org_name": getattr(org, "name", None) or getattr(org, "en_name", None) or "",
            "account_name": account_name,
            "account_number": account_number or (claim.setting.account_number if claim.setting else ""),
            "amount_spent": float(claim.total_amount),
            "total_amount": float(claim.total_amount),
            "status": claim.status,
            "created_at": claim.created_at,
            "closed_at": closing_doc.filing_date if closing_doc else None,
            "closing_document_id": claim.closing_document_id or "-",
            "closing_document_name": closing_doc.document_number if closing_doc else "-",
            "old_document_number": claim.old_document_number or ""
        })

    # 2. ดึงข้อมูลรายการส่งคืนพัสดุที่ผูกกับ fund_request
    parcel_records = (
        db.session.query(ParcelReturnDetail)
        .filter(ParcelReturnDetail.fund_request_id.isnot(None))
        .order_by(ParcelReturnDetail.id.desc())
        .all()
    )

    for record in parcel_records:
        _attach_parcel_return_context(record)
        closing_document = record.closing_document
        ticket = getattr(record, "borrowing_ticket", None)
        fund_request = getattr(record, "fund_request", None)
        org = getattr(fund_request, "org", None) if fund_request else None
        if org is None and ticket:
            org = _get_staff_org(_get_user_by_id(getattr(ticket, "borrower_id", None)))
        account_name, account_number = _bank_account_search_info(getattr(ticket, "bank_account_info", None) if ticket else None)

        processed_claims.append({
            "record_type": "parcel_return",
            "id": record.id,
            "ticket_id": record.ticket_id,
            "fund_request_id": record.fund_request_id,
            "ticket_number": (
                f"บย. {record.display_ticket_number}"
                if record.ticket_id and record.display_ticket_number not in {None, "-", "N/A"}
                else (record.display_ticket_number or "N/A")
            ),
            "borrowing_ticket_name": record.display_subject_name if getattr(record, "display_subject_name", None) else "N/A",
            "borrower_name": record.display_borrower_name if getattr(record, "display_borrower_name", None) else "N/A",
            "org_id": getattr(org, "id", None),
            "org_name": getattr(org, "name", None) or getattr(org, "en_name", None) or "",
            "account_name": account_name,
            "account_number": account_number or (ticket.account_number if ticket else ""),
            "amount_spent": float(record.amount_spent or 0),
            "total_amount": float(record.amount_spent or 0),
            "status": record.status,
            "created_at": record.created_at if hasattr(record, 'created_at') else None,
            "closed_at": closing_document.filing_date if closing_document else None,
            "closing_document_id": record.closing_document_id or "-",
            "closing_document_name": closing_document.document_number if closing_document else "-",
            "old_document_number": record.old_document_number or ""
        })

    claim_proofed_count = sum(
        1
        for record in processed_claims
        if record["record_type"] == "petty_cash" and (record["status"] or "").strip() == "ผ่านการตรวจสอบ"
    )
    pending_review_count = sum(
        1
        for record in processed_claims
        if (record.get("status") or "").strip() in {"รอตรวจสอบ", "กำลังตรวจสอบ"}
    )
    proofed_count = sum(
        1
        for record in processed_claims
        if (record.get("status") or "").strip() in {"ผ่านการตรวจสอบ", "ได้รับเอกสารแล้ว"}
    )

    current_year_be = datetime.now().year + 543
    if datetime.now().month <= 11:
        current_interest_period_key = f"06/{current_year_be}"
    else:
        current_interest_period_key = f"12/{current_year_be}"
    current_interest_period = _format_interest_period_label(current_interest_period_key)

    active_settings = db.session.query(PettyCashSetting).filter(
        PettyCashSetting.valid == True,
        PettyCashSetting.fiscal_year == _current_petty_cash_fiscal_year(),
    ).all()
    for setting in active_settings:
        _attach_petty_cash_setting_people(setting)

    approved_interest_requests = db.session.query(FundRequest).filter(
        FundRequest.form_type == FUND_REQUEST_FORM_INTEREST,
    ).all()

    matched_requests = []
    for fr in approved_interest_requests:
        if _normalize_interest_period_value(fr.period_year) == current_interest_period_key:
            matched_requests.append(fr)

    submitted_org_ids = {fr.org_id for fr in matched_requests if getattr(fr, "org_id", None)}

    pending_interest_departments = []
    for setting in active_settings:
        is_submitted = setting.org_id in submitted_org_ids
        custodian = setting.custodian_name or (setting.custodian_user.name if getattr(setting, "custodian_user", None) else None) or '-'

        pending_interest_departments.append({
            "id": setting.id,
            "department_name": setting.department_name,
            "account_number": setting.account_number or '-',
            "custodian_name": custodian,
            "is_submitted": is_submitted,
            "is_pending": not is_submitted,
            "pending_period": current_interest_period,
        })

    pending_interest_count = len(pending_interest_departments)

    return render_template(
        "advance_payment/petty_cash_claim_history.html",
        records=processed_claims,
        history_mode="petty_cash",
        claim_proofed_count=claim_proofed_count,
        pending_review_count=pending_review_count,
        proofed_count=proofed_count,
        pending_interest_departments=pending_interest_departments,
        pending_interest_count=pending_interest_count,
        current_interest_period=current_interest_period,
        org_options=org_options,
    )


def _parcel_return_history_fallback(parcel_return):
    if getattr(parcel_return, "fund_request_id", None):
        return "advance_payment.petty_cash_claim_history"
    return "advance_payment.return_records_history"

@bp.route("/finance/petty-cash-settings", methods=["GET", "POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def petty_cash_settings(_render_after_post=False):
    bank_account_options = _get_bank_account_dropdown_options()
    bank_account_values = {option["value"] for option in bank_account_options}
    org_options = db.session.query(Org).order_by(Org.name.asc()).all()
    staff_options = _get_staff_accounts_from_directory()
    current_fiscal_year = _current_petty_cash_fiscal_year()

    if request.method == "POST" and not _render_after_post:
        setting_ids = request.form.getlist("setting_id[]")
        fiscal_years = request.form.getlist("fiscal_year[]")
        dept_names = request.form.getlist("dept_name[]")
        org_ids = request.form.getlist("org_id[]")
        custodian_names = request.form.getlist("custodian_name[]")
        custodian_ids = request.form.getlist("custodian_id[]")
        budgets = request.form.getlist("budget[]")
        acc_numbers = request.form.getlist("account_number[]")
        bank_account_info_ids = request.form.getlist("bank_account_info_id[]")
        valid_dept_names = request.form.getlist("valid_dept[]")

        errors = []
        row_count = max(len(dept_names), len(org_ids))
        for i in range(row_count):
            raw_setting_id = setting_ids[i].strip() if i < len(setting_ids) else ""
            raw_org_id = org_ids[i].strip() if i < len(org_ids) else ""
            selected_org = db.session.query(Org).filter_by(id=int(raw_org_id)).first() if raw_org_id.isdigit() else None
            name = selected_org.name if selected_org else (dept_names[i].strip() if i < len(dept_names) else "")
            fy_str = fiscal_years[i].strip() if i < len(fiscal_years) else ""
            raw_custodian_id = custodian_ids[i].strip() if i < len(custodian_ids) else ""
            selected_custodian = (
                db.session.query(StaffAccount).filter_by(id=int(raw_custodian_id)).first()
                if raw_custodian_id.isdigit() else None
            )
            custodian = (
                selected_custodian.fullname
                if selected_custodian
                else (custodian_names[i].strip() if i < len(custodian_names) else "")
            )
            bg_str = (budgets[i].strip().replace(",", "") if i < len(budgets) else "")
            acc = acc_numbers[i].strip() if i < len(acc_numbers) else ""
            raw_bank_account_info_id = bank_account_info_ids[i].strip() if i < len(bank_account_info_ids) else ""

            # A row containing anything besides fiscal year or the valid flag
            # is an actual setting row and must be complete before saving.
            # This prevents partially filled new rows from being silently
            # ignored by the condition below.
            row_has_setting_data = any(
                (
                    raw_org_id,
                    name,
                    raw_custodian_id,
                    custodian,
                    bg_str,
                    acc,
                    raw_bank_account_info_id,
                )
            )
            if row_has_setting_data and not all((name, custodian, bg_str, acc)):
                errors.append(f"แถวที่ {i + 1} กรุณากรอกข้อมูลให้ครบทุกช่อง")
                continue

            selected_bank_account = _get_bank_account_info(
                bank_account_info_id=raw_bank_account_info_id,
                account_number=acc,
            )
            bank_account_info_id = selected_bank_account.id if selected_bank_account else None
            if selected_bank_account and selected_bank_account.account_number:
                acc = selected_bank_account.account_number
            elif acc:
                errors.append(f"แถวที่ {i + 1} เลขที่บัญชีนี้ถูกปิดแล้วหรือไม่อยู่ในรายการที่ใช้งานได้")
                continue
            is_valid = name in valid_dept_names

            if name and bg_str and acc and fy_str:
                selected_org = selected_org or _resolve_org_by_department_name(name)
                if not selected_org:
                    continue

                # The settings form accepts Buddhist Era years; persist Gregorian years internally.
                requested_fiscal_year = int(fy_str) - 543

                # ค้นหาว่ามี Setting ของ (หน่วยงานนี้ + ปีงบประมาณนี้) อยู่แล้วหรือไม่
                existing = (
                    db.session.query(PettyCashSetting)
                    .filter_by(org_id=selected_org.id, fiscal_year=requested_fiscal_year)
                    .first()
                )

                if existing:
                    # ถ้ามีข้อมูลของปีงบประมาณนี้อยู่แล้ว ให้ UPDATE ข้อมูล
                    existing.custodian_id = selected_custodian.id if selected_custodian else None
                    existing.budget = Decimal(bg_str)
                    existing.bank_account_info_id = bank_account_info_id
                    existing.valid = is_valid
                else:
                    # ถ้ายังไม่มีข้อมูลของปีงบประมาณนี้ ให้ INSERT เป็นรายการใหม่
                    new_setting = PettyCashSetting(
                        fiscal_year=requested_fiscal_year,
                        org_id=selected_org.id,
                        custodian_id=selected_custodian.id if selected_custodian else None,
                        budget=Decimal(bg_str),
                        bank_account_info_id=bank_account_info_id,
                        valid=is_valid,
                        created_at=datetime.now(),
                    )
                    db.session.add(new_setting)

        try:
            db.session.commit()
            flash("บันทึกข้อมูลตั้งต้นเงินสดย่อยเรียบร้อยแล้ว", "success")
        except Exception as e:
            db.session.rollback()
            return _validation_error_response(f"เกิดข้อผิดพลาดในการบันทึก: {str(e)}", 500)

        return petty_cash_settings(_render_after_post=True)

    # ดึง Setting ทั้งหมดเรียงตาม org_id
    all_settings = (
        db.session.query(PettyCashSetting)
        .order_by(PettyCashSetting.org_id.asc(), PettyCashSetting.fiscal_year.desc(), PettyCashSetting.id.desc())
        .all()
    )

    # จัดกลุ่ม Setting ตาม org_id
    settings_by_org = {}
    for setting in all_settings:
        settings_by_org.setdefault(setting.org_id, []).append(setting)

    # เลือก Setting ที่จะนำมาแสดงผล:
    # 1. ยึดข้อมูลของปีงบประมาณปัจจุบัน (current_fiscal_year) ก่อน
    # 2. ถ้ายังไม่มีของปีปัจจุบัน ให้เลือกปีล่าสุดที่มีแทน
    display_settings = []
    for org_id, org_settings in settings_by_org.items():
        current_setting = next((s for s in org_settings if s.fiscal_year == current_fiscal_year), None)
        if current_setting:
            display_settings.append(current_setting)
        elif org_settings:
            display_settings.append(org_settings[0]) # org_settings ถูกเรียง fiscal_year.desc() ไว้แล้ว

    display_settings.sort(
        key=lambda setting: (
            getattr(setting, "department_name", "ไม่พบข้อมูลหน่วยงาน") or "ไม่พบข้อมูลหน่วยงาน",
            getattr(setting, "fiscal_year", 0) or 0,
            0 if getattr(setting, "id", None) else 1,
        )
    )

    setting_org_ids = {setting.id: setting.org_id for setting in display_settings if getattr(setting, "id", None)}
    setting_custodian_ids = {setting.id: setting.custodian_id for setting in display_settings if getattr(setting, "id", None)}

    # Summarize petty-cash requests across all fiscal years by department.
    # Seed the summary from every setting so years/departments with no requests
    # yet are still shown with zero totals.
    request_summary = {}
    for setting in all_settings:
        key = (setting.fiscal_year, setting.org_id)
        request_summary[key] = {
            "fiscal_year": setting.fiscal_year,
            "department_name": setting.department_name or "ไม่พบข้อมูลหน่วยงาน",
            "request_count": 0,
            "used_amount": Decimal("0.00"),
        }

    history_requests = (
        db.session.query(FundRequest)
        .filter(
            FundRequest.form_type == FUND_REQUEST_FORM_PETTY_CASH,
            FundRequest.status.notin_(["กำลังดำเนินการ", "ปฏิเสธ", "ยกเลิก"]),
            FundRequest.request_date.isnot(None),
        )
        .all()
    )

    for fund_request in history_requests:
        fiscal_year = convert_to_fiscal_year(fund_request.request_date)
        key = (fiscal_year, getattr(fund_request, "org_id", None))
        summary = request_summary.setdefault(
            key,
            {
                "fiscal_year": fiscal_year,
                "department_name": fund_request.department_name or "ไม่พบข้อมูลหน่วยงาน",
                "request_count": 0,
                "used_amount": Decimal("0.00"),
            },
        )
        summary["request_count"] += 1
        summary["used_amount"] += Decimal(fund_request.amount or 0)

    # Only show departments and fiscal years with actual request history.
    history_summary = sorted(
        request_summary.values(),
        key=lambda item: (-item["fiscal_year"], item["department_name"]),
    )

    claim_details = (
        db.session.query(PettyCashClaimDetail)
        .filter(PettyCashClaimDetail.status == "ผ่านการตรวจสอบ")
        .order_by(PettyCashClaimDetail.created_at.desc())
        .all()
    )
    claim_details = [
        claim
        for claim in claim_details
        if getattr(claim, "created_at", None)
        and convert_to_fiscal_year(claim.created_at.date()) == current_fiscal_year
        and not _claim_has_only_category_six(claim)
    ]

    dept_summary = {}
    for s in display_settings:
        summary = _calculate_petty_cash_balance_summary(s)
        summary["setting"] = s
        # Use the setting primary key as the canonical summary key so the
        # template is not dependent on a mutable department name string.
        dept_summary[getattr(s, "id", None)] = summary

    for claim in claim_details:
        _attach_petty_cash_claim_context(claim)
        setting_id = claim.petty_cash_setting_id or (claim.setting.id if claim.setting else None)

        if setting_id not in dept_summary:
            if claim.setting:
                summary = _calculate_petty_cash_balance_summary(claim.setting)
            else:
                summary = {
                    "setting": None,
                    "total_claims": 0,
                    "total_spent": 0.0,
                    "total_amount": 0.0,
                    "remaining_budget": 0.0,
                    "initial_budget": 0.0,
                }
            summary["setting"] = claim.setting
            dept_summary[setting_id] = summary

    return render_template(
        "petty_cash_settings.html",
        settings=display_settings,
        claim_details=claim_details,
        dept_summary=dept_summary,
        bank_account_options=bank_account_options,
        bank_account_values=bank_account_values,
        org_options=org_options,
        staff_options=staff_options,
        setting_org_ids=setting_org_ids,
        setting_custodian_ids=setting_custodian_ids,
        history_summary=history_summary,
        current_fiscal_year=current_fiscal_year,
    )


@bp.route("/api/custodian/suggest", methods=["GET"])
@module_system_required(FINANCE_SYSTEM)
def suggest_custodian():
    """ API สำหรับแนะนำชื่อผู้รักษาเงินสดย่อย จากชื่อหน่วยงาน """
    dept_name = request.args.get("department_name", "").strip()
    if not dept_name:
        return jsonify({"custodian_name": ""})

    dept_data = get_department_data_service(dept_name)
    if dept_data and "account_controller" in dept_data:
        controller_name = dept_data["account_controller"].get("name", "")
        if controller_name and "..." not in controller_name:
            return jsonify({"custodian_name": controller_name})

    org = _resolve_org_by_department_name(dept_name)
    setting = (
        db.session.query(PettyCashSetting)
        .filter_by(org_id=org.id, fiscal_year=_current_petty_cash_fiscal_year(), valid=True)
        .first()
        if org
        else None
    )
    if setting and setting.custodian_name:
        return jsonify({"custodian_name": setting.custodian_name})

    return jsonify({"custodian_name": ""})

@bp.route("/api/petty-cash-options", methods=["GET"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def api_petty_cash_options():
    q = request.args.get("q", "").strip()
    query = db.session.query(PettyCashSetting).filter(
        PettyCashSetting.valid == True,
        PettyCashSetting.fiscal_year == _current_petty_cash_fiscal_year(),
    )
    settings = query.all()
    if q:
        settings = [s for s in settings if q.casefold() in (s.department_name or "ไม่พบข้อมูลชื่อหน่วยงาน").casefold()]
    results = [
        {
            "id": s.id,
            "department_name": s.department_name,
            "budget": float(s.budget),
            "account_number": s.account_number
        }
        for s in settings
    ]
    return jsonify(results)

@bp.route("/finance/closing-management", methods=["GET", "POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def closing_management(_render_after_post=False, _forced_search_closing_number=None):
    search_closing_number = (
        _forced_search_closing_number
        if _forced_search_closing_number is not None
        else request.args.get("search_closing_number", "").strip()
    )
    searched_closing_results = []
    searched_returns = []
    searched_parcel_returns = []
    searched_petty_cash = []

    if search_closing_number:
        searched_docs = (
            db.session.query(ClosingDocument)
            .filter(ClosingDocument.document_number.contains(search_closing_number))
            .order_by(ClosingDocument.filing_date.desc(), ClosingDocument.id.desc())
            .all()
        )

        for searched_doc in searched_docs:
            doc_returns = [link.ticket_return for link in searched_doc.links if link.ticket_return is not None]
            doc_parcel_returns = [link.parcel_return for link in searched_doc.links if link.parcel_return is not None]
            doc_petty_cash = [link.claim for link in searched_doc.links if link.claim is not None]


            for petty in doc_petty_cash:
                related_claim = _attach_petty_cash_claim_context(petty)
                petty.amount = float(petty.total_amount or 0)
                petty.department_name = (
                    petty.setting.department_name
                    if petty.setting
                    else (petty.user.department if petty.user else "ไม่ระบุ")
                )
                petty.requester_name = "-"
                petty.display_claim_number = "-"
                if related_claim:
                    fund_request = related_claim.fund_request
                    petty.requester_name = _fund_request_requester_name(fund_request, getattr(related_claim.user, "name", petty.requester_name)) if fund_request else (related_claim.user.name if related_claim.user else petty.requester_name)
                    petty.display_claim_number = (
                        related_claim.claim_number
                        or (fund_request.ticket_number if fund_request and fund_request.ticket_number else None)
                        or f"PC-{related_claim.id}"
                    )
                    petty.name = petty.requester_name

            for ret in doc_returns:
                if not hasattr(ret, 'borrowing_ticket') or ret.borrowing_ticket is None:
                    ret.borrowing_ticket = db.session.query(BorrowingTicket).filter_by(id=ret.ticket_id).first()

            for pr in doc_parcel_returns:
                _attach_parcel_return_context(pr)

            searched_closing_results.append({
                "doc": searched_doc,
                "returns": doc_returns,
                "parcel_returns": doc_parcel_returns,
                "petty_cash": doc_petty_cash,
                "historical_return_ids": {link.ticket_return_id for link in searched_doc.links if not link.is_active},
                "historical_parcel_ids": {link.parcel_return_id for link in searched_doc.links if not link.is_active},
                "historical_claim_ids": {link.claim_id for link in searched_doc.links if not link.is_active},
                "petty_cash_total": sum(petty.total_amount or 0 for petty in doc_petty_cash),
                "loan_total": (
                    sum(ret.closing_amount for ret in doc_returns)
                    + sum(pr.amount_spent or 0 for pr in doc_parcel_returns)
                ),
            })

    if request.method == "POST" and not _render_after_post:
        document_number = request.form.get("document_number", "").strip()
        try:
            filing_date = datetime.strptime(request.form.get("filing_date", ""), "%Y-%m-%d").date()
            selections = [
                (ReturnDetail, {int(value) for value in request.form.getlist("return_ids[]")}, "ผ่านการตรวจสอบ"),
                (ParcelReturnDetail, {int(value) for value in request.form.getlist("parcel_return_ids[]")}, "ได้รับเอกสารแล้ว"),
                (PettyCashClaimDetail, {int(value) for value in request.form.getlist("petty_claim_ids[]")}, "โอนเงินสดย่อยสำเร็จ"),
            ]
        except (ValueError, TypeError):
            return _validation_error_response("วันที่หรือรายการตั้งฎีกาไม่ถูกต้อง")
        if not document_number or len(document_number) > 255 or not any(ids for _, ids, _ in selections):
            return _validation_error_response("กรุณาระบุเลขที่ฎีกาและเลือกรายการตั้งฎีกา")
        if db.session.query(ClosingDocument).filter_by(document_number=document_number).first():
            return _validation_error_response("เลขที่ฎีกานี้มีอยู่แล้ว กรุณาใช้เลขที่ใหม่")

        selected_records = []
        for model, ids, status in selections:
            records = db.session.query(model).filter(model.id.in_(ids)).with_for_update().all()
            if len(records) != len(ids) or any(
                record.status != status or record.closing_document is not None for record in records
            ):
                db.session.rollback()
                return _validation_error_response("มีรายการที่ไม่พร้อมตั้งฎีกาหรือผูกกับฎีกาอื่นแล้ว กรุณาตรวจสอบอีกครั้ง")
            selected_records.extend(records)

        total_amount = sum((record.total_amount if isinstance(record, PettyCashClaimDetail)
                            else record.closing_amount if isinstance(record, ReturnDetail)
                            else record.amount_spent) or Decimal("0") for record in selected_records)
        new_closing_doc = ClosingDocument(
            document_number=document_number, filing_date=filing_date,
            total_amount=total_amount, created_at=datetime.now(),
        )
        db.session.add(new_closing_doc)
        updated_ticket_ids = set()
        for record in selected_records:
            record.status = "เอกสารตั้งฎีกา"
            record.closing_document = new_closing_doc
            if not isinstance(record, PettyCashClaimDetail) and record.ticket_id:
                updated_ticket_ids.add(record.ticket_id)
        for ticket_id in updated_ticket_ids:
            _recalculate_borrowing_ticket_status(ticket_id)
        db.session.commit()
        flash(f"บันทึกเอกสารตั้งฎีกาเลขที่ {document_number} ยอดรวม {total_amount:,.2f} บาท สำเร็จ")
        return closing_management(_render_after_post=True)

    # --- ส่วนการดึงข้อมูลเพื่อแสดงผล (GET) ---
    proofed_records = db.session.query(ReturnDetail).filter(ReturnDetail.status == "ผ่านการตรวจสอบ", ~ReturnDetail.closing_links.any(is_active=True)).all()
    processed_records = []
    for record in proofed_records:
        ticket = db.session.query(BorrowingTicket).filter_by(id=record.ticket_id).first()
        processed_records.append({
            "id": record.id,
            "ticket_id": record.ticket_id,
            "borrowing_ticket_name": ticket.borrowing_ticket_name if ticket else "N/A",
            "borrowing_ticket_number": ticket.number if ticket else "N/A",
            "borrower_name": (ticket.borrower_name or getattr(_get_user_by_id(getattr(ticket, "borrower_id", None)), "name", "")) if ticket else "N/A",
            "amount_spent": float(record.amount_spent or 0),
            "closing_amount": float(record.closing_amount),
            "cash_amount": float(sum(item.amount or 0 for item in record.receipt_items if item.is_cash)),
            "status": record.status,
            "created_at": record.created_at,
        })

    proofed_parcels = db.session.query(ParcelReturnDetail).filter(ParcelReturnDetail.status == "ได้รับเอกสารแล้ว", ~ParcelReturnDetail.closing_links.any(is_active=True)).all()
    processed_parcels = []
    for pr in proofed_parcels:
        _attach_parcel_return_context(pr)
        ticket = getattr(pr, "borrowing_ticket", None)
        fund_request = getattr(pr, "fund_request", None)
        borrower_name = "N/A"
        borrowing_ticket_number = "N/A"
        borrowing_ticket_name = "N/A"
        display_ticket_id = getattr(pr, "display_ticket_id", None)

        if ticket:
            borrowing_ticket_number = ticket.number if ticket.number else "N/A"
            borrowing_ticket_name = ticket.borrowing_ticket_name
            borrower_name = (
                ticket.borrower_name
                or getattr(_get_user_by_id(getattr(ticket, "borrower_id", None)), "name", "")
                or borrower_name
            )
        elif fund_request:
            borrowing_ticket_number = fund_request.ticket_number if fund_request.ticket_number else "ไม่พบข้อมูล"
            borrowing_ticket_name = fund_request.purpose or "ไม่พบข้อมูล"
            borrower_name = _fund_request_requester_name(fund_request, borrower_name)

        processed_parcels.append({
            "id": pr.id,
            "ticket_id": pr.ticket_id,
            "fund_request_id": pr.fund_request_id,
            "display_ticket_id": display_ticket_id,
            "borrowing_ticket_name": borrowing_ticket_name,
            "borrowing_ticket_number": borrowing_ticket_number,
            "borrower_name": borrower_name,
            "amount_spent": float(pr.amount_spent or 0),
            "items_description": pr.items_description,
            "status": pr.status,
            "created_at": pr.created_at,
        })

    # ดึงรายการเงินสดย่อยที่มีสถานะเป็น transferred เพื่อนำไปแสดงในตารางที่ 3
    transferred_petty_claims = db.session.query(PettyCashClaimDetail).filter(
        PettyCashClaimDetail.status == "โอนเงินสดย่อยสำเร็จ",
        ~PettyCashClaimDetail.closing_links.any(is_active=True),
    ).all()
    for petty in transferred_petty_claims:
        _attach_petty_cash_claim_context(petty)

    all_petty_settings = db.session.query(PettyCashSetting).all()

    return render_template(
        "closing_management.html",
        search_closing_number=search_closing_number,
        searched_closing_results=searched_closing_results,
        searched_returns=searched_returns,
        searched_parcel_returns=searched_parcel_returns,
        searched_petty_cash=searched_petty_cash,
        records=processed_records,
        parcel_records=processed_parcels,
        transferred_petty_claims=transferred_petty_claims,
        pending_last_edit_records=[*proofed_records, *proofed_parcels, *transferred_petty_claims],
        all_petty_settings=all_petty_settings
    )

@bp.route("/finance/returns/<int:return_id>/update-closing-doc", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def update_return_closing_doc(return_id):
    """ แก้ไขเลขฎีกาของใบคืนเงินชิ้นนี้ พร้อมบันทึกประวัติเดิม """
    return_detail = db.session.query(ReturnDetail).filter_by(id=return_id).with_for_update().first()
    if not return_detail:
        abort(404)

    new_doc_number = request.form.get("new_document_number", "").strip()
    if not new_doc_number:
        flash("กรุณาระบุหมายเลขฎีกาใหม่", "danger")
        return redirect(request.referrer)

    current_doc = return_detail.closing_document
    if current_doc and current_doc.document_number == new_doc_number:
        return redirect(request.referrer or url_for("advance_payment.closing_management"))

    target_doc = db.session.query(ClosingDocument).filter_by(document_number=new_doc_number).with_for_update().first()
    if target_doc and not target_doc.is_active:
        flash("ไม่สามารถย้ายรายการไปฎีกาที่ถูกยกเลิกแล้ว", "danger")
        return redirect(request.referrer or url_for("advance_payment.closing_management"))
    if not target_doc:
        target_doc = ClosingDocument(
            document_number=new_doc_number,
            filing_date=date.today(),
            total_amount=0,
            created_at=datetime.now(),
        )
        db.session.add(target_doc)
        db.session.flush()

    if current_doc:
        current_doc = db.session.query(ClosingDocument).filter_by(id=current_doc.id).with_for_update().first()
        current_doc.total_amount = max(0, current_doc.total_amount - return_detail.closing_amount)
    target_doc.total_amount += return_detail.closing_amount
    return_detail.closing_document = target_doc
    return_detail.status = "เอกสารตั้งฎีกา"

    db.session.commit()
    flash(f"อัปเดตเลขฎีกาเป็น {new_doc_number} เรียบร้อยแล้ว", "success")
    return redirect(request.referrer)

@bp.route("/finance/returns/<int:return_id>/proof")
@bp.route("/finance/returns/<int:return_id>/proof", endpoint="return_proof_detail")
@module_system_required({ADVANCE_PAYMENT_SYSTEM, FINANCE_SYSTEM})
def view_return_proof_detail(return_id):
    return_detail = db.session.query(ReturnDetail).get(return_id)
    if not return_detail:
        abort(404)

    borrowing_ticket = db.session.query(BorrowingTicket).get(return_detail.ticket_id)
    if not borrowing_ticket:
        abort(404)

    if _selected_system() == ADVANCE_PAYMENT_SYSTEM and (
        (not _is_current_coordinator() and borrowing_ticket.borrower_id != _current_user_id())
        or (_is_current_coordinator() and borrowing_ticket.creator_id != _current_user_id())
    ):
        abort(403)

    _prepare_document_display_list(return_detail.documents)

    proof_files = (
        db.session.query(ReturnProofFile)
        .filter(ReturnProofFile.return_detail_id == return_id)
        .order_by(ReturnProofFile.id.asc())
        .all()
    )
    receipt_items = (
        db.session.query(ReturnReceiptItem)
        .filter(ReturnReceiptItem.return_detail_id == return_id)
        .order_by(ReturnReceiptItem.id.asc())
        .all()
    )

    # รองรับไฟล์หลักฐานเก่าที่มี return_detail_id แต่ไม่มี receipt_item_id
    linked_item_ids = {
        file.receipt_item.id
        for file in proof_files
        if file.receipt_item
    }
    unlinked_files = [file for file in proof_files if not file.receipt_item]
    unlinked_items = [item for item in receipt_items if item.id not in linked_item_ids]
    for file, item in zip(unlinked_files, unlinked_items):
        file.receipt_item = item

    # Render every receipt item, including items without an uploaded proof file.
    proof_file_by_item_id = {}
    orphan_proof_files = []
    for file in proof_files:
        item = getattr(file, "receipt_item", None)
        if item is None:
            orphan_proof_files.append(file)
        elif item.id not in proof_file_by_item_id:
            proof_file_by_item_id[item.id] = file

    proof_rows = []
    for item in receipt_items:
        file = proof_file_by_item_id.get(item.id)
        proof_rows.append(
            file
            or SimpleNamespace(
                id=None,
                receipt_item=item,
                proof_reference=None,
                filename=None,
                original_filename=None,
                created_at=None,
            )
        )
    proof_rows.extend(orphan_proof_files)

    return render_template(
        "return_proof_detail.html",
        return_detail=return_detail,
        borrowing_ticket=borrowing_ticket,
        proof_files=proof_rows,
        pdf_reference_options=_pdf_reference_options(),
        pdf_fiscal_year_default=convert_to_fiscal_year(datetime.now().date()),
    )

@bp.route(
    "/finance/ticket/<int:ticket_id>/note",
    methods=["POST"]
)
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def update_finance_note(ticket_id):

    ticket = db.session.query(
        BorrowingTicket
    ).get(ticket_id)

    ticket.finance_note = request.form.get(
        "finance_note",
        ""
    )

    db.session.commit()

    flash("Note saved")

    return verification_view(ticket_id)

@bp.errorhandler(403)
def forbidden(_exception):
    return render_template("advance_payment/403.html"), 403

@bp.route("/staff/fund-request", methods=["GET", "POST"])
@module_system_required(PETTY_CASH_SYSTEM)
def staff_fund_request():
    user = db.session.query(StaffAccount).filter_by(id=_current_user_id()).first()
    if not user:
        abort(404)

    user_display_name = getattr(user, "name", None) or getattr(user, "fullname", None) or getattr(user, "email", None) or "ไม่พบข้อมูลชื่อ"
    user_display_position = getattr(user, "position", None) or "ไม่พบข้อมูลตำแหน่ง"
    setting = _resolve_petty_cash_setting(user)

    # A fund request must always be backed by an active petty-cash setting
    # for the current fiscal year. The UI disables the button when there is
    # no setting, but this backend check also blocks direct POST requests.
    if request.method == "POST" and (
        not setting
        or not getattr(setting, "id", None)
        or not getattr(setting, "valid", False)
        or getattr(setting, "fiscal_year", None) != _current_petty_cash_fiscal_year()
    ):
        return _validation_redirect_response(
            "ไม่พบการตั้งค่าเงินสดย่อยของหน่วยงานหรือปีงบประมาณปัจจุบัน",
            url_for(
                "advance_payment.staff_fund_request",
                form_type=request.values.get("form_type", FUND_REQUEST_FORM_PETTY_CASH),
            )
        )

    is_secretary = _is_current_secretary(user, setting)
    _attach_petty_cash_setting_people(setting)
    approved_borrowing_tickets = _get_approved_borrowing_tickets_for_setting(setting)
    dept_summary = _calculate_petty_cash_balance_summary(
        setting,
        user_id=user.id if not is_secretary and not (setting and setting.id) else None,
    )
    staff_department_name = _get_staff_department_name(user)
    staff_org = _get_staff_org(user) or (setting.org if setting else None) or _resolve_org_by_department_name(staff_department_name)
    department_employees = _serialize_org_department(staff_org).get("staff_members", []) if staff_org else []
    for ticket in approved_borrowing_tickets:
        _attach_borrowing_ticket_people(ticket)
    form = FundRequestForm(request.form)

    if request.method == "GET":
        form.requester_name.data = user_display_name
        form.requester_position.data = user_display_position
        # Use the staff/org name for employee lookup, and keep petty cash account data from the setting.
        if staff_org:
            form.department.data = staff_org.name
        elif staff_department_name:
            form.department.data = staff_department_name
        elif setting:
            form.department.data = setting.department_name

        if setting:
            form.account_number.data = setting.account_number

        form.period_year.data = str(datetime.now().year)

    if request.method == "POST" and form.validate():
        try:
            req_dept = (setting.department_name if setting else None) or _get_staff_department_name(user) or "ไม่ระบุหน่วยงาน"
            req_acc = setting.account_number if setting else ""
            form_type = form.form_type.data
            selected_borrowing_ticket = None
            requester_id = user.id
            available_budget = float(dept_summary.get("remaining_budget", 0.0) or 0.0)

            req_date = form.request_date.data if form.request_date.data else datetime.now().date()
            receive_interest = _coerce_date(request.form.get("receive_interest"))
            withdraw_intrest = _coerce_date(request.form.get("withdraw_intrest"))
            if form_type == FUND_REQUEST_FORM_BORROWING_TICKET:
                borrowing_ticket_id = request.form.get("borrowing_ticket_id", type=int)
                if not borrowing_ticket_id:
                    return _validation_redirect_response(
                        "กรุณาเลือกใบยืมเงินที่ต้องการเบิกผ่านบัญชีเงินสดย่อย",
                        url_for("advance_payment.staff_fund_request", form_type=FUND_REQUEST_FORM_BORROWING_TICKET),
                    )

                selected_borrowing_ticket = next(
                    (ticket for ticket in approved_borrowing_tickets if ticket.id == borrowing_ticket_id),
                    None,
                )
                if not selected_borrowing_ticket:
                    return _validation_redirect_response(
                        "ไม่พบใบยืมเงินที่สามารถใช้งานได้สำหรับหน่วยงานนี้ หรือใบยืมเงินถูกใช้สร้างใบเบิกแล้ว",
                        url_for("advance_payment.staff_fund_request", form_type=FUND_REQUEST_FORM_BORROWING_TICKET),
                    )

                borrower_user = getattr(selected_borrowing_ticket, "borrower_user", None)
                if is_secretary:
                    requester_id = getattr(borrower_user, "id", None) or selected_borrowing_ticket.borrower_id or user.id
                    req_name = selected_borrowing_ticket.borrower_name or getattr(borrower_user, "name", "") or user_display_name
                    req_pos = getattr(borrower_user, "position", "") or user_display_position or "ไม่พบข้อมูลตำแหน่ง"
                else:
                    requester_id = user.id
                    req_name = user_display_name
                    req_pos = user_display_position or "ไม่พบข้อมูลตำแหน่ง"
                req_dept = _get_staff_department_name(borrower_user, req_dept) or req_dept
                req_acc = selected_borrowing_ticket.account_number or req_acc
            else:
                if is_secretary:
                    selected_requester_id = request.form.get("requester_id", type=int)
                    selected_requester = next(
                        (employee for employee in department_employees if employee.get("id") == selected_requester_id),
                        None,
                    )
                    if not selected_requester:
                        return _validation_redirect_response(
                            "กรุณาเลือกผู้ขอเบิกจากรายชื่อบุคลากรในหน่วยงาน",
                            url_for("advance_payment.staff_fund_request", form_type=form_type),
                        )
                    requester_id = selected_requester_id
                    req_name = selected_requester.get("name", "")
                    req_pos = selected_requester.get("position", "")
                else:
                    requester_id = user.id
                    req_name = user_display_name
                    req_pos = user_display_position

            requested_amount = float(form.amount.data or 0.0)
            if form_type == FUND_REQUEST_FORM_BORROWING_TICKET and selected_borrowing_ticket:
                requested_amount = float(selected_borrowing_ticket.required_budget or 0.0)

            if form_type not in {FUND_REQUEST_FORM_INTEREST, FUND_REQUEST_FORM_BORROWING_TICKET} and requested_amount > available_budget:
                error_message = (
                    f"ยอดขอเบิก {requested_amount:,.2f} บาท เกินยอดคงเหลือ "
                    f"{available_budget:,.2f} บาท กรุณาปรับจำนวนเงินก่อนส่งแบบฟอร์ม"
                )
                redirect_kwargs = {"form_type": form_type}
                if selected_borrowing_ticket:
                    redirect_kwargs["borrowing_ticket_id"] = selected_borrowing_ticket.id
                return _validation_redirect_response(
                    error_message,
                    url_for("advance_payment.staff_fund_request", **redirect_kwargs),
                )

            # รายการใหม่ออกเลขที่ใบเบิกทันที โดยประเภทเบิกเงินยืมถือว่าเบิกเงินแล้ว
            new_request = FundRequest(
                requester_id=requester_id,
                creator_id=user.id,
                org_id=getattr(staff_org, "id", None),
                form_type=form_type,
                ticket_number=None,  # ระบบจะออกเลขที่ให้ทันทีหลังสร้างรายการ
                request_date=req_date,
                receive_interest=receive_interest if form_type == FUND_REQUEST_FORM_INTEREST else None,
                withdraw_intrest=withdraw_intrest if form_type == FUND_REQUEST_FORM_INTEREST else None,
                amount=form.amount.data,
                purpose=form.purpose.data if form_type == FUND_REQUEST_FORM_PETTY_CASH else ("ขออนุมัติเบิกดอกเบี้ย" if form_type == FUND_REQUEST_FORM_INTEREST else ""),
                period_year=_normalize_interest_period_value(request.form.get("period_year")) if form_type == FUND_REQUEST_FORM_INTEREST else "",
                borrowing_ticket_id=selected_borrowing_ticket.id if selected_borrowing_ticket else None,
                created_at=datetime.now(),
                status="เบิกเงินแล้ว" if form_type == FUND_REQUEST_FORM_BORROWING_TICKET else "อนุมัติแล้ว"
            )

            db.session.add(new_request)
            db.session.flush()

            if form_type == FUND_REQUEST_FORM_PETTY_CASH:
                descriptions = request.form.getlist("item_description[]")
                amounts = request.form.getlist("item_amount[]")
                categories = request.form.getlist("item_category[]")

                for i in range(len(descriptions)):
                    desc = descriptions[i].strip()
                    amt_str = amounts[i].strip().replace(",", "")
                    category = categories[i].strip()

                    if desc:
                        amt = float(amt_str) if amt_str else 0.0
                        item_obj = FundRequestItem(
                            fund_request_id=new_request.id,
                            description=desc,
                            amount=amt,
                            category_type=int(category) if category.isdigit() else 1,
                            created_at=datetime.now()
                        )
                        db.session.add(item_obj)

            if form_type == FUND_REQUEST_FORM_BORROWING_TICKET and selected_borrowing_ticket:
                ticket_amount = float(selected_borrowing_ticket.required_budget or 0)
                ticket_number = selected_borrowing_ticket.number or "-"
                ticket_name = selected_borrowing_ticket.borrowing_ticket_name or "ใบยืมเงิน"
                new_request.amount = ticket_amount
                new_request.purpose = f"เบิกเงินยืมผ่านบัญชีเงินสดย่อย บ.ย. {ticket_number}"
                new_request.request_date = req_date
                db.session.add(
                    FundRequestItem(
                        fund_request_id=new_request.id,
                        description=f"เบิกเงินยืมผ่านบัญชีเงินสดย่อยตามใบยืมเงิน บ.ย. {ticket_number}",
                        amount=ticket_amount,
                        category_type=5,
                        created_at=datetime.now(),
                    )
                )

            if form_type == FUND_REQUEST_FORM_INTEREST:
                # 1. ดึงค่าจาก Radio Button (จะได้ เช่น "มิถุนายน พ.ศ. 2567" หรือ "ธันวาคม พ.ศ. 2567")
                selected_period = request.form.get("period_year_radio", "")
                period_year_val = _normalize_interest_period_value(selected_period)

                withdrawal_proof_file = request.files.get("withdrawal_proof_file")
                new_request.period_year = period_year_val
                new_request.status = "เบิกเงินแล้ว"

                if withdrawal_proof_file and withdrawal_proof_file.filename:
                    original_filename = os.path.basename(withdrawal_proof_file.filename)
                    if original_filename:
                        upload_folder = os.path.join(
                            _upload_root(),
                            "fund_requests",
                            str(user.id),
                        )
                        os.makedirs(upload_folder, exist_ok=True)
                        proof_reference = f"uploads/fund_requests/{user.id}/{original_filename}"
                        withdrawal_proof_file.save(os.path.join(upload_folder, original_filename))
                        new_request.withdrawal_proof_reference = proof_reference
                        new_request.withdrawal_proof_filename = withdrawal_proof_file.filename

            _assign_fund_request_ticket_number(new_request, reference_date=req_date)
            db.session.commit()

            pdf_bytes = generate_fund_request_pdf(new_request)

            response = current_app.response_class(pdf_bytes, mimetype='application/pdf')
            response.headers['Content-Disposition'] = f'attachment; filename=Fund_Request_{new_request.id}.pdf'
            return response

        except Exception as e:
            db.session.rollback()
            import traceback
            traceback.print_exc()
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return _validation_error_response(f"เกิดข้อผิดพลาด: {str(e)}", 500)
            return f"เกิดข้อผิดพลาด: {str(e)}", 500

    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        form_errors = "; ".join(
            ", ".join(errors)
            for errors in form.errors.values()
        )
        return _validation_error_response(form_errors or "กรุณาตรวจสอบข้อมูลในฟอร์ม")

    selected_form_type = request.args.get("form_type", form.form_type.data or FUND_REQUEST_FORM_PETTY_CASH)
    selected_borrowing_ticket_id = request.args.get("borrowing_ticket_id", type=int)
    return render_template(
        "staff_fund_request.html",
        form=form,
        setting=setting,
        approved_borrowing_tickets=approved_borrowing_tickets,
        department_employees=department_employees,
        current_year_be=convert_to_fiscal_year(datetime.now().date()) + 543,
        selected_form_type=selected_form_type,
        selected_borrowing_ticket_id=selected_borrowing_ticket_id,
        is_secretary=is_secretary,
        current_user_display_name=user_display_name,
        current_user_display_position=user_display_position,
        dept_summary=dept_summary,
    )

@bp.route("/staff/fund-request/<int:request_id>/cancel", methods=["POST"])
@module_role_required(secretary_permission, SECRETARY_ROLE, PETTY_CASH_SYSTEM)
def cancel_fund_request(request_id):
    staff = current_user
    if not staff.is_authenticated or not _is_current_secretary(staff):
        abort(403)

    fund_req = db.session.query(FundRequest).get(request_id)
    if not fund_req:
        abort(404)

    if fund_req.status in {"ยกเลิก", "ส่งเบิกแล้ว", "ส่งเบิกครบแล้ว", "เบิกเงินสำเร็จ", "เคลียร์ยอดสำเร็จ"}:
        return _validation_error_response("ไม่สามารถยกเลิกรายการที่สิ้นสุดกระบวนการแล้วได้")

    cancellation_reason = request.form.get("cancellation_reason", "").strip()

    fund_req.status = "ยกเลิก"
    if hasattr(fund_req, 'rejection_comment'):
        fund_req.rejection_comment = cancellation_reason

    db.session.commit()
    flash("ยกเลิกใบเบิกเรียบร้อยแล้ว (สิ้นสุดกระบวนการ)", "info")
    return staff_fund_request_history()

@bp.route("/staff/fund-request-history", methods=["GET"])
@module_system_required(PETTY_CASH_SYSTEM)
def staff_fund_request_history():
    user = db.session.query(StaffAccount).filter_by(id=_current_user_id()).first()
    if not user:
        abort(404)

    setting = _resolve_petty_cash_setting(user)
    is_secretary = _is_current_secretary(user, setting)
    is_staff_user = not is_secretary

    fund_requests_query = db.session.query(FundRequest)
    history_org = _get_staff_org(user)
    if not history_org and setting:
        history_org = getattr(setting, "org", None) or _resolve_org_by_department_name(getattr(setting, "department_name", None))
    fund_requests_query = _fund_request_org_filter(
        fund_requests_query,
        history_org,
        getattr(setting, "department_name", None) or _get_staff_department_name(user),
    )
    if is_staff_user:
        fund_requests_query = fund_requests_query.filter(FundRequest.requester_id == user.id)
    fund_requests = fund_requests_query.order_by(FundRequest.id.desc()).all()
    for fund_request in fund_requests:
        fund_request.display_requester_name = _fund_request_requester_name(fund_request, "-")

    if is_staff_user or not (setting and setting.id):
        history_items = db.session.query(PettyCashClaimDetail)\
            .filter(
                PettyCashClaimDetail.user_id == user.id,
                PettyCashClaimDetail.status != "ฉบับร่าง",
            )\
            .order_by(PettyCashClaimDetail.id.desc()).all()
    else:
        history_items = db.session.query(PettyCashClaimDetail)\
            .filter(
                PettyCashClaimDetail.petty_cash_setting_id == setting.id,
                PettyCashClaimDetail.status != "ฉบับร่าง",
            )\
            .order_by(PettyCashClaimDetail.id.desc()).all()

    dept_summary = _calculate_petty_cash_balance_summary(
        setting,
        user_id=user.id if is_staff_user and not (setting and setting.id) else None,
    )
    dept_summary["total_claims"] = len(history_items)
    dept_summary["history"] = history_items

    if is_staff_user or not (setting and setting.id):
        claim_history = (
            db.session.query(PettyCashClaimDetail)
            .filter(PettyCashClaimDetail.user_id == user.id)
            .order_by(PettyCashClaimDetail.id.desc())
            .all()
        )
    else:
        claim_history = (
            db.session.query(PettyCashClaimDetail)
            .filter(PettyCashClaimDetail.petty_cash_setting_id == setting.id)
            .order_by(PettyCashClaimDetail.id.desc())
            .all()
        )

    for claim in claim_history:
        _attach_petty_cash_claim_context(claim)
        fund_request = claim.fund_request
        claim.claim_number = (
            claim.claim_number
            or (fund_request.ticket_number if fund_request and fund_request.ticket_number else None)
            or f"PC-{claim.id}"
        )
        claim.has_rejected_followup = (claim.status or "").strip() == "ปฏิเสธ"

    rejected_followup_fund_request_ids = set()
    if fund_requests:
        rejected_followup_fund_request_ids.update(
            fund_request_id
            for (fund_request_id,) in db.session.query(PettyCashClaimDetail.fund_request_id)
            .filter(
                PettyCashClaimDetail.fund_request_id.in_([fr.id for fr in fund_requests if getattr(fr, "id", None)]),
                PettyCashClaimDetail.status == "ปฏิเสธ",
            )
            .all()
            if fund_request_id is not None
        )
        rejected_followup_fund_request_ids.update(
            fund_request_id
            for (fund_request_id,) in db.session.query(ParcelReturnDetail.fund_request_id)
            .filter(
                ParcelReturnDetail.fund_request_id.in_([fr.id for fr in fund_requests if getattr(fr, "id", None)]),
                ParcelReturnDetail.status == "ปฏิเสธ",
            )
            .all()
            if fund_request_id is not None
        )
    for fund_request in fund_requests:
        fund_request.has_rejected_followup = (
            (fund_request.status or "").strip() == "ปฏิเสธ"
            or fund_request.id in rejected_followup_fund_request_ids
        )

    return render_template(
        "staff_fund_request_history.html",
        is_secretary=is_secretary,
        setting=setting,
        fund_requests=fund_requests,
        claim_history=claim_history,
        dept_summary=dept_summary
    )


@bp.route("/staff/petty-cash-claims/<int:claim_id>/claim-number", methods=["POST"])
@module_system_required(PETTY_CASH_SYSTEM)
def update_petty_cash_claim_number(claim_id):
    staff = current_user

    claim = db.session.query(PettyCashClaimDetail).get(claim_id)
    if not claim:
        abort(404)

    can_edit = False
    if not _is_current_secretary():
        can_edit = claim.user_id == staff.id
    else:
        setting = _resolve_petty_cash_setting(staff)
        can_edit = bool(
            (setting and setting.id and claim.petty_cash_setting_id == setting.id)
            or claim.user_id == staff.id
        )

    if not can_edit:
        abort(403)

    claim_number = request.form.get("claim_number", "").strip()
    if not claim_number:
        return _validation_error_response("กรุณาระบุเลขอว.")

    claim.claim_number = claim_number
    db.session.commit()
    flash("บันทึกเลขอว. เรียบร้อยแล้ว", "success")
    return staff_fund_request_history()

@bp.route("/staff/fund-request/<int:request_id>/pdf")
@module_system_required(PETTY_CASH_SYSTEM)
def export_fund_request_pdf(request_id):
    fund_req = db.session.query(FundRequest).get(request_id)
    if not fund_req:
        abort(404)

    if _selected_system() == PETTY_CASH_SYSTEM:
        staff = current_user
        setting = _resolve_petty_cash_setting(staff)
        history_org = _get_staff_org(staff)
        if not history_org and setting:
            history_org = getattr(setting, "org", None) or _resolve_org_by_department_name(getattr(setting, "department_name", None))
        scoped_request = _fund_request_org_filter(
            db.session.query(FundRequest).filter(FundRequest.id == request_id),
            history_org,
            getattr(setting, "department_name", None) or _get_staff_department_name(staff),
        ).first()
        if not _is_current_secretary():
            scoped_request = (
                _fund_request_org_filter(
                    db.session.query(FundRequest).filter(
                        FundRequest.id == request_id,
                        FundRequest.requester_id == staff.id,
                    ),
                    history_org,
                    getattr(setting, "department_name", None) or _get_staff_department_name(staff),
                )
                .first()
            )
        if scoped_request is None:
            abort(403)
        
    pdf_bytes = generate_fund_request_pdf(fund_req)
    
    response = current_app.response_class(pdf_bytes, mimetype='application/pdf')
    if fund_req.form_type == FUND_REQUEST_FORM_BORROWING_TICKET:
        filename = f"Borrowing_Ticket_Petty_Cash_{request_id}.pdf"
    else:
        filename = f"FundRequest_Form{fund_req.form_type}_{request_id}.pdf"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response


def _pdf_reference_options():
    return {
        "product_codes": db.session.query(ProductCode).order_by(ProductCode.id.asc()).all(),
        "cost_centers": db.session.query(CostCenter).order_by(CostCenter.id.asc()).all(),
        "iocodes": db.session.query(IOCode).filter(IOCode.is_active.is_(True)).order_by(IOCode.id.asc()).all(),
    }


def _save_pdf_reference_data(document, borrowing_ticket=None, *, require_reference=True):
    reference_number = request.form.get("reference_number", "").strip()
    reference_date = request.form.get("reference_date", "").strip()
    fiscal_year = request.form.get("fiscal_year", "").strip()
    product_code_id = request.form.get("product_code_id", "").strip()
    cost_center_id = request.form.get("cost_center_id", "").strip()
    iocode_id = request.form.get("iocode_id", "").strip()
    if borrowing_ticket is not None:
        require_reference = True
        reference_number = getattr(borrowing_ticket, "aip_ref_no", None) or reference_number
        reference_date = getattr(borrowing_ticket, "aip_ref_date", None) or reference_date
    else:
        # The PDF modal no longer collects these fields. Reuse the values
        # already saved on the claim instead of treating the missing form
        # fields as an incomplete reference.
        reference_number = reference_number or getattr(document, "reference_number", None)
        reference_date = reference_date or getattr(document, "reference_date", None)
    if not all((fiscal_year, product_code_id, cost_center_id, iocode_id)) or (
        require_reference and not all((reference_number, reference_date))
    ):
        abort(400, description="กรุณากรอกข้อมูลอ้างอิงสำหรับเอกสาร PDF ให้ครบถ้วน")
    if not require_reference:
        parsed_date = None
    elif isinstance(reference_date, date):
        parsed_date = reference_date
    else:
        try:
            parsed_date = datetime.strptime(reference_date, "%Y-%m-%d").date()
        except ValueError:
            abort(400, description="รูปแบบวันที่หนังสือไม่ถูกต้อง")
    try:
        fiscal_year = int(fiscal_year)
    except ValueError:
        abort(400, description="ปีงบประมาณไม่ถูกต้อง")
    if fiscal_year >= 2400:
        fiscal_year -= 543
    if fiscal_year <= 0:
        abort(400, description="ปีงบประมาณไม่ถูกต้อง")

    if require_reference:
        document.reference_number = reference_number
        document.reference_date = parsed_date
    document.fiscal_year = fiscal_year
    document.product_code = db.session.get(ProductCode, product_code_id)
    document.cost_center = db.session.get(CostCenter, cost_center_id)
    document.iocode = db.session.get(IOCode, iocode_id)
    if not all((document.product_code, document.cost_center, document.iocode)):
        abort(400, description="ไม่พบข้อมูลรหัสงบประมาณที่เลือก")
    db.session.commit()


@bp.route("/staff/petty-cash-claim/<int:claim_id>/pdf", methods=["GET", "POST"])
@module_system_required(PETTY_CASH_SYSTEM)
def export_petty_cash_claim_pdf(claim_id):
    claim = db.session.query(PettyCashClaimDetail).get(claim_id)
    if not claim:
        abort(404)

    if _selected_system() == PETTY_CASH_SYSTEM:
        staff = current_user
        setting = _resolve_petty_cash_setting(staff)
        can_view = bool(
            _is_current_secretary()
            or claim.user_id == staff.id
            or (setting and claim.petty_cash_setting_id == setting.id)
        )
        if not can_view:
            abort(403)

    if request.method == "GET":
        return redirect(url_for("advance_payment.petty_cash_claim_detail", claim_id=claim_id))

    claim_type = request.form.get("claim_type")
    if claim_type not in ("1", "2"):
        claim_type = "1" if claim.reference_number and claim.reference_date else "2"
    if claim_type not in ("1", "2"):
        abort(400, description="ประเภทเอกสาร PDF ไม่ถูกต้อง")
    _save_pdf_reference_data(claim, require_reference=claim_type == "1")
    _attach_petty_cash_claim_context(claim)
    pdf_bytes = generate_petty_claim(claim, claim_type=claim_type)

    response = current_app.response_class(pdf_bytes, mimetype='application/pdf')
    filename = f"Petty_Claim_{claim_id}.pdf"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response


@bp.route("/finance/returns/<int:return_id>/pdf", methods=["GET", "POST"])
@module_system_required({ADVANCE_PAYMENT_SYSTEM, FINANCE_SYSTEM})
def export_ticket_return_pdf(return_id):
    return_detail = db.session.query(ReturnDetail).get(return_id)
    if not return_detail:
        abort(404)

    borrowing_ticket = db.session.query(BorrowingTicket).get(return_detail.ticket_id)
    if not borrowing_ticket:
        abort(404)

    if _selected_system() == ADVANCE_PAYMENT_SYSTEM and (
        (not _is_current_coordinator() and borrowing_ticket.borrower_id != _current_user_id())
        or (_is_current_coordinator() and borrowing_ticket.creator_id != _current_user_id())
    ):
        abort(403)

    if request.method == "GET":
        return redirect(url_for("advance_payment.return_proof_detail", return_id=return_id))

    return_detail.borrowing_ticket = borrowing_ticket
    _save_pdf_reference_data(return_detail, borrowing_ticket=borrowing_ticket)
    pdf_bytes = generate_ticket_return(return_detail)

    response = current_app.response_class(pdf_bytes, mimetype="application/pdf")
    response.headers["Content-Disposition"] = (
        f"attachment; filename=Ticket_Return_{return_id}.pdf"
    )
    return response


def get_department_data_service(dept_name=None):
    """แหล่งข้อมูลหน่วยงานจาก MIS Org model."""
    if dept_name:
        org = _resolve_org_by_department_name(dept_name)
        return _serialize_org_department(org)

    orgs = db.session.query(Org).order_by(Org.name.asc()).all()
    return {
        org.name: _serialize_org_department(org)
        for org in orgs
        if org and org.name
    }

@bp.route("/api/employees/departments", methods=["GET"])
@module_system_required(PETTY_CASH_SYSTEM)
def api_get_department_employees():
    """ API สำหรับส่ง JSON ไปยังระบบ Frontend """
    dept = request.args.get("department")
    data = get_department_data_service(dept)

    if dept and not data:
        return jsonify([]) 
    
    staff_list = data.get("staff_members", []) if isinstance(data, dict) else []
    return jsonify(staff_list)

CATEGORY_CHOICES = {
    1: "ค่าตอบแทน (เช่น ค่าเบี้ยเลี้ยง, ค่าตอบแทนวิทยากร)",
    2: "ค่าใช้สอย (เช่น ค่าซ่อมแซม, ค่าเช่า, ค่าจ้างเหมา)",
    3: "ค่าวัสดุ (เช่น เครื่องเขียน, วัสดุสำนักงาน, อุปกรณ์)",
    4: "ค่าสาธารณูปโภค (เช่น ค่าที่พัก, ค่าเดินทาง, ค่าค่าน้ำ-ไฟ)",
    5: "อื่น ๆ",
    6: "โอนคืนบัญชีหน่วย"
}


@bp.route("/coordinator/petty-cash-claim/autosave-draft", methods=["POST"], endpoint="coordinator_petty_cash_claim_autosave_draft")
@bp.route("/borrower/petty-cash-claim/autosave-draft", methods=["POST"], endpoint="borrower_petty_cash_claim_autosave_draft")
@module_system_required(ADVANCE_PAYMENT_SYSTEM)
def autosave_petty_cash_claim_draft():
    user_id = _current_user_id()
    data = request.get_json() or {}
    
    fund_request_id = data.get("fund_request_id")
    items = data.get("items", [])
    announcements = data.get("announcements", [])
    reference_number = (data.get("reference_number") or "").strip()
    reference_date_raw = (data.get("reference_date") or "").strip()

    # 1. ดึง Setting ของ StaffAccount ปัจจุบันก่อน (ถ้าไม่มีค่อย fallback ไปตัว active ตัวแรก)
    staff = current_user
    setting = _resolve_petty_cash_setting(staff)

    # 2. ค้นหา PettyCashClaimDetail สถานะ Draft ของ user รายนี้
    query = db.session.query(PettyCashClaimDetail).filter(
        PettyCashClaimDetail.user_id == user_id,
        PettyCashClaimDetail.status == "ฉบับร่าง"
    )
    
    if fund_request_id and str(fund_request_id).isdigit():
        query = query.filter(PettyCashClaimDetail.fund_request_id == int(fund_request_id))

    claim_detail = query.order_by(PettyCashClaimDetail.id.desc()).first()

    # 3. หากยังไม่มี Draft ให้สร้างขึ้นใหม่
    if not claim_detail:
        claim_detail = PettyCashClaimDetail(
            user_id=user_id,
        petty_cash_setting_id=setting.id if setting and setting.id else None,
            fund_request_id=int(fund_request_id) if fund_request_id and str(fund_request_id).isdigit() else None,
            status="ฉบับร่าง",
            total_amount=0.0,
            created_at=datetime.now()
        )
        db.session.add(claim_detail)
        db.session.flush()
    else:
        # อัปเดตผูกกับ fund_request_id และ setting_id ล่าสุด
        if fund_request_id and str(fund_request_id).isdigit():
            claim_detail.fund_request_id = int(fund_request_id)
        if setting and setting.id and not claim_detail.petty_cash_setting_id:
            claim_detail.petty_cash_setting_id = setting.id
            
        # ลบ items เดิมออกก่อนเซฟชุดใหม่
        db.session.query(PettyCashClaimItem).filter_by(claim_id=claim_detail.id).delete()

    total_amount = 0.0

    # 4. บันทึกรายการเบิกสดย่อย (PettyCashClaimItem)
    for item in items:
        r_date = _coerce_date(item.get("receipt_date"))
        cat_type_str = str(item.get("category_type") or "1").strip()
        cat_type_int = int(cat_type_str) if cat_type_str.isdigit() else 1
        
        try:
            amt = float(str(item.get("amount") or 0.0).replace(",", ""))
        except (ValueError, TypeError):
            amt = 0.0

        # เงื่อนไขเฉพาะสำหรับหมวด 6 (โอนคืน) vs หมวด 1-5
        if cat_type_str == "6" or cat_type_int == 6:
            item_desc = "เงินโอนคงเหลือจากการยืมเงินสดย่อย"
            item_custom_cat = ""
            # หมวด 6 ไม่สะสมยอดรวมส่งเบิก
        else:
            item_desc = (item.get("description") or "").strip()
            total_amount += amt

        claim_item = PettyCashClaimItem(
            claim_id=claim_detail.id,
            receipt_date=r_date,
            description=item_desc,
            category_type=cat_type_int,
            amount=amt
        )
        db.session.add(claim_item)

    claim_detail.total_amount = total_amount
    if reference_number and reference_date_raw:
        try:
            claim_detail.reference_date = datetime.strptime(reference_date_raw, "%Y-%m-%d").date()
            claim_detail.reference_number = reference_number
        except ValueError:
            pass
    elif not reference_number and not reference_date_raw:
        claim_detail.reference_number = None
        claim_detail.reference_date = None

    # 5. บันทึกเอกสารประกาศประกอบ (Documents)
    _replace_claim_detail_documents(claim_detail, announcements)

    db.session.commit()

    saved_time = datetime.now().strftime("%H:%M:%S")
    return jsonify({
        "success": True, 
        "saved_at": saved_time, 
        "claim_id": claim_detail.id
    })

@bp.route("/staff/petty-cash/claim", methods=["GET", "POST"])
@module_system_required({PETTY_CASH_SYSTEM, FINANCE_SYSTEM})
def submit_petty_cash_claim(_render_after_post=False, _forced_fund_request_id=None):
    user_id = _current_user_id()
    current_role = _current_module_role() or getattr(current_user, "role", None)
    if _selected_system() not in {PETTY_CASH_SYSTEM, FINANCE_SYSTEM}:
        abort(403)

    setting = _resolve_petty_cash_setting(current_user)
    is_staff_user = _selected_system() == PETTY_CASH_SYSTEM and not _is_current_secretary()
    is_finance_user = (current_role == "finance")
    can_submit_claim = _selected_system() == PETTY_CASH_SYSTEM

    approved_fund_requests = []
    if can_submit_claim:
        fund_request_query = db.session.query(FundRequest).filter(FundRequest.requester_id == user_id)
        fund_request_query = _fund_request_org_filter(
            fund_request_query, _get_staff_org(current_user) or getattr(setting, "org", None), getattr(setting, "department_name", None)
        )
        approved_fund_requests = [
            fund_request for fund_request in fund_request_query.order_by(FundRequest.id.desc()).all()
            if (fund_request.status or "").strip() == "อนุมัติแล้ว"
        ]
    elif setting and setting.id:
        setting_org = getattr(setting, "org", None) or _resolve_org_by_department_name(setting.department_name)
        fund_request_query = db.session.query(FundRequest).filter(FundRequest.requester_id == user_id)
        fund_request_query = _fund_request_org_filter(fund_request_query, setting_org, setting.department_name)
        approved_fund_requests = [
            fund_request for fund_request in fund_request_query.order_by(FundRequest.id.desc()).all()
            if (fund_request.status or "").strip() == "อนุมัติแล้ว"
        ]
    else:
        approved_fund_requests = [
            fund_request
            for fund_request in db.session.query(FundRequest).filter(
                FundRequest.requester_id == user_id,
            ).order_by(FundRequest.id.desc()).all()
            if (fund_request.status or "").strip() == "อนุมัติแล้ว"
        ]

    # 2. ตรวจสอบการเลือก Fund Request เพื่อ Auto-fill ในหน้า Submit Claim
    selected_fund_request = None
    selected_fr_id = (
        _forced_fund_request_id
        if _forced_fund_request_id is not None
        else request.args.get("fund_request_id", type=int)
    )
    if selected_fr_id:
        selected_request_query = db.session.query(FundRequest).filter_by(id=selected_fr_id)
        if not can_submit_claim and not is_finance_user:
            selected_request_query = selected_request_query.filter_by(requester_id=user_id)
        selected_fund_request = selected_request_query.first()

    if request.method == "POST" and not _render_after_post:
        action = request.form.get("action", "submit")
        is_draft = (action == "draft")

        receipt_dates = request.form.getlist("receipt_date[]")
        descriptions = request.form.getlist("description[]")
        category_types = request.form.getlist("category_type[]")
        amounts = request.form.getlist("amount[]")
        announcement_ids = request.form.getlist("announcement_ids[]")
        announcement_titles = request.form.getlist("announcement_titles[]")
        reference_number = (request.form.get("reference_number") or "").strip()
        reference_date_raw = (request.form.get("reference_date") or "").strip()
        reference_files = [
            file_storage
            for file_storage in request.files.getlist("reference_files[]")
            if file_storage and file_storage.filename
        ]
        existing_reference_paths = request.form.getlist("existing_reference_files[]")
        existing_reference_names = request.form.getlist("existing_reference_filenames[]")
        fund_request_id_raw = (request.form.get("fund_request_id") or "").strip()
        fund_request_id = int(fund_request_id_raw) if fund_request_id_raw.isdigit() else None
        no_reference_info = request.form.get("has_reference_info") == "true"

        if no_reference_info:
            reference_number = ""
            reference_date_raw = ""
            reference_files = []
            existing_reference_paths = []
            existing_reference_names = []

        reference_date = None
        if reference_number or reference_date_raw:
            if not reference_number or not reference_date_raw:
                return _validation_redirect_response(
                    "กรุณากรอกเลขที่อนุมัติในหลักการและวันที่หนังสือให้ครบถ้วน หรือเว้นว่างทั้งสองช่อง",
                    request.referrer or url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id or None),
                )
            try:
                reference_date = datetime.strptime(reference_date_raw, "%Y-%m-%d").date()
            except ValueError:
                return _validation_redirect_response(
                    "รูปแบบวันที่หนังสืออนุมัติไม่ถูกต้อง",
                    request.referrer or url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id or None),
                )

        existing_reference_files = [
            (path, existing_reference_names[index] if index < len(existing_reference_names) else "reference")
            for index, path in enumerate(existing_reference_paths)
            if path
        ]
        if len(existing_reference_files) + len(reference_files) > 2:
            return _validation_redirect_response(
                "แนบไฟล์เอกสารอ้างอิงได้ไม่เกิน 2 ไฟล์",
                request.referrer or url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id or None),
            )

        parcel_amount_raw = (request.form.get("parcel_amount") or "").replace(",", "").strip()
        parcel_items_description = (request.form.get("items_description") or "").strip()
        parcel_sent_date_raw = (request.form.get("sent_date") or "").strip()
        has_parcel_data = any((parcel_amount_raw, parcel_items_description, parcel_sent_date_raw))
        parcel_amount = None
        parcel_sent_date = None

        if not is_draft and has_parcel_data:
            if not fund_request_id:
                return _validation_redirect_response(
                    "กรุณาเลือกคำขอเบิกเงินก่อนส่งข้อมูลพัสดุ",
                    request.referrer or url_for("advance_payment.submit_petty_cash_claim"),
                )
            if not parcel_amount_raw or not parcel_items_description or not parcel_sent_date_raw:
                return _validation_redirect_response(
                    "กรุณากรอกข้อมูลส่งคืนฝ่ายพัสดุให้ครบถ้วน",
                    request.referrer or url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id),
                )
            try:
                parcel_amount = float(parcel_amount_raw)
                parcel_sent_date = datetime.strptime(parcel_sent_date_raw, "%Y-%m-%d").date()
                if parcel_amount < 0:
                    raise ValueError
            except (TypeError, ValueError):
                return _validation_redirect_response(
                    "กรุณาระบุข้อมูลส่งคืนฝ่ายพัสดุให้ถูกต้อง",
                    request.referrer or url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id),
                )

        has_claim_data = any(
            value.strip()
            for values in (receipt_dates, descriptions, amounts)
            for value in values
            if value
        ) or any(file_storage and file_storage.filename for file_storage in request.files.values())
        if not is_draft and not has_claim_data and not has_parcel_data:
            return _validation_redirect_response(
                "กรุณากรอกข้อมูลรายการเบิกหรือข้อมูลส่งคืนฝ่ายพัสดุอย่างน้อยหนึ่งรายการ",
                request.referrer or url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id),
            )
        if not is_draft and not has_claim_data:
            receipt_dates = []
            descriptions = []
            category_types = []
            amounts = []

        if not is_draft and not has_claim_data and parcel_amount is not None:
            fund_totals = _calculate_fund_request_totals(fund_request_id)
            projected_total = fund_totals["cumulative_total"] + parcel_amount
            if _is_over_limit(projected_total, fund_totals["request_amount"]):
                return _redirect_with_limit_popup(
                    request.referrer or url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id),
                    (
                        "ยอดรวมใบเบิกเงินสดย่อยและส่งคืนพัสดุจะเป็น "
                        f"{_format_currency_amount(projected_total)} บาท ซึ่งเกินยอดขอเบิก "
                        f"{_format_currency_amount(fund_totals['request_amount'])} บาท"
                    ),
                )
            _create_parcel_return_record(
                ticket_id=None,
                fund_request_id=fund_request_id,
                amount=parcel_amount,
                items_description=parcel_items_description,
                sent_date=parcel_sent_date,
                status="รอตรวจสอบ",
            )
            db.session.commit()
            flash("บันทึกข้อมูลการส่งคืนฝ่ายพัสดุเรียบร้อยแล้ว", "success")
            return submit_petty_cash_claim(
                _render_after_post=True,
                _forced_fund_request_id=fund_request_id,
            )

        parsed_items = []
        total_claim_amount = 0.0
        old_receipt_count = 0

        for i in range(len(receipt_dates)):
            r_date = _coerce_date(receipt_dates[i]) if i < len(receipt_dates) and receipt_dates[i] else None
            cat_val_str = str(category_types[i]).strip() if i < len(category_types) and category_types[i] else "1"
            cat_val_int = int(cat_val_str) if cat_val_str.isdigit() else 1

            if not is_draft and (
                not r_date
                or not (descriptions[i].strip() if i < len(descriptions) else "")
                or not (amounts[i].strip() if i < len(amounts) else "")
            ):
                return _validation_redirect_response(
                    f"รายการที่ {i + 1} ต้องกรอกวันที่ รายละเอียด และจำนวนเงินให้ครบถ้วน",
                    request.referrer or url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id or None),
                )

            try:
                amt = float(str(amounts[i] or 0).replace(",", "")) if i < len(amounts) else 0.0
            except (ValueError, TypeError):
                amt = 0.0

            if not is_draft and amt > 20000 and cat_val_int != 6:
                return _validation_redirect_response(
                    "เงินสดย่อยจ่ายได้ครั้งละไม่เกินสองหมื่นบาท",
                    request.referrer or url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id or None),
                )

            if not is_draft and r_date and _receipt_requires_additional_document(r_date):
                old_receipt_count += 1

            if cat_val_str == "6" or cat_val_int == 6:
                item_desc = "เงินโอนคงเหลือจากการยืมเงินสดย่อย"
            else:
                item_desc = (descriptions[i] or "").strip() if i < len(descriptions) else ""
                total_claim_amount += amt

            parsed_items.append(
                {
                    "receipt_date": r_date,
                    "description": item_desc,
                    "category_type": cat_val_int,
                    "amount": amt,
                }
            )

        proof_file_error = _proof_file_validation_error(len(parsed_items), is_draft=is_draft)
        if proof_file_error:
            return _validation_redirect_response(
                proof_file_error,
                request.referrer or url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id or None),
            )

        existing_draft_query = db.session.query(PettyCashClaimDetail).filter_by(
            user_id=user_id,
            status="ฉบับร่าง",
        )
        if fund_request_id is not None:
            existing_draft_query = existing_draft_query.filter(
                PettyCashClaimDetail.fund_request_id == fund_request_id
            )
        existing_draft = existing_draft_query.first()

        if not is_draft and fund_request_id:
            fund_totals = _calculate_fund_request_totals(
                fund_request_id,
                exclude_claim_id=existing_draft.id if existing_draft else None,
            )
            projected_total = fund_totals["cumulative_total"] + total_claim_amount + (parcel_amount or 0)
            if _is_over_limit(projected_total, fund_totals["request_amount"]):
                return _redirect_with_limit_popup(
                    request.referrer or url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id or None),
                    (
                        "ยอดรวมใบเบิกเงินสดย่อยและส่งคืนพัสดุจะเป็น "
                        f"{_format_currency_amount(projected_total)} บาท "
                        f"ซึ่งเกินยอดขอเบิก {_format_currency_amount(fund_totals['request_amount'])} บาท"
                    ),
                )

        if existing_draft:
            if fund_request_id is not None and existing_draft.fund_request_id != fund_request_id:
                existing_draft.fund_request_id = fund_request_id
            old_items = db.session.query(PettyCashClaimItem).filter_by(claim_id=existing_draft.id).all()
            for oi in old_items:
                db.session.query(PettyCashClaimProofFile).filter_by(claim_item_id=oi.id).delete()
            db.session.query(PettyCashClaimItem).filter_by(claim_id=existing_draft.id).delete()
            db.session.query(PettyCashClaimProofFile).filter_by(
                claim_id=existing_draft.id,
                claim_item_id=None,
            ).delete()
            claim_detail = existing_draft
        else:
            claim_detail = PettyCashClaimDetail(
                user_id=user_id,
                petty_cash_setting_id=setting.id if setting and setting.id else None,
                fund_request_id=fund_request_id
            )
            db.session.add(claim_detail)

        if setting and setting.id and not claim_detail.petty_cash_setting_id:
            claim_detail.petty_cash_setting_id = setting.id

        # บันทึก Fund Request ID ที่ผูกกับเอกสารฉบับนี้
        if hasattr(claim_detail, 'fund_request_id'):
            claim_detail.fund_request_id = fund_request_id
        claim_detail.reference_number = reference_number or None
        claim_detail.reference_date = reference_date

        legacy_uploaded_files = request.files.getlist("proof_file[]")
        legacy_existing_file_paths = request.form.getlist("existing_proof_files[]")
        legacy_existing_file_names = request.form.getlist("existing_proof_filenames[]")

        claim_detail.status = (
            "ฉบับร่าง"
            if is_draft
            else (
                "เสร็จสิ้นกระบวนการ"
                if parsed_items and all(item["category_type"] == 6 for item in parsed_items)
                else "รอตรวจสอบ"
            )
        )
        claim_detail.created_at = datetime.now()
        db.session.flush()

        for i, item_data in enumerate(parsed_items):
            item = PettyCashClaimItem(
                claim_id=claim_detail.id,
                receipt_date=item_data["receipt_date"],
                description=item_data["description"],
                category_type=item_data["category_type"],
                amount=item_data["amount"]
            )
            db.session.add(item)
            db.session.flush()

            uploaded_files = request.files.getlist(f"proof_files_{i}[]")
            if not uploaded_files and i < len(legacy_uploaded_files):
                uploaded_files = [legacy_uploaded_files[i]]

            for file_storage in uploaded_files:
                if not file_storage or not file_storage.filename:
                    continue
                original_filename = os.path.basename(file_storage.filename)
                if not original_filename:
                    continue

                upload_folder = os.path.join(_upload_root(), f"petty_cash/{user_id}")
                os.makedirs(upload_folder, exist_ok=True)
                proof_path = f"uploads/petty_cash/{user_id}/{original_filename}"
                file_storage.save(os.path.join(upload_folder, original_filename))

                proof_file_record = PettyCashClaimProofFile(
                    claim_id=claim_detail.id,
                    claim_item_id=item.id,
                    proof_reference=proof_path,
                    filename=original_filename,
                    created_at=datetime.now()
                )
                db.session.add(proof_file_record)

            existing_file_paths = request.form.getlist(f"existing_proof_files_{i}[]")
            existing_file_names = request.form.getlist(f"existing_proof_filenames_{i}[]")
            if not existing_file_paths and i < len(legacy_existing_file_paths):
                existing_file_paths = [legacy_existing_file_paths[i]] if legacy_existing_file_paths[i] else []
                existing_file_names = [legacy_existing_file_names[i] if i < len(legacy_existing_file_names) else "receipt"]
            for file_index, existing_file_path in enumerate(existing_file_paths):
                if existing_file_path:
                    proof_file_record = PettyCashClaimProofFile(
                        claim_id=claim_detail.id,
                        claim_item_id=item.id,
                        proof_reference=existing_file_path,
                        filename=existing_file_names[file_index] if file_index < len(existing_file_names) else "receipt",
                        created_at=datetime.now()
                    )
                    db.session.add(proof_file_record)

        for file_storage in reference_files:
            original_filename = os.path.basename(file_storage.filename)
            if not original_filename:
                continue
            upload_folder = os.path.join(_upload_root(), f"petty_cash/{user_id}")
            os.makedirs(upload_folder, exist_ok=True)
            reference_path = f"uploads/petty_cash/{user_id}/{original_filename}"
            file_storage.save(os.path.join(upload_folder, original_filename))
            db.session.add(PettyCashClaimProofFile(
                claim_id=claim_detail.id,
                claim_item_id=None,
                proof_reference=reference_path,
                filename=original_filename,
                created_at=datetime.now(),
            ))

        for existing_path, existing_name in existing_reference_files:
            db.session.add(PettyCashClaimProofFile(
                claim_id=claim_detail.id,
                claim_item_id=None,
                proof_reference=existing_path,
                filename=existing_name,
                created_at=datetime.now(),
            ))

        # บันทึกยอดรวมเงินเฉพาะส่วนที่จะขอเบิกตั้งเรื่องคืนจากการเงิน (ไม่รวมหมวด 6)
        claim_detail.amount = total_claim_amount
        if hasattr(claim_detail, 'total_amount'):
            claim_detail.total_amount = total_claim_amount

        # ปรับปรุงส่วนบันทึกเอกสารประกาศประกอบ ให้รองรับมากกว่า 1 รายการ และบันทึกถูกต้อง
        announcement_references = []
        for i, title in enumerate(announcement_titles):
            cleaned_title = (title or "").strip()
            cleaned_id = (announcement_ids[i] if i < len(announcement_ids) else "").strip()
            if cleaned_title or cleaned_id:
                announcement_references.append({
                    "id": cleaned_id,
                    "title": cleaned_title,
                })
        _replace_claim_detail_documents(claim_detail, announcement_references)

        if parcel_amount is not None:
            _create_parcel_return_record(
                ticket_id=None,
                fund_request_id=fund_request_id,
                amount=parcel_amount,
                items_description=parcel_items_description,
                sent_date=parcel_sent_date,
                status="รอตรวจสอบ",
            )

        # ตรวจสอบยอดและเปลี่ยนสถานะ FundRequest เมื่อส่งเบิก (ไม่ใช่ Draft)
        if not is_draft and fund_request_id:
            fund_req = db.session.query(FundRequest).get(fund_request_id)
            if fund_req:
                _recalculate_fund_request_submission_status(fund_req.id)

        db.session.commit()
        if not is_draft:
            _send_notification_email(claim_detail, object_type="petty_claim")

        if not is_draft and old_receipt_count > 0:
            flash(
                f"พบ {old_receipt_count} รายการที่มีใบเสร็จเกิน 10 วัน กรุณาจัดทำเอกสารขออนุมัติเบิกจ่ายล่าช้าเกิน 30 วัน",
                "warning",
            )

        if is_draft:
            flash("บันทึกฉบับร่างเรียบร้อยแล้ว", "success")
        else:
            flash("ส่งใบเบิกเงินสดย่อยเรียบร้อยแล้ว", "success")

        return petty_cash_claim_detail(claim_detail.id)

    claim_query = db.session.query(PettyCashClaimDetail).filter_by(
        user_id=user_id,
        status="ฉบับร่าง",
    )
    if selected_fund_request:
        claim_query = claim_query.filter(PettyCashClaimDetail.fund_request_id == selected_fund_request.id)
    claim_detail = claim_query.first()
    _attach_petty_cash_claim_context(claim_detail)

    history_fund_request = selected_fund_request
    if history_fund_request is None and claim_detail and getattr(claim_detail, "fund_request", None):
        history_fund_request = claim_detail.fund_request

    claim_history = []
    parcel_return_history = []
    fund_request_total_info = {"request_amount": 0.0, "parcel_total": 0.0}
    if history_fund_request:
        fund_request_total_info = _calculate_fund_request_totals(
            history_fund_request.id,
            exclude_claim_id=claim_detail.id if claim_detail else None,
        )
        claim_history = (
            db.session.query(PettyCashClaimDetail)
            .filter(
                PettyCashClaimDetail.fund_request_id == history_fund_request.id,
                PettyCashClaimDetail.status != "ฉบับร่าง",
            )
            .order_by(PettyCashClaimDetail.created_at.desc())
            .all()
        )
        for claim in claim_history:
            _attach_petty_cash_claim_context(claim)
            claim.items_description_summary = ", ".join(
                item.description for item in claim.items if (item.description or "").strip()
            ) or "-"

        parcel_return_history = (
            db.session.query(ParcelReturnDetail)
            .filter(ParcelReturnDetail.fund_request_id == history_fund_request.id)
            .order_by(ParcelReturnDetail.sent_date.desc(), ParcelReturnDetail.created_at.desc())
            .all()
        )
        for parcel_return in parcel_return_history:
            _attach_parcel_return_context(parcel_return)

    for fund_request in approved_fund_requests:
        _attach_fund_request_people(fund_request)
        _attach_fund_request_ticket(fund_request)
    if selected_fund_request:
        _attach_fund_request_people(selected_fund_request)
        _attach_fund_request_ticket(selected_fund_request)

    verification_fund_request = selected_fund_request
    if verification_fund_request is None and claim_detail:
        verification_fund_request = getattr(claim_detail, "fund_request", None)

    fund_request_status = getattr(verification_fund_request, "status", None)
    verification_creator_name = None
    if claim_detail and getattr(claim_detail, "user", None) and getattr(claim_detail.user, "name", None):
        verification_creator_name = claim_detail.user.name
    elif (
        verification_fund_request
        and getattr(verification_fund_request, "creator", None)
        and getattr(verification_fund_request.creator, "name", None)
    ):
        verification_creator_name = verification_fund_request.creator.name

    verification_requester_name = None
    if (
        verification_fund_request
        and getattr(verification_fund_request, "requester_user", None)
        and getattr(verification_fund_request.requester_user, "name", None)
    ):
        verification_requester_name = verification_fund_request.requester_user.name

    verification_ticket_number = (
        getattr(verification_fund_request, "ticket_number", None) or "-"
    )
    verification_request_date = (
        getattr(verification_fund_request, "request_date", None)
        or (claim_detail.created_at.date() if claim_detail and claim_detail.created_at else None)
    )
    verification_purpose = getattr(verification_fund_request, "purpose", None) or "-"
    verification_created_at = (
        claim_detail.created_at
        if claim_detail and claim_detail.created_at
        else (
            getattr(verification_fund_request, "created_at", None)
            if verification_fund_request
            else None
        )
    )
    verification_amount = (
        getattr(claim_detail, "total_amount", None)
        if claim_detail and getattr(claim_detail, "total_amount", None)
        else (
            getattr(selected_fund_request, "amount", None)
            if selected_fund_request and getattr(selected_fund_request, "amount", None)
            else (
                getattr(verification_fund_request, "amount", None)
                if verification_fund_request and getattr(verification_fund_request, "amount", None)
                else 0
            )
        )
    )
    verification_status = (
        getattr(claim_detail, "status", None)
        if claim_detail and getattr(claim_detail, "status", None)
        else (fund_request_status or "-")
    )

    return render_template(
        "submit_petty_cash_claim.html",
        setting=setting,
        claim_detail=claim_detail,
        approved_fund_requests=approved_fund_requests,
        selected_fund_request=selected_fund_request,
        can_submit_claim=can_submit_claim,
        history_fund_request=history_fund_request,
        claim_history=claim_history,
        parcel_return_history=parcel_return_history,
        fund_request_total_info=fund_request_total_info,
        fund_request_status=fund_request_status,
        verification_fund_request=verification_fund_request,
        verification_creator_name=verification_creator_name,
        verification_requester_name=verification_requester_name,
        verification_ticket_number=verification_ticket_number,
        verification_request_date=verification_request_date,
        verification_purpose=verification_purpose,
        verification_created_at=verification_created_at,
        verification_amount=verification_amount,
        verification_status=verification_status,
        fund_request_status_steps=FUND_REQUEST_STATUS_STEPS,
    )


@bp.route("/staff/petty-cash/parcel-returns/<int:parcel_return_id>/edit", methods=["POST"], endpoint="staff_parcel_return_edit")
@module_system_required(PETTY_CASH_SYSTEM)
def staff_parcel_return_edit(parcel_return_id):
    parcel_return = db.session.query(ParcelReturnDetail).get(parcel_return_id)
    if not parcel_return:
        abort(404)

    staff = current_user
    if not staff.is_authenticated or _selected_system() != PETTY_CASH_SYSTEM:
        abort(403)

    fund_request = _get_fund_request_by_id(getattr(parcel_return, "fund_request_id", None))
    if not fund_request:
        return _validation_redirect_response(
            "ไม่พบคำขอที่เกี่ยวข้องกับรายการนี้",
            request.referrer or url_for("advance_payment.staff_fund_request_history"),
        )

    if not _is_current_secretary() and fund_request.requester_id != staff.id:
        abort(403)

    current_status = (parcel_return.status or "").strip()
    if current_status not in {"รอตรวจสอบ", "ปฏิเสธ"}:
        return _validation_redirect_response(
            "สามารถแก้ไขรายการส่งคืนพัสดุได้เฉพาะก่อนฝ่ายการเงินตรวจสอบ หรือหลังถูกปฏิเสธเท่านั้น",
            url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request.id),
        )

    amount = request.form.get("amount", "0").replace(",", "")
    items_description = request.form.get("items_description", "").strip()
    sent_date_str = request.form.get("sent_date")

    if not items_description or not sent_date_str:
        return _validation_redirect_response(
            "กรุณากรอกรายละเอียดรายการและวันที่ส่งให้ครบถ้วน",
            url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request.id),
        )

    try:
        parsed_amount = float(amount or 0)
    except (TypeError, ValueError):
        return _validation_redirect_response(
            "กรุณาระบุจำนวนเงินให้ถูกต้อง",
            url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request.id),
        )

    ticket_id = getattr(fund_request, "borrowing_ticket_id", None)
    if ticket_id:
        ticket_totals = _calculate_ticket_return_totals_with_parcel(ticket_id, exclude_parcel_return_id=parcel_return.id)
        projected_ticket_total = ticket_totals["cumulative_total"] + parsed_amount
        if _is_over_limit(projected_ticket_total, ticket_totals["budget"]):
            return _redirect_with_limit_popup(
                url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request.id),
                (
                    "ยอดรวมเอกสารส่งใช้เงินยืมและส่งคืนพัสดุจะเป็น "
                    f"{_format_currency_amount(projected_ticket_total)} บาท "
                    f"ซึ่งเกินวงเงิน {_format_currency_amount(ticket_totals['budget'])} บาท"
                ),
            )

    fund_totals = _calculate_fund_request_totals(fund_request.id, exclude_parcel_return_id=parcel_return.id)
    projected_fund_total = fund_totals["cumulative_total"] + parsed_amount
    if _is_over_limit(projected_fund_total, fund_totals["request_amount"]):
        return _redirect_with_limit_popup(
            url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request.id),
            (
                "ยอดรวมใบเบิกเงินสดย่อยและส่งคืนพัสดุจะเป็น "
                f"{_format_currency_amount(projected_fund_total)} บาท "
                f"ซึ่งเกินยอดขอเบิก {_format_currency_amount(fund_totals['request_amount'])} บาท"
            ),
        )

    parcel_return.amount_spent = parsed_amount
    parcel_return.items_description = items_description
    parcel_return.sent_date = datetime.strptime(sent_date_str, "%Y-%m-%d").date()
    parcel_return.status = "รอตรวจสอบ"
    db.session.commit()
    _send_notification_email(parcel_return, object_type="parcel_return")

    flash("แก้ไขรายการส่งคืนพัสดุเรียบร้อยแล้ว", "success")
    return submit_petty_cash_claim(
        _render_after_post=True,
        _forced_fund_request_id=fund_request.id,
    )

@bp.route("/finance/petty-claims/<int:claim_id>/detail", methods=["GET"])
@module_system_required({PETTY_CASH_SYSTEM, FINANCE_SYSTEM})
def petty_cash_claim_detail(claim_id):
    claim_detail = db.session.query(PettyCashClaimDetail).get(claim_id)
    if not claim_detail:
        abort(404)
    if _selected_system() == FINANCE_SYSTEM and _claim_has_only_category_six(claim_detail):
        abort(404)
    _attach_petty_cash_claim_context(claim_detail)
    borrowing_ticket = None
    if getattr(claim_detail, "fund_request", None):
        borrowing_ticket = getattr(claim_detail.fund_request, "borrowing_ticket", None)
    if borrowing_ticket is None and getattr(claim_detail, "fund_request", None):
        borrowing_ticket = _get_borrowing_ticket_by_id(getattr(claim_detail.fund_request, "borrowing_ticket_id", None))

    if _selected_system() == PETTY_CASH_SYSTEM and not _is_current_secretary() and claim_detail.user_id != current_user.id:
        abort(403)
        
    return render_template(
        "petty_cash_claim_detail.html", # หรือชื่อไฟล์ HTML template ที่คุณใช้อยู่
        claim_detail=claim_detail,
        borrowing_ticket=borrowing_ticket,
        pdf_reference_options=_pdf_reference_options(),
        pdf_fiscal_year_default=convert_to_fiscal_year(datetime.now().date()),
    )

# 1. เปลี่ยนสถานะเป็น "กำลังตรวจสอบ"
@bp.route("/finance/petty-claims/<int:claim_id>/checking", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def mark_petty_claim_checking(claim_id):
    claim = _get_finance_visible_claim(claim_id)
    
    claim.status = "กำลังตรวจสอบ"
    db.session.commit()
    _send_notification_email(claim, object_type="petty_claim")
    flash("เปลี่ยนสถานะเป็น 'กำลังตรวจสอบ' เรียบร้อยแล้ว", "success")
    return petty_cash_claim_detail(claim.id)

# 2. ยืนยันการตรวจสอบ (ผ่านการตรวจสอบ)
@bp.route("/finance/petty-claims/<int:claim_id>/proofed", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def mark_petty_claim_proofed(claim_id):
    claim = _get_finance_visible_claim(claim_id)

    claim.status = "ผ่านการตรวจสอบ"
    db.session.commit()
    flash("ทำเครื่องหมายรายการเงินสดย่อยเป็น 'ผ่านการตรวจสอบ' เรียบร้อยแล้ว", "success")
    return petty_cash_claim_detail(claim.id)


# 3. โอนเงินสดย่อยสำเร็จ (โอนเงินสดย่อยสำเร็จ / transferred + บันทึกวันที่)
@bp.route("/finance/petty-claims/<int:claim_id>/transfer", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def mark_petty_claim_transferred(claim_id):
    claim = _get_finance_visible_claim(claim_id)
        
    transferred_date_str = request.form.get("transferred_at")
    if not transferred_date_str:
        return _validation_error_response("กรุณาระบุวันที่หน่วยงานได้รับเงิน/วันที่โอนเงิน")

    claim.status = "โอนเงินสดย่อยสำเร็จ"
    claim.transferred_at = datetime.strptime(transferred_date_str, "%Y-%m-%d").date()
    fund_req = db.session.query(FundRequest).get(claim.fund_request_id)
    if fund_req:
        fund_req.status = "เบิกเงินสำเร็จ"
        _recalculate_fund_request_submission_status(fund_req.id)
    
    db.session.commit()
    _send_notification_email(claim, object_type="petty_claim")
    flash("เปลี่ยนสถานะเป็น 'โอนเงินสดย่อยสำเร็จ' และบันทึกวันที่เรียบร้อยแล้ว", "success")
    return petty_cash_claim_detail(claim.id)


# 4. เปลี่ยนสถานะเป็น ได้รับเงินแล้ว/ล้างลูกหนี้เสร็จสมบูรณ์
@bp.route("/finance/petty-claims/<int:claim_id>/received", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def mark_petty_claim_received(claim_id):
    claim = _get_finance_visible_claim(claim_id)
        
    claim.status = "เสร็จสิ้นกระบวนการ"
    db.session.commit()
    _send_notification_email(claim, object_type="petty_claim")
    flash("เปลี่ยนสถานะเป็น 'ได้รับเงินแล้ว' สิ้นสุดกระบวนการเรียบร้อย", "success")
    return petty_cash_claim_detail(claim.id)


# 5. ปฏิเสธรายการเบิกเงินสดย่อย
@bp.route("/finance/petty-claims/<int:claim_id>/reject", methods=["POST"])
@module_role_required(finance_permission, FINANCE_SYSTEM, FINANCE_SYSTEM)
def reject_petty_claim(claim_id):
    claim = _get_finance_visible_claim(claim_id)

    rejection_comment = request.form.get("rejection_comment", "").strip()
    if rejection_comment:
        existing = claim.rejection_comment or ""
        count = existing.count("ครั้งที่") + 1
        staff = current_user
        user_name = staff.name if staff else "ไม่ระบุชื่อ"
        formatted_new_comment = (
            f"ครั้งที่ {count}: {rejection_comment} "
            f"ผู้ปฏิเสธ: {user_name} เมื่อ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        if existing:
            claim.rejection_comment = f"{existing}\n{formatted_new_comment}"
        else:
            claim.rejection_comment = formatted_new_comment

    claim.status = "ปฏิเสธ"
    db.session.commit()
    _send_notification_email(claim, object_type="petty_claim")
    flash("ปฏิเสธรายการเบิกเงินสดย่อยเรียบร้อยแล้ว", "info")
    return petty_cash_claim_detail(claim.id)


@bp.route("/finance/petty-claims/<int:claim_id>/confirm-edit", methods=["POST"])
@flask_login_required
def confirm_petty_claim_edit(claim_id):
    if _selected_system() == FINANCE_SYSTEM:
        abort(403)
    claim = db.session.query(PettyCashClaimDetail).get(claim_id)
    if not claim:
        abort(404)
    if _selected_system() == PETTY_CASH_SYSTEM and not _is_current_secretary() and claim.user_id != _current_user_id():
        abort(403)
    if (claim.status or "").strip().lower() != "รอยืนยันการแก้ไข":
        return _validation_error_response("รายการนี้ไม่มีการแก้ไขที่รอการยืนยัน")

    claim.status = "รอตรวจสอบ"
    db.session.commit()
    if claim.fund_request_id:
        _recalculate_fund_request_submission_status(claim.fund_request_id)
    _send_notification_email(claim, object_type="petty_claim")
    flash("ยืนยันการแก้ไขเรียบร้อยแล้ว และส่งรายการกลับไปรอตรวจสอบ", "success")
    return petty_cash_claim_detail(claim.id)

@bp.route("/staff/petty-cash-ledger", methods=["GET"])
@module_role_required(secretary_permission, SECRETARY_ROLE, PETTY_CASH_SYSTEM)
def petty_cash_ledger():
    user_id = _current_user_id()
    staff = current_user
    selected_month = (request.args.get("month") or "").strip()
    today = datetime.now().date()
    default_month = today.replace(day=1)

    try:
        selected_month_start = datetime.strptime(f"{selected_month}-01", "%Y-%m-%d").date()
    except ValueError:
        selected_month_start = default_month
        selected_month = default_month.strftime("%Y-%m")

    selected_month = selected_month_start.strftime("%Y-%m")
    fiscal_year = selected_month_start.year + (selected_month_start.month >= 10)
    current_setting = _resolve_petty_cash_setting(staff, fiscal_year=fiscal_year)

    if selected_month_start.year == 9999 and selected_month_start.month == 12:
        next_month_start = selected_month_start
    else:
        next_month_start = (
            date(selected_month_start.year + 1, 1, 1)
            if selected_month_start.month == 12
            else date(selected_month_start.year, selected_month_start.month + 1, 1)
        )
    
    # 1. ดึงงบประมาณตั้งต้นของหน่วยงาน
    initial_budget = 0.0
    if current_setting:
        initial_budget = float(current_setting.budget or 0)
    department_org = getattr(current_setting, "org", None) if current_setting else None
    department_name = getattr(department_org, "name", None) or (current_setting.department_name if current_setting else None)
    account_number = (current_setting.account_number or "").strip() if current_setting else ""

    ledger_raw_items = []

    def _append_ledger_row(
        *,
        receipt_date,
        created_at,
        description,
        doc_number=" ",
        bank_income=0.0,
        bank_expense=0.0,
        cat_7=0.0,
        cat_8=0.0,
        cat_9=0.0,
        cat_10=0.0,
        cat_11=0.0,
        custom_category=" ",
        cat_12=0.0,
        submitted_date=None,
        is_fund_request=False,
        sort_order=0,
    ):
        ledger_raw_items.append({
            "receipt_date": receipt_date,
            "created_at": created_at,
            "description": description,
            "doc_number": doc_number,
            "bank_income": bank_income,
            "bank_expense": bank_expense,
            "cat_7": cat_7,
            "cat_8": cat_8,
            "cat_9": cat_9,
            "cat_10": cat_10,
            "cat_11": cat_11,
            "custom_category": custom_category,
            "cat_12": cat_12,
            "submitted_date": submitted_date,
            "is_fund_request": is_fund_request,
            "sort_order": sort_order,
        })

    # 2. ดึงข้อมูล Fund Request (การเบิก/ยืมเงิน) -> แยกยอดเงินตามหมวดหมู่
    approved_fund_requests = []
    if department_name or account_number:
        fund_request_scope = []
        if current_setting and getattr(current_setting, "org_id", None):
            fund_request_scope.append(FundRequest.org_id == current_setting.org_id)
        elif department_name:
            fund_request_org = _resolve_org_by_department_name(department_name)
            if fund_request_org and getattr(fund_request_org, "id", None):
                fund_request_scope.append(FundRequest.org_id == fund_request_org.id)
            else:
                fund_request_scope.append(False)
        if account_number:
            # Type 32 is tied to the petty-cash account through its borrowing ticket.
            fund_request_scope.append(
                and_(
                    FundRequest.form_type == FUND_REQUEST_FORM_BORROWING_TICKET,
                    FundRequest.borrowing_ticket_id.in_(
                        db.session.query(BorrowingTicket.id).filter(BorrowingTicket.account_number == account_number)
                    ),
                )
            )
        approved_fund_requests = (
            db.session.query(FundRequest)
            .filter(
                or_(*fund_request_scope),
                ~FundRequest.status.in_(["กำลังดำเนินการ", "ปฏิเสธ", "ยกเลิก"]),
            )
            .all()
        )

    for fr in approved_fund_requests:
        amt = float(fr.amount or 0)
        if str(fr.form_type) == FUND_REQUEST_FORM_BORROWING_TICKET and amt <= 0:
            amt = float(getattr(fr.borrowing_ticket, "required_budget", 0) or 0)
        ticket_label = f"({fr.ticket_number or '-'})"

        if str(fr.form_type) == FUND_REQUEST_FORM_INTEREST:
            fund_in_date = _coerce_date(fr.receive_interest)
            withdrawal_date = _coerce_date(fr.withdraw_intrest)
            created_at = fr.created_at or datetime.now()
            submitted_date = created_at.date()

            if fund_in_date:
                _append_ledger_row(
                    # ดอกเบี้ยเข้าบัญชีให้แสดงตามวันที่เงินเข้าจริง
                    receipt_date=fund_in_date,
                    created_at=created_at,
                    description=f"ดอกเบี้ยจากธนาคาร",
                    bank_income=amt,
                    cat_11=amt,
                    custom_category="ได้รับดอกเบี้ยจากธนาคาร",
                    submitted_date=submitted_date,
                    is_fund_request=True,
                    sort_order=0,
                )

            if withdrawal_date:
                _append_ledger_row(
                    # เบิกดอกเบี้ยให้แสดงตามวันที่เบิกจริง
                    receipt_date=withdrawal_date,
                    created_at=created_at,
                    description=f"เบิกดอกเบี้ย {ticket_label}",
                    bank_expense=amt,
                    cat_11=amt,
                    custom_category=f"เบิกดอกเบี้ยตามงวดเดือน {_format_interest_period_label(fr.period_year)} ",
                    submitted_date=submitted_date,
                    is_fund_request=True,
                    sort_order=1,
                )
            continue
        
        # คำนวณจำแนกยอดเงินตามหมวดหมู่ที่เบิกไป (1-6)
        cat_7 = sum(float(item.amount or 0) for item in fr.items if str(item.category_type) == "1")
        cat_8 = sum(float(item.amount or 0) for item in fr.items if str(item.category_type) == "2")
        cat_9 = sum(float(item.amount or 0) for item in fr.items if str(item.category_type) == "3")
        cat_10 = sum(float(item.amount or 0) for item in fr.items if str(item.category_type) == "4")
        cat_11 = sum(float(item.amount or 0) for item in fr.items if str(item.category_type) == "5")
        cat_12 = sum(float(item.amount or 0) for item in fr.items if str(item.category_type) == "6")
        custom_category = next((item.description for item in fr.items if str(item.category_type) == "5" and item.description), None)

        _append_ledger_row(
            receipt_date=fr.request_date,
            created_at=fr.created_at,
            description=f"{fr.purpose or fr.department_name} {ticket_label}",
            bank_expense=amt,  # ยอดรายจ่ายเบิกเงินสดย่อย
            cat_7=cat_7,
            cat_8=cat_8,
            cat_9=cat_9,
            cat_10=cat_10,
            cat_11=cat_11,
            custom_category=custom_category,
            cat_12=cat_12,
            submitted_date=fr.created_at.date(),
            is_fund_request=True,
            sort_order=0,
        )

    if account_number:
        approved_borrowing_tickets = (
            db.session.query(BorrowingTicket)
            .filter(
                BorrowingTicket.account_number == account_number,
                BorrowingTicket.approved_at.isnot(None),
            )
            .order_by(BorrowingTicket.approved_at.asc(), BorrowingTicket.created_at.asc())
            .all()
        )

        for ticket in approved_borrowing_tickets:
            approved_at = ticket.approved_at
            if not approved_at:
                continue

            borrow_amount = float(ticket.required_budget or 0)
            _append_ledger_row(
                receipt_date=approved_at.date(),
                created_at=ticket.created_at,
                description=f"เงินยืมตามสัญญา บ.ย. {ticket.number or '-'}",
                bank_income=borrow_amount,
                cat_11=borrow_amount,
                custom_category="สัญญายืมเงิน",
                submitted_date=approved_at.date(),
                is_fund_request=False,
                sort_order=0,
            )

    all_claims = []
    if current_setting and current_setting.id:
        all_claims = (
            db.session.query(PettyCashClaimDetail)
            .filter(PettyCashClaimDetail.petty_cash_setting_id == current_setting.id)
            .all()
        )
    elif current_user:
        all_claims = (
            db.session.query(PettyCashClaimDetail)
            .filter(PettyCashClaimDetail.user_id == current_user.id)
            .all()
        )
    # แยกรายการที่เป็นหมวด 6 (โอนคืนบัญชีหน่วย) ออกมาเป็น Row ใหม่
    for claim in all_claims:
        _attach_petty_cash_claim_context(claim)
        if (claim.status or "").strip() == "ปฏิเสธ":
            continue
        for item in claim.items:   
            if str(item.category_type) == "6":
                item_amt = float(item.amount or 0)
                _append_ledger_row(
                    receipt_date=item.receipt_date or claim.transferred_at or claim.created_at.date(),
                    created_at=claim.created_at,
                    description=f"{item.description} (" + (claim.fund_request.ticket_number if claim.fund_request else "-") + ")",
                    bank_income=item_amt,  # แสดงยอดเงินโอนคืนเป็นรายรับ
                    cat_12=item_amt,
                    submitted_date=claim.created_at.date(),
                    is_fund_request=False,
                    sort_order=0,
                )

    # 3. ดึงข้อมูล Claim ที่คณะคืน
    transferred_claims = []
    if current_setting and current_setting.id:
        transferred_claims = [
            claim
            for claim in db.session.query(PettyCashClaimDetail)
            .filter(PettyCashClaimDetail.petty_cash_setting_id == current_setting.id)
            .all()
            if (claim.status or "").strip() not in {
                "ฉบับร่าง",
                "รอตรวจสอบ",
                "กำลังดำเนินการ",
                "ปฏิเสธ",
                "กำลังตรวจสอบ",
                "ผ่านการตรวจสอบ",
            }
        ]
    elif current_user:
        transferred_claims = [
            claim
            for claim in db.session.query(PettyCashClaimDetail)
            .filter(PettyCashClaimDetail.user_id == current_user.id)
            .all()
            if (claim.status or "").strip() not in {
                "ฉบับร่าง",
                "รอตรวจสอบ",
                "กำลังดำเนินการ",
                "ปฏิเสธ",
                "กำลังตรวจสอบ",
                "ผ่านการตรวจสอบ",
            }
        ]

    for claim in transferred_claims:
        # Category 6 returns already have their own ledger rows above.
        if _claim_has_only_category_six(claim):
            continue
        _attach_petty_cash_claim_context(claim)

        # กำหนด doc_no ตามเลขที่อ้างอิงและวันที่อ้างอิงของ PettyCashClaimDetail
        if claim.reference_number:
            ref_date_str = thai_date(claim.reference_date) if claim.reference_date else "-"
            doc_no = f"{claim.reference_number} ลงวันที่ {ref_date_str}"
        else:
            doc_no = "-"

        # ยอดรับเงินคืนเข้าบัญชีธนาคาร (คำนวณจากหมวด 1-5)
        claim_total = float(
            claim.total_amount or sum(float(i.amount or 0) for i in claim.items if str(i.category_type) != "6"))

        # คำนวณยอดแยกตามหมวดหมู่เฉพาะของ Claim (หมวด 1-5)
        cat_7 = sum(float(i.amount or 0) for i in claim.items if str(i.category_type) == "1")
        cat_8 = sum(float(i.amount or 0) for i in claim.items if str(i.category_type) == "2")
        cat_9 = sum(float(i.amount or 0) for i in claim.items if str(i.category_type) == "3")
        cat_10 = sum(float(i.amount or 0) for i in claim.items if str(i.category_type) == "4")
        cat_11 = sum(float(i.amount or 0) for i in claim.items if str(i.category_type) == "5")

        # เพิ่ม Row หลักสำหรับเงินที่ได้รับโอนคืนจากคณะ (หมวด 1-5)
        _append_ledger_row(
            receipt_date=claim.transferred_at or claim.created_at.date(),
            created_at=claim.created_at,
            description="คณะคืนเงินสดย่อย (" + (claim.fund_request.ticket_number if claim.fund_request else "-") + ")",
            doc_number=doc_no,
            bank_income=claim_total,
            cat_7=cat_7,
            cat_8=cat_8,
            cat_9=cat_9,
            cat_10=cat_10,
            cat_11=cat_11,
            cat_12=0.0,  # กำหนด cat_12 ของ Row หลักให้เป็น 0
            submitted_date=claim.created_at.date(),
            is_fund_request=False,
            sort_order=0,
        )

    # 4. เรียงลำดับรายการตามวันที่ทำรายการ (receipt_date) และเวลาที่สร้าง
    ledger_raw_items.sort(key=lambda x: (x["receipt_date"], x["created_at"], x.get("sort_order", 0)))

    opening_balance = initial_budget
    has_prior_transactions = False
    for item in ledger_raw_items:
        if item["receipt_date"] < selected_month_start:
            has_prior_transactions = True
            opening_balance += item["bank_income"] - item["bank_expense"]

    opening_row_description = "งบประมาณตั้งต้น" if selected_month_start.month == 10 else "ยกยอดมา"
    opening_row_income = initial_budget if not has_prior_transactions else opening_balance

    month_ledger_items = [
        item
        for item in ledger_raw_items
        if selected_month_start <= item["receipt_date"] < next_month_start
    ]

    month_ledger_items.sort(key=lambda x: (x["receipt_date"], x["created_at"], x.get("sort_order", 0)))

    ledger_items = []
    running_balance = opening_row_income

    ledger_items.append(
        {
            "receipt_date": selected_month_start,
            "created_at": None,
            "description": opening_row_description,
            "doc_number": " ",
            "bank_income": opening_row_income,
            "bank_expense": 0.0,
            "cat_7": 0.0,
            "cat_8": 0.0,
            "cat_9": 0.0,
            "cat_10": 0.0,
            "cat_11": 0.0,
            "custom_category": " ",
            "cat_12": 0.0,
            "submitted_date": selected_month_start,
            "is_fund_request": False,
            "sort_order": -1,
            "running_balance": running_balance,
            "is_opening_row": True,
        }
    )

    for item in month_ledger_items:
        running_balance += item["bank_income"] - item["bank_expense"]
        item_copy = item.copy()
        item_copy["running_balance"] = running_balance
        item_copy["is_opening_row"] = False
        ledger_items.append(item_copy)

    if request.args.get("download") == "monthly-report":
        if not current_setting or not getattr(current_setting, "id", None):
            flash("ไม่พบการตั้งค่าเงินสดย่อยสำหรับหน่วยงาน", "warning")
            return redirect(url_for("advance_payment.petty_cash_ledger", month=selected_month))
        summary = summarize_petty_cash_month(selected_month_start, approved_fund_requests, all_claims)
        department_data = get_department_data_service(department_name) or {}
        pdf_bytes = generate_petty_cash_monthly_report_pdf(
            setting=current_setting,
            month_start=selected_month_start,
            remaining_budget=running_balance,
            summary=summary,
            telephone_number=department_data.get("telephone_number", ""),
        )
        # Use the same department/account scope as the ledger, including all
        # request statuses as requested for the monthly attachment bundle.
        monthly_requests = (
            db.session.query(FundRequest)
            .filter(
                or_(*fund_request_scope),
                FundRequest.request_date >= selected_month_start,
                FundRequest.request_date < next_month_start,
            )
            .order_by(FundRequest.request_date.asc(), FundRequest.id.asc())
            .all()
            if department_name or account_number else []
        )
        pdf_bytes = append_petty_cash_monthly_attachments(
            pdf_bytes, setting=current_setting, month_start=selected_month_start,
            ledger_items=ledger_items, fund_requests=monthly_requests,
        )
        response = current_app.response_class(pdf_bytes, mimetype="application/pdf")
        response.headers["Content-Disposition"] = (
            f'attachment; filename="Petty_Cash_Monthly_Report_{selected_month_start:%Y-%m}.pdf"'
        )
        response.headers["Cache-Control"] = "private, no-store"
        return response

    return render_template(
        "petty_cash_ledger.html",
        initial_budget=initial_budget,
        opening_balance=opening_balance,
        ledger_items=ledger_items,
        selected_month=selected_month,
        selected_month_start=selected_month_start,
        selected_month_end=next_month_start,
    )
