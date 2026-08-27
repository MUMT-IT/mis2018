"""Remove stored status from procurement plans

Revision ID: 9e3f4a5b6c7d
Revises: 8d2e3f4a5b6c
"""
from alembic import op
import sqlalchemy as sa


revision = '9e3f4a5b6c7d'
down_revision = '8d2e3f4a5b6c'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index('ix_procurement_plans_status', table_name='procurement_plans')
    op.drop_column('procurement_plans', 'status')


def downgrade():
    op.add_column('procurement_plans', sa.Column('status', sa.String(length=64), nullable=True))
    op.create_index('ix_procurement_plans_status', 'procurement_plans', ['status'])
