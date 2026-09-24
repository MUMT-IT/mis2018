"""Make short URL expiration optional.

Revision ID: f2b3c4d5e6f7
Revises: f1a2b3c4d5e6
"""

from alembic import op
import sqlalchemy as sa


revision = 'f2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'shorturl_mappings',
        'expires_at',
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        'shorturl_mappings',
        'expires_at',
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
