"""Add the assigned custodian to petty cash carryovers."""

from alembic import op
import sqlalchemy as sa


revision = "z3d4e5f6a7b8"
down_revision = "y2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    # Carryover rows created during development are not production data.
    op.execute(sa.text("DELETE FROM petty_cash_fiscal_year_carryovers"))
    op.add_column(
        "petty_cash_fiscal_year_carryovers",
        sa.Column("custodian_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_petty_cash_carryovers_custodian",
        "petty_cash_fiscal_year_carryovers",
        "staff_account",
        ["custodian_id"],
        ["id"],
    )
    op.alter_column(
        "petty_cash_fiscal_year_carryovers",
        "custodian_id",
        nullable=False,
    )


def downgrade():
    op.drop_constraint(
        "fk_petty_cash_carryovers_custodian",
        "petty_cash_fiscal_year_carryovers",
        type_="foreignkey",
    )
    op.drop_column("petty_cash_fiscal_year_carryovers", "custodian_id")
