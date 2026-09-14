"""Remove created_at from cash_mng_bank_account_infos

Revision ID: bb22cc33dd44
Revises: aa11bb22cc33
"""

from alembic import op
import sqlalchemy as sa


revision = "bb22cc33dd44"
down_revision = "aa11bb22cc33"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("cash_mng_bank_account_infos", schema=None) as batch_op:
        batch_op.drop_column("created_at")


def downgrade():
    with op.batch_alter_table("cash_mng_bank_account_infos", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
