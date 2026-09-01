import os
from datetime import date, datetime, timedelta
from sqlalchemy import extract
from functools import wraps
import re
from types import SimpleNamespace
from .pdf_utils import generate_fnar02_pdf, generate_fund_request_pdf

from flask import (
    after_this_request,
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template as _render_template,
    request,
    session,
    send_file,
    url_for,
)
from flask_login import current_user
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from .borrowing_ticket_eligibility import calculate_borrowing_ticket_eligibility
from .forms import BorrowingTicketForm, FundRequestForm, BankAccountInfoForm
from .models import db, BankAccountInfo, BorrowingTicket, Document, ParcelReturnDetail, PettyCashClaimDetail, PettyCashClaimItem, PettyCashClaimProofFile, ReturnDetail, ReturnReceiptItem, ReturnProofFile, StaffAccount, ClosingDocument, PettyCashSetting, FundRequest, FundRequestItem, document_petty_claim_association, document_return_association
from .email_utils import generate_notification_email_content
from . import advance_payment as bp
from app.models import Org
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
    return _render_template(template_name, *args, **kwargs)

COORDINATOR_ROLE = "cash_management_coordinator"
SECRETARY_ROLE = "secretary"
ADVANCE_PAYMENT_SYSTEM = "advance_payment"
PETTY_CASH_SYSTEM = "petty_cash"
FINANCE_SYSTEM = "finance"
AVAILABLE_SYSTEMS = (FINANCE_SYSTEM, PETTY_CASH_SYSTEM, ADVANCE_PAYMENT_SYSTEM)
FUND_REQUEST_FORM_BORROWING_TICKET = "32"
FUND_REQUEST_NUMBERED_STATUSES = {"อนุมัติแล้ว", "เบิกเงินแล้ว", "ส่งเบิกแล้ว"}
STATUS_NORMALIZATION_MAP = {
    "waiting": "รอตรวจสอบ",
    "pending": "รอตรวจสอบ",
    "checking": "กำลังตรวจสอบ",
    "draft": "ฉบับร่าง",
    "proofed": "ผ่านการตรวจสอบ",
    "received": "ได้รับเอกสารแล้ว",
    "reject": "ปฏิเสธ",
    "rejected": "ปฏิเสธ",
    "ปฏิเสธ": "ปฏิเสธ",
    "รอตรวจสอบ": "รอตรวจสอบ",
    "กำลังส่งคำขอ": "รอตรวจสอบ",
    "กำลังตรวจสอบ": "กำลังตรวจสอบ",
    "ฉบับร่าง": "ฉบับร่าง",
    "ผ่านการตรวจสอบ": "ผ่านการตรวจสอบ",
    "ได้รับเอกสารแล้ว": "ได้รับเอกสารแล้ว",
    "ปฏิเสธ": "ปฏิเสธ",
}

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

def _is_coordinator_role(role):
    return role == COORDINATOR_ROLE


def _is_petty_cash_role(role):
    return role == SECRETARY_ROLE


def _dashboard_endpoint_for_role(role):
    if session.get("advance_payment_system") == PETTY_CASH_SYSTEM:
        return "advance_payment.staff_fund_request_history"
    if session.get("advance_payment_system") == FINANCE_SYSTEM:
        return "advance_payment.finance_dashboard"
    return "advance_payment.coordinator_dashboard"


def _dashboard_party_label(role):
    if _is_coordinator_role(role):
        return "ผู้ประสานงาน"
    if _is_petty_cash_role(role):
        return "ผู้ดูแลเงินสดย่อย"
    return "ผู้ใช้งาน"


def _normalize_status_label(status_value, default=None):
    normalized = (status_value or "").strip()
    if not normalized:
        return default
    return STATUS_NORMALIZATION_MAP.get(normalized.lower(), STATUS_NORMALIZATION_MAP.get(normalized, normalized))


def _bank_account_type_label(record_type):
    return BANK_ACCOUNT_TYPE_LABELS.get((record_type or "").strip(), "ไม่ระบุประเภท")


def _normalize_lookup_value(value):
    return re.sub(r"\s+", "", (value or "").strip()).lower()


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


def _resolve_org_by_department_name(dept_name):
    normalized = _normalize_lookup_value(dept_name)
    if not normalized:
        return None

    query = db.session.query(Org)
    raw_name = (dept_name or "").strip()
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


def _org_account_controller(org):
    if not org:
        return None

    secretary_staff = getattr(org, "secretary_staff", None) or []
    if secretary_staff:
        controller = secretary_staff[0]
        return {
            "name": getattr(controller, "name", "") or getattr(controller, "fullname", "") or getattr(controller, "email", ""),
            "position": getattr(controller, "position", "") or "เจ้าหน้าที่",
            "email": getattr(controller, "email", ""),
        }

    active_accounts = getattr(org, "active_staff_accounts", None) or []
    if active_accounts:
        controller = active_accounts[0]
        return {
            "name": getattr(controller, "name", "") or getattr(controller, "fullname", "") or getattr(controller, "email", ""),
            "position": getattr(controller, "position", "") or "เจ้าหน้าที่",
            "email": getattr(controller, "email", ""),
        }

    return None


def _serialize_org_department(org):
    if not org:
        return None

    staff_members = []
    for staff in getattr(org, "active_staff_accounts", None) or []:
        if not staff:
            continue
        staff_members.append(
            {
                "id": getattr(staff, "id", None),
                "name": getattr(staff, "name", None) or getattr(staff, "fullname", None) or getattr(staff, "email", ""),
                "position": getattr(staff, "position", "") or "บุคลากร",
                "email": getattr(staff, "email", ""),
                "department": getattr(org, "name", "") or "",
            }
        )

    controller = _org_account_controller(org)
    head_account = None
    head_identifier = (getattr(org, "head", None) or "").strip()
    if head_identifier:
        head_account = StaffAccount.query.filter_by(email=head_identifier).first()

    head_name = (
        getattr(head_account, "name", None)
        or getattr(head_account, "fullname", None)
        or head_identifier
    )
    head_position = getattr(head_account, "position", None) or "หัวหน้าหน่วยงาน"
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
            "position": "เจ้าหน้าที่",
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
    return [role for role in (COORDINATOR_ROLE, SECRETARY_ROLE) if role in role_names]


def _default_module_role(staff):
    roles = _available_module_roles(staff)
    if roles:
        return roles[0]
    return None


def _sync_advance_payment_session(staff, role=None, system=None):
    if not staff:
        return

    session["user_id"] = staff.id
    session["user_email"] = staff.email
    if system is not None:
        session["advance_payment_system"] = system
    session["user_role"] = role if role in {COORDINATOR_ROLE, SECRETARY_ROLE} else None


def _module_user_from_session():
    if current_user.is_authenticated:
        _sync_advance_payment_session(current_user, session.get("user_role"))
        return current_user

    user_id = session.get("user_id")
    if not user_id:
        return None

    legacy_user = db.session.query(StaffAccount).get(user_id)
    if not legacy_user:
        session.pop("user_id", None)
        session.pop("user_email", None)
        session.pop("user_role", None)
        return None

    return legacy_user


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


def _is_current_coordinator():
    return _selected_system() == ADVANCE_PAYMENT_SYSTEM and _is_coordinator_role(session.get("user_role"))


def _is_current_secretary():
    return _selected_system() == PETTY_CASH_SYSTEM and _is_petty_cash_role(session.get("user_role"))


def _get_user_by_id(user_id):
    if not user_id:
        return None
    return db.session.query(StaffAccount).get(user_id)


def _get_borrowing_ticket_by_id(ticket_id):
    if not ticket_id:
        return None
    return db.session.query(BorrowingTicket).get(ticket_id)


def _can_submit_return_detail(user_id, borrowing_ticket):
    if not user_id or not borrowing_ticket:
        return False

    return user_id in {borrowing_ticket.creator_id, borrowing_ticket.borrower_id}


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
        parcel_return.display_borrower_name = fund_request.requester_name or getattr(requester_user, "name", "") or "-"
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
    claim.closing_document = _get_closing_document(getattr(claim, "closing_document_id", None))

    if claim.setting:
        _attach_petty_cash_setting_people(claim.setting)
    if claim.fund_request:
        _attach_fund_request_people(claim.fund_request)
        _attach_fund_request_ticket(claim.fund_request)

    _prepare_document_display_list(claim.documents)
    return claim


def _get_bank_account_dropdown_options():
    bank_accounts = (
        db.session.query(BankAccountInfo)
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
    query = db.session.query(BankAccountInfo)

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


def _resolve_petty_cash_setting(user):
    if not user:
        return None

    setting = getattr(user, "petty_cash_setting", None)
    if setting:
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

    query = db.session.query(PettyCashSetting).filter(PettyCashSetting.valid == True)

    if user_id:
        setting = query.filter(PettyCashSetting.custodian_id == user_id).first()
        if setting:
            return setting

    for setting in query.all():
        custodian_name = _normalize_lookup_value(getattr(setting, "custodian_name", None))
        if custodian_name and custodian_name in user_name_candidates:
            return setting

    for org_name in org_names:
        setting = query.filter_by(department_name=org_name).first()
        if setting:
            return setting

    department_name = (getattr(user, "department", "") or "").strip()
    if department_name:
        setting = query.filter_by(department_name=department_name).first()
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
        budget=0,
        department_name=department_name or "ไม่ระบุหน่วยงาน",
        account_number="",
        custodian_name=getattr(user, "name", "") or "",
        staff=user,
    )


