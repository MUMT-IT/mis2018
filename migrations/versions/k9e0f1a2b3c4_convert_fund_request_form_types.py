"""replace numeric FundRequest form types with meaningful values

Revision ID: k9e0f1a2b3c4
Revises: c9920d07b912
"""

from alembic import op
import sqlalchemy as sa


revision = "k9e0f1a2b3c4"
down_revision = "c9920d07b912"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            "UPDATE petty_cash_fund_requests "
            "SET form_type = CASE form_type "
            "WHEN '30' THEN 'petty_cash' "
            "WHEN '31' THEN 'interest' "
            "WHEN '32' THEN 'borrowing' "
            "END "
            "WHERE form_type IN ('30', '31', '32')"
        )
    )


def downgrade():
    op.execute(
        sa.text(
            "UPDATE petty_cash_fund_requests "
            "SET form_type = CASE form_type "
            "WHEN 'petty_cash' THEN '30' "
            "WHEN 'interest' THEN '31' "
            "WHEN 'borrowing' THEN '32' "
            "END "
            "WHERE form_type IN ('petty_cash', 'interest', 'borrowing')"
        )
    )
