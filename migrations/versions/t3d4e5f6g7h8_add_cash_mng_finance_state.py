"""Add the global cash-management finance state switch.

Revision ID: t3d4e5f6g7h8
Revises: s2c3d4e5f6g7
Create Date: 2026-10-09
"""

from alembic import op
import sqlalchemy as sa


revision = "t3d4e5f6g7h8"
down_revision = "s2c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cash_mng_finance_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "is_open",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_edited_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["last_edited_by_id"], ["staff_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO cash_mng_finance_states (id, is_open) "
            "VALUES (1, true)"
        )
    )


def downgrade():
    op.drop_table("cash_mng_finance_states")
