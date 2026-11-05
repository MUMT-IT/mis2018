"""Remove length limits from advance payment purpose and descriptions.

Revision ID: 0a4e6b8c2d1f
Revises: 782b3c72b3b6
"""

from alembic import op
import sqlalchemy as sa


revision = "0a4e6b8c2d1f"
down_revision = "782b3c72b3b6"
branch_labels = None
depends_on = None


STRING_COLUMNS = (
    ("cash_advance_borrowing_tickets", "borrowing_ticket_purpose", 255, False),
    ("cash_advance_return_receipt_items", "description", 255, False),
    ("petty_cash_fund_requests", "purpose", 1000, True),
    ("petty_cash_fund_request_items", "description", 255, False),
    ("petty_cash_claim_items", "description", 255, False),
)


def upgrade():
    for table_name, column_name, old_length, nullable in STRING_COLUMNS:
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.String(length=old_length),
            type_=sa.String(),
            existing_nullable=nullable,
        )


def downgrade():
    for table_name, column_name, old_length, nullable in reversed(STRING_COLUMNS):
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.String(),
            type_=sa.String(length=old_length),
            existing_nullable=nullable,
        )