def _calculate_petty_cash_balance_summary(setting, *, user_id=None):
    initial_budget = float(getattr(setting, "budget", 0) or 0)
    department_name = (getattr(setting, "department_name", "") or "").strip()
    setting_id = getattr(setting, "id", None)

    approved_fund_requests = []
    if department_name:
        approved_fund_requests = (
            db.session.query(FundRequest)
            .filter(FundRequest.department_name == department_name)
            .all()
        )
        approved_fund_requests = [
            fund_request
            for fund_request in approved_fund_requests
            if (fund_request.status or "").strip() not in {"ปฏิเสธ", "กำลังดำเนินการ"}
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
        if (claim.status or "").strip() not in {"ฉบับร่าง", "รอตรวจสอบ", "กำลังตรวจสอบ"}
    ]

    total_claim_incomes = 0.0
    for claim in approved_claims:
        for item in claim.items:
            total_claim_incomes += float(item.amount or 0)

    running_balance = initial_budget - total_fund_expenses + total_claim_incomes

    return {
        "total_claims": len(approved_claims),
        "total_fund_requests": len(approved_fund_requests),
        "total_amount": running_balance,
        "total_spent": total_fund_expenses,
        "remaining_budget": running_balance,
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
    department_name = (getattr(fund_request, "department_name", "") or "").strip()
    if not department_name:
        return None

    base_date = _fund_request_number_base_date(fund_request, reference_date=reference_date)
    fiscal_year, year_start, year_end = _get_fiscal_year_date_range(base_date)
    buddhist_year = fiscal_year + 543

    issued_count = (
        db.session.query(func.count(FundRequest.id))
        .filter(
            FundRequest.request_date >= year_start,
            FundRequest.request_date <= year_end,
            func.trim(func.coalesce(FundRequest.ticket_number, "")) != "",
            FundRequest.status.in_(FUND_REQUEST_NUMBERED_STATUSES),
        )
        .scalar()
        or 0
    )

    ticket_number = f"{issued_count + 1}/{buddhist_year}"
    fund_request.ticket_number = ticket_number
    return ticket_number

@bp.before_request
def recheck_overdue_and_upcoming_statuses():
    user_id = session.get("user_id")
    if not user_id:
        return

    today = datetime.now().date()

    query = db.session.query(BorrowingTicket).filter(
        BorrowingTicket.status != "ปฏิเสธ",
        BorrowingTicket.status != "กำลังส่งคำขอ",
        BorrowingTicket.status != "เคลียร์ยอดแล้ว"
    )

    if _is_coordinator_role(session.get("user_role")):
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

def login_required(role=None):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            staff = _module_user_from_session()
            if not staff:
                return redirect(url_for("advance_payment.login"))

            user_role = session.get("user_role")
            available_roles = _available_module_roles(staff)
            if user_role not in available_roles and user_role is not None:
                user_role = None
                session["user_role"] = None

            if role in {"coordinator", COORDINATOR_ROLE}:
                if _selected_system() != ADVANCE_PAYMENT_SYSTEM or not _is_coordinator_role(user_role):
                    abort(403)
            elif role in {"advance_payment", ADVANCE_PAYMENT_SYSTEM}:
                if _selected_system() != ADVANCE_PAYMENT_SYSTEM:
                    abort(403)
            elif role in {"staff", SECRETARY_ROLE, "petty_cash", PETTY_CASH_SYSTEM}:
                if _selected_system() != PETTY_CASH_SYSTEM:
                    abort(403)
            elif role == FINANCE_SYSTEM or role == "finance":
                if _selected_system() != FINANCE_SYSTEM or user_role != FINANCE_SYSTEM:
                    abort(403)
            elif role is not None and user_role != role:
                abort(403)

            return view_func(*args, **kwargs)

        return wrapped

    return decorator


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


def _get_closing_document(closing_document_id):
    if not closing_document_id:
        return None

    try:
        closing_document_id = int(closing_document_id)
    except (TypeError, ValueError):
        return None

    return db.session.query(ClosingDocument).get(closing_document_id)


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
            extra_ctx["borrower_name"] = (
                fund_request.requester_name
                or (requester.name if requester else None)
                or "ผู้ขอเบิก"
            )

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
@login_required(role="finance")
def mark_return_checking(return_id):
    return_detail = db.session.query(ReturnDetail).get(return_id)
    if not return_detail:
        abort(404)

    return_detail.status = "กำลังตรวจสอบ"
    db.session.commit()

    _recalculate_borrowing_ticket_status(return_detail.ticket_id)
    _send_notification_email(return_detail, object_type="return")
    flash("เปลี่ยนสถานะเป็น 'กำลังตรวจสอบ' เรียบร้อยแล้ว")
    return redirect(url_for("advance_payment.view_return_proof_detail", return_id=return_id))

@bp.route("/finance/returns/<int:return_id>/received", methods=["POST"])
@login_required(role="finance")
def mark_return_received(return_id):
    return_detail = db.session.query(ReturnDetail).get(return_id)
    if not return_detail:
        abort(404)

    return_detail.status = "ล้างลูกหนี้เงินยืม"
    db.session.commit()

    _recalculate_borrowing_ticket_status(return_detail.ticket_id)


    flash("เปลี่ยนสถานะเป็น 'ได้รับเงินแล้ว' และสิ้นสุดกระบวนการเรียบร้อย")
    return redirect(url_for("advance_payment.view_return_proof_detail", return_id=return_id))

@bp.route("/finance/closing-documents/<int:closing_doc_id>/cancel", methods=["POST"])
@login_required(role="finance")
def cancel_closing_doc(closing_doc_id):
    """
    ยกเลิกฎีกา (เปลี่ยนสภาวะจากการล้างยอดเงินเป็นการเก็บยอดเงินไว้แล้วเช็คจากสถานะ):
    - เปลี่ยน status ของ ClosingDocument เป็น 'ถูกยกเลิก'
    - คงยอดรวม (total_amount) และรายการที่ผูกไว้ในฎีกาเดิมไว้สำหรับตรวจสอบประวัติ
    - ย้ายรายการส่งใช้ (ReturnDetail, ParcelReturnDetail, PettyCashClaimDetail) กลับมารอตั้งฎีกาใหม่
      และบันทึกหมายเลขฎีกาที่ถูกยกเลิกไว้ใน old_closing_document_name
    """
    closing_doc = db.session.query(ClosingDocument).get(closing_doc_id)
    if not closing_doc:
        abort(404)

    # เปลี่ยนสถานะฎีกาเป็น ถูกยกเลิก (โดยไม่ล้าง total_amount ให้เป็น 0)
    closing_doc.status = "ถูกยกเลิก"
    doc_number = closing_doc.document_number
    updated_tickets = set()

    def append_history(existing_history):
        history_items = [
            item.strip()
            for item in (existing_history or "").split(",")
            if item.strip()
        ]
        if doc_number not in history_items:
            history_items.append(doc_number)
        return ", ".join(history_items)

    # 1. จัดการรายการส่งใช้เงินยืม (ReturnDetail)
    returns_in_doc = db.session.query(ReturnDetail).filter(
        ReturnDetail.closing_document_id == closing_doc.id
    ).all()

    for ret in returns_in_doc:
        ret.old_closing_document_name = append_history(ret.old_closing_document_name)
        ret.closing_document_id = None
        ret.status = "ผ่านการตรวจสอบ"  # สถานะกลับมารอตั้งฎีกาใหม่
        updated_tickets.add(ret.ticket_id)

    # 2. จัดการรายการส่งคืนพัสดุ (ParcelReturnDetail)
    parcel_in_doc = db.session.query(ParcelReturnDetail).filter(
        ParcelReturnDetail.closing_document_id == closing_doc.id
    ).all()

    for pr in parcel_in_doc:
        pr.old_closing_document_name = append_history(pr.old_closing_document_name)
        pr.closing_document_id = None
        pr.status = "ได้รับเอกสารแล้ว"  # สถานะกลับมารอตั้งฎีกาใหม่
        updated_tickets.add(pr.ticket_id)

    # 3. จัดการรายการเงินสดย่อย (PettyCashClaimDetail)
    petty_in_doc = db.session.query(PettyCashClaimDetail).filter(
        PettyCashClaimDetail.closing_document_id == closing_doc.id
    ).all()

    for petty in petty_in_doc:
        petty.old_closing_document_name = append_history(petty.old_closing_document_name)
        petty.closing_document_id = None
        petty.status = "โอนเงินสดย่อยสำเร็จ"  # สถานะกลับมารอตั้งฎีกาใหม่

    # 4. คำนวณสถานะตั๋วเงินยืมใหม่สำหรับทุกสัญญาที่เกี่ยวข้อง
    for ticket_id in updated_tickets:
        _recalculate_borrowing_ticket_status(ticket_id)

    db.session.commit()
    flash(f"ยกเลิกฎีกาเลขที่ {doc_number} เรียบร้อยแล้ว (สถานะเปลี่ยนเป็น 'ถูกยกเลิก' และคงยอดเงินประวัติไว้)", "success")
    return redirect(url_for("advance_payment.closing_management", search_closing_number=doc_number))

@bp.route("/finance/closing-documents/<int:closing_doc_id>/bulk-receive", methods=["POST"])
@login_required(role="finance")
def bulk_receive_closing_doc(closing_doc_id):
    """ เปลี่ยนสถานะเอกสารทุกรายการในฎีกานี้เป็น ล้างลูกหนี้เงินยืม """
    closing_doc = db.session.query(ClosingDocument).get(closing_doc_id)
    if not closing_doc:
        abort(404)

    returns_in_doc = db.session.query(ReturnDetail).filter(
        ReturnDetail.closing_document_id == closing_doc.id,
        ReturnDetail.status != "ล้างลูกหนี้เงินยืม"
    ).all()

    parcel_in_doc = db.session.query(ParcelReturnDetail).filter(
        ParcelReturnDetail.closing_document_id == closing_doc.id,
        ParcelReturnDetail.status != "ได้รับเอกสารแล้ว"
    ).all()

    petty_in_doc = db.session.query(PettyCashClaimDetail).filter(
        PettyCashClaimDetail.closing_document_id == closing_doc.id,
        PettyCashClaimDetail.status != "เสร็จสิ้นกระบวนการ"
    ).all()

    if not returns_in_doc and not petty_in_doc and not parcel_in_doc:
        flash("ไม่มีรายการเอกสารส่งใช้เงินยืม พัสดุ หรือเงินสดย่อยที่ต้องล้างลูกหนี้ในฎีกานี้เพิ่มเติม", "info")
        return redirect(url_for("advance_payment.closing_management", search_closing_number=closing_doc.document_number))

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

    closing_doc.status = "ล้างลูกหนี้เงินยืม"

    db.session.commit()
    flash(f"เปลี่ยนสถานะรายการทั้งหมดรวมถึงเงินสดย่อยในฎีกา {closing_doc.document_number} เป็น 'ล้างลูกหนี้เงินยืม' เรียบร้อยแล้ว", "success")
    return redirect(url_for("advance_payment.closing_management", search_closing_number=closing_doc.document_number))

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


def _is_return_amount_limit_exempt(description):
    return "เงินเหลือส่งใช้เงินยืม" in (description or "")

def _recalculate_borrowing_ticket_status(ticket_id):
    borrowing_ticket = (
        db.session.query(BorrowingTicket).filter_by(id=ticket_id).first()
    )
    if borrowing_ticket is None:
        return None

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
    staff = _module_user_from_session()
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
            _sync_advance_payment_session(staff, elevated_role, requested_system)
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
    if not current_user.is_authenticated and not session.get("user_id"):
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
@login_required(role=ADVANCE_PAYMENT_SYSTEM)
def coordinator_dashboard():
    user_id = session.get("user_id")
    user_role = session.get("user_role")
    is_borrower_mode = not _is_current_coordinator()
    current_user = db.session.query(StaffAccount).filter_by(id=user_id).first()
    if not current_user:
        abort(404)

    # ผู้ยืมเห็นเฉพาะของตัวเอง ส่วนผู้ประสานงานยังเลือกแทนคนอื่นได้
    if is_borrower_mode:
        dept_users = [current_user]
    else:
        dept_users = (
            db.session.query(StaffAccount)
            .order_by(StaffAccount.email.asc())
            .all()
        )
    if not dept_users:
        dept_users = [current_user]

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

    for ticket in borrowing_ticket_history:
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
            exclude_return_id=draft_detail.id if draft_detail else None,
        )
        ticket.parcel_return_total = ticket_display_totals["parcel_total"]
        ticket.submitted_return_total = ticket_display_totals["cumulative_total"]
        ticket_remaining = totals["remaining_amount"]
        ticket.ticket_remaining = ticket_remaining

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
            flash(
                "คุณยังไม่สามารถสร้างสัญญาเงินยืมใหม่ได้ เนื่องจากมีรายการค้างที่ต้องดำเนินการก่อน",
                "warning",
            )
            return redirect(url_for(_dashboard_endpoint_for_role(user_role)))

        # ผู้ยืมสร้างได้เฉพาะของตัวเอง ส่วนผู้ประสานงานเลือกแทนได้
        selected_coordinator_email = (
            (current_user.email or "").strip().lower()
            if is_borrower_mode
            else request.form.get("borrower_email", "").strip().lower()
        )
        if not selected_coordinator_email:
            flash(f"กรุณาเลือก{_dashboard_party_label(user_role)}ก่อนสร้างสัญญาเงินยืม", "danger")
            return redirect(url_for(_dashboard_endpoint_for_role(user_role)))

        coordinator_user = (
            db.session.query(StaffAccount)
            .filter_by(email=selected_coordinator_email)
            .first()
        )

        if not coordinator_user:
            flash(f"ไม่พบข้อมูล{_dashboard_party_label(user_role)}ที่ระบุในระบบ", "danger")
            return redirect(url_for(_dashboard_endpoint_for_role(user_role)))

        allowed_coordinator_emails = {
            user.email.strip().lower()
            for user in dept_users
            if user.email
        }
        if coordinator_user.email.strip().lower() not in allowed_coordinator_emails:
            flash(f"ไม่พบ{_dashboard_party_label(user_role)}ที่ระบุในระบบ", "danger")
            return redirect(url_for(_dashboard_endpoint_for_role(user_role)))

        # ตรวจสอบสิทธิ์ความสามารถในการยืมเงินของผู้ยืมจริง (Borrower) ด้วย calculate_borrowing_ticket_eligibility
        coordinator_eligibility = eligibility_by_email.get(
            (coordinator_user.email or "").strip().lower()
        )

        if not coordinator_eligibility.is_eligible:
            # หากผู้ยืมไม่ผ่านเงื่อนไข ระบบจะแจ้งเตือนและไม่อนุญาตให้สร้างสัญญา
            flash(
                f"ไม่สามารถสร้างสัญญาแทนได้: {coordinator_user.name} ไม่ผ่านเงื่อนไขการยืมเงินทดรองจ่าย "
                f"(สถานะที่ยังค้างอยู่: {', '.join(coordinator_eligibility.blocking_statuses)})",
                "danger"
            )
            return redirect(url_for(_dashboard_endpoint_for_role(user_role)))

        if form.validate():
            # บันทึกผู้สร้างสัญญาและผู้ยืมจริงแยกกันด้วย creator_id / borrower_id
            selected_account_number = (form.account_number.data or "").strip()
            selected_bank_account = _get_bank_account_info(
                bank_account_info_id=request.form.get("bank_account_info_id"),
                account_number=selected_account_number,
            )
            if selected_bank_account:
                selected_account_number = selected_bank_account.account_number

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
            db.session.commit()

            flash(f"สร้างสัญญาเงินยืมทดรองจ่ายแทน {coordinator_user.name} เรียบร้อยแล้ว", "success")
            _send_notification_email(new_ticket)
            return redirect(url_for(_dashboard_endpoint_for_role(user_role), download_ticket_id=new_ticket.id))

    dashboard_template = "borrower_dashboard.html" if is_borrower_mode else "coordinator_dashboard.html"
    bank_account_options = _get_bank_account_dropdown_options()
    bank_account_values = [option["value"] for option in bank_account_options]

    return render_template(
        dashboard_template,
        dashboard_title=f"แดชบอร์ด{_dashboard_party_label(user_role)}",
        dashboard_description=(
            "มุมมองส่วนตัวสำหรับจัดการสัญญาเงินยืมและเอกสารส่งใช้ของคุณ"
            if is_borrower_mode
            else "ศูนย์กลางจัดการสัญญาเงินยืม การส่งหลักฐาน และรายการรออนุมัติของผู้ประสานงาน"
        ),
        dashboard_role="Borrower" if is_borrower_mode else "Coordinator",
        dashboard_party_label=_dashboard_party_label(user_role),
        dashboard_party_scope="เฉพาะตัวเอง" if is_borrower_mode else "บุคลากรทั้งองค์กร",
        dashboard_can_choose_proxy=not is_borrower_mode,
        borrowing_ticket_history=borrowing_ticket_history,
        return_details=return_details,
        borrowing_ticket_form=form,
        borrowing_ticket_form_locked=form_locked,
        bank_account_options=bank_account_options,
        bank_account_values=bank_account_values,
        shadow_sum_debt=shadow_sum_debt,
        summary_days_remaining=summary_days_remaining,
        summary_overdue_days=summary_overdue_days,
        dept_users=dept_users,
        current_user=current_user,
    )

@bp.route("/coordinator/ticket/<int:ticket_id>/pdf", endpoint="coordinator_ticket_pdf")
@bp.route("/borrower/ticket/<int:ticket_id>/pdf", endpoint="borrower_ticket_pdf")
@bp.route("/coordinator/ticket/<int:ticket_id>/pdf", endpoint="export_ticket_pdf")
@login_required()
def export_ticket_pdf(ticket_id):
    ticket = db.session.query(BorrowingTicket).get(ticket_id)
    if not ticket:
        abort(404)

    if _selected_system() == ADVANCE_PAYMENT_SYSTEM and (
        (not _is_current_coordinator() and ticket.borrower_id != session.get("user_id"))
        or (_is_current_coordinator() and ticket.creator_id != session.get("user_id"))
    ):
        abort(403)

    pdf_bytes = generate_fnar02_pdf(ticket)

    response = current_app.response_class(pdf_bytes, mimetype='application/pdf')
    response.headers['Content-Disposition'] = f'attachment; filename=FNAR02_Ticket_{ticket_id}.pdf'
    return response

@bp.route("/finance/dashboard")
@login_required(role="finance")
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

    proofed_return_count = db.session.query(ReturnDetail).filter(ReturnDetail.status == "ผ่านการตรวจสอบ").count()
    proofed_parcel_count = db.session.query(ParcelReturnDetail).filter(ParcelReturnDetail.status == "ได้รับเอกสารแล้ว").count()
    proofed_claim_count = db.session.query(PettyCashClaimDetail).filter(PettyCashClaimDetail.status == "ผ่านการตรวจสอบ").count()
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

    for ticket in borrowing_tickets:
        ticket.status = _normalize_status_label(ticket.status, default="กำลังส่งคำขอ")

    for claim in petty_cash_claims:
        _attach_petty_cash_claim_context(claim)
        fund_request = claim.fund_request
        setting = claim.setting

        claim.requester_name = (
            fund_request.requester_name
            if fund_request and fund_request.requester_name
            else (claim.user.name if claim.user else "-")
        )
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
        normalized_status = _normalize_status_label(raw_status, default="กำลังส่งคำขอ")
        ticket.status = normalized_status
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
    active_settings = db.session.query(PettyCashSetting).filter(PettyCashSetting.valid == True).all()
    for setting in active_settings:
        _attach_petty_cash_setting_people(setting)

    # ==========================================
    # 4. ดึง FundRequest (ฟอร์ม 31) มาตรวจสอบ
    # ==========================================
    approved_interest_requests = db.session.query(FundRequest).filter(
        FundRequest.form_type == "31",
    ).all()

    matched_requests = []
    for fr in approved_interest_requests:
        if _normalize_interest_period_value(fr.period_year) == current_interest_period_key:
            matched_requests.append(fr)

    submitted_dept_names = {fr.department_name for fr in matched_requests if fr.department_name}

    pending_interest_departments = []
    for setting in active_settings:
        is_submitted = setting.department_name in submitted_dept_names
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
        dashboard_title="แดชบอร์ดฝ่ายการเงิน",
        dashboard_role="Finance",
        dashboard_description="เจ้าหน้าที่ฝ่ายการเงินสามารถตรวจสอบการอนุมัติและบันทึกทางการเงินได้จากส่วนนี้",
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
@login_required(role="finance")
def cash_mng_document_download(file_id):
    return _download_cash_mng_document(file_id)


