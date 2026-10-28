"""Add the advance-payment status catalog.

Revision ID: r1s2t3u4v5w6
Revises: q0d1e2f3a4b5
Create Date: 2026-10-28
"""

from alembic import op
import sqlalchemy as sa


revision = "r1s2t3u4v5w6"
down_revision = "q0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "advance_payment_statuses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status_group", sa.String(length=64), nullable=False),
        sa.Column("code", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_advance_payment_statuses_code"),
        sa.UniqueConstraint(
            "status_group",
            "code",
            name="uq_advance_payment_statuses_group_code",
        ),
    )
    op.create_index(
        "ix_advance_payment_statuses_status_group",
        "advance_payment_statuses",
        ["status_group"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_advance_payment_statuses_status_group",
        table_name="advance_payment_statuses",
    )
    op.drop_table("advance_payment_statuses")
