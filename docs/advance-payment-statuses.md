# Advance Payment Statuses

สถานะกลางสำหรับระบบเบิกจ่ายเงินล่วงหน้า โดย `code` เป็นชื่ออ้างอิงภาษาอังกฤษตัวพิมพ์ใหญ่คั่นด้วย underscore ส่วน `status_group` ใช้แยกระบบ

| id | Status group | Code | Name |
|---:|---|---:|---|
| — | `borrowing_ticket` | `PENDING` | กำลังส่งคำขอ |
| — | `borrowing_ticket` | `IN_PROGRESS` | กำลังดำเนินการ |
| — | `borrowing_ticket` | `APPROVED` | อนุมัติจ่ายเงิน |
| — | `borrowing_ticket` | `PARTIAL_RETURN` | มียอดคงค้าง |
| — | `borrowing_ticket` | `CLOSING_REJECTED` | ฎีกาถูกตีกลับจากกองคลัง |
| — | `borrowing_ticket` | `CLOSED` | เคลียร์ยอดแล้ว |
| — | `borrowing_ticket` | `REJECTED` | ปฏิเสธ |
| — | `return_detail` | `DRAFT` | ฉบับร่าง |
| — | `return_detail` | `PENDING` | รอตรวจสอบ |
| — | `return_detail` | `IN_PROGRESS` | กำลังตรวจสอบ |
| — | `return_detail` | `APPROVED` | ผ่านการตรวจสอบ |
| — | `return_detail` | `REJECTED` | ปฏิเสธ |
| — | `return_detail` | `EDIT_CONFIRMATION_REQUIRED` | รอยืนยันการแก้ไข |
| — | `return_detail` | `CLOSING_REJECTED` | ฎีกาถูกตีกลับจากกองคลัง |
| — | `return_detail` | `SETTLED` | ล้างลูกหนี้เงินยืม |
| — | `return_detail` | `CLOSING` | เอกสารตั้งฎีกา |
| — | `parcel_return` | `DRAFT` | ฉบับร่าง |
| — | `parcel_return` | `PENDING` | รอตรวจสอบ |
| — | `parcel_return` | `IN_PROGRESS` | กำลังตรวจสอบ |
| — | `parcel_return` | `REJECTED` | ปฏิเสธ |
| — | `parcel_return` | `EDIT_CONFIRMATION_REQUIRED` | รอยืนยันการแก้ไข |
| — | `parcel_return` | `IN_PROCESS` | พัสดุกำลังดำเนินการ |
| — | `parcel_return` | `DOCUMENT_RECEIVED` | ได้รับเอกสารแล้ว |
| — | `parcel_return` | `APPROVED` | ยืนยันการตรวจสอบ |
| — | `parcel_return` | `CASH_TRANSFER_COMPLETED` | โอนเงินสดย่อยสำเร็จ |
| — | `parcel_return` | `SETTLED` | ล้างลูกหนี้เงินยืม |
| — | `parcel_return` | `CLOSING` | เอกสารตั้งฎีกา |
| — | `fund_request` | `PENDING` | รอการอนุมัติ |
| — | `fund_request` | `APPROVED` | อนุมัติแล้ว |
| — | `fund_request` | `WITHDRAWN` | เบิกเงินแล้ว |
| — | `fund_request` | `CLAIMS_SUBMITTED` | ส่งเบิกครบแล้ว |
| — | `fund_request` | `SETTLED` | เคลียร์ยอดสำเร็จ |
| — | `fund_request` | `CLAIM_CANCELLED` | ยกเลิกใบเบิก |
| — | `fund_request` | `REJECTED` | ใบเบิกถูกปฏิเสธ |
| — | `petty_cash_claim` | `DRAFT` | ฉบับร่าง |
| — | `petty_cash_claim` | `PENDING` | รอตรวจสอบ |
| — | `petty_cash_claim` | `IN_PROCESS` | กำลังตรวจสอบ |
| — | `petty_cash_claim` | `APPROVED` | ผ่านการตรวจสอบ |
| — | `petty_cash_claim` | `REJECTED` | ปฏิเสธ |
| — | `petty_cash_claim` | `EDIT_CONFIRMATION_REQUIRED` | รอยืนยันการแก้ไข |
| — | `petty_cash_claim` | `CASH_RETURNED` | โอนคืนเงินสดย่อย |
| — | `petty_cash_claim` | `CASH_TRANSFER_COMPLETED` | โอนเงินสดย่อยสำเร็จ |
| — | `petty_cash_claim` | `SETTLED` | เสร็จสิ้นกระบวนการ |
