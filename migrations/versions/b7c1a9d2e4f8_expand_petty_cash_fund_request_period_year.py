"""expand petty cash fund request period_year length

Revision ID: b7c1a9d2e4f8
Revises: ffb97545b5b7
Create Date: 2026-08-31 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7c1a9d2e4f8"
down_revision = "ffb97545b5b7"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "petty_cash_fund_requests",
        "period_year",
        existing_type=sa.String(length=10),
        type_=sa.String(length=100),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "petty_cash_fund_requests",
        "period_year",
        existing_type=sa.String(length=100),
        type_=sa.String(length=10),
        existing_nullable=True,
    )
