"""allow room systems without equipment

Revision ID: m7g8h9i0j1k2
Revises: m6f7g8h9i0j1
Create Date: 2026-10-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'm7g8h9i0j1k2'
down_revision = 'm6f7g8h9i0j1'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'maintenance_room_system_equipment',
        'procurement_detail_id',
        existing_type=sa.Integer(),
        nullable=True
    )
    op.create_index(
        'uq_mrse_room_group_without_asset',
        'maintenance_room_system_equipment',
        ['room_id', 'check_group_id'],
        unique=True,
        postgresql_where=sa.text('procurement_detail_id IS NULL')
    )
    op.create_index(
        'uq_mrse_room_procurement_asset',
        'maintenance_room_system_equipment',
        ['room_id', 'procurement_detail_id'],
        unique=True,
        postgresql_where=sa.text('procurement_detail_id IS NOT NULL')
    )


def downgrade():
    op.drop_index('uq_mrse_room_procurement_asset', table_name='maintenance_room_system_equipment')
    op.drop_index('uq_mrse_room_group_without_asset', table_name='maintenance_room_system_equipment')
    op.execute(
        'DELETE FROM maintenance_room_system_equipment '
        'WHERE procurement_detail_id IS NULL'
    )
    op.alter_column(
        'maintenance_room_system_equipment',
        'procurement_detail_id',
        existing_type=sa.Integer(),
        nullable=False
    )
