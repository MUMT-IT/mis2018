"""Add an optional personal note to fund requests."""

from alembic import op
import sqlalchemy as sa


revision = "w0a1b2c3d4e5"
down_revision = "v9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "petty_cash_fund_requests",
        sa.Column("personal_note", sa.String(length=2000), nullable=True),
    )


def downgrade():
    op.drop_column("petty_cash_fund_requests", "personal_note")
