"""Add status evidence timestamps to advance payment records.

Revision ID: p3c4d5e6f7a8
Revises: n2b3c4d5e6f7
"""

from alembic import op
import sqlalchemy as sa


revision = "p3c4d5e6f7a8"
down_revision = "n2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "cash_advance_borrowing_tickets",
        sa.Column("reject_approved_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "cash_advance_return_details",
        sa.Column("approved_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "cash_advance_return_details",
        sa.Column("reject_approved_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "cash_mng_parcel_return_details",
        sa.Column("approved_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "petty_cash_fund_requests",
        sa.Column("cancel_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "petty_cash_claim_details",
        sa.Column("approved_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("petty_cash_claim_details", "approved_at")
    op.drop_column("petty_cash_fund_requests", "cancel_at")
    op.drop_column("cash_mng_parcel_return_details", "approved_at")
    op.drop_column("cash_advance_return_details", "reject_approved_at")
    op.drop_column("cash_advance_return_details", "approved_at")
    op.drop_column("cash_advance_borrowing_tickets", "reject_approved_at")