@bp.route("/finance/bank-accounts", methods=["GET", "POST"])
@login_required(role="finance")
def finance_bank_account_registry():
    show_editor = request.method == "POST"
    form = BankAccountInfoForm()
    form.record_type.choices = list(BANK_ACCOUNT_TYPE_LABELS.items())

    def _parse_bank_account_created_at(raw_value):
        value = (raw_value or "").strip()
        if not value:
            return None
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return None


    if request.method == "POST":
        if request.form.get("edit_mode") != "1":
            flash("กรุณากดแก้ไขข้อมูลบัญชีธนาคารก่อน", "warning")
            return redirect(url_for("advance_payment.finance_bank_account_registry"))

        row_ids = request.form.getlist("record_id[]")
        row_types = request.form.getlist("record_type[]")
        row_thai_names = request.form.getlist("thai_name[]")
        row_created_ats = request.form.getlist("created_at[]")
        row_account_numbers = request.form.getlist("account_number[]")

        errors = []
        processed = 0

        for index, (raw_id, raw_type, raw_thai, raw_created_at, raw_account) in enumerate(
            zip(row_ids, row_types, row_thai_names, row_created_ats, row_account_numbers),
            start=1,
        ):
            record_type = (raw_type or "").strip()
            thai_name = (raw_thai or "").strip()
            created_at = _parse_bank_account_created_at(raw_created_at)
            account_number = (raw_account or "").strip()
            record_id = (raw_id or "").strip()

            if not any([record_type, thai_name, created_at, account_number, record_id]):
                continue

            if not all([record_type, thai_name, created_at, account_number]):
                errors.append(f"แถวที่ {index} กรุณากรอกข้อมูลให้ครบทุกช่อง")
                continue

            if record_id:
                record = db.session.query(BankAccountInfo).filter_by(id=int(record_id)).first()
                if record is None:
                    errors.append(f"แถวที่ {index} ไม่พบรายการเดิมสำหรับแก้ไข")
                    continue
                record.record_type = record_type
                record.thai_name = thai_name
                record.created_at = created_at
                record.account_number = account_number
            else:
                db.session.add(
                    BankAccountInfo(
                        record_type=record_type,
                        thai_name=thai_name,
                        created_at=created_at,
                        account_number=account_number,
                    )
                )
            processed += 1

        if errors:
            db.session.rollback()
            for error in errors:
                flash(error, "danger")
        elif processed > 0:
            db.session.commit()
            flash("บันทึกข้อมูลบัญชีธนาคารเรียบร้อยแล้ว", "success")
            return redirect(url_for("advance_payment.finance_bank_account_registry"))
        else:
            flash("ไม่มีข้อมูลที่ต้องบันทึก", "warning")

    records = (
        db.session.query(BankAccountInfo)
        .order_by(BankAccountInfo.record_type.asc(), BankAccountInfo.thai_name.asc())
        .all()
    )

    if request.method == "POST":
        edit_rows = []
        for raw_id, raw_type, raw_thai, raw_created_at, raw_account in zip(
            request.form.getlist("record_id[]"),
            request.form.getlist("record_type[]"),
            request.form.getlist("thai_name[]"),
            request.form.getlist("created_at[]"),
            request.form.getlist("account_number[]"),
        ):
            edit_rows.append(
                {
                    "id": raw_id,
                    "record_type": raw_type,
                    "thai_name": raw_thai,
                    "created_at": raw_created_at,
                    "account_number": raw_account,
                }
            )
    else:
        edit_rows = [
            {
                "id": record.id,
                "record_type": record.record_type,
                "thai_name": record.thai_name,
                "created_at": record.created_at,
                "account_number": record.account_number,
            }
            for record in records
        ]

    return render_template(
        "bank_account_registry.html",
        dashboard_title="จัดการข้อมูลบัญชีธนาคาร",
        dashboard_role="Finance",
        dashboard_description="บันทึกข้อมูลบัญชีธนาคารสำหรับเงินสดย่อยและเงินยืมของแต่ละหน่วยงาน",
        form=form,
        records=records,
        edit_rows=edit_rows,
        bank_account_type_labels=BANK_ACCOUNT_TYPE_LABELS,
        total_records=len(records),
        show_editor=show_editor,
    )

@bp.route("/finance/tickets", methods=["GET"])
@login_required(role="finance")
def tickets_view():
    filter_type = request.args.get("filter", "").strip()
    today_date = datetime.now().date()

    # Query ข้อมูลตั๋วเงินยืมทั้งหมด
    query = db.session.query(BorrowingTicket).order_by(BorrowingTicket.id.desc())

    # กรองข้อมูลตาม filter ที่ส่งมาจาก Dashboard
    if filter_type == "near_due":
        tickets = [
            t for t in query.all()
            if t.status not in ["เอกสารตั้งฎีกา", "เคลียร์ยอดแล้ว", "ปฏิเสธ", "กำลังส่งคำขอ"]
            and t.due_date
            and 0 <= (t.due_date - today_date).days <= 15
        ]
    elif filter_type == "overdue":
        tickets = [
            t for t in query.all()
            if t.status not in ["เอกสารตั้งฎีกา", "เคลียร์ยอดแล้ว", "ปฏิเสธ", "กำลังส่งคำขอ"]
            and t.due_date
            and today_date > t.due_date
        ]
    elif filter_type == "pending_debt":
        tickets = [
            t for t in query.all()
            if t.status not in ["เอกสารตั้งฎีกา", "เคลียร์ยอดแล้ว", "ปฏิเสธ", "กำลังส่งคำขอ"]
        ]
    else:
        tickets = query.all()

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
        dashboard_role="Finance"
    )

@bp.route("/tickets/<int:ticket_id>/verification")
def verification_view(ticket_id):
    user_role = session.get("user_role")
    if _selected_system() not in {ADVANCE_PAYMENT_SYSTEM, FINANCE_SYSTEM}:
        return redirect(url_for("advance_payment.login"))

    borrowing_ticket = (
        db.session.query(BorrowingTicket).filter_by(id=ticket_id).first()
    )
    if borrowing_ticket is None:
        abort(404)

    if _selected_system() == ADVANCE_PAYMENT_SYSTEM and not _is_current_coordinator() and borrowing_ticket.borrower_id != session.get("user_id"):
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


def _redirect_back_or(default_endpoint):
    return redirect(request.referrer or url_for(default_endpoint))


def _recalculate_fund_request_submission_status(fund_request_id):
    fund_request = db.session.query(FundRequest).get(fund_request_id)
    if not fund_request:
        return None

    fund_request_status = (fund_request.status or "").strip()
    if fund_request_status not in {"อนุมัติแล้ว", "ส่งเบิกแล้ว"}:
        return fund_request.status

    claim_total = (
        db.session.query(func.coalesce(func.sum(PettyCashClaimDetail.total_amount), 0))
        .filter(
            PettyCashClaimDetail.fund_request_id == fund_request_id,
            PettyCashClaimDetail.status != "ฉบับร่าง",
        )
        .scalar()
        or 0
    )

    parcel_total = (
        db.session.query(func.coalesce(func.sum(ParcelReturnDetail.amount_spent), 0))
        .filter(
            ParcelReturnDetail.fund_request_id == fund_request_id,
            ParcelReturnDetail.status != "ปฏิเสธ",
        )
        .scalar()
        or 0
    )

    combined_total = float(claim_total or 0) + float(parcel_total or 0)
    target_total = float(fund_request.amount or 0)

    if round(combined_total, 2) == round(target_total, 2) and target_total > 0:
        fund_request.status = "ส่งเบิกแล้ว"
    elif fund_request_status == "ส่งเบิกแล้ว":
        fund_request.status = "อนุมัติแล้ว"

    db.session.commit()
    return fund_request.status


@bp.route("/borrower/tickets/<int:ticket_id>/parcel-return", methods=["POST"])
@login_required()
def submit_parcel_return(ticket_id):
    amount = request.form.get("amount", "0").replace(",", "")
    items_description = request.form.get("items_description", "").strip()
    sent_date_str = request.form.get("sent_date")
    fund_request_id_raw = (request.form.get("fund_request_id") or request.args.get("fund_request_id") or "").strip()
    fund_request_id = int(fund_request_id_raw) if fund_request_id_raw.isdigit() else None

    if not items_description or not sent_date_str:
        flash("กรุณากรอกรายละเอียดรายการและวันที่ส่งให้ครบถ้วน")
        return redirect(url_for("advance_payment.borrower_dashboard"))

    try:
        parsed_amount = float(amount or 0)
    except (TypeError, ValueError):
        flash("กรุณาระบุจำนวนเงินให้ถูกต้อง", "danger")
        return redirect(url_for(_dashboard_endpoint_for_role(session.get("user_role"))))

    ticket_totals = _calculate_ticket_return_totals_with_parcel(ticket_id)
    projected_ticket_total = ticket_totals["cumulative_total"] + parsed_amount
    if _is_over_limit(projected_ticket_total, ticket_totals["budget"]):
        flash(
            (
                "ยอดรวมเอกสารส่งใช้เงินยืมและส่งคืนพัสดุจะเป็น "
                f"{_format_currency_amount(projected_ticket_total)} บาท "
                f"ซึ่งเกินวงเงิน {_format_currency_amount(ticket_totals['budget'])} บาท"
            ),
            "danger",
        )
        return redirect(url_for(_dashboard_endpoint_for_role(session.get("user_role"))))

    if fund_request_id:
        fund_totals = _calculate_fund_request_totals(fund_request_id)
        projected_fund_total = fund_totals["cumulative_total"] + parsed_amount
        if _is_over_limit(projected_fund_total, fund_totals["request_amount"]):
            flash(
                (
                    "ยอดรวมใบเบิกเงินสดย่อยและส่งคืนพัสดุจะเป็น "
                    f"{_format_currency_amount(projected_fund_total)} บาท "
                    f"ซึ่งเกินยอดขอเบิก {_format_currency_amount(fund_totals['request_amount'])} บาท"
                ),
                "danger",
            )
            return redirect(url_for(_dashboard_endpoint_for_role(session.get("user_role"))))

    sent_date = datetime.strptime(sent_date_str, "%Y-%m-%d").date()

    _create_parcel_return_record(
        ticket_id=ticket_id,
        fund_request_id=fund_request_id,
        amount=parsed_amount,
        items_description=items_description,
        sent_date=sent_date,
        status="รอตรวจสอบ",
    )

    flash("บันทึกข้อมูลการส่งคืนฝ่ายพัสดุเรียบร้อยแล้ว")
    return redirect(url_for(_dashboard_endpoint_for_role(session.get("user_role"))))


@bp.route("/staff/fund-request/<int:fund_request_id>/parcel-return", methods=["GET", "POST"], endpoint="submit_fund_request_parcel_return")
@login_required()
def submit_fund_request_parcel_return(fund_request_id):
    fund_request = db.session.query(FundRequest).filter_by(id=fund_request_id).first()
    if request.method == "GET":
        return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id))

    if fund_request is None:
        flash("ไม่พบคำขอที่เลือก")
        return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id))

    amount = request.form.get("amount", "0").replace(",", "")
    items_description = request.form.get("items_description", "").strip()
    sent_date_str = request.form.get("sent_date")

    if not items_description or not sent_date_str:
        flash("กรุณากรอกรายละเอียดรายการและวันที่ส่งให้ครบถ้วน")
        return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id))

    try:
        parsed_amount = float(amount or 0)
    except (TypeError, ValueError):
        flash("กรุณาระบุจำนวนเงินให้ถูกต้อง", "danger")
        return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id))

    ticket_id = getattr(fund_request, "borrowing_ticket_id", None)
    if ticket_id:
        ticket_totals = _calculate_ticket_return_totals_with_parcel(ticket_id)
        projected_ticket_total = ticket_totals["cumulative_total"] + parsed_amount
        if _is_over_limit(projected_ticket_total, ticket_totals["budget"]):
            flash(
                (
                    "ยอดรวมเอกสารส่งใช้เงินยืมและส่งคืนพัสดุจะเป็น "
                    f"{_format_currency_amount(projected_ticket_total)} บาท "
                    f"ซึ่งเกินวงเงิน {_format_currency_amount(ticket_totals['budget'])} บาท"
                ),
                "danger",
            )
            return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id))

    fund_totals = _calculate_fund_request_totals(fund_request_id)
    projected_fund_total = fund_totals["cumulative_total"] + parsed_amount
    if _is_over_limit(projected_fund_total, fund_totals["request_amount"]):
        flash(
            (
                "ยอดรวมใบเบิกเงินสดย่อยและส่งคืนพัสดุจะเป็น "
                f"{_format_currency_amount(projected_fund_total)} บาท "
                f"ซึ่งเกินยอดขอเบิก {_format_currency_amount(fund_totals['request_amount'])} บาท"
            ),
            "danger",
        )
        return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id))

    sent_date = datetime.strptime(sent_date_str, "%Y-%m-%d").date()

    _create_parcel_return_record(
        fund_request_id=fund_request.id,
        amount=parsed_amount,
        items_description=items_description,
        sent_date=sent_date,
        status="รอตรวจสอบ",
    )

    flash("บันทึกข้อมูลการส่งคืนฝ่ายพัสดุเรียบร้อยแล้ว")
    return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id))


@bp.route("/coordinator/parcel-returns/<int:parcel_return_id>/edit", methods=["POST"], endpoint="coordinator_parcel_return_edit")
@login_required(role="coordinator")
def update_parcel_return(parcel_return_id):
    parcel_return = db.session.query(ParcelReturnDetail).get(parcel_return_id)
    if not parcel_return:
        abort(404)

    borrowing_ticket = db.session.query(BorrowingTicket).get(parcel_return.ticket_id)
    if borrowing_ticket and borrowing_ticket.creator_id != session.get("user_id"):
        abort(403)

    current_status = (parcel_return.status or "").strip()
    if current_status not in {"รอตรวจสอบ", "ปฏิเสธ"}:
        flash("สามารถแก้ไขรายการส่งคืนพัสดุได้เฉพาะก่อนฝ่ายการเงินตรวจสอบ หรือหลังถูกปฏิเสธเท่านั้น", "warning")
        return _redirect_back_or(_parcel_return_history_fallback(parcel_return))

    amount = request.form.get("amount", "0").replace(",", "")
    items_description = request.form.get("items_description", "").strip()
    sent_date_str = request.form.get("sent_date")

    if not items_description or not sent_date_str:
        flash("กรุณากรอกรายละเอียดรายการและวันที่ส่งให้ครบถ้วน", "danger")
        return _redirect_back_or(_parcel_return_history_fallback(parcel_return))

    try:
        parsed_amount = float(amount or 0)
    except (TypeError, ValueError):
        flash("กรุณาระบุจำนวนเงินให้ถูกต้อง", "danger")
        return _redirect_back_or(_parcel_return_history_fallback(parcel_return))

    ticket_totals = _calculate_ticket_return_totals_with_parcel(parcel_return.ticket_id, exclude_parcel_return_id=parcel_return.id)
    projected_ticket_total = ticket_totals["cumulative_total"] + parsed_amount
    if _is_over_limit(projected_ticket_total, ticket_totals["budget"]):
        flash(
            (
                "ยอดรวมเอกสารส่งใช้เงินยืมและส่งคืนพัสดุจะเป็น "
                f"{_format_currency_amount(projected_ticket_total)} บาท "
                f"ซึ่งเกินวงเงิน {_format_currency_amount(ticket_totals['budget'])} บาท"
            ),
            "danger",
        )
        return _redirect_back_or(_parcel_return_history_fallback(parcel_return))

    if parcel_return.fund_request_id:
        fund_totals = _calculate_fund_request_totals(parcel_return.fund_request_id, exclude_parcel_return_id=parcel_return.id)
        projected_fund_total = fund_totals["cumulative_total"] + parsed_amount
        if _is_over_limit(projected_fund_total, fund_totals["request_amount"]):
            flash(
                (
                    "ยอดรวมใบเบิกเงินสดย่อยและส่งคืนพัสดุจะเป็น "
                    f"{_format_currency_amount(projected_fund_total)} บาท "
                    f"ซึ่งเกินยอดขอเบิก {_format_currency_amount(fund_totals['request_amount'])} บาท"
                ),
                "danger",
            )
            return _redirect_back_or(_parcel_return_history_fallback(parcel_return))

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
    return _redirect_back_or(_parcel_return_history_fallback(parcel_return))

