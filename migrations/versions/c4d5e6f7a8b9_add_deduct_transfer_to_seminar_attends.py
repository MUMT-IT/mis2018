"""Add transfer deduction flag to seminar attendance records."""

from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b9"
down_revision = "b534577b36d1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "staff_seminar_attends",
        sa.Column("deduct_transfer", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("staff_seminar_attends", "deduct_transfer")
