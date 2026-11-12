"""Generate the cash-advance receivables report in the source XLS layout."""

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

import xlwt


AMOUNT_KEYS = ("borrowed", "repaid", "before_pending", "pending", "remaining")
CENT = Decimal("0.01")
THAI_MONTHS = ("มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
               "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม")
SHORT_MONTHS = ("มค.", "กพ.", "มีค.", "เมย.", "พค.", "มิย.",
                "กค.", "สค.", "กย.", "ตค.", "พย.", "ธค.")
HEADERS = ("วันที่ยืม", "วันที่ครบกำหนด", "ชื่อผู้ยืม", "", "เลขที่ยืม",
           "จำนวนเงินยืม", "ส่งใช้เงินยืม", "คงเหลือ", "เอกสารระหว่าง",
           "คงเหลือสุทธิ", "วัตถุประสงค์")


def build_receivable_row(ticket, *, approved_amount, pending_amount,
                         historical_repaid=0, historical_pending=0,
                         first_name_with_title=None, last_name=None,
                         borrow_text=None):
    """Combine source balances with approved and pending system returns."""
    borrowed = Decimal(str(ticket.required_budget)).quantize(CENT)
    repaid = (Decimal(str(historical_repaid)) + Decimal(str(approved_amount))).quantize(CENT)
    pending = (Decimal(str(historical_pending)) + Decimal(str(pending_amount))).quantize(CENT)
    before_pending = borrowed - repaid
    remaining = before_pending - pending
    if min(borrowed, repaid, pending, before_pending, remaining) < 0:
        raise ValueError(f"Invalid receivable balance for ticket {ticket.number}")
    borrower = (ticket.borrower_name or "").strip()
    if first_name_with_title is None and last_name is None:
        first_name_with_title, separator, last_name = borrower.rpartition(" ")
        if not separator:
            first_name_with_title, last_name = borrower, ""
    return {
        "number": ticket.number or "",
        "first_name_with_title": first_name_with_title or "",
        "last_name": last_name or "",
        "borrow_text": borrow_text,
        "borrowed_on": ticket.approved_at.date() if ticket.approved_at else None,
        "due_on": ticket.due_date,
        "purpose": ticket.borrowing_ticket_purpose or "",
        "borrowed": borrowed, "repaid": repaid,
        "before_pending": before_pending, "pending": pending,
        "remaining": remaining,
    }


def _style(*, bold=False, size=14, horizontal=xlwt.Alignment.HORZ_LEFT,
           num_format=None, bordered=False, wrap=False,
           top_border=True, bottom_border=True):
    style = xlwt.XFStyle()
    font = xlwt.Font()
    font.name = "TH SarabunPSK"
    font.height = size * 20
    font.bold = bold
    style.font = font
    alignment = xlwt.Alignment()
    alignment.horz = horizontal
    alignment.vert = xlwt.Alignment.VERT_CENTER
    alignment.wrap = int(wrap)
    style.alignment = alignment
    borders = xlwt.Borders()
    if bordered:
        borders.left = xlwt.Borders.THIN
        borders.right = xlwt.Borders.THIN
        borders.top = xlwt.Borders.THIN if top_border else xlwt.Borders.NO_LINE
        borders.bottom = xlwt.Borders.THIN if bottom_border else xlwt.Borders.NO_LINE
    style.borders = borders
    if num_format:
        style.num_format_str = num_format
    return style


def _write_total(sheet, row_index, label, totals, text_style, number_style):
    for col in (0, 1, 4, 10):
        sheet.write(row_index, col, "", text_style)
    sheet.write_merge(row_index, row_index, 2, 3, label, text_style)
    for col, key in enumerate(AMOUNT_KEYS, start=5):
        sheet.write(row_index, col, float(totals[key]), number_style)


