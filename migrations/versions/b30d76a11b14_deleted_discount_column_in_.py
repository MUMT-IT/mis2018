"""Deleted discount column in ServiceInvoice model

Revision ID: b30d76a11b14
Revises: 940e2b256ecb
Create Date: 2025-05-26 10:50:11.519109

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b30d76a11b14'
down_revision = '940e2b256ecb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_invoices', schema=None) as batch_op:
        batch_op.drop_column('discount')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('discount', sa.VARCHAR(), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
