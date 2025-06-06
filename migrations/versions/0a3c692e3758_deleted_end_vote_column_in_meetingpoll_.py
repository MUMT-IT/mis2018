"""Deleted end_vote column in MeetingPoll model

Revision ID: 0a3c692e3758
Revises: e7d1962e5625
Create Date: 2025-03-26 13:50:09.358771

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0a3c692e3758'
down_revision = 'e7d1962e5625'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('meeting_polls', schema=None) as batch_op:
        batch_op.drop_column('end_vote')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('meeting_polls', schema=None) as batch_op:
        batch_op.add_column(sa.Column('end_vote', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
