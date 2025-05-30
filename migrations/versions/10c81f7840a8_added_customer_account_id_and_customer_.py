"""Added customer_account_id and customer_account column in ServiceRequest model

Revision ID: 10c81f7840a8
Revises: 98d8a9c3cb73
Create Date: 2024-11-19 13:27:51.345444

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '10c81f7840a8'
down_revision = '98d8a9c3cb73'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_account_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(None, 'service_customer_accounts', ['customer_account_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_requests', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('customer_account_id')
    # ### end Alembic commands ###
