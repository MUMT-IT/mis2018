"""Add legacy cash advance opening balances and source batches.

Revision ID: a9c4e7b2d105
Revises: 1b5f6c7d8e9a
"""

from alembic import op
import sqlalchemy as sa


revision = "a9c4e7b2d105"
down_revision = "1b5f6c7d8e9a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cash_advance_import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_file_path", sa.String(length=1024), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("staff_account.id"), nullable=False),
        sa.Column("uploaded_on", sa.Date(), nullable=False),
    )
    op.add_column("cash_advance_borrowing_tickets", sa.Column("opening_balance_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("cash_advance_borrowing_tickets", sa.Column("import_batch_id", sa.Integer(), nullable=True))
    op.add_column("cash_advance_borrowing_tickets", sa.Column("import_source_row", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_cash_advance_ticket_import_batch",
        "cash_advance_borrowing_tickets", "cash_advance_import_batches",
        ["import_batch_id"], ["id"],
    )
    for column in ("aip_ref_date", "borrowing_ticket_start_date", "borrowing_ticket_end_date"):
        op.alter_column("cash_advance_borrowing_tickets", column, existing_type=sa.Date(), nullable=True)
    op.execute(sa.text("""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM cash_advance_borrowing_tickets
            WHERE number IS NOT NULL AND btrim(number) <> ''
            GROUP BY btrim(number) HAVING count(*) > 1
          ) THEN
            RAISE EXCEPTION 'Duplicate borrowing ticket numbers exist; resolve them before this migration';
          END IF;
        END $$
    """))
    op.execute(sa.text("""
        CREATE UNIQUE INDEX uq_cash_advance_ticket_trimmed_number
        ON cash_advance_borrowing_tickets (btrim(number))
        WHERE number IS NOT NULL AND btrim(number) <> ''
    """))


def downgrade():
    op.execute(sa.text("DROP INDEX uq_cash_advance_ticket_trimmed_number"))
    for column in ("aip_ref_date", "borrowing_ticket_start_date", "borrowing_ticket_end_date"):
        op.alter_column("cash_advance_borrowing_tickets", column, existing_type=sa.Date(), nullable=False)
    op.drop_constraint("fk_cash_advance_ticket_import_batch", "cash_advance_borrowing_tickets", type_="foreignkey")
    op.drop_column("cash_advance_borrowing_tickets", "import_source_row")
    op.drop_column("cash_advance_borrowing_tickets", "import_batch_id")
    op.drop_column("cash_advance_borrowing_tickets", "opening_balance_amount")
    op.drop_table("cash_advance_import_batches")
