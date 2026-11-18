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
