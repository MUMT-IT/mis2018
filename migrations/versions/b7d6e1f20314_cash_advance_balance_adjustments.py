"""Record finance corrections to existing cash advance receivable balances.

Revision ID: b7d6e1f20314
Revises: a9c4e7b2d105
"""

from alembic import op
import sqlalchemy as sa


revision = "b7d6e1f20314"
down_revision = "a9c4e7b2d105"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("cash_advance_borrowing_tickets", sa.Column("historical_repaid_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("cash_advance_borrowing_tickets", sa.Column("historical_pending_amount", sa.Numeric(12, 2), nullable=True))
    op.create_table(
        "cash_advance_balance_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("cash_advance_borrowing_tickets.id"), nullable=False),
        sa.Column("old_borrowed_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("old_repaid_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("old_pending_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("new_borrowed_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("new_repaid_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("new_pending_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.String(length=2000), nullable=False),
        sa.Column("source_file_path", sa.String(length=1024), nullable=False),
        sa.Column("source_report_date", sa.Date(), nullable=True),
        sa.Column("edited_by_id", sa.Integer(), sa.ForeignKey("staff_account.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cash_advance_balance_adjustments_ticket_id", "cash_advance_balance_adjustments", ["ticket_id"])


def downgrade():
    op.drop_index("ix_cash_advance_balance_adjustments_ticket_id", table_name="cash_advance_balance_adjustments")
    op.drop_table("cash_advance_balance_adjustments")
    op.drop_column("cash_advance_borrowing_tickets", "historical_pending_amount")
    op.drop_column("cash_advance_borrowing_tickets", "historical_repaid_amount")
