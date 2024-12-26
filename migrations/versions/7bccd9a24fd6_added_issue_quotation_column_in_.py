"""Added issue_quotation column in ServiceRequest model

Revision ID: 7bccd9a24fd6
Revises: 08bd12dae55c
Create Date: 2024-12-25 14:03:38.958830

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '7bccd9a24fd6'
down_revision = '08bd12dae55c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('issue_quotation', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('service_requests', schema=None) as batch_op:
        batch_op.drop_column('issue_quotation')
    # ### end Alembic commands ###