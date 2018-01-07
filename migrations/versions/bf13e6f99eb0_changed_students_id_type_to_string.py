"""changed students.id type to string

Revision ID: bf13e6f99eb0
Revises: 0fe419fedb6c
Create Date: 2018-01-07 19:59:27.009679

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bf13e6f99eb0'
down_revision = '0fe419fedb6c'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('students', 'id', type_=sa.String())
    pass


def downgrade():
    op.alter_column('students', 'id', type_=sa.Integer())