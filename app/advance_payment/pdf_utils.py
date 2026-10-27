import base64
import html
import os
import re
from calendar import monthrange
from decimal import Decimal
from io import BytesIO
from datetime import datetime
from pathlib import Path
from bahttext import bahttext
from numpy.distutils.fcompiler import none

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Circle
from wcwidth import center

from .models import (
    db,
    BankAccountInfo,
    StaffAccount,
    PettyCashSetting,
    ParcelReturnDetail,
)
from .views import (
    FUND_REQUEST_FORM_BORROWING_TICKET,
    FUND_REQUEST_FORM_INTEREST,
    FUND_REQUEST_FORM_PETTY_CASH,
)
from app.models import Org
from app.staff.models import StaffHeadPosition, StaffLeaveApprover, StaffPersonalInfo


# Non-breaking spaces keep a writable gap in ReportLab paragraphs.
# Unicode whitespace also remains empty under strip() in data checks.
PDF_BLANK = "\u00a0" * 24

INTEREST_PERIOD_MONTH_LABELS = {
    "06": "มิถุนายน",
    "12": "ธันวาคม",
}


def _format_interest_period_label(period_value):
    normalized = (period_value or "").strip()
    if not normalized:
        return PDF_BLANK

    short_match = re.fullmatch(r"(\d{2})/(\d{4})", normalized)
    if short_match:
        month_code, year_be = short_match.groups()
        month_name = INTEREST_PERIOD_MONTH_LABELS.get(month_code)
        if month_name:
            return f"{month_name} พ.ศ. {year_be}"

    long_match = re.search(r"(มิถุนายน|ธันวาคม)\s*พ\.?ศ\.?\s*(\d{4})", normalized)
    if long_match:
        month_name, year_be = long_match.groups()
        return f"{month_name} พ.ศ. {year_be}"

    return normalized


# =========================================================================
# 1. GLOBAL FONT REGISTRATION & STYLES SETUP
# =========================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE_DIR, 'fonts')
APP_STATIC_DIR = Path(BASE_DIR).parent / "static"
PDF_REGULAR_FONT_PATH = APP_STATIC_DIR / "fonts" / "THSarabunNew.ttf"
PDF_BOLD_FONT_PATH = APP_STATIC_DIR / "fonts" / "THSarabunNewBold.ttf"
PDF_CHECKBOX_FONT_PATH = Path(FONTS_DIR) / "DejaVuSans.ttf"
PDF_LOGO_PATH = Path(BASE_DIR) / "static" / "logo-MU_black-white-2-1.png"

R_PATH = os.path.join(FONTS_DIR, 'THSarabun.ttf')
B_PATH = os.path.join(FONTS_DIR, 'THSarabun Bold.ttf')
I_PATH = os.path.join(FONTS_DIR, 'THSarabun Italic.ttf')
BI_PATH = os.path.join(FONTS_DIR, 'THSarabun BoldItalic.ttf')

DEJAVU_PATH = str(PDF_CHECKBOX_FONT_PATH)
if os.path.exists(DEJAVU_PATH):
    pdfmetrics.registerFont(TTFont('DejaVuSans', DEJAVU_PATH))

pdfmetrics.registerFont(TTFont('Sarabun', R_PATH))
pdfmetrics.registerFont(TTFont('SarabunBold', B_PATH if os.path.exists(B_PATH) else R_PATH))
pdfmetrics.registerFont(TTFont('SarabunItalic', I_PATH if os.path.exists(I_PATH) else R_PATH))
pdfmetrics.registerFont(TTFont('SarabunBoldItalic', BI_PATH if os.path.exists(BI_PATH) else R_PATH))

# Global Styles Configuration (Standard Font Size = 16)
DEFAULT_FONT_SIZE = 16
DEFAULT_LEADING = 20

styles = getSampleStyleSheet()

# สไตล์มาตรฐาน (Font Size 16)
styles.add(ParagraphStyle(name='ThaiNormal', fontName='Sarabun', fontSize=DEFAULT_FONT_SIZE, leading=DEFAULT_LEADING, alignment=TA_LEFT))
styles.add(ParagraphStyle(name='ThaiBold', fontName='SarabunBold', fontSize=DEFAULT_FONT_SIZE, leading=DEFAULT_LEADING, alignment=TA_LEFT))
styles.add(ParagraphStyle(name='ThaiCenter', fontName='Sarabun', fontSize=DEFAULT_FONT_SIZE, leading=DEFAULT_LEADING, alignment=TA_CENTER))
styles.add(ParagraphStyle(name='ThaiCenterBold', fontName='SarabunBold', fontSize=DEFAULT_FONT_SIZE, leading=DEFAULT_LEADING, alignment=TA_CENTER))
styles.add(ParagraphStyle(name='ThaiRight', fontName='Sarabun', fontSize=DEFAULT_FONT_SIZE, leading=DEFAULT_LEADING, alignment=TA_RIGHT))
styles.add(ParagraphStyle(name='ThaiRightBold', fontName='SarabunBold', fontSize=DEFAULT_FONT_SIZE, leading=DEFAULT_LEADING, alignment=TA_RIGHT))
styles.add(ParagraphStyle(name='ThaiJustify', fontName='Sarabun', fontSize=DEFAULT_FONT_SIZE, leading=DEFAULT_LEADING, alignment=TA_JUSTIFY, wordWrap='CJK'))

# สไตล์เฉพาะกรณี (เช่น ข้อความเชิงอรรถ/ตัวอักษรขนาดเล็ก)
styles.add(ParagraphStyle(name='ThaiSmallRight', fontName='Sarabun', fontSize=13, leading=16, alignment=TA_RIGHT))
styles.add(ParagraphStyle(name='ThaiFooter', fontName='Sarabun', fontSize=11, leading=14, alignment=TA_CENTER))

# เพิ่มสไตล์ย่อหน้าหนังสือราชการ (ย่อหน้า 2.5 ซม.)
styles.add(ParagraphStyle(
    name='ThaiOfficial',
    fontName='Sarabun',
    fontSize=DEFAULT_FONT_SIZE,
    leading=DEFAULT_LEADING,
    alignment=TA_JUSTIFY,
    # Do not use ReportLab's CJK line-break mode here.  In that mode the
    # paragraph is split into character-based lines and many lines are
    # marked as hard breaks, so TA_JUSTIFY cannot distribute word spacing.
    # The official memo text contains normal Thai word spaces, allowing the
    # default word wrapper to justify each non-final line correctly.
    firstLineIndent=70  # ปรับระยะย่อหน้าให้เท่ากันทุกพารากราฟที่นี่
))
# =========================================================================
# 2. HELPER FUNCTIONS
# =========================================================================
def _pdf_text(value):
    """Leave room to handwrite missing data while preserving real values such as zero."""
    if value is None:
        return PDF_BLANK
    text = str(value)
    if not text.strip() or re.fullmatch(r"[.\s]+", text) or text.strip().startswith("ไม่พบข้อมูล"):
        return PDF_BLANK
    return text


def _pdf_amount(value):
    if not _pdf_text(value).strip():
        return PDF_BLANK
    amount = Decimal(str(value))
    return "-" if amount == 0 else f"{amount:,.2f}"


def _pdf_count(value):
    if not _pdf_text(value).strip():
        return PDF_BLANK
    return "-" if Decimal(str(value)) == 0 else str(value)


def get_department_info_from_api(dept_name):
    """ ดึงข้อมูลจาก Service โดยใช้ชื่อหน่วยงาน (dept_name) เป็น Key """
    from .views import get_department_data_service

    dept_data = get_department_data_service(dept_name) if str(dept_name or "").strip() else None
    
    if dept_data:
        controller_info = dept_data.get("account_controller") or {}
        if not _pdf_text(controller_info.get("name")).strip():
            controller_info = {}

        return {
            "head": PDF_BLANK,
            "head_position": PDF_BLANK,
            "custodian": _pdf_text(controller_info.get("name")),
            "position": _pdf_text(controller_info.get("position"))
        }
    
    # Leave missing department fields blank.
    return {
        "head": PDF_BLANK,
        "head_position": PDF_BLANK,
        "custodian": PDF_BLANK,
        "position": PDF_BLANK
    }

def get_thai_month_year(date_obj):
    if not date_obj:
        return PDF_BLANK
    th_months = [
        "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
        "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
    ]
    return f"{date_obj.day} {th_months[date_obj.month - 1]} {date_obj.year + 543}"


def _format_fiscal_year_for_pdf(value):
    """Format stored fiscal-year values as the Buddhist year used in PDFs."""
    if value is None or str(value).strip() == "":
        return PDF_BLANK
    try:
        fiscal_year = int(value)
    except (TypeError, ValueError):
        return str(value)
    return str(fiscal_year + 543 if fiscal_year < 2400 else fiscal_year)

def draw_dotted_line():
    return Paragraph("....................................................................................................................................................", styles['ThaiCenter'])


def _build_global_header(
    department_name,
    telephone_number,
    paragraph_style,
    *,
    logo_size=78,
    leave_style=False,
):
    """Build the shared university letterhead.

    ``leave_style`` reproduces the five-column arrangement used by the
    leave_record_info PDF.  It is opt-in so existing PDFs using the original
    three-column header keep their current layout.
    """
    if PDF_LOGO_PATH.is_file():
        logo = Image(str(PDF_LOGO_PATH), width=logo_size, height=logo_size)
        logo.hAlign = "CENTER"
    else:
        logo = Drawing(logo_size, logo_size)
        radius = logo_size / 2 - 4
        logo.add(Circle(logo_size / 2, logo_size / 2, radius,
                        strokeColor=colors.black, strokeWidth=1,
                        fillColor=colors.white))

    header_right = Paragraph(
        f"<br/><br/>{department_name}<br/>"
        f"คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>"
        f"โทร.{telephone_number}",
        paragraph_style,
    )
    if leave_style:
        # Same column structure as leave_record_info:
        # [left spacer, spacer, logo, organization text, right spacer].
        header_table = Table(
            [["", "", logo, header_right, ""]],
            colWidths=[100, 92, 66, 212, 1],
        )
    else:
        header_table = Table(
            [["", logo, header_right]],
            # Keep the right-hand text in a dedicated column so it cannot
            # overlap the logo when a department name is long.
            colWidths=[170, 110, 165],
        )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    if leave_style:
        header_table.setStyle(TableStyle([
            ("ALIGN", (2, 0), (2, 0), "CENTER"),
        ]))
        header_table.hAlign = "LEFT"
    return header_table


def missing_department_notice():
    return PDF_BLANK


def _get_user_by_id(user_id):
    if not user_id:
        return None
    return db.session.query(StaffAccount).get(user_id)


def _thai_signature_name(staff):
    """Return a Thai signature name without the personal title."""
    personal_info = getattr(staff, "personal_info", None)
    if personal_info is None:
        return None
    name_parts = (
        getattr(personal_info, "th_firstname", None),
        getattr(personal_info, "th_lastname", None),
    )
    signature_name = " ".join(
        str(value).strip() for value in name_parts if value and str(value).strip()
    )
    return signature_name or None


