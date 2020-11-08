"""merged wfh revision head

Revision ID: 9646fc7b894d
Revises: 50585d469351, 6c6d790581d7
Create Date: 2020-05-22 15:17:03.384977

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9646fc7b894d'
down_revision = ('50585d469351', '6c6d790581d7')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
