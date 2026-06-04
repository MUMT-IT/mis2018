"""merge database heads

Revision ID: c4e3209db45b
Revises: c4a9e3d2b1f0, c2f54399ce6d
Create Date: 2026-06-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4e3209db45b'
down_revision = ('c4a9e3d2b1f0', 'c2f54399ce6d')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
