"""renamed lender to procurement in AVUBorrowReturnServiceDetail model

Revision ID: 971217a015f6
Revises: ba102c70d58c
Create Date: 2024-01-30 15:23:43.981412

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '971217a015f6'
down_revision = 'ba102c70d58c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('avu_borrow_return_service_details', schema=None) as batch_op:
        batch_op.add_column(sa.Column('procurement_id', sa.Integer(), nullable=True))
        batch_op.drop_constraint('avu_borrow_return_service_details_lender_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(None, 'procurement_details', ['procurement_id'], ['id'])
        batch_op.drop_column('lender_id')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('avu_borrow_return_service_details', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lender_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key('avu_borrow_return_service_details_lender_id_fkey', 'procurement_details', ['lender_id'], ['id'])
        batch_op.drop_column('procurement_id')

    # ### end Alembic commands ###