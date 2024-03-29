"""added number limit string in column erp code, procurement no, and cost center

Revision ID: 700be2a134f5
Revises: 9c5f74248de0
Create Date: 2022-11-03 18:18:01.532000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '700be2a134f5'
down_revision = '9c5f74248de0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('procurement_details', 'erp_code',
               existing_type=sa.VARCHAR(),
               nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('procurement_details', 'erp_code',
               existing_type=sa.VARCHAR(),
               nullable=False)
    # ### end Alembic commands ###
