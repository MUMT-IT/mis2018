"""added room and coordinators association table

Revision ID: 024bd0251d0f
Revises: c88d3f379f5f
Create Date: 2023-11-29 16:34:39.732453

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '024bd0251d0f'
down_revision = 'c88d3f379f5f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('room_coordinator_assoc',
    sa.Column('staff_id', sa.Integer(), nullable=True),
    sa.Column('room_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['room_id'], ['scheduler_room_resources.id'], ),
    sa.ForeignKeyConstraint(['staff_id'], ['staff_account.id'], )
    )
    op.drop_table('meeting_poll_teams')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('meeting_poll_teams',
    sa.Column('group_detail_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('poll_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['group_detail_id'], ['staff_group_details.id'], name='meeting_poll_teams_group_detail_id_fkey'),
    sa.ForeignKeyConstraint(['poll_id'], ['meeting_polls.id'], name='meeting_poll_teams_poll_id_fkey'),
    sa.PrimaryKeyConstraint('group_detail_id', 'poll_id', name='meeting_poll_teams_pkey')
    )
    op.drop_table('room_coordinator_assoc')
    # ### end Alembic commands ###