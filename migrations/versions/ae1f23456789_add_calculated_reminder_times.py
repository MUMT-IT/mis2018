"""Store daily calculated personalized reminder times."""
from alembic import op
import sqlalchemy as sa

revision = 'ae1f23456789'
down_revision = '9d0e1f234567'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('staff_checkin_reminder_setting', sa.Column('sample_days', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('staff_checkin_reminder_setting', sa.Column('average_checkin_time', sa.Time()))
    op.add_column('staff_checkin_reminder_setting', sa.Column('calculated_for', sa.Date()))


def downgrade():
    op.drop_column('staff_checkin_reminder_setting', 'calculated_for')
    op.drop_column('staff_checkin_reminder_setting', 'average_checkin_time')
    op.drop_column('staff_checkin_reminder_setting', 'sample_days')
