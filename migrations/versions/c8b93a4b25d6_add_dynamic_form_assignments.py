"""Add reusable dynamic form assignments.

Revision ID: c8b93a4b25d6
Revises: b7a8293a14c5
"""

from alembic import op
import sqlalchemy as sa


revision = "c8b93a4b25d6"
down_revision = "b7a8293a14c5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dynamic_form_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("assigned_by_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["dynamic_form_versions.id"]),
        sa.ForeignKeyConstraint(["assigned_by_id"], ["staff_account.id"]),
    )


def downgrade():
    op.drop_table("dynamic_form_assignments")
