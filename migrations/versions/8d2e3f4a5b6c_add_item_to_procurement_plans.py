"""Add item to procurement plans

Revision ID: 8d2e3f4a5b6c
Revises: 7c1d2e3f4a5b
"""
from alembic import op
import sqlalchemy as sa


revision = '8d2e3f4a5b6c'
down_revision = '7c1d2e3f4a5b'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('procurement_plans', sa.Column('item', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('procurement_plans', 'item')
