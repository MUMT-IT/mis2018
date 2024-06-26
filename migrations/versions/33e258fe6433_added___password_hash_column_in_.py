"""Added __password_hash column in ServiceCustomerAccount Model

Revision ID: 33e258fe6433
Revises: 265e7d29dd25
Create Date: 2024-04-26 13:22:28.606174

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '33e258fe6433'
down_revision = '265e7d29dd25'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_customer_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('password', sa.String(length=255), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_customer_accounts', schema=None) as batch_op:
        batch_op.drop_column('password')

    # ### end Alembic commands ###
