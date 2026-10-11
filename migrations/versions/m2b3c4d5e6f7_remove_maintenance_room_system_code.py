"""remove maintenance room system code

Revision ID: m2b3c4d5e6f7
Revises: m1a2b3c4d5e6
Create Date: 2026-10-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm2b3c4d5e6f7'
down_revision = 'm1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        'maintenance_room_systems_code_key',
        'maintenance_room_systems',
        type_='unique'
    )
    op.drop_column('maintenance_room_systems', 'code')


def downgrade():
    op.add_column(
        'maintenance_room_systems',
        sa.Column('code', sa.String(length=32), nullable=True)
    )
    op.execute(
        "UPDATE maintenance_room_systems "
        "SET code = 'system-' || id::text "
        "WHERE code IS NULL"
    )
    op.alter_column('maintenance_room_systems', 'code', nullable=False)
    op.create_unique_constraint(
        'maintenance_room_systems_code_key',
        'maintenance_room_systems', ['code']
    )
