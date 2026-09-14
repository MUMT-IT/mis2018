"""Store the latest finance edit on advance payment business records.

Revision ID: f1a24b5c7d93
Revises: e0f13a4b6c82
"""
from alembic import op
import sqlalchemy as sa

revision = "f1a24b5c7d93"
down_revision = "e0f13a4b6c82"
branch_labels = None
depends_on = None

TABLES = (
    "cash_advance_borrowing_tickets",
    "cash_mng_documents",
    "cash_advance_return_details",
    "cash_advance_return_receipt_items",
    "cash_advance_return_proof_files",
    "cash_mng_parcel_return_details",
    "cash_mng_closing_documents",
    "cash_mng_closing_document_links",
    "petty_cash_settings",
    "cash_mng_bank_account_infos",
    "petty_cash_fund_requests",
    "petty_cash_fund_request_items",
    "petty_cash_claim_details",
    "petty_cash_claim_items",
    "petty_cash_claim_proof_files",
)


def upgrade():
    # Existing records remain NULL: their actual editor/time is unknown.
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("last_edited_at", sa.DateTime(), nullable=True))
            batch.add_column(sa.Column("last_edited_by_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_" + table + "_last_editor", "staff_account",
                ["last_edited_by_id"], ["id"],
            )


def downgrade():
    for table in reversed(TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint("fk_" + table + "_last_editor", type_="foreignkey")
            batch.drop_column("last_edited_by_id")
            batch.drop_column("last_edited_at")