@bp.route("/finance/parcel-returns/<int:parcel_return_id>/proofed", methods=["POST"])
@login_required(role="finance")
def mark_parcel_proofed(parcel_return_id):
    parcel_return = db.session.query(ParcelReturnDetail).get(parcel_return_id)
    if not parcel_return:
        abort(404)

    current_status = (parcel_return.status or "").strip()
    if current_status in {"ได้รับเอกสารแล้ว", "เอกสารตั้งฎีกา"}:
        flash("รายการนี้ผ่านขั้นตอนตรวจสอบแล้ว", "warning")
        return _redirect_back_or(_parcel_return_history_fallback(parcel_return))

    if current_status not in {"รอตรวจสอบ", "กำลังตรวจสอบ"}:
        flash("ต้องอยู่ในสถานะรอตรวจสอบก่อนจึงจะยืนยันการมีอยู่ของเอกสารพัสดุได้", "warning")
        return _redirect_back_or(_parcel_return_history_fallback(parcel_return))

    parcel_return.status = "พัสดุกำลังดำเนินการ"
    db.session.commit()
    _send_notification_email(parcel_return, object_type="parcel_return")
    if parcel_return.fund_request_id:
        _recalculate_fund_request_submission_status(parcel_return.fund_request_id)

    _recalculate_borrowing_ticket_status(parcel_return.ticket_id)
    flash("ยืนยันการมีอยู่ของเอกสารส่งคืนพัสดุเรียบร้อยแล้ว", "success")
    return _redirect_back_or(_parcel_return_history_fallback(parcel_return))


@bp.route("/finance/parcel-returns/<int:parcel_return_id>/received", methods=["POST"])
@login_required(role="finance")
def mark_parcel_received(parcel_return_id):
    parcel_return = db.session.query(ParcelReturnDetail).get(parcel_return_id)
    if not parcel_return:
        abort(404)

    current_status = (parcel_return.status or "").strip()
    if current_status not in {"พัสดุกำลังดำเนินการ", "กำลังตรวจสอบ"}:
        flash("ต้องยืนยันการมีอยู่ของเอกสารส่งคืนพัสดุก่อนรับเอกสารจริง", "danger")
        return _redirect_back_or(_parcel_return_history_fallback(parcel_return))

    parcel_return.status = "ได้รับเอกสารแล้ว"
    db.session.commit()
    _send_notification_email(parcel_return, object_type="parcel_return")
    if parcel_return.fund_request_id:
        _recalculate_fund_request_submission_status(parcel_return.fund_request_id)

    _recalculate_borrowing_ticket_status(parcel_return.ticket_id)

    flash("เปลี่ยนสถานะพัสดุเป็น 'ได้รับเอกสารแล้ว' เรียบร้อย")
    return _redirect_back_or(_parcel_return_history_fallback(parcel_return))


@bp.route("/finance/parcel-returns/<int:parcel_return_id>/reject", methods=["POST"])
@login_required(role="finance")
def reject_parcel_return(parcel_return_id):
    parcel_return = db.session.query(ParcelReturnDetail).get(parcel_return_id)
    if not parcel_return:
        abort(404)

    current_status = (parcel_return.status or "").strip()
    if current_status in {"ได้รับเอกสารแล้ว", "เอกสารตั้งฎีกา"}:
        flash("ไม่สามารถปฏิเสธรายการที่รับเอกสารแล้วหรือปิดรายการแล้วได้", "warning")
        return _redirect_back_or(_parcel_return_history_fallback(parcel_return))

    new_comment = request.form.get("rejection_comment", "").strip()

    if new_comment:
        existing_comment = parcel_return.rejection_comment or ""
        count = existing_comment.count("ครั้งที่") + 1
        current_user = db.session.query(StaffAccount).get(session.get("user_id"))
        user_name = current_user.name if current_user else "ไม่ระบุชื่อ"
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
    return _redirect_back_or(_parcel_return_history_fallback(parcel_return))

@bp.route("/api/documents/suggest", methods=["GET"])
@login_required()
def suggest_documents():
    q = request.args.get("q", "").strip()
    docs = _list_cash_mng_documents(search_query=q, limit=20)
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
@login_required()
def submit_return_details():
    ticket_id = request.form.get("ticket_id") or request.args.get("ticket_id")
    if not ticket_id:
        flash("กรุณาระบุเอกสารสัญญาเงินยืมที่ต้องการส่งหลักฐาน", "danger")
        return redirect(url_for(_dashboard_endpoint_for_role(session.get("user_role"))))

    borrowing_ticket = db.session.query(BorrowingTicket).filter_by(id=ticket_id).first()
    if borrowing_ticket is None:
        abort(404)

    current_user_id = session.get("user_id")
    if not _can_submit_return_detail(current_user_id, borrowing_ticket):
        abort(403)

    if borrowing_ticket.status in {"เคลียร์ยอดแล้ว", "เอกสารตั้งฎีกา", "ปฏิเสธ"}:
        flash("ไม่สามารถดำเนินการสำหรับสัญญาเงินยืมที่มีสถานะนี้ได้", "danger")
        return redirect(url_for(_dashboard_endpoint_for_role(session.get("user_role"))))

    action = request.form.get("action", "submit")
    is_draft = (action == "draft")

    receipt_dates = request.form.getlist("receipt_date[]")
    store_names = request.form.getlist("store_name[]")
    descriptions = request.form.getlist("description[]")
    amounts = request.form.getlist("amount[]")

    if not is_draft and not receipt_dates:
        flash("กรุณาเพิ่มรายละเอียดใบเสร็จอย่างน้อย 1 รายการ", "warning")
        return redirect(url_for(_dashboard_endpoint_for_role(session.get("user_role"))))

    parsed_rows = []
    total_amount_spent = 0.0
    old_receipt_count = 0

    for i in range(len(receipt_dates)):
        r_date_raw = receipt_dates[i]
        r_date = _coerce_date(r_date_raw) if r_date_raw else None
        if not is_draft and not r_date:
            flash("ทุกแถวของรายการใบเสร็จต้องระบุวันที่ที่ถูกต้อง", "danger")
            return redirect(url_for(_dashboard_endpoint_for_role(session.get("user_role"))))

        try:
            amt = float((amounts[i] or "0").replace(",", "")) if i < len(amounts) else 0.0
            if amt < 0:
                raise ValueError
        except (TypeError, ValueError):
            if not is_draft:
                flash("ทุกแถวของรายการใบเสร็จต้องระบุจำนวนเงินที่ถูกต้อง", "danger")
                return redirect(url_for(_dashboard_endpoint_for_role(session.get("user_role"))))
            amt = 0.0

        description = descriptions[i].strip() if i < len(descriptions) else ""
        if not is_draft and amt > 100000 and not _is_return_amount_limit_exempt(description):
            flash(f"รายการที่ {i + 1} มียอดเกิน 100,000 บาท กรุณาแก้ไขก่อนส่งเบิก", "danger")
            return redirect(url_for(_dashboard_endpoint_for_role(session.get("user_role"))))

        if not is_draft and _receipt_requires_additional_document(r_date):
            old_receipt_count += 1

        total_amount_spent += amt
        parsed_rows.append(
            {
                "receipt_date": r_date,
                "store_name": store_names[i].strip() if i < len(store_names) else "",
                "description": description,
                "amount": amt,
            }
        )

    if not is_draft:
        ticket_totals = _calculate_ticket_return_totals_with_parcel(ticket_id)
        projected_total = ticket_totals["cumulative_total"] + total_amount_spent
        if _is_over_limit(projected_total, ticket_totals["budget"]):
            flash(
                (
                    "ยอดรวมเอกสารส่งใช้เงินยืมและส่งคืนพัสดุจะเป็น "
                    f"{_format_currency_amount(projected_total)} บาท "
                    f"ซึ่งเกินวงเงิน {_format_currency_amount(ticket_totals['budget'])} บาท"
                ),
                "danger",
            )
            return redirect(url_for(_dashboard_endpoint_for_role(session.get("user_role"))))

    existing_draft = db.session.query(ReturnDetail).filter_by(ticket_id=ticket_id, status="ฉบับร่าง").first()

    if existing_draft:
        old_items = db.session.query(ReturnReceiptItem).filter_by(return_detail_id=existing_draft.id).all()
        for oi in old_items:
            db.session.query(ReturnProofFile).filter_by(return_receipt_item_id=oi.id).delete()
        db.session.query(ReturnReceiptItem).filter_by(return_detail_id=existing_draft.id).delete()
        return_detail = existing_draft
    else:
        return_detail = ReturnDetail(
            ticket_id=ticket_id,
            proof_reference="Itemized Details Stored",
            created_at=datetime.now(),
        )
        db.session.add(return_detail)
        db.session.flush()

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
            amount=row["amount"]
        )
        db.session.add(receipt_obj)

        uploaded_files = request.files.getlist(f"proof_files_{i}[]")
        if not uploaded_files and i < len(legacy_uploaded_files):
            uploaded_files = [legacy_uploaded_files[i]]

        for file_storage in uploaded_files:
            if not file_storage or not file_storage.filename:
                continue
            _, ext = os.path.splitext(file_storage.filename)
            clean_store_name = re.sub(r'[^\u0e00-\u0e7fa-zA-Z0-9\s_-]', '', receipt_obj.store_name or "receipt").strip().replace(" ", "_")
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            new_filename = f"{clean_store_name or 'receipt'}_{timestamp_str}{ext}"

            upload_folder = os.path.join(_upload_root(), str(ticket_id))
            os.makedirs(upload_folder, exist_ok=True)
            proof_path = f"uploads/{ticket_id}/{new_filename}"
            file_storage.save(os.path.join(upload_folder, new_filename))

            proof_file_record = ReturnProofFile(
                return_detail_id=return_detail.id,
                return_receipt_item_id=receipt_obj.id,
                proof_reference=proof_path,
                filename=new_filename,
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

    db.session.commit()

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

    return redirect(url_for(_dashboard_endpoint_for_role(session.get("user_role"))))

@bp.app_template_filter('filter_actionable_tickets')
def filter_actionable_tickets(tickets):
    actionable_statuses = {"อนุมัติจ่ายเงิน", "มียอดคงค้าง",}
    return [
        t
        for t in tickets
        if (t.status or "").strip().lower() in actionable_statuses or (t.status or "").strip() in actionable_statuses
    ]

@bp.route("/proof-file/<int:file_id>/edit-inline", methods=["POST"])
@login_required()
def edit_receipt_item_inline(file_id):
    source = (request.form.get("source") or "").strip().lower()
    proof_file = None
    receipt_item = None
    is_claim = False

    if source == "petty_claim":
        is_claim = True
        proof_file = db.session.query(PettyCashClaimProofFile).get(file_id)
        if not proof_file:
            receipt_item = db.session.query(PettyCashClaimItem).get(file_id)
            if receipt_item:
                proof_file = getattr(receipt_item, "proof_file", None) or (
                    receipt_item.proof_files[0] if getattr(receipt_item, "proof_files", None) else None
                )
    elif source in {"return", "return_detail"}:
        proof_file = db.session.query(ReturnProofFile).get(file_id)
        if not proof_file:
            receipt_item = db.session.query(ReturnReceiptItem).get(file_id)
            if receipt_item:
                proof_file = getattr(receipt_item, "proof_file", None) or (
                    receipt_item.proof_files[0] if getattr(receipt_item, "proof_files", None) else None
                )
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

        if claim_detail.status.lower() not in ["รอตรวจสอบ", "ปฏิเสธ", "ฉบับร่าง"]:
            flash("ไม่สามารถแก้ไขได้ เนื่องจากสถานะเอกสารถูกเปลี่ยนแปลงไปแล้ว")
            return redirect(url_for("advance_payment.petty_cash_claim_detail", claim_id=claim_detail.id))

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
            (not _is_current_coordinator() and borrowing_ticket.borrower_id != session.get("user_id"))
            or (_is_current_coordinator() and borrowing_ticket.creator_id != session.get("user_id"))
        ):
            abort(403)

        if return_detail.status.lower() not in ["รอตรวจสอบ", "ปฏิเสธ", "ฉบับร่าง"]:
            flash("ไม่สามารถแก้ไขได้ เนื่องจากสถานะเอกสารถูกเปลี่ยนแปลงไปแล้ว")
            return redirect(url_for("advance_payment.view_return_proof_detail", return_id=return_detail.id))

        if not receipt_item and proof_file:
            receipt_item = getattr(proof_file, "receipt_item", None)

    # ==========================================
    # 5. อัปเดตข้อมูลรายละเอียด และ ตรวจสอบอายุใบเสร็จ
    # ==========================================
    receipt_is_old = False  # ตัวแปรสถานะตรวจสอบอายุใบเสร็จเกิน 10 วัน

    if receipt_item:
        if hasattr(receipt_item, "store_name") and request.form.get("store_name"):
            receipt_item.store_name = request.form.get("store_name", "").strip()

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
            if not _is_return_amount_limit_exempt(receipt_item.description) and parsed_item_amount > 100000:
                flash("รายการนี้มียอดเกิน 100,000 บาท กรุณาแก้ไขก่อนส่งเบิก", "danger")
                redirect_target = (
                    url_for("advance_payment.petty_cash_claim_detail", claim_id=claim_detail.id)
                    if is_claim
                    else url_for("advance_payment.view_return_proof_detail", return_id=return_detail.id)
                )
                return redirect(redirect_target)
            receipt_item.amount = parsed_item_amount

    if is_claim:
        total_spent_for_claim = sum(float(i.amount or 0) for i in claim_detail.items)
        if claim_detail.fund_request_id:
            fund_totals = _calculate_fund_request_totals(claim_detail.fund_request_id, exclude_claim_id=claim_detail.id)
            projected_total = fund_totals["cumulative_total"] + total_spent_for_claim
            if _is_over_limit(projected_total, fund_totals["request_amount"]):
                flash(
                    (
                        "ยอดรวมใบเบิกเงินสดย่อยและส่งคืนพัสดุจะเป็น "
                        f"{_format_currency_amount(projected_total)} บาท "
                        f"ซึ่งเกินยอดขอเบิก {_format_currency_amount(fund_totals['request_amount'])} บาท"
                    ),
                    "danger",
                )
                return redirect(url_for("advance_payment.petty_cash_claim_detail", claim_id=claim_detail.id))
    else:
        total_spent_for_return = sum(float(i.amount or 0) for i in return_detail.receipt_items)
        ticket_totals = _calculate_ticket_return_totals_with_parcel(return_detail.ticket_id, exclude_return_id=return_detail.id)
        projected_total = ticket_totals["cumulative_total"] + total_spent_for_return
        if _is_over_limit(projected_total, ticket_totals["budget"]):
            flash(
                (
                    "ยอดรวมเอกสารส่งใช้เงินยืมและส่งคืนพัสดุจะเป็น "
                    f"{_format_currency_amount(projected_total)} บาท "
                    f"ซึ่งเกินวงเงิน {_format_currency_amount(ticket_totals['budget'])} บาท"
                ),
                "danger",
            )
            return redirect(url_for("advance_payment.view_return_proof_detail", return_id=return_detail.id))

    # 6. จัดการอัปโหลดไฟล์ใหม่ (ถ้ามีการแนบไฟล์)
    uploaded_file = request.files.get("proof_file")
    if uploaded_file and uploaded_file.filename != "":
        user_id = session.get("user_id")
        filename = secure_filename(uploaded_file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"inline_{timestamp}_{filename}"

        user_upload_dir = os.path.join(_upload_root(), str(user_id or "claim"))
        os.makedirs(user_upload_dir, exist_ok=True)
        uploaded_file.save(os.path.join(user_upload_dir, unique_filename))

        if proof_file:
            proof_file.proof_reference = f"uploads/{user_id or 'claim'}/{unique_filename}"
            if hasattr(proof_file, "original_filename"):
                proof_file.original_filename = uploaded_file.filename
            elif hasattr(proof_file, "filename"):
                proof_file.filename = uploaded_file.filename
            proof_file.created_at = datetime.now()

    # ==========================================
    # 7. บันทึกข้อมูลและแจ้งเตือน Warning หากใบเสร็จเกิน 10 วัน
    # ==========================================
    if is_claim:
        claim_detail.status = "รอตรวจสอบ"
        claim_detail.total_amount = total_spent_for_claim

        db.session.commit()

        # แจ้งเตือนเรื่องใบเสร็จเกิน 10 วัน (ถ้ามี)
        if receipt_is_old:
            flash("ใบเสร็จมีอายุเกิน 10 วัน กรุณาจัดทำเอกสารขออนุมัติเบิกจ่ายล่าช้าประกอบการยื่นเพิ่มเติม", "warning")

        flash("แก้ไขข้อมูลรายการเบิกเงินสดย่อยสำเร็จเรียบร้อยแล้ว", "success")
        return redirect(url_for("advance_payment.petty_cash_claim_detail", claim_id=claim_detail.id))
    else:
        return_detail.status = "รอตรวจสอบ"
        return_detail.amount_spent = total_spent_for_return
        _send_notification_email(return_detail, object_type="return")

        db.session.commit()

        if receipt_is_old:
            flash("ใบเสร็จมีอายุเกิน 10 วัน กรุณาเตรียมเอกสารเพิ่มเติมประกอบการยื่น", "warning")

        flash("แก้ไขข้อมูลรายการใบเสร็จและอัปเดตหลักฐานสำเร็จเรียบร้อยแล้ว", "success")
        return redirect(url_for("advance_payment.view_return_proof_detail", return_id=return_detail.id))

@bp.route("/coordinator/tickets/<int:ticket_id>/autosave-draft", methods=["POST"], endpoint="coordinator_autosave_draft")
@bp.route("/borrower/tickets/<int:ticket_id>/autosave-draft", methods=["POST"], endpoint="borrower_autosave_draft")
@login_required(role=ADVANCE_PAYMENT_SYSTEM)
def autosave_return_draft(ticket_id):
    ticket = db.session.query(BorrowingTicket).filter_by(id=ticket_id).first()
    if not ticket or ticket.status in {"เคลียร์ยอดแล้ว", "เอกสารตั้งฎีกา", "ปฏิเสธ"}:
        return jsonify({"success": False, "message": "ไม่สามารถบันทึกร่างได้"}), 400

    # ผู้ใช้ทั่วไปบันทึกฉบับร่างได้เฉพาะสัญญาที่ตนเป็นผู้ยืม
    if not _is_current_coordinator() and ticket.borrower_id != session.get("user_id"):
        abort(403)

    data = request.get_json() or {}
    items = data.get("items", [])
    announcements = data.get("announcements", [])  # <--- 1. รับค่าประกาศเพิ่มจาก JSON

    # ค้นหา ReturnDetail สถานะ Draft เดิม
    existing_draft = db.session.query(ReturnDetail).filter_by(ticket_id=ticket_id, status="ฉบับร่าง").first()

    if existing_draft:
        db.session.query(ReturnReceiptItem).filter_by(return_detail_id=existing_draft.id).delete()
        return_detail = existing_draft
    else:
        return_detail = ReturnDetail(ticket_id=ticket_id, proof_reference="Itemized Details Stored", status="ฉบับร่าง")
        db.session.add(return_detail)
        db.session.flush()

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
            amount=amt
        )
        db.session.add(receipt_obj)

    # <--- 2. เพิ่มส่วนจัดการบันทึกประกาศเข้า ReturnDetail --->
    _replace_return_detail_documents(return_detail, announcements)

    db.session.commit()

    saved_time = datetime.now().strftime("%H:%M:%S")
    return jsonify({"success": True, "saved_at": saved_time})