def _get_head_signature(
    *,
    ticket=None,
    fund_request=None,
    claim=None,
    setting=None,
    staff_account_id=None,
):
    """Resolve the organization head and position for PDF signatures.

    ``StaffHeadPosition`` is organization-specific. Fund requests and
    petty-cash reports use their setting organization. Standalone claim/ticket
    documents use their requesting staff member's organization.
    """
    if fund_request is None and claim is not None:
        fund_request = getattr(claim, "fund_request", None)
    if ticket is None and fund_request is not None:
        ticket = getattr(fund_request, "borrowing_ticket", None)

    borrower_account_id = (
        getattr(ticket, "borrower_id", None)
        or getattr(fund_request, "requester_id", None)
        or getattr(claim, "user_id", None)
        or staff_account_id
    )

    borrower_account = _get_user_by_id(borrower_account_id)
    borrower_org = getattr(
        getattr(borrower_account, "personal_info", None), "org", None
    )

    # Fund-request approval authority and its displayed head must both come
    # from the petty-cash setting organization. Standalone ticket/report PDFs
    # continue to derive their organization from the requesting staff member.
    if setting is None and fund_request is not None:
        setting = getattr(fund_request, "petty_cash_setting", None)
        if setting is None and getattr(fund_request, "petty_cash_setting_id", None):
            setting = db.session.query(PettyCashSetting).get(
                fund_request.petty_cash_setting_id
            )

    org = getattr(setting, "org", None)
    if org is None and getattr(setting, "org_id", None):
        org = db.session.query(Org).get(setting.org_id)

    if setting is None:
        org = borrower_org

    candidate_org_ids = []
    org_id = getattr(org, "id", None)
    if org_id is not None:
        candidate_org_ids.append(org_id)

    for candidate_org_id in candidate_org_ids:
        candidate_org = (
            org if getattr(org, "id", None) == candidate_org_id
            else db.session.query(Org).get(candidate_org_id)
        )
        head_identifier = (getattr(candidate_org, "head", None) or "").strip()
        head_account = (
            db.session.query(StaffAccount)
            .filter(StaffAccount.email == head_identifier)
            .first()
            if head_identifier else None
        )

        head_position_query = db.session.query(StaffHeadPosition).filter(
            StaffHeadPosition.org_id == candidate_org_id
        )
        # Match the head account as well as org_id.  This prevents selecting
        # the other position when the same person heads multiple orgs.
        if head_account is not None:
            head_position_query = head_position_query.filter(
                StaffHeadPosition.staff_account_id == head_account.id
            )
        head_position_record = (
            head_position_query
            .order_by(StaffHeadPosition.id.desc())
            .first()
        )
        if head_position_record is None:
            continue

        head_account = getattr(head_position_record, "staff", None) or head_account
        head_personal_info = getattr(head_account, "personal_info", None)
        if head_personal_info is None and getattr(head_account, "personal_id", None):
            head_personal_info = (
                db.session.query(StaffPersonalInfo)
                .filter(StaffPersonalInfo.id == head_account.personal_id)
                .first()
            )
        if head_personal_info is None:
            continue

        head_name = " ".join(
            str(value).strip() for value in (
                getattr(head_personal_info, "th_title", None),
                getattr(head_personal_info, "th_firstname", None),
                getattr(head_personal_info, "th_lastname", None),
            ) if value and str(value).strip()
        )
        return _pdf_text(head_name), _pdf_text(head_position_record.position)

    # If the current organization has no head, walk up its parent hierarchy
    # until a head email is found. Keep a visited set to avoid malformed cycles.
    head_email = None
    current_org = org
    visited_org_ids = set()
    while current_org is not None:
        org_key = getattr(current_org, "id", None) or id(current_org)
        if org_key in visited_org_ids:
            break
        visited_org_ids.add(org_key)

        head_email = (getattr(current_org, "head", None) or "").strip()
        if head_email:
            break

        parent_id = getattr(current_org, "parent_id", None)
        current_org = (
            db.session.query(Org).get(parent_id)
            if parent_id
            else None
        )

    if not head_email:
        return _pdf_text(None), _pdf_text(None)

    head_account = (
        db.session.query(StaffAccount)
        .filter(StaffAccount.email == head_email)
        .first()
    )
    personal_id = getattr(head_account, "personal_id", None)
    if not personal_id:
        return _pdf_text(None), _pdf_text(None)

    head_personal_info = (
        db.session.query(StaffPersonalInfo)
        .filter(StaffPersonalInfo.id == personal_id)
        .first()
    )
    if not head_personal_info:
        return _pdf_text(None), _pdf_text(None)

    head_name = " ".join(
        str(value).strip() for value in (
            getattr(head_personal_info, "th_title", None),
            getattr(head_personal_info, "th_firstname", None),
            getattr(head_personal_info, "th_lastname", None),
        ) if value and str(value).strip()
    )
    # The position is organization-specific and must come from
    # staff_head_positions, never from the staff member's generic position.
    head_position_record = (
        db.session.query(StaffHeadPosition)
        .filter_by(org_id=getattr(current_org, "id", None), staff_account_id=head_account.id)
        .order_by(StaffHeadPosition.id.desc())
        .first()
        if getattr(current_org, "id", None) and head_account is not None
        else None
    )
    return _pdf_text(head_name), _pdf_text(getattr(head_position_record, "position", None))


def _get_leave_approver_signatures(ticket):
    """Return active lower/middle approvers, or one active fallback approver."""
    borrower_id = getattr(ticket, "borrower_id", None)
    if not borrower_id:
        return []

    def approver_signature(approver):
        approver_account = getattr(approver, "account", None)
        if approver_account is None:
            approver_account = _get_user_by_id(getattr(approver, "approver_account_id", None))
        if approver_account is None:
            return None

        personal_info = getattr(approver_account, "personal_info", None)
        signer_name = getattr(personal_info, "fullname", None)
        if not signer_name and personal_info is not None:
            signer_name = " ".join(
                value for value in (
                    getattr(personal_info, "th_firstname", None),
                    getattr(personal_info, "th_lastname", None),
                ) if value
            )

        position_record = (
            db.session.query(StaffHeadPosition)
            .filter_by(staff_account_id=approver_account.id)
            .first()
        )
        return (
            _pdf_text(signer_name),
            _pdf_text(getattr(position_record, "position", None)),
        )

    signatures = []
    approver_filters = (
        {"is_lower_level": True},
        {"is_middle_level": True},
    )
    for level_filter in approver_filters:
        approver = (
            db.session.query(StaffLeaveApprover)
            .filter_by(
                staff_account_id=borrower_id,
                is_active=True,
                **level_filter,
            )
            .first()
        )
        if approver is None:
            continue
        signature = approver_signature(approver)
        if signature is not None:
            signatures.append(signature)

    if not signatures:
        fallback_approver = (
            db.session.query(StaffLeaveApprover)
            .filter_by(
                staff_account_id=borrower_id,
                is_active=True,
            )
            .order_by(StaffLeaveApprover.id.asc())
            .first()
        )
        if fallback_approver is not None:
            fallback_signature = approver_signature(fallback_approver)
            if fallback_signature is not None:
                signatures.append(fallback_signature)

    return signatures


def _get_leave_approver_signature(ticket):
    """Resolve one FNAR02 signer, preferring lower over middle level."""
    signatures = _get_leave_approver_signatures(ticket)
    if signatures:
        return signatures[0]
    return _pdf_text(None), _pdf_text(None)


def _get_bank_account_info_for_ticket(ticket):
    if not ticket:
        return None

    cached_account = getattr(ticket, "bank_account_info", None)
    if cached_account is not None:
        return cached_account

    bank_account_info_id = getattr(ticket, "bank_account_info_id", None)
    if bank_account_info_id:
        record = db.session.query(BankAccountInfo).get(bank_account_info_id)
        if record is not None:
            return record

    account_number = (getattr(ticket, "account_number", "") or "").strip()
    if account_number:
        return db.session.query(BankAccountInfo).filter_by(account_number=account_number).first()

    return None


def _get_bank_account_info_for_account_number(account_number):
    normalized_account_number = (account_number or "").strip()
    if not normalized_account_number:
        return None

    return db.session.query(BankAccountInfo).filter_by(account_number=normalized_account_number).first()


def _get_bank_account_info_for_petty_cash_setting(setting):
    """Resolve the petty-cash account from the setting's FK and organization."""
    if not setting:
        return None

    bank_account_info_id = getattr(setting, "bank_account_info_id", None)
    if bank_account_info_id:
        account = db.session.query(BankAccountInfo).get(bank_account_info_id)
        if account:
            return account

    org_id = getattr(setting, "org_id", None)
    if org_id:
        return (
            db.session.query(BankAccountInfo)
            .filter_by(org_id=org_id, record_type="petty_cash")
            .order_by(BankAccountInfo.id.asc())
            .first()
        )
    return None


# =========================================================================
# 3. PDF GENERATION FUNCTIONS
# =========================================================================
def summarize_petty_cash_month(month_start, fund_requests, claims):
    """Summarize petty-cash documents requiring action.

    A submitted document is counted per claim, but only while the claim is in
    one of the three review statuses. Parcel-return documents in the
    ``รอตรวจสอบ``, ``พัสดุกำลังดำเนินการ``, or ``ได้รับเอกสารแล้ว`` statuses
    are submitted documents as well. The pending amount is the unsubmitted
    remainder of each petty-cash FundRequest after non-rejected linked
    documents are accounted for. Requests whose linked documents are all
    rejected therefore remain pending for their full requested amount.
    """
    # The report's selected month controls the ledger balance, but documents
    # requiring action must remain visible even when they were submitted in a
    # previous month.
    requests = list(fund_requests)
    request_ids = {fr.id for fr in requests}
    submitted_statuses = {"รอตรวจสอบ", "กำลังตรวจสอบ", "ผ่านการตรวจสอบ"}
    rejected_statuses = {"ปฏิเสธ", "ถูกปฏิเสธ"}
    non_accounted_claim_statuses = rejected_statuses | {"ฉบับร่าง", "ยกเลิก"}
    submitted_claims = [
        claim for claim in claims
        if claim.fund_request_id in request_ids
        and (claim.status or "").strip() in submitted_statuses
    ]
    parcel_returns = (
        db.session.query(ParcelReturnDetail)
        .filter(ParcelReturnDetail.fund_request_id.in_(request_ids))
        .all()
        if request_ids else []
    )
    submitted_parcel_returns = [
        parcel for parcel in parcel_returns
        if (parcel.status or "").strip() in {
            "รอตรวจสอบ",
            "พัสดุกำลังดำเนินการ",
            "ได้รับเอกสารแล้ว",
        }
    ]
    # Track the amount already represented by every non-rejected linked
    # document. This also handles partially submitted FundRequests: the
    # remaining amount must stay in the "ยังไม่ส่งเบิก" row.
    accounted_amount_by_request = {}
    for claim in claims:
        if claim.fund_request_id not in request_ids:
            continue
        if (claim.status or "").strip() in non_accounted_claim_statuses:
            continue
        accounted_amount_by_request.setdefault(claim.fund_request_id, Decimal("0.00"))
        accounted_amount_by_request[claim.fund_request_id] += sum(
            (Decimal(str(item.amount or 0)) for item in claim.items),
            Decimal("0.00"),
        )
    for parcel in parcel_returns:
        if parcel.fund_request_id is None:
            continue
        if (parcel.status or "").strip() in rejected_statuses | {"ฉบับร่าง"}:
            continue
        accounted_amount_by_request.setdefault(parcel.fund_request_id, Decimal("0.00"))
        accounted_amount_by_request[parcel.fund_request_id] += Decimal(str(parcel.amount_spent or 0))

    pending = []
    pending_amount = Decimal("0.00")
    for fr in requests:
        if fr.form_type != FUND_REQUEST_FORM_PETTY_CASH or not fr.request_date:
            continue
        remaining = max(
            Decimal(str(fr.amount or 0))
            - accounted_amount_by_request.get(fr.id, Decimal("0.00")),
            Decimal("0.00"),
        )
        if remaining <= 0:
            continue
        pending.append(fr)
        pending_amount += remaining
    submitted_amount = sum(
        (Decimal(str(item.amount or 0))
         for claim in submitted_claims
         for item in claim.items
         if str(item.category_type) != "6"
         and item.receipt_date),
        Decimal("0.00"),
    )
    submitted_parcel_amount = sum(
        (Decimal(str(parcel.amount_spent or 0)) for parcel in submitted_parcel_returns),
        Decimal("0.00"),
    )
    return {
        "submitted_count": len(submitted_claims) + len(submitted_parcel_returns),
        "submitted_amount": submitted_amount,
        "submitted_parcel_amount": submitted_parcel_amount,
        "pending_count": len(pending),
        "pending_amount": pending_amount,
    }


