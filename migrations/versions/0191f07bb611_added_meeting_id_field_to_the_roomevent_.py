"""added meeting ID field to the RoomEvent model

Revision ID: 0191f07bb611
Revises: 7556ef97c771
Create Date: 2023-06-10 11:29:35.911609

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0191f07bb611'
down_revision = '7556ef97c771'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('scheduler_room_reservations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('meeting_event_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(None, 'meeting_events', ['meeting_event_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('scheduler_room_reservations', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('meeting_event_id')

    # ### end Alembic commands ###
