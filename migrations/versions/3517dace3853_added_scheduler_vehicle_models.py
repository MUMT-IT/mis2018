"""added scheduler vehicle models

Revision ID: 3517dace3853
Revises: c1e80486147a
Create Date: 2018-11-26 02:38:59.949043

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3517dace3853'
down_revision = 'c1e80486147a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('scheduler_vehicle_avails',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('availability', sa.String(length=32), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('scheduler_vehicle_types',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=32), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('scheduler_vehicle_resources',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('license', sa.String(length=8), nullable=False),
    sa.Column('maker', sa.String(length=16), nullable=False),
    sa.Column('model', sa.String(length=16), nullable=True),
    sa.Column('year', sa.String(length=4), nullable=True),
    sa.Column('occupancy', sa.Integer(), nullable=False),
    sa.Column('desc', sa.Text(), nullable=True),
    sa.Column('business_hour_start', sa.Time(), nullable=True),
    sa.Column('business_hour_end', sa.Time(), nullable=True),
    sa.Column('availability_id', sa.Integer(), nullable=True),
    sa.Column('type_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['availability_id'], ['scheduler_vehicle_avails.id'], ),
    sa.ForeignKeyConstraint(['type_id'], ['scheduler_vehicle_types.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('scheduler_vehicle_resources')
    op.drop_table('scheduler_vehicle_types')
    op.drop_table('scheduler_vehicle_avails')
    # ### end Alembic commands ###
