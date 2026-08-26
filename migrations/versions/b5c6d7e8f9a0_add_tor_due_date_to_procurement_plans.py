"""Add TOR due date to procurement plans

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
"""
from alembic import op
import sqlalchemy as sa


revision = 'b5c6d7e8f9a0'
down_revision = 'a4b5c6d7e8f9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('procurement_plans', sa.Column('tor_due_date', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('procurement_plans', 'tor_due_date')
