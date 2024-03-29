"""added book number field to the receipt model

Revision ID: 1fd84d7a9e98
Revises: 7fe034326b48
Create Date: 2020-01-24 05:04:49.336144

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1fd84d7a9e98'
down_revision = '7fe034326b48'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comhealth_test_receipts', sa.Column('book_number', sa.String(length=16), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('comhealth_test_receipts', 'book_number')
    # ### end Alembic commands ###
