"""Add overdue reminder generation logs."""

from alembic import op
import sqlalchemy as sa


revision = "b7e1c9d4f2a6"
down_revision = "z3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cash_advance_overdue_reminder_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("borrowing_ticket_id", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["borrowing_ticket_id"], ["cash_advance_borrowing_tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["creator_id"], ["staff_account.id"]),
    )
    op.create_index("ix_cash_advance_overdue_reminder_logs_ticket_id", "cash_advance_overdue_reminder_logs", ["borrowing_ticket_id"])
    op.create_index("ix_cash_advance_overdue_reminder_logs_creator_id", "cash_advance_overdue_reminder_logs", ["creator_id"])


def downgrade():
    op.drop_index("ix_cash_advance_overdue_reminder_logs_creator_id", table_name="cash_advance_overdue_reminder_logs")
    op.drop_index("ix_cash_advance_overdue_reminder_logs_ticket_id", table_name="cash_advance_overdue_reminder_logs")
    op.drop_table("cash_advance_overdue_reminder_logs")
