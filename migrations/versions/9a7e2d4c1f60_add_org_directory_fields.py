"""Add organization directory URL and staff directory fields.

Revision ID: 9a7e2d4c1f60
Revises: f7a4078bc5b4
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa


revision = '9a7e2d4c1f60'
down_revision = 'f7a4078bc5b4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('orgs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('directory_url', sa.String(), nullable=True))

    with op.batch_alter_table('staff_personal_info', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position_level', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('image_url', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('staff_personal_info', schema=None) as batch_op:
        batch_op.drop_column('image_url')
        batch_op.drop_column('position_level')
    with op.batch_alter_table('orgs', schema=None) as batch_op:
        batch_op.drop_column('directory_url')
