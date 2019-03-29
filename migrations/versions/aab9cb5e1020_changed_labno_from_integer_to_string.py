"""changed labno from integer to string

Revision ID: aab9cb5e1020
Revises: 59eb86ebb428
Create Date: 2019-03-29 06:08:22.545788

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aab9cb5e1020'
down_revision = '59eb86ebb428'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('comhealth_test_records', 'labno', type_=sa.String())


def downgrade():
    op.alter_column('comhealth_test_records', 'labno', type_=sa.Integer())
