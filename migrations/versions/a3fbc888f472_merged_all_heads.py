"""merged all heads

Revision ID: a3fbc888f472
Revises: b3bf4a3b5bb6, 582a09b6d299
Create Date: 2020-12-16 16:35:24.933651

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3fbc888f472'
down_revision = ('b3bf4a3b5bb6', '582a09b6d299')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
