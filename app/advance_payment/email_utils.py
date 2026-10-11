from datetime import date, datetime
from decimal import Decimal
import re


REJECTION_HISTORY_MARKER = re.compile(r"(?m)^ครั้งที่\s+\d+\s*:")
FINANCE_NOTIFICATION_EMAIL = "ploy.j0912@gmail.com"


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
        # Keep non-ASCII text outside strftime. On Windows, strftime may use
        # the active system locale encoding and fail on the Thai suffix.
        return value.strftime(f"%d/%m/{value.year + 543} %H:%M") + " น."
    if isinstance(value, date):
        return value.strftime(f"%d/%m/{value.year + 543}")
    return value


def _amount(value):
    return f"{Decimal(str(value or 0)):,.2f}"


def _ticket_name(ticket):
    return getattr(ticket, "borrowing_ticket_purpose", None) or getattr(ticket, "borrowing_ticket_name", None) or "-"


def _ticket_number(ticket):
    return getattr(ticket, "number", None) or "-"


def _normalize_recipient_email(email):
    """Return a complete Mahidol address for an internal account username."""
    normalized = str(email or "").strip().lower()
    if normalized and "@" not in normalized:
        normalized = f"{normalized}@mahidol.ac.th"
    return normalized


def latest_rejection_comment(value):
    """Return only the newest entry while preserving the stored history."""
    text = str(value or "").strip()
    if not text:
        return ""
    matches = list(REJECTION_HISTORY_MARKER.finditer(text))
    if not matches:
        return text
    return text[matches[-1].start():].strip()


def generate_finance_notification_email_content(
    target_object,
    notification_type,
    extra_ctx=None,
):
    """Build the finance-only pending-review and deadline notifications."""
    ctx = extra_ctx or {}
    recipient_emails = (FINANCE_NOTIFICATION_EMAIL,)
    footer = "ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย\nคณะเทคนิคการแพทย์"
    action_url = str(ctx.get("action_url") or "").strip()
    action_section = f"\n\n{action_url}" if action_url else ""

    if notification_type == "pending_review":
        document_type = str(ctx.get("document_type") or "รายการ").strip()
        reference = str(ctx.get("reference") or "").strip()
        document_label = " ".join(
            value for value in (document_type, reference) if value
        )
        person_name = str(ctx.get("person_name") or "-").strip()
        amount = _amount(ctx.get("amount", 0))
        created_at = thai_datetime(ctx.get("created_at")) or "-"

        subject = f"มีรายการใหม่รอตรวจสอบ: {document_label}"
        body = f"""เรียน ฝ่ายการเงิน

มีรายการใหม่ส่งเข้ามาเพื่อรอการตรวจสอบในระบบ

รายละเอียดรายการ
- ประเภทเอกสาร: {document_label}
- ผู้ยืม/ผู้ขอเบิก: {person_name}
- จำนวนเงิน: {amount} บาท
- วันที่สร้างรายการ: {created_at}
- สถานะปัจจุบัน: รอตรวจสอบ{action_section}

{footer}"""
    elif notification_type in {"upcoming", "overdue"}:
        number = _ticket_number(target_object)
        borrower_name = str(ctx.get("borrower_name") or "-").strip()
        due_date = thai_date(getattr(target_object, "due_date", None)) or "-"
        remaining_amount = _amount(ctx.get("remaining_amount", 0))

        if notification_type == "upcoming":
            subject = f"สัญญาเงินยืม บย.{number} ใกล้ครบกำหนด"
            intro = """สัญญาเงินยืมทดรองจ่ายต่อไปนี้ใกล้ถึงกำหนดส่งใช้
กรุณาตรวจสอบและติดตามผู้ยืมเพื่อดำเนินการส่งใช้เงินยืมภายในกำหนด"""
        else:
            subject = f"สัญญาเงินยืม บย.{number} เกินกำหนด"
            intro = """สัญญาเงินยืมทดรองจ่ายต่อไปนี้เกินกำหนดส่งใช้แล้ว
กรุณาตรวจสอบและติดตามผู้ยืมเพื่อดำเนินการส่งใช้เงินยืมโดยเร็ว"""

        body = f"""เรียน ฝ่ายการเงิน

{intro}

รายละเอียดสัญญา
- เลขที่สัญญา: บย.{number}
- ผู้ยืม: {borrower_name}
- วันครบกำหนดส่งใช้: {due_date}
- ยอดคงค้างปัจจุบัน: {remaining_amount} บาท{action_section}

{footer}"""
    else:
        raise ValueError(
            f"ไม่รองรับ finance notification_type: {notification_type}"
        )

    return {
        "to_emails": recipient_emails,
        "subject": subject,
        "body": body,
    }


