"""Store the date a petty-cash parcel return was transferred back."""

from alembic import op
import sqlalchemy as sa


revision = "s6f7a8b9c0d1"
down_revision = "t7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "cash_mng_parcel_return_details",
        sa.Column("transferred_at", sa.Date(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE cash_mng_parcel_return_details "
            "SET status = 'โอนเงินสดย่อยสำเร็จ' "
            "WHERE status = 'โอนคืนเงินสดย่อย'"
        )
    )


def downgrade():
    op.drop_column("cash_mng_parcel_return_details", "transferred_at")
