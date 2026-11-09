"""Add petty cash fiscal year carryover reconciliation."""

from alembic import op
import sqlalchemy as sa


revision = "x1b2c3d4e5f6"
down_revision = "w0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "petty_cash_fiscal_year_carryovers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("source_fiscal_year", sa.Integer(), nullable=False),
        sa.Column("target_fiscal_year", sa.Integer(), nullable=False),
        sa.Column("finance_budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("finance_pending_transfer", sa.Numeric(12, 2), nullable=True),
        sa.Column("custodian_bank_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("custodian_cash_on_hand", sa.Numeric(12, 2), nullable=True),
        sa.Column("custodian_pending_budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("finance_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("custodian_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "source_fiscal_year", "target_fiscal_year", name="uq_petty_cash_carryover_org_years"),
    )
    op.create_index("ix_petty_cash_fiscal_year_carryovers_org_id", "petty_cash_fiscal_year_carryovers", ["org_id"])


def downgrade():
    op.drop_index("ix_petty_cash_fiscal_year_carryovers_org_id", table_name="petty_cash_fiscal_year_carryovers")
    op.drop_table("petty_cash_fiscal_year_carryovers")
