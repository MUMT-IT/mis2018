import os
import re
from io import BytesIO
from datetime import datetime
from bahttext import bahttext

from flask import current_app
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Circle, Rect
from .models import db, BankAccountInfo, StaffAccount, PettyCashSetting
from app.models import Org


INTEREST_PERIOD_MONTH_LABELS = {
    "06": "มิถุนายน",
    "12": "ธันวาคม",
}


def _format_interest_period_label(period_value):
    normalized = (period_value or "").strip()
    if not normalized:
        return ""

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

R_PATH = os.path.join(FONTS_DIR, 'THSarabun.ttf')
B_PATH = os.path.join(FONTS_DIR, 'THSarabun Bold.ttf')
I_PATH = os.path.join(FONTS_DIR, 'THSarabun Italic.ttf')
BI_PATH = os.path.join(FONTS_DIR, 'THSarabun BoldItalic.ttf')

DEJAVU_PATH = os.path.join(FONTS_DIR, 'DejaVuSans.ttf')
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
styles.add(ParagraphStyle(name='ThaiJustify', fontName='Sarabun', fontSize=DEFAULT_FONT_SIZE, leading=DEFAULT_LEADING, alignment=TA_JUSTIFY))

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
    firstLineIndent=70  # ปรับระยะย่อหน้าให้เท่ากันทุกพารากราฟที่นี่
))
# =========================================================================
# 2. HELPER FUNCTIONS
# =========================================================================
def get_department_info_from_api(dept_name):
    """ ดึงข้อมูลจาก Service โดยใช้ชื่อหน่วยงาน (dept_name) เป็น Key """
    from .views import get_department_data_service

    dept_data = get_department_data_service(dept_name)
    
    if dept_data:
        head_info = dept_data.get("head_of_department", {})
        controller_info = dept_data.get("account_controller", {})
        return {
            "head": head_info.get("name", "......................................................."),
            "head_position": head_info.get("position", "หัวหน้าฝ่าย"),
            "keeper": controller_info.get("name", "......................................................."),
            "position": controller_info.get("position", "เจ้าหน้าที่")
        }
    
    # กรณีหาชื่อหน่วยงานไม่พบใน mock data
    return {
        "head": ".......................................................",
        "head_position": "หัวหน้าฝ่าย",
        "keeper": ".......................................................",
        "position": "เจ้าหน้าที่"
    }

def get_thai_month_year(date_obj):
    if not date_obj:
        return ""
    th_months = [
        "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
        "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
    ]
    return f"{date_obj.day} {th_months[date_obj.month - 1]} {date_obj.year + 543}"

def draw_dotted_line():
    return Paragraph("....................................................................................................................................................", styles['ThaiCenter'])


def missing_department_notice():
    return "!!! ไม่พบข้อมูลหน่วยงาน !!!"


def _get_user_by_id(user_id):
    if not user_id:
        return None
    return db.session.query(StaffAccount).get(user_id)


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


# =========================================================================
# 3. PDF GENERATION FUNCTIONS
# =========================================================================
from reportlab.platypus import PageBreak  # เพิ่ม Import PageBreak สำหรับขึ้นหน้าใหม่

