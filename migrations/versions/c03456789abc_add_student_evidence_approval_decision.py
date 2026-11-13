"""Store the approver's pass/fail decision for student evidence.

Revision ID: c03456789abc
Revises: bf23456789ab
"""
from alembic import op
import sqlalchemy as sa

revision = 'c03456789abc'
down_revision = 'bf23456789ab'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('eduqa_student_skill_evidence',
                  sa.Column('endorsed_passed', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('eduqa_student_skill_evidence', 'endorsed_passed')
