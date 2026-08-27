"""Allow procurement plans without an assigned procurement officer

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
"""
from alembic import op


revision = 'e8f9a0b1c2d3'
down_revision = 'd7e8f9a0b1c2'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('procurement_plans', 'responsible_staff_id', nullable=True)


def downgrade():
    op.alter_column('procurement_plans', 'responsible_staff_id', nullable=False)