def generate_fnar02_pdf(ticket):
    """
    สร้างเอกสาร PDF หน้าปกและสัญญาการยืมเงินทดรองจ่าย (แบบฟอร์ม FNAR02)
    - หน้า 1: บันทึกข้อความ ขออนุมัติยืมเงินทดรองจ่าย
    - หน้า 2: สัญญาการยืมเงิน (แบบฟอร์ม FNAR02)
    """
    borrower_name = (
        getattr(ticket, "borrower_name", None)
        or ".........................................................."
    )
    
    borrower_user = getattr(ticket, "borrower_user", None) or _get_user_by_id(getattr(ticket, "borrower_id", None))
    creator_user = getattr(ticket, "creator_user", None) or _get_user_by_id(getattr(ticket, "creator_id", None))

    # 1. ดึงชื่อหน่วยงานจาก org ของผู้ยืมก่อน แล้วค่อย fallback ของเก่า
    borrower_org = getattr(getattr(borrower_user, "personal_info", None), "org", None)
    department_name = (
        getattr(borrower_org, "name", None)
        or getattr(borrower_user, "department", None)
        or getattr(ticket, "borrower_department", None)
        or "........................................"
    )

    # 2. ค้นหาข้อมูลผู้บังคับบัญชา (head_of_department) และผู้ดูแลบัญชี โดยใช้ชื่อหน่วยงาน
    dept_info = get_department_info_from_api(department_name)
    
    # 3. Map ค่าเพื่อนำไปใช้ในเอกสาร
    head_name = dept_info.get("head", ".......................................................")
    head_pos = dept_info.get("head_position", "........................................")

    # แปลงข้อมูลวันที่ และงบประมาณ
    date_thai = get_thai_month_year(ticket.request_date) if hasattr(ticket, 'request_date') and ticket.request_date else "........................................"
    due_date_thai = get_thai_month_year(ticket.due_date) if ticket.due_date else "........................................"
    
    start_date_str = get_thai_month_year(ticket.borrowing_ticket_start_date) if hasattr(ticket, 'borrowing_ticket_start_date') and ticket.borrowing_ticket_start_date else "........................................"
    end_date_str = get_thai_month_year(ticket.borrowing_ticket_end_date) if hasattr(ticket, 'borrowing_ticket_end_date') and ticket.borrowing_ticket_end_date else "........................................"
    
    req_budget = getattr(ticket, 'required_budget', 0) or 0
    amount_numeric = f"{req_budget:,.2f}" if req_budget else "................"
    amount_text = bahttext(req_budget) if req_budget else "........................................................"
    
    bank_account_info = _get_bank_account_info_for_ticket(ticket)
    account_number = (getattr(ticket, 'account_number', '') or '').strip() or (
        bank_account_info.account_number if bank_account_info else '....................................'
    )
    account_name = (
        bank_account_info.thai_name
        if bank_account_info and bank_account_info.thai_name
        else '....................................'
    )
    borrowing_purpose = getattr(ticket, 'borrowing_ticket_purpose', None) or getattr(ticket, 'borrowing_ticket_name', None) or "........................................................"
    
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        leftMargin=72,
        rightMargin=72,
        topMargin=36,
        bottomMargin=36,
        title="บันทึกข้อความ - ขออนุมัติยืมเงินทดรองจ่าย"
    )
    
    story = []

    # =========================================================================
    # PAGE 1: บันทึกข้อความ
    # =========================================================================

    # 1. โลโก้ตรามหาวิทยาลัย (จัดกลาง)
    logo_path = os.path.join(BASE_DIR, 'static', 'logo-MU_black-white-2-1.png')
    if os.path.exists(logo_path):
        from reportlab.platypus import Image
        logo_img = Image(logo_path, width=75, height=75)
        logo_img.hAlign = 'CENTER'
        story.append(logo_img)
    else:
        d = Drawing(75, 75)
        d.add(Circle(37.5, 37.5, 35, strokeColor=colors.black, strokeWidth=1, fillColor=colors.white))
        d.hAlign = 'CENTER'
        story.append(d)

    story.append(Spacer(1, 10))
    from .views import get_department_data_service
    telephone_number = get_department_data_service(department_name).get("telephone_number", "................................")
    
    # 2. ข้อมูลส่วนหัว (ชื่อหน่วยงาน และที่อยู่ชิดขวา)
    header_info_html = f"""
    {department_name}<br/>
    คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>
    999 ถ.พุทธมณฑลสาย4 ศาลายา พุทธมณฑล นครปฐม 73170<br/>
    โทร. {telephone_number}
    """
    story.append(Paragraph(header_info_html, styles['ThaiRight']))
    story.append(Spacer(1, 6))

    # 3. ข้อมูลเลขที่, วันที่, เรื่อง, เรียน
    info_table_data = [
        [Paragraph("<b>ที่</b>", styles['ThaiNormal'])],
        [Paragraph("<b>วันที่</b>", styles['ThaiNormal'])],
        [Paragraph("<b>เรื่อง</b>", styles['ThaiNormal']), Paragraph("ขออนุมัติยืมเงินทดรองจ่าย", styles['ThaiNormal'])],
        [Paragraph("<b>เรียน</b>", styles['ThaiNormal']), Paragraph("คณบดีคณะเทคนิคการแพทย์", styles['ThaiNormal'])],
    ]
    t_info = Table(info_table_data, colWidths=[45, 394])
    t_info.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 15))

    # 4. เนื้อหาบันทึกข้อความ (ย่อหน้า)
    p1_html = f"ด้วย {department_name} มีความประสงค์จะขอยืมเงินทดรองจ่าย จำนวนเงิน {amount_numeric}- บาท ({amount_text}) เพื่อทดรองจ่าย{borrowing_purpose} ตั้งแต่วันที่ {start_date_str} – {end_date_str}"
    story.append(Paragraph(p1_html, styles['ThaiOfficial']))
    story.append(Spacer(1, 12))

    p2_html = f"ทั้งนี้โดยมอบหมายให้ {borrower_name} เป็นผู้ยืมเงิน โดยโปรดโอนเงินเข้าบัญชี เลขที่ {account_number} ชื่อบัญชี {account_name} โดยมีระยะเวลาในการดำเนินภายใน {due_date_thai}"
    story.append(Paragraph(p2_html, styles['ThaiOfficial']))
    story.append(Spacer(1, 12))

    p3_html = "จึงเรียนมาเพื่อโปรดพิจารณาอนุมัติ และลงนามในสัญญาการยืมเงินที่แนบมาพร้อมนี้<br/>ด้วยจักเป็นพระคุณยิ่ง"
    story.append(Paragraph(p3_html, styles['ThaiOfficial']))
    story.append(Spacer(1, 80))

    # 5. ส่วนลงนาม (ชิดขวา/กึ่งกลางขวา)
    sign_html = f"""
    ({head_name})<br/>
    {head_pos}
    """
    p_sign = Paragraph(sign_html, styles['ThaiCenter'])
    
    t_sign = Table([[ "", p_sign ]], colWidths=[237, 250])
    t_sign.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(t_sign)

    # =========================================================================
    # PAGE 2: แบบฟอร์ม FNAR02 (สัญญาการยืมเงิน)
    # =========================================================================
    story.append(PageBreak())  # ขึ้นหน้าใหม่สำหรับหน้า 2

    p_title = Paragraph("<b>สัญญาการยืมเงิน</b><br/><br/>", styles['ThaiCenterBold'])
    p_sub_title = Paragraph("ยื่นต่อ คณบดีคณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล", styles['ThaiCenter'])
    from .views import convert_to_fiscal_year

    fiscal_year_date = (
        getattr(ticket, "request_date", None)
        or getattr(ticket, "approved_at", None)
        or getattr(ticket, "created_at", None)
    )
    fiscal_year_be = convert_to_fiscal_year(fiscal_year_date) + 543 if fiscal_year_date else None
    fiscal_year_label = fiscal_year_be or "................"
    p_no = Paragraph(f"เลขที่................................./{fiscal_year_label}", styles['ThaiCenter'])
    p_due_lbl = Paragraph("<b>วันครบกำหนด</b>", styles['ThaiCenterBold'])
    p_due_line = Paragraph(f"{due_date_thai}", styles['ThaiCenter'])
    
    borrower_position = (
        getattr(borrower_user, "position", None)
        or getattr(ticket, "borrower_position", None)
        or "........................"
    )

    borrower_html = f"""
    ข้าพเจ้า &nbsp;&nbsp;{borrower_name}&nbsp;&nbsp; ตำแหน่ง &nbsp;&nbsp;{borrower_position}<br/>
    สังกัด &nbsp;&nbsp;{department_name} มหาวิทยาลัยมหิดล<br/>
    มีความประสงค์ขอยืมเงินจาก คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>
    เพื่อเป็นค่าใช้จ่ายใน&nbsp;&nbsp;{getattr(ticket, 'borrowing_ticket_purpose', None) or ticket.borrowing_ticket_name or '..................................................................'}
    """
    p_borrower = Paragraph(borrower_html, styles['ThaiNormal'])
    p_amt_txt = Paragraph(f"(ตัวอักษร) ( &nbsp;&nbsp;{amount_text} &nbsp;&nbsp;)", styles['ThaiCenter'])
    p_amt_num = Paragraph(f"(ตัวเลข) &nbsp;&nbsp;{amount_numeric} &nbsp;&nbsp;บาท", styles['ThaiCenter'])

    agreement_html = f"""
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ข้าพเจ้าสัญญาว่าจะปฏิบัติตามระเบียบของมหาวิทยาลัยมหิดลทุกประการ และจะนำใบสำคัญคู่จ่ายที่ถูกต้อง พร้อมทั้ง
    เงินเหลือจ่าย (ถ้ามี) ส่งใช้ภายในกำหนด 15 วัน หลังจากเสร็จสิ้นภารกิจ คือวันที่ &nbsp;{due_date_thai}&nbsp; ถ้าข้าพเจ้าไม่ส่งตามกำหนด ข้าพเจ้ายินยอมให้หักเงินเดือน ค่าจ้าง เบี้ยหวัด บำเหน็จ บำนาญหรือเงินอื่นใด ที่ข้าพเจ้าพึงได้รับจาก
    มหาวิทยาลัยมหิดล ชดใช้จำนวนเงินที่ยืมไปจนครบถ้วนได้ทันที<br/><br/>
    ลงชื่อ ............................................................................. ผู้ยืม &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; วันที่...................................................................<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;( {borrower_name} ) &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
    """
    p_agreement = Paragraph(agreement_html, styles['ThaiNormal'])

    box3_html = f"""
    <b>เสนอ คณบดี</b><br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ได้ตรวจสอบแล้ว เห็นสมควรอนุมัติให้ยืมตามใบยืมฉบับนี้ได้ จำนวนเงิน {amount_numeric} บาท ( {amount_text} )<br/><br/>
    ลงชื่อ ............................................................................. &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; วันที่...................................................................<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;( ....................................................................... )<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;รองคณบดีฝ่ายการคลังและสินทรัพย์
    """
    p_box3 = Paragraph(box3_html, styles['ThaiNormal'])

    p_title_box4 = Paragraph("<b>คำอนุมัติ</b>", styles['ThaiCenterBold'])

    box4_content_html = f"""
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;อนุมัติให้ยืมตามเงื่อนไขข้างต้นได้ เป็นจำนวนเงิน {amount_numeric} บาท ( {amount_text} )<br/><br/>
    ลงชื่อผู้อนุมัติ .................................................................... &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; วันที่...................................................................<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;( ............................................................. )<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;คณบดีคณะเทคนิคการแพทย์
    """
    p_content_box4 = Paragraph(box4_content_html, styles['ThaiNormal'])
    p_box4 = [p_title_box4, p_content_box4]

    p_title_box5 = Paragraph("<b>ใบรับเงิน</b>", styles['ThaiCenterBold'])

    box5_content_html = f"""
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ได้รับเงินยืมจำนวนเงิน {amount_numeric} บาท ( {amount_text} ) ไว้เป็นการถูกต้องแล้ว<br/><br/>
    ลายมือชื่อ ..................................................................... ผู้รับเงิน &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; วันที่...................................................................<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;( {borrower_name} )<br/>
    """
    p_content_box5 = Paragraph(box5_content_html, styles['ThaiNormal'])
    p_box5 = [p_title_box5, p_content_box5]

    form_data = [
        [[p_title, p_sub_title], [p_no, p_due_lbl, p_due_line]],
        [[p_borrower], ""],
        [[p_amt_txt], [p_amt_num]],
        [[p_agreement], ""],
        [[p_box3], ""],
        [p_box4, ""],
        [p_box5, ""]
    ]
    
    master_table = Table(form_data, colWidths=[275, 256])
    master_table.setStyle(TableStyle([
        ('SPAN', (0, 1), (1, 1)),
        ('SPAN', (0, 3), (1, 3)),
        ('SPAN', (0, 4), (1, 4)),
        ('SPAN', (0, 5), (1, 5)),
        ('SPAN', (0, 6), (1, 6)),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    story.append(master_table)
    story.append(Spacer(1, 10))
    p_note = Paragraph("<b>หมายเหตุ:</b> ใบเสร็จแต่ละใบจะต้องมียอดไม่เกิน -100,000- บาท", styles['ThaiNormal'])
    story.append(p_note)

    # สร้างและส่งคืน PDF Bytes
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def generate_petty_claim(claim, document_kind="petty_claim"):
    """
    สร้างเอกสาร PDF สำหรับรายการขออนุมัติเบิกค่าใช้จ่ายของ petty cash claim
    โดยยึดรูปแบบหน้าเดียวตามเอกสารตัวอย่าง:
    - ส่วนหัวกึ่งกลาง + ข้อมูลหน่วยงานชิดขวา
    - ข้อมูลหนังสือ / วันที่ / เรื่อง / เรียน
    - เนื้อความหนังสือราชการ
    - ตารางรายการแบบไม่มีเส้น
    - ส่วนลงนามท้ายหน้า
    """
    from .views import convert_to_fiscal_year, get_department_data_service

    if not claim:
        return b""

    is_ticket_return = document_kind == "ticket_return"

    fund_request = getattr(claim, "fund_request", None)
    setting = getattr(claim, "setting", None)
    requester = getattr(claim, "user", None)

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
        or "........................................"
    )

    dept_info = get_department_info_from_api(department_name)
    head_name = dept_info.get("head", ".......................................................")
    head_pos = dept_info.get("head_position", "หัวหน้าฝ่าย")

    requester_name = (
        getattr(requester, "name", None)
        or getattr(requester, "fullname", None)
        or getattr(claim, "requester_name", None)
        or getattr(fund_request, "requester_name", None)
        or "........................................"
    )

    requester_position = (
        getattr(requester, "position", None)
        or getattr(claim, "requester_position", None)
        or getattr(fund_request, "requester_position", None)
        or "........................................"
    )

    request_date = (
        getattr(fund_request, "approved_at", None)
        or getattr(claim, "created_at", None)
    )
    date_thai = get_thai_month_year(request_date.date()) if request_date else "........................................"

    claim_number = (
        getattr(claim, "claim_number", None)
        or getattr(fund_request, "ticket_number", None)
        or f"PC-{getattr(claim, 'id', '')}"
    )

    claim_date = getattr(claim, "created_at", None)
    claim_date_thai = get_thai_month_year(claim_date.date()) if claim_date else date_thai

    request_purpose = (
        getattr(fund_request, "purpose", None)
        or getattr(fund_request, "borrowing_ticket_name", None)
        or getattr(fund_request, "claim_name", None)
        or ("วัตถุประสงค์ของการขอเบิกค่าใช้จ่าย" if is_ticket_return else "วัตถุประสงค์ของการขอเบิกเงินสดย่อย")
    )
    subject_text = (
        f"ส่งใช้เงินยืม บย. {claim_number}"
        if is_ticket_return
        else f"ขออนุมัติเบิกค่าใช้จ่าย{request_purpose}"
    )

    claim_items = list(getattr(claim, "items", None) or [])
    display_items = [
        item for item in claim_items
        if str(getattr(item, "category_type", "")).strip() != "6"
    ]

    amount_value = float(
        getattr(claim, "total_amount", 0) or sum(
            float(getattr(item, "amount", 0) or 0)
            for item in display_items
        )
    )
    amount_numeric = f"{amount_value:,.2f}" if amount_value else "................"
    amount_text = bahttext(amount_value) if amount_value else "........................................................"

    if claim_items:
        first_receipt = min(
            (getattr(item, "receipt_date", None) for item in claim_items if getattr(item, "receipt_date", None)),
            default=None,
        )
    else:
        first_receipt = None

    if first_receipt:
        start_date_str = get_thai_month_year(first_receipt)
    else:
        start_date_str = date_thai

    if display_items:
        end_receipt = max(
            (getattr(item, "receipt_date", None) for item in display_items if getattr(item, "receipt_date", None)),
            default=None,
        )
    else:
        end_receipt = None
    end_date_str = get_thai_month_year(end_receipt) if end_receipt else date_thai

    bank_account_info = None
    borrowing_ticket = getattr(fund_request, "borrowing_ticket", None) if fund_request else None
    request_account_number = getattr(borrowing_ticket, "account_number", None) if borrowing_ticket else None
    if request_account_number:
        bank_account_info = _get_bank_account_info_for_account_number(request_account_number)
    if not bank_account_info and setting and getattr(setting, "account_number", None):
        bank_account_info = _get_bank_account_info_for_account_number(setting.account_number)

    account_number = (
        (request_account_number or "").strip()
        or (getattr(setting, "account_number", "") or "").strip()
        or (bank_account_info.account_number if bank_account_info else "....................................")
    )
    account_name = (
        bank_account_info.thai_name
        if bank_account_info and bank_account_info.thai_name
        else "...................................."
    )

    fiscal_year_date = request_date or claim_date
    fiscal_year_be = convert_to_fiscal_year(fiscal_year_date.date()) + 543 if fiscal_year_date else None
    fiscal_year_label = str(fiscal_year_be) if fiscal_year_be else "................"

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=55,
        rightMargin=55,
        topMargin=28,
        bottomMargin=30,
        title="Petty Claim Request",
    )

    story = []

    claim_style = ParagraphStyle(
        name="ThaiClaimBody",
        fontName="Sarabun",
        fontSize=16,
        leading=20,
        alignment=TA_JUSTIFY,
        textColor=colors.black,
    )
    claim_body = ParagraphStyle(
        name="ThaiClaimIndentedBody",
        parent=claim_style,
        firstLineIndent=70,
    )
    claim_center = ParagraphStyle(
        name="ThaiClaimCenter",
        fontName="Sarabun",
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.black,
    )
    claim_right = ParagraphStyle(
        name="ThaiClaimRight",
        fontName="Sarabun",
        fontSize=16,
        leading=20,
        alignment=TA_RIGHT,
        textColor=colors.black,
    )
    claim_left = ParagraphStyle(
        name="ThaiClaimLeft",
        fontName="Sarabun",
        fontSize=16,
        leading=20,
        alignment=TA_LEFT,
        textColor=colors.black,
    )
    logo_path = os.path.join(BASE_DIR, 'static', 'logo-MU_black-white-2-1.png')
    if os.path.exists(logo_path):
        from reportlab.platypus import Image
        logo_img = Image(logo_path, width=78, height=78)
        logo_img.hAlign = 'CENTER'
    else:
        logo_img = Drawing(78, 78)
        logo_img.add(Circle(39, 39, 35, strokeColor=colors.black, strokeWidth=1, fillColor=colors.white))

    dept_service_data = get_department_data_service(department_name) or {}
    org = getattr(getattr(requester, "personal_info", None), "org", None)
    telephone_number = (
        getattr(org, "phone_number", None)
        or dept_service_data.get("telephone_number")
        or dept_service_data.get("phone_number")
        or "........................"
    )

    header_right = Paragraph(
        f"{department_name}<br/>"
        f"คณะเทคนิคการแพทย์<br/>"
        f"มหาวิทยาลัยมหิดล<br/>{telephone_number}",
        claim_right,
    )
    header_table = Table([["", logo_img, header_right]], colWidths=[170, 110, 175])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))

    info_data = [
        [Paragraph("ที่", claim_left), Paragraph(getattr(fund_request, "aip_ref_no", None) or claim_number, claim_left)],
        [Paragraph("วันที่", claim_left), Paragraph(date_thai, claim_left)],
        [Paragraph("เรื่อง", claim_left), Paragraph(subject_text, claim_left)],
        [Paragraph("เรียน", claim_left), Paragraph("คณบดีคณะเทคนิคการแพทย์", claim_left)],
    ]
    info_table = Table(info_data, colWidths=[45, 410])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 18))

    if is_ticket_return:
        body_1 = (
            f"ตามหนังสือที่ {getattr(fund_request, 'aip_ref_no', None) or claim_number} "
            f"ลงวันที่ {date_thai} ซึ่งคณะได้อนุมัติให้{request_purpose}นั้น"
        )
        body_2 = (
            f"ในการนี้ {department_name} ดำเนินการดังกล่าวเสร็จสิ้นแล้ว "
            f"จึงขออนุมัติเบิกค่าใช้จ่ายในการ{request_purpose} "
            f"โดยขออนุมัติเบิกค่าใช้จ่ายสำหรับการจัดโครงการดังกล่าว "
            f"เป็นจำนวน {amount_numeric} บาท ({amount_text}) "
            f"โดยมี {requester_name} ตำแหน่ง {requester_position} เป็นผู้ส่งใช้เงินยืม "
            f"โดยมีรายละเอียดดังนี้"
        )
    else:
        body_1 = (
            f"ตามหนังสือที่ {claim_number} ลงวันที่ {date_thai} "
            f"ซึ่งคณะได้รับการอนุมัติให้ดำเนินการแล้ว"
        )
        body_2 = (
            f"ในการนี้ {department_name} ได้ดำเนินการตามวัตถุประสงค์ดังกล่าวเสร็จสิ้นแล้ว "
            f"จึงขออนุมัติเบิกค่าใช้จ่ายในการ{request_purpose} "
            f"เป็นจำนวนเงินรวม {amount_numeric} บาท ({amount_text}) "
            f"โดยมี {requester_name} ตำแหน่ง {requester_position} เป็นผู้ยื่นเรื่อง "
            f"โดยมีรายละเอียดดังนี้"
        )

    story.append(Paragraph(body_1, claim_body))
    story.append(Spacer(1, 8))
    story.append(Paragraph(body_2, claim_body))
    story.append(Spacer(1, 10))

    table_rows = []
    for idx, item in enumerate(display_items, 1):
        table_rows.append([
            Paragraph(f"{idx}.", claim_center),
            Paragraph(
                getattr(item, "description", None)
                or "........................................................",
                claim_style,
            ),
            Paragraph(
                f"{float(getattr(item, 'amount', 0) or 0):,.2f}",
                claim_right,
            ),
        ])

    if table_rows:
        # Keep the item list aligned with the indented first line of the body.
        items_table = Table(table_rows, colWidths=[35, 270, 80])
        items_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 4))

    total_table = Table(
        [[
            Paragraph("รวมทั้งสิ้น", claim_right),
            Paragraph(f"{amount_text}", claim_left),
            Paragraph(f"{amount_numeric} บาท", claim_right),
        ]],
        colWidths=[55, 250, 80],
    )
    total_table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 10))

    if is_ticket_return:
        ref_text = (
            f"โดยเบิกจากเงินปีงบประมาณ {fiscal_year_label} ผลผลิต "
            f"........................................ รหัสศูนย์ต้นทุน "
            f"........................................ หมายเลขรหัสศูนย์ต้นทุน "
            f"........................................ รหัสใบสั่งงานภายใน "
            f"........................................ เอกสารฉบับนี้ส่งคืนบัญชี "
            f"{account_name} บย. เลขที่บัญชี {account_number} "
            f"เพื่อทำการขอเบิกเงินคืนเข้าบัญชีเงินสดย่อยของหน่วยงานต่อไป "
            f"ดังรายละเอียดตามเอกสารที่แนบมาพร้อมนี้"
        )
    else:
        ref_text = (
            f"โดยเบิกจากเงินปีงบประมาณ {fiscal_year_label} "
            f"ผลผลิต ........................................ "
            f"รหัสศูนย์ต้นทุน ........................................ "
            f"รหัสใบสั่งงานภายใน ........................................ "
            f"เอกสารฉบับนี้ส่งคืนบัญชี {account_name} "
            f"เลขที่บัญชี {account_number} เพื่อทำการขอเบิกเงินเข้าบัญชีเงินสดย่อยของหน่วยงานต่อไป "
            f"ดังรายละเอียดตามเอกสารที่แนบมาพร้อมนี้"
        )
    story.append(Paragraph(ref_text, claim_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("จึงเรียนมาเพื่อโปรดพิจารณาอนุมัติจักเป็นพระคุณยิ่ง", claim_center))
    story.append(Spacer(1, 34))

    sign_right = Paragraph(
        f"({head_name})<br/>"
        f"{head_pos}",
        claim_center,
    )
    head_sign_table = Table([["", sign_right]], colWidths=[170, 285])
    head_sign_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
    ]))
    story.append(head_sign_table)
    story.append(Spacer(1, 50))

    approval_sign = Paragraph(
        "อนุมัติ<br/><br/>"
        "(......................)<br/>"
        "คณบดีคณะเทคนิคการแพทย์",
        claim_center,
    )
    approval_sign_table = Table([[approval_sign, ""]], colWidths=[170, 285])
    approval_sign_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
    ]))
    story.append(approval_sign_table)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


