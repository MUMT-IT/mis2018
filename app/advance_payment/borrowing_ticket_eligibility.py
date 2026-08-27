from dataclasses import dataclass
from typing import Iterable

ACTIVE_STATUS_LABELS = {
    "อนุมัติจ่ายเงิน": "อนุมัติจ่ายเงิน",
    "มียอดคงค้าง": "มียอดคงค้าง",
    "เกินกำหนดส่งใช้": "เกินกำหนดส่งใช้",
    "รอตรวจสอบ": "รอตรวจสอบ",
}

IGNORED_STATUS_LABELS = {"เคลียร์ยอดแล้ว"}

@dataclass(frozen=True)
class BorrowingTicketEligibility:
    is_eligible: bool
    blocking_statuses: tuple[str, ...]
    blocking_records: tuple[dict, ...]

def _get_record_value(record, key, default=None):
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)

def calculate_borrowing_ticket_eligibility(
    borrowing_history: Iterable,
    borrower_email: str,  # รับ email ของผู้ยืมเพิ่มเข้ามา
    current_ticket_id=None,
):
    blocking_statuses = []
    blocking_records = []
    seen_statuses = set()

    # ทำความสะอาดข้อมูล email ที่ส่งเข้ามาเพื่อป้องกัน case sensitive หรือ space ขอบข้าง
    target_email = (borrower_email or "").strip().lower()

    for record in borrowing_history:
        record_id = _get_record_value(record, "id")
        if current_ticket_id is not None and record_id == current_ticket_id:
            continue

        # รองรับทั้งชื่อฟิลด์ของข้อมูลภายนอกและ BorrowingTicket ในระบบ
        record_email = (
            _get_record_value(record, "borrower_email")
            or _get_record_value(record, "email")
            or ""
        ).strip().lower()
        if record_email != target_email:
            continue  # ข้าม Record ที่ไม่ใช่ของผู้ยืมคนนี้

        status = (_get_record_value(record, "status") or "").strip()
        normalized_status = status.casefold()

        if normalized_status in {label.casefold() for label in IGNORED_STATUS_LABELS}:
            continue

        if normalized_status == "เคลียร์ยอดแล้ว":
            continue

        blocking_label = next(
            (
                label
                for label in ACTIVE_STATUS_LABELS.values()
                if label.casefold() == normalized_status
            ),
            None,
        )
        if blocking_label:
            if blocking_label not in seen_statuses:
                blocking_statuses.append(blocking_label)
                seen_statuses.add(blocking_label)
            blocking_records.append(record)

    return BorrowingTicketEligibility(
        is_eligible=not blocking_records,
        blocking_statuses=tuple(blocking_statuses),
        blocking_records=tuple(blocking_records),
    )

