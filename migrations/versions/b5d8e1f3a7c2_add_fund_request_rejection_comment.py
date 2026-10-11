"""Add the fund-request rejection comment.

Revision ID: b5d8e1f3a7c2
Revises: a4f7c9e2b6d1
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa


revision = "b5d8e1f3a7c2"
down_revision = "a4f7c9e2b6d1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "petty_cash_fund_requests",
        sa.Column("rejection_comment", sa.String(length=4000), nullable=True),
    )


def downgrade():
    op.drop_column("petty_cash_fund_requests", "rejection_comment")
