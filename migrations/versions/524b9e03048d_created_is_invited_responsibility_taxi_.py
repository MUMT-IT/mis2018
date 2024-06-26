"""created is_invited, responsibility, taxi_cost, train_ticket_cost, flight_ticket_cost, fuel_cost and accommodation_cost columns in staff_seminar_attends table

Revision ID: 524b9e03048d
Revises: deff8bff6a0d
Create Date: 2022-07-08 15:54:02.439833

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '524b9e03048d'
down_revision = 'deff8bff6a0d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('staff_seminar_attends', sa.Column('accommodation_cost', sa.Float(), nullable=True))
    op.add_column('staff_seminar_attends', sa.Column('flight_ticket_cost', sa.Float(), nullable=True))
    op.add_column('staff_seminar_attends', sa.Column('fuel_cost', sa.Float(), nullable=True))
    op.add_column('staff_seminar_attends', sa.Column('is_invited', sa.Float(), nullable=True))
    op.add_column('staff_seminar_attends', sa.Column('responsibility', sa.String(), nullable=True))
    op.add_column('staff_seminar_attends', sa.Column('taxi_cost', sa.Float(), nullable=True))
    op.add_column('staff_seminar_attends', sa.Column('train_ticket_cost', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('staff_seminar_attends', 'train_ticket_cost')
    op.drop_column('staff_seminar_attends', 'taxi_cost')
    op.drop_column('staff_seminar_attends', 'responsibility')
    op.drop_column('staff_seminar_attends', 'is_invited')
    op.drop_column('staff_seminar_attends', 'fuel_cost')
    op.drop_column('staff_seminar_attends', 'flight_ticket_cost')
    op.drop_column('staff_seminar_attends', 'accommodation_cost')
    # ### end Alembic commands ###
