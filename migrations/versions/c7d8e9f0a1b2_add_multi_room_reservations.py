"""add multi-room reservations and conjoined rooms

Revision ID: c7d8e9f0a1b2
Revises: bb023f8215e9
Create Date: 2026-09-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c7d8e9f0a1b2'
down_revision = 'bb023f8215e9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scheduler_room_conjoined_rooms',
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('conjoined_room_id', sa.Integer(), nullable=False),
        sa.CheckConstraint('room_id <> conjoined_room_id', name='ck_conjoined_rooms_distinct'),
        sa.ForeignKeyConstraint(['room_id'], ['scheduler_room_resources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conjoined_room_id'], ['scheduler_room_resources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('room_id', 'conjoined_room_id'),
    )
    op.create_table(
        'scheduler_room_reservation_rooms',
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['scheduler_room_reservations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['room_id'], ['scheduler_room_resources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('event_id', 'room_id'),
    )
    op.create_index(
        'ix_scheduler_room_reservation_rooms_room_id',
        'scheduler_room_reservation_rooms',
        ['room_id'],
    )


def downgrade():
    op.drop_index(
        'ix_scheduler_room_reservation_rooms_room_id',
        table_name='scheduler_room_reservation_rooms',
    )
    op.drop_table('scheduler_room_reservation_rooms')
    op.drop_table('scheduler_room_conjoined_rooms')
