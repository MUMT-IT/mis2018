"""add SQLAlchemy-Continuum remote address metadata

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'transaction',
        sa.Column('remote_addr', sa.String(length=50), nullable=True),
    )


def downgrade():
    op.drop_column('transaction', 'remote_addr')
