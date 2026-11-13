"""Track reminder attempts to prevent duplicate LINE messages."""
from alembic import op
import sqlalchemy as sa

revision = 'bf23456789ab'
down_revision = 'ae1f23456789'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'staff_checkin_reminder_delivery',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('staff_account.id'), nullable=False),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('mode', sa.String(10), nullable=False),
        sa.Column('scheduled_time', sa.Time(), nullable=False),
        sa.Column('status', sa.String(10), nullable=False),
        sa.Column('attempted_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('staff_id', 'work_date', 'mode', name='uq_checkin_reminder_mode'),
        sa.UniqueConstraint('staff_id', 'work_date', 'scheduled_time', name='uq_checkin_reminder_slot'),
    )


def downgrade():
    op.drop_table('staff_checkin_reminder_delivery')
