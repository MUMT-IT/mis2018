"""changed the type of the amount field to float

Revision ID: e7629760b468
Revises: edea59c5d8fd
Create Date: 2022-03-03 14:07:25.987000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7629760b468'
down_revision = 'edea59c5d8fd'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('tracker_accounts', column_name="amount", type_=sa.Float())


def downgrade():
    op.alter_column('tracker_accounts', column_name="amount", type_=sa.Integer())
