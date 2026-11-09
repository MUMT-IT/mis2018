"""Mark remaining-money return receipt items as cash.

Revision ID: s2c3d4e5f6g7
Revises: r1b2c3d4e5f6
Create Date: 2026-10-08
"""

from alembic import op
import sqlalchemy as sa


revision = "s2c3d4e5f6g7"
down_revision = "r1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            """
            UPDATE public.cash_advance_return_receipt_items
            SET is_cash = true
            WHERE description = 'เงินเหลือส่งใช้เงินยืม'
            """
        )
    )


def downgrade():
    # This update cannot be reversed safely because rows that were already
    # marked as cash are indistinguishable from rows changed by this migration.
    pass
