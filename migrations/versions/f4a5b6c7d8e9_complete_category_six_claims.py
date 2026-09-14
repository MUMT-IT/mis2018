"""complete petty cash claims that only transfer money back

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
"""

from alembic import op
import sqlalchemy as sa


revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            "UPDATE petty_cash_claim_details AS claim "
            "SET status = 'เสร็จสิ้นกระบวนการ' "
            "WHERE EXISTS ("
            "  SELECT 1 FROM petty_cash_claim_items AS item "
            "  WHERE item.claim_id = claim.id"
            ") AND NOT EXISTS ("
            "  SELECT 1 FROM petty_cash_claim_items AS item "
            "  WHERE item.claim_id = claim.id AND item.category_type <> 6"
            ")"
        )
    )


def downgrade():
    pass
