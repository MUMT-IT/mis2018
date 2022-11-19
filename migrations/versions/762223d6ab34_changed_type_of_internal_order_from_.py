"""Changed type of internal order from integer to string in ElectronicReceiptItem model

Revision ID: 762223d6ab34
Revises: c839d3abec54
Create Date: 2022-11-19 21:21:27.946000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '762223d6ab34'
down_revision = 'c839d3abec54'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('electronic_receipt_items', 'internal_order', type_=sa.String())


def downgrade():
    op.alter_column('electronic_receipt_items', 'internal_order', type_=sa.INTEGER())
