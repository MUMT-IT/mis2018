"""Generate the cash-advance receivables report in the source XLS layout."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

import xlwt

from .categories import CATEGORY_LABELS
from .date_utils import THAI_MONTHS


AMOUNT_KEYS = ("borrowed", "repaid", "before_pending", "pending", "remaining")
CENT = Decimal("0.01")
SHORT_MONTHS = ("มค.", "กพ.", "มีค.", "เมย.", "พค.", "มิย.",
                "กค.", "สค.", "กย.", "ตค.", "พย.", "ธค.")
HEADERS = ("วันที่ยืม", "วันที่ครบกำหนด", "ชื่อผู้ยืม", "", "เลขที่ยืม",
           "จำนวนเงินยืม", "ส่งใช้เงินยืม", "คงเหลือ", "เอกสารระหว่าง",
           "คงเหลือสุทธิ", "วัตถุประสงค์")


def borrower_name_parts(ticket):
    """Use the same borrower name in receivables and borrowing registers."""
    person = getattr(getattr(ticket, "borrower_user", None), "personal_info", None)
    first = "".join((getattr(person, "th_title", "") or "",
                     getattr(person, "th_firstname", "") or "")) or None
    last = getattr(person, "th_lastname", None)
    if first is None and last is None:
        first, separator, last = (ticket.borrower_name or "").strip().rpartition(" ")
        if not separator:
            first, last = last, ""
    return first or "", last or ""


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
    if first_name_with_title is None and last_name is None:
        first_name_with_title, last_name = borrower_name_parts(ticket)
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


def generate_individual_debtors_xls(rows, *, report_date: date) -> bytes:
    """Return the individual debtor ledger using the revised A–J example."""
    rows = list(rows)
    sections = max(0, (len(rows) - 15 + 12) // 13)
    if 4 + len(rows) + 3 * sections + 10 > 65536:
        raise ValueError("รายการมากเกินขนาดที่ไฟล์ .xls รองรับ")
    book = xlwt.Workbook(encoding="utf-8")
    sheet = book.add_sheet(f"{SHORT_MONTHS[report_date.month - 1]}{(report_date.year + 543) % 100:02d}")
    sheet.show_grid = False
    sheet.portrait = False
    sheet.fit_width_to_pages = 1
    for col, width in enumerate((3097, 4864, 7116, 7091, 3968,
                                 4019, 3174, 9753, 4172, 2995)):
        sheet.col(col).width = width
    title_style = _style(size=16, horizontal=xlwt.Alignment.HORZ_CENTER)
    header_style = _style(size=16, bold=True, bordered=True, wrap=True,
                          horizontal=xlwt.Alignment.HORZ_CENTER)
    split_header_top_style = _style(size=16, bold=True, bordered=True, wrap=True,
                                    horizontal=xlwt.Alignment.HORZ_CENTER,
                                    bottom_border=False)
    split_header_bottom_style = _style(size=16, bold=True, bordered=True, wrap=True,
                                       horizontal=xlwt.Alignment.HORZ_CENTER,
                                       top_border=False)
    text_style = _style(size=16, bordered=True)
    number_style = _style(size=16, bordered=True, num_format="#,##0.00",
                          horizontal=xlwt.Alignment.HORZ_RIGHT)
    date_style = _style(size=16, bordered=True, num_format="DD/MM/YYYY",
                        horizontal=xlwt.Alignment.HORZ_CENTER)
    total_style = _style(size=16, bold=True, bordered=True,
                         horizontal=xlwt.Alignment.HORZ_CENTER)
    total_number_style = _style(size=16, bold=True, bordered=True,
                                num_format="#,##0.00", horizontal=xlwt.Alignment.HORZ_RIGHT)
    signature_style = _style(size=16)
    for index, height in enumerate((585, 480, 480, 480)):
        sheet.row(index).height = height
    sheet.write_merge(0, 0, 0, 9, "ทะเบียนคุมลูกหนี้เงินยืมรายตัว", title_style)
    sheet.write_merge(1, 1, 0, 9,
                      f"ณ วันที่ {report_date.day}  {THAI_MONTHS[report_date.month - 1]}  {report_date.year + 543}",
                      title_style)
    for first, last, top, bottom, label in (
        (0, 0, 2, 3, "วันที่ยืม"), (2, 3, 2, 3, "รายการ/วัตถุประสงค์ที่ยืม"),
        (4, 4, 2, 3, "เลขที่เอกสาร"), (5, 5, 2, 3, "จำนวนเงินยืม"),
        (6, 7, 2, 2, "ส่งคืน"), (8, 8, 2, 3, "คงเหลือสุทธิ"),
        (9, 9, 2, 3, "หมายเหตุ"),
    ):
        sheet.write_merge(top, bottom, first, last, label, header_style)
    sheet.write(2, 1, "วันที่ครบกำหนด", split_header_top_style)
    sheet.write(3, 1, "คืนเงินยืม", split_header_bottom_style)
    sheet.write(3, 6, "เงินสด", header_style)
    sheet.write(3, 7, "ใบสำคัญ", header_style)

    totals = [Decimal("0.00") for _ in range(4)]
    row_index = 4

    def carry(label):
        sheet.row(row_index).height = 1125
        sheet.write_merge(row_index, row_index, 2, 3, label, total_style)
        for col in (0, 1, 4, 9):
            sheet.write(row_index, col, "", total_style)
        for col, amount in zip((5, 6, 7, 8), totals):
            sheet.write(row_index, col, float(amount), total_number_style)

    for item_index, item in enumerate(rows):
        if item_index == 15 or (item_index > 15 and (item_index - 15) % 13 == 0):
            for col in range(10):
                sheet.write(row_index, col, "", text_style)
            sheet.row(row_index).height = 615
            row_index += 1
            carry("ยอดยกไป")
            row_index += 1
            carry("ยอดยกมา")
            row_index += 1
        borrowed = Decimal(str(item["borrowed"])).quantize(CENT)
        cash = Decimal(str(item["cash"])).quantize(CENT)
        receipts = Decimal(str(item["receipts"])).quantize(CENT)
        remaining = borrowed - cash - receipts
        if min(borrowed, cash, receipts, remaining) < 0:
            raise ValueError(f"Invalid individual debtor balance for {item['number']}")
        for col, value in ((2, item["first_name_with_title"]),
                           (3, item["last_name"]), (4, item["number"])):
            sheet.write(row_index, col, str(value or ""), text_style)
        sheet.write(row_index, 9, "", text_style)
        for col, day in ((0, item["borrowed_on"]), (1, item["due_on"])):
            if day:
                sheet.write(row_index, col,
                            datetime(day.year + 543, day.month, day.day), date_style)
            else:
                sheet.write(row_index, col, "", text_style)
        for col, amount in zip((5, 6, 7, 8), (borrowed, cash, receipts, remaining)):
            sheet.write(row_index, col, float(amount), number_style)
            totals[col - 5] += amount
        sheet.row(row_index).height = 660
        row_index += 1
    for col in range(10):
        sheet.write(row_index, col, "", text_style)
    row_index += 1
    carry("ยอดยกไป")
    sheet.write(row_index + 4, 2, "(................................................)", signature_style)
    sheet.write(row_index + 4, 7, "(................................................)", signature_style)
    sheet.write(row_index + 5, 2, "ผู้จัดทำ", signature_style)
    sheet.write(row_index + 5, 7, "ผู้ตรวจทาน", signature_style)
    sheet.write(row_index + 6, 2, "วันที่ ................................", signature_style)
    sheet.write(row_index + 6, 7, "วันที่ ................................", signature_style)
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def _outstanding_age_bucket(due_on: date, report_date: date) -> tuple[int, str]:
    """Use the source workbook's exact aging boundaries and labels."""
    if due_on > report_date:
        return 0, "ยังไม่ครบกำหนดชำระ"
    days_overdue = (report_date - due_on).days
    if days_overdue <= 15:
        return 1, "ค้างชำระไม่เกิน 1-15 วัน"
    if days_overdue <= 45:
        return 2, "ค้างชำระตั้งแต่ 16-45 วัน"
    return 3, "ค้างชำระตั้งแต่ 45 วันขึ้นไป"


