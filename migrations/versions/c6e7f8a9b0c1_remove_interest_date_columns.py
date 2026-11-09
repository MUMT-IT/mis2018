"""Remove separate interest receipt and withdrawal dates."""

from alembic import op
import sqlalchemy as sa


revision = "c6e7f8a9b0c1"
down_revision = "aa77cc88dd99"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("petty_cash_fund_requests", schema=None) as batch_op:
        batch_op.drop_column("receive_interest")
        batch_op.drop_column("withdraw_intrest")


def downgrade():
    with op.batch_alter_table("petty_cash_fund_requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("receive_interest", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("withdraw_intrest", sa.Date(), nullable=True))
