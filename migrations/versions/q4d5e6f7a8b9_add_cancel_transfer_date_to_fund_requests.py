"""Store the date cancelled fund-request money returned to the system."""

from alembic import op
import sqlalchemy as sa


revision = "q4d5e6f7a8b9"
down_revision = "90be85ea3bf8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "petty_cash_fund_requests",
        sa.Column("cancel_transferred_at", sa.Date(), nullable=True),
    )


def downgrade():
    op.drop_column("petty_cash_fund_requests", "cancel_transferred_at")
