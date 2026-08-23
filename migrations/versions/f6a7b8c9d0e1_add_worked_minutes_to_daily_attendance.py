"""add worked minutes to daily attendance snapshots

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'staff_daily_attendance',
        sa.Column('worked_minutes', sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column('staff_daily_attendance', 'worked_minutes')
