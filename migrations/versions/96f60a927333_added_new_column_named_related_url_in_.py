"""added new column named related_url in pa_items table

Revision ID: 96f60a927333
Revises: e9de38dd1f26
Create Date: 2025-02-03 10:54:52.845340

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '96f60a927333'
down_revision = 'e9de38dd1f26'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pa_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('related_url', sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pa_items', schema=None) as batch_op:
        batch_op.drop_column('related_url')
    # ### end Alembic commands ###