"""Add optional medical technologist license number to CE members."""

from alembic import op
import sqlalchemy as sa


revision = "aa1b2c3d4e5f"
down_revision = "z3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ce_members",
        sa.Column(
            "mt_license_no",
            sa.String(length=100),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("ce_members", "mt_license_no")
