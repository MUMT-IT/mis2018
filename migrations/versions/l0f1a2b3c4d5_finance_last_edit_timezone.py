"""Store finance edit timestamps with timezone information.

Revision ID: l0f1a2b3c4d5
Revises: k9e0f1a2b3c4
"""
from alembic import op
import sqlalchemy as sa


revision = "l0f1a2b3c4d5"
down_revision = "k9e0f1a2b3c4"
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
    # Existing values are intentionally left unchanged. Only the column type
    # changes so newly written values can retain their timezone information.
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                "last_edited_at",
                existing_type=sa.DateTime(),
                type_=sa.DateTime(timezone=True),
                existing_nullable=True,
            )


def downgrade():
    for table in reversed(TABLES):
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                "last_edited_at",
                existing_type=sa.DateTime(timezone=True),
                type_=sa.DateTime(),
                existing_nullable=True,
            )
