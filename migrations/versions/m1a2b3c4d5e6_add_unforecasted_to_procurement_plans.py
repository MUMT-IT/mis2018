"""Add unforecasted flag to procurement plans

Revision ID: m1a2b3c4d5e6
Revises: 95198b79d094
"""
from alembic import op
import sqlalchemy as sa


revision = 'm1a2b3c4d5e6'
down_revision = '95198b79d094'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'procurement_plans',
        sa.Column('is_unforecasted', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column('procurement_plans', 'is_unforecasted')
