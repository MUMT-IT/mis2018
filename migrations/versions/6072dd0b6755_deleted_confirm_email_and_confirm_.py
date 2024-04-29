"""Deleted confirm_email and confirm_password and Changed password name in ServiceCustomerAccount Model

Revision ID: 6072dd0b6755
Revises: f08c179e544e
Create Date: 2024-04-26 13:13:20.237712

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6072dd0b6755'
down_revision = 'f08c179e544e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_customer_accounts', schema=None) as batch_op:
        batch_op.drop_constraint('service_customer_accounts_confirm_email_key', type_='unique')
        batch_op.drop_column('confirm_password')
        batch_op.drop_column('confirm_email')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_customer_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('confirm_email', sa.VARCHAR(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('confirm_password', sa.VARCHAR(length=255), autoincrement=False, nullable=True))
        batch_op.create_unique_constraint('service_customer_accounts_confirm_email_key', ['confirm_email'])

    # ### end Alembic commands ###