def generate_petty_cash_monthly_report_pdf(*, setting, month_start, remaining_budget,
                                          summary, telephone_number=""):
    """Create the MT-Petty Cash-004 monthly status letter as PDF bytes."""
    from reportlab.platypus import Image

    department_name = setting.department_name or missing_department_notice()
    department = str(department_name)
    head_name, head_position = _get_head_signature(setting=setting)
    telephone = str(telephone_number or PDF_BLANK)
    last_day = month_start.replace(day=monthrange(month_start.year, month_start.month)[1])
    month_label = get_thai_month_year(month_start).split(" ", 1)[1]
    last_day_label = get_thai_month_year(last_day)
    budget = setting.budget
    balance = Decimal(str(remaining_budget)).quantize(Decimal("0.01")) if remaining_budget is not None else None
    submitted_values = (
        summary.get("submitted_amount"),
        summary.get("submitted_parcel_amount"),
    )
    submitted = (
        sum(Decimal(str(value or 0)) for value in submitted_values)
        if any(value is not None for value in submitted_values)
        else None
    )
    pending = summary.get("pending_amount")
    total = (sum(Decimal(str(value)) for value in (balance, submitted, pending))
             if all(value is not None for value in (balance, submitted, pending)) else None)
    normal = ParagraphStyle("MonthlyNormal", parent=styles["ThaiNormal"], fontSize=14, leading=18, wordWrap="CJK")
    right = ParagraphStyle("MonthlyRight", parent=normal, alignment=TA_RIGHT)
    center = ParagraphStyle("MonthlyCenter", parent=normal, alignment=TA_CENTER)
    official = ParagraphStyle("MonthlyOfficial", parent=normal, firstLineIndent=48)
    p = lambda text, style=normal: Paragraph(text, style)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=68, rightMargin=50,
                            topMargin=36, bottomMargin=40,
                            title=f"รายงานสถานะเงินสดย่อย ประจำเดือน{month_label}")
    story = [p("MT-Petty Cash-004", right)]
    if PDF_LOGO_PATH.is_file():
        logo = Image(str(PDF_LOGO_PATH), width=70, height=70)
        logo.hAlign = "CENTER"
        story.append(logo)
    story.extend([
        p(f"{department}<br/>คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>โทร.{telephone}", right),
        Spacer(1, 24), p("ที่"), p("วันที่"),
        p(f"เรื่อง รายงานสถานะเงินสดย่อยของ{department} ประจำเดือน{month_label}"),
        Spacer(1, 8), p("เรียน คณบดีคณะเทคนิคการแพทย์"), Spacer(1, 8),
    ])
    attachments = Table([[p("สิ่งที่ส่งมาด้วย"), p(
        f"1. ทะเบียนคุมเงินสดย่อย ณ วันที่ {last_day_label}<br/>"
        "2. สำเนาใบยืมเงินสดย่อย/ใบเบิกเงินสดย่อย<br/>"
        "3. สำเนาสมุดเงินฝากออมทรัพย์ 1 เล่ม")]], colWidths=[78, doc.width - 78])
    attachments.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.extend([attachments, Spacer(1, 16), p(
        f"ตามที่ {department} ได้รับจัดสรรเงินสดย่อยจากเงินทดรองจ่ายของคณะฯ "
        f"ประจำปีงบประมาณ {_format_fiscal_year_for_pdf(setting.fiscal_year)} "
        f"เป็นจำนวนเงิน {_pdf_amount(budget)} บาท ({bahttext(budget) if budget is not None else PDF_BLANK}) "
        f"{department} ขอรายงานสถานะเงินสดย่อย ณ วันที่ {last_day_label} ดังนี้", official),
        Spacer(1, 4)])
    rows = [
        [p("ลำดับที่", center), p("รายการ", center), p("จำนวนเงิน", center)],
        [p("1", center), p("เงินฝากอยู่ในบัญชีเงินฝากออมทรัพย์ 1 เล่ม"), p(f"{_pdf_amount(balance)}", right)],
        [p("2", center), p(f'เอกสารเบิกจ่ายที่ส่งเบิกมาแล้ว รวม {_pdf_count(summary.get("submitted_count"))} ฉบับ'), p(f"{_pdf_amount(submitted)}", right)],
        [p("3", center), p(f'เอกสารเบิกจ่ายที่ยังไม่ส่งเบิก รวม {_pdf_count(summary.get("pending_count"))} ฉบับ'), p(f"{_pdf_amount(pending)}", right)],
        ["", p(f"ตัวอักษร ({bahttext(total) if total is not None else PDF_BLANK}) <b>รวมทั้งสิ้น</b>", right), p(f"<b>{_pdf_amount(total)}</b>", right)],
    ]
    table = Table(rows, colWidths=[44, doc.width - 156, 112])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TOPPADDING", (0, 0), (-1, -1), 3),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story.extend([table, p("จึงเรียนมาเพื่อโปรดทราบ", official), Spacer(1, 40)])
    signature = Table([["", p(f"({head_name})<br/>{head_position}", center)]],
                      colWidths=[doc.width * 0.45, doc.width * 0.55])
    story.append(signature)
    doc.build(story)
    return buffer.getvalue()


def _build_fnar02_context(ticket):
    """Collect the values shared by both Chromium-rendered FNAR02 pages."""
    borrower_name = getattr(ticket, "borrower_name", None) or PDF_BLANK
    borrower_user = (
        getattr(ticket, "borrower_user", None)
        or _get_user_by_id(getattr(ticket, "borrower_id", None))
    )
    borrower_org = getattr(
        getattr(borrower_user, "personal_info", None),
        "org",
        None,
    )
    department_name = (
        getattr(borrower_org, "name", None)
        or getattr(borrower_user, "department", None)
        or getattr(ticket, "borrower_department", None)
        or PDF_BLANK
    )
    header_org = getattr(borrower_org, "parent", None) or borrower_org
    header_department_name = (
        getattr(header_org, "name", None)
        or department_name
    )

    due_date = getattr(ticket, "due_date", None)
    start_date = getattr(ticket, "borrowing_ticket_start_date", None)
    end_date = getattr(ticket, "borrowing_ticket_end_date", None)
    required_budget = getattr(ticket, "required_budget", None)

    bank_account_info = _get_bank_account_info_for_ticket(ticket)
    account_number = (getattr(ticket, "account_number", "") or "").strip() or (
        _pdf_text(bank_account_info.account_number)
        if bank_account_info
        else PDF_BLANK
    )
    account_name = (
        bank_account_info.thai_name
        if bank_account_info and bank_account_info.thai_name
        else PDF_BLANK
    )
    borrowing_purpose = (
        getattr(ticket, "borrowing_ticket_purpose", None)
        or PDF_BLANK
    )
    borrower_position = (
        getattr(borrower_user, "position", None)
        or getattr(ticket, "borrower_position", None)
        or PDF_BLANK
    )

    from .views import convert_to_fiscal_year, get_department_data_service

    telephone_number = _pdf_text(
        (get_department_data_service(department_name) or {}).get("telephone_number")
    )
    fiscal_year_date = (
        getattr(ticket, "request_date", None)
        or getattr(ticket, "approved_at", None)
        or getattr(ticket, "created_at", None)
    )
    fiscal_year_label = (
        convert_to_fiscal_year(fiscal_year_date) + 543
        if fiscal_year_date
        else PDF_BLANK
    )
    return {
        "borrower_name": borrower_name,
        "borrower_position": borrower_position,
        "department_name": department_name,
        "header_department_name": header_department_name,
        "leave_approver_signatures": _get_leave_approver_signatures(ticket),
        "due_date_thai": get_thai_month_year(due_date) if due_date else PDF_BLANK,
        "start_date_str": get_thai_month_year(start_date) if start_date else PDF_BLANK,
        "end_date_str": get_thai_month_year(end_date) if end_date else PDF_BLANK,
        "amount_numeric": _pdf_amount(required_budget),
        "amount_text": (
            bahttext(required_budget)
            if required_budget is not None
            else PDF_BLANK
        ),
        "account_number": account_number,
        "account_name": account_name,
        "borrowing_purpose": borrowing_purpose,
        "telephone_number": telephone_number,
        "fiscal_year_label": fiscal_year_label,
    }


