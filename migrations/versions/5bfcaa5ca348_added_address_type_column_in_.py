"""Added address_type column in ServiceCustomerAddress model

Revision ID: 5bfcaa5ca348
Revises: 266db1a3f764
Create Date: 2024-11-20 10:47:25.907293

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5bfcaa5ca348'
down_revision = '266db1a3f764'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_customer_addresses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('address_type', sa.String(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_customer_addresses', schema=None) as batch_op:
        batch_op.drop_column('address_type')
    # ### end Alembic commands ###
