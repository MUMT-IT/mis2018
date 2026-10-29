"""Consolidate advance-payment statuses into one catalog.

Revision ID: d72d68d9af22
Revises: 7bf3b205e354
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa


revision = "d72d68d9af22"
down_revision = "7bf3b205e354"
branch_labels = None
depends_on = None


# (table name, status group, original status column length)
STATUS_TABLES = (
    ("cash_advance_borrowing_tickets", "borrowing_ticket", 64),
    ("cash_advance_return_details", "return_detail", 32),
    ("cash_mng_parcel_return_details", "parcel_return", 32),
    ("petty_cash_fund_requests", "fund_request", 64),
    ("petty_cash_claim_details", "petty_cash_claim", 32),
)


# (status group, code, Thai name); keep in sync with docs/advance-payment-statuses.md.
STATUS_ROWS = (
    ("borrowing_ticket", "PENDING", "กำลังส่งคำขอ"),
    ("borrowing_ticket", "IN_PROGRESS", "กำลังดำเนินการ"),
    ("borrowing_ticket", "APPROVED", "อนุมัติจ่ายเงิน"),
    ("borrowing_ticket", "PARTIAL_RETURN", "มียอดคงค้าง"),
    ("borrowing_ticket", "CLOSING_REJECTED", "ฎีกาถูกตีกลับจากกองคลัง"),
    ("borrowing_ticket", "CLOSED", "เคลียร์ยอดแล้ว"),
    ("borrowing_ticket", "REJECTED", "ปฏิเสธ"),
    ("return_detail", "DRAFT", "ฉบับร่าง"),
    ("return_detail", "PENDING", "รอตรวจสอบ"),
    ("return_detail", "IN_PROGRESS", "กำลังตรวจสอบ"),
    ("return_detail", "APPROVED", "ผ่านการตรวจสอบ"),
    ("return_detail", "REJECTED", "ปฏิเสธ"),
    ("return_detail", "EDIT_CONFIRMATION_REQUIRED", "รอยืนยันการแก้ไข"),
    ("return_detail", "CLOSING_REJECTED", "ฎีกาถูกตีกลับจากกองคลัง"),
    ("return_detail", "SETTLED", "ล้างลูกหนี้เงินยืม"),
    ("return_detail", "CLOSING", "เอกสารตั้งฎีกา"),
    ("parcel_return", "DRAFT", "ฉบับร่าง"),
    ("parcel_return", "PENDING", "รอตรวจสอบ"),
    ("parcel_return", "IN_PROGRESS", "กำลังตรวจสอบ"),
    ("parcel_return", "REJECTED", "ปฏิเสธ"),
    ("parcel_return", "EDIT_CONFIRMATION_REQUIRED", "รอยืนยันการแก้ไข"),
    ("parcel_return", "IN_PROCESS", "พัสดุกำลังดำเนินการ"),
    ("parcel_return", "DOCUMENT_RECEIVED", "ได้รับเอกสารแล้ว"),
    ("parcel_return", "APPROVED", "ยืนยันการตรวจสอบ"),
    ("parcel_return", "CASH_TRANSFER_COMPLETED", "โอนเงินสดย่อยสำเร็จ"),
    ("parcel_return", "SETTLED", "ล้างลูกหนี้เงินยืม"),
    ("parcel_return", "CLOSING", "เอกสารตั้งฎีกา"),
    ("fund_request", "PENDING", "รอการอนุมัติ"),
    ("fund_request", "APPROVED", "อนุมัติแล้ว"),
    ("fund_request", "WITHDRAWN", "เบิกเงินแล้ว"),
    ("fund_request", "CLAIMS_SUBMITTED", "ส่งเบิกครบแล้ว"),
    ("fund_request", "SETTLED", "เคลียร์ยอดสำเร็จ"),
    ("fund_request", "CLAIM_CANCELLED", "ยกเลิกใบเบิก"),
    ("fund_request", "REJECTED", "ใบเบิกถูกปฏิเสธ"),
    ("petty_cash_claim", "DRAFT", "ฉบับร่าง"),
    ("petty_cash_claim", "PENDING", "รอตรวจสอบ"),
    ("petty_cash_claim", "IN_PROCESS", "กำลังตรวจสอบ"),
    ("petty_cash_claim", "APPROVED", "ผ่านการตรวจสอบ"),
    ("petty_cash_claim", "REJECTED", "ปฏิเสธ"),
    ("petty_cash_claim", "EDIT_CONFIRMATION_REQUIRED", "รอยืนยันการแก้ไข"),
    ("petty_cash_claim", "CASH_RETURNED", "โอนคืนเงินสดย่อย"),
    ("petty_cash_claim", "CASH_TRANSFER_COMPLETED", "โอนเงินสดย่อยสำเร็จ"),
    ("petty_cash_claim", "SETTLED", "เสร็จสิ้นกระบวนการ"),
)


def upgrade():
    op.create_table(
        "advance_payment_statuses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status_group", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint(
            "status_group", "code", name="uq_advance_payment_statuses_group_code"
        ),
    )
    op.create_index(
        "ix_advance_payment_statuses_status_group",
        "advance_payment_statuses",
        ["status_group"],
    )
    status_table = sa.table(
        "advance_payment_statuses",
        sa.column("status_group", sa.String(length=64)),
        sa.column("code", sa.String(length=64)),
        sa.column("name", sa.String(length=255)),
    )
    op.bulk_insert(
        status_table,
        [
            {"status_group": group, "code": code, "name": name}
            for group, code, name in STATUS_ROWS
        ],
    )

    connection = op.get_bind()
    for table_name, status_group, _ in STATUS_TABLES:
        op.add_column(table_name, sa.Column("status_id", sa.Integer(), nullable=True))
        op.create_index(f"ix_{table_name}_status_id", table_name, ["status_id"])
        op.create_foreign_key(
            f"fk_{table_name}_status_id",
            table_name,
            "advance_payment_statuses",
            ["status_id"],
            ["id"],
        )
        connection.execute(
            sa.text(
                f"UPDATE {table_name} AS target "
                "SET status_id = catalog.id "
                "FROM advance_payment_statuses AS catalog "
                "WHERE catalog.status_group = :status_group "
                "AND catalog.name = target.status"
            ),
            {"status_group": status_group},
        )
        missing = connection.execute(
            sa.text(f"SELECT COUNT(*) FROM {table_name} WHERE status_id IS NULL")
        ).scalar_one()
        if missing:
            raise RuntimeError(
                f"{table_name} has {missing} rows with no matching status name"
            )
        op.alter_column(
            table_name, "status_id", existing_type=sa.Integer(), nullable=False
        )
        op.drop_column(table_name, "status")


def downgrade():
    connection = op.get_bind()
    for table_name, status_group, status_length in reversed(STATUS_TABLES):
        op.add_column(
            table_name,
            sa.Column("status", sa.String(length=status_length), nullable=True),
        )
        connection.execute(
            sa.text(
                f"UPDATE {table_name} AS target "
                "SET status = catalog.name "
                "FROM advance_payment_statuses AS catalog "
                "WHERE catalog.id = target.status_id "
                "AND catalog.status_group = :status_group"
            ),
            {"status_group": status_group},
        )
        missing = connection.execute(
            sa.text(f"SELECT COUNT(*) FROM {table_name} WHERE status IS NULL")
        ).scalar_one()
        if missing:
            raise RuntimeError(
                f"{table_name} has {missing} status IDs without a matching name"
            )
        op.alter_column(
            table_name,
            "status",
            existing_type=sa.String(length=status_length),
            nullable=False,
        )
        op.drop_constraint(
            f"fk_{table_name}_status_id", table_name, type_="foreignkey"
        )
        op.drop_index(f"ix_{table_name}_status_id", table_name=table_name)
        op.drop_column(table_name, "status_id")

    op.drop_index(
        "ix_advance_payment_statuses_status_group",
        table_name="advance_payment_statuses",
    )
    op.drop_table("advance_payment_statuses")
