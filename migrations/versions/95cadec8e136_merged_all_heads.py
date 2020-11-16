"""merged all heads

Revision ID: 95cadec8e136
Revises: 6f31d823928e, 92a8e81581a8
Create Date: 2020-11-16 21:25:01.935418

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '95cadec8e136'
down_revision = ('6f31d823928e', '92a8e81581a8')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
