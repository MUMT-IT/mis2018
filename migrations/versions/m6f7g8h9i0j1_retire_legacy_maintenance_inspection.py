"""retire legacy maintenance inspection

Revision ID: m6f7g8h9i0j1
Revises: m5e6f7g8h9i0
Create Date: 2026-10-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'm6f7g8h9i0j1'
down_revision = 'm5e6f7g8h9i0'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        'ck_maintenance_room_system_equipment_source',
        'maintenance_room_system_equipment',
        type_='check'
    )
    op.drop_constraint(
        'maintenance_room_system_equipment_room_equipment_id_fkey',
        'maintenance_room_system_equipment',
        type_='foreignkey'
    )
    op.drop_index(
        'ix_maintenance_room_system_equipment_room_equipment_id',
        table_name='maintenance_room_system_equipment'
    )
    op.drop_column('maintenance_room_system_equipment', 'room_equipment_id')
    op.alter_column(
        'maintenance_room_system_equipment',
        'procurement_detail_id',
        existing_type=sa.Integer(),
        nullable=False
    )

    op.drop_table('maintenance_inspection_items')
    op.execute(
        'DROP TRIGGER IF EXISTS trg_maintenance_inspection_submissions_updated_at '
        'ON maintenance_inspection_submissions'
    )
    op.drop_table('maintenance_inspection_submissions')

    op.execute(
        'DROP TRIGGER IF EXISTS trg_maintenance_room_equipment_updated_at '
        'ON maintenance_room_equipment'
    )
    op.drop_table('maintenance_room_equipment')
    op.drop_table('maintenance_equipment_types')


def downgrade():
    raise NotImplementedError(
        'Legacy maintenance tables contained deleted operational data and cannot be restored automatically.'
    )
