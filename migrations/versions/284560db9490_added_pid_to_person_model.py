"""added PID to person model

Revision ID: 284560db9490
Revises: 1450978b43fa
Create Date: 2018-01-24 23:13:11.569196

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '284560db9490'
down_revision = '1450978b43fa'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('food_persons', sa.Column('pid', sa.String(length=13), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('food_persons', 'pid')
    # ### end Alembic commands ###
