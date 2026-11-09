"""Add the fund-request approval timestamp.

Revision ID: a4f7c9e2b6d1
Revises: d4a5b6c7e8f9
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa


revision = "a4f7c9e2b6d1"
down_revision = "d4a5b6c7e8f9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "petty_cash_fund_requests",
        sa.Column("approved_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE petty_cash_fund_requests
            SET approved_at = created_at
            WHERE ticket_number IS NOT NULL
              AND TRIM(ticket_number) <> ''
            """
        )
    )


def downgrade():
    op.drop_column("petty_cash_fund_requests", "approved_at")