generate_petty_claim_pdf = generate_petty_claim


def generate_ticket_return(return_detail):
    """สร้างหนังสือส่งใช้เงินยืมจาก CashAdvanceBorrowingTicket โดยเฉพาะ."""
    if not return_detail:
        return b""

    ticket = getattr(return_detail, "borrowing_ticket", None)
    if not ticket:
        return b""

    from .views import convert_to_fiscal_year, get_department_data_service

    borrower = getattr(ticket, "borrower_user", None)
    borrower_org = getattr(getattr(borrower, "personal_info", None), "org", None)
    department_name = getattr(borrower_org, "name", None) or getattr(borrower, "department", None)
    department_name = department_name or "........................................"
    ticket_number = getattr(ticket, "number", None) or f"บ.ย.-{getattr(ticket, 'id', '')}"
    ticket_date = getattr(ticket, "approved_at", None) or getattr(ticket, "created_at", None)
    aip_ref_no = getattr(ticket, "aip_ref_no", None) or ticket_number
    request_purpose = getattr(ticket, "borrowing_ticket_purpose", None) or "........................................"
    requester_name = getattr(ticket, "borrower_name", None) or getattr(borrower, "name", None) or "........................................"
    requester_position = getattr(borrower, "position", None) or "........................................"
    date_thai = get_thai_month_year(ticket_date.date()) if ticket_date else "........................................"
    return_items = list(getattr(return_detail, "receipt_items", None) or [])
    amount_value = float(getattr(return_detail, "amount_spent", 0) or sum(float(item.amount or 0) for item in return_items))
    amount_numeric = f"{amount_value:,.2f}" if amount_value else "................"
    amount_text = bahttext(amount_value) if amount_value else "........................................................"

    bank_account_info = _get_bank_account_info_for_account_number(getattr(ticket, "account_number", None))
    account_number = getattr(ticket, "account_number", None) or "...................................."
    account_name = (
        bank_account_info.thai_name
        if bank_account_info and bank_account_info.thai_name
        else "...................................."
    )
    fiscal_year = convert_to_fiscal_year(ticket_date.date()) + 543 if ticket_date else None
    fiscal_year_label = str(fiscal_year) if fiscal_year else "................"

    return_body = ParagraphStyle(
        name="ThaiTicketReturnBody",
        fontName="Sarabun",
        fontSize=16,
        leading=20,
        alignment=TA_JUSTIFY,
        firstLineIndent=70,
        textColor=colors.black,
    )
    return_left = ParagraphStyle(
        name="ThaiTicketReturnLeft",
        fontName="Sarabun",
        fontSize=16,
        leading=20,
        alignment=TA_LEFT,
        textColor=colors.black,
    )
    return_center = ParagraphStyle(
        name="ThaiTicketReturnCenter",
        fontName="Sarabun",
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.black,
    )
    return_right = ParagraphStyle(
        name="ThaiTicketReturnRight",
        fontName="Sarabun",
        fontSize=16,
        leading=20,
        alignment=TA_RIGHT,
        textColor=colors.black,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=55,
        rightMargin=55,
        topMargin=28,
        bottomMargin=30,
        title="Ticket Return Request",
    )
    story = []

    logo_path = os.path.join(BASE_DIR, "static", "logo-MU_black-white-2-1.png")
    if os.path.exists(logo_path):
        from reportlab.platypus import Image
        logo = Image(logo_path, width=78, height=78)
        logo.hAlign = "CENTER"
    else:
        logo = Drawing(78, 78)
        logo.add(Circle(39, 39, 35, strokeColor=colors.black, strokeWidth=1, fillColor=colors.white))

    dept_service_data = get_department_data_service(department_name) or {}
    telephone_number = (
        getattr(borrower_org, "phone_number", None)
        or dept_service_data.get("telephone_number")
        or dept_service_data.get("phone_number")
        or "........................"
    )
    header_right = Paragraph(
        f"ชื่อหน่วยงาน {department_name}<br/>"
        f"คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>"
        f"โทรศัพท์ {telephone_number}",
        return_right,
    )
    header_table = Table([["", logo, header_right]], colWidths=[170, 110, 175])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.extend([header_table, Spacer(1, 10)])

    dept_info = get_department_info_from_api(department_name)
    head_name = dept_info.get("head", ".......................................................")
    head_position = dept_info.get("head_position", "หัวหน้าหน่วยงาน")

    info_table = Table([
        [Paragraph("ที่", return_left)],
        [Paragraph("วันที่", return_left)],
        [Paragraph("เรื่อง", return_left), Paragraph(f"ส่งใช้เงินยืม บย. {ticket_number}", return_left)],
        [Paragraph("เรียน", return_left), Paragraph("คณบดีคณะเทคนิคการแพทย์", return_left)],
    ], colWidths=[45, 410])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.extend([info_table, Spacer(1, 18)])

    story.append(Paragraph(
        f"ตามหนังสือที่...............ลงวันที่.................."
        f"ซึ่งคณะได้อนุมัติให้{request_purpose}นั้น",
        return_body,
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"ในการนี้ {department_name} ดำเนินการดังกล่าวเสร็จสิ้นแล้ว "
        f"จึงขออนุมัติเบิกค่าใช้จ่ายในการ{request_purpose} "
        f"โดยขออนุมัติเบิกค่าใช้จ่ายสำหรับการจัดโครงการดังกล่าว "
        f"เป็นจำนวน {amount_numeric} บาท ({amount_text}) "
        f"โดยมีรายละเอียดดังนี้",
        return_body,
    ))
    story.append(Spacer(1, 10))

    item_rows = []
    for index, item in enumerate(return_items, 1):
        item_rows.append([
            Paragraph(f"{index}.", return_center),
            Paragraph(item.description or "........................................................", return_left),
            Paragraph(f"{float(item.amount or 0):,.2f}", return_right),
        ])
    if item_rows:
        item_table = Table(item_rows, colWidths=[35, 270, 80])
        item_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.extend([item_table, Spacer(1, 4)])

    total_table = Table([[
        Paragraph("รวมทั้งสิ้น ", return_right),
        Paragraph(amount_text, return_left),
        Paragraph(f"{amount_numeric} บาท", return_right),
    ]], colWidths=[55, 250, 80])
    total_table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.extend([total_table, Spacer(1, 10)])

    story.append(Paragraph(
        f"โดยเบิกจากเงินปีงบประมาณ {fiscal_year_label} ผลผลิต "
        f"........................................ รหัสศูนย์ต้นทุน "
        f"........................................ หมายเลขรหัสศูนย์ต้นทุน "
        f"........................................ รหัสใบสั่งงานภายใน "
        f"........................................ เอกสารฉบับนี้ส่งคืนบัญชีเงินยืม "
        f"บย.{ticket_number} "
        f"เพื่อทำการขอเบิกเงินคืนเข้าบัญชีเงินสดย่อยของหน่วยงานต่อไป "
        f"ดังรายละเอียดตามเอกสารที่แนบมาพร้อมนี้",
        return_left,
    ))
    story.extend([
        Spacer(1, 12),
        Paragraph("จึงเรียนมาเพื่อโปรดพิจารณาอนุมัติจักเป็นพระคุณยิ่ง", return_center),
        Spacer(1, 34),
    ])

    head_sign = Table([["", Paragraph(f"({head_name})<br/>{head_position}", return_center)]], colWidths=[170, 285])
    head_sign.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(head_sign)
    story.append(Spacer(1, 50))
    approval_sign = Table([[Paragraph("อนุมัติ<br/><br/>(......................)<br/>คณบดีคณะเทคนิคการแพทย์", return_center), ""]], colWidths=[170, 285])
    approval_sign.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(approval_sign)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


