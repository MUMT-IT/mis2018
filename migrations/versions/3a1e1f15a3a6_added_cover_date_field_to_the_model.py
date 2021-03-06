"""added cover date field to the model

Revision ID: 3a1e1f15a3a6
Revises: 0c892eac47fa
Create Date: 2020-11-01 22:57:47.716571

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a1e1f15a3a6'
down_revision = '0c892eac47fa'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('research_pub', sa.Column('cover_date', sa.Date(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('research_pub', 'cover_date')
    # ### end Alembic commands ###
