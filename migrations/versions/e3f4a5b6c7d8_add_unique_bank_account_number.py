"""make bank account numbers unique

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
"""

from alembic import op
import sqlalchemy as sa


revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            "UPDATE cash_mng_bank_account_infos "
            "SET account_number = regexp_replace(account_number, '[^0-9]', '', 'g')"
        )
    )
    op.create_unique_constraint(
        "uq_cash_mng_bank_account_infos_account_number",
        "cash_mng_bank_account_infos",
        ["account_number"],
    )


def downgrade():
    op.drop_constraint(
        "uq_cash_mng_bank_account_infos_account_number",
        "cash_mng_bank_account_infos",
        type_="unique",
    )
