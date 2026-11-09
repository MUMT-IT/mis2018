"""Remove the assigned custodian from petty cash carryovers."""

from alembic import op


revision = "aa77cc88dd99"
down_revision = "z3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "fk_petty_cash_carryovers_custodian",
        "petty_cash_fiscal_year_carryovers",
        type_="foreignkey",
    )
    op.drop_column("petty_cash_fiscal_year_carryovers", "custodian_id")


def downgrade():
    import sqlalchemy as sa

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
