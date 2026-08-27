"""Add AdvancePayment tables.

Revision ID: 5f8a9c1d2e3b
Revises: 4b5c6d7e8f90
"""

from alembic import op
import sqlalchemy as sa


revision = "5f8a9c1d2e3b"
down_revision = "4b5c6d7e8f90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cash_mng_bank_account_infos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("thai_name", sa.String(length=255), nullable=False),
        sa.Column("english_name", sa.String(length=255), nullable=False),
        sa.Column("account_number", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "record_type",
            "thai_name",
            name="uq_cash_mng_bank_account_infos_record_type_thai_name",
        ),
    )

    op.create_table(
        "cash_advance_borrowing_tickets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("borrower_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("borrowing_ticket_purpose", sa.String(length=255), nullable=False),
        sa.Column("required_budget", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("account_number", sa.String(length=100), nullable=False),
        sa.Column("bank_account_info_id", sa.Integer(), nullable=True),
        sa.Column("borrowing_ticket_start_date", sa.Date(), nullable=False),
        sa.Column("borrowing_ticket_end_date", sa.Date(), nullable=False),
        sa.Column("finance_verified", sa.Boolean(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("closed_date", sa.DateTime(), nullable=True),
        sa.Column("rejection_comment", sa.String(length=1000), nullable=True),
        sa.Column("finance_note", sa.String(length=2000), nullable=True),
        sa.Column("aip_ref_no", sa.String(length=255), nullable=False),
        sa.Column("aip_ref_date", sa.Date(), nullable=False),
        sa.Column("last_notified_type", sa.String(length=50), nullable=True),
        sa.Column("last_notified_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["bank_account_info_id"], ["cash_mng_bank_account_infos.id"]),
        sa.ForeignKeyConstraint(["borrower_id"], ["staff_account.id"]),
        sa.ForeignKeyConstraint(["creator_id"], ["staff_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "cash_mng_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("borrower_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["borrower_id"], ["staff_account.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["cash_advance_borrowing_tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id"),
    )

    op.create_table(
        "cash_mng_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "cash_mng_closing_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_number", sa.String(length=255), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_number"),
    )

    op.create_table(
        "cash_advance_return_details",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("amount_spent", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("proof_reference", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("old_closing_document_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("rejection_comment", sa.String(length=4000), nullable=True),
        sa.Column("closing_document_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["closing_document_id"], ["cash_mng_closing_documents.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["cash_advance_borrowing_tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "cash_advance_return_receipt_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("return_detail_id", sa.Integer(), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("store_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["return_detail_id"], ["cash_advance_return_details.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "cash_advance_return_proof_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("return_detail_id", sa.Integer(), nullable=False),
        sa.Column("return_receipt_item_id", sa.Integer(), nullable=True),
        sa.Column("proof_reference", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["return_detail_id"], ["cash_advance_return_details.id"]),
        sa.ForeignKeyConstraint(["return_receipt_item_id"], ["cash_advance_return_receipt_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "petty_cash_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("department_name", sa.String(length=255), nullable=False),
        sa.Column("custodian_name", sa.String(length=255), nullable=True),
        sa.Column("budget", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("account_number", sa.String(length=100), nullable=False),
        sa.Column("bank_account_info_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("custodian_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["bank_account_info_id"], ["cash_mng_bank_account_infos.id"]),
        sa.ForeignKeyConstraint(["custodian_id"], ["staff_account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("department_name"),
        sa.UniqueConstraint("custodian_id"),
    )

    op.create_table(
        "petty_cash_fund_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("borrowing_ticket_id", sa.Integer(), nullable=True),
        sa.Column("form_type", sa.String(length=10), nullable=False),
        sa.Column("requester_name", sa.String(length=255), nullable=False),
        sa.Column("requester_position", sa.String(length=255), nullable=False),
        sa.Column("department_name", sa.String(length=255), nullable=False),
        sa.Column("account_number", sa.String(length=100), nullable=False),
        sa.Column("ticket_number", sa.String(length=64), nullable=True),
        sa.Column("request_date", sa.Date(), nullable=False),
        sa.Column("fund_in_date", sa.Date(), nullable=True),
        sa.Column("withdrawal_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("purpose", sa.String(length=1000), nullable=True),
        sa.Column("period_year", sa.String(length=10), nullable=True),
        sa.Column("withdrawal_proof_reference", sa.String(length=500), nullable=True),
        sa.Column("withdrawal_proof_filename", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["borrowing_ticket_id"], ["cash_advance_borrowing_tickets.id"]),
        sa.ForeignKeyConstraint(["requester_id"], ["staff_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "petty_cash_fund_request_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fund_request_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("category_type", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["fund_request_id"], ["petty_cash_fund_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "cash_mng_parcel_return_details",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=True),
        sa.Column("fund_request_id", sa.Integer(), nullable=True),
        sa.Column("amount_spent", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("items_description", sa.String(length=1000), nullable=False),
        sa.Column("sent_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closing_document_id", sa.Integer(), nullable=True),
        sa.Column("old_closing_document_name", sa.String(length=255), nullable=True),
        sa.Column("rejection_comment", sa.String(length=4000), nullable=True),
        sa.ForeignKeyConstraint(["closing_document_id"], ["cash_mng_closing_documents.id"]),
        sa.ForeignKeyConstraint(["fund_request_id"], ["petty_cash_fund_requests.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["cash_advance_borrowing_tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "petty_cash_claim_details",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("Claim_number", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("petty_cash_setting_id", sa.Integer(), nullable=False),
        sa.Column("fund_request_id", sa.Integer(), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("rejection_comment", sa.String(length=4000), nullable=True),
        sa.Column("transferred_at", sa.Date(), nullable=True),
        sa.Column("closing_document_id", sa.Integer(), nullable=True),
        sa.Column("old_closing_document_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["closing_document_id"], ["cash_mng_closing_documents.id"]),
        sa.ForeignKeyConstraint(["fund_request_id"], ["petty_cash_fund_requests.id"]),
        sa.ForeignKeyConstraint(["petty_cash_setting_id"], ["petty_cash_settings.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["staff_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "petty_cash_claim_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("category_type", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["petty_cash_claim_details.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "petty_cash_claim_proof_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("claim_item_id", sa.Integer(), nullable=True),
        sa.Column("proof_reference", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["petty_cash_claim_details.id"]),
        sa.ForeignKeyConstraint(["claim_item_id"], ["petty_cash_claim_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "cash_mng_document_return_association",
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("return_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["cash_mng_documents.id"]),
        sa.ForeignKeyConstraint(["return_id"], ["cash_advance_return_details.id"]),
        sa.PrimaryKeyConstraint("document_id", "return_id"),
    )

    op.create_table(
        "cash_mng_document_petty_claim_association",
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["petty_cash_claim_details.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["cash_mng_documents.id"]),
        sa.PrimaryKeyConstraint("document_id", "claim_id"),
    )


def downgrade():
    op.drop_table("cash_mng_document_petty_claim_association")
    op.drop_table("cash_mng_document_return_association")
    op.drop_table("petty_cash_claim_proof_files")
    op.drop_table("petty_cash_claim_items")
    op.drop_table("petty_cash_claim_details")
    op.drop_table("cash_mng_parcel_return_details")
    op.drop_table("petty_cash_fund_request_items")
    op.drop_table("petty_cash_fund_requests")
    op.drop_table("petty_cash_settings")
    op.drop_table("cash_advance_return_proof_files")
    op.drop_table("cash_advance_return_receipt_items")
    op.drop_table("cash_advance_return_details")
    op.drop_table("cash_mng_closing_documents")
    op.drop_table("cash_mng_documents")
    op.drop_table("cash_mng_notifications")
    op.drop_table("cash_advance_borrowing_tickets")
    op.drop_table("cash_mng_bank_account_infos")