def generate_notification_email_content(target_object, object_type="ticket", extra_ctx=None):
    ctx = extra_ctx or {}
    borrower_name = ctx.get("borrower_name", "ผู้รับบริการ")
    requester_name = ctx.get("requester_name", "ผู้ขอเบิก")
    recipient_emails = tuple(dict.fromkeys(
        normalized_email
        for normalized_email in (
            _normalize_recipient_email(email)
            for email in ctx.get("recipient_emails", ())
        )
        if normalized_email
    ))
    footer = "ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย\nคณะเทคนิคการแพทย์"

    if object_type == "ticket":
        ticket_name = _ticket_name(target_object)
        status = getattr(target_object, "status", "")
        number = _ticket_number(target_object)
        start_date = thai_date(getattr(target_object, "borrowing_ticket_start_date", None))
        end_date = thai_date(getattr(target_object, "borrowing_ticket_end_date", None))
        approved_at = thai_date(getattr(target_object, "approved_at", None))
        due_date = thai_date(getattr(target_object, "due_date", None))
        closed_date = thai_date(getattr(target_object, "closed_date", None))
        budget_request = _amount(
            getattr(target_object, "budget_request", None)
            or getattr(target_object, "required_budget", 0)
        )
        remaining_amount = _amount(ctx.get("remaining_amount", 0))
        rejection_reason = latest_rejection_comment(
            getattr(target_object, "rejection_comment", None)
        ) or "-"
        is_overdue = ctx.get("is_overdue", False)
        is_upcoming = ctx.get("is_upcoming", False)
        days_remaining = ctx.get("days_remaining", "")

        if is_overdue:
            subject = f"แจ้งติดตามการส่งใช้เงินยืมทดรองจ่าย บย. {number}"
            body = f"""สัญญาเงินยืมเงินทดรองจ่ายของท่านถึงวันครบกำหนดส่งใช้แล้ว กรุณาดำเนินการส่งเอกสารส่งใช้เงินยืม เพื่อป้องกันการหักเงินเดือนหรือเงินอื่นใดที่ได้รับจากมหาวิทยาลัยมหิดล

รายละเอียดสัญญา:
- ผู้ยืม {borrower_name}
- เลขที่สัญญา บย.{number}
- ยอดคงค้าง {remaining_amount} บาท
- ระยะเวลาโครงการ {start_date} - {end_date}
- วันครบกำหนดส่งคืน {due_date}

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif is_upcoming:
            subject = f"แจ้งติดตามการส่งใช้เงินยืมทดรองจ่าย บย. {number}"
            body = f"""สัญญาเงินยืมเงินทดรองจ่ายของท่านใกล้ถึงกำหนดส่งใช้แล้ว
กรุณาดำเนินการส่งเอกสารส่งใช้เงินยืมภายในกำหนด 15 วัน

รายละเอียดสัญญา:
- ผู้ยืม {borrower_name}
- เลขที่สัญญา บย.{number}
- ยอดคงค้าง {remaining_amount} บาท
- ระยะเวลาโครงการ {start_date} - {end_date}
- วันครบกำหนดส่งคืน {due_date}
  (เหลือเวลา {days_remaining} วันก่อนครบกำหนด)

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif status == "กำลังส่งคำขอ":
            subject = "แจ้งสถานะสัญญาเงินยืมทดรองจ่าย [กำลังส่งคำขอ]"
            body = f"""คำขอสัญญาเงินยืมทดรองจ่าย เพื่อ {ticket_name} ถูกบันทึกคำขอเรียบร้อยแล้ว

รายละเอียดสัญญา:
- ผู้ยืม {borrower_name}
- ระยะเวลาโครงการ {start_date} - {end_date}
- จำนวนเงิน {budget_request} บาท

**กรุณาดำเนินการส่งหนังสือขออนุมัติยืมเงินและสัญญาการยืมเงินผ่านระบบ e-office ต่อไป

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif status == "อนุมัติจ่ายเงิน":
            subject = "แจ้งสถานะสัญญาเงินยืมทดรองจ่าย [อนุมัติจ่ายเงิน]"
            body = f"""คำขอสัญญาเงินยืมทดรองจ่าย เพื่อ {ticket_name} ได้รับการอนุมัติเรียบร้อยแล้ว

