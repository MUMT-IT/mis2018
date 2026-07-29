"""Add external flag to orgs

Revision ID: 2f4a8c1d9b7e
Revises: c4e3209db45b
Create Date: 2026-06-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f4a8c1d9b7e'
down_revision = 'c4e3209db45b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('orgs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_external', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('orgs', schema=None) as batch_op:
        batch_op.drop_column('is_external')
