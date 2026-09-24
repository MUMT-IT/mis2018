"""Add notes to short URL mappings.

Revision ID: f3c4d5e6f7a8
Revises: f2b3c4d5e6f7
"""

from alembic import op
import sqlalchemy as sa


revision = 'f3c4d5e6f7a8'
down_revision = 'f2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('shorturl_mappings', sa.Column('note', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('shorturl_mappings', 'note')
