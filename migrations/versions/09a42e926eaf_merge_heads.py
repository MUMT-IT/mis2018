"""merge heads

Revision ID: 09a42e926eaf
Revises: a1bcebe7b26f, a29fec8b282e, b1ddddbc52e4
Create Date: 2026-02-02 09:44:58.606729

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '09a42e926eaf'
down_revision = ('a1bcebe7b26f', 'a29fec8b282e', 'b1ddddbc52e4')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
