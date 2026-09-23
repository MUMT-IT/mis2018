"""Track the user who creates each return detail.

Revision ID: d4e8a91f0c72
Revises: l0f1a2b3c4d5
"""

from alembic import op
import sqlalchemy as sa


revision = "d4e8a91f0c72"
down_revision = "l0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("cash_advance_return_details", sa.Column("creator_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_cash_advance_return_details_creator_id",
        "cash_advance_return_details",
        "staff_account",
        ["creator_id"],
        ["id"],
    )
    op.create_index(
        "ix_cash_advance_return_details_creator_id",
        "cash_advance_return_details",
        ["creator_id"],
    )
    # รายการเดิมยังไม่มีผู้สร้างรายการ จึงใช้ผู้สร้างสัญญาเป็นค่าอ้างอิงเดิม
    op.execute(
        sa.text(
            "UPDATE cash_advance_return_details AS return_detail "
            "SET creator_id = ticket.creator_id "
            "FROM cash_advance_borrowing_tickets AS ticket "
            "WHERE return_detail.ticket_id = ticket.id "
            "AND return_detail.creator_id IS NULL"
        )
    )


def downgrade():
    op.drop_index("ix_cash_advance_return_details_creator_id", table_name="cash_advance_return_details")
    op.drop_constraint(
        "fk_cash_advance_return_details_creator_id",
        "cash_advance_return_details",
        type_="foreignkey",
    )
    op.drop_column("cash_advance_return_details", "creator_id")