@bp.route("/finance/returns/<int:return_id>/proofed", methods=["POST"])
@login_required(role="finance")
def mark_return_proofed(return_id):
    return_detail = (
        db.session.query(ReturnDetail).filter_by(id=return_id).first()
    )
    if return_detail is None:
        abort(404)

    if return_detail.status == "เอกสารตั้งฎีกา":
        flash("ไม่สามารถย้อนกลับรายการหลักฐานเอกสารส่งใช้เงินยืมที่ปิดรายการไปแล้วได้")
        return redirect(
            url_for("advance_payment.view_return_proof_detail", return_id=return_detail.ticket_id)
        )

    if return_detail.status == "ผ่านการตรวจสอบ":
        flash("รายการหลักฐานเอกสารส่งใช้เงินยืมนี้ได้รับการตรวจสอบและยืนยันแล้ว")
        return redirect(
            url_for("advance_payment.view_return_proof_detail", return_id=return_detail.ticket_id)
        )

    return_detail.status = "ผ่านการตรวจสอบ"
    db.session.commit()

    _recalculate_borrowing_ticket_status(return_detail.ticket_id)
    _send_notification_email(return_detail, object_type="return")
    flash("ทำเครื่องหมายรายการเอกสารส่งใช้เงินยืมเป็น ผ่านการตรวจสอบ เรียบร้อยแล้ว")

    return redirect(
        url_for("advance_payment.verification_view", ticket_id=return_detail.ticket_id)
    )

@bp.route("/finance/returns/<int:return_id>/reject", methods=["POST"])
@login_required(role="finance")
def reject_return_detail(return_id):
    return_detail = (
        db.session.query(ReturnDetail).filter_by(id=return_id).first()
    )
    if return_detail is None:
        abort(404)

    if return_detail.status == "เอกสารตั้งฎีกา":
        flash("ไม่สามารถแก้ไขรายการหลักฐานเอกสารส่งใช้เงินยืมที่ปิดรายการไปแล้วได้")
        return redirect(
            url_for("advance_payment.verification_view", ticket_id=return_detail.ticket_id)
        )

    new_comment = request.form.get("rejection_comment", "").strip()

    if new_comment:
        existing_comment = return_detail.rejection_comment or ""
        count = existing_comment.count("ครั้งที่") + 1
        current_user = db.session.query(StaffAccount).get(session.get("user_id"))
        user_name = current_user.name if current_user else "ไม่ระบุชื่อ"
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

    return redirect(
        url_for("advance_payment.verification_view", ticket_id=return_detail.ticket_id)
    )

@bp.route("/finance/tickets/<int:ticket_id>/approve", methods=["POST"])
@login_required(role="finance")
def approve_borrowing_ticket(ticket_id):
    borrowing_ticket = (
        db.session.query(BorrowingTicket).filter_by(id=ticket_id).first()
    )
    if borrowing_ticket is None:
        abort(404)

    if borrowing_ticket.status != "กำลังส่งคำขอ":
        flash("เฉพาะสัญญาเงินยืมเงินที่ กำลังส่งคำขอ เท่านั้นที่สามารถอนุมัติได้")
        return redirect(url_for("advance_payment.finance_dashboard"))

    raw_number = (request.form.get("number") or "").strip()
    if not raw_number:
        flash("กรุณาระบุเลขที่สัญญา")
        return redirect(url_for("advance_payment.verification_view", ticket_id=ticket_id))

    if not raw_number.isdigit():
        flash("เลขที่สัญญาต้องเป็นตัวเลขเท่านั้น เช่น 1, 2, 3")
        return redirect(url_for("advance_payment.verification_view", ticket_id=ticket_id))

    number = int(raw_number)
    borrowing_ticket.status = "อนุมัติจ่ายเงิน"
    borrowing_ticket.number = number
    borrowing_ticket.approved_at = datetime.now()
    borrowing_ticket.finance_verified = True
    db.session.commit()

    _send_notification_email(borrowing_ticket)

    flash("อนุมัติสัญญาเงินยืมเงินทดรองจ่ายและส่งอีเมลแจ้งเตือนเรียบร้อยแล้ว")

    return redirect(url_for("advance_payment.finance_dashboard"))

@bp.route("/api/login", methods=["POST"])
def api_login():
    payload = request.get_json(silent=True) or request.form
    requested_role = (payload.get("role") or payload.get("login_path") or "").strip()
    staff = _module_user_from_session()
    if not staff:
        return jsonify({"ok": False, "message": "กรุณาเข้าสู่ระบบ MIS ก่อนใช้งาน Advance Payment"}), 401

    requested_role, error_message = _ensure_module_role(staff, requested_role)
    if not requested_role:
        return jsonify({"ok": False, "message": error_message or "กรุณาเลือกบทบาท"}), 401

    _sync_advance_payment_session(staff, requested_role)
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
@login_required(role="finance")
def reject_borrowing_ticket(ticket_id):
    borrowing_ticket = (
        db.session.query(BorrowingTicket).filter_by(id=ticket_id).first()
    )
    if borrowing_ticket is None:
        abort(404)

    if borrowing_ticket.status != "กำลังส่งคำขอ":
        flash("เฉพาะสัญญาเงินยืมเงินที่ กำลังส่งคำขอ เท่านั้นที่สามารถปฏิเสธได้")
        return redirect(url_for("advance_payment.finance_dashboard"))

    borrowing_ticket.rejection_comment = request.form.get(
        "rejection_comment",
        ""
    ).strip()
    borrowing_ticket.finance_verified = False
    borrowing_ticket.status = "ปฏิเสธ"
    db.session.commit()
    _send_notification_email(borrowing_ticket)
    flash("ปฏิเสธสัญญาเงินยืมเงินทดรองจ่ายเรียบร้อยแล้ว")
    return redirect(url_for("advance_payment.finance_dashboard"))

@bp.route("/finance/return-records", methods=["GET"])
@login_required(role="finance")
def return_records_history():
    # 1. ดึงข้อมูลประวัติหลักฐานเอกสารส่งใช้เงินยืม (ReturnDetail)
    return_records = db.session.query(ReturnDetail).filter(ReturnDetail.status != "ฉบับร่าง").all()

    processed_records = []
    for record in return_records:
        ticket = db.session.query(BorrowingTicket).filter_by(id=record.ticket_id).first()
        closing_document = _get_closing_document(record.closing_document_id)

        processed_records.append({
            "record_type": "return",
            "id": record.id,
            "ticket_id": record.ticket_id,
            "ticket_number": f"บย. {ticket.number}" if ticket and ticket.number else "N/A",
            "borrowing_ticket_name": ticket.borrowing_ticket_name if ticket else "N/A",
            "borrower_name": (ticket.borrower_name or getattr(_get_user_by_id(getattr(ticket, "borrower_id", None)), "name", "")) if ticket else "N/A",
            "amount_spent": float(record.amount_spent or 0),
            "total_amount": float(record.amount_spent or 0),
            "status": record.status,
            "created_at": record.created_at,
            "closed_at": closing_document.filing_date if closing_document else None,
            "closing_document_id": record.closing_document_id or "-",
            "closing_document_name": closing_document.document_number if closing_document else "-",
            "old_document_number": record.old_closing_document_name or ""
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
        closing_document = _get_closing_document(record.closing_document_id)

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
            "amount_spent": float(record.amount_spent or 0),
            "total_amount": float(record.amount_spent or 0),
            "status": record.status,
            "created_at": record.created_at if hasattr(record, 'created_at') else None,
            "closed_at": closing_document.filing_date if closing_document else None,
            "closing_document_id": record.closing_document_id or "-",
            "closing_document_name": closing_document.document_number if closing_document else "-",
            "old_document_number": record.old_closing_document_name or ""
        })

    return render_template(
        "advance_payment/return_records_history.html",
        records=processed_records,
        history_mode="return",
    )


@bp.route("/finance/petty-cash-claim-records", methods=["GET"])
@login_required(role="finance")
def petty_cash_claim_history():
    # 1. ดึงข้อมูลรายการขอเบิกเงินสดย่อย (PettyCashClaimDetail)
    claim_details = (
        db.session.query(PettyCashClaimDetail)
        .filter(PettyCashClaimDetail.status != "ฉบับร่าง")
        .order_by(PettyCashClaimDetail.created_at.desc())
        .all()
    )

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
        borrower_name = claim.user.name if claim.user else '-'

        processed_claims.append({
            "record_type": "petty_cash",
            "id": claim.id,
            "fund_request_id": claim.fund_request_id,
            "ticket_id": None,
            "ticket_number": ticket_num,
            "borrowing_ticket_name": dept_name,
            "borrower_name": borrower_name,
            "amount_spent": float(claim.total_amount),
            "total_amount": float(claim.total_amount),
            "status": claim.status,
            "created_at": claim.created_at,
            "closed_at": closing_doc.filing_date if closing_doc else None,
            "closing_document_id": claim.closing_document_id or "-",
            "closing_document_name": closing_doc.document_number if closing_doc else "-",
            "old_document_number": claim.old_closing_document_name or ""
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
        closing_document = _get_closing_document(record.closing_document_id)

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
            "amount_spent": float(record.amount_spent or 0),
            "total_amount": float(record.amount_spent or 0),
            "status": record.status,
            "created_at": record.created_at if hasattr(record, 'created_at') else None,
            "closed_at": closing_document.filing_date if closing_document else None,
            "closing_document_id": record.closing_document_id or "-",
            "closing_document_name": closing_document.document_number if closing_document else "-",
            "old_document_number": record.old_closing_document_name or ""
        })

    return render_template(
        "advance_payment/petty_cash_claim_history.html",
        records=processed_claims,
        history_mode="petty_cash",
    )


def _parcel_return_history_fallback(parcel_return):
    if getattr(parcel_return, "fund_request_id", None):
        return "advance_payment.petty_cash_claim_history"
    return "advance_payment.return_records_history"

@bp.route("/finance/petty-cash-settings", methods=["GET", "POST"])
@login_required(role="finance")
def petty_cash_settings():
    bank_account_options = _get_bank_account_dropdown_options()
    bank_account_values = {option["value"] for option in bank_account_options}

    if request.method == "POST":
        fiscal_years = request.form.getlist("fiscal_year[]")
        dept_names = request.form.getlist("dept_name[]")
        custodian_names = request.form.getlist("custodian_name[]")  # <--- รับชื่อผู้ดูแลบัญชี
        budgets = request.form.getlist("budget[]")
        acc_numbers = request.form.getlist("account_number[]")
        bank_account_info_ids = request.form.getlist("bank_account_info_id[]")
        valid_dept_names = request.form.getlist("valid_dept[]")

        for i in range(len(dept_names)):
            name = dept_names[i].strip()
            fy_str = fiscal_years[i].strip() if i < len(fiscal_years) else ""
            custodian = custodian_names[i].strip() if i < len(custodian_names) else ""
            bg_str = budgets[i].strip().replace(",", "")
            acc = acc_numbers[i].strip() if i < len(acc_numbers) else ""
            raw_bank_account_info_id = bank_account_info_ids[i].strip() if i < len(bank_account_info_ids) else ""
            selected_bank_account = _get_bank_account_info(
                bank_account_info_id=raw_bank_account_info_id,
                account_number=acc,
            )
            bank_account_info_id = selected_bank_account.id if selected_bank_account else None
            if selected_bank_account and selected_bank_account.account_number:
                acc = selected_bank_account.account_number
            is_valid = name in valid_dept_names

            if name and bg_str and acc and fy_str:
                existing = db.session.query(PettyCashSetting).filter_by(department_name=name).first()
                if existing:
                    existing.fiscal_year = int(fy_str)
                    existing.custodian_name = custodian  # <--- อัปเดตผู้ดูแลบัญชี
                    existing.budget = float(bg_str)
                    existing.account_number = acc
                    existing.bank_account_info_id = bank_account_info_id
                    existing.valid = is_valid
                else:
                    new_setting = PettyCashSetting(
                        fiscal_year=int(fy_str),
                        department_name=name,
                        custodian_name=custodian,  # <--- สร้างพร้อมบันทึกผู้ดูแลบัญชี
                        budget=float(bg_str),
                        account_number=acc,
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
            flash(f"เกิดข้อผิดพลาดในการบันทึก: {str(e)}", "danger")

        return redirect(url_for("advance_payment.petty_cash_settings"))

    settings = db.session.query(PettyCashSetting).all()

    claim_details = (
        db.session.query(PettyCashClaimDetail)
        .filter(PettyCashClaimDetail.status == "ผ่านการตรวจสอบ")
        .order_by(PettyCashClaimDetail.created_at.desc())
        .all()
    )

    dept_summary = {}
    for s in settings:
        summary = _calculate_petty_cash_balance_summary(s)
        summary["setting"] = s
        # Use the setting primary key as the canonical summary key so the
        # template is not dependent on a mutable department name string.
        dept_summary[s.id] = summary

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
        settings=settings,
        claim_details=claim_details,
        dept_summary=dept_summary,
        bank_account_options=bank_account_options,
        bank_account_values=bank_account_values,
    )


