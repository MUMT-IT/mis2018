"""add maintenance room equipment tables

Revision ID: b7a50d9c8e12
Revises: 33caa7a78fe2
Create Date: 2026-07-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7a50d9c8e12'
down_revision = '33caa7a78fe2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'maintenance_equipment_types',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    op.create_table(
        'maintenance_room_equipment',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('equipment_type_id', sa.Integer(), nullable=False),
        sa.Column('equipment_name', sa.String(length=255), nullable=False),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['equipment_type_id'], ['maintenance_equipment_types.id']),
        sa.ForeignKeyConstraint(['room_id'], ['scheduler_room_resources.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_maintenance_room_equipment_room_id',
        'maintenance_room_equipment',
        ['room_id'],
        unique=False
    )
    op.create_index(
        'ix_maintenance_room_equipment_equipment_type_id',
        'maintenance_room_equipment',
        ['equipment_type_id'],
        unique=False
    )
    op.execute("""
        CREATE FUNCTION maintenance_set_updated_at()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_maintenance_room_equipment_updated_at
        BEFORE UPDATE ON maintenance_room_equipment
        FOR EACH ROW
        EXECUTE FUNCTION maintenance_set_updated_at()
    """)


def downgrade():
    op.execute(
        'DROP TRIGGER IF EXISTS trg_maintenance_room_equipment_updated_at '
        'ON maintenance_room_equipment'
    )
    op.execute('DROP FUNCTION IF EXISTS maintenance_set_updated_at()')
    op.drop_index(
        'ix_maintenance_room_equipment_equipment_type_id',
        table_name='maintenance_room_equipment'
    )
    op.drop_index(
        'ix_maintenance_room_equipment_room_id',
        table_name='maintenance_room_equipment'
    )
    op.drop_table('maintenance_room_equipment')
    op.drop_table('maintenance_equipment_types')
