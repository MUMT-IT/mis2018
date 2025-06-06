"""Added discount column in ServiceQuotation model

Revision ID: 310fcb9def44
Revises: dc070efa6387
Create Date: 2025-05-15 11:09:29.173912

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '310fcb9def44'
down_revision = 'dc070efa6387'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_quotations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('discount', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_quotations', schema=None) as batch_op:
        batch_op.drop_column('discount')
    # ### end Alembic commands ###