def _pdf_asset_data_uri(path, mime_type):
    """Embed a local font or image so Chromium can render self-contained HTML."""
    asset_path = Path(path)
    if not asset_path.is_file():
        raise FileNotFoundError(f"PDF asset not found: {asset_path}")
    encoded = base64.b64encode(asset_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


PDF_REGULAR_FONT_DATA_URI = _pdf_asset_data_uri(PDF_REGULAR_FONT_PATH, "font/ttf")
PDF_BOLD_FONT_DATA_URI = _pdf_asset_data_uri(PDF_BOLD_FONT_PATH, "font/ttf")
PDF_CHECKBOX_FONT_DATA_URI = _pdf_asset_data_uri(PDF_CHECKBOX_FONT_PATH, "font/ttf")
PDF_LOGO_DATA_URI = _pdf_asset_data_uri(PDF_LOGO_PATH, "image/png")


def _build_fnar02_html(memo_context):
    """Build both FNAR02 pages as Thai print HTML for Chromium."""
    escaped = {
        key: html.escape(str(value), quote=True)
        for key, value in memo_context.items()
        if key != "leave_approver_signatures"
    }
    signature_blocks = []
    for signer_name, signer_position in memo_context["leave_approver_signatures"]:
        signature_blocks.append(
            '<div class="signature">'
            f"({html.escape(str(signer_name))})<br>"
            f"{html.escape(str(signer_position))}"
            "</div>"
        )
    signatures_html = "".join(signature_blocks)

    paragraph_one = (
        f"ด้วย{escaped['department_name']} มีความประสงค์จะขอยืมเงินทดรองจ่าย "
        f"จำนวนเงิน {escaped['amount_numeric']} บาท ({escaped['amount_text']}) "
        f"เพื่อทดรองจ่าย{escaped['borrowing_purpose']} ตั้งแต่วันที่ "
        f"{escaped['start_date_str']} - {escaped['end_date_str']}"
    )
    paragraph_two = (
        f"ทั้งนี้โดยมอบหมายให้ {escaped['borrower_name']} เป็นผู้ยืมเงิน "
        f"โดยโปรดโอนเงินเข้าบัญชี เลขที่ {escaped['account_number']} "
        f"ชื่อบัญชี {escaped['account_name']} โดยมีระยะเวลาในการดำเนินภายในวันที่ "
        f"{escaped['due_date_thai']}"
    )

    return f"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>บันทึกข้อความ - ขออนุมัติยืมเงินทดรองจ่าย</title>
<style>
  @font-face {{
    font-family: "TH Sarabun New";
    src: url("{PDF_REGULAR_FONT_DATA_URI}") format("truetype");
    font-style: normal;
    font-weight: 400;
  }}
  @font-face {{
    font-family: "TH Sarabun New";
    src: url("{PDF_BOLD_FONT_DATA_URI}") format("truetype");
    font-style: normal;
    font-weight: 700;
  }}
  @page {{ size: A4; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font-family: "TH Sarabun New", "TH Sarabun PSK", sans-serif;
    font-size: 16pt;
    line-height: 1.25;
    color: #000;
  }}
  .page {{
    min-height: 297mm;
    margin: 0 auto;
    break-after: page;
  }}
  .memo-page {{
    width: 200mm;
    padding: 12.7mm 14.82mm 7mm;
  }}
  .contract-page {{
    width: 190mm;
    padding: 14.8mm 0 5mm;
    break-after: auto;
  }}
  .memo-header {{ height: 37mm; position: relative; }}
  .logo {{
    position: absolute;
    top: 0;
    left: 50%;
    width: 25.75mm;
    height: 25.75mm;
    transform: translateX(-50%);
    object-fit: contain;
  }}
  .organization {{
    position: absolute;
    top: 7mm;
    right: 0;
    width: 77mm;
    text-align: right;
  }}
  .memo-info {{
    display: grid;
    grid-template-columns: 17mm 1fr;
    row-gap: .5mm;
  }}
  .memo-info strong {{ font-weight: 700; }}
  .memo-body {{ margin-top: 4mm; }}
  .government-text {{
    font-family: "TH Sarabun New", "TH Sarabun PSK", sans-serif;
    word-break: normal;
    line-break: strict;
    overflow-wrap: normal;
    text-align: justify;
    text-justify: inter-word;
    text-align-last: left;
    margin: 0 0 4.2mm;
    text-indent: 24.7mm;
  }}
  .signatures {{
    margin-left: 51%;
    padding-top: 10mm;
    text-align: center;
  }}
  .signature {{ break-inside: avoid; }}
  .signature + .signature {{ margin-top: 22mm; }}
  .contract-page {{
    font-size: 16pt;
    line-height: 1.15;
  }}
  .contract-table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }}
  .contract-table td {{
    border: .3mm solid #000;
    padding: 1.4mm 3.5mm;
    vertical-align: top;
  }}
  .contract-table tr {{ break-inside: avoid; }}
  .contract-center {{ text-align: center; }}
  .contract-title {{
    font-size: 17pt;
    font-weight: 700;
    margin-bottom: 7mm;
  }}
  .contract-section-title {{
    font-weight: 700;
    text-align: center;
    margin-bottom: 1mm;
  }}
  .contract-line {{ margin-bottom: .7mm; }}
  .contract-indent {{
    margin: 0;
    text-indent: 12mm;
    text-align: justify;
    text-justify: inter-word;
    text-align-last: left;
    word-break: normal;
    line-break: strict;
  }}
  .contract-header {{ height: 25mm; }}
  .contract-borrower {{ height: 31mm; }}
  .contract-amount {{ height: 10.5mm; }}
  .contract-agreement {{ height: 50mm; }}
  .contract-proposal {{ height: 46mm; }}
  .contract-approval {{ height: 45mm; }}
  .contract-receipt {{ height: 40.5mm; }}
  .signature-grid {{
    display: grid;
    grid-template-columns: minmax(0, 58fr) minmax(0, 42fr);
    column-gap: 4mm;
    align-items: start;
    margin-top: 8mm;
  }}
  .signature-block {{
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    column-gap: 0;
    align-items: end;
    padding-right: 11mm;
  }}
  .signature-line {{
    display: contents;
  }}
  .signature-rule {{
    height: .9em;
    overflow: hidden;
    white-space: nowrap;
    line-height: .75em;
  }}
  .signature-rule::after {{
    content: "..................................................................................................................................";
    letter-spacing: .25mm;
  }}
  .signature-name,
  .signature-position {{
    grid-column: 2;
    text-align: center;
    line-height: 1.1;
  }}
  .date-line {{
    display: grid;
    grid-template-columns: auto 1fr;
    column-gap: 1mm;
    align-items: end;
    align-self: start;
  }}
  .contract-footer {{
    margin-top: 1mm;
    font-size: 11pt;
    line-height: 1;
    text-align: center;
  }}
</style>
</head>
<body>
<main class="page memo-page">
  <header class="memo-header">
    <img class="logo" src="{PDF_LOGO_DATA_URI}" alt="ตรามหาวิทยาลัยมหิดล">
    <div class="organization">
      <br>{escaped['header_department_name']}<br>
      คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br>
      โทร.{escaped['telephone_number']}
    </div>
  </header>
  <section class="memo-info">
    <span>ที่</span><span>&nbsp;</span>
    <span>วันที่</span><span>&nbsp;</span>
    <span>เรื่อง</span><span>ขออนุมัติยืมเงินทดรองจ่าย</span>
    <span>เรียน</span><span>คณบดีคณะเทคนิคการแพทย์</span>
  </section>
  <section class="memo-body">
    <p class="government-text">{paragraph_one}</p>
    <p class="government-text">{paragraph_two}</p>
    <p class="government-text">จึงเรียนมาเพื่อโปรดพิจารณาอนุมัติ และลงนามในสัญญาการยืมเงินที่แนบมาพร้อมนี้<br>ด้วยจักเป็นพระคุณยิ่ง</p>
  </section>
  <section class="signatures">{signatures_html}</section>
</main>
<main class="page contract-page">
  <table class="contract-table">
    <colgroup>
      <col style="width: 50%">
      <col style="width: 50%">
    </colgroup>
    <tr class="contract-header">
      <td class="contract-center">
        <div class="contract-title">สัญญาการยืมเงิน</div>
        <div>ยื่นต่อ คณบดีคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล</div>
      </td>
      <td class="contract-center">
        <div class="contract-line">เลขที่.................................../{escaped['fiscal_year_label']}</div>
        <div class="contract-section-title">วันครบกำหนด</div>
        <div>{escaped['due_date_thai']}</div>
      </td>
    </tr>
    <tr class="contract-borrower">
      <td colspan="2">
        <div class="contract-line">ข้าพเจ้า&nbsp;&nbsp;{escaped['borrower_name']}&nbsp;&nbsp;ตำแหน่ง&nbsp;&nbsp;{escaped['borrower_position']}</div>
        <div class="contract-line">สังกัด&nbsp;&nbsp;{escaped['department_name']} มหาวิทยาลัยมหิดล</div>
        <div class="contract-line">มีความประสงค์ขอยืมเงินจาก คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล</div>
        <div>เพื่อทดรองจ่าย&nbsp;&nbsp;{escaped['borrowing_purpose']}</div>
      </td>
    </tr>
    <tr class="contract-amount">
      <td class="contract-center">(ตัวอักษร)&nbsp;(&nbsp;{escaped['amount_text']}&nbsp;)</td>
      <td class="contract-center">(ตัวเลข)&nbsp;&nbsp;{escaped['amount_numeric']}&nbsp;&nbsp;บาท</td>
    </tr>
    <tr class="contract-agreement">
      <td colspan="2">
        <p class="contract-indent">ข้าพเจ้าสัญญาว่าจะปฏิบัติตามระเบียบของมหาวิทยาลัยมหิดลทุกประการ และจะนำใบสำคัญคู่จ่ายที่ถูกต้อง พร้อมทั้งเงินเหลือจ่าย (ถ้ามี) ส่งใช้ภายในกำหนด 15 วัน หลังจากเสร็จสิ้นภารกิจ คือวันที่ {escaped['due_date_thai']} ถ้าข้าพเจ้าไม่ส่งตามกำหนด ข้าพเจ้ายินยอมให้หักเงินเดือน ค่าจ้าง เบี้ยหวัด บำเหน็จ บำนาญหรือเงินอื่นใด ที่ข้าพเจ้าพึงได้รับจากมหาวิทยาลัยมหิดล ชดใช้จำนวนเงินที่ยืมไปจนครบถ้วนได้ทันที</p>
        <div class="signature-grid">
          <div class="signature-block">
            <div class="signature-line"><span>ลงชื่อ</span><span class="signature-rule"></span><span>ผู้ยืม</span></div>
            <div class="signature-name">(&nbsp;{escaped['borrower_name']}&nbsp;)</div>
          </div>
          <div class="date-line"><span>วันที่</span><span class="signature-rule"></span></div>
        </div>
      </td>
    </tr>
    <tr class="contract-proposal">
      <td colspan="2">
        <div>เสนอ คณบดี</div>
        <p class="contract-indent">ได้ตรวจสอบแล้ว เห็นสมควรอนุมัติให้ยืมตามใบยืมฉบับนี้ได้ จำนวนเงิน {escaped['amount_numeric']} บาท ({escaped['amount_text']})</p>
        <div class="signature-grid">
          <div class="signature-block">
            <div class="signature-line"><span>ลงชื่อ</span><span class="signature-rule"></span><span></span></div>
            <div class="signature-name">(&nbsp;รองศาสตราจารย์ ดร.วิลาสินี จึงประสบสุข&nbsp;)</div>
            <div class="signature-position">รองคณบดีฝ่ายการคลังและสินทรัพย์</div>
          </div>
          <div class="date-line"><span>วันที่</span><span class="signature-rule"></span></div>
        </div>
      </td>
    </tr>
    <tr class="contract-approval">
      <td colspan="2">
        <div class="contract-section-title">คำอนุมัติ</div>
        <p class="contract-indent">อนุมัติให้ยืมตามเงื่อนไขข้างต้นได้ เป็นจำนวนเงิน {escaped['amount_numeric']} บาท ({escaped['amount_text']})</p>
        <div class="signature-grid">
          <div class="signature-block">
            <div class="signature-line"><span>ลงชื่อผู้อนุมัติ</span><span class="signature-rule"></span><span></span></div>
            <div class="signature-name">(&nbsp;ผู้ช่วยศาสตราจารย์ ดร.โชติรส พลับพลึง&nbsp;)</div>
            <div class="signature-position">คณบดีคณะเทคนิคการแพทย์</div>
          </div>
          <div class="date-line"><span>วันที่</span><span class="signature-rule"></span></div>
        </div>
      </td>
    </tr>
    <tr class="contract-receipt">
      <td colspan="2">
        <div class="contract-section-title">ใบรับเงิน</div>
        <p class="contract-indent">ได้รับเงินยืมจำนวนเงิน {escaped['amount_numeric']} บาท ({escaped['amount_text']}) ไว้เป็นการถูกต้องแล้ว</p>
        <div class="signature-grid">
          <div class="signature-block">
            <div class="signature-line"><span>ลายมือชื่อ</span><span class="signature-rule"></span><span>ผู้รับเงิน</span></div>
            <div class="signature-name">(&nbsp;{escaped['borrower_name']}&nbsp;)</div>
          </div>
          <div class="date-line"><span>วันที่</span><span class="signature-rule"></span></div>
        </div>
      </td>
    </tr>
  </table>
  <div class="contract-footer">หมายเหตุ: ใบเสร็จแต่ละใบจะต้องมียอดไม่เกิน -100,000- บาท</div>