@bp.route("/api/custodian/suggest", methods=["GET"])
@login_required()
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

    setting = db.session.query(PettyCashSetting).filter_by(department_name=dept_name).first()
    if setting and setting.custodian_name:
        return jsonify({"custodian_name": setting.custodian_name})

    return jsonify({"custodian_name": ""})

@bp.route("/api/petty-cash-options", methods=["GET"])
@login_required(role="finance")
def api_petty_cash_options():
    q = request.args.get("q", "").strip()
    query = db.session.query(PettyCashSetting).filter(PettyCashSetting.valid == True)
    if q:
        query = query.filter(PettyCashSetting.department_name.contains(q))

    settings = query.all()
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
@login_required(role="finance")
def closing_management():
    search_closing_number = request.args.get("search_closing_number", "").strip()
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
        matched_return_ids = set()
        matched_parcel_return_ids = set()
        matched_petty_cash_ids = set()

        for searched_doc in searched_docs:
            doc_returns = db.session.query(ReturnDetail).filter(
                (ReturnDetail.closing_document_id == searched_doc.id)
                | (ReturnDetail.old_closing_document_name == searched_doc.document_number)
            ).all()
            doc_parcel_returns = db.session.query(ParcelReturnDetail).filter(
                (ParcelReturnDetail.closing_document_id == searched_doc.id)
                | (ParcelReturnDetail.old_closing_document_name == searched_doc.document_number)
            ).all()
            doc_petty_cash = db.session.query(PettyCashClaimDetail).filter(
                (PettyCashClaimDetail.closing_document_id == searched_doc.id)
                | (PettyCashClaimDetail.old_closing_document_name == searched_doc.document_number)
            ).all()

            matched_return_ids.update(ret.id for ret in doc_returns)
            matched_parcel_return_ids.update(pr.id for pr in doc_parcel_returns)
            matched_petty_cash_ids.update(petty.id for petty in doc_petty_cash)

            for petty in doc_petty_cash:
                related_claim = _attach_petty_cash_claim_context(petty)
                petty.amount = float(petty.total_amount or 0)
                petty.department_name = (
                    petty.setting.department_name
                    if petty.setting
                    else (petty.user.department if petty.user else "ไม่ระบุ")
                )
                petty.requester_name = "-"
                petty.claim_number = "-"
                if related_claim:
                    fund_request = related_claim.fund_request
                    petty.requester_name = (
                        fund_request.requester_name
                        if fund_request and fund_request.requester_name
                        else (related_claim.user.name if related_claim.user else petty.requester_name)
                    )
                    petty.claim_number = (
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
            })

        # Keep showing records that only refer to an older/cancelled document.
        searched_petty_cash = db.session.query(PettyCashClaimDetail).filter(
            PettyCashClaimDetail.old_closing_document_name.contains(search_closing_number)
        ).all()
        searched_returns = db.session.query(ReturnDetail).filter(
            ReturnDetail.old_closing_document_name.contains(search_closing_number)
        ).all()
        searched_parcel_returns = db.session.query(ParcelReturnDetail).filter(
            ParcelReturnDetail.old_closing_document_name.contains(search_closing_number)
        ).all()

        searched_petty_cash = [
            petty for petty in searched_petty_cash if petty.id not in matched_petty_cash_ids
        ]
        searched_returns = [
            ret for ret in searched_returns if ret.id not in matched_return_ids
        ]
        searched_parcel_returns = [
            pr for pr in searched_parcel_returns if pr.id not in matched_parcel_return_ids
        ]

        for petty in searched_petty_cash:
            related_claim = _attach_petty_cash_claim_context(petty)
            petty.amount = float(petty.total_amount or 0)
            petty.department_name = (
                petty.setting.department_name
                if petty.setting
                else (petty.user.department if petty.user else "ไม่ระบุ")
            )
            petty.requester_name = "-"
            petty.claim_number = "-"
            if related_claim:
                fund_request = related_claim.fund_request
                petty.requester_name = (
                    fund_request.requester_name
                    if fund_request and fund_request.requester_name
                    else (related_claim.user.name if related_claim.user else petty.requester_name)
                )
                petty.claim_number = (
                    related_claim.claim_number
                    or (fund_request.ticket_number if fund_request and fund_request.ticket_number else None)
                    or f"PC-{related_claim.id}"
                )
                petty.name = petty.requester_name

        for ret in searched_returns:
            if not hasattr(ret, 'borrowing_ticket') or ret.borrowing_ticket is None:
                ret.borrowing_ticket = db.session.query(BorrowingTicket).filter_by(id=ret.ticket_id).first()

        for pr in searched_parcel_returns:
            _attach_parcel_return_context(pr)

    if request.method == "POST":
        document_number = request.form.get("document_number", "").strip()
        filing_date_str = request.form.get("filing_date", "").strip()
        total_amount_input = request.form.get("total_amount", "0").strip()

        return_ids = request.form.getlist("return_ids[]")
        parcel_return_ids = request.form.getlist("parcel_return_ids[]")
        petty_claim_ids = request.form.getlist("petty_claim_ids[]")  # รับเฉพาะ ID ของรายการเงินสดย่อยที่ถูกเลือก

        if not document_number or not filing_date_str:
            flash("กรุณากรอกเลขที่ฎีกาและวันที่ตั้งฎีกา")
            return redirect(url_for("advance_payment.closing_management"))

        filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d").date()
        total_amount = float(total_amount_input.replace(",", ""))

        new_closing_doc = ClosingDocument(
            document_number=document_number,
            filing_date=filing_date,
            total_amount=total_amount,
            created_at=datetime.now(),
        )
        db.session.add(new_closing_doc)
        db.session.flush()

        # --- ส่วนจัดการรายการเงินสดย่อย (Petty Claim) ที่เลือก ---
        if petty_claim_ids:
            # ดึงเฉพาะรายการ PettyCashClaimDetail ที่ถูกติ๊กเลือก และมีสถานะเป็น transferred
            selected_claims = db.session.query(PettyCashClaimDetail).filter(
                PettyCashClaimDetail.id.in_([int(p_id) for p_id in petty_claim_ids]),
                PettyCashClaimDetail.status == "โอนเงินสดย่อยสำเร็จ"
            ).all()

            for claim in selected_claims:
                _attach_petty_cash_claim_context(claim)
                setting_id = claim.setting.id if claim.setting else None
                dept_name = claim.setting.department_name if claim.setting else "ไม่ระบุ"
                budget_val = float(claim.setting.budget or 0) if claim.setting else 0.0
                acc_num = claim.setting.account_number if claim.setting else ""
                claim_amount = float(claim.total_amount or claim.amount or 0)
                requester_name = (
                    claim.fund_request.requester_name
                    if claim.fund_request and claim.fund_request.requester_name
                    else (claim.user.name if claim.user else "-")
                )

                # อัปเดตสถานะของ PettyCashClaimDetail เดิม
                claim.status = "เอกสารตั้งฎีกา"
                claim.closing_document_id = new_closing_doc.id

        updated_ticket_ids = set()

        if return_ids:
            records = db.session.query(ReturnDetail).filter(
                ReturnDetail.id.in_([int(r_id) for r_id in return_ids]),
                ReturnDetail.status == "ผ่านการตรวจสอบ"
            ).all()
            for record in records:
                previous_document = _get_closing_document(record.closing_document_id)
                if previous_document and previous_document.id != new_closing_doc.id:
                    record.old_closing_document_name = previous_document.document_number
                record.status = "เอกสารตั้งฎีกา"
                record.closing_document_id = new_closing_doc.id
                updated_ticket_ids.add(record.ticket_id)

        if parcel_return_ids:
            parcel_records = db.session.query(ParcelReturnDetail).filter(
                ParcelReturnDetail.id.in_([int(p_id) for p_id in parcel_return_ids]),
                ParcelReturnDetail.status == "ได้รับเอกสารแล้ว"
            ).all()
            for pr_record in parcel_records:
                previous_document = _get_closing_document(pr_record.closing_document_id)
                if previous_document and previous_document.id != new_closing_doc.id:
                    pr_record.old_closing_document_name = previous_document.document_number
                pr_record.status = "เอกสารตั้งฎีกา"
                pr_record.closing_document_id = new_closing_doc.id
                updated_ticket_ids.add(pr_record.ticket_id)

        for t_id in updated_ticket_ids:
            _recalculate_borrowing_ticket_status(t_id)

        db.session.commit()
        flash(f"บันทึกเอกสารตั้งฎีกาเลขที่ {document_number} ยอดรวม {total_amount:,.2f} บาท สำเร็จ")
        return redirect(url_for("advance_payment.closing_management"))

    # --- ส่วนการดึงข้อมูลเพื่อแสดงผล (GET) ---
    proofed_records = db.session.query(ReturnDetail).filter(ReturnDetail.status == "ผ่านการตรวจสอบ").all()
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
            "status": record.status,
            "created_at": record.created_at,
        })

    proofed_parcels = db.session.query(ParcelReturnDetail).filter(ParcelReturnDetail.status == "ได้รับเอกสารแล้ว").all()
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
            borrowing_ticket_number = fund_request.ticket_number if fund_request.ticket_number else "N/A"
            borrowing_ticket_name = fund_request.purpose or "N/A"
            borrower_name = (
                fund_request.requester_name
                or getattr(_get_user_by_id(getattr(fund_request, "requester_id", None)), "name", "")
                or borrower_name
            )

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
        PettyCashClaimDetail.status == "โอนเงินสดย่อยสำเร็จ"
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
        all_petty_settings=all_petty_settings
    )

@bp.route("/finance/returns/<int:return_id>/update-closing-doc", methods=["POST"])
@login_required(role="finance")
def update_return_closing_doc(return_id):
    """ แก้ไขเลขฎีกาของใบคืนเงินชิ้นนี้ พร้อมบันทึกประวัติเดิม """
    return_detail = db.session.query(ReturnDetail).get(return_id)
    if not return_detail:
        abort(404)

    new_doc_number = request.form.get("new_document_number", "").strip()
    if not new_doc_number:
        flash("กรุณาระบุหมายเลขฎีกาใหม่", "danger")
        return redirect(request.referrer)

    # เก็บประวัติฎีกาเดิมก่อนเปลี่ยน
    current_doc = return_detail.closing_document
    if current_doc:
        old_history = return_detail.old_closing_document_name
        return_detail.old_closing_document_name = f"{old_history}, {current_doc.document_number}" if old_history else current_doc.document_number
        current_doc.total_amount = max(0, float(current_doc.total_amount or 0) - float(return_detail.amount_spent or 0))

    target_doc = db.session.query(ClosingDocument).filter_by(document_number=new_doc_number).first()
    if not target_doc:
        target_doc = ClosingDocument(
            document_number=new_doc_number,
            filing_date=date.today(),
            total_amount=0,
            created_at=datetime.now(),
        )
        db.session.add(target_doc)
        db.session.flush()

    target_doc.total_amount = float(target_doc.total_amount or 0) + float(return_detail.amount_spent or 0)
    return_detail.closing_document_id = target_doc.id
    return_detail.status = "เอกสารตั้งฎีกา"

    db.session.commit()
    flash(f"อัปเดตเลขฎีกาเป็น {new_doc_number} เรียบร้อยแล้ว", "success")
    return redirect(request.referrer)

