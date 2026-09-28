from datetime import date, datetime
from decimal import Decimal


def thai_date(value):
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
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
        rejection_reason = getattr(target_object, "rejection_comment", None) or "-"
        is_overdue = ctx.get("is_overdue", False)
        is_upcoming = ctx.get("is_upcoming", False)
        days_remaining = ctx.get("days_remaining", "")

        if is_overdue:
            subject = "[แจ้งกำหนดส่งเอกสารส่งใช้เงินยืม] สัญญาเงินยืมเงินทดรองจ่าย"
            body = f"""เนื่องจากขณะนี้ระบบพบว่าสัญญาเงินยืมเงินทดรองจ่ายของท่านถึงวันครบกำหนดแล้ว
ขอความอนุเคราะห์ตรวจสอบและดำเนินการส่งเอกสารส่งใช้เงินยืม

รายละเอียดสัญญา:
- ชื่อผู้ยืม {borrower_name}
- เลขที่สัญญา บย.{number}
- จำนวนเงิน {remaining_amount}
- ระยะเวลาโครงการ {start_date} - {end_date}
- วันครบกำหนดส่งคืน {due_date}

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif is_upcoming:
            subject = f"[แจ้งกำหนดส่งเอกสารส่งใช้เงินยืม(เหลือเวลา {days_remaining} วัน)] สัญญาเงินยืมเงินทดรองจ่าย"
            body = f"""เนื่องจากสัญญาเงินยืมเงินทดรองจ่ายของท่านใกล้ถึงกำหนดแล้ว
ขอความอนุเคราะห์ตรวจสอบและดำเนินการส่งเอกสารส่งใช้เงินยืม

รายละเอียดสัญญา:
- ชื่อผู้ยืม {borrower_name}
- เลขที่สัญญา บย.{number}
- จำนวนเงิน {remaining_amount}
- ระยะเวลาโครงการ {start_date} - {end_date}
- วันครบกำหนดส่งคืน {due_date}
  (เหลือเวลา {days_remaining} วันก่อนครบกำหนด)

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif status == "กำลังส่งคำขอ":
            subject = "แจ้งสถานะสัญญาเงินยืมทดรองจ่าย [กำลังส่งคำขอ]"
            body = f"""คำขอสัญญาเงินยืมเพื่อ {ticket_name} ถูกบันทึกคำขอเรียบร้อยแล้ว

รายละเอียดสัญญา:
- ชื่อผู้ยืม {borrower_name}
- ระยะเวลาโครงการ {start_date} - {end_date}
- จำนวนเงิน {budget_request}

**กรุณาดำเนินการส่งหนังสือขออนุมัติยืมเงินและสัญญาการยืมเงินผ่านระบบ e-office ต่อไป

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif status == "อนุมัติจ่ายเงิน":
            subject = "แจ้งสถานะสัญญาเงินยืมทดรองจ่าย [อนุมัติจ่ายเงิน]"
            body = f"""คำขอสัญญาเงินยืมเพื่อ {ticket_name} ได้รับการอนุมัติเรียบร้อยแล้ว

รายละเอียดสัญญา:
- ชื่อผู้ยืม {borrower_name}
- เลขที่สัญญา บย.{number}
- วันที่ได้รับเงินยืม {approved_at}
- จำนวนเงิน {budget_request}
- วันครบกำหนดส่งคืน {due_date}

**กรุณาดำเนินงานและส่งเอกสารส่งใช้เงินยืมภายในกำหนด

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif status == "เคลียร์ยอดแล้ว":
            subject = "แจ้งสถานะสัญญาเงินยืมทดรองจ่าย [เคลียร์ยอดแล้ว]"
            body = f"""สัญญาเงินยืมเพื่อ {ticket_name} ได้รับการเคลียร์ยอดครบถ้วนแล้ว

รายละเอียดสัญญา:
- ชื่อผู้ยืม {borrower_name}
- เลขที่สัญญา บย.{number}
- สถานะปัจจุบัน เคลียร์ยอดแล้ว
- วันที่เคลียร์ยอด {closed_date}

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif status == "ปฏิเสธ":
            subject = "แจ้งสถานะสัญญาเงินยืมทดรองจ่าย [ปฏิเสธคำขอ]"
            body = f"""คำขอสัญญาเงินยืมเพื่อ {ticket_name} ถูกปฏิเสธ

