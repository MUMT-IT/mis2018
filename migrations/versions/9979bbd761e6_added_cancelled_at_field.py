"""added cancelled at field

Revision ID: 9979bbd761e6
Revises: 8e7e2c7c8b8c
Create Date: 2021-02-24 00:41:55.950131

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9979bbd761e6'
down_revision = '8e7e2c7c8b8c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('health_service_timeslots', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('health_service_timeslots', 'cancelled_at')
    # ### end Alembic commands ###
