"""Add personal check-in reminder preferences."""
from alembic import op
import sqlalchemy as sa

revision = '8c9d0e1f2345'
down_revision = '6b3bc8c2c20e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'staff_checkin_reminder_setting',
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('staff_account.id'), primary_key=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('reminder_time', sa.Time(), nullable=False),
        sa.Column('weekdays', sa.String(13), nullable=False),
    )


def downgrade():
    op.drop_table('staff_checkin_reminder_setting')
