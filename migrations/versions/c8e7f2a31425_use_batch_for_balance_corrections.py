"""Use the upload batch as the latest balance correction source.

Revision ID: c8e7f2a31425
Revises: b7d6e1f20314
"""

from alembic import op
import sqlalchemy as sa


revision = "c8e7f2a31425"
down_revision = "b7d6e1f20314"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM cash_advance_balance_adjustments) THEN
            RAISE EXCEPTION 'Existing balance adjustment history must be reviewed before dropping its table';
          END IF;
        END $$
    """))
    op.drop_index("ix_cash_advance_balance_adjustments_ticket_id", table_name="cash_advance_balance_adjustments")
    op.drop_table("cash_advance_balance_adjustments")
    op.add_column("cash_advance_borrowing_tickets", sa.Column("balance_adjustment_batch_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_cash_advance_ticket_balance_adjustment_batch",
        "cash_advance_borrowing_tickets", "cash_advance_import_batches",
        ["balance_adjustment_batch_id"], ["id"],
    )


def downgrade():
    op.drop_constraint("fk_cash_advance_ticket_balance_adjustment_batch", "cash_advance_borrowing_tickets", type_="foreignkey")
    op.drop_column("cash_advance_borrowing_tickets", "balance_adjustment_batch_id")
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
