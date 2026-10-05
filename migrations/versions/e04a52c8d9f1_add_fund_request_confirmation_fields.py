"""Add fund-request confirmation actors and defer the withdrawal date.

Revision ID: e04a52c8d9f1
Revises: d93f41a6b7c8
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa


revision = "e04a52c8d9f1"
down_revision = "d93f41a6b7c8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "petty_cash_fund_requests",
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "petty_cash_fund_requests",
        sa.Column("confirmed_by_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "petty_cash_fund_requests",
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_fund_request_confirmed_by",
        "petty_cash_fund_requests",
        "staff_account",
        ["confirmed_by_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_fund_request_approved_by",
        "petty_cash_fund_requests",
        "staff_account",
        ["approved_by_id"],
        ["id"],
    )
    op.create_index(
        "ix_petty_cash_fund_requests_confirmed_by_id",
        "petty_cash_fund_requests",
        ["confirmed_by_id"],
    )
    op.create_index(
        "ix_petty_cash_fund_requests_approved_by_id",
        "petty_cash_fund_requests",
        ["approved_by_id"],
    )
    op.alter_column(
        "petty_cash_fund_requests",
        "request_date",
        existing_type=sa.Date(),
        nullable=True,
    )
    # Before this revision request_date was mandatory and "อนุมัติแล้ว"
    # already meant the request had entered the original post-withdrawal
    # workflow. Preserve that meaning under the new explicit withdrawal step.
    op.execute(
        sa.text(
            """
            UPDATE petty_cash_fund_requests
            SET status = 'เบิกเงินแล้ว'
            WHERE status = 'อนุมัติแล้ว'
              AND request_date IS NOT NULL
            """
        )
    )


def downgrade():
    op.execute(
        sa.text(
            """
            UPDATE petty_cash_fund_requests
            SET status = 'อนุมัติแล้ว'
            WHERE status = 'เบิกเงินแล้ว'
              AND request_date IS NOT NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE petty_cash_fund_requests
            SET request_date = CAST(created_at AS DATE)
            WHERE request_date IS NULL
            """
        )
    )
    op.alter_column(
        "petty_cash_fund_requests",
        "request_date",
        existing_type=sa.Date(),
        nullable=False,
    )
    op.drop_index(
        "ix_petty_cash_fund_requests_approved_by_id",
        table_name="petty_cash_fund_requests",
    )
    op.drop_index(
        "ix_petty_cash_fund_requests_confirmed_by_id",
        table_name="petty_cash_fund_requests",
    )
    op.drop_constraint(
        "fk_fund_request_approved_by",
        "petty_cash_fund_requests",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_fund_request_confirmed_by",
        "petty_cash_fund_requests",
        type_="foreignkey",
    )
    op.drop_column("petty_cash_fund_requests", "approved_by_id")
    op.drop_column("petty_cash_fund_requests", "confirmed_by_id")
    op.drop_column("petty_cash_fund_requests", "confirmed_at")
