"""added print profile note field to the Receipt model

Revision ID: 7d9062fc6c39
Revises: 49b842ea6d1b
Create Date: 2019-12-23 22:54:46.491070

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7d9062fc6c39'
down_revision = '49b842ea6d1b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comhealth_receipt_ids', sa.Column('print_profile_note', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('comhealth_receipt_ids', 'print_profile_note')
    # ### end Alembic commands ###
