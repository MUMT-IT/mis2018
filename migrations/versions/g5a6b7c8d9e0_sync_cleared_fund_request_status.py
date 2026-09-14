"""mark fully settled fund requests as cleared

Revision ID: g5a6b7c8d9e0
Revises: f4a5b6c7d8e9
"""

from alembic import op
import sqlalchemy as sa


revision = "g5a6b7c8d9e0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            "UPDATE petty_cash_fund_requests AS fund "
            "SET status = CASE WHEN EXISTS ("
            "  SELECT 1 FROM petty_cash_claim_details AS pending_claim "
            "  JOIN petty_cash_claim_items AS pending_item "
            "    ON pending_item.claim_id = pending_claim.id "
            "  WHERE pending_claim.fund_request_id = fund.id "
            "    AND pending_claim.status <> 'ฉบับร่าง' "
            "    AND pending_item.category_type <> 6 "
            "    AND pending_item.amount > 0 "
            "    AND pending_claim.status NOT IN ('โอนเงินสดย่อยสำเร็จ', 'เสร็จสิ้นกระบวนการ')"
            ") THEN 'ส่งเบิกครบแล้ว' ELSE 'เคลียร์ยอดสำเร็จ' END "
            "WHERE fund.amount > 0 "
            "AND fund.status IN ('อนุมัติแล้ว', 'ส่งเบิกแล้ว', 'ส่งเบิกครบแล้ว', 'เบิกเงินสำเร็จ') "
            "AND round(fund.amount, 2) = round(" 
            "  COALESCE((SELECT SUM(claim.total_amount) "
            "    FROM petty_cash_claim_details AS claim "
            "    WHERE claim.fund_request_id = fund.id "
            "      AND claim.status <> 'ฉบับร่าง'), 0) "
            "  + COALESCE((SELECT SUM(item.amount) "
            "    FROM petty_cash_claim_items AS item "
            "    JOIN petty_cash_claim_details AS claim ON claim.id = item.claim_id "
            "    WHERE claim.fund_request_id = fund.id "
            "      AND claim.status <> 'ฉบับร่าง' "
            "      AND item.category_type = 6), 0) "
            "  + COALESCE((SELECT SUM(parcel.amount_spent) "
            "    FROM cash_mng_parcel_return_details AS parcel "
            "    WHERE parcel.fund_request_id = fund.id "
            "      AND parcel.status <> 'ปฏิเสธ'), 0), 2)"
        )
    )


def downgrade():
    pass