def generate_receivables_xls(rows, *, report_date: date) -> bytes:
    """Return a BIFF8 XLS with the source title, headers, columns and totals."""
    rows = list(rows)
    if len(rows) + (len(rows) // 22) * 3 + 10 > 65536:
        raise ValueError("รายการมากเกินขนาดที่ไฟล์ .xls รองรับ")
    book = xlwt.Workbook(encoding="utf-8")
    sheet = book.add_sheet(f"{SHORT_MONTHS[report_date.month - 1]}{(report_date.year + 543) % 100:02d}")
    sheet.show_grid = False
    sheet.portrait = False
    sheet.fit_width_to_pages = 1
    sheet.set_panes_frozen(True)
    sheet.set_horz_split_pos(4)
    for col, width in enumerate((2218, 4494, 12572, 5660, 2503, 3840,
                                 3384, 3214, 11804, 3640, 30236)):
        sheet.col(col).width = width
    title_style = _style(size=16)
    header_style = _style(bold=True, horizontal=xlwt.Alignment.HORZ_CENTER,
                          bordered=True, wrap=True)
    split_header_top_style = _style(
        bold=True, horizontal=xlwt.Alignment.HORZ_CENTER,
        bordered=True, bottom_border=False, wrap=True,
    )
    split_header_bottom_style = _style(
        bold=True, horizontal=xlwt.Alignment.HORZ_CENTER,
        bordered=True, top_border=False, wrap=True,
    )
    text_style = _style(bordered=True)
    number_style = _style(horizontal=xlwt.Alignment.HORZ_RIGHT,
                          num_format="#,##0.00", bordered=True)
    due_style = _style(horizontal=xlwt.Alignment.HORZ_CENTER,
                       num_format="DD/MM/YYYY", bordered=True)
    total_style = _style(bold=True, bordered=True)
    total_number_style = _style(bold=True, horizontal=xlwt.Alignment.HORZ_RIGHT,
                                num_format="#,##0.00", bordered=True)
    signature_style = _style()
    for index, height in enumerate((480, 540, 480, 480)):
        sheet.row(index).height = height
    sheet.write_merge(0, 0, 0, 13, "รายงานลูกหนี้เงินยืม", title_style)
    sheet.write_merge(1, 1, 0, 13,
                      f"ณ วันที่  {report_date.day}  {THAI_MONTHS[report_date.month - 1]}  {report_date.year + 543}",
                      title_style)
    for col in (0, 2, 4, 5, 6, 7, 9, 10):
        sheet.write_merge(2, 3, col, 3 if col == 2 else col, HEADERS[col], header_style)
    sheet.write(2, 1, HEADERS[1], split_header_top_style)
    sheet.write(3, 1, "คืนเงินยืม", split_header_bottom_style)
    sheet.write(2, 8, HEADERS[8], split_header_top_style)
    sheet.write(3, 8, "รอเบิก", split_header_bottom_style)
    totals = {key: Decimal("0.00") for key in AMOUNT_KEYS}
    row_index = 4
    for item_index, item in enumerate(rows):
        if item_index and item_index % 22 == 0:
            for col in range(11):
                sheet.write(row_index, col, "", text_style)
            row_index += 1
            _write_total(sheet, row_index, "รวมเงิน", totals, total_style, total_number_style)
            row_index += 1
            _write_total(sheet, row_index, "ยอดยกมา", totals, total_style, total_number_style)
            row_index += 1
        sheet.row(row_index).height = 522
        borrowed_on = item["borrowed_on"]
        borrow_text = item.get("borrow_text") or (
            f"{SHORT_MONTHS[borrowed_on.month - 1]}{borrowed_on.day}"
            if borrowed_on else ""
        )
        for col, value in ((0, borrow_text), (2, item["first_name_with_title"]),
                           (3, item["last_name"]), (4, item["number"]),
                           (10, item["purpose"])):
            sheet.write(row_index, col, str(value or ""), text_style)
        due_on = item["due_on"]
        if due_on:
            sheet.write(row_index, 1, datetime(due_on.year + 543, due_on.month, due_on.day), due_style)
        else:
            sheet.write(row_index, 1, "", text_style)
        for col, key in enumerate(AMOUNT_KEYS, start=5):
            amount = Decimal(str(item[key])).quantize(CENT)
            totals[key] += amount
            sheet.write(row_index, col, float(amount), number_style)
        row_index += 1
    for col in range(11):
        sheet.write(row_index, col, "", text_style)
    row_index += 1
    _write_total(sheet, row_index, "รวมเงิน", totals, total_style, total_number_style)
    # Keep the two signature positions from the sample without copying its
    # signatories or implying that this newly generated report was signed.
    sheet.write(row_index + 4, 2, "(................................................)", signature_style)
    sheet.write(row_index + 4, 8, "(................................................)", signature_style)
    sheet.write(row_index + 5, 2, "ผู้จัดทำ", signature_style)
    sheet.write(row_index + 5, 8, "ผู้ตรวจทาน", signature_style)
    sheet.write(row_index + 6, 2, "วันที่ ................................", signature_style)
    sheet.write(row_index + 6, 8, "วันที่ ................................", signature_style)
    output = BytesIO()
    book.save(output)
    return output.getvalue()
