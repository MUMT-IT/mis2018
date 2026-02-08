"""merged all heads

Revision ID: dc2f756e54c0
Revises: b50897fd5374, 986a70767b54, f160ec5804e8
Create Date: 2020-08-25 10:47:07.548051

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dc2f756e54c0'
down_revision = ('986a70767b54', 'f160ec5804e8')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