@bp.route("/finance/returns/<int:return_id>/proof")
@bp.route("/finance/returns/<int:return_id>/proof", endpoint="return_proof_detail")
@login_required()
def view_return_proof_detail(return_id):
    return_detail = db.session.query(ReturnDetail).get(return_id)
    if not return_detail:
        abort(404)

    borrowing_ticket = db.session.query(BorrowingTicket).get(return_detail.ticket_id)
    if not borrowing_ticket:
        abort(404)

    if _selected_system() == ADVANCE_PAYMENT_SYSTEM and (
        (not _is_current_coordinator() and borrowing_ticket.borrower_id != session.get("user_id"))
        or (_is_current_coordinator() and borrowing_ticket.creator_id != session.get("user_id"))
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

    return render_template(
        "return_proof_detail.html",
        return_detail=return_detail,
        borrowing_ticket=borrowing_ticket,
        proof_files=proof_files
    )

@bp.route(
    "/finance/ticket/<int:ticket_id>/note",
    methods=["POST"]
)
@login_required(role="finance")
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

    return redirect(
        url_for(
            "advance_payment.verification_view",
            ticket_id=ticket_id
        )
    )

@bp.errorhandler(403)
def forbidden(_exception):
    return render_template("advance_payment/403.html"), 403

@bp.route("/staff/fund-request", methods=["GET", "POST"])
@login_required(role=PETTY_CASH_SYSTEM)
def staff_fund_request():
    user = db.session.query(StaffAccount).filter_by(id=session["user_id"]).first()
    if not user:
        abort(404)

    setting = _resolve_petty_cash_setting(user)
    _attach_petty_cash_setting_people(setting)
    approved_borrowing_tickets = _get_approved_borrowing_tickets_for_setting(setting)
    staff_department_name = _get_staff_department_name(user)
    staff_org = _get_staff_org(user) or _resolve_org_by_department_name(staff_department_name)
    department_employees = _serialize_org_department(staff_org).get("staff_members", []) if staff_org else []
    for ticket in approved_borrowing_tickets:
        _attach_borrowing_ticket_people(ticket)
    form = FundRequestForm(request.form)

    if request.method == "GET":
        form.requester_name.data = user.name if user else ""
        form.requester_position.data = user.position if hasattr(user, 'position') else "เจ้าหน้าที่"
        # Use the staff/org name for employee lookup, and keep petty cash account data from the setting.
        if staff_department_name:
            form.department.data = staff_department_name
        elif setting:
            form.department.data = setting.department_name

        if setting:
            form.account_number.data = setting.account_number

        form.period_year.data = str(datetime.now().year)

    if request.method == "POST" and form.validate():
        try:
            req_dept = setting.department_name if setting else (_get_staff_department_name(user) or "ไม่ระบุหน่วยงาน")
            req_acc = setting.account_number if setting else ""
            form_type = form.form_type.data
            selected_borrowing_ticket = None

            req_date = form.request_date.data if form.request_date.data else datetime.now().date()
            fund_in_date = _coerce_date(request.form.get("fund_in_date"))
            withdrawal_date = _coerce_date(request.form.get("withdrawal_date"))
            if form_type == '31':
                req_name = user.name
                req_pos = user.position if hasattr(user, 'position') and user.position else "ผู้ดูแลบัญชี"
            elif form_type == FUND_REQUEST_FORM_BORROWING_TICKET:
                borrowing_ticket_id = request.form.get("borrowing_ticket_id", type=int)
                if not borrowing_ticket_id:
                    flash("กรุณาเลือกใบยืมเงินที่ต้องการเบิกผ่านบัญชีเงินสดย่อย", "danger")
                    return redirect(url_for("advance_payment.staff_fund_request", form_type=FUND_REQUEST_FORM_BORROWING_TICKET))

                selected_borrowing_ticket = next(
                    (ticket for ticket in approved_borrowing_tickets if ticket.id == borrowing_ticket_id),
                    None,
                )
                if not selected_borrowing_ticket:
                    flash("ไม่พบใบยืมเงินที่สามารถใช้งานได้สำหรับหน่วยงานนี้", "danger")
                    return redirect(url_for("advance_payment.staff_fund_request", form_type=FUND_REQUEST_FORM_BORROWING_TICKET))

                borrower_user = getattr(selected_borrowing_ticket, "borrower_user", None)
                req_name = selected_borrowing_ticket.borrower_name or getattr(borrower_user, "name", "") or user.name
                req_pos = getattr(borrower_user, "position", "") or user.position or "ผู้ขอเบิก"
                req_dept = _get_staff_department_name(borrower_user, req_dept) or req_dept
                req_acc = selected_borrowing_ticket.account_number or req_acc
                req_date = datetime.now().date()
            else:
                req_name = form.requester_name.data
                req_pos = form.requester_position.data

            # ตั้งสถานะเริ่มต้นเป็น 'กำลังดำเนินการ' และ ticket_number เป็น None (ยังไม่มีเลข)
            new_request = FundRequest(
                requester_id=user.id,
                form_type=form_type,
                requester_name=req_name,
                requester_position=req_pos,
                department_name=req_dept,
                account_number=req_acc,
                ticket_number=None,  # รอระบุเลขตอนอนุมัติ
                request_date=req_date,
                fund_in_date=fund_in_date if form_type == '31' else None,
                withdrawal_date=withdrawal_date if form_type == '31' else None,
                amount=form.amount.data,
                purpose=form.purpose.data if form_type == '30' else ("ขออนุมัติเบิกดอกเบี้ย" if form_type == '31' else ""),
                period_year=_normalize_interest_period_value(request.form.get("period_year")) if form_type == '31' else "",
                borrowing_ticket_id=selected_borrowing_ticket.id if selected_borrowing_ticket else None,
                created_at=datetime.now(),
                status="กำลังดำเนินการ"
            )

            db.session.add(new_request)
            db.session.flush()

            if form_type == '30':
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
                new_request.requester_name = selected_borrowing_ticket.borrower_name or new_request.requester_name
                new_request.requester_position = getattr(getattr(selected_borrowing_ticket, "borrower_user", None), "position", "") or new_request.requester_position
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

            if form_type == '31':
                # 1. ดึงค่าจาก Radio Button (จะได้ เช่น "มิถุนายน พ.ศ. 2567" หรือ "ธันวาคม พ.ศ. 2567")
                selected_period = request.form.get("period_year_radio", "")
                period_year_val = _normalize_interest_period_value(selected_period)

                withdrawal_proof_file = request.files.get("withdrawal_proof_file")
                new_request.period_year = period_year_val

                if withdrawal_proof_file and withdrawal_proof_file.filename:
                    safe_filename = secure_filename(withdrawal_proof_file.filename)
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    new_filename = f"withdrawal_proof_{timestamp_str}_{safe_filename}"
                    upload_folder = os.path.join(
                        _upload_root(),
                        "fund_requests",
                        str(user.id),
                    )
                    os.makedirs(upload_folder, exist_ok=True)
                    proof_reference = f"uploads/fund_requests/{user.id}/{new_filename}"
                    withdrawal_proof_file.save(os.path.join(upload_folder, new_filename))
                    new_request.status = "เบิกเงินแล้ว"
                    _assign_fund_request_ticket_number(new_request, reference_date=req_date)
                    new_request.withdrawal_proof_reference = proof_reference
                    new_request.withdrawal_proof_filename = withdrawal_proof_file.filename

            db.session.commit()

            pdf_bytes = generate_fund_request_pdf(new_request)

            response = current_app.response_class(pdf_bytes, mimetype='application/pdf')
            response.headers['Content-Disposition'] = f'attachment; filename=Fund_Request_{new_request.id}.pdf'
            return response

        except Exception as e:
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return f"เกิดข้อผิดพลาด: {str(e)}", 500

    selected_form_type = request.args.get("form_type", form.form_type.data or "30")
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
    )

@bp.route("/staff/fund-request/<int:request_id>/reject", methods=["POST"])
@login_required(role=SECRETARY_ROLE)
def reject_fund_request(request_id):
    current_user = db.session.query(StaffAccount).get(session.get("user_id"))
    if not current_user or not _is_current_secretary():
        abort(403)

    fund_req = db.session.query(FundRequest).get(request_id)
    if not fund_req:
        abort(404)

    if fund_req.status != "กำลังดำเนินการ":
        flash("สามารถปฏิเสธได้เฉพาะรายการที่อยู่ในสถานะกำลังดำเนินการเท่านั้น", "warning")
        return redirect(url_for("advance_payment.staff_fund_request_history"))

    rejection_comment = request.form.get("rejection_comment", "").strip()

    fund_req.status = "ปฏิเสธ"
    if hasattr(fund_req, 'rejection_comment'):
        fund_req.rejection_comment = rejection_comment

    db.session.commit()
    flash("ปฏิเสธใบเบิกเรียบร้อยแล้ว (สิ้นสุดกระบวนการ)", "info")
    return redirect(url_for("advance_payment.staff_fund_request_history"))

@bp.route("/staff/fund-request-history", methods=["GET"])
@login_required(role=PETTY_CASH_SYSTEM)
def staff_fund_request_history():
    user = db.session.query(StaffAccount).filter_by(id=session["user_id"]).first()
    if not user:
        abort(404)

    setting = _resolve_petty_cash_setting(user)
    is_staff_user = not _is_current_secretary()

    fund_requests_query = db.session.query(FundRequest)
    if is_staff_user:
        fund_requests_query = fund_requests_query.filter_by(requester_id=user.id)
    fund_requests = fund_requests_query.order_by(FundRequest.id.desc()).all()

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

    return render_template(
        "staff_fund_request_history.html",
        setting=setting,
        fund_requests=fund_requests,
        claim_history=claim_history,
        dept_summary=dept_summary
    )


@bp.route("/staff/petty-cash-claims/<int:claim_id>/claim-number", methods=["POST"])
@login_required(role=PETTY_CASH_SYSTEM)
def update_petty_cash_claim_number(claim_id):
    current_user = db.session.query(StaffAccount).get(session.get("user_id"))
    if not current_user:
        abort(404)

    claim = db.session.query(PettyCashClaimDetail).get(claim_id)
    if not claim:
        abort(404)

    can_edit = False
    if not _is_current_secretary():
        can_edit = claim.user_id == current_user.id
    else:
        setting = _resolve_petty_cash_setting(current_user)
        can_edit = bool(
            (setting and setting.id and claim.petty_cash_setting_id == setting.id)
            or claim.user_id == current_user.id
        )

    if not can_edit:
        abort(403)

    claim_number = request.form.get("claim_number", "").strip()
    if not claim_number:
        flash("กรุณาระบุเลขอว.", "warning")
        return redirect(request.referrer or url_for("advance_payment.staff_fund_request_history"))

    claim.claim_number = claim_number
    db.session.commit()
    flash("บันทึกเลขอว. เรียบร้อยแล้ว", "success")
    return redirect(request.referrer or url_for("advance_payment.staff_fund_request_history"))

@bp.route("/staff/fund-request/<int:request_id>/pdf")
@login_required()
def export_fund_request_pdf(request_id):
    fund_req = db.session.query(FundRequest).get(request_id)
    if not fund_req:
        abort(404)
        
    if _selected_system() == PETTY_CASH_SYSTEM and not _is_current_secretary() and fund_req.user_id != session.get("user_id"):
        abort(403)
        
    pdf_bytes = generate_fund_request_pdf(fund_req)
    
    response = current_app.response_class(pdf_bytes, mimetype='application/pdf')
    if fund_req.form_type == FUND_REQUEST_FORM_BORROWING_TICKET:
        filename = f"Borrowing_Ticket_Petty_Cash_{request_id}.pdf"
    else:
        filename = f"FundRequest_Form{fund_req.form_type}_{request_id}.pdf"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
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
@login_required()
def api_get_department_employees():
    """ API สำหรับส่ง JSON ไปยังระบบ Frontend """
    dept = request.args.get("department")
    data = get_department_data_service(dept)

    if dept and not data:
        return jsonify([]) 
    
    staff_list = data.get("staff_members", []) if isinstance(data, dict) else []
    return jsonify(staff_list)

@bp.route("/api/employees/suggest", methods=["GET"])
@login_required()
def suggest_employees():
    q = request.args.get("q", "").strip().lower()
    
    current_user = db.session.query(StaffAccount).get(session.get("user_id"))
    user_dept = None
    
    if current_user:
        if getattr(current_user, 'petty_cash_setting', None):
            user_dept = current_user.petty_cash_setting.department_name
        else:
            user_dept = _get_staff_department_name(current_user)

    dept = user_dept or request.args.get("department", "").strip()

    if not dept:
        return jsonify([])

    dept_data = get_department_data_service(dept)
    if not dept_data:
        return jsonify([])

    all_members = []
    seen_names = set()

    head = dept_data.get("head_of_department")
    if head and head.get("name") not in seen_names:
        all_members.append({
            "id": f"head_{dept_data.get('department_code')}",
            "name": head.get("name"),
            "position": head.get("position", "หัวหน้าฝ่าย"),
            "department": dept
        })
        seen_names.add(head.get("name"))

    staff_members = dept_data.get("staff_members", [])
    for member in staff_members:
        if member.get("name") not in seen_names:
            all_members.append({
                "id": member.get("id"),
                "name": member.get("name"),
                "position": member.get("position", "บุคลากร"),
                "department": dept
            })
            seen_names.add(member.get("name"))

    if q:
        filtered_results = [
            m for m in all_members
            if q in m["name"].lower() or q in m["position"].lower()
        ]
    else:
        filtered_results = all_members

    return jsonify(filtered_results[:10])

CATEGORY_CHOICES = {
    1: "ค่าตอบแทน (เช่น ค่าเบี้ยเลี้ยง, ค่าตอบแทนวิทยากร)",
    2: "ค่าใช้สอย (เช่น ค่าซ่อมแซม, ค่าเช่า, ค่าจ้างเหมา)",
    3: "ค่าวัสดุ (เช่น เครื่องเขียน, วัสดุสำนักงาน, อุปกรณ์)",
    4: "ค่าสาธารณูปโภค (เช่น ค่าที่พัก, ค่าเดินทาง, ค่าค่าน้ำ-ไฟ)",
    5: "อื่น ๆ",
    6: "โอนคืนบัญชีหน่วย"
}

@bp.route("/staff/fund-request/<int:request_id>/approve", methods=["POST"])
@login_required(role=SECRETARY_ROLE)
def approve_fund_request(request_id):
    current_user = db.session.query(StaffAccount).get(session.get("user_id"))
    if not current_user or not _is_current_secretary():
        abort(403)

    fund_req = db.session.query(FundRequest).get(request_id)
    if not fund_req:
        abort(404)

    if fund_req.status != "กำลังดำเนินการ":
        flash("สามารถอนุมัติได้เฉพาะรายการที่อยู่ในสถานะกำลังดำเนินการเท่านั้น", "warning")
        return redirect(url_for("advance_payment.staff_fund_request_history"))

    # แยกประเภทฟอร์มในการปรับสถานะ
    if fund_req.form_type in {'30', FUND_REQUEST_FORM_BORROWING_TICKET}:
        fund_req.status = "อนุมัติแล้ว"
    elif fund_req.form_type == '31':
        fund_req.status = "เบิกเงินแล้ว"
    else:
        fund_req.status = "อนุมัติแล้ว"

    ticket_number = _assign_fund_request_ticket_number(fund_req)

    db.session.commit()
    flash(f"อนุมัติใบเบิกและออกเลขที่ {ticket_number} เรียบร้อยแล้ว", "success")
    return redirect(url_for("advance_payment.staff_fund_request_history"))

