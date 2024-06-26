"""Added customer_info_id, customer_info column in StaffAccount and added StaffCustomerInfo Model

Revision ID: 8f3c107ef47b
Revises: 33e258fe6433
Create Date: 2024-04-26 16:09:43.140931

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f3c107ef47b'
down_revision = '33e258fe6433'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('staff_customer_info',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('title', sa.String(), nullable=True),
    sa.Column('firstname', sa.String(), nullable=False),
    sa.Column('lastname', sa.String(), nullable=False),
    sa.Column('organization_name', sa.String(), nullable=True),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('telephone', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('staff_account', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_info_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(None, 'staff_customer_info', ['customer_info_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('staff_account', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('customer_info_id')

    op.drop_table('staff_customer_info')
    # ### end Alembic commands ###
