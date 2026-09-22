"""Normalize advance payment money columns to Decimal-compatible values.

Revision ID: o3c4d5e6f7a8
Revises: n2b3c4d5e6f7
"""

from alembic import op
import sqlalchemy as sa


revision = "o3c4d5e6f7a8"
down_revision = "n2b3c4d5e6f7"
branch_labels = None
depends_on = None


MONEY_COLUMNS = (
    ("cash_advance_return_details", "amount_spent"),
    ("cash_advance_return_receipt_items", "amount"),
    ("cash_mng_parcel_return_details", "amount_spent"),
    ("cash_mng_closing_documents", "total_amount"),
    ("petty_cash_settings", "budget"),
    ("petty_cash_fund_requests", "amount"),
    ("petty_cash_fund_request_items", "amount"),
    ("petty_cash_claim_details", "total_amount"),
    ("petty_cash_claim_items", "amount"),
)

REQUIRED_MONEY_COLUMNS = (
    ("cash_advance_borrowing_tickets", "required_budget"),
)


def upgrade():
    for table_name, column_name in REQUIRED_MONEY_COLUMNS:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.alter_column(
                column_name,
                existing_type=sa.Numeric(precision=12, scale=2),
                type_=sa.Numeric(precision=12, scale=2, asdecimal=True),
                existing_nullable=False,
            )
    for table_name, column_name in MONEY_COLUMNS:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.alter_column(
                column_name,
                existing_type=sa.Numeric(precision=12, scale=2),
                type_=sa.Numeric(precision=12, scale=2, asdecimal=True),
                existing_nullable=False,
                server_default=sa.text("0.00"),
            )


def downgrade():
    for table_name, column_name in reversed(MONEY_COLUMNS):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.alter_column(
                column_name,
                existing_type=sa.Numeric(precision=12, scale=2, asdecimal=True),
                type_=sa.Numeric(precision=12, scale=2),
                existing_nullable=False,
                server_default=None,
            )
    for table_name, column_name in reversed(REQUIRED_MONEY_COLUMNS):
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.alter_column(
                column_name,
                existing_type=sa.Numeric(precision=12, scale=2, asdecimal=True),
                type_=sa.Numeric(precision=12, scale=2),
                existing_nullable=False,
            )
