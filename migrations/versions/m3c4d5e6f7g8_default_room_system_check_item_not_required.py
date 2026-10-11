"""default room system check item not required

Revision ID: m3c4d5e6f7g8
Revises: m2b3c4d5e6f7
Create Date: 2026-10-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm3c4d5e6f7g8'
down_revision = 'm2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'maintenance_room_system_check_items',
        'is_required',
        existing_type=sa.Boolean(),
        server_default=sa.false()
    )


def downgrade():
    op.alter_column(
        'maintenance_room_system_check_items',
        'is_required',
        existing_type=sa.Boolean(),
        server_default=sa.true()
    )