def generate_outstanding_debt_xls(rows, *, report_date: date) -> bytes:
    """Return the outstanding debtor aging report in the source A–M layout."""
    rows = list(rows)
    if len(rows) + 6 > 65536:
        raise ValueError("รายการมากเกินขนาดที่ไฟล์ .xls รองรับ")

    def style(*, bold=False, horizontal=xlwt.Alignment.HORZ_LEFT,
              left=False, right=False, top=False, bottom=False,
              double_bottom=False, number_format=None):
        cell_style = _style(size=16, bold=bold, horizontal=horizontal,
                            num_format=number_format, wrap=True)
        border = xlwt.Borders()
        border.left = xlwt.Borders.THIN if left else xlwt.Borders.NO_LINE
        border.right = xlwt.Borders.THIN if right else xlwt.Borders.NO_LINE
        border.top = xlwt.Borders.THIN if top else xlwt.Borders.NO_LINE
        border.bottom = (xlwt.Borders.DOUBLE if double_bottom else
                         xlwt.Borders.THIN if bottom else xlwt.Borders.NO_LINE)
        cell_style.borders = border
        return cell_style

    center = xlwt.Alignment.HORZ_CENTER
    right = xlwt.Alignment.HORZ_RIGHT
    amount_format = '#,##0.00;(#,##0.00);"-"'
    date_format = "mm-dd-yy"
    book = xlwt.Workbook(encoding="utf-8")
    sheet = book.add_sheet("Sheet1")
    for col, width in enumerate((3.5, 4.6, 7.5, 23.5, 21.0, 13.5, 13.7,
                                 12.2, 31.6, 19.0, 16.7, 17.1, 18.0)):
        sheet.col(col).width = round(width * 256)
    for row_index in range(max(len(rows), 1) + 6):
        sheet.row(row_index).height = 468

    title_style = style(horizontal=center)
    subtitle_style = style(horizontal=center, bottom=True)
    header_top = style(bold=True, horizontal=center, left=True, right=True, top=True)
    header_bottom = style(bold=True, horizontal=center, left=True, right=True, bottom=True)
    group_header = style(bold=True, horizontal=center, left=True, right=True,
                         top=True, bottom=True)
    body_center = style(horizontal=center, left=True, right=True, top=True, bottom=True)
    body_number = style(horizontal=right, left=True, right=True, top=True,
                        bottom=True, number_format=amount_format)
    body_date = style(horizontal=center, left=True, right=True, top=True,
                      bottom=True, number_format=date_format)
    split_left = style(horizontal=right, left=True, top=True, bottom=True)
    split_right = style(left=False, right=True, top=True, bottom=True)
    name_left = style(left=True)
    name_right = style(right=True)
    blank_name_left = style(left=True, top=True, bottom=True)
    blank_name_right = style(right=True, top=True, bottom=True)
    total_number = style(horizontal=right, left=True, right=True,
                         double_bottom=True, number_format=amount_format)

    sheet.write_merge(0, 0, 0, 12, "รายงานยอดลูกหนี้คงค้างเงินทดรอง", title_style)
    sheet.write_merge(1, 1, 0, 12,
                      f"ประจำเดือน{THAI_MONTHS[report_date.month - 1]} {report_date.year + 543}",
                      subtitle_style)
    sheet.write(2, 0, "", header_top)
    sheet.write(3, 0, "", header_bottom)
    sheet.write_merge(2, 2, 1, 2, "เลขที่ใบยืม", header_top)
    sheet.write_merge(3, 3, 1, 2, "", header_bottom)
    sheet.write_merge(2, 2, 3, 4, "ชื่อผู้ยืม", header_top)
    sheet.write(3, 3, "", style(bold=True, horizontal=center, left=True, bottom=True))
    sheet.write(3, 4, "", style(bold=True, horizontal=center, right=True, bottom=True))
    for col, upper, lower in ((5, "จำนวนเงิน", "บาท"),
                              (6, "วันที่ครบกำหนด", "ชำระ"),
                              (7, "", "วันที่ปัจจุบัน"),
                              (8, "", "กลุ่มอายุลูกหนี้")):
        sheet.write(2, col, upper, header_top)
        sheet.write(3, col, lower, header_bottom)
    sheet.write_merge(2, 2, 9, 12, "กลุ่มลูกหนี้ที่ค้างชำระ", group_header)
    for col, label in enumerate(("ยังไม่ครบกำหนดชำระ", "ค้างชำระ 1-15 วัน",
                                 "ค้างชำระ16-45 วัน", "ค้างชำระเกิน 45 วัน"), start=9):
        sheet.write(3, col, label, group_header)

    totals = [Decimal("0.00") for _ in range(4)]
    total_balance = Decimal("0.00")
    for index, item in enumerate(rows, start=1):
        row_index = index + 3
        borrowed = Decimal(str(item["borrowed"])).quantize(CENT)
        cash = Decimal(str(item["cash"])).quantize(CENT)
        receipts = Decimal(str(item["receipts"])).quantize(CENT)
        balance = borrowed - cash - receipts
        if balance <= 0:
            raise ValueError(f"Invalid outstanding balance for {item['number']}")
        due_on = item["due_on"]
        if due_on is None:
            raise ValueError(f"Missing due date for {item['number']}")
        bucket, age_label = _outstanding_age_bucket(due_on, report_date)
        total_balance += balance
        totals[bucket] += balance

        sheet.write(row_index, 0, index, body_center)
        sheet.write(row_index, 1, "บย.", split_left)
        sheet.write(row_index, 2, str(item["number"] or ""), split_right)
        sheet.write(row_index, 3, str(item["first_name_with_title"] or ""), name_left)
        sheet.write(row_index, 4, str(item["last_name"] or ""), name_right)
        sheet.write(row_index, 5, float(balance), body_number)
        sheet.write(row_index, 6,
                    datetime(due_on.year + 543, due_on.month, due_on.day), body_date)
        if index == 1:
            sheet.write(row_index, 7,
                        datetime(report_date.year + 543, report_date.month, report_date.day),
                        body_date)
        else:
            sheet.write(row_index, 7, "", body_center)
        sheet.write(row_index, 8, age_label, body_center)
        for column, bucket_amount in enumerate(
            (balance if bucket == 0 else 0, balance if bucket == 1 else 0,
             balance if bucket == 2 else 0, balance if bucket == 3 else 0), start=9
        ):
            sheet.write(row_index, column, float(bucket_amount), body_number)

    blank_styles = (body_center, split_left, split_right,
                    blank_name_left, blank_name_right, body_number, body_date,
                    body_date, body_center, body_number, body_number,
                    body_number, body_number)
    if not rows:
        for column, blank_style in enumerate(blank_styles):
            if column == 7:
                sheet.write(4, column,
                            datetime(report_date.year + 543, report_date.month, report_date.day),
                            body_date)
            else:
                sheet.write(4, column, "", blank_style)

    # The source's unlabeled adjustment row was a manual error; keep its layout blank.
    blank_row = max(len(rows), 1) + 4
    for column, blank_style in enumerate(blank_styles):
        sheet.write(blank_row, column, "", blank_style)
    total_row = blank_row + 1
    sheet.write(total_row, 4, "", style(right=True, top=True, bottom=True))
    sheet.write(total_row, 5, float(total_balance), total_number)
    for column, amount in enumerate(totals, start=9):
        sheet.write(total_row, column, float(amount), total_number)
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def generate_borrowing_register_xls(rows, *, report_date: date) -> bytes:
    rows = list(rows)
    # A page has 14 transactions before its first carryover, then 15 per page.
    if len(rows) + 2 * (len(rows) // 14) + 12 > 65536:
        raise ValueError("รายการมากเกินขนาดที่ไฟล์ .xls รองรับ")

    book = xlwt.Workbook(encoding="utf-8")
    month_label = SHORT_MONTHS[report_date.month - 1]
    # This source sheet uses ต.ค. while the receivables sheets use ตค.
    month_label = f"{month_label[:-2]}.{month_label[-2:]}"
    sheet = book.add_sheet(
        f"{month_label}{(report_date.year + 543) % 100:02d}"
    )
    sheet.show_grid = False
    sheet.portrait = True
    sheet.fit_width_to_pages = 1
    for col, width in enumerate((13, 19, 35, 20, 10, 12, 13, 40, 14, 12)):
        sheet.col(col).width = int(width * 256)

    title = _style(size=16, horizontal=xlwt.Alignment.HORZ_CENTER)
    header = _style(size=16, bold=True, bordered=True, wrap=True,
                    horizontal=xlwt.Alignment.HORZ_CENTER)
    text = _style(size=16, bordered=True)
    center = _style(size=16, bordered=True, horizontal=xlwt.Alignment.HORZ_CENTER)
    number = _style(size=16, bordered=True, horizontal=xlwt.Alignment.HORZ_RIGHT,
                    num_format="#,##0.00;(#,##0.00)")
    date_style = _style(size=16, bordered=True,
                        horizontal=xlwt.Alignment.HORZ_CENTER,
                        num_format="[$-101041E]d\\ mmm\\ yy;@")
    carry_text = _style(size=16, bold=True, bordered=True)
    carry_number = _style(size=16, bold=True, bordered=True,
                          horizontal=xlwt.Alignment.HORZ_RIGHT,
                          num_format="#,##0.00;(#,##0.00)")
    opening_prompt = _style(size=16, bold=True, bordered=True)
    opening_prompt.font.colour_index = xlwt.Style.colour_map["red"]
    signature = _style(size=16)

    sheet.row(0).height = 510
    sheet.row(1).height = 975
    sheet.row(2).height = sheet.row(3).height = 480
    sheet.write_merge(0, 0, 0, 9, "ทะเบียนคุมการยืมเงิน", title)
    for first, last, top, bottom, label in (
        (0, 0, 2, 3, "วัน/เดือน/ปี"),
        (2, 3, 2, 3, "รายการ"),
        (6, 7, 2, 2, "รายการจ่าย"),
        (8, 8, 2, 3, "เงินคงเหลือ"),
        (9, 9, 2, 3, "หมายเหตุ"),
    ):
        sheet.write_merge(top, bottom, first, last, label, header)
    for col, top, bottom in (
        (1, "วันที่ครบกำหนด", "การคืนเงินยืม"),
        (4, "เลขที่", "เอกสาร"),
        (5, "รับ/(คืน)", "เงินยืม"),
        (6, None, "ลูกหนี้"),
        (7, None, "ใบสำคัญ"),
    ):
        if top is not None:
            sheet.write(2, col, top, header)
        sheet.write(3, col, bottom, header)

    def write_carry(row_index, label, values=None, label_style=None):
        sheet.row(row_index).height = 1170
        sheet.write_merge(row_index, row_index, 2, 3, label, label_style or carry_text)
        for col in (0, 1, 4, 7, 8, 9):
            sheet.write(row_index, col, "", carry_text)
        for col in (5, 6):
            value = values[col - 5] if values else ""
            sheet.write(row_index, col, value, carry_number)

    def excel_date(value):
        return datetime(value.year + 543, value.month, value.day)

    row_index = 4
    opening_row = row_index
    write_carry(row_index, "กรุณากรอกยอดยกมา", label_style=opening_prompt)
    row_index += 1
    on_page = 0
    page_capacity = 14
    def group_size(index):
        entry = rows[index]
        if entry.get("description") == "รับจากเงินทดรองจ่าย(งานคลัง)":
            return 2
        if entry.get("g", 0) < 0 and entry.get("i", 0) > 0:
            return 2
        if entry.get("g", 0) < 0 and entry.get("h", 0) > 0:
            following = index + 1
            while following < len(rows) and rows[following].get("g", 0) < 0 and rows[following].get("h", 0) > 0:
                following += 1
            if following < len(rows) and rows[following].get("h", 0) < 0:
                return following - index + 1
        return 1

    for item_index, entry in enumerate(rows):
        required = group_size(item_index)
        if on_page == page_capacity or (
            on_page and required <= page_capacity and on_page + required > page_capacity
        ):
            last_detail = row_index
            write_carry(row_index, "ยอดยกไป", (
                xlwt.Formula(f"SUM(F{opening_row + 1}:F{last_detail})"),
                xlwt.Formula(f"SUM(G{opening_row + 1}:G{last_detail})"),
            ))
            prior_row = row_index + 1
            row_index += 1
            opening_row = row_index
            write_carry(row_index, "ยอดยกมา", (
                xlwt.Formula(f"F{prior_row}"), xlwt.Formula(f"G{prior_row}"),
            ))
            row_index += 1
            on_page = 0
            page_capacity = 15
        sheet.row(row_index).height = 558
        for col, key in ((0, "date"), (1, "due_date")):
            value = entry.get(key)
            sheet.write(row_index, col, excel_date(value) if value else "",
                        date_style if value else center)
        for col, key, style in ((2, "description", text), (3, "last_name", text),
                                (4, "ticket_number", center), (9, "note", text)):
            sheet.write(row_index, col, str(entry.get(key) or ""), style)
        for col, key in ((5, "f"), (6, "g"), (7, "h"), (8, "i")):
            value = entry.get(key)
            sheet.write(row_index, col, float(value) if value is not None else "", number)
        row_index += 1
        on_page += 1

    last_detail = row_index
    write_carry(row_index, "ยอดยกไป", (
        xlwt.Formula(f"SUM(F{opening_row + 1}:F{last_detail})"),
        xlwt.Formula(f"SUM(G{opening_row + 1}:G{last_detail})"),
    ))
    for offset, label in ((3, "(................................................)"),
                          (4, "ผู้จัดทำ"), (5, "วันที่ ................................")):
        sheet.write(row_index + offset, 2, label, signature)
    for offset, label in ((3, "(................................................)"),
                          (4, "ผู้ตรวจทาน"), (5, "วันที่ ................................")):
        sheet.write(row_index + offset, 7, label, signature)

    output = BytesIO()
    book.save(output)
    return output.getvalue()


FUND_CATEGORY_COLUMNS = {1: "g", 2: "h", 3: "i", 4: "j", 7: "k", 8: "o"}


def _fund_category_amounts(items, total, *, source):
    amounts = defaultdict(lambda: Decimal("0.00"))
    for item in items:
        amount = Decimal(str(item.amount or 0)).quantize(CENT)
        column = FUND_CATEGORY_COLUMNS.get(item.category_type)
        if column is None:
            reason = ("หมวดอื่น ๆ ยังไม่มีคอลัมน์ในทะเบียน" if item.category_type == 5
                      else "กรุณาจัดหมวดรายการก่อนดาวน์โหลด")
            raise ValueError(f"{source}, รายการ {item.id}: {reason}")
        if not amount.is_finite() or amount <= 0:
            raise ValueError(f"{source}, รายการ {item.id}: จำนวนเงินไม่ถูกต้อง")
        amounts[column] += amount
    if sum(amounts.values(), Decimal("0.00")) != Decimal(str(total or 0)).quantize(CENT):
        raise ValueError(f"{source}: ยอดแยกหมวดไม่ตรงกับยอดรวม")
    return dict(amounts)


def _fund_register_rows(target_date):
    """Build fund movements using the existing loan register and finance helpers."""
    # Resolve view helpers at export time, after blueprint registration finishes.
    from . import views as finance
    from .models import (db, ParcelReturnDetail, PettyCashClaimDetail,
                         PettyCashFiscalYearTopUpTransfer)
    from sqlalchemy import func, or_

    first_day = target_date.replace(day=1)
    zero = Decimal("0.00")
    money = finance._money_decimal

    def local_day(value):
        return (value.astimezone(ZoneInfo("Asia/Bangkok")).date()
                if value.tzinfo else value.date()) if isinstance(value, datetime) else value

    def in_month(value):
        return value is not None and first_day <= local_day(value) <= target_date

    events = []

    def append(day, order, description, amounts, ticket_ids=()):
        if in_month(day) and any(amounts.values()):
            events.append((local_day(day), order, len(events), {
                "date": local_day(day), "description": description,
                **{key: value for key, value in amounts.items() if value},
                "ticket_ids": sorted(set(ticket_ids)),
            }))

    daily = defaultdict(lambda: {
        "loan": zero, "cash": zero, "noncash": zero,
        "loan_ids": set(), "cash_ids": set(), "noncash_ids": set(),
    })
    day = None
    for row in finance._borrowing_register_rows(target_date):
        day = row.get("date") or day
        if day is None:
            continue
        if row.get("description") == "รับจากเงินทดรองจ่าย(งานคลัง)":
            daily[day]["loan"] += money(row["f"])
            daily[day]["loan_ids"].add(row["ticket_id"])
        elif row.get("description", "").startswith("รับคืนเงินยืม"):
            kind = "noncash" if row.get("h") else "cash"
            daily[day][kind] -= money(row["g"])
            daily[day][f"{kind}_ids"].add(row["ticket_id"])

    categories = defaultdict(lambda: defaultdict(lambda: zero))
    ticket_ids = {ticket.id for ticket in finance._receivables_export_tickets(target_date)}
    if ticket_ids:
        returns, parcels = finance._ticket_return_rows_as_of(
            ticket_ids, target_date, report_stage="settled", require_approval_by_target=False,
        )
        for detail in returns:
            if not in_month(detail.settled_at) or finance._return_detail_is_cash(detail):
                continue
            if not (finance._return_ticket_ids(detail) & ticket_ids):
                continue
            amounts = _fund_category_amounts(
                detail.receipt_items, detail.amount_spent, source=f"รายการคืนเงินยืม {detail.id}",
            )
            for column, amount in amounts.items():
                categories[local_day(detail.settled_at)][column] += amount
        for parcel in parcels:
            if (parcel.fund_request_id is None and in_month(parcel.settled_at)
                    and finance._parcel_return_ticket_ids(parcel) & ticket_ids):
                amount = money(parcel.amount_spent)
                if amount <= 0:
                    raise ValueError(f"รายการคืนพัสดุ {parcel.id}: จำนวนเงินไม่ถูกต้อง")
                categories[local_day(parcel.settled_at)]["i"] += amount

    for day in sorted(set(daily) | set(categories)):
        movement = daily[day]
        if sum(categories[day].values(), zero) != movement["noncash"]:
            raise ValueError(f"ยอดคืนวันที่ {day:%d/%m/%Y} ไม่ตรงกับทะเบียนคุมการยืมเงิน")
        amount = movement["loan"]
        append(day, 5, "จ่ายเงินยืม", {"f": amount, "l": amount}, movement["loan_ids"])
        append(day, 1, "รับคืนเงินยืม", {"l": -movement["noncash"], **categories[day]},
               movement["noncash_ids"])
        amount = movement["cash"]
        append(day, 3, "รับคืนเงินยืม", {"f": -amount, "l": -amount}, movement["cash_ids"])

    transfers = db.session.query(PettyCashFiscalYearTopUpTransfer).all()
    counted_reductions = set()
    for transfer in transfers:
        if transfer.transfer_type != finance.PETTY_CASH_TRANSFER_REDUCTION or not in_month(transfer.transferred_at):
            continue
        record = transfer.fund_request
        if record is None or record.form_type != finance.FUND_REQUEST_FORM_REDUCTION:
            raise ValueError(f"รายการลดวงเงิน {transfer.id}: ไม่พบใบเบิกลดวงเงินที่เชื่อมกัน")
        if record.is_legacy_import or record.status_id in finance._status_ids("fund_request", {
            "PENDING", "REJECTED", "CLAIM_CANCELLED",
        }):
            continue
        amount = money(record.amount)
        if record.request_date is None or amount <= 0 or amount != money(transfer.transfer_amount):
            raise ValueError(f"ใบเบิกลดวงเงิน {record.id}: กรุณาตรวจสอบข้อมูลโอนและยอดเงินที่เชื่อมกัน")
        if record.id in counted_reductions:
            raise ValueError(f"ใบเบิกลดวงเงิน {record.id}: มีข้อมูลโอนซ้ำกัน")
        counted_reductions.add(record.id)
        append(transfer.transferred_at, 0, "รับคืนเงินสดย่อย", {"f": -amount, "m": -amount})
    for transfer in transfers:
        if transfer.transfer_type == finance.PETTY_CASH_TRANSFER_TOP_UP and in_month(transfer.transferred_at):
            amount = money(transfer.transfer_amount)
            if amount <= 0:
                raise ValueError(f"รายการเพิ่มวงเงิน {transfer.id}: จำนวนเงินไม่ถูกต้อง")
            append(transfer.transferred_at, 0, "รับคืนเงินสดย่อย", {"f": amount, "m": amount})

    # Include adjacent UTC dates, then apply Bangkok calendar dates above.
    near_start, near_end = first_day - timedelta(days=1), target_date + timedelta(days=1)
    cheque_days = defaultdict(lambda: defaultdict(lambda: zero))
    cheque_tickets = defaultdict(set)
    claims = db.session.query(PettyCashClaimDetail).filter(
        or_(func.date(PettyCashClaimDetail.settled_at).between(near_start, near_end),
            PettyCashClaimDetail.transferred_at.between(first_day, target_date)),
        PettyCashClaimDetail.status_id.notin_(finance._status_ids("petty_cash_claim", {"REJECTED"})),
    ).all()
    for claim in claims:
        if finance._claim_has_only_category_six(claim):
            continue
        settled = claim.fund_request_id is not None and in_month(claim.settled_at)
        transferred = in_month(claim.transferred_at)
        if not (settled or transferred):
            continue
        amounts = _fund_category_amounts(claim.items, claim.total_amount,
                                         source=f"ใบเบิกเงินสดย่อย {claim.id}")
        total = money(claim.total_amount)
        ticket_id = getattr(claim.fund_request, "borrowing_ticket_id", None)
        linked_ids = {ticket_id} if ticket_id else set()
        if settled:
            day = local_day(claim.settled_at)
            cheque_days[day]["f"] -= total
            for column, amount in amounts.items():
                cheque_days[day][column] -= amount
            cheque_tickets[day].update(linked_ids)
        if transferred:
            append(claim.transferred_at, 4, "โอนเงินสดย่อย", {"f": total, **amounts}, linked_ids)

    parcels = db.session.query(ParcelReturnDetail).filter(
        ParcelReturnDetail.fund_request_id.isnot(None),
        or_(func.date(ParcelReturnDetail.settled_at).between(near_start, near_end),
            ParcelReturnDetail.transferred_at.between(first_day, target_date)),
        ParcelReturnDetail.status_id.notin_(finance._status_ids("parcel_return", {"REJECTED"})),
    ).all()
    for parcel in parcels:
        settled, transferred = in_month(parcel.settled_at), in_month(parcel.transferred_at)
        if not (settled or transferred):
            continue
        amount = money(parcel.amount_spent)
        if amount <= 0:
            raise ValueError(f"รายการคืนพัสดุ {parcel.id}: จำนวนเงินไม่ถูกต้อง")
        linked_ids = finance._parcel_return_ticket_ids(parcel)
        ticket_id = getattr(parcel.fund_request, "borrowing_ticket_id", None)
        if ticket_id:
            linked_ids.add(ticket_id)
        if settled:
            day = local_day(parcel.settled_at)
            cheque_days[day]["f"] -= amount
            cheque_days[day]["i"] -= amount
            cheque_tickets[day].update(linked_ids)
        if transferred:
            append(parcel.transferred_at, 4, "โอนเงินสดย่อย", {"f": amount, "i": amount}, linked_ids)
    for day, amounts in cheque_days.items():
        append(day, 2, "รับเช็คเงินยืม", dict(amounts), cheque_tickets[day])

    return [row for _, _, _, row in sorted(events, key=lambda entry: entry[:3])]


def generate_fund_register_xls(rows, *, report_date: date) -> bytes:
    """Write the source A–P layout; opening balances are entered after download."""
    rows = list(rows)
    page_size = 21
    pages = max(1, (len(rows) + page_size - 1) // page_size)
    if 3 + pages * (page_size + 2) + 7 > 65536:
        raise ValueError("รายการมากเกินขนาดที่ไฟล์ .xls รองรับ")
    book = xlwt.Workbook(encoding="utf-8")
    month = SHORT_MONTHS[report_date.month - 1]
    sheet = book.add_sheet(f"{month}{(report_date.year + 543) % 100:02d}")
    sheet.show_grid = False
    sheet.portrait = False
    sheet.fit_width_to_pages = 1
    for col, width in enumerate((1755, 1206, 8338, 2706, 3693, 3547, 2925, 3254,
                                 3035, 3584, 2779, 3510, 3547, 3218, 3181, 3803)):
        sheet.col(col).width = width
    title = _style(size=16, horizontal=xlwt.Alignment.HORZ_CENTER)
    header = _style(size=16, bold=True, bordered=True, wrap=True,
                    horizontal=xlwt.Alignment.HORZ_CENTER)
    text = _style(size=16, bordered=True)
    center = _style(size=16, bordered=True, horizontal=xlwt.Alignment.HORZ_CENTER)
    number = _style(size=16, bordered=True, horizontal=xlwt.Alignment.HORZ_RIGHT,
                    num_format="#,##0.00;(#,##0.00)")
    carry_number = _style(size=16, bold=True, bordered=True,
                          horizontal=xlwt.Alignment.HORZ_RIGHT, num_format="#,##0.00;(#,##0.00)")
    carry_text = _style(size=16, bold=True, bordered=True)
    prompt = _style(size=16, bold=True, bordered=True, wrap=True)
    prompt.font.colour_index = xlwt.Style.colour_map["red"]
    signature = _style(size=16)
    for row, height in enumerate((465, 600, 420)):
        sheet.row(row).height = height
    sheet.write_merge(0, 0, 0, 15, "ทะเบียนคุมเงินทดรองจ่าย", title)
    for col, label in enumerate(("เดือน/ปี", "วันที่", "รายการ", "เอกสาร")):
        sheet.write_merge(1, 2, col, col, label, header)
    for col, top, bottom in ((4, "ได้รับจัดสรร", "(1)"), (5, "จ่าย(รับ)", "(2)"),
                             (15, "คงเหลือ(รับ-จ่าย)", "(1)-(2)=(4)")):
        for row, label, top_border, bottom_border in ((1, top, True, False), (2, bottom, False, True)):
            sheet.write(row, col, label, _style(size=16, bold=True, bordered=True, wrap=True,
                        horizontal=xlwt.Alignment.HORZ_CENTER,
                        top_border=top_border, bottom_border=bottom_border))
    sheet.write_merge(1, 1, 6, 14, "รายการเบิกจ่าย (3)=(2)", header)
    for col, label in enumerate((CATEGORY_LABELS[1], CATEGORY_LABELS[2], CATEGORY_LABELS[3],
                                CATEGORY_LABELS[4], CATEGORY_LABELS[7], "เงินยืม", "เงินสดย่อย",
                                "เงินทดรองจ่าย", CATEGORY_LABELS[8]), start=6):
        sheet.write(2, col, label, header)

    def write_carry(row, label, *, opening=None, first=None):
        sheet.row(row).height = 1110
        for col in range(16):
            value = ""
            if col == 2:
                value = label
            elif col >= 4 and opening is not None:
                letter = chr(ord("A") + col)
                if col == 15 and first is not None:
                    formula = f'IF(AND(ISNUMBER(E{row + 1}),ISNUMBER(F{row + 1})),E{row + 1}-F{row + 1},"")'
                elif first is None:
                    formula = f'IF(ISNUMBER({letter}{opening}),{letter}{opening},"")'
                else:
                    formula = f'IF(ISNUMBER({letter}{opening}),{letter}{opening}+SUM({letter}{first}:{letter}{row}),"")'
                value = xlwt.Formula(formula)
            style = (prompt if opening is None else carry_text) if col == 2 else (
                carry_number if col >= 4 else center)
            sheet.write(row, col, value, style)

    row = 3
    write_carry(row, "กรุณากรอกยอดยกมา")
    opening = row + 1
    row += 1
    for page in range(pages):
        first = row + 1
        entries = rows[page * page_size:(page + 1) * page_size]
        for index in range(page_size):
            entry = entries[index] if index < len(entries) else {}
            day = entry.get("date")
            sheet.row(row).height = 582
            sheet.write(row, 0, month if day else "", center)
            sheet.write(row, 1, day.day if day else "", center)
            sheet.write(row, 2, entry.get("description", ""), text)
            sheet.write(row, 3, "", center)
            for col, key in enumerate("efghijklmno", start=4):
                value = entry.get(key)
                sheet.write(row, col, float(value) if value is not None else "", number)
            formula = (f'IF(AND(ISNUMBER(E{opening}),ISNUMBER(F{opening})),'
                       f'E{opening}-F{opening}+SUM(E{first}:E{row + 1})-SUM(F{first}:F{row + 1}),"")')
            sheet.write(row, 15, xlwt.Formula(formula) if entry else "", number)
            row += 1
        write_carry(row, "ยอดยกไป", opening=opening, first=first)
        previous = row + 1
        row += 1
        if page < pages - 1:
            write_carry(row, "ยอดยกมา", opening=previous)
            opening = row + 1
            row += 1
    for col in (4, 11):
        for offset, label in ((3, "(................................................)"),
                              (4, "ผู้จัดทำ" if col == 4 else "ผู้ตรวจทาน"),
                              (5, "วันที่ ................................")):
            sheet.write(row + offset, col, label, signature)
    output = BytesIO()
    book.save(output)
    return output.getvalue()
