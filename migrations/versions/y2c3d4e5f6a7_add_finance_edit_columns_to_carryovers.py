"""Add finance edit audit columns to petty cash carryovers."""

from alembic import op
import sqlalchemy as sa


revision = "y2c3d4e5f6a7"
down_revision = "x1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "petty_cash_fiscal_year_carryovers",
        sa.Column("last_edited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "petty_cash_fiscal_year_carryovers",
        sa.Column("last_edited_by_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_petty_cash_carryovers_last_edited_by",
        "petty_cash_fiscal_year_carryovers",
        "staff_account",
        ["last_edited_by_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(
        "fk_petty_cash_carryovers_last_edited_by",
        "petty_cash_fiscal_year_carryovers",
        type_="foreignkey",
    )
    op.drop_column("petty_cash_fiscal_year_carryovers", "last_edited_by_id")
    op.drop_column("petty_cash_fiscal_year_carryovers", "last_edited_at")
