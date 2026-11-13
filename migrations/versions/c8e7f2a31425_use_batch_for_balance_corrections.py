"""Store corrected historical balances and their source upload batch.

Revision ID: c8e7f2a31425
Revises: a9c4e7b2d105
"""

from alembic import op
import sqlalchemy as sa


revision = "c8e7f2a31425"
down_revision = "a9c4e7b2d105"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("cash_advance_borrowing_tickets", sa.Column("historical_repaid_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("cash_advance_borrowing_tickets", sa.Column("historical_pending_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("cash_advance_borrowing_tickets", sa.Column("balance_adjustment_batch_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_cash_advance_ticket_balance_adjustment_batch",
        "cash_advance_borrowing_tickets", "cash_advance_import_batches",
        ["balance_adjustment_batch_id"], ["id"],
    )


def downgrade():
    op.drop_constraint("fk_cash_advance_ticket_balance_adjustment_batch", "cash_advance_borrowing_tickets", type_="foreignkey")
    op.drop_column("cash_advance_borrowing_tickets", "balance_adjustment_batch_id")
    op.drop_column("cash_advance_borrowing_tickets", "historical_pending_amount")
    op.drop_column("cash_advance_borrowing_tickets", "historical_repaid_amount")
