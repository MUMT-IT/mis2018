"""Seed advance-payment status codes."""

from alembic import op
import sqlalchemy as sa


revision = "s2t3u4v5w6x7"
down_revision = "r1s2t3u4v5w6"
branch_labels = None
depends_on = None


# (code, status_group, name)
STATUS_ROWS = (
    (101, "borrowing_ticket", "กำลังส่งคำขอ"),
    (102, "borrowing_ticket", "กำลังดำเนินการ"),
    (103, "borrowing_ticket", "อนุมัติแล้ว"),
    (104, "borrowing_ticket", "อนุมัติจ่ายเงิน"),
    (105, "borrowing_ticket", "มียอดคงค้าง"),
    (106, "borrowing_ticket", "เอกสารตั้งฎีกา"),
    (107, "borrowing_ticket", "ฎีกาถูกตีกลับจากกองคลัง"),
    (108, "borrowing_ticket", "เคลียร์ยอดแล้ว"),
    (109, "borrowing_ticket", "ปฏิเสธ"),
    (201, "return_detail", "ฉบับร่าง"),
    (202, "return_detail", "รอตรวจสอบ"),
    (203, "return_detail", "กำลังตรวจสอบ"),
    (204, "return_detail", "ผ่านการตรวจสอบ"),
    (205, "return_detail", "ปฏิเสธ"),
    (206, "return_detail", "รอยืนยันการแก้ไข"),
    (207, "return_detail", "ฎีกาถูกตีกลับจากกองคลัง"),
    (301, "parcel_return", "ฉบับร่าง"),
    (302, "parcel_return", "รอตรวจสอบ"),
    (303, "parcel_return", "กำลังตรวจสอบ"),
    (304, "parcel_return", "ผ่านการตรวจสอบ"),
    (305, "parcel_return", "ปฏิเสธ"),
    (306, "parcel_return", "ถูกปฏิเสธ"),
    (307, "parcel_return", "รอยืนยันการแก้ไข"),
    (308, "parcel_return", "พัสดุกำลังดำเนินการ"),
    (309, "parcel_return", "ได้รับเอกสารแล้ว"),
    (310, "parcel_return", "ยืนยันการตรวจสอบ"),
    (311, "parcel_return", "โอนเงินสดย่อยสำเร็จ"),
    (401, "fund_request", "รอการอนุมัติ"),
    (402, "fund_request", "อนุมัติแล้ว"),
    (403, "fund_request", "เบิกเงินแล้ว"),
    (404, "fund_request", "ส่งเบิกครบแล้ว"),
    (405, "fund_request", "เคลียร์ยอดสำเร็จ"),
    (406, "fund_request", "ยกเลิก"),
    (407, "fund_request", "ยกเลิกใบเบิก"),
    (408, "fund_request", "ฉบับร่าง"),
    (501, "petty_cash_claim", "ฉบับร่าง"),
    (502, "petty_cash_claim", "รอตรวจสอบ"),
    (503, "petty_cash_claim", "กำลังตรวจสอบ"),
    (504, "petty_cash_claim", "ผ่านการตรวจสอบ"),
    (505, "petty_cash_claim", "ปฏิเสธ"),
    (506, "petty_cash_claim", "ถูกปฏิเสธ"),
    (507, "petty_cash_claim", "รอยืนยันการแก้ไข"),
    (508, "petty_cash_claim", "โอนคืนเงินสดย่อย"),
    (509, "petty_cash_claim", "โอนเงินสดย่อยสำเร็จ"),
    (510, "petty_cash_claim", "เสร็จสิ้นกระบวนการ"),
    (511, "petty_cash_claim", "ยกเลิก"),
)


def upgrade():
    status_table = sa.table(
        "advance_payment_statuses",
        sa.column("status_group", sa.String),
        sa.column("code", sa.Integer),
        sa.column("name", sa.String),
    )
    op.bulk_insert(
        status_table,
        [
            {"status_group": group, "code": code, "name": name}
            for code, group, name in STATUS_ROWS
        ],
    )


def downgrade():
    status_table = sa.table(
        "advance_payment_statuses",
        sa.column("code", sa.Integer),
    )
    op.execute(
        status_table.delete().where(
            status_table.c.code.in_([code for code, _, _ in STATUS_ROWS])
        )
    )
