"""Add retirement flag to SmartClass online accounts

Revision ID: 4b5c6d7e8f90
Revises: 8e1e3d19354e
"""
from alembic import op
import sqlalchemy as sa


revision = '4b5c6d7e8f90'
down_revision = '8e1e3d19354e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'smartclass_scheduler_online_accounts',
        sa.Column('is_retired', sa.Boolean(), nullable=True),
    )


def downgrade():
    op.drop_column('smartclass_scheduler_online_accounts', 'is_retired')
