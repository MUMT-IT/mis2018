"""Shared date parsing and formatting for advance payment."""

from datetime import date, datetime
import re


THAI_MONTHS = (
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
)


def coerce_date(value):
    """Accept ISO or day/month/year dates with Gregorian or Buddhist years."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        iso = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
        display = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
        if iso or display:
            year, month, day = map(int, iso.groups()) if iso else (
                int(display[3]), int(display[2]), int(display[1])
            )
            if year >= 2400:
                year -= 543
            try:
                return date(year, month, day)
            except ValueError:
                pass
    return None


def parse_date(value):
    """Parse a required date, preserving ValueError for existing callers."""
    parsed = coerce_date(value)
    if parsed is None:
        raise ValueError("Invalid date")
    return parsed


def parse_datetime(value):
    """Parse a date-only input into a midnight datetime."""
    return datetime.combine(parse_date(value), datetime.min.time())


def thai_date(value):
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime(f"%d/%m/{value.year + 543}")
    return value


def thai_datetime(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        # Keep Thai text outside strftime for Windows locale compatibility.
        return value.strftime(f"%d/%m/{value.year + 543} %H:%M") + " น."
    if isinstance(value, date):
        return thai_date(value)
    return value


def thai_long_date(value):
    return f"{value.day} {THAI_MONTHS[value.month - 1]} {value.year + 543}"


def parse_reference_date(value):
    """Parse legacy claim dates; leave other reference text unparsed."""
    if isinstance(value, datetime):
        return value.date()
    return coerce_date(value)


def normalize_reference_date(value):
    if value is None:
        return None
    parsed = parse_reference_date(value)
    return parsed.isoformat() if parsed else (str(value).strip() or None)


def reference_date_short(value):
    # Detail page: show parsed dates with a Buddhist year; keep free text as entered.
    parsed = parse_reference_date(value)
    return thai_date(parsed) if parsed else (value or "")


def reference_date_form(value):
    # Edit form: use a Gregorian year so saving the date parses back to the same day.
    parsed = parse_reference_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else (value or "")


def reference_date_long(value):
    parsed = parse_reference_date(value)
    return thai_long_date(parsed) if parsed else (value or "")
