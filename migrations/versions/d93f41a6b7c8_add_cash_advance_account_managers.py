"""Add cash-advance account managers.

Revision ID: d93f41a6b7c8
Revises: b5d8e1f3a7c2
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa


revision = "d93f41a6b7c8"
down_revision = "b5d8e1f3a7c2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cash_advance_account_managers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bank_account_info_id", sa.Integer(), nullable=False),
        sa.Column("staff_account_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bank_account_info_id"],
            ["cash_mng_bank_account_infos.id"],
            name="fk_cash_advance_account_manager_bank_account",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["staff_account_id"],
            ["staff_account.id"],
            name="fk_cash_advance_account_manager_staff",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bank_account_info_id",
            "staff_account_id",
            name="uq_cash_advance_account_manager",
        ),
    )
    op.create_index(
        "ix_cash_advance_account_managers_bank_account_info_id",
        "cash_advance_account_managers",
        ["bank_account_info_id"],
    )
    op.create_index(
        "ix_cash_advance_account_managers_staff_account_id",
        "cash_advance_account_managers",
        ["staff_account_id"],
    )


def downgrade():
    op.drop_index(
        "ix_cash_advance_account_managers_staff_account_id",
        table_name="cash_advance_account_managers",
    )
    op.drop_index(
        "ix_cash_advance_account_managers_bank_account_info_id",
        table_name="cash_advance_account_managers",
    )
    op.drop_table("cash_advance_account_managers")