รายละเอียดสัญญา:
- ผู้ยืม {borrower_name}
- เลขที่สัญญา บย.{number}
- วันที่ได้รับเงินยืม {approved_at}
- จำนวนเงิน {budget_request} บาท
- วันครบกำหนดส่งคืน {due_date}

**กรุณาดำเนินงานและส่งเอกสารส่งใช้เงินยืมภายในกำหนด

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif status == "เคลียร์ยอดแล้ว":
            subject = f"แจ้งสถานะสัญญาเงินยืมทดรองจ่าย บย. {number} [เคลียร์ยอดแล้ว]"
            body = f"""สัญญาเงินยืมทดรองจ่าย เลขที่ บย.{number} ได้รับการเคลียร์ยอดครบแล้ว

รายละเอียดสัญญา:
- ผู้ยืม {borrower_name}
- เลขที่สัญญา บย.{number}
- วันที่เคลียร์ยอด {closed_date}

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif status == "ปฏิเสธ":
            subject = "แจ้งสถานะสัญญาเงินยืมทดรองจ่าย [ปฏิเสธคำขอ]"
            body = f"""คำขอสัญญาเงินยืมเพื่อ {ticket_name} ถูกปฏิเสธ

เนื่องจาก {rejection_reason}

รายละเอียดสัญญา:
- ผู้ยืม {borrower_name}
- ระยะเวลาโครงการ {start_date} - {end_date}
- จำนวนเงิน {budget_request} บาท

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        else:
            subject = f"แจ้งสถานะสัญญาเงินยืมทดรองจ่าย [{status}]"
            body = f"ขอแจ้งอัปเดตสถานะสัญญาเงินยืมทดรองจ่าย\n\n- สถานะปัจจุบัน {status}"

    elif object_type == "return":
        ticket = ctx.get("ticket")
        number = _ticket_number(ticket) if ticket else "-"
        amount = _amount(getattr(target_object, "amount_spent", 0))
        status = getattr(target_object, "status", "")
        rejection_reason = latest_rejection_comment(
            getattr(target_object, "rejection_comment", None)
        ) or "-"
        status_label = {"รอตรวจสอบ": "รอการตรวจสอบ", "ผ่านการตรวจสอบ": "ผ่านการตรวจสอบ", "ปฏิเสธ": "ปฏิเสธหลักฐาน"}.get(status, status)
        subject = f"แจ้งสถานะเอกสารส่งใช้เงินยืมทดรองจ่ายบย. {number} [{status_label}]"
        if status == "รอตรวจสอบ":
            body = f"""หลักฐานเอกสารส่งใช้เงินยืมบย.{number} ถูกบันทึกเรียบร้อยแล้ว

รายละเอียดเอกสารส่งใช้เงินยืม:
- ผู้ยืม {borrower_name}
- จำนวนเงินในเอกสารชุดนี้ {amount} บาท

กรุณารอการตรวจสอบจากหน่วยการเงินฯ

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif status == "ผ่านการตรวจสอบ":
            body = f"""เอกสารส่งใช้เงินยืมบย.{number} จำนวนเงิน {amount} บาท
ได้รับการตรวจสอบหลักฐานว่าถูกต้องเรียบร้อยแล้ว

รายละเอียดเอกสารส่งใช้เงินยืม:
- ผู้ยืม {borrower_name}
- จำนวนเงินในเอกสารชุดนี้ {amount} บาท
- ยอดคงค้างปัจจุบัน {_amount(ctx.get("remaining_amount", 0))}

