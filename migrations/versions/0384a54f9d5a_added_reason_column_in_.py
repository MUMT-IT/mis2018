"""Added reason column in ElectronicReceiptRequest model

Revision ID: 0384a54f9d5a
Revises: 9c0052ee8f39
Create Date: 2022-11-17 13:49:15.480000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0384a54f9d5a'
down_revision = '9c0052ee8f39'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('electronic_receipt_requests', sa.Column('reason', sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('electronic_receipt_requests', 'reason')
    # ### end Alembic commands ###
