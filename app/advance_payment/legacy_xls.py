"""Read the old receivables report without touching Flask or the database.

The report has one ticket per data row in columns A–K.  Its Excel date cells
encode Buddhist years as if they were Gregorian years, while the borrow-date
column contains only a Thai month abbreviation and day.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

import xlrd


MAX_FILE_BYTES = 5 * 1024 * 1024
_XLS_SIGNATURE = bytes.fromhex("d0cf11e0a1b11ae1")
_CENT = Decimal("0.01")
_MONTHS = {
    "มค": 1, "กพ": 2, "มีค": 3, "เมย": 4, "พค": 5, "มิย": 6,
    "กค": 7, "สค": 8, "กย": 9, "ตค": 10, "พย": 11, "ธค": 12,
}
_FULL_MONTHS = {
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4,
    "พฤษภาคม": 5, "มิถุนายน": 6, "กรกฎาคม": 7, "สิงหาคม": 8,
    "กันยายน": 9, "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12,
}
_AMOUNT_COLUMNS = (5, 6, 7, 8, 9)  # F–J, zero-based
_NAME_PREFIX = re.compile(
    r"^\s*(?:"
    r"รองศาสตราจารย์|ผู้ช่วยศาสตราจารย์|ศาสตราจารย์|อาจารย์|"
    r"นางสาว|นาง|นาย|"
    r"[ก-๙]+\s*\."
    r")\s*"
)


def legacy_borrower_name_key(first_name_with_title: str, last_name: str) -> str:
    """Compare given name and surname after removing known leading titles.

    Dotted Thai abbreviations at the start are removed without enumerating
    every academic title. Plain whitespace alone does not identify a title.
    """
    given_name = (first_name_with_title or "").strip()
    while given_name:
        match = _NAME_PREFIX.match(given_name)
        if not match:
            break
        given_name = given_name[match.end():]
    return re.sub(r"\s+", "", given_name) + "|" + re.sub(r"\s+", "", last_name or "")


class LegacyXlsError(ValueError):
    """The uploaded file cannot be read as this report format."""


@dataclass(frozen=True)
class RowIssue:
    code: str
    message: str


@dataclass
class LegacyTicketRow:
    source_row: int  # one-based Excel row, retained for source lookup
    borrow_text: str
    due_text: str
    first_name_with_title: str
    last_name: str
    ticket_number: str
    purpose: str
    borrow_date: date | None = None
    due_date: date | None = None
    borrowed_amount: Decimal | None = None
    repaid_amount: Decimal | None = None
    balance_before_pending: Decimal | None = None
    pending_documents_amount: Decimal | None = None
    opening_balance_amount: Decimal | None = None
    issues: list[RowIssue] = field(default_factory=list)

    @property
    def borrower_name(self) -> str:
        return " ".join(part for part in (
            self.first_name_with_title, self.last_name
        ) if part)

    @property
    def ready_for_review(self) -> bool:
        return not self.issues and self.opening_balance_amount is not None


@dataclass
class LegacyReport:
    sheet_name: str
    report_date: date | None
    header_row: int
    total_row: int | None
    rows: list[LegacyTicketRow]
    file_totals: dict[str, Decimal] | None
    calculated_totals: dict[str, Decimal] | None
    issues: list[RowIssue] = field(default_factory=list)


@dataclass
class LegacyContractCheck:
    row: LegacyTicketRow
    borrower_ids: list[int]
    reasons: list[str]
    duplicate_in_database: bool = False

    @property
    def ready_after_migration(self) -> bool:
        return not self.reasons


def check_legacy_contracts(
    report: LegacyReport,
    *,
    existing_numbers: set[str],
    borrower_ids_by_name: dict[str, list[int]],
    upload_date: date,
) -> list[LegacyContractCheck]:
    """Check whether approved legacy rows can be imported from database snapshots."""
    current_fiscal_year = upload_date.year + (upload_date.month >= 10) + 543
    report_reasons = [issue.message for issue in report.issues]
    checks = []
    for row in report.rows:
        reasons = report_reasons + [issue.message for issue in row.issues]
        number = row.ticket_number.strip()
        duplicate = bool(number and number in existing_numbers)
        if duplicate:
            reasons.append("เลขที่ยืมมีอยู่ในฐานข้อมูลแล้ว")
        suffix = re.search(r"/(\d{2})$", number)
        if suffix and 2500 + int(suffix.group(1)) >= current_fiscal_year:
            reasons.append("ปีท้ายเลขที่ยืมต้องเก่ากว่าปีงบประมาณ ณ วันอัปโหลด")
        name_key = legacy_borrower_name_key(row.first_name_with_title, row.last_name)
        borrower_ids = borrower_ids_by_name.get(name_key, [])
        if not borrower_ids:
            reasons.append("ไม่พบบัญชีผู้ยืมที่ชื่อ–นามสกุลตรงกันในระบบ")
        elif len(borrower_ids) > 1:
            reasons.append("พบบัญชีผู้ยืมชื่อตรงกันหลายบัญชี ต้องเลือกคนที่ถูกต้อง")
        checks.append(LegacyContractCheck(
            row=row,
            borrower_ids=borrower_ids,
            reasons=reasons,
            duplicate_in_database=duplicate,
        ))
    return checks


def _text(sheet, row: int, col: int) -> str:
    if col >= sheet.ncols or row >= sheet.nrows:
        return ""
    value = sheet.cell_value(row, col)
    return str(value).strip() if value is not None else ""


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _find_sheet_and_header(book):
    matches = []
    for sheet in book.sheets():
        for row in range(max(0, sheet.nrows - 1)):
            if (
                _compact(_text(sheet, row, 0)) == "วันที่ยืม"
                and _compact(_text(sheet, row, 4)) == "เลขที่ยืม"
                and _compact(_text(sheet, row, 5)) == "จำนวนเงินยืม"
                and _compact(_text(sheet, row, 9)) == "คงเหลือสุทธิ"
                and "ครบกำหนด" in _compact(_text(sheet, row, 1))
                and "คืนเงินยืม" in _compact(_text(sheet, row + 1, 1))
                and "เอกสารระหว่าง" in _compact(_text(sheet, row, 8))
                and "รอเบิก" in _compact(_text(sheet, row + 1, 8))
            ):
                matches.append((sheet, row))
    if len(matches) != 1:
        raise LegacyXlsError(
            f"Expected one receivables table; found {len(matches)}"
        )
    return matches[0]


def _report_date(sheet, header_row: int) -> date | None:
    for row in range(header_row):
        match = re.search(
            r"(\d{1,2})\s+([ก-๙]+)\s+(\d{4})",
            _text(sheet, row, 0),
        )
        if match and match.group(2) in _FULL_MONTHS:
            year = int(match.group(3))
            if year >= 2400:
                year -= 543
            try:
                return date(year, _FULL_MONTHS[match.group(2)], int(match.group(1)))
            except ValueError:
                return None
    return None


def _amount(sheet, row: int, col: int, *, blank_is_zero=False,
            dash_is_zero=False) -> Decimal | None:
    if col >= sheet.ncols:
        return Decimal("0.00") if blank_is_zero else None
    cell = sheet.cell(row, col)
    if cell.ctype == xlrd.XL_CELL_ERROR:
        return None
    value = cell.value
    if cell.ctype == xlrd.XL_CELL_EMPTY or str(value).strip() == "":
        return Decimal("0.00") if blank_is_zero else None
    if dash_is_zero and str(value).strip() == "-":
        return Decimal("0.00")
    try:
        amount = Decimal(str(value)).quantize(_CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
    return amount if amount.is_finite() else None


def _borrow_date(value: str, ticket_number: str) -> date | None:
    match = re.fullmatch(r"\s*([ก-๙]+)\.?\s*(\d{1,2})\s*", value)
    suffix = re.search(r"/(\d{2})$", ticket_number)
    if not match or not suffix:
        return None
    month = _MONTHS.get(match.group(1))
    if month is None:
        return None
    buddhist_year = 2500 + int(suffix.group(1))
    if month >= 10:
        buddhist_year -= 1
    try:
        return date(buddhist_year - 543, month, int(match.group(2)))
    except ValueError:
        return None


def _due_date(sheet, row: int, datemode: int) -> date | None:
    cell = sheet.cell(row, 1)
    if cell.ctype not in (xlrd.XL_CELL_DATE, xlrd.XL_CELL_NUMBER):
        return None
    try:
        excel_date = xlrd.xldate.xldate_as_datetime(cell.value, datemode).date()
        year = excel_date.year - 543 if 2400 <= excel_date.year <= 2700 else excel_date.year
        if not 1900 <= year <= 2100:
            return None
        return date(year, excel_date.month, excel_date.day)
    except (ValueError, OverflowError, xlrd.XLDateError):
        return None


def _is_summary(sheet, row: int) -> bool:
    return _compact(_text(sheet, row, 2)) in {"รวมเงิน", "ยอดยกมา"}


def _is_candidate(sheet, row: int) -> bool:
    if _is_summary(sheet, row):
        return False
    if _text(sheet, row, 4):
        return True
    return bool(
        _text(sheet, row, 0)
        and (_text(sheet, row, 2) or _text(sheet, row, 3))
        and _amount(sheet, row, 5) is not None
    )


def _parse_row(sheet, row: int, datemode: int, report_date: date | None):
    ticket = LegacyTicketRow(
        source_row=row + 1,
        borrow_text=_text(sheet, row, 0),
        due_text=_text(sheet, row, 1),
        first_name_with_title=_text(sheet, row, 2),
        last_name=_text(sheet, row, 3),
        ticket_number=_text(sheet, row, 4),
        purpose=_text(sheet, row, 10),
    )
    def issue(code, message):
        ticket.issues.append(RowIssue(code, message))

    if not ticket.ticket_number:
        issue("missing_number", "ไม่มีเลขที่ยืม")
    elif not re.fullmatch(r"\d+/\d{2}", ticket.ticket_number):
        issue("invalid_number", "เลขที่ยืมไม่อยู่ในรูปแบบเลข/YY")
    if not ticket.first_name_with_title or not ticket.last_name:
        issue("missing_borrower_name", "ชื่อหรือนามสกุลผู้ยืมไม่ครบ")
    if not ticket.purpose:
        issue("missing_purpose", "ไม่มีวัตถุประสงค์")

    ticket.borrow_date = _borrow_date(ticket.borrow_text, ticket.ticket_number)
    if ticket.borrow_date is None:
        issue("invalid_borrow_date", "อ่านวันที่ยืมไม่ได้")
    ticket.due_date = _due_date(sheet, row, datemode)
    if ticket.due_date is None:
        issue("invalid_due_date", "อ่านวันที่ครบกำหนดไม่ได้")
    if ticket.borrow_date and report_date and ticket.borrow_date > report_date:
        issue("borrow_after_report", "วันที่ยืมอยู่หลังวันที่รายงาน")
    if ticket.borrow_date and ticket.due_date and ticket.borrow_date > ticket.due_date:
        issue("borrow_after_due", "วันที่ยืมอยู่หลังวันครบกำหนด")

    values = [
        _amount(sheet, row, 5),
        _amount(sheet, row, 6, blank_is_zero=True),
        _amount(sheet, row, 7),
        _amount(sheet, row, 8, blank_is_zero=True),
        _amount(sheet, row, 9, dash_is_zero=True),
    ]
    (
        ticket.borrowed_amount,
        ticket.repaid_amount,
        ticket.balance_before_pending,
        ticket.pending_documents_amount,
        ticket.opening_balance_amount,
    ) = values
    if any(value is None for value in values):
        issue("invalid_amount", "อ่านยอดเงิน F–J ไม่ครบหรือมีเซลล์สูตรที่ไม่มีค่า")
        return ticket
    f, g, h, i, j = values
    if f <= 0 or any(value < 0 for value in (g, h, i, j)) or j > f:
        issue("amount_out_of_range", "ยอดเงินไม่อยู่ในช่วงที่นำเข้าได้")
    if f - g != h or h - i != j:
        issue("amount_mismatch", "ยอดเงินไม่ตรงสูตร F−G=H และ H−I=J")
    return ticket


def parse_legacy_cash_advance_xls(file_bytes: bytes) -> LegacyReport:
    """Return parsed ticket rows and review issues from one old XLS report."""
    if not file_bytes or len(file_bytes) > MAX_FILE_BYTES:
        raise LegacyXlsError("File is empty or larger than 5 MB")
    if not file_bytes.startswith(_XLS_SIGNATURE):
        raise LegacyXlsError("Expected a legacy .xls file")
    try:
        book = xlrd.open_workbook(file_contents=file_bytes, on_demand=True)
    except (xlrd.XLRDError, ValueError) as exc:
        raise LegacyXlsError("Could not read the .xls workbook") from exc
    try:
        sheet, header_row = _find_sheet_and_header(book)
        report_date = _report_date(sheet, header_row)
        rows = [
            _parse_row(sheet, row, book.datemode, report_date)
            for row in range(header_row + 2, sheet.nrows)
            if _is_candidate(sheet, row)
        ]
        rows_by_number = {}
        for row in rows:
            if row.ticket_number:
                rows_by_number.setdefault(row.ticket_number, []).append(row)
        for same_number_rows in rows_by_number.values():
            if len(same_number_rows) > 1:
                for row in same_number_rows:
                    row.issues.append(RowIssue(
                        "duplicate_in_file", "เลขที่ยืมซ้ำในไฟล์"
                    ))
        total_candidates = [
            row for row in range(header_row + 2, sheet.nrows)
            if _compact(_text(sheet, row, 2)) == "รวมเงิน"
            and all(_amount(sheet, row, col) is not None for col in _AMOUNT_COLUMNS)
        ]
        total_row = total_candidates[-1] if total_candidates else None
        names = ("F", "G", "H", "I", "J")
        file_totals = (
            {name: _amount(sheet, total_row, col)
             for name, col in zip(names, _AMOUNT_COLUMNS)}
            if total_row is not None else None
        )
        calculated_totals = None
        if rows and all(
            all(_amount(sheet, row.source_row - 1, col,
                        blank_is_zero=col in (6, 8),
                        dash_is_zero=col == 9) is not None
                for col in _AMOUNT_COLUMNS)
            for row in rows
        ):
            calculated_totals = {
                name: sum(
                    (_amount(sheet, row.source_row - 1, col,
                             blank_is_zero=col in (6, 8),
                             dash_is_zero=col == 9)
                     for row in rows),
                    Decimal("0.00"),
                )
                for name, col in zip(names, _AMOUNT_COLUMNS)
            }
        report = LegacyReport(
            sheet_name=sheet.name,
            report_date=report_date,
            header_row=header_row + 1,
            total_row=total_row + 1 if total_row is not None else None,
            rows=rows,
            file_totals=file_totals,
            calculated_totals=calculated_totals,
        )
        if report_date is None:
            report.issues.append(RowIssue("missing_report_date", "อ่านวันที่รายงานไม่ได้"))
        if not rows:
            report.issues.append(RowIssue("no_tickets", "ไม่พบแถว ticket"))
        if file_totals is None:
            report.issues.append(RowIssue("missing_total", "ไม่พบแถวรวมท้ายรายงาน"))
        elif calculated_totals is None:
            report.issues.append(RowIssue("incomplete_total", "มีแถวที่อ่านยอดเงินไม่ได้"))
        elif calculated_totals != file_totals:
            report.issues.append(RowIssue("total_mismatch", "ผลรวม F–J ไม่ตรงแถวรวมท้ายรายงาน"))
        return report
    finally:
        book.release_resources()