</main>
</body>
</html>"""


def _render_html_with_chromium(html_source):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        try:
            page = browser.new_page()
            page.set_content(html_source, wait_until="load")
            page.evaluate("() => document.fonts.ready")
            return page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                display_header_footer=False,
                margin={
                    "top": "0",
                    "right": "0",
                    "bottom": "0",
                    "left": "0",
                },
            )
        finally:
            browser.close()


def _render_fnar02_with_chromium(fnar02_context):
    return _render_html_with_chromium(_build_fnar02_html(fnar02_context))


def generate_fnar02_pdf(ticket):
    """Generate both FNAR02 pages with Playwright Chromium."""
    from pypdf import PdfReader

    fnar02_context = _build_fnar02_context(ticket)
    chromium_pdf = _render_fnar02_with_chromium(fnar02_context)
    page_count = len(PdfReader(BytesIO(chromium_pdf)).pages)
    if page_count != 2:
        raise ValueError(
            f"Chromium rendered {page_count} FNAR02 pages; expected exactly 2"
        )
    return chromium_pdf


def _build_reimbursement_letter_html(context):
    """Build a one-page Thai reimbursement letter for Chromium printing."""
    def escaped(value):
        return html.escape(str(value), quote=True)

    paragraphs_html = "".join(
        f'<p class="government-text">{escaped(paragraph)}</p>'
        for paragraph in context["body_paragraphs"]
    )
    items_html = "".join(
        f'<tr class="text-center">'
        f'<td class="item-number">{index}.</td>'
        f'<td>{escaped(description)}</td>'
        f'<td class="amount">{escaped(amount)} บาท</td>'
        "</tr>"
        for index, description, amount in context["items"]
    )
    extra_header_class = " extra-header-space" if context.get("extra_header_space") else ""

    return f"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>{escaped(context['title'])}</title>
<style>
  @font-face {{
    font-family: "TH Sarabun New";
    src: url("{PDF_REGULAR_FONT_DATA_URI}") format("truetype");
    font-style: normal;
    font-weight: 400;
  }}
  @font-face {{
    font-family: "TH Sarabun New";
    src: url("{PDF_BOLD_FONT_DATA_URI}") format("truetype");
    font-style: normal;
    font-weight: 700;
  }}
  @page {{ size: A4; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    color: #000;
    font-family: "TH Sarabun New", "TH Sarabun PSK", sans-serif;
    font-size: 16pt;
    line-height: 1.25;
  }}
  .letter-page {{
    width: 210mm;
    min-height: 297mm;
    margin: 0 auto;
    padding: 7.8mm 19.4mm;
  }}
  .letterhead {{
    position: relative;
    height: 27.5mm;
    margin-bottom: 6mm
  }}
  .letter-page.extra-header-space .document-info {{ margin-top: 7mm; }}
  .logo {{
    position: absolute;
    top: 0;
    left: 67.7mm;
    width: 23.3mm;
    height: 23.3mm;
    object-fit: contain;
  }}
  .organization {{
    position: absolute;
    top: 6mm;
    right: 0;
    width: 74.8mm;
    text-align: right;
  }}
  .document-info {{
    display: grid;
    grid-template-columns: 16.9mm minmax(0, 1fr);
    row-gap: .7mm;
  }}
  .letter-body {{
    --summary-offset: 24.7mm;
    --summary-width: 135.8mm;
    margin-top: 6.3mm;
  }}
  .government-text {{
    margin: 0 0 2.8mm;
    text-indent: 24.7mm;
    text-align: justify;
    text-justify: inter-word;
    text-align-last: left;
    word-break: normal;
    line-break: strict;
    overflow-wrap: normal;
  }}
  .items {{
    width: var(--summary-width);
    margin: 0 0 1.4mm var(--summary-offset);
    border-collapse: collapse;
    table-layout: fixed;
  }}
  .items tr {{ break-inside: avoid; }}
  .items td {{ padding: .7mm 0; vertical-align: top; }}
  .items .item-number {{ width: 12.3mm; text-align: left; }}
  .items .amount {{ width: 28.2mm; text-align: right; white-space: nowrap; }}
  .total-row {{
    display: grid;
    grid-template-columns: 19.5mm minmax(0, 1fr) 28.2mm;
    width: var(--summary-width);
    margin: 0 0 3.5mm var(--summary-offset);
  }}
  .total-amount {{ text-align: right; }}
  .total-amount {{ white-space: nowrap; }}
  .total-label {{ text-align: left; text-decoration: underline; }}
  .closing {{
    margin: 0;
    text-align: center;
  }}
  .head-signature {{
    width: 50%;
    margin-top: 16mm ;
    margin-left: 51%;
    text-align: center;
    break-inside: avoid;
  }}
  .approval-signature {{
    width: 50%;
    margin-top: 16mm ;
    margin-right: 51%;
    text-align: center;
    break-inside: avoid;
  }}
  .approval-title {{ margin-bottom: 14mm; }}
</style>
</head>
<body>
<main class="letter-page{extra_header_class}">
  <header class="letterhead">
    <img class="logo" src="{PDF_LOGO_DATA_URI}" alt="ตรามหาวิทยาลัยมหิดล">
    <div class="organization">
      <br>{escaped(context['department_name'])}<br>
      คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br>
      โทร.{escaped(context['telephone_number'])}
    </div>
  </header>
  <section class="document-info">
    <span>ที่</span><span>&nbsp;</span>
    <span>วันที่</span><span>&nbsp;</span>
    <span>เรื่อง</span><span>{escaped(context['subject'])}</span>
    <span>เรียน</span><span>คณบดีคณะเทคนิคการแพทย์</span>
  </section>
  <section class="letter-body">
    {paragraphs_html}
    <table class="items"><tbody>{items_html}</tbody></table>
    <div class="total-row">
      <span class="total-label">รวมทั้งสิ้น</span>
      <span>&nbsp;&nbsp;{escaped(context['amount_text'])}</span>
      <span class="total-amount">{escaped(context['amount_numeric'])} บาท</span>
    </div>
    <p class="government-text">{escaped(context['reference_text'])}</p>
    <p class="closing">จึงเรียนมาเพื่อโปรดพิจารณาอนุมัติจักเป็นพระคุณยิ่ง</p>
  </section>
  <section class="head-signature">
    <div>({escaped(context['head_name'])})</div>
    <div>{escaped(context['head_position'])}</div>
  </section>
  <section class="approval-signature">
    <div class="approval-title">อนุมัติ</div>
    <div>(ผู้ช่วยศาสตราจารย์ ดร.โชติรส พลับพลึง)</div>
    <div>คณบดีคณะเทคนิคการแพทย์</div>
  </section>
</main>
</body>
</html>"""


def generate_petty_claim(claim, claim_type="1"):
    """
    สร้างเอกสาร PDF สำหรับรายการขออนุมัติเบิกค่าใช้จ่ายของ petty cash claim
    โดยยึดรูปแบบหน้าเดียวตามเอกสารตัวอย่าง:
    - ส่วนหัวกึ่งกลาง + ข้อมูลหน่วยงานชิดขวา
    - ข้อมูลหนังสือ / วันที่ / เรื่อง / เรียน
    - เนื้อความหนังสือราชการ
    - ตารางรายการแบบไม่มีเส้น
    - ส่วนลงนามท้ายหน้า
    """
    from .views import get_department_data_service

    if not claim:
        return b""

    if claim_type not in ("1", "2"):
        raise ValueError("Unsupported petty claim type")
    no_approval_letter = claim_type == "2"

    fund_request = getattr(claim, "fund_request", None)
    setting = getattr(claim, "setting", None)
    if setting is None:
        setting = db.session.query(PettyCashSetting).get(getattr(claim, "petty_cash_setting_id", None))
    requester = getattr(claim, "user", None) or _get_user_by_id(getattr(claim, "user_id", None))

    requester_org = getattr(getattr(requester, "personal_info", None), "org", None)
    fund_request_org = getattr(fund_request, "org", None) or db.session.query(Org).get(getattr(fund_request, "org_id", None))
    setting_org = getattr(setting, "org", None)
    department_name = (
        getattr(setting_org, "name", None)
        or getattr(fund_request_org, "name", None)
        or getattr(requester_org, "name", None)
        or (getattr(setting, "department_name", None) or "").strip()
        or (getattr(fund_request, "department_name", None) or "").strip()
        or (getattr(requester, "department", None) or "").strip()
        or PDF_BLANK
    )

    borrowing_ticket = getattr(fund_request, "borrowing_ticket", None) if fund_request else None
    head_name, head_position = _get_head_signature(claim=claim, fund_request=fund_request)

    requester_name = (
        getattr(requester, "name", None)
        or getattr(requester, "fullname", None)
        or getattr(claim, "requester_name", None)
        or getattr(fund_request, "requester_name", None)
        or PDF_BLANK
    )

    requester_position = (
        getattr(requester, "position", None)
        or getattr(claim, "requester_position", None)
        or getattr(fund_request, "requester_position", None)
        or PDF_BLANK
    )

    request_purpose = (
        getattr(fund_request, "purpose", None)
        or getattr(fund_request, "claim_name", None)
        or PDF_BLANK
    )
    subject_text = (f"ขออนุมัติเบิกค่าใช้จ่าย{request_purpose}")

    claim_items = list(getattr(claim, "items", None) or [])
    display_items = [
        item for item in claim_items
        if str(getattr(item, "category_type", "")).strip() != "6"
    ]

    amount_value = sum(
        (Decimal(str(getattr(item, "amount", 0) or 0)) for item in display_items),
        Decimal("0.00"),
    )
    amount_numeric = f"{amount_value:,.2f}" if amount_value else PDF_BLANK
    amount_text = bahttext(amount_value) if amount_value else PDF_BLANK

    bank_account_info = None
    request_account_number = getattr(borrowing_ticket, "account_number", None) if borrowing_ticket else None
    if request_account_number:
        bank_account_info = _get_bank_account_info_for_account_number(request_account_number)
    if not bank_account_info:
        bank_account_info = _get_bank_account_info_for_petty_cash_setting(setting)

    setting_account_number = (
        getattr(bank_account_info, "account_number", None)
        or getattr(setting, "account_number", None)
        or ""
    )

    account_number = (
        (request_account_number or "").strip()
        or setting_account_number.strip()
        or (_pdf_text(bank_account_info.account_number) if bank_account_info else PDF_BLANK)
    )
    account_name = (
        bank_account_info.thai_name
        if bank_account_info and bank_account_info.thai_name
        else PDF_BLANK
    )

    fiscal_year_label = _format_fiscal_year_for_pdf(getattr(claim, "fiscal_year", None))
    reference_number = getattr(claim, "reference_number", None) or PDF_BLANK
    reference_date = getattr(claim, "reference_date", None)
    reference_date_label = get_thai_month_year(reference_date) if reference_date else PDF_BLANK
    product_name = getattr(getattr(claim, "product_code", None), "id", None) or PDF_BLANK
    cost_center_label = getattr(getattr(claim, "cost_center", None), "id", None) or PDF_BLANK
    mission_label = getattr(getattr(claim, "iocode", None), "id", None) or PDF_BLANK

    dept_service_data = get_department_data_service(department_name) or {}
    org = getattr(getattr(requester, "personal_info", None), "org", None)
    telephone_number = (
        getattr(org, "phone_number", None)
        or dept_service_data.get("telephone_number")
        or dept_service_data.get("phone_number")
        or PDF_BLANK
    )

    body_1 = (
        f"ตามหนังสือที่ {reference_number} ลงวันที่ {reference_date_label} ซึ่งคณะได้อนุมัติให้ {request_purpose}นั้น"
    )
    body_2 = (
        f"ในการนี้{department_name}ได้ดำเนินการตามวัตถุประสงค์ดังกล่าวเสร็จสิ้นแล้ว จึงขออนุมัติเบิกค่าใช้จ่าย ในการ{request_purpose} เป็นจำนวนเงินรวม {amount_numeric} บาท ({amount_text}) โดยมี {requester_name} ตำแหน่ง {requester_position} เป็นผู้ยื่นเรื่อง โดยมีรายละเอียดดังนี้"
    )

    ref_text = (
        f"โดยเบิกจากเงินปีงบประมาณ {fiscal_year_label} ผลผลิต {product_name} รหัสศูนย์ต้นทุน {cost_center_label} รหัสใบสั่งงานภายใน {mission_label} "
        f"เอกสารฉบับนี้ส่งคืนบัญชี {account_name} เลขที่บัญชี {account_number} เพื่อทำการขอเบิกเงินเข้าบัญชีเงินสดย่อยของหน่วยงานต่อไป ดังรายละเอียดตามเอกสารที่แนบมาพร้อมนี้"
    )
    if no_approval_letter:
        body_paragraphs = [
            f"ด้วย{department_name} คณะเทคนิคการแพทย์ มีความประสงค์ดำเนินการ {request_purpose} โดยจะมีค่าใช้จ่ายในการดำเนินการ ดังนี้"
        ]
        ref_text = (
            f"ในการนี้\u00a0จึงเรียนมาเพื่อโปรดพิจารณาอนุมัติในหลักการค่าใช้จ่ายในการ{request_purpose} จำนวน {amount_numeric} บาท ({amount_text}) จากเงินรายได้คณะฯ "
            f"ประจำปีงบประมาณ {fiscal_year_label} ผลผลิต {product_name} รหัสศูนย์ต้นทุน {cost_center_label} รหัสใบสั่งงานภายใน {mission_label} "
            f"เอกสารฉบับนี้ส่งคืนบัญชี {account_name} เลขที่บัญชี {account_number} เพื่อทำการขอเบิกเงินเข้าบัญชีเงินสดย่อยของหน่วยงานต่อไป ดังรายละเอียดตามเอกสารที่แนบมาพร้อมนี้"
        )
    else:
        body_paragraphs = [body_1, body_2]

    document_context = {
        "title": "Petty Claim Request",
        "department_name": department_name,
        "telephone_number": telephone_number,
        "subject": subject_text,
        "body_paragraphs": body_paragraphs,
        "items": [
            (
                index,
                getattr(item, "description", None) or PDF_BLANK,
                _pdf_amount(getattr(item, "amount", None)),
            )
            for index, item in enumerate(display_items, 1)
        ],
        "amount_text": amount_text,
        "amount_numeric": amount_numeric,
        "reference_text": ref_text,
        "head_name": head_name,
        "head_position": head_position,
        "extra_header_space": no_approval_letter,
    }
    return _render_html_with_chromium(
        _build_reimbursement_letter_html(document_context)
    )


