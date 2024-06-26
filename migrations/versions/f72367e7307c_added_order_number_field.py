"""added order number field

Revision ID: f72367e7307c
Revises: 93cec64301c4
Create Date: 2023-06-20 23:16:09.804171

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f72367e7307c'
down_revision = '93cec64301c4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pa_levels', schema=None) as batch_op:
        batch_op.add_column(sa.Column('order', sa.Integer(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('pa_levels', schema=None) as batch_op:
        batch_op.drop_column('order')

    # ### end Alembic commands ###
