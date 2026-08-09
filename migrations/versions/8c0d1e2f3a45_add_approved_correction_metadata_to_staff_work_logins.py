"""add approved correction metadata to staff work logins

Revision ID: 8c0d1e2f3a45
Revises: 7b9c0d1e2f34
Create Date: 2026-08-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '8c0d1e2f3a45'
down_revision = '7b9c0d1e2f34'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('staff_work_logins', sa.Column('record_source', sa.String(length=30), nullable=True))
    op.add_column('staff_work_logins', sa.Column('correction_type', sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column('staff_work_logins', 'correction_type')
    op.drop_column('staff_work_logins', 'record_source')
