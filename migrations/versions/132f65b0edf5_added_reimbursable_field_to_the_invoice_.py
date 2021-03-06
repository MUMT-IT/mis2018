"""added reimbursable field to the invoice model

Revision ID: 132f65b0edf5
Revises: 543a6b9e1fdb
Create Date: 2019-12-19 06:04:37.618495

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '132f65b0edf5'
down_revision = '543a6b9e1fdb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comhealth_invoice', sa.Column('reimbursable', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('comhealth_invoice', 'reimbursable')
    # ### end Alembic commands ###
