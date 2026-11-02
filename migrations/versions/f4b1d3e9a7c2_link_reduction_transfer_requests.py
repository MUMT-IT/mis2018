"""Link reduction transfers to their fund requests.

Revision ID: f4b1d3e9a7c2
Revises: f4a0c2d8e6b1
Create Date: 2026-10-30
"""

from alembic import op
import sqlalchemy as sa


revision = "f4b1d3e9a7c2"
down_revision = "f4a0c2d8e6b1"
branch_labels = None
depends_on = None


TABLE = "petty_cash_fiscal_year_top_up_transfers"


def upgrade():
    op.add_column(TABLE, sa.Column("fund_request_id", sa.Integer(), nullable=True))
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.create_foreign_key(
            "fk_petty_cash_transfer_fund_request",
            "petty_cash_fund_requests",
            ["fund_request_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_petty_cash_fiscal_year_top_up_transfers_fund_request_id", ["fund_request_id"])

    # Backfill only unambiguous settings; never guess among multiple requests.
    op.execute(sa.text(
        "UPDATE petty_cash_fiscal_year_top_up_transfers "
        "SET fund_request_id = ("
        "SELECT MIN(fr.id) FROM petty_cash_fund_requests AS fr "
        "WHERE fr.petty_cash_setting_id = petty_cash_fiscal_year_top_up_transfers.petty_cash_setting_id "
        "AND fr.form_type = 'reduction' AND fr.is_legacy_import = false "
        "HAVING COUNT(*) = 1"
        ") WHERE transfer_type = 2"
    ))
    op.execute(sa.text(
        "UPDATE petty_cash_fiscal_year_top_up_transfers "
        "SET transferred_at = ("
        "SELECT fr.request_date FROM petty_cash_fund_requests AS fr "
        "WHERE fr.id = petty_cash_fiscal_year_top_up_transfers.fund_request_id"
        ") WHERE transfer_type = 2 AND fund_request_id IS NOT NULL"
    ))


def downgrade():
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_index("ix_petty_cash_fiscal_year_top_up_transfers_fund_request_id")
        batch_op.drop_constraint("fk_petty_cash_transfer_fund_request", type_="foreignkey")
        batch_op.drop_column("fund_request_id")