**กรุณาดำเนินการส่งหนังสือขออนุมัติเบิกจ่ายผ่านระบบ e-office ต่อไป

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif status == "ปฏิเสธ":
            body = f"""เอกสารส่งใช้เงินยืมบย.{number} ถูกปฏิเสธ

เนื่องจาก {rejection_reason}

รายละเอียดเอกสารส่งใช้เงินยืม:
- ผู้ยืม {borrower_name}
- จำนวนเงินในเอกสารชุดนี้ {amount} บาท

กรุณาดำเนินการแก้ไขข้อมูลและทำการบันทึกข้อมูลใหม่อีกครั้ง

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        else:
            body = f"ขอแจ้งอัปเดตสถานะเอกสารส่งใช้เงินยืม\n\n- สถานะปัจจุบัน {status}"

    elif object_type == "fund_request":
        ticket_number = getattr(target_object, "ticket_number", None) or "-"
        status = getattr(target_object, "status", "")
        action = ctx.get("action", "status")
        action_messages = {
            "confirm": "กรุณาตรวจสอบและยืนยันข้อมูลใบเบิก",
            "approve": "กรุณาตรวจสอบและอนุมัติใบเบิก",
            "withdrawal": "การอนุมัติครบถ้วนแล้ว กรุณาบันทึกวันที่เบิกเงิน",
            "withdrawn": "บันทึกการเบิกเงินเรียบร้อยแล้ว",
        }
        action_message = action_messages.get(
            action,
            f"สถานะปัจจุบัน: {status}",
        )
        action_url = ctx.get("action_url")
        action_link = f"\n- เปิดรายการ {action_url}" if action_url else ""
        subject = f"แจ้งดำเนินการใบเบิกเงินสดย่อย เลขที่ {ticket_number}"
        body = f"""{action_message}

รายละเอียดรายการ:
- เลขที่ใบเบิก {ticket_number}
- ผู้ขอเบิก {requester_name}
- จำนวนเงิน {_amount(getattr(target_object, 'amount', 0))} บาท
- สถานะ {status}{action_link}

{footer}"""

    elif object_type == "petty_claim":
        status = getattr(target_object, "status", "")
        fund_request = ctx.get("fund_request")
        ticket_number = getattr(fund_request, "ticket_number", None) or "-"
        items = [item for item in (getattr(target_object, "items", None) or []) if str(getattr(item, "category_type", "")).strip() != "6"]
        claim_amount = _amount(sum((Decimal(str(getattr(item, "amount", 0) or 0)) for item in items), Decimal("0")))
        transferred_at = thai_date(getattr(target_object, "transferred_at", None))
        rejection_reason = latest_rejection_comment(
            getattr(target_object, "rejection_comment", None)
        ) or "-"
        status_label = status
        subject = f"แจ้งสถานะรายการขออนุมัติเบิกค่าใช้จ่ายเงินสดย่อย เลขที่ {ticket_number} [{status_label}]"
        if status == "รอตรวจสอบ":
            intro = f" รายการขออนุมัติเบิกค่าใช้จ่าย เงินสดย่อย ใบเบิกเลขที่ {ticket_number} อยู่ระหว่างรอการตรวจสอบ"
            tail = "\n\nกรุณารอการตรวจสอบจากฝ่ายการเงิน"
        elif status == "ผ่านการตรวจสอบ":
            intro = f" รายการขออนุมัติเบิกค่าใช้จ่าย เงินสดย่อย ใบเบิกเลขที่ {ticket_number} ผ่านการตรวจสอบเรียบร้อยแล้ว"
            tail = "\n\n**กรุณาดำเนินการส่งหนังสือขออนุมัติเบิกจ่ายผ่านระบบ e-office ต่อไป"
        elif status == "ปฏิเสธ":
            intro = f" รายการขออนุมัติเบิกค่าใช้จ่าย เงินสดย่อย ใบเบิกเลขที่ {ticket_number} ถูกปฏิเสธ\n\nเนื่องจาก {rejection_reason}"
            tail = "\n\nกรุณาดำเนินการแก้ไขข้อมูลและทำการบันทึกข้อมูลใหม่อีกครั้ง"
        elif status == "โอนเงินสดย่อยสำเร็จ":
            intro = f"รายการขออนุมัติเบิกค่าใช้จ่าย เงินสดย่อย ใบเบิกเลขที่ {ticket_number} ได้รับการโอนเงินสดย่อยสำเร็จแล้ว\n\n- ผู้ยืม {requester_name}\n- จำนวนเงิน {claim_amount} บาท\n- วันที่โอนเงินสำเร็จ {transferred_at}"
            tail = ""
        else:
            intro = " ขอแจ้งอัปเดตสถานะรายการขออนุมัติเบิกเงินสดย่อย\n\n- สถานะปัจจุบัน " + status
            tail = ""
        body = f"""{intro}

