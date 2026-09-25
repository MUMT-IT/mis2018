from datetime import date, datetime
from decimal import Decimal


def thai_date(value):
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime(f"%d/%m/{value.year + 543}")
    return value


def generate_notification_email_content(target_object, object_type="ticket", extra_ctx=None):
    ctx = extra_ctx or {}
    borrower_name = ctx.get("borrower_name", "ผู้รับบริการ")
    requester_name = ctx.get("requester_name", "ผู้ขอเบิก")
    recipient_emails = tuple(
        dict.fromkeys(
            email.strip()
            for email in ctx.get("recipient_emails", ())
            if email and email.strip()
        )
    )

    if object_type == "ticket":
        ticket_name = getattr(target_object, "borrowing_ticket_purpose", None) or target_object.borrowing_ticket_name
        status = target_object.status
        remaining_amount = ctx.get("remaining_amount", 0.0)
        approved_at_str = thai_date(target_object.approved_at)
        closed_date_str = thai_date(target_object.closed_date)
        due_date_str = thai_date(target_object.due_date)

        status_mapping = {
            "กำลังส่งคำขอ": ("กำลังส่งคำขอ", f"เรียนคุณ {borrower_name},\n\nระบบได้รับคำขอสัญญาเงินยืมโครงการ {ticket_name} เรียบร้อยแล้ว ขณะนี้อยู่ระหว่างรอการตรวจสอบจากฝ่ายการเงิน"),
            "อนุมัติจ่ายเงิน": ("อนุมัติจ่ายเงิน", f"เรียนคุณ {borrower_name},\n\nสัญญาเงินยืมโครงการ {ticket_name} ได้รับการอนุมัติเรียบร้อยแล้ว กรุณาดำเนินงานและส่งเอกสารส่งใช้เงินยืมภายในกำหนด"),
            "มียอดคงค้าง": ("มียอดคงค้าง", f"เรียนคุณ {borrower_name},\n\nฝ่ายการเงินได้รับเอกสารส่งใช้บางส่วนของโครงการ {ticket_name} แล้ว แต่ยังมีรายละเอียดคงค้างตามด้านล่าง"),
            "เคลียร์ยอดแล้ว": ("เคลียร์ยอดแล้ว", f"เรียนคุณ {borrower_name},\n\nสัญญาเงินยืมโครงการ {ticket_name} ได้ทำการส่งใช้เงินยืมและตรวจสอบยอดครบถ้วนเสร็จสิ้นแล้ว"),
            "ปฏิเสธ": ("ปฏิเสธคำขอ", f"เรียนคุณ {borrower_name},\n\nคำขอสัญญาเงินยืมโครงการ {ticket_name} ถูกปฏิเสธ\nเหตุผล: {target_object.rejection_comment or '-'}"),
        }

        is_overdue = ctx.get("is_overdue", False)
        is_upcoming = ctx.get("is_upcoming", False)
        days_remaining = ctx.get("days_remaining", False)
        if is_overdue:
            subject = f"[ทวงถามกำหนดส่งคืน] สัญญาเงินยืมเงินทดรองจ่ายโครงการ {ticket_name}"
            intro_text = f"เรียนคุณ {borrower_name},\n\nเนื่องจากขณะนี้ระบบพบว่าสัญญาเงินยืมเงินทดรองจ่ายของท่านถึงกำหนดหรือเกินกำหนดเวลาแล้ว ขอความอนุเคราะห์ตรวจสอบและดำเนินการส่งเอกสารส่งใช้เงินยืม"
            status_th = "เกินกำหนดส่งใช้"
        elif is_upcoming:
            subject = f"[ทวงถามกำหนดส่งคืน(เหลือเวลา {days_remaining} วัน)] สัญญาเงินยืมเงินทดรองจ่ายโครงการ {ticket_name}"
            intro_text = f"เรียนคุณ {borrower_name},\n\nเนื่องจากขณะนี้ระบบพบว่าสัญญาเงินยืมเงินทดรองจ่ายของท่านใกล้ถึงกำหนดแล้ว ขอความอนุเคราะห์ตรวจสอบและดำเนินการส่งเอกสารส่งใช้เงินยืม"
            status_th = "ใกล้ถึงกำหนดส่งใช้"
        else:
            status_th, intro_text = status_mapping.get(status, (status, f"เรียนคุณ {borrower_name},\n\nขอแจ้งอัปเดตสถานะสัญญาเงินยืมของท่าน"))
            subject = f"[แจ้งเตือน] อัปเดตสถานะสัญญาเงินยืมโครงการ {ticket_name} [{status_th}]"

        details = ""
        if status not in ["กำลังส่งคำขอ", "ปฏิเสธ"]:
            details = f"""
- วันที่จ่ายเงิน: {approved_at_str}
- ยอดเงินยืมคงค้าง: {remaining_amount:,.2f} บาท
- วันครบกำหนดส่งคืน: {due_date_str} {f"(เหลือเวลา {days_remaining} วันก่อนครบกำหนด)" if is_upcoming else " "}
- วันที่เคลียร์ยอด: {closed_date_str}
"""

        body = f"""{intro_text}

รายละเอียดสัญญา:
- ชื่อโครงการ: {ticket_name}
- สถานะปัจจุบัน: {status_th}{details}
หากท่านมีข้อสงสัยประการใด สามารถติดต่อประสานงานกับฝ่ายการเงินได้ทันที

ขอแสดงความนับถือ
ฝ่ายการเงินและบัญชี
"""

    elif object_type == "return":
        ticket = ctx.get("ticket")
        ticket_name = (
            getattr(ticket, "borrowing_ticket_purpose", None)
            if ticket
            else "-"
        ) or (getattr(ticket, "borrowing_ticket_name", None) if ticket else "-")
        status = target_object.status
        amount_spent = target_object.amount_spent or 0.0

        status_mapping = {
            "รอตรวจสอบ": ("รอการตรวจสอบ", f"เรียนคุณ {borrower_name},\n\nฝ่ายการเงินได้รับหลักฐานเอกสารส่งใช้เงินยืมโครงการ {ticket_name} จำนวนเงิน {amount_spent:,.2f} บาท เรียบร้อยแล้ว ขณะนี้กำลังอยู่ระหว่างตรวจสอบหลักฐาน"),
            "กำลังตรวจสอบ": ("กำลังตรวจสอบ", f"เรียนคุณ {borrower_name},\n\nฝ่ายการเงินกำลังทำการตรวจสอบความถูกต้องของรายการใบเสร็จในเอกสารส่งใช้เงินยืมโครงการ {ticket_name}"),
            "ผ่านการตรวจสอบ": ("ผ่านการตรวจสอบ", f"เรียนคุณ {borrower_name},\n\nเอกสารส่งใช้เงินยืมโครงการ {ticket_name} จำนวนเงิน {amount_spent:,.2f} บาท ได้รับการตรวจสอบหลักฐานว่าถูกต้องเรียบร้อยแล้ว"),
            "ปฏิเสธ": ("ปฏิเสธหลักฐาน", f"เรียนคุณ {borrower_name},\n\nเอกสารส่งใช้เงินยืมโครงการ {ticket_name} ถูกปฏิเสธเนื่องจากหลักฐานไม่ครบถ้วนหรือไม่ถูกต้อง\nรายละเอียด: {target_object.rejection_comment if target_object.rejection_comment else '-'}"),
        }

        status_th, intro_text = status_mapping.get(status, (status, f"เรียนคุณ {borrower_name},\n\nขอแจ้งอัปเดตสถานะเอกสารส่งใช้เงินยืมของท่าน"))
        subject = f"[แจ้งเตือน] อัปเดตสถานะเอกสารส่งใช้เงินยืมโครงการ {ticket_name} [{status_th}]"

        body = f"""{intro_text}

รายละเอียดเอกสารส่งใช้เงินยืม:
- โครงการ: {ticket_name}
- จำนวนเงินในเอกสารชุดนี้: {amount_spent:,.2f} บาท
- สถานะเอกสาร: {status_th}

ท่านสามารถติดตามสถานะการส่งใช้เงินยืมแบบละเอียดได้ทางแผงควบคุมระบบ

ขอแสดงความนับถือ
ฝ่ายการเงินและบัญชี
"""

    if object_type == "petty_claim":
        status = target_object.status
        display_items = [
            item
            for item in (getattr(target_object, "items", None) or [])
            if str(getattr(item, "category_type", "")).strip() != "6"
        ]
        claim_amount = sum(
            (Decimal(str(getattr(item, "amount", 0) or 0)) for item in display_items),
            Decimal("0.00"),
        )
        item_lines = "\n".join(
            f"{idx}. {getattr(item, 'description', None) or '-'}    "
            f"{Decimal(str(getattr(item, 'amount', 0) or 0)):,.2f} บาท"
            for idx, item in enumerate(display_items, 1)
        ) or "-"
        transferred_at = thai_date(getattr(target_object, "transferred_at", None))

        status_mapping = {
            "รอตรวจสอบ": f"เรียนคุณ {requester_name},\n\nรายการขออนุมัติเบิกเงินสดย่อย จำนวนเงิน {claim_amount:,.2f} บาท อยู่ระหว่างรอการตรวจสอบ",
            "กำลังตรวจสอบ": f"เรียนคุณ {requester_name},\n\nรายการขออนุมัติเบิกเงินสดย่อย จำนวนเงิน {claim_amount:,.2f} บาท กำลังอยู่ระหว่างการตรวจสอบ",
            "ผ่านการตรวจสอบ": f"เรียนคุณ {requester_name},\n\nรายการขออนุมัติเบิกเงินสดย่อย จำนวนเงิน {claim_amount:,.2f} บาท ผ่านการตรวจสอบเรียบร้อยแล้ว",
            "โอนเงินสดย่อยสำเร็จ": f"เรียนคุณ {requester_name},\n\nรายการขออนุมัติเบิกเงินสดย่อย จำนวนเงิน {claim_amount:,.2f} บาท โอนเงินสดย่อยสำเร็จแล้ว",
            "ปฏิเสธ": f"เรียนคุณ {requester_name},\n\nรายการขออนุมัติเบิกเงินสดย่อย จำนวนเงิน {claim_amount:,.2f} บาท ถูกปฏิเสธ",
        }
        status_th = status
        intro_text = status_mapping.get(
            status,
            f"เรียนคุณ {requester_name},\n\nขอแจ้งอัปเดตสถานะรายการขออนุมัติเบิกเงินสดย่อย",
        )
        rejection_text = (
            f"- เหตุผล: {getattr(target_object, 'rejection_comment', None) or '-'}\n"
            if status == "ปฏิเสธ"
            else ""
        )
        transfer_text = (
            f"- วันที่โอนเงิน: {transferred_at}\n"
            if status == "โอนเงินสดย่อยสำเร็จ" and transferred_at
            else ""
        )
        subject = f"[แจ้งเตือน] อัปเดตสถานะรายการขออนุมัติเบิกเงินสดย่อย [{status_th}]"
        body = f"""{intro_text}

- สถานะปัจจุบัน: {status_th}
{rejection_text}{transfer_text}
รายละเอียดรายการขออนุมัติเบิกเงินสดย่อย:
{item_lines}

รวมทั้งสิ้น                                         {claim_amount:,.2f} บาท

กรุณาตรวจสอบรายละเอียดและดำเนินการตามความเหมาะสม

ขอแสดงความนับถือ
ฝ่ายการเงินและบัญชี
"""

    if object_type == "parcel_return":
        ticket = ctx.get("ticket")
        fund_request = ctx.get("fund_request")
        ticket_name = (
            getattr(ticket, "borrowing_ticket_purpose", None)
            if ticket
            else (fund_request.purpose if fund_request and fund_request.purpose else None)
            or (fund_request.ticket_number if fund_request and fund_request.ticket_number else None)
            or "-"
        )
        status = target_object.status
        amount_spent = target_object.amount_spent or 0.0
        items_description = target_object.items_description or "-"

        status_mapping = {
            "พัสดุกำลังดำเนินการ": ("พัสดุกำลังดำเนินการ", f"เรียนคุณ {borrower_name},\n\nรายการส่งคืนพัสดุของโครงการ {ticket_name} ผ่านการตรวจสอบเบื้องต้นแล้ว"),
            "ได้รับเอกสารแล้ว": ("ได้รับเอกสารแล้ว", f"เรียนคุณ {borrower_name},\n\nรายการส่งคืนพัสดุของโครงการ {ticket_name} ฝ่ายการเงินได้รับเอกสารเรียบร้อยแล้ว"),
            "โอนเงินสดย่อยสำเร็จ": ("โอนเงินสดย่อยสำเร็จ", f"เรียนคุณ {borrower_name},\n\nรายการส่งคืนพัสดุของโครงการ {ticket_name} โอนเงินสดย่อยสำเร็จแล้ว"),
            "ปฏิเสธ": ("ปฏิเสธ", f"เรียนคุณ {borrower_name},\n\nรายการส่งคืนพัสดุของโครงการ {ticket_name} ถูกปฏิเสธ\nเหตุผล: {target_object.rejection_comment or '-'}"),
        }

        status_th, intro_text = status_mapping.get(
            status,
            (status, f"เรียนคุณ {borrower_name},\n\nขอแจ้งอัปเดตสถานะรายการส่งคืนพัสดุของโครงการ {ticket_name}"),
        )
        subject = f"[แจ้งเตือน] อัปเดตสถานะรายการส่งคืนพัสดุ [{status_th}]"
        body = f"""{intro_text}

รายละเอียดรายการ:
- โครงการ: {ticket_name}
- รายละเอียดพัสดุ: {items_description}
- จำนวนเงิน: {amount_spent:,.2f} บาท
- สถานะปัจจุบัน: {status_th}

หากต้องการตรวจสอบรายละเอียดเพิ่มเติม สามารถดูได้จากระบบตามปกติ

ขอแสดงความนับถือ
ฝ่ายการเงินและบัญชี
"""

    return {
        "to_emails": recipient_emails,
        "subject": subject,
        "body": body,
    }
