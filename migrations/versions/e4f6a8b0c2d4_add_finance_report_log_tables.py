"""Replace test reminder logs with finance report exports and their tickets."""

from alembic import op
import sqlalchemy as sa


revision = "e4f6a8b0c2d4"
down_revision = "81064cedf061"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cash_advance_finance_report_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_type", sa.String(length=40), nullable=False),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("staff_account.id"), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_cash_advance_finance_report_logs_creator_id",
        "cash_advance_finance_report_logs", ["creator_id"],
    )
    op.create_index(
        "ix_cash_advance_finance_report_logs_created_at",
        "cash_advance_finance_report_logs", ["created_at"],
    )
    op.create_table(
        "cash_advance_finance_report_log_items",
        sa.Column(
            "export_id", sa.Integer(),
            sa.ForeignKey("cash_advance_finance_report_logs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "ticket_id", sa.Integer(),
            sa.ForeignKey("cash_advance_borrowing_tickets.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index(
        "ix_cash_advance_finance_report_log_items_ticket_id",
        "cash_advance_finance_report_log_items", ["ticket_id"],
    )
    op.drop_index("ix_cash_advance_overdue_reminder_logs_creator_id", table_name="cash_advance_overdue_reminder_logs")
    op.drop_index("ix_cash_advance_overdue_reminder_logs_ticket_id", table_name="cash_advance_overdue_reminder_logs")
    op.drop_table("cash_advance_overdue_reminder_logs")


def downgrade():
    op.create_table(
        "cash_advance_overdue_reminder_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("borrowing_ticket_id", sa.Integer(), sa.ForeignKey("cash_advance_borrowing_tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("staff_account.id"), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cash_advance_overdue_reminder_logs_ticket_id", "cash_advance_overdue_reminder_logs", ["borrowing_ticket_id"])
    op.create_index("ix_cash_advance_overdue_reminder_logs_creator_id", "cash_advance_overdue_reminder_logs", ["creator_id"])
    op.drop_index(
        "ix_cash_advance_finance_report_log_items_ticket_id",
        table_name="cash_advance_finance_report_log_items",
    )
    op.drop_table("cash_advance_finance_report_log_items")
    op.drop_index(
        "ix_cash_advance_finance_report_logs_created_at",
        table_name="cash_advance_finance_report_logs",
    )
    op.drop_index(
        "ix_cash_advance_finance_report_logs_creator_id",
        table_name="cash_advance_finance_report_logs",
    )
    op.drop_table("cash_advance_finance_report_logs")
