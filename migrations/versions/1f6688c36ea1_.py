"""merge heads

Revision ID: 1f6688c36ea1
Revises: 1a4bc4862d4f, 5dc53da28b8a
Create Date: 2025-04-30 10:05:43.239597

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1f6688c36ea1'
down_revision = ('1a4bc4862d4f', '5dc53da28b8a')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
