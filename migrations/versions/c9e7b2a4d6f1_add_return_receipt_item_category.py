"""Store the finance category on each return receipt item.

Revision ID: c9e7b2a4d6f1
Revises: 76c5a38fc0e0
"""

from alembic import op
import sqlalchemy as sa


revision = "c9e7b2a4d6f1"
down_revision = "76c5a38fc0e0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "cash_advance_return_receipt_items",
        sa.Column("category_type", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_return_receipt_item_finance_category",
        "cash_advance_return_receipt_items",
        "category_type IS NULL OR (NOT is_cash AND category_type IN (1, 2, 3, 4, 7, 8))",
    )


def downgrade():
    op.drop_constraint(
        "ck_return_receipt_item_finance_category",
        "cash_advance_return_receipt_items",
        type_="check",
    )
    op.drop_column("cash_advance_return_receipt_items", "category_type")
