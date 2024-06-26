"""Added taxpayer_identification_no column in StaffCustomerInfo Model

Revision ID: 65b190531fae
Revises: 8f3c107ef47b
Create Date: 2024-04-30 08:23:32.994334

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '65b190531fae'
down_revision = '8f3c107ef47b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('staff_customer_info', schema=None) as batch_op:
        batch_op.add_column(sa.Column('taxpayer_identification_no', sa.String(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('staff_customer_info', schema=None) as batch_op:
        batch_op.drop_column('taxpayer_identification_no')

    # ### end Alembic commands ###
