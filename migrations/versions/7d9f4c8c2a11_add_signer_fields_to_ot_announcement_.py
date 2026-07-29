"""add signer fields to ot announcement signatories

Revision ID: 7d9f4c8c2a11
Revises: c431f7f3a7f9
Create Date: 2026-07-02 19:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7d9f4c8c2a11'
down_revision = 'c431f7f3a7f9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ot_announcement_signatories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('signer_staff_account_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('signer_position', sa.String(), nullable=True))
        batch_op.create_foreign_key(None, 'staff_account', ['signer_staff_account_id'], ['id'])


def downgrade():
    with op.batch_alter_table('ot_announcement_signatories', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('signer_position')
        batch_op.drop_column('signer_staff_account_id')
