"""renamed from item_id column to procurement_detail_id column and tablename in ProcurementBorrowItem model

Revision ID: 2f522ac90835
Revises: 45d94097fb3e
Create Date: 2023-02-27 16:48:21.912000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f522ac90835'
down_revision = '45d94097fb3e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('procurement_borrow_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('borrow_detail_id', sa.Integer(), nullable=True),
    sa.Column('procurement_detail_id', sa.Integer(), nullable=True),
    sa.Column('item', sa.String(), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.Column('unit', sa.String(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['borrow_detail_id'], ['procurement_borrow_details.id'], ),
    sa.ForeignKeyConstraint(['procurement_detail_id'], ['procurement_details.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_table('electronic_borrow_items')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('electronic_borrow_items',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('borrow_detail_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('item_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('item', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('quantity', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('unit', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('note', sa.TEXT(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['borrow_detail_id'], [u'procurement_borrow_details.id'], name=u'electronic_borrow_items_borrow_detail_id_fkey'),
    sa.ForeignKeyConstraint(['item_id'], [u'procurement_details.id'], name=u'electronic_borrow_items_item_id_fkey'),
    sa.PrimaryKeyConstraint('id', name=u'electronic_borrow_items_pkey')
    )
    op.drop_table('procurement_borrow_items')
    # ### end Alembic commands ###
