"""Add closed_at to cash_mng_bank_account_infos

Revision ID: aa11bb22cc33
Revises: e3f4a5b6c7d8
"""

from alembic import op
import sqlalchemy as sa


revision = "aa11bb22cc33"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("cash_mng_bank_account_infos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("closed_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("cash_mng_bank_account_infos", schema=None) as batch_op:
        batch_op.drop_column("closed_at")