รายละเอียดอนุมัติเบิกเงินสดย่อย
- ผู้ยืม {requester_name}
- จำนวนเงินในเอกสารชุดนี้ {claim_amount} บาท{tail}

{footer}"""

    elif object_type == "parcel_return":
        ticket = ctx.get("ticket")
        fund_request = ctx.get("fund_request")
        reference = f"สัญญาเงินยืม บย.{_ticket_number(ticket)}" if ticket else f"ใบเบิกเงินสดย่อยเลขที่{getattr(fund_request, 'ticket_number', None) or '-'}"
        status = getattr(target_object, "status", "")
        item_name = {
            1: "รายการส่งว-119",
            5: "รายการส่งว-5763",
        }.get(getattr(target_object, "type", None), "รายการส่งคืนพัสดุ")
        items_description = getattr(target_object, "items_description", None) or "-"
        amount = _amount(getattr(target_object, "amount_spent", 0))
        transferred_at = thai_date(getattr(target_object, "transferred_at", None))
        rejection_reason = latest_rejection_comment(
            getattr(target_object, "rejection_comment", None)
        ) or "-"
        status_label = "ถูกปฏิเสธ" if status in {"ปฏิเสธ", "ถูกปฏิเสธ"} else status
        subject = f"แจ้งสถานะ{item_name} [{status_label}]"
        tail = ""
        if status == "รอตรวจสอบ":
            intro = f"{item_name} ของ{reference} อยู่ระหว่างรอการตรวจสอบ"
            tail = "\n\nกรุณารอการตรวจสอบจากฝ่ายการเงิน"
        elif status == "พัสดุกำลังดำเนินการ":
            intro = f"{item_name} ของ{reference}\nอยู่ระหว่างกระบวนการการทำงานของพัสดุ"
        elif status == "ยืนยันการตรวจสอบ":
            intro = f"ฝ่ายการเงินได้รับเอกสาร{item_name} ของ{reference} เรียบร้อยแล้ว"
        elif status == "ได้รับเอกสารแล้ว":
            intro = f"ฝ่ายการเงินได้รับเอกสาร{item_name} ของ{reference} เรียบร้อยแล้ว"
        elif status == "โอนเงินสดย่อยสำเร็จ":
            intro = f"{item_name} ของ{reference} ได้รับการดำเนินการโอนคืนเงินสดย่อยสำเร็จแล้ว"
        elif status in {"ปฏิเสธ", "ถูกปฏิเสธ"}:
            intro = f"{item_name} ของ{reference} ถูกปฏิเสธ\n\nเนื่องจาก {rejection_reason}"
            tail = "\n\nกรุณาดำเนินการแก้ไขข้อมูลและทำการบันทึกข้อมูลใหม่อีกครั้ง"
        else:
            intro = f"ขอแจ้งอัปเดตสถานะ{item_name} ของ{reference}\n\n- สถานะปัจจุบัน {status}"
        transfer_line = f"\n- วันที่โอนเงินสำเร็จ {transferred_at}" if status == "โอนเงินสดย่อยสำเร็จ" else ""
        body = f"""{intro}

รายละเอียดรายการ:
- ผู้ยืม {borrower_name}
- รายการ {items_description}
- จำนวนเงิน {amount} บาท{transfer_line}{tail}

{footer}"""
    else:
        raise ValueError(f"ไม่รองรับ object_type: {object_type}")

    return {"to_emails": recipient_emails, "subject": subject, "body": body}
