"""allow one petty cash setting per organization per fiscal year

Revision ID: b0c1d2e3f4a5
Revises: a7c4e9f2b6d8
Create Date: 2026-09-03 00:00:00.000000
"""

from alembic import op


revision = "b0c1d2e3f4a5"
down_revision = "a7c4e9f2b6d8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("petty_cash_settings", schema=None) as batch_op:
        batch_op.drop_constraint("uq_petty_cash_settings_org_id", type_="unique")
        batch_op.create_unique_constraint(
            "uq_petty_cash_settings_org_fiscal_year",
            ["org_id", "fiscal_year"],
        )


def downgrade():
    with op.batch_alter_table("petty_cash_settings", schema=None) as batch_op:
        batch_op.drop_constraint("uq_petty_cash_settings_org_fiscal_year", type_="unique")
        batch_op.create_unique_constraint("uq_petty_cash_settings_org_id", ["org_id"])
