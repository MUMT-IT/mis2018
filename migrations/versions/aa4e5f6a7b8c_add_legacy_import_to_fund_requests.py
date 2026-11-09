"""Mark historical petty-cash fund requests imported by custodians."""

from alembic import op
import sqlalchemy as sa


revision = "aa4e5f6a7b8c"
down_revision = "c6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "petty_cash_fund_requests",
        sa.Column("is_legacy_import", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_petty_cash_fund_requests_is_legacy_import",
        "petty_cash_fund_requests",
        ["is_legacy_import"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_petty_cash_fund_requests_is_legacy_import",
        table_name="petty_cash_fund_requests",
    )
    op.drop_column("petty_cash_fund_requests", "is_legacy_import")