เนื่องจาก {rejection_reason}

รายละเอียดสัญญา:
- ชื่อผู้ยืม {borrower_name}
- ระยะเวลาโครงการ {start_date} - {end_date}
- จำนวนเงิน {budget_request}

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
        rejection_reason = getattr(target_object, "rejection_comment", None) or "-"
        status_label = {"รอตรวจสอบ": "รอการตรวจสอบ", "ผ่านการตรวจสอบ": "ผ่านการตรวจสอบ", "ปฏิเสธ": "ปฏิเสธหลักฐาน"}.get(status, status)
        subject = f"แจ้งสถานะเอกสารส่งใช้เงินยืมของสัญญาเงินยืมเงินทดรองจ่าย [{status_label}]"
        if status == "รอตรวจสอบ":
            body = f"""หลักฐานเอกสารส่งใช้เงินยืมบย.{number} ถูกบันทึกเรียบร้อยแล้ว

รายละเอียดเอกสารส่งใช้เงินยืม:
- ชื่อผู้ยืม {borrower_name}
- จำนวนเงินในเอกสารชุดนี้ {amount} บาท

กรุณารอการตรวจสอบจากฝ่ายการเงิน

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif status == "ผ่านการตรวจสอบ":
            body = f"""เอกสารส่งใช้เงินยืมบย.{number} จำนวนเงิน {amount} บาท
ได้รับการตรวจสอบหลักฐานว่าถูกต้องเรียบร้อยแล้ว

รายละเอียดเอกสารส่งใช้เงินยืม:
- ชื่อผู้ยืม {borrower_name}
- จำนวนเงินในเอกสารชุดนี้ {amount} บาท
- ยอดคงค้างปัจจุบัน {_amount(ctx.get("remaining_amount", 0))}

