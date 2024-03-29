"""added unit field to the lab test model

Revision ID: d9528fe05a59
Revises: 5b0c486a48d9
Create Date: 2018-03-25 15:11:36.610552

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd9528fe05a59'
down_revision = '5b0c486a48d9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('food_health_lab_tests', sa.Column('unit', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('food_health_lab_tests', 'unit')
    # ### end Alembic commands ###
