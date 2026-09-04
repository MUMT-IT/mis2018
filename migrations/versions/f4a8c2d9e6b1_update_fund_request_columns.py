"""remove denormalized fund request fields and rename interest dates

Revision ID: f4a8c2d9e6b1
Revises: e3a7f1b2c4d5
"""
from alembic import op
import sqlalchemy as sa


revision = "f4a8c2d9e6b1"
down_revision = "e3a7f1b2c4d5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("petty_cash_fund_requests", schema=None) as batch_op:
        batch_op.drop_column("requester_name")
        batch_op.drop_column("requester_position")
        batch_op.drop_column("department_name")
        batch_op.drop_column("account_number")
        batch_op.alter_column("fund_in_date", new_column_name="receive_interest")
        batch_op.alter_column("withdrawal_date", new_column_name="withdraw_intrest")


def downgrade():
    with op.batch_alter_table("petty_cash_fund_requests", schema=None) as batch_op:
        batch_op.alter_column("receive_interest", new_column_name="fund_in_date")
        batch_op.alter_column("withdraw_intrest", new_column_name="withdrawal_date")
        batch_op.add_column(sa.Column("requester_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("requester_position", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("department_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("account_number", sa.String(length=100), nullable=True))
