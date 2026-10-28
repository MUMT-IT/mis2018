"""Cascade deletion for advance-payment aggregate children.

Revision ID: q0d1e2f3a4b5
Revises: p9c8t7u6v5w4
Create Date: 2026-10-27
"""

from alembic import op


revision = "q0d1e2f3a4b5"
down_revision = "p9c8t7u6v5w4"
branch_labels = None
depends_on = None


# Borrowing-ticket foreign keys are intentionally absent. A borrowing ticket
# remains protected by NO ACTION once a return, parcel return, fund request, or
# ticket association refers to it.
_FOREIGN_KEYS = (
    (
        "cash_mng_notifications_ticket_id_fkey",
        "cash_mng_notifications",
        "cash_advance_borrowing_tickets",
        ["ticket_id"],
        ["id"],
    ),
    (
        "cash_mng_document_return_association_document_id_fkey",
        "cash_mng_document_return_association",
        "cash_mng_documents",
        ["document_id"],
        ["id"],
    ),
    (
        "cash_mng_document_return_association_return_id_fkey",
        "cash_mng_document_return_association",
        "cash_advance_return_details",
        ["return_id"],
        ["id"],
    ),
    (
        "cash_advance_return_borrowing_ticket_association_return_id_fkey",
        "cash_advance_return_borrowing_ticket_association",
        "cash_advance_return_details",
        ["return_id"],
        ["id"],
    ),
    (
        "cash_advance_parcel_borrowing_ticket_asso_parcel_return_id_fkey",
        "cash_advance_parcel_borrowing_ticket_association",
        "cash_mng_parcel_return_details",
        ["parcel_return_id"],
        ["id"],
    ),
    (
        "cash_advance_return_receipt_items_return_detail_id_fkey",
        "cash_advance_return_receipt_items",
        "cash_advance_return_details",
        ["return_detail_id"],
        ["id"],
    ),
    (
        "cash_advance_return_proof_files_return_detail_id_fkey",
        "cash_advance_return_proof_files",
        "cash_advance_return_details",
        ["return_detail_id"],
        ["id"],
    ),
    (
        "cash_advance_return_proof_files_return_receipt_item_id_fkey",
        "cash_advance_return_proof_files",
        "cash_advance_return_receipt_items",
        ["return_receipt_item_id"],
        ["id"],
    ),
    (
        "cash_mng_parcel_return_details_fund_request_id_fkey",
        "cash_mng_parcel_return_details",
        "petty_cash_fund_requests",
        ["fund_request_id"],
        ["id"],
    ),
    (
        "cash_mng_closing_document_links_document_id_fkey",
        "cash_mng_closing_document_links",
        "cash_mng_closing_documents",
        ["document_id"],
        ["id"],
    ),
    (
        "cash_mng_closing_document_links_ticket_return_id_fkey",
        "cash_mng_closing_document_links",
        "cash_advance_return_details",
        ["ticket_return_id"],
        ["id"],
    ),
    (
        "cash_mng_closing_document_links_parcel_return_id_fkey",
        "cash_mng_closing_document_links",
        "cash_mng_parcel_return_details",
        ["parcel_return_id"],
        ["id"],
    ),
    (
        "cash_mng_closing_document_links_claim_id_fkey",
        "cash_mng_closing_document_links",
        "petty_cash_claim_details",
        ["claim_id"],
        ["id"],
    ),
    (
        "petty_cash_fund_request_items_fund_request_id_fkey",
        "petty_cash_fund_request_items",
        "petty_cash_fund_requests",
        ["fund_request_id"],
        ["id"],
    ),
    (
        "cash_mng_document_petty_claim_association_document_id_fkey",
        "cash_mng_document_petty_claim_association",
        "cash_mng_documents",
        ["document_id"],
        ["id"],
    ),
    (
        "cash_mng_document_petty_claim_association_claim_id_fkey",
        "cash_mng_document_petty_claim_association",
        "petty_cash_claim_details",
        ["claim_id"],
        ["id"],
    ),
    (
        "petty_cash_claim_details_fund_request_id_fkey",
        "petty_cash_claim_details",
        "petty_cash_fund_requests",
        ["fund_request_id"],
        ["id"],
    ),
    (
        "petty_cash_claim_items_claim_id_fkey",
        "petty_cash_claim_items",
        "petty_cash_claim_details",
        ["claim_id"],
        ["id"],
    ),
    (
        "petty_cash_claim_proof_files_claim_id_fkey",
        "petty_cash_claim_proof_files",
        "petty_cash_claim_details",
        ["claim_id"],
        ["id"],
    ),
    (
        "petty_cash_claim_proof_files_claim_item_id_fkey",
        "petty_cash_claim_proof_files",
        "petty_cash_claim_items",
        ["claim_item_id"],
        ["id"],
    ),
)


def _replace_foreign_keys(*, ondelete=None):
    for name, source, referent, local_columns, remote_columns in _FOREIGN_KEYS:
        op.drop_constraint(name, source, type_="foreignkey")
        op.create_foreign_key(
            name,
            source,
            referent,
            local_columns,
            remote_columns,
            ondelete=ondelete,
        )


def upgrade():
    _replace_foreign_keys(ondelete="CASCADE")


def downgrade():
    _replace_foreign_keys()
