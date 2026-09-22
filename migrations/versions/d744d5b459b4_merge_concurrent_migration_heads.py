"""merge concurrent migration heads

Revision ID: d744d5b459b4
Revises: 9862e112af74, m1a2b3c4d5e6, o3c4d5e6f7a8
Create Date: 2026-09-22 08:47:04.030793

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd744d5b459b4'
down_revision = ('9862e112af74', 'm1a2b3c4d5e6', 'o3c4d5e6f7a8')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
