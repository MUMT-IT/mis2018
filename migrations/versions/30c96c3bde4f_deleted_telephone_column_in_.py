"""Deleted telephone column in ServiceCustomerInfo model

Revision ID: 30c96c3bde4f
Revises: 4d2cf4202693
Create Date: 2024-07-15 16:20:13.038624

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '30c96c3bde4f'
down_revision = '4d2cf4202693'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_customer_infos', schema=None) as batch_op:
        batch_op.drop_column('telephone')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_customer_infos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('telephone', sa.VARCHAR(), autoincrement=False, nullable=True))

    # ### end Alembic commands ###
