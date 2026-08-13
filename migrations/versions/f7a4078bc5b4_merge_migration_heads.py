"""merge migration heads

Revision ID: f7a4078bc5b4
Revises: 8c0d1e2f3a45, c4d7a8e1f2b3, e4fe4f6ff5d1
Create Date: 2026-08-09 16:35:55.157158

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7a4078bc5b4'
down_revision = ('8c0d1e2f3a45', 'c4d7a8e1f2b3', 'e4fe4f6ff5d1')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
