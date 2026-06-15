"""Add external_email to staff_account

Revision ID: 2c5b8f0e7d1a
Revises: 2f4a8c1d9b7e
Create Date: 2026-06-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2c5b8f0e7d1a'
down_revision = '2f4a8c1d9b7e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('staff_account', schema=None) as batch_op:
        batch_op.add_column(sa.Column('external_email', sa.String(), nullable=True))
        batch_op.create_index(batch_op.f('ix_staff_account_external_email'), ['external_email'], unique=True)


def downgrade():
    with op.batch_alter_table('staff_account', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_staff_account_external_email'))
        batch_op.drop_column('external_email')
