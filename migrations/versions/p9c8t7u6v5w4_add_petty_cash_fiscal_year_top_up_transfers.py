"""Add petty-cash fiscal-year top-up transfer records.

Revision ID: p9c8t7u6v5w4
Revises: 6b7fade84402
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa


revision = "p9c8t7u6v5w4"
down_revision = "6b7fade84402"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "petty_cash_fiscal_year_top_up_transfers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("petty_cash_setting_id", sa.Integer(), nullable=False),
        sa.Column("transfer_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("transferred_at", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_edited_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["last_edited_by_id"],
            ["staff_account.id"],
            name="fk_petty_cash_top_up_transfer_last_editor",
        ),
        sa.ForeignKeyConstraint(
            ["petty_cash_setting_id"],
            ["petty_cash_settings.id"],
            name="fk_petty_cash_top_up_transfer_setting",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "petty_cash_setting_id",
            name="uq_petty_cash_top_up_transfer_setting",
        ),
    )
    op.create_index(
        "ix_petty_cash_top_up_transfer_setting_id",
        "petty_cash_fiscal_year_top_up_transfers",
        ["petty_cash_setting_id"],
    )


def downgrade():
    op.drop_index(
        "ix_petty_cash_top_up_transfer_setting_id",
        table_name="petty_cash_fiscal_year_top_up_transfers",
    )
    op.drop_table("petty_cash_fiscal_year_top_up_transfers")
