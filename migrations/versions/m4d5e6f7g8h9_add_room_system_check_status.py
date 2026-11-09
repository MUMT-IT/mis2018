"""add room system check status

Revision ID: m4d5e6f7g8h9
Revises: m3c4d5e6f7g8
Create Date: 2026-10-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'm4d5e6f7g8h9'
down_revision = 'm3c4d5e6f7g8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'maintenance_room_system_check_submissions',
        sa.Column(
            'status', sa.String(length=20), nullable=False,
            server_default='minor_issue'
        )
    )
    op.create_check_constraint(
        'ck_maintenance_room_system_check_submission_status',
        'maintenance_room_system_check_submissions',
        "status IN ('normal', 'minor_issue', 'unavailable')"
    )
    op.alter_column(
        'maintenance_room_system_check_submissions',
        'status',
        existing_type=sa.String(length=20),
        server_default=None
    )


def downgrade():
    op.drop_constraint(
        'ck_maintenance_room_system_check_submission_status',
        'maintenance_room_system_check_submissions',
        type_='check'
    )
    op.drop_column('maintenance_room_system_check_submissions', 'status')