generate_petty_claim_pdf = generate_petty_claim


def generate_ticket_return(return_detail):
    """สร้างหนังสือส่งใช้เงินยืมจาก CashAdvanceBorrowingTicket โดยเฉพาะ."""
    if not return_detail:
        return b""

    ticket = getattr(return_detail, "borrowing_ticket", None)
    if not ticket:
        return b""

    from .views import get_department_data_service

    borrower = getattr(ticket, "borrower_user", None)
    borrower_org = getattr(getattr(borrower, "personal_info", None), "org", None)
    department_name = getattr(borrower_org, "name", None) or getattr(borrower, "department", None)
    department_name = department_name or PDF_BLANK
    ticket_number = getattr(ticket, "number", None) or PDF_BLANK
    request_purpose = getattr(ticket, "borrowing_ticket_purpose", None) or PDF_BLANK
    return_items = [
        item for item in (getattr(return_detail, "receipt_items", None) or [])
        if not getattr(item, "is_cash", False)
    ]
    amount_value = sum(
        (Decimal(str(item.amount or 0)) for item in return_items),
        Decimal("0.00"),
    )
    amount_numeric = f"{amount_value:,.2f}" if amount_value else PDF_BLANK
    amount_text = bahttext(amount_value) if amount_value else PDF_BLANK

    fiscal_year_label = _format_fiscal_year_for_pdf(getattr(return_detail, "fiscal_year", None))
    reference_number = getattr(ticket, "aip_ref_no", None) or getattr(return_detail, "reference_number", None) or PDF_BLANK
    reference_date = getattr(ticket, "aip_ref_date", None) or getattr(return_detail, "reference_date", None)
    reference_date_label = get_thai_month_year(reference_date) if reference_date else PDF_BLANK
    product_name = getattr(getattr(return_detail, "product_code", None), "name", None) or PDF_BLANK
    cost_center_label = getattr(getattr(return_detail, "cost_center", None), "id", None) or PDF_BLANK
    mission_label = getattr(getattr(return_detail, "iocode", None), "id", None) or PDF_BLANK

    dept_service_data = get_department_data_service(department_name) or {}
    telephone_number = (
        getattr(borrower_org, "phone_number", None)
        or dept_service_data.get("telephone_number")
        or dept_service_data.get("phone_number")
        or PDF_BLANK
    )
    head_name, head_position = _get_head_signature(ticket=ticket)
    document_context = {
        "title": "Ticket Return Request",
        "department_name": department_name,
        "telephone_number": telephone_number,
        "subject": f"ขออนุมัติเบิกจ่ายพร้อมส่งใช้เงินยืม บย. {ticket_number}",
        "body_paragraphs": [
            f"ตามหนังสือที่ {reference_number} ลงวันที่ {reference_date_label} ซึ่งคณะได้อนุมัติให้ {request_purpose}นั้น",
            f"ในการนี้{department_name}ดำเนินการดังกล่าวเสร็จสิ้นแล้ว จึงขออนุมัติเบิกค่าใช้จ่าย ในการ{request_purpose} โดยขออนุมัติเบิกค่าใช้จ่ายสำหรับการจัด โครงการดังกล่าว เป็นจำนวน {amount_numeric} บาท ({amount_text}) โดยมีรายละเอียดดังนี้",
        ],
        "items": [
            (
                index,
                getattr(item, "description", None) or PDF_BLANK,
                _pdf_amount(getattr(item, "amount", None)),
            )
            for index, item in enumerate(return_items, 1)
        ],
        "amount_text": amount_text,
        "amount_numeric": amount_numeric,
        "reference_text": (
            f"โดยเบิกจากเงินปีงบประมาณ {fiscal_year_label} ผลผลิต {product_name} รหัสศูนย์ต้นทุน {cost_center_label} รหัสใบสั่งงานภายใน {mission_label} "
            f"เอกสารฉบับนี้ส่งคืนบัญชีเงินยืม บย.{ticket_number} เพื่อทำการขอเบิกเงินคืนต่อไป ดังรายละเอียดตาม เอกสารที่แนบมาพร้อมนี้"
        ),
        "head_name": head_name,
        "head_position": head_position,
    }
    return _render_html_with_chromium(
        _build_reimbursement_letter_html(document_context)
    )


generate_ticket_return_pdf = generate_ticket_return


def _build_fund_request_html(context):
    """Build the MT-Petty Cash-02 form for Playwright Chromium."""
    def escaped(value):
        return html.escape(str(value), quote=True)

    item_rows = "".join(
        "<tr>"
        f'<td class="center">{escaped(index)}</td>'
        f"<td>{escaped(description)}</td>"
        f'<td class="amount">{escaped(amount)}</td>'
        "</tr>"
        for index, description, amount in context["items"]
    )

    def signature_cells(signatures):
        return "".join(
            '<div class="signature-cell">'
            f"<div>{escaped(label)}</div><div class=\"signature-space\"></div>"
            f"<div>{escaped(signature_line)}</div><div>(&nbsp;{escaped(name)}&nbsp;)</div>"
            f"<div>ตำแหน่ง {escaped(position)}</div><div>วันที่ {escaped(date)}</div>"
            "</div>"
            for label, signature_line, name, position, date in signatures
        )

    separator_dots = "." * 260

    return f"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>{escaped(context['title'])}</title>
