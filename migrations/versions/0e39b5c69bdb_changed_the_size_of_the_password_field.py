"""changed the size of the password field

Revision ID: 0e39b5c69bdb
Revises: 2bd4b1f18129
Create Date: 2019-02-16 15:25:49.909326

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0e39b5c69bdb'
down_revision = '2bd4b1f18129'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('staff_account', 'password', type_=sa.String(255))


def downgrade():
    op.alter_column('staff_account', 'password', type_=sa.String(64))
