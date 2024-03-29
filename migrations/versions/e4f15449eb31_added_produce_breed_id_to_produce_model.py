"""added produce_breed_id to produce model

Revision ID: e4f15449eb31
Revises: dd24e97fd44c
Create Date: 2018-02-03 22:38:33.277663

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4f15449eb31'
down_revision = 'dd24e97fd44c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('food_produce_breeds',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column(u'food_produces', sa.Column('produce_breed_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'food_produces', 'food_produce_breeds', ['produce_breed_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'food_produces', type_='foreignkey')
    op.drop_column(u'food_produces', 'produce_breed_id')
    op.drop_table('food_produce_breeds')
    # ### end Alembic commands ###