<style>
  @font-face {{ font-family: "TH Sarabun New"; src: url("{PDF_REGULAR_FONT_DATA_URI}") format("truetype"); font-weight: 400; }}
  @font-face {{ font-family: "TH Sarabun New"; src: url("{PDF_BOLD_FONT_DATA_URI}") format("truetype"); font-weight: 700; }}
  @font-face {{ font-family: "DejaVu Sans"; src: url("{PDF_CHECKBOX_FONT_DATA_URI}") format("truetype"); }}
  @page {{ size: A4; margin: 0; }}
  :root {{ --form-border: .5px solid #8c8c8c; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: "TH Sarabun New", sans-serif; font-size: 16pt; line-height: 1.12; color: #000; }}
  .page {{ width: 210mm; min-height: 297mm; padding: 5.6mm 15.9mm; margin: 0 auto; }}
  .form-header {{ display: grid; grid-template-columns: 24mm 1fr 36mm; align-items: center; }}
  .logo {{ width: 24.7mm; height: 24.7mm; object-fit: contain; }}
  .form-title {{ text-align: center; font-weight: 700; }}
  .form-code {{ text-align: right; font-size: 13pt; align-self: start; }}
  .dotted-separator {{
    height: 1.5mm;
    margin: 2mm 0;
    overflow: hidden;
    white-space: nowrap;
    font-size: 10pt;
    line-height: .6mm;
    letter-spacing: .25mm;
  }}
  .section-heading {{ display: grid; grid-template-columns: 1fr auto; align-items: start; margin-bottom: .8mm; }}
  .section-meta {{ text-align: right; font-size: 13pt; line-height: 1.2; }}
  .section-body {{ margin-bottom: 1.3mm; }}
  table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
  th, td {{ border: var(--form-border); padding: 1mm 1.2mm; vertical-align: middle; }}
  th {{ text-align: center; font-weight: 700; }}
  .item-number {{ width: 17mm; }}
  .item-amount {{ width: 42mm; }}
  .center {{ text-align: center; }}
  .amount {{ text-align: right; white-space: nowrap; }}
  .total-label {{ text-align: right; font-weight: 700; }}
  .signature-grid {{ display: grid; border: var(--form-border); border-right: 0; margin-top: 5mm; break-inside: avoid; }}
  .signature-grid.three {{ grid-template-columns: 1fr 1fr 1.2fr; }}
  .signature-grid.two {{ grid-template-columns: 1fr 1fr; width: 87%; margin-left: auto; margin-right: auto; }}
  .signature-cell {{ border-right: var(--form-border); padding: 1.4mm; text-align: center; min-height: 32mm; }}
  .signature-space {{ height: 6mm; }}
  .section-two {{ margin-top: 1mm; }}
  .recipient {{ margin: 0 0 1mm; }}
  .option {{ margin: 0 0 1mm; text-indent: 24.7mm; text-align: justify; text-justify: inter-word; line-break: strict; }}
  .checkbox {{ font-family: "DejaVu Sans", sans-serif; text-indent: 0; }}
  .footer-note {{ margin-top: 1.5mm; font-size: 11pt; line-height: 1; text-align: center; }}
</style>
</head>
<body>
<main class="page">
  <header class="form-header">
    <img class="logo" src="{PDF_LOGO_DATA_URI}" alt="ตรามหาวิทยาลัยมหิดล">
    <div class="form-title">ใบยืมเงินสดย่อย/ใบเบิกเงินสดย่อย<br>{escaped(context['department'])}</div>
    <div class="form-code">MT-Petty Cash-02</div>
  </header>
  <div class="dotted-separator">{separator_dots}</div>
  <section>
    <div class="section-heading"><strong>ส่วนที่ 1 ใบยืมเงินสดย่อย</strong><div class="section-meta">เลขที่ใบเบิกเงิน {escaped(context['ticket_number'])}<br>วันที่ {escaped(context['date_thai'])}</div></div>
    <div class="section-body">ข้าพเจ้า {escaped(context['requester'])} ตำแหน่ง {escaped(context['requester_position'])} มีความประสงค์ขอยืมเงินสดย่อย<br>เพื่อ{escaped(context['purpose'])} มีรายละเอียดดังนี้</div>
    <table>
      <thead><tr><th class="item-number">ลำดับ</th><th>รายการ</th><th class="item-amount">จำนวนเงิน (บาท)</th></tr></thead>
      <tbody>{item_rows}<tr><td class="total-label" colspan="2">รวมเป็นเงินทั้งสิ้น</td><td class="amount"><strong>{escaped(context['total_amount'])}</strong></td></tr></tbody>
    </table>
    <div class="signature-grid three">{signature_cells(context['section_one_signatures'])}</div>
  </section>
  <div class="dotted-separator">{separator_dots}</div>
  <section class="section-two">
    <div class="section-heading"><strong>ส่วนที่ 2 ใบเบิกเงิน</strong><div class="section-meta">เลขที่ใบเบิกเงิน {escaped(context['ticket_number'])}<br>วันที่ {escaped(context['date_thai'])}</div></div>
    <p class="recipient"><strong>เรียน</strong>&nbsp;&nbsp;{escaped(context['head_position'])}</p>
    <p class="option"><span class="checkbox">{escaped(context['petty_checkbox'])}</span> {escaped(context['petty_text'])}</p>
    <p class="option"><span class="checkbox">{escaped(context['interest_checkbox'])}</span> {escaped(context['interest_text_before'])}&nbsp;<span class="checkbox">{escaped(context['june_checkbox'])}</span> งวดเดือน มิถุนายน พ.ศ. {escaped(context['period_year'])}&nbsp;<span class="checkbox">{escaped(context['december_checkbox'])}</span> งวดเดือน ธันวาคม พ.ศ. {escaped(context['period_year'])}<br>{escaped(context['interest_text_after'])}</p>
    <div class="signature-grid two">{signature_cells(context['section_two_signatures'])}</div>
    <div class="footer-note">หมายเหตุ: ใบเสร็จแต่ละใบจะต้องมียอดไม่เกิน -20,000- บาท</div>
  </section>
</main>
</body>
</html>"""


def generate_fund_request_pdf(fund_request):
    """Generate the MT-Petty Cash-02 form with Playwright Chromium."""
    form_type = str(fund_request.form_type or "")
    is_interest_form = form_type == FUND_REQUEST_FORM_INTEREST
    is_borrowing_form = form_type == FUND_REQUEST_FORM_BORROWING_TICKET
    borrowing_ticket = getattr(fund_request, "borrowing_ticket", None)

    date_thai = (
        get_thai_month_year(fund_request.request_date)
        if getattr(fund_request, "request_date", None)
        else PDF_BLANK
    )
    requester_user = _get_user_by_id(getattr(fund_request, "requester_id", None))
    requester = getattr(requester_user, "name", "") or PDF_BLANK
    requester_pos = getattr(requester_user, "position", "") or PDF_BLANK
    purpose = fund_request.purpose or PDF_BLANK
    ticket_number = fund_request.ticket_number or PDF_BLANK

    if is_borrowing_form and borrowing_ticket:
        requester = borrowing_ticket.borrower_name or requester
        requester_user = getattr(borrowing_ticket, "borrower_user", None) or _get_user_by_id(getattr(borrowing_ticket, "borrower_id", None))
        requester_pos = getattr(requester_user, "position", "") or requester_pos
        purpose = f"เบิกเงินยืมผ่านบัญชีเงินสดย่อยตามใบยืมเงิน บ.ย. {_pdf_text(borrowing_ticket.number)}"
    
    # Resolve the organization by its stable ID; department_name is legacy display data.
    org = db.session.query(Org).get(getattr(fund_request, "org_id", None))
    dept_lookup = getattr(fund_request, "org_id", None) or getattr(org, "name", None)
    dept_info = get_department_info_from_api(dept_lookup)
    head_name, head_position = _get_head_signature(fund_request=fund_request)
    request_setting = getattr(fund_request, "petty_cash_setting", None)
    if request_setting is None and getattr(fund_request, "petty_cash_setting_id", None):
        request_setting = db.session.query(PettyCashSetting).get(fund_request.petty_cash_setting_id)
    custodian_user = _get_user_by_id(getattr(request_setting, "custodian_id", None))
    custodian_name = _pdf_text(
        getattr(custodian_user, "name", None)
        or getattr(custodian_user, "fullname", None)
        or dept_info.get("custodian")
    )
    custodian_position = _pdf_text(
        getattr(custodian_user, "position", None)
        or dept_info.get("position")
    )

    creator_id = getattr(fund_request, "creator_id", None)
    requester_id = getattr(fund_request, "requester_id", None)
    custodian_id = getattr(request_setting, "custodian_id", None)
    confirmed_by_id = getattr(fund_request, "confirmed_by_id", None)
    approved_by_id = getattr(fund_request, "approved_by_id", None)
    created_at = getattr(fund_request, "created_at", None)
    confirmed_at = getattr(fund_request, "confirmed_at", None)
    approved_at = getattr(fund_request, "approved_at", None)

    creator_user = (
        getattr(fund_request, "creator", None)
        or _get_user_by_id(creator_id)
    )
    confirmed_user = (
        getattr(fund_request, "confirmed_by", None)
        or _get_user_by_id(confirmed_by_id)
    )
    approved_user = (
        getattr(fund_request, "approved_by", None)
        or _get_user_by_id(approved_by_id)
    )

    requester_signature_user = None
    requester_signed_at = None
    if creator_id == requester_id and created_at:
        requester_signature_user = creator_user
        requester_signed_at = created_at
    elif confirmed_by_id == requester_id and confirmed_at:
        requester_signature_user = confirmed_user
        requester_signed_at = confirmed_at

    custodian_signature_user = None
    custodian_signed_at = None
    if creator_id == custodian_id and created_at:
        custodian_signature_user = creator_user
        custodian_signed_at = created_at
    elif confirmed_by_id == custodian_id and confirmed_at:
        custodian_signature_user = confirmed_user
        custodian_signed_at = confirmed_at

    approver_signature_user = approved_user if approved_by_id and approved_at else None

    def signature_date(value):
        if not value:
            return "................................................."
        date_value = value.date() if isinstance(value, datetime) else value
        return get_thai_month_year(date_value)

    requester_signature_date = signature_date(requester_signed_at)
    custodian_signature_date = signature_date(custodian_signed_at)
    approver_signature_date = signature_date(
        approved_at if approver_signature_user is not None else None
    )
    signature_placeholder = "......................................................."
    requester_signature_line = (
        _thai_signature_name(requester_signature_user) or signature_placeholder
    )
    custodian_signature_line = (
        _thai_signature_name(custodian_signature_user) or signature_placeholder
    )
    head_signature_line = (
        _thai_signature_name(approver_signature_user) or signature_placeholder
    )

    amount_source = fund_request.amount
    if amount_source is None and borrowing_ticket:
        amount_source = borrowing_ticket.required_budget
    amount_val = float(amount_source) if amount_source is not None else None
    amount_str = _pdf_amount(amount_val)
    amount_text_th = bahttext(amount_val) if amount_val is not None else PDF_BLANK

    dept_display = getattr(org, "name", None) or missing_department_notice()
    items = fund_request.items if hasattr(fund_request, 'items') and fund_request.items else []
    item_rows = []
    total_amount = 0.0
    has_total_amount = False

    if is_borrowing_form and not items and borrowing_ticket:
        ticket_no = getattr(borrowing_ticket, "number", None) or PDF_BLANK
        ticket_amount = borrowing_ticket.required_budget
        if ticket_amount is None:
            ticket_amount = amount_val
        item_rows.append((
            "1",
            f"เบิกเงินยืมผ่านบัญชีเงินสดย่อยตามใบยืมเงิน บ.ย. {ticket_no}",
            _pdf_amount(ticket_amount),
        ))
        total_amount = float(ticket_amount) if ticket_amount is not None else 0.0
        has_total_amount = ticket_amount is not None
    elif not is_interest_form and items:
        for idx, item in enumerate(items, 1):
            amt = float(item.amount or 0)
            total_amount += amt
            has_total_amount = has_total_amount or item.amount is not None
            item_rows.append((
                str(idx),
                item.description or PDF_BLANK,
                _pdf_amount(item.amount),
            ))
    else:
        item_rows.append((PDF_BLANK, PDF_BLANK, PDF_BLANK))

    dept_name = getattr(org, "name", None) or missing_department_notice()
    today = datetime.now().date()
    current_fiscal_year = today.year + 1 if today.month >= 10 else today.year
    setting = (
        db.session.query(PettyCashSetting)
        .filter_by(org_id=getattr(org, "id", None), fiscal_year=current_fiscal_year, valid=True)
        .first()
    )
    request_account_number = (
        getattr(borrowing_ticket, "account_number", None)
        or getattr(setting, "account_number", None)
        or ""
    )
    bank_account_info = _get_bank_account_info_for_account_number(request_account_number)
    acc_num = (
        bank_account_info.account_number
        if bank_account_info and bank_account_info.account_number
        else (request_account_number or PDF_BLANK)
    )
    acc_name = (
        bank_account_info.thai_name
        if bank_account_info and bank_account_info.thai_name
        else PDF_BLANK
    )
    chk_box = "☐"
    chk_box_checked = "☑"

    if not is_interest_form:
        box_petty_cash = chk_box_checked
        p_dept_1 = dept_name
        p_acc_1 = acc_num
        p_amt_str_1 = f"-{amount_str}-" if amount_str.strip() else PDF_BLANK
        p_amt_text_1 = amount_text_th
        p_borrow_no = ticket_number
        p_borrow_date = get_thai_month_year(borrowing_ticket.approved_at.date()) if is_borrowing_form and borrowing_ticket and borrowing_ticket.approved_at else date_thai
        p_borrower_name = requester

        box_interest = chk_box
        box_june = chk_box
        box_dec = chk_box
        p_period_yr = date_thai.split()[-1] if date_thai.strip() else today.year + 543 # current year if none
        p_dept_2 = dept_name
        p_acc_2 = ".................."
        p_amt_str_2 = ".................."
        p_amt_text_2 = ".................."

    else:
        box_petty_cash = chk_box
        p_dept_1 = ".................."
        p_acc_1 = acc_num
        p_amt_str_1 = ".................."
        p_amt_text_1 = ".................."
        p_borrow_no = ticket_number
        p_borrow_date = ".................."
        p_borrower_name = ".................."

        # ส่วนดอกเบี้ยเติมข้อมูลจริง
        box_interest = chk_box_checked
        
        # รองรับทั้งค่าเก่าแบบ "มิถุนายน พ.ศ. 2567" และค่าใหม่แบบ "06/2567"
        period_value = str(fund_request.period_year or "")
        period_label = _format_interest_period_label(period_value)

        # เช็คการติ๊กเลือกงวด
        box_june = chk_box_checked if period_value.startswith("06/") or "มิถุนายน" in period_label else chk_box
        box_dec = chk_box_checked if period_value.startswith("12/") or "ธันวาคม" in period_label else chk_box

        # สกัดเฉพาะเลขปี พ.ศ. ออกมาจากสตริง (เช่น "2567")
        year_match = re.search(r'\d{4}', period_label or period_value)
        p_period_yr = year_match.group(0) if year_match else today.year + 543 # current year if none

        p_dept_2 = dept_name
        p_acc_2 = acc_num
        p_amt_str_2 = f"-{amount_str}-" if amount_str.strip() else PDF_BLANK
        p_amt_text_2 = amount_text_th

    context = {
        "title": f"MT-Petty-Cash-02_{fund_request.ticket_number}",
        "department": dept_display,
        "ticket_number": ticket_number,
        "date_thai": date_thai,
        "requester": requester,
        "requester_position": requester_pos,
        "purpose": purpose if not is_interest_form else PDF_BLANK,
        "items": item_rows,
        "total_amount": _pdf_amount(total_amount if has_total_amount else None),
        "section_one_signatures": [
            ("ลงชื่อผู้ขอยืม", requester_signature_line, requester, requester_pos, requester_signature_date),
            ("ลงชื่อผู้เก็บรักษาเงินสดย่อย", custodian_signature_line, custodian_name, custodian_position, custodian_signature_date),
            ("ลงชื่อผู้อนุมัติ", head_signature_line, head_name, head_position, approver_signature_date),
        ],
        "head_position": head_position,
        "petty_checkbox": box_petty_cash,
        "petty_text": (
            f"ขออนุมัติเบิกเงินสดย่อยจากบัญชี{acc_name} เลขที่บัญชี {p_acc_1} "
            f"เป็นจำนวนเงิน {p_amt_str_1} บาท ({p_amt_text_1}) ตามใบยืมเงินสดย่อยเลขที่ "
            f"{p_borrow_no} ลงวันที่ {p_borrow_date} โดยมี {p_borrower_name} เป็นผู้ยืม"
        ),
        "interest_checkbox": box_interest,
        "june_checkbox": box_june,
        "december_checkbox": box_dec,
        "period_year": p_period_yr,
        "interest_text_before": "ขออนุมัติเบิกดอกเบี้ย",
        "interest_text_after": (
            f"จากบัญชี {p_dept_2} เลขที่บัญชี {p_acc_1} ชื่อบัญชี {acc_name} "
            f"เป็นจำนวนเงิน {p_amt_str_2} บาท ({p_amt_text_2}) และขออนุมัตินำส่งดอกเบี้ย"
            "เข้าเป็นเงินรายได้คณะฯ โอนเข้าบัญชี เลขที่ 016-300-325-6 ชื่อบัญชีมหาวิทยาลัยมหิดล"
        ),
        "section_two_signatures": [
            ("ลงชื่อผู้เก็บรักษาเงินสดย่อย", custodian_signature_line, custodian_name, custodian_position, custodian_signature_date),
            ("ลงชื่อผู้อนุมัติ", head_signature_line, head_name, head_position, approver_signature_date),
        ],
    }
    return _render_html_with_chromium(_build_fund_request_html(context))


def generate_petty_cash_ledger_pdf(*, setting, month_start, ledger_items):
    """Render the existing 17-column monthly ledger as landscape A4 pages."""
    from reportlab.lib.pagesizes import landscape
    from reportlab.platypus import LongTable
    from decimal import Decimal

    ledger_items = list(ledger_items)

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=20,
                            rightMargin=20, topMargin=60, bottomMargin=28)
    body = ParagraphStyle("LedgerBody", fontName="Sarabun", fontSize=9,
                          leading=11, wordWrap="CJK")
    center = ParagraphStyle("LedgerCenter", parent=body, alignment=TA_CENTER)
    right = ParagraphStyle("LedgerRight", parent=body, alignment=TA_RIGHT)
    header = ParagraphStyle("LedgerHeader", parent=center, fontName="SarabunBold")

    def cell(value, style=body):
        return Paragraph(_pdf_text(value), style)

    def heading(value):
        return Paragraph(value, header)

    def amount(row, key):
        value = row.get(key) or 0
        return cell(f"{value:,.2f}" if value > 0 else PDF_BLANK, right)

    rows = [
        [heading(text) for text in [
            "(1)<br/>เดือน / ปี", "(2)<br/>วันที่", "(3)<br/>รายการ",
            "(4)<br/>เลขที่หนังสืออนุมัติเบิกค่าใช้จ่าย", "(5)<br/>เงินฝากธนาคาร", "",
            "(6)<br/>เงินสด", "", "(7-11)<br/>รายละเอียดรายจ่ายต่าง ๆ", "", "", "", "", "",
            "(12)<br/>โอนคืนบัญชีหน่วย", "(13)<br/>ยอดเงินคงเหลือ", "วันที่ส่งเอกสารเบิก"]],
        [heading(text) for text in ["", "", "", "", "รับ", "จ่าย", "รับ", "จ่าย",
            "(7)<br/>ค่าตอบแทน", "(8)<br/>ค่าใช้สอย", "(9)<br/>ค่าวัสดุ",
            "(10)<br/>ค่าสาธารณูปโภค", "(11)<br/>อื่น ๆ", "", "", "", ""]],
        [heading(text) for text in ["", "", "", "", "", "", "", "", "", "", "", "",
                                   "รายการ", "จำนวนเงิน", "", "", ""]],
    ]
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
        ("BACKGROUND", (0, 0), (-1, 2), colors.HexColor("#f0f1f2")),
        ("VALIGN", (0, 0), (-1, 2), "MIDDLE"),
        ("VALIGN", (0, 3), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("SPAN", (4, 0), (5, 0)), ("SPAN", (6, 0), (7, 0)),
        ("SPAN", (8, 0), (13, 0)), ("SPAN", (12, 1), (13, 1)),
    ]
    commands += [("SPAN", (col, 0), (col, 2)) for col in [0, 1, 2, 3, 14, 15, 16]]
    commands += [("SPAN", (col, 1), (col, 2)) for col in range(4, 12)]
    for row in ledger_items:
        receipt_date = row.get("receipt_date")
        created_at = row.get("created_at")
        balance = row.get("running_balance")
        rows.append([
            cell(receipt_date.strftime("%m/%Y") if receipt_date else PDF_BLANK, center),
            cell(1 if row.get("is_opening_row") else receipt_date.day if receipt_date else PDF_BLANK, center),
            cell(row.get("description")), cell(row.get("doc_number") or PDF_BLANK),
            amount(row, "bank_income"), amount(row, "bank_expense"), "", "",
            *[amount(row, key) for key in ["cat_7", "cat_8", "cat_9", "cat_10"]],
            cell(row.get("custom_category") or PDF_BLANK), amount(row, "cat_11"), amount(row, "cat_12"),
            cell(f"{_pdf_amount(balance)}" if balance is not None else PDF_BLANK, right),
            cell(created_at.strftime("%d/%m/%Y") if created_at else PDF_BLANK, center),
        ])
    if len(rows) == 3:
        rows.append([cell(PDF_BLANK, center)] + [""] * 16)
        commands.append(("SPAN", (0, 3), (-1, 3)))
    widths = [33, 23, 100, 63, 49, 49, 28, 28, 44, 44, 44, 46, 56, 44, 47, 53, 50]
    widths = [width * doc.width / sum(widths) for width in widths]
    # Include the opening balance, exactly as displayed in the bank receipt column.
    total_income = sum((Decimal(str(row.get("bank_income") or 0)) for row in ledger_items), Decimal("0"))
    total_expense = sum((Decimal(str(row.get("bank_expense") or 0)) for row in ledger_items), Decimal("0"))
    totals = [""] * 17
    totals[3] = cell("รวมทั้งสิ้น", right)
    totals[4] = cell(f"{total_income:,.2f}", right)
    totals[5] = cell(f"{total_expense:,.2f}", right)
    totals[15] = cell(f"{total_income - total_expense:,.2f}", right)
    totals_table = Table([totals], colWidths=widths)
    totals_table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    department = str(setting.department_name or PDF_BLANK)
    info = get_department_info_from_api(setting.department_name)
    custodian_name = str(info.get("custodian") or PDF_BLANK)
    custodian_position = str(info.get("position") or PDF_BLANK)
    head_name, head_position = _get_head_signature(setting=setting)
    signature_style = ParagraphStyle("LedgerSignature", parent=center, fontSize=11, leading=14)
    dotted_line = ".......................................................<br/>"
    signatures = Table([[
        Paragraph(dotted_line + f"({custodian_name})<br/>ตำแหน่ง {custodian_position} - ผู้เก็บรักษาเงินสดย่อย{department}", signature_style),
        Paragraph(dotted_line + f"({head_name})<br/>ตำแหน่ง {head_position}", signature_style),
        Paragraph(dotted_line + "(&nbsp;" + "&nbsp;" * 55 + ")<br/>ตำแหน่ง นักวิชาการเงินและบัญชี", signature_style),
    ]], colWidths=[doc.width * 0.38, doc.width * 0.30, doc.width * 0.32])
    signatures.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 28),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    # Keep totals and all signatures on the final ledger page, outside the grid.
    commands[0] = ("GRID", (0, 0), (-1, len(rows) - 1), 0.4, colors.black)
    footer_index = len(rows)
    rows.append([[totals_table, signatures]] + [""] * 16)
    commands.extend([
        ("SPAN", (0, footer_index), (-1, footer_index)),
        ("NOSPLIT", (0, footer_index), (-1, footer_index)),
        ("LEFTPADDING", (0, footer_index), (-1, footer_index), 0),
        ("RIGHTPADDING", (0, footer_index), (-1, footer_index), 0),
        ("TOPPADDING", (0, footer_index), (-1, footer_index), 0),
        ("BOTTOMPADDING", (0, footer_index), (-1, footer_index), 0),
    ])
    table = LongTable(rows, colWidths=widths, repeatRows=3, splitByRow=1, splitInRow=1)
    table.setStyle(TableStyle(commands))

    def page_header(canvas, document):
        canvas.saveState()
        width, height = landscape(A4)
        title_style = ParagraphStyle("LedgerTitle", parent=center, fontSize=12, leading=14)
        month_label = get_thai_month_year(month_start).split(" ", 1)[1]
        title = Paragraph(
            "<b>ทะเบียนคุมเงินสดย่อย</b><br/>"
            f"{setting.department_name or PDF_BLANK} ประจำเดือน "
            f"{month_label}", title_style)
        _, title_height = title.wrap(document.width, 40)
        title.drawOn(canvas, document.leftMargin, height - 18 - title_height)
        canvas.setFont("Sarabun", 9)
        canvas.drawRightString(width - 20, height - 12, "MT-Petty Cash-003")
        canvas.drawRightString(width - 20, 14, f"หน้า {document.page}")
        canvas.restoreState()

    doc.build([table], onFirstPage=page_header, onLaterPages=page_header)
    return output.getvalue()


def append_petty_cash_monthly_attachments(report_pdf, *, setting, month_start,
                                         ledger_items, fund_requests):
    """Keep the report intact, then append the ledger and each month's request."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    def append(data):
        reader = PdfReader(BytesIO(data))
        for page in reader.pages:
            writer.add_page(page)

    append(report_pdf)
    append(generate_petty_cash_ledger_pdf(setting=setting, month_start=month_start,
                                          ledger_items=ledger_items))
    # Defend the public helper against accidentally attaching other months.
    monthly_requests = [fr for fr in fund_requests if fr.request_date
                        and (fr.request_date.year, fr.request_date.month)
                        == (month_start.year, month_start.month)]
    for fund_request in sorted(monthly_requests, key=lambda fr: (fr.request_date, fr.id)):
        append(generate_fund_request_pdf(fund_request))
    writer.add_metadata({"/Title": f"Petty Cash Monthly Report {month_start:%Y-%m}"})
    output = BytesIO()
    writer.write(output)
    writer.close()
    return output.getvalue()
