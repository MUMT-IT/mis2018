"""added qoute field to profile model

Revision ID: 59eb86ebb428
Revises: 75f6a0b71871
Create Date: 2019-03-27 18:33:22.720506

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '59eb86ebb428'
down_revision = '75f6a0b71871'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comhealth_test_profiles', sa.Column('quote', sa.Numeric(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('comhealth_test_profiles', 'quote')
    # ### end Alembic commands ###
