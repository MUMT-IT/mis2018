"""add online meeting and max_participants to ce_event_entities

Revision ID: f2a6bc4d9e10
Revises: 9c8e7f42b2d1
Create Date: 2026-03-03 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2a6bc4d9e10'
down_revision = '9c8e7f42b2d1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ce_event_entities', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'max_participants',
            sa.Integer(),
            nullable=True,
            comment='Maximum participants allowed for this event (applies to course/webinar)',
        ))
        batch_op.add_column(sa.Column(
            'online_platform',
            sa.String(length=50),
            nullable=True,
            comment='Online meeting platform for webinar (e.g., zoom, webex, teams, meet, other)',
        ))
        batch_op.add_column(sa.Column(
            'online_meeting_url',
            sa.String(length=1024),
            nullable=True,
            comment='Online meeting URL for webinar',
        ))
        batch_op.add_column(sa.Column(
            'online_meeting_password',
            sa.String(length=255),
            nullable=True,
            comment='Online meeting password/passcode for webinar',
        ))


def downgrade():
    with op.batch_alter_table('ce_event_entities', schema=None) as batch_op:
        batch_op.drop_column('online_meeting_password')
        batch_op.drop_column('online_meeting_url')
        batch_op.drop_column('online_platform')
        batch_op.drop_column('max_participants')
