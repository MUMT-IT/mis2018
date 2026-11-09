"""Add settlement timestamps to finance records.

Revision ID: q0a1b2c3d4e5
Revises: e04a52c8d9f1
Create Date: 2026-10-07
"""

from alembic import op
import sqlalchemy as sa


revision = "q0a1b2c3d4e5"
down_revision = "e04a52c8d9f1"
branch_labels = None
depends_on = None


SETTLEMENT_TABLES = (
    "cash_advance_borrowing_tickets",
    "cash_advance_return_details",
    "cash_mng_parcel_return_details",
    "petty_cash_claim_details",
)

BORROWING_TICKET_INDEX = "ix_cash_advance_borrowing_tickets_settled_approved"


def upgrade():
    for table_name in SETTLEMENT_TABLES:
        op.add_column(
            table_name,
            sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        )

    op.create_index(
        BORROWING_TICKET_INDEX,
        "cash_advance_borrowing_tickets",
        ["settled_at", "approved_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        BORROWING_TICKET_INDEX,
        table_name="cash_advance_borrowing_tickets",
    )

    for table_name in reversed(SETTLEMENT_TABLES):
        op.drop_column(table_name, "settled_at")
