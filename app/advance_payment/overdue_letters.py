"""One-page Thai debt reminder letters for overdue borrowing tickets."""

from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path

from bahttext import bahttext
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .date_utils import thai_long_date


STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
FONT_REGULAR = "OverdueSarabun"
FONT_BOLD = "OverdueSarabunBold"
LOGO_PATH = STATIC_DIR / "img" / "logo-MU_black-white-2-1.png"


def _register_fonts():
    registered = set(pdfmetrics.getRegisteredFontNames())
    if FONT_REGULAR not in registered:
        pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(STATIC_DIR / "fonts" / "THSarabunNew.ttf")))
    if FONT_BOLD not in registered:
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(STATIC_DIR / "fonts" / "THSarabunNewBold.ttf")))
    pdfmetrics.registerFontFamily(FONT_REGULAR, normal=FONT_REGULAR, bold=FONT_BOLD)


def build_reminder_letter(ticket, *, as_of, remaining_amount, dean_name=None):
    """Capture the values printed on a letter at generation time."""
    amount = Decimal(str(remaining_amount)).quantize(Decimal("0.01"))
    if not ticket.due_date or ticket.due_date >= as_of or amount <= 0:
        raise ValueError("Only overdue tickets with an outstanding balance can be printed")
    number = (ticket.number or "").strip()
    borrower_name = (ticket.borrower_name or "").strip()
    if not number or not borrower_name:
        raise ValueError(f"Ticket {ticket.id} has no number or borrower name")
    approval_date = ticket.borrowing_approval_date
    received_date = ticket.approved_at.date() if ticket.approved_at else None
    if approval_date:
        date_phrase = f"ลงวันที่ {thai_long_date(approval_date)}"
    elif received_date:
        # Older imports record the actual payment date, not a contract date.
        date_phrase = f"ซึ่งได้รับเงินยืมเมื่อวันที่ {thai_long_date(received_date)}"
    else:
        date_phrase = ""
    return {
        "ticket_number": number,
        "borrower_name": borrower_name,
        "date_phrase": date_phrase,
        "due_date": thai_long_date(ticket.due_date),
        "as_of": thai_long_date(as_of),
        "overdue_days": (as_of - ticket.due_date).days,
        "remaining_amount": amount,
        "amount_text": bahttext(amount),
        "dean_name": (dean_name or "").strip(),
    }


def generate_overdue_reminders_pdf(letters):
    """Return one printable A4 page per borrowing contract."""
    if not letters:
        raise ValueError("No overdue letters to generate")
    _register_fonts()
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=52, leftMargin=52,
        topMargin=35, bottomMargin=38,
        title="หนังสือเร่งรัดการส่งใช้เงินยืม",
    )
    normal = ParagraphStyle(
        "ReminderNormal", fontName=FONT_REGULAR, fontSize=15, leading=21,
        textColor=colors.black, wordWrap="CJK",
    )
    right = ParagraphStyle("ReminderRight", parent=normal, alignment=TA_RIGHT)
    centered = ParagraphStyle("ReminderCenter", parent=normal, alignment=TA_CENTER)
    body = ParagraphStyle(
        "ReminderBody", parent=normal, alignment=TA_JUSTIFY,
        firstLineIndent=32, spaceAfter=9,
    )
    story = []
    for index, letter in enumerate(letters):
        if index:
            story.append(PageBreak())
        logo = Image(str(LOGO_PATH), width=62, height=62)
        logo.hAlign = "CENTER"
        story.extend([logo, Spacer(1, 2)])
        story.append(Paragraph("งานคลังและพัสดุ<br/>คณะเทคนิคการแพทย์ มหาวิทยาลัยมหิดล<br/>โทร. 0-2441-4372-5 ต่อ 2820, 2830", right))
        story.append(Spacer(1, 18))
        story.append(Paragraph("ที่ ............................................................", normal))
        story.append(Paragraph(f"วันที่ {escape(letter['as_of'])}", normal))
        story.append(Paragraph("เรื่อง&nbsp;&nbsp;ขอความอนุเคราะห์เร่งรัดการส่งใช้เงินยืม", normal))
        story.append(Paragraph(f"เรียน&nbsp;&nbsp;{escape(letter['borrower_name'])}", normal))
        story.append(Spacer(1, 17))
        story.append(Paragraph(
            "ตามที่ คณะเทคนิคการแพทย์ ได้มีการจ่ายเงินยืมตามสัญญาการยืมเงินเลขที่ "
            f"{escape(letter['ticket_number'])} {escape(letter['date_phrase'])} "
            f"ซึ่งได้ครบกำหนดส่งคืนเมื่อวันที่ {escape(letter['due_date'])} แล้วนั้น",
            body,
        ))
        story.append(Paragraph(
            "บัดนี้ได้ล่วงเลยกำหนดระยะเวลาการส่งคืนเงินดังกล่าว ณ วันที่ "
            f"{escape(letter['as_of'])} เป็นระยะเวลา {letter['overdue_days']} วัน "
            "ตามสัญญาที่ท่านลงนามไว้ (ตามเอกสารแนบ) โดยมียอดคงค้างที่ต้องส่งใช้ "
            f"เป็นจำนวนเงินรวมทั้งสิ้น {letter['remaining_amount']:,.2f} บาท "
            f"({escape(letter['amount_text'])})",
            body,
        ))
        story.append(Paragraph(
            "ทางคณะเทคนิคการแพทย์ จึงใคร่ขอให้ท่านโปรดส่งคืนภายใน 15 วันหลังจากได้รับหนังสือฉบับนี้ "
            "หากไม่สามารถคืนภายใน 60 วัน หลังครบกำหนดตามสัญญา ต้องทำหนังสือชี้แจงเหตุผลที่ชัดเจน"
            "และส่งล่วงหน้า 7 วัน หากไม่ดำเนินการตามกำหนด คณะฯ จะดำเนินการหักเงินเดือน ค่าจ้าง "
            "เบี้ยหวัด บำเหน็จ บำนาญ หรือเงินอื่นใดตามที่ท่านได้ลงนามในสัญญาการยืมเงิน "
            "ทั้งนี้หากท่านดำเนินการส่งใช้เงินยืมแล้วในระหว่างการจัดส่งหนังสือฉบับนี้ "
            "ต้องขออภัยมา ณ โอกาสนี้",
            body,
        ))
        story.append(Paragraph("จึงเรียนมาเพื่อโปรดดำเนินการด้วย จักเป็นพระคุณยิ่ง", body))
        story.append(Spacer(1, 58))
        signature = escape(letter["dean_name"]) if letter["dean_name"] else "...................................................."
        story.append(Paragraph(f"({signature})", centered))
        story.append(Paragraph("คณบดีคณะเทคนิคการแพทย์", centered))
    doc.build(story)
    return output.getvalue()
