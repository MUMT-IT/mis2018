"""Normalize typed parcel-return statuses and enforce one direct parent.

Revision ID: d4a5b6c7e8f9
Revises: c2f45ae11edb
Create Date: 2026-10-02

This migration is intentionally guarded. It must be reviewed before it is run:
ambiguous parent links, borrowing-passthrough children, and approved workflow
statuses without approved_at stop the migration instead of being guessed.
"""

from alembic import op
import sqlalchemy as sa


revision = "d4a5b6c7e8f9"
down_revision = "c2f45ae11edb"
branch_labels = None
depends_on = None


PARCEL_TABLE = "cash_mng_parcel_return_details"
PARENT_CONSTRAINT = "ck_cash_mng_parcel_return_details_exactly_one_parent"


def _row_ids(bind, statement):
    return [row[0] for row in bind.execute(sa.text(statement)).fetchall()]


def _require_manual_review(label, row_ids):
    if not row_ids:
        return
    preview = ", ".join(str(row_id) for row_id in row_ids[:20])
    remainder = len(row_ids) - 20
    if remainder > 0:
        preview = f"{preview}, ... (+{remainder} more)"
    raise RuntimeError(f"{label}; affected IDs: {preview}")


def upgrade():
    bind = op.get_bind()

    _require_manual_review(
        "Parcel returns must have exactly one of ticket_id or fund_request_id",
        _row_ids(
            bind,
            f"""
            SELECT id
            FROM {PARCEL_TABLE}
            WHERE (ticket_id IS NULL AND fund_request_id IS NULL)
               OR (ticket_id IS NOT NULL AND fund_request_id IS NOT NULL)
            ORDER BY id
            """,
        ),
    )

    _require_manual_review(
        "Typed parcel returns in the compatibility status require an explicit mapping",
        _row_ids(
            bind,
            f"""
            SELECT id
            FROM {PARCEL_TABLE}
            WHERE type IN (1, 5)
              AND status = 'กำลังตรวจสอบ'
            ORDER BY id
            """,
        ),
    )

    _require_manual_review(
        "Typed parcel returns in an approved workflow status require approved_at",
        _row_ids(
            bind,
            f"""
            SELECT id
            FROM {PARCEL_TABLE}
            WHERE type IN (1, 5)
              AND approved_at IS NULL
              AND status IN (
                  'พัสดุกำลังดำเนินการ',
                  'ได้รับเอกสารแล้ว',
                  'ยืนยันการตรวจสอบ',
                  'โอนเงินสดย่อยสำเร็จ',
                  'เอกสารตั้งฎีกา',
                  'ล้างลูกหนี้เงินยืม'
              )
            ORDER BY id
            """,
        ),
    )

    _require_manual_review(
        "Borrowing-passthrough fund requests must not own parcel returns",
        _row_ids(
            bind,
            f"""
            SELECT parcel.id
            FROM {PARCEL_TABLE} AS parcel
            JOIN petty_cash_fund_requests AS fund_request
              ON fund_request.id = parcel.fund_request_id
            WHERE fund_request.form_type = 'borrowing'
            ORDER BY parcel.id
            """,
        ),
    )

    _require_manual_review(
        "Borrowing-passthrough fund requests must not own petty-cash claims",
        _row_ids(
            bind,
            """
            SELECT claim.id
            FROM petty_cash_claim_details AS claim
            JOIN petty_cash_fund_requests AS fund_request
              ON fund_request.id = claim.fund_request_id
            WHERE fund_request.form_type = 'borrowing'
            ORDER BY claim.id
            """,
        ),
    )

    # Direct SQL changes data only; it does not invoke application email hooks.
    # approved_at is deliberately preserved exactly as stored.
    op.execute(
        sa.text(
            f"""
            UPDATE {PARCEL_TABLE}
            SET status = 'ยืนยันการตรวจสอบ'
            WHERE type IN (1, 5)
              AND status IN ('พัสดุกำลังดำเนินการ', 'ได้รับเอกสารแล้ว')
              AND approved_at IS NOT NULL
            """
        )
    )

    with op.batch_alter_table(PARCEL_TABLE, schema=None) as batch_op:
        batch_op.create_check_constraint(
            PARENT_CONSTRAINT,
            "(ticket_id IS NOT NULL AND fund_request_id IS NULL) OR "
            "(ticket_id IS NULL AND fund_request_id IS NOT NULL)",
        )


def downgrade():
    with op.batch_alter_table(PARCEL_TABLE, schema=None) as batch_op:
        batch_op.drop_constraint(PARENT_CONSTRAINT, type_="check")

    # Do not guess whether a normalized row previously used
    # พัสดุกำลังดำเนินการ or ได้รับเอกสารแล้ว. The status data remains valid.