@bp.route("/coordinator/petty-cash-claim/autosave-draft", methods=["POST"], endpoint="coordinator_petty_cash_claim_autosave_draft")
@bp.route("/borrower/petty-cash-claim/autosave-draft", methods=["POST"], endpoint="borrower_petty_cash_claim_autosave_draft")
@login_required()
def autosave_petty_cash_claim_draft():
    user_id = session.get("user_id")
    data = request.get_json() or {}
    
    fund_request_id = data.get("fund_request_id")
    items = data.get("items", [])
    announcements = data.get("announcements", [])

    # 1. ดึง Setting ของ StaffAccount ปัจจุบันก่อน (ถ้าไม่มีค่อย fallback ไปตัว active ตัวแรก)
    current_user = db.session.query(StaffAccount).get(user_id) if user_id else None
    setting = _resolve_petty_cash_setting(current_user)

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
@login_required()
def submit_petty_cash_claim():
    user_id = session["user_id"]
    current_user = db.session.query(StaffAccount).get(user_id)
    current_role = session.get("user_role") or (getattr(current_user, "role", None) if current_user else None)
    if not current_user or _selected_system() not in {PETTY_CASH_SYSTEM, FINANCE_SYSTEM}:
        abort(403)

    setting = _resolve_petty_cash_setting(current_user)
    is_staff_user = _selected_system() == PETTY_CASH_SYSTEM and not _is_current_secretary()
    is_finance_user = (current_role == "finance")
    can_submit_claim = _selected_system() == PETTY_CASH_SYSTEM

    approved_fund_requests = []
    if can_submit_claim:
        approved_fund_requests = [
            fund_request
            for fund_request in db.session.query(FundRequest).filter(
                FundRequest.requester_id == user_id,
            ).order_by(FundRequest.id.desc()).all()
            if (fund_request.status or "").strip() == "อนุมัติแล้ว"
        ]
    elif setting and setting.id:
        approved_fund_requests = [
            fund_request
            for fund_request in db.session.query(FundRequest).filter(
                FundRequest.requester_id == user_id,
                FundRequest.department_name == setting.department_name,
            ).order_by(FundRequest.id.desc()).all()
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
    selected_fr_id = request.args.get("fund_request_id", type=int)
    if selected_fr_id:
        selected_request_query = db.session.query(FundRequest).filter_by(id=selected_fr_id)
        if not can_submit_claim and not is_finance_user:
            selected_request_query = selected_request_query.filter_by(requester_id=user_id)
        selected_fund_request = selected_request_query.first()

    if request.method == "POST":
        action = request.form.get("action", "submit")
        is_draft = (action == "draft")

        receipt_dates = request.form.getlist("receipt_date[]")
        descriptions = request.form.getlist("description[]")
        category_types = request.form.getlist("category_type[]")
        amounts = request.form.getlist("amount[]")
        announcement_ids = request.form.getlist("announcement_ids[]")
        announcement_titles = request.form.getlist("announcement_titles[]")
        fund_request_id_raw = (request.form.get("fund_request_id") or "").strip()
        fund_request_id = int(fund_request_id_raw) if fund_request_id_raw.isdigit() else None

        parsed_items = []
        total_claim_amount = 0.0
        old_receipt_count = 0

        for i in range(len(receipt_dates)):
            r_date = _coerce_date(receipt_dates[i]) if i < len(receipt_dates) and receipt_dates[i] else None
            cat_val_str = str(category_types[i]).strip() if i < len(category_types) and category_types[i] else "1"
            cat_val_int = int(cat_val_str) if cat_val_str.isdigit() else 1

            try:
                amt = float(str(amounts[i] or 0).replace(",", "")) if i < len(amounts) else 0.0
            except (ValueError, TypeError):
                amt = 0.0

            if not is_draft and amt > 20000 and cat_val_int != 6:
                flash("เงินสดย่อยจ่ายได้ครั้งละไม่เกินสองหมื่นบาท", "danger")
                return redirect(request.referrer or url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id or None))

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
            projected_total = fund_totals["cumulative_total"] + total_claim_amount
            if _is_over_limit(projected_total, fund_totals["request_amount"]):
                flash(
                    (
                        "ยอดรวมใบเบิกเงินสดย่อยและส่งคืนพัสดุจะเป็น "
                        f"{_format_currency_amount(projected_total)} บาท "
                        f"ซึ่งเกินยอดขอเบิก {_format_currency_amount(fund_totals['request_amount'])} บาท"
                    ),
                    "danger",
                )
                return redirect(request.referrer or url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request_id or None))

        if existing_draft:
            if fund_request_id is not None and existing_draft.fund_request_id != fund_request_id:
                existing_draft.fund_request_id = fund_request_id
            old_items = db.session.query(PettyCashClaimItem).filter_by(claim_id=existing_draft.id).all()
            for oi in old_items:
                db.session.query(PettyCashClaimProofFile).filter_by(claim_item_id=oi.id).delete()
            db.session.query(PettyCashClaimItem).filter_by(claim_id=existing_draft.id).delete()
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

        legacy_uploaded_files = request.files.getlist("proof_file[]")
        legacy_existing_file_paths = request.form.getlist("existing_proof_files[]")
        legacy_existing_file_names = request.form.getlist("existing_proof_filenames[]")

        claim_detail.status = "ฉบับร่าง" if is_draft else "รอตรวจสอบ"
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

            uploaded_files = request.files.getlist(f"proof_files_{i}[]")
            if not uploaded_files and i < len(legacy_uploaded_files):
                uploaded_files = [legacy_uploaded_files[i]]

            for file_storage in uploaded_files:
                if not file_storage or not file_storage.filename:
                    continue
                _, ext = os.path.splitext(file_storage.filename)
                clean_desc = re.sub(r'[^\u0e00-\u0e7fa-zA-Z0-9\s_-]', '', item.description or "receipt").strip().replace(" ", "_")
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                new_filename = f"petty_{clean_desc or 'receipt'}_{timestamp_str}{ext}"

                upload_folder = os.path.join(_upload_root(), f"petty_cash/{user_id}")
                os.makedirs(upload_folder, exist_ok=True)
                proof_path = f"uploads/petty_cash/{user_id}/{new_filename}"
                file_storage.save(os.path.join(upload_folder, new_filename))

                proof_file_record = PettyCashClaimProofFile(
                    claim_id=claim_detail.id,
                    claim_item_id=item.id,
                    proof_reference=proof_path,
                    filename=new_filename,
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

        return redirect(url_for("advance_payment.staff_fund_request_history"))

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
    )


@bp.route("/staff/petty-cash/parcel-returns/<int:parcel_return_id>/edit", methods=["POST"], endpoint="staff_parcel_return_edit")
@login_required(role=PETTY_CASH_SYSTEM)
def staff_parcel_return_edit(parcel_return_id):
    parcel_return = db.session.query(ParcelReturnDetail).get(parcel_return_id)
    if not parcel_return:
        abort(404)

    current_user = db.session.query(StaffAccount).get(session.get("user_id"))
    if not current_user or _selected_system() != PETTY_CASH_SYSTEM:
        abort(403)

    fund_request = _get_fund_request_by_id(getattr(parcel_return, "fund_request_id", None))
    if not fund_request:
        flash("ไม่พบคำขอที่เกี่ยวข้องกับรายการนี้", "warning")
        return redirect(request.referrer or url_for("advance_payment.staff_fund_request_history"))

    if not _is_current_secretary() and fund_request.requester_id != current_user.id:
        abort(403)

    current_status = (parcel_return.status or "").strip()
    if current_status not in {"รอตรวจสอบ", "ปฏิเสธ"}:
        flash("สามารถแก้ไขรายการส่งคืนพัสดุได้เฉพาะก่อนฝ่ายการเงินตรวจสอบ หรือหลังถูกปฏิเสธเท่านั้น", "warning")
        return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request.id))

    amount = request.form.get("amount", "0").replace(",", "")
    items_description = request.form.get("items_description", "").strip()
    sent_date_str = request.form.get("sent_date")

    if not items_description or not sent_date_str:
        flash("กรุณากรอกรายละเอียดรายการและวันที่ส่งให้ครบถ้วน", "danger")
        return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request.id))

    try:
        parsed_amount = float(amount or 0)
    except (TypeError, ValueError):
        flash("กรุณาระบุจำนวนเงินให้ถูกต้อง", "danger")
        return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request.id))

    ticket_id = getattr(fund_request, "borrowing_ticket_id", None)
    if ticket_id:
        ticket_totals = _calculate_ticket_return_totals_with_parcel(ticket_id, exclude_parcel_return_id=parcel_return.id)
        projected_ticket_total = ticket_totals["cumulative_total"] + parsed_amount
        if _is_over_limit(projected_ticket_total, ticket_totals["budget"]):
            flash(
                (
                    "ยอดรวมเอกสารส่งใช้เงินยืมและส่งคืนพัสดุจะเป็น "
                    f"{_format_currency_amount(projected_ticket_total)} บาท "
                    f"ซึ่งเกินวงเงิน {_format_currency_amount(ticket_totals['budget'])} บาท"
                ),
                "danger",
            )
            return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request.id))

    fund_totals = _calculate_fund_request_totals(fund_request.id, exclude_parcel_return_id=parcel_return.id)
    projected_fund_total = fund_totals["cumulative_total"] + parsed_amount
    if _is_over_limit(projected_fund_total, fund_totals["request_amount"]):
        flash(
            (
                "ยอดรวมใบเบิกเงินสดย่อยและส่งคืนพัสดุจะเป็น "
                f"{_format_currency_amount(projected_fund_total)} บาท "
                f"ซึ่งเกินยอดขอเบิก {_format_currency_amount(fund_totals['request_amount'])} บาท"
            ),
            "danger",
        )
        return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request.id))

    parcel_return.amount_spent = parsed_amount
    parcel_return.items_description = items_description
    parcel_return.sent_date = datetime.strptime(sent_date_str, "%Y-%m-%d").date()
    parcel_return.status = "รอตรวจสอบ"
    db.session.commit()
    _send_notification_email(parcel_return, object_type="parcel_return")

    flash("แก้ไขรายการส่งคืนพัสดุเรียบร้อยแล้ว", "success")
    return redirect(url_for("advance_payment.submit_petty_cash_claim", fund_request_id=fund_request.id))

@bp.route("/finance/petty-claims/<int:claim_id>/detail", methods=["GET"])
@login_required()
def petty_cash_claim_detail(claim_id):
    current_user = db.session.query(StaffAccount).get(session.get("user_id"))
    claim_detail = db.session.query(PettyCashClaimDetail).get(claim_id)
    if not claim_detail:
        abort(404)
    _attach_petty_cash_claim_context(claim_detail)
    borrowing_ticket = None
    if getattr(claim_detail, "fund_request", None):
        borrowing_ticket = getattr(claim_detail.fund_request, "borrowing_ticket", None)
    if borrowing_ticket is None and getattr(claim_detail, "fund_request", None):
        borrowing_ticket = _get_borrowing_ticket_by_id(getattr(claim_detail.fund_request, "borrowing_ticket_id", None))

    if current_user and _selected_system() == PETTY_CASH_SYSTEM and not _is_current_secretary() and claim_detail.user_id != current_user.id:
        abort(403)
        
    return render_template(
        "petty_cash_claim_detail.html", # หรือชื่อไฟล์ HTML template ที่คุณใช้อยู่
        claim_detail=claim_detail,
        borrowing_ticket=borrowing_ticket
    )

# 1. เปลี่ยนสถานะเป็น "กำลังตรวจสอบ"
@bp.route("/finance/petty-claims/<int:claim_id>/checking", methods=["POST"])
@login_required(role="finance")
def mark_petty_claim_checking(claim_id):
    claim = db.session.query(PettyCashClaimDetail).get(claim_id)
    if not claim:
        abort(404)
    
    claim.status = "กำลังตรวจสอบ"
    db.session.commit()
    _send_notification_email(claim, object_type="petty_claim")
    flash("เปลี่ยนสถานะเป็น 'กำลังตรวจสอบ' เรียบร้อยแล้ว", "success")
    return redirect(request.referrer or url_for("advance_payment.petty_cash_settings"))

# 2. ยืนยันการตรวจสอบ (ผ่านการตรวจสอบ)
@bp.route("/finance/petty-claims/<int:claim_id>/proofed", methods=["POST"])
@login_required(role="finance")
def mark_petty_claim_proofed(claim_id):
    claim = db.session.query(PettyCashClaimDetail).get(claim_id)
    if not claim:
        abort(404)

    claim.status = "ผ่านการตรวจสอบ"
    db.session.commit()
    flash("ทำเครื่องหมายรายการเงินสดย่อยเป็น 'ผ่านการตรวจสอบ' เรียบร้อยแล้ว", "success")
    return redirect(request.referrer or url_for("advance_payment.petty_cash_settings"))


# 3. โอนเงินสดย่อยสำเร็จ (โอนเงินสดย่อยสำเร็จ / transferred + บันทึกวันที่)
@bp.route("/finance/petty-claims/<int:claim_id>/transfer", methods=["POST"])
@login_required(role="finance")
def mark_petty_claim_transferred(claim_id):
    claim = db.session.query(PettyCashClaimDetail).get(claim_id)
    if not claim:
        abort(404)
        
    transferred_date_str = request.form.get("transferred_at")
    if not transferred_date_str:
        flash("กรุณาระบุวันที่หน่วยงานได้รับเงิน/วันที่โอนเงิน", "danger")
        return redirect(request.referrer or url_for("advance_payment.petty_cash_settings"))

    claim.status = "โอนเงินสดย่อยสำเร็จ"
    claim.transferred_at = datetime.strptime(transferred_date_str, "%Y-%m-%d").date()
    fund_req = db.session.query(FundRequest).get(claim.fund_request_id)
    if fund_req:
        fund_req.status = "เบิกเงินสำเร็จ"
    
    db.session.commit()
    _send_notification_email(claim, object_type="petty_claim")
    flash("เปลี่ยนสถานะเป็น 'โอนเงินสดย่อยสำเร็จ' และบันทึกวันที่เรียบร้อยแล้ว", "success")
    return redirect(request.referrer or url_for("advance_payment.petty_cash_settings"))


# 4. เปลี่ยนสถานะเป็น ได้รับเงินแล้ว/ล้างลูกหนี้เสร็จสมบูรณ์
@bp.route("/finance/petty-claims/<int:claim_id>/received", methods=["POST"])
@login_required(role="finance")
def mark_petty_claim_received(claim_id):
    claim = db.session.query(PettyCashClaimDetail).get(claim_id)
    if not claim:
        abort(404)
        
    claim.status = "เสร็จสิ้นกระบวนการ"
    db.session.commit()
    _send_notification_email(claim, object_type="petty_claim")
    flash("เปลี่ยนสถานะเป็น 'ได้รับเงินแล้ว' สิ้นสุดกระบวนการเรียบร้อย", "success")
    return redirect(request.referrer or url_for("advance_payment.petty_cash_settings"))


# 5. ปฏิเสธรายการเบิกเงินสดย่อย
@bp.route("/finance/petty-claims/<int:claim_id>/reject", methods=["POST"])
@login_required(role="finance")
def reject_petty_claim(claim_id):
    claim = db.session.query(PettyCashClaimDetail).get(claim_id)
    if not claim:
        abort(404)

    rejection_comment = request.form.get("rejection_comment", "").strip()
    if rejection_comment:
        existing = claim.rejection_comment or ""
        count = existing.count("ครั้งที่") + 1
        current_user = db.session.query(StaffAccount).get(session.get("user_id"))
        user_name = current_user.name if current_user else "ไม่ระบุชื่อ"
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
    return redirect(request.referrer or url_for("advance_payment.petty_cash_settings"))

@bp.route("/staff/petty-cash-ledger", methods=["GET"])
@login_required(role=SECRETARY_ROLE)
def petty_cash_ledger():
    user_id = session.get("user_id")
    current_user = db.session.query(StaffAccount).get(user_id)
    current_setting = _resolve_petty_cash_setting(current_user)
    selected_month = (request.args.get("month") or "").strip()
    today = datetime.now().date()
    default_month = today.replace(day=1)

    try:
        selected_month_start = datetime.strptime(f"{selected_month}-01", "%Y-%m-%d").date()
    except ValueError:
        selected_month_start = default_month
        selected_month = default_month.strftime("%Y-%m")

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
    department_name = current_setting.department_name if current_setting else None

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
    if department_name:
        approved_fund_requests = (
            db.session.query(FundRequest)
            .filter(
                FundRequest.department_name == department_name,
                ~FundRequest.status.in_(["กำลังดำเนินการ", "ปฏิเสธ"]),
            )
            .all()
        )

    for fr in approved_fund_requests:
        amt = float(fr.amount or 0)
        ticket_label = f"(ก.ศ.{fr.ticket_number or '-'})"

        if str(fr.form_type) == "31":
            fund_in_date = _coerce_date(fr.fund_in_date)
            withdrawal_date = _coerce_date(fr.withdrawal_date)
            created_at = fr.created_at or datetime.now()
            submitted_date = created_at.date()

            if fund_in_date:
                _append_ledger_row(
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
                    receipt_date=withdrawal_date,
                    created_at=created_at + timedelta(microseconds=1),
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
            receipt_date=fr.request_date or fr.created_at.date(),
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

    account_number = (current_setting.account_number or "").strip() if current_setting else ""
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
                created_at=approved_at or ticket.created_at,
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
                    description=f"{item.description} (ก.ศ. " + (claim.fund_request.ticket_number if claim.fund_request else "-") + ")",
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
        _attach_petty_cash_claim_context(claim)
        if claim.documents:
            doc_no = ", ".join([doc.title for doc in claim.documents if doc.title])
        else:
            doc_no = claim.closing_document.document_number if claim.closing_document else "-"

        # ยอดรับเงินคืนเข้าบัญชีธนาคาร (คำนวณจากหมวด 1-5)
        claim_total = float(claim.total_amount or sum(float(i.amount or 0) for i in claim.items if str(i.category_type) != "6"))
        
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
            description="คณะคืนเงินสดย่อย (ก.ศ. " + (claim.fund_request.ticket_number if claim.fund_request else "-") + ")",
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

    opening_row_description = "งบประมาณตั้งต้น" if not has_prior_transactions else "ยกยอดมา"
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

    return render_template(
        "petty_cash_ledger.html",
        initial_budget=initial_budget,
        opening_balance=opening_balance,
        ledger_items=ledger_items,
        selected_month=selected_month,
        selected_month_start=selected_month_start,
        selected_month_end=next_month_start,
    )
