"""Added default of print number column in ElectronicReceiptDetail model

Revision ID: 8c8ef2c96a89
Revises: 0384a54f9d5a
Create Date: 2022-11-17 14:14:01.702000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c8ef2c96a89'
down_revision = '0384a54f9d5a'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(u'electronic_receipt_details', sa.Column('print_number', sa.Integer(), nullable=True, default=0))


def downgrade():
    op.drop_column(u'electronic_receipt_details', 'print_number')
