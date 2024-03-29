"""Added foreignKey of cost center and internal order in ElectronicReceiptItem model

Revision ID: 6287cac015eb
Revises: 9a3e93353177
Create Date: 2022-11-20 13:37:23.157000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6287cac015eb'
down_revision = '9a3e93353177'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('electronic_receipt_items', sa.Column('cost_center_id', sa.String(length=12), nullable=True))
    op.add_column('electronic_receipt_items', sa.Column('iocode_id', sa.String(length=16), nullable=True))
    op.create_foreign_key(None, 'electronic_receipt_items', 'iocodes', ['iocode_id'], ['id'])
    op.create_foreign_key(None, 'electronic_receipt_items', 'cost_centers', ['cost_center_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'electronic_receipt_items', type_='foreignkey')
    op.drop_constraint(None, 'electronic_receipt_items', type_='foreignkey')
    op.drop_column('electronic_receipt_items', 'iocode_id')
    op.drop_column('electronic_receipt_items', 'cost_center_id')
    # ### end Alembic commands ###
