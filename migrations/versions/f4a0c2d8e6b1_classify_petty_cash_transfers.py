"""Classify annual petty-cash transfers and store unsigned amounts.

Revision ID: f4a0c2d8e6b1
Revises: e83f9a1b2c4d
Create Date: 2026-10-30
"""

from alembic import op
import sqlalchemy as sa


revision = "f4a0c2d8e6b1"
down_revision = "e83f9a1b2c4d"
branch_labels = None
depends_on = None


TABLE = "petty_cash_fiscal_year_top_up_transfers"


def upgrade():
    op.add_column(TABLE, sa.Column("transfer_type", sa.Integer(), nullable=True))
    op.execute(sa.text(
        "UPDATE petty_cash_fiscal_year_top_up_transfers "
        "SET transfer_type = CASE WHEN transfer_amount > 0 THEN 1 "
        "WHEN transfer_amount < 0 THEN 2 ELSE 0 END, "
        "transfer_amount = ABS(transfer_amount)"
    ))
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.alter_column("transfer_type", nullable=False)
        batch_op.create_check_constraint(
            "ck_petty_cash_transfer_type_amount",
            "(transfer_type = 0 AND transfer_amount = 0) OR "
            "(transfer_type IN (1, 2) AND transfer_amount > 0)",
        )


def downgrade():
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_constraint("ck_petty_cash_transfer_type_amount", type_="check")
    op.execute(sa.text(
        "UPDATE petty_cash_fiscal_year_top_up_transfers "
        "SET transfer_amount = CASE WHEN transfer_type = 2 "
        "THEN -transfer_amount ELSE transfer_amount END"
    ))
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_column("transfer_type")
