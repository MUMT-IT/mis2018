"""add creator id to petty cash fund requests

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
"""

from alembic import op
import sqlalchemy as sa


revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("petty_cash_fund_requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("creator_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_petty_cash_fund_requests_creator_id", ["creator_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_petty_cash_fund_requests_creator_id_staff_account",
            "staff_account",
            ["creator_id"],
            ["id"],
        )

    op.execute(
        sa.text(
            "UPDATE petty_cash_fund_requests "
            "SET creator_id = requester_id WHERE creator_id IS NULL"
        )
    )


def downgrade():
    with op.batch_alter_table("petty_cash_fund_requests", schema=None) as batch_op:
        batch_op.drop_constraint("fk_petty_cash_fund_requests_creator_id_staff_account", type_="foreignkey")
        batch_op.drop_index("ix_petty_cash_fund_requests_creator_id")
        batch_op.drop_column("creator_id")
