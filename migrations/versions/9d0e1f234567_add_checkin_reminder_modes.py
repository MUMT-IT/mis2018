"""Add independently selectable check-in reminder modes."""
from alembic import op
import sqlalchemy as sa

revision = '9d0e1f234567'
down_revision = '8c9d0e1f2345'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('staff_checkin_reminder_setting', sa.Column('system_reminder', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('staff_checkin_reminder_setting', sa.Column('average_reminder', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('staff_checkin_reminder_setting', 'average_reminder')
    op.drop_column('staff_checkin_reminder_setting', 'system_reminder')