generate_ticket_return_pdf = generate_ticket_return

def generate_fund_request_pdf(fund_request):
    """
    ฟังก์ชันสร้างเอกสาร PDF ใบยืมเงินสดย่อย/ใบเบิกเงินสดย่อย
    """
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=35,
        rightMargin=35,
        topMargin=15,
        bottomMargin=15,
        title=f"MT-Petty-Cash-02_{fund_request.id}"
    )
    
    story = []
    
    form_type = str(fund_request.form_type or "")
    is_type_31 = form_type == "31"
    is_type_32 = form_type == "32"
    borrowing_ticket = getattr(fund_request, "borrowing_ticket", None)

    date_thai = get_thai_month_year(fund_request.request_date)
    requester_user = _get_user_by_id(getattr(fund_request, "requester_id", None))
    requester = getattr(requester_user, "name", "") or ""
    requester_pos = getattr(requester_user, "position", "") or ""
    purpose = fund_request.purpose or ""
    ticket_number = fund_request.ticket_number or ""

    if is_type_32 and borrowing_ticket:
        requester = borrowing_ticket.borrower_name or requester
        requester_user = getattr(borrowing_ticket, "borrower_user", None) or _get_user_by_id(getattr(borrowing_ticket, "borrower_id", None))
        requester_pos = getattr(requester_user, "position", "") or requester_pos
        purpose = f"เบิกเงินยืมผ่านบัญชีเงินสดย่อยตามใบยืมเงิน บ.ย. {borrowing_ticket.number}"
        if borrowing_ticket.approved_at:
            date_thai = get_thai_month_year(borrowing_ticket.approved_at.date())
    
    # Resolve the organization by its stable ID; department_name is legacy display data.
    org = db.session.query(Org).get(getattr(fund_request, "org_id", None))
    dept_lookup = getattr(fund_request, "org_id", None) or getattr(org, "name", None)
    dept_info = get_department_info_from_api(dept_lookup)
    head_name = dept_info.get("head", ".......................................................")
    head_pos = dept_info.get("head_position", "หัวหน้าฝ่าย")
    keeper_name = dept_info.get("keeper", ".......................................................")
    keeper_pos = dept_info.get("position", "เจ้าหน้าที่")
    
    amount_val = float(fund_request.amount or (borrowing_ticket.required_budget if borrowing_ticket else 0) or 0)
    amount_str = f"{amount_val:,.2f}" if amount_val > 0 else "                  "
    amount_text_th = bahttext(amount_val) if amount_val > 0 else "................................................................................"

    # Header & Logo
    logo_path = os.path.join(BASE_DIR, 'static', 'logo-MU_black-white-2-1.png')
    if os.path.exists(logo_path):
        from reportlab.platypus import Image
        logo_flowable = Image(logo_path, width=70, height=70)
    else:
        d = Drawing(100, 100)
        d.add(Circle(50, 50, 40, strokeColor=colors.black, strokeWidth=1, fillColor=colors.white))
        logo_flowable = d

    dept_display = getattr(org, "name", None) or missing_department_notice()
    form_title_text = "ใบยืมเงินสดย่อย/ใบเบิกเงินสดย่อย"
    header_title = Paragraph(
        f"<b>{form_title_text}</b><br/>"
        f"<b>{dept_display}</b>", 
        styles['ThaiCenterBold']
    )
    header_code = Paragraph("MT-Petty Cash-02", styles['ThaiSmallRight'])
    
    header_table = Table([[logo_flowable, header_title, header_code]], colWidths=[60, 365, 100])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4))
    story.append(draw_dotted_line())
    story.append(Spacer(1, 4))

    # ส่วนที่ 1 ใบยืมเงินสดย่อย
    sec1_title_l = Paragraph("<b>ส่วนที่ 1 ใบยืมเงินสดย่อย</b>", styles['ThaiBold'])
    sec1_title_r = Paragraph(
        f"เลขที่ใบเบิกเงิน {ticket_number}<br/>"
        f"วันที่ {date_thai}", 
        styles['ThaiSmallRight']
    )
    sec1_header_table = Table([[sec1_title_l, sec1_title_r]], colWidths=[250, 275])
    sec1_header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(sec1_header_table)
    story.append(Spacer(1, 2))

    sec1_body = Paragraph(
        f"ข้าพเจ้า {requester if not is_type_31 else '........................'} ตำแหน่ง {requester_pos  if not is_type_31 else '........................'} มีความประสงค์ขอยืมเงินสดย่อย<br/>"
        f"เพื่อ{purpose  if not is_type_31 else '........................'} มีรายละเอียดดังนี้",
        styles['ThaiNormal']
    )
    story.append(sec1_body)
    story.append(Spacer(1, 4))

    # ==================== ตารางรายการ ====================
    table_data = [
        [
            Paragraph("<b>ลำดับ</b>", styles['ThaiCenterBold']),
            Paragraph("<b>รายการ</b>", styles['ThaiCenterBold']),
            Paragraph("<b>จำนวนเงิน (บาท)</b>", styles['ThaiCenterBold'])
        ]
    ]

    items = fund_request.items if hasattr(fund_request, 'items') and fund_request.items else []
    total_amount = 0.0

    if is_type_32 and not items and borrowing_ticket:
        ticket_no = getattr(borrowing_ticket, "number", None) or "-"
        ticket_amount = float(borrowing_ticket.required_budget or amount_val or 0)
        table_data.append([
            Paragraph("1", styles['ThaiCenter']),
            Paragraph(f"เบิกเงินยืมผ่านบัญชีเงินสดย่อยตามใบยืมเงิน บ.ย. {ticket_no}", styles['ThaiNormal']),
            Paragraph(f"{ticket_amount:,.2f}", styles['ThaiRight'])
        ])
        total_amount = ticket_amount
    elif not is_type_31 and items:
        for idx, item in enumerate(items, 1):
            amt = float(item.amount or 0)
            total_amount += amt
            table_data.append([
                Paragraph(str(idx), styles['ThaiCenter']),
                Paragraph(item.description or "", styles['ThaiNormal']),
                Paragraph(f"{amt:,.2f}", styles['ThaiRight'])
            ])
    else:
        table_data.append([
            Paragraph("&nbsp;", styles['ThaiCenter']),
            Paragraph("&nbsp;", styles['ThaiNormal']),
            Paragraph("&nbsp;", styles['ThaiRight'])
        ])

    table_data.append([
        Paragraph("<b>รวมเป็นเงินทั้งสิ้น</b>", styles['ThaiRightBold']),
        "",
        Paragraph(f"<b>{total_amount:,.2f}</b>", styles['ThaiRightBold'])
    ])

    last_row_idx = len(table_data) - 1

    item_table = Table(table_data, colWidths=[50, 350, 120])
    item_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('SPAN', (0, last_row_idx), (1, last_row_idx)),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    
    story.append(item_table)
    story.append(Spacer(1, 15))

    sig_box_data_1 = [
        [
            Paragraph(f"ลงชื่อผู้ขอยืม<br/><br/>.......................................................<br/>( {requester} )<br/>ตำแหน่ง {requester_pos}<br/>วันที่ .................................................", styles['ThaiCenter']),
            Paragraph(f"ลงชื่อผู้เก็บรักษาเงินสดย่อย<br/><br/>.......................................................<br/>( {keeper_name} )<br/>ตำแหน่ง {keeper_pos}<br/>วันที่ .................................................", styles['ThaiCenter']),
            Paragraph(f"ลงชื่อผู้อนุมัติให้ยืม<br/><br/>.......................................................<br/>( {head_name} )<br/>ตำแหน่ง {head_pos}<br/>วันที่ .................................................", styles['ThaiCenter'])
        ]
    ]
    t_sig1 = Table(sig_box_data_1, colWidths=[175, 175, 175])
    t_sig1.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_sig1)
    story.append(Spacer(1, 4))
    story.append(draw_dotted_line())
    story.append(Spacer(1, 4))

    # ส่วนที่ 2 ใบเบิกเงิน
    # =========================================================================
    # ส่วนที่ 2 ใบเบิกเงิน (เงื่อนไข dynamic ตาม form_type)
    # =========================================================================
    sec2_title_l = Paragraph("<b>ส่วนที่ 2 ใบเบิกเงิน</b>", styles['ThaiBold'])
    sec2_title_r = Paragraph(
        f"เลขที่ใบเบิกเงิน {ticket_number}<br/>"
        f"วันที่ {date_thai}", 
        styles['ThaiSmallRight']
    )
    sec2_header_table = Table([[sec2_title_l, sec2_title_r]], colWidths=[250, 275])
    sec2_header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(sec2_header_table)
    story.append(Spacer(1, 2))

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
        else (request_account_number or "........................")
    )
    acc_name = (
        bank_account_info.thai_name
        if bank_account_info and bank_account_info.thai_name
        else "........................"
    )
    chk_box = '<font name="DejaVuSans">&#x2610;</font>'
    chk_box_checked = '<font name="DejaVuSans">&#x2611;</font>'

    if not is_type_31:
        box_petty_cash = chk_box_checked
        p_dept_1 = dept_name
        p_acc_1 = acc_num
        p_amt_str_1 = f"-{amount_str}-"
        p_amt_text_1 = amount_text_th
        p_borrow_no = ticket_number
        p_borrow_date = get_thai_month_year(borrowing_ticket.approved_at.date()) if is_type_32 and borrowing_ticket and borrowing_ticket.approved_at else date_thai
        p_borrower_name = requester

        box_interest = chk_box
        box_june = chk_box
        box_dec = chk_box
        p_period_yr = date_thai.split()[-1] if date_thai else "................"
        p_dept_2 = "........................"
        p_acc_2 = "........................"
        p_amt_str_2 = "........................"
        p_amt_text_2 = "........................"

    else:
        box_petty_cash = chk_box
        p_dept_1 = "........................"
        p_acc_1 = acc_num
        p_amt_str_1 = "........................"
        p_amt_text_1 = "........................"
        p_borrow_no = ticket_number
        p_borrow_date = "........................"
        p_borrower_name = "........................"

        # ส่วนดอกเบี้ยเติมข้อมูลจริง
        box_interest = chk_box_checked
        
        # รองรับทั้งค่าเก่าแบบ "มิถุนายน พ.ศ. 2567" และค่าใหม่แบบ "06/2567"
        period_value = str(fund_request.period_year or "")
        period_label = _format_interest_period_label(period_value)

        # เช็คการติ๊กเลือกงวด
        box_june = chk_box_checked if period_value.startswith("06/") or "มิถุนายน" in period_label else chk_box
        box_dec = chk_box_checked if period_value.startswith("12/") or "ธันวาคม" in period_label else chk_box

        # สกัดเฉพาะเลขปี พ.ศ. ออกมาจากสตริง (เช่น "2567") หากไม่มีจะใช้เส้นประ
        year_match = re.search(r'\d{4}', period_label or period_value)
        p_period_yr = year_match.group(0) if year_match else "................"

        p_dept_2 = dept_name
        p_acc_2 = acc_num
        p_amt_str_2 = f"-{amount_str}-"
        p_amt_text_2 = amount_text_th

    # ประกอบ Text ในรูปแบบเดียวกันทั้งหมด
    sec2_body_text = Paragraph(
        f"<b>เรียน</b> &nbsp;&nbsp;{head_pos}<br/>"
        f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{box_petty_cash} ขออนุมัติเบิกเงินสดย่อยจากบัญชี{acc_name} "
        f"เลขที่บัญชี {p_acc_1} เป็นจำนวนเงิน {p_amt_str_1} บาท "
        f"({p_amt_text_1}) ตามใบยืมเงินสดย่อยเลขที่ {p_borrow_no} "
        f"ลงวันที่ {p_borrow_date} โดยมี {p_borrower_name} เป็นผู้ยืม<br/>"
        f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{box_interest} ขออนุมัติเบิกดอกเบี้ย &nbsp;{box_june} งวดเดือน มิถุนายน พ.ศ. {p_period_yr} "
        f"&nbsp;{box_dec} งวดเดือน ธันวาคม พ.ศ. {p_period_yr} จากบัญชี {p_dept_2} "
        f"เลขที่บัญชี {p_acc_1} ชื่อบัญชี{acc_name} เป็นจำนวนเงิน {p_amt_str_2} บาท ({p_amt_text_2}) "
        f"และขออนุมัตินำส่งดอกเบี้ยเข้าเป็นเงินรายได้คณะฯ โอนเข้าบัญชี เลขที่ 016-300-325-6 "
        f"ชื่อบัญชีมหาวิทยาลัยมหิดล",
        styles['ThaiJustify']
    )
    story.append(sec2_body_text)
    story.append(Spacer(1, 6))

    sig_box_data_2 = [
        [
            Paragraph(f"ลงชื่อผู้เก็บรักษาเงินสดย่อย<br/><br/>.......................................................<br/>( {keeper_name} )<br/>ตำแหน่ง {keeper_pos}", styles['ThaiCenter']),
            Paragraph(f"ลงชื่อผู้อนุมัติ<br/><br/>.......................................................<br/>( {head_name} )<br/>ตำแหน่ง {head_pos}", styles['ThaiCenter'])
        ]
    ]
    t_sig2 = Table(sig_box_data_2, colWidths=[200, 200])
    t_sig2.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    t_sig2_container = Table([[t_sig2]], colWidths=[525])
    t_sig2_container.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_sig2_container)
    story.append(Spacer(1, 8))

    footer_text = Paragraph(
        # "แบบฟอร์ม MT-Petty Cash-02 ใช้สำหรับขออนุมัติยืมเงินและเบิกถอนเงินสำหรับดำเนินงานภายในภาควิชาฯ/ศูนย์ฯ/งานฯ "
        # "และเบิกถอนดอกเบี้ย ทำรายการเป็นครั้งๆ",
        "หมายเหตุ: ใบเสร็จแต่ละใบจะต้องมียอดไม่เกิน -20,000- บาท",
        styles['ThaiFooter']
    )
    story.append(footer_text)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
