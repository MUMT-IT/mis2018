"""Add passing percentage to dynamic form versions.

Revision ID: u8b9c0d1e2f3
Revises: s6f7a8b9c0d1
"""

from alembic import op
import sqlalchemy as sa


revision = "u8b9c0d1e2f3"
down_revision = "s6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "dynamic_form_versions",
        sa.Column("passing_percentage", sa.Numeric(5, 2), nullable=True),
    )


def downgrade():
    op.drop_column("dynamic_form_versions", "passing_percentage")
