"""renamed lis result model table

Revision ID: 01843dc7a010
Revises: 352411cc1bd2
Create Date: 2018-09-10 02:24:34.177171

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '01843dc7a010'
down_revision = '352411cc1bd2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('lis_results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('reported_by', sa.Integer(), nullable=False),
    sa.Column('quant_value', sa.Numeric(), nullable=True),
    sa.Column('qual_value', sa.String(), nullable=True),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=True),
    sa.Column('comment', sa.String(), nullable=True),
    sa.Column('commenter_id', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['commenter_id'], ['students.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['lis_orders.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_table('lis_result_child')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('lis_result_child',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('reported_by', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('quant_value', sa.NUMERIC(), autoincrement=False, nullable=True),
    sa.Column('qual_value', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('revision', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('order_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('comment', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('commenter_id', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['commenter_id'], [u'students.id'], name=u'lis_result_child_commenter_id_fkey'),
    sa.ForeignKeyConstraint(['order_id'], [u'lis_orders.id'], name=u'lis_result_child_order_id_fkey'),
    sa.PrimaryKeyConstraint('id', name=u'lis_result_child_pkey')
    )
    op.drop_table('lis_results')
    # ### end Alembic commands ###
