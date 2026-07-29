"""drop role from ot announcement signatories

Revision ID: 1b2c3d4e5f67
Revises: 7d9f4c8c2a11
Create Date: 2026-07-02 19:20:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '1b2c3d4e5f67'
down_revision = '7d9f4c8c2a11'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ot_announcement_signatories', schema=None) as batch_op:
        batch_op.drop_column('role')


def downgrade():
    from sqlalchemy import String
    import sqlalchemy as sa

    with op.batch_alter_table('ot_announcement_signatories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', String(), nullable=False))
