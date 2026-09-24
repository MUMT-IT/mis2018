"""Restore the created_at default for student skill evidence.

Revision ID: e0d5c6b7a8f9
Revises: d9c4b5a36e17
"""

from alembic import op
import sqlalchemy as sa


revision = "e0d5c6b7a8f9"
down_revision = "d9c4b5a36e17"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "eduqa_student_skill_evidence",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "eduqa_student_skill_evidence",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False,
    )