**กรุณาดำเนินการส่งหนังสือขออนุมัติเบิกจ่ายผ่านระบบ e-office ต่อไป

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        elif status == "ปฏิเสธ":
            body = f"""เอกสารส่งใช้เงินยืมบย.{number} ถูกปฏิเสธ

เนื่องจาก {rejection_reason}

รายละเอียดเอกสารส่งใช้เงินยืม:
- ชื่อผู้ยืม {borrower_name}
- จำนวนเงินในเอกสารชุดนี้ {amount} บาท

กรุณาดำเนินการแก้ไขข้อมูลและทำการบันทึกข้อมูลใหม่อีกครั้ง

ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย
คณะเทคนิคการแพทย์"""
        else:
            body = f"ขอแจ้งอัปเดตสถานะเอกสารส่งใช้เงินยืม\n\n- สถานะปัจจุบัน {status}"

    elif object_type == "petty_claim":
        status = getattr(target_object, "status", "")
        fund_request = ctx.get("fund_request")
        ticket_number = getattr(fund_request, "ticket_number", None) or "-"
        items = [item for item in (getattr(target_object, "items", None) or []) if str(getattr(item, "category_type", "")).strip() != "6"]
        claim_amount = _amount(sum((Decimal(str(getattr(item, "amount", 0) or 0)) for item in items), Decimal("0")))
        transferred_at = thai_date(getattr(target_object, "transferred_at", None))
        status_label = status
        subject = f"แจ้งสถานะรายการขออนุมัติเบิกเงินสดย่อย [{status_label}]"
        if status == "รอตรวจสอบ":
            intro = f" รายการขออนุมัติเบิกเงินสดย่อยของใบเบิกเลขที่ {ticket_number} อยู่ระหว่างรอการตรวจสอบ"
            tail = "\n\nกรุณารอการตรวจสอบจากฝ่ายการเงิน"
        elif status == "ผ่านการตรวจสอบ":
            intro = f" รายการขออนุมัติเบิกเงินสดย่อยของใบเบิกเลขที่ {ticket_number} ผ่านการตรวจสอบเรียบร้อยแล้ว"
            tail = "\n\n**กรุณาดำเนินการส่งหนังสือขออนุมัติเบิกจ่ายผ่านระบบ e-office ต่อไป"
        elif status == "ปฏิเสธ":
            intro = f" รายการขออนุมัติเบิกเงินสดย่อยของใบเบิกเลขที่ {ticket_number} ถูกปฏิเสธ\n\nเนื่องจาก {getattr(target_object, 'rejection_comment', None) or '-'}"
            tail = "\n\nกรุณาดำเนินการแก้ไขข้อมูลและทำการบันทึกข้อมูลใหม่อีกครั้ง"
        elif status == "โอนเงินสดย่อยสำเร็จ":
            intro = f"รายการขออนุมัติเบิกเงินสดย่อยของใบเบิกเลขที่ {ticket_number} ได้รับการโอนเงินสดย่อยสำเร็จแล้ว\n\n- ชื่อผู้ยืม {requester_name}\n- จำนวนเงิน {claim_amount} บาท\n- วันที่โอนเงินสำเร็จ {transferred_at}"
            tail = ""
        else:
            intro = " ขอแจ้งอัปเดตสถานะรายการขออนุมัติเบิกเงินสดย่อย\n\n- สถานะปัจจุบัน " + status
            tail = ""
        body = f"""{intro}

รายละเอียดอนุมัติเบิกเงินสดย่อย
- ชื่อผู้ยืม {requester_name}
- จำนวนเงินในเอกสารชุดนี้ {claim_amount} บาท{tail}

{footer}"""

    elif object_type == "parcel_return":
        ticket = ctx.get("ticket")
        fund_request = ctx.get("fund_request")
        footer = "ระบบจัดการเงินยืมทดรองจ่ายและเงินสดย่อย\nคณะเทคนิคการแพทย์"
        reference = f"สัญญาเงินยืม บย.{_ticket_number(ticket)}" if ticket else f"ใบเบิกเงินสดย่อยเลขที่{getattr(fund_request, 'ticket_number', None) or '-'}"
        status = getattr(target_object, "status", "")
        items_description = getattr(target_object, "items_description", None) or "-"
        amount = _amount(getattr(target_object, "amount_spent", 0))
        transferred_at = thai_date(getattr(target_object, "transferred_at", None))
        subject = f"แจ้งสถานะรายการส่งคืนพัสดุ [{ {'ปฏิเสธ': 'ถูกปฏิเสธ'}.get(status, status) }]"
        if status == "พัสดุกำลังดำเนินการ":
            intro = f"รายการส่งคืนพัสดุของ{reference}\nอยู่ระหว่างกระบวนการการทำงานของพัสดุ"
        elif status == "ได้รับเอกสารแล้ว":
            intro = f"ฝ่ายการเงินได้รับเอกสารรายการส่งคืนพัสดุของ{reference} เรียบร้อยแล้ว"
        elif status == "โอนเงินสดย่อยสำเร็จ":
            intro = f"รายการส่งคืนพัสดุของใบเบิกเงินสดย่อยเลขที่{getattr(fund_request, 'ticket_number', None) or '-'} ได้รับการดำเนินการโอนคืนเงินสดย่อยสำเร็จแล้ว"
        else:
            intro = f"รายการส่งคืนพัสดุของ{reference} ถูกปฏิเสธ\n\nเนื่องจาก {getattr(target_object, 'rejection_comment', None) or '-'}"
        transfer_line = f"\n- วันที่โอนเงินสำเร็จ {transferred_at}" if status == "โอนเงินสดย่อยสำเร็จ" else ""
        body = f"""{intro}

รายละเอียดรายการ:
- ชื่อผู้ยืม {borrower_name}
- รายการ {items_description}
- จำนวนเงิน {amount} บาท{transfer_line}

{footer}"""
    else:
        raise ValueError(f"ไม่รองรับ object_type: {object_type}")

    return {"to_emails": recipient_emails, "subject": subject, "body": body}
