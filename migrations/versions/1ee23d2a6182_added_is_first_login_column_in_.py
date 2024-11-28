"""Added is_first_login column in ServiceCustomerAccount model

Revision ID: 1ee23d2a6182
Revises: 6a493d61e6d2
Create Date: 2024-11-27 11:50:46.629761

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1ee23d2a6182'
down_revision = '6a493d61e6d2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_customer_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_first_login', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_customer_accounts', schema=None) as batch_op:
        batch_op.drop_column('is_first_login')
    # ### end Alembic commands ###