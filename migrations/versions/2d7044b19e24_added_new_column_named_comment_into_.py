"""added new column named comment into RommEvent table

Revision ID: 2d7044b19e24
Revises: 0c6cf61f3ac8
Create Date: 2024-06-12 21:02:10.846095

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2d7044b19e24'
down_revision = '0c6cf61f3ac8'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('scheduler_room_reservations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('comment', sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('scheduler_room_reservations', schema=None) as batch_op:
        batch_op.drop_column('comment')

    # ### end Alembic commands ###
