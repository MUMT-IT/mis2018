"""added thumbnail url field

Revision ID: 6ec79a0163cd
Revises: 1c2d9f4a8b71
Create Date: 2026-05-30 22:18:14.310988

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6ec79a0163cd'
down_revision = '1c2d9f4a8b71'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('procurement_details', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_thumbnail_url', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('procurement_details', schema=None) as batch_op:
        batch_op.drop_column('image_thumbnail_url')
