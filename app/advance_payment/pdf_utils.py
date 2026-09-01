import os
import re
from io import BytesIO
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
from .models import db, BankAccountInfo, StaffAccount


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

    # 1. ดึงชื่อหน่วยงานจากผู้ยืม
    department_name = (
        getattr(borrower_user, "department", None)
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
    requester = fund_request.requester_name or ""
    requester_pos = fund_request.requester_position or ""
    purpose = fund_request.purpose or ""

    if is_type_32 and borrowing_ticket:
        requester = borrowing_ticket.borrower_name or requester
        requester_user = getattr(borrowing_ticket, "borrower_user", None) or _get_user_by_id(getattr(borrowing_ticket, "borrower_id", None))
        requester_pos = getattr(requester_user, "position", "") or requester_pos
        purpose = f"เบิกเงินยืมผ่านบัญชีเงินสดย่อยตามใบยืมเงิน บ.ย. {borrowing_ticket.number}"
        if borrowing_ticket.approved_at:
            date_thai = get_thai_month_year(borrowing_ticket.approved_at.date())
    
    dept_info = get_department_info_from_api(fund_request.department_name)
    head_name = dept_info.get("head", ".......................................................")
    head_pos = dept_info.get("head_position", "หัวหน้าฝ่าย")
    keeper_name = dept_info.get("keeper", ".......................................................")
    keeper_pos = dept_info.get("position", "เจ้าหน้าที่")
    
    if hasattr(fund_request, 'account_controller_name') and fund_request.account_controller_name:
        keeper_name = fund_request.account_controller_name

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

    dept_display = fund_request.department_name or missing_department_notice()
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
        f"เลขที่ใบเบิกเงิน...................<br/>"
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
        f"เลขที่ใบเบิกเงิน...................<br/>"
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

    dept_name = fund_request.department_name or missing_department_notice()
    bank_account_info = _get_bank_account_info_for_account_number(fund_request.account_number)
    acc_num = (
        bank_account_info.account_number
        if bank_account_info and bank_account_info.account_number
        else (fund_request.account_number or "........................")
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
        p_borrow_no = "........................"
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
        p_acc_1 = "........................"
        p_amt_str_1 = "........................"
        p_amt_text_1 = "........................"
        p_borrow_no = "........................"
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
