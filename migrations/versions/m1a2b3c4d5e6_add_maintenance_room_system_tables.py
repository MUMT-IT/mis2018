"""add maintenance room system tables

Revision ID: m1a2b3c4d5e6
Revises: 95198b79d094
Create Date: 2026-10-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm1a2b3c4d5e6'
down_revision = '95198b79d094'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'maintenance_room_systems',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.UniqueConstraint('name')
    )

    op.create_table(
        'maintenance_room_system_check_groups',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('system_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('can_bind_equipment', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(['system_id'], ['maintenance_room_systems.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_maintenance_room_system_check_groups_system_id',
        'maintenance_room_system_check_groups', ['system_id'], unique=False
    )

    op.create_table(
        'maintenance_room_system_check_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('check_group_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=500), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(
            ['check_group_id'], ['maintenance_room_system_check_groups.id']
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_maintenance_room_system_check_items_check_group_id',
        'maintenance_room_system_check_items', ['check_group_id'], unique=False
    )

    op.create_table(
        'maintenance_room_system_equipment',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('system_id', sa.Integer(), nullable=False),
        sa.Column('check_group_id', sa.Integer(), nullable=False),
        sa.Column('procurement_detail_id', sa.Integer(), nullable=True),
        sa.Column('room_equipment_id', sa.Integer(), nullable=True),
        sa.Column('display_name_override', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint(
            "(procurement_detail_id IS NOT NULL AND room_equipment_id IS NULL) OR "
            "(procurement_detail_id IS NULL AND room_equipment_id IS NOT NULL)",
            name='ck_maintenance_room_system_equipment_source'
        ),
        sa.ForeignKeyConstraint(['check_group_id'], ['maintenance_room_system_check_groups.id']),
        sa.ForeignKeyConstraint(['procurement_detail_id'], ['procurement_details.id']),
        sa.ForeignKeyConstraint(['room_equipment_id'], ['maintenance_room_equipment.id']),
        sa.ForeignKeyConstraint(['room_id'], ['scheduler_room_resources.id']),
        sa.ForeignKeyConstraint(['system_id'], ['maintenance_room_systems.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_maintenance_room_system_equipment_room_id', 'maintenance_room_system_equipment', ['room_id'], unique=False)
    op.create_index('ix_maintenance_room_system_equipment_system_id', 'maintenance_room_system_equipment', ['system_id'], unique=False)
    op.create_index('ix_maintenance_room_system_equipment_check_group_id', 'maintenance_room_system_equipment', ['check_group_id'], unique=False)
    op.create_index('ix_maintenance_room_system_equipment_procurement_detail_id', 'maintenance_room_system_equipment', ['procurement_detail_id'], unique=False)
    op.create_index('ix_maintenance_room_system_equipment_room_equipment_id', 'maintenance_room_system_equipment', ['room_equipment_id'], unique=False)
    op.execute("""
        CREATE TRIGGER trg_maintenance_room_system_equipment_updated_at
        BEFORE UPDATE ON maintenance_room_system_equipment
        FOR EACH ROW
        EXECUTE FUNCTION maintenance_set_updated_at()
    """)

    op.create_table(
        'maintenance_room_system_check_submissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('system_id', sa.Integer(), nullable=False),
        sa.Column('inspected_by_id', sa.Integer(), nullable=False),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['inspected_by_id'], ['staff_account.id']),
        sa.ForeignKeyConstraint(['room_id'], ['scheduler_room_resources.id']),
        sa.ForeignKeyConstraint(['system_id'], ['maintenance_room_systems.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_maintenance_room_system_check_submissions_room_id', 'maintenance_room_system_check_submissions', ['room_id'], unique=False)
    op.create_index('ix_maintenance_room_system_check_submissions_system_id', 'maintenance_room_system_check_submissions', ['system_id'], unique=False)
    op.create_index('ix_maintenance_room_system_check_submissions_inspected_by_id', 'maintenance_room_system_check_submissions', ['inspected_by_id'], unique=False)
    op.execute("""
        CREATE TRIGGER trg_maintenance_room_system_check_submissions_updated_at
        BEFORE UPDATE ON maintenance_room_system_check_submissions
        FOR EACH ROW
        EXECUTE FUNCTION maintenance_set_updated_at()
    """)

    op.create_table(
        'maintenance_room_system_check_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('check_item_id', sa.Integer(), nullable=False),
        sa.Column('is_checked', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['check_item_id'], ['maintenance_room_system_check_items.id']),
        sa.ForeignKeyConstraint(['submission_id'], ['maintenance_room_system_check_submissions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'submission_id', 'check_item_id',
            name='uq_maintenance_room_system_check_result_item'
        )
    )
    op.create_index('ix_maintenance_room_system_check_results_submission_id', 'maintenance_room_system_check_results', ['submission_id'], unique=False)
    op.create_index('ix_maintenance_room_system_check_results_check_item_id', 'maintenance_room_system_check_results', ['check_item_id'], unique=False)


def downgrade():
    op.drop_index('ix_maintenance_room_system_check_results_check_item_id', table_name='maintenance_room_system_check_results')
    op.drop_index('ix_maintenance_room_system_check_results_submission_id', table_name='maintenance_room_system_check_results')
    op.drop_table('maintenance_room_system_check_results')

    op.execute('DROP TRIGGER IF EXISTS trg_maintenance_room_system_check_submissions_updated_at ON maintenance_room_system_check_submissions')
    op.drop_index('ix_maintenance_room_system_check_submissions_inspected_by_id', table_name='maintenance_room_system_check_submissions')
    op.drop_index('ix_maintenance_room_system_check_submissions_system_id', table_name='maintenance_room_system_check_submissions')
    op.drop_index('ix_maintenance_room_system_check_submissions_room_id', table_name='maintenance_room_system_check_submissions')
    op.drop_table('maintenance_room_system_check_submissions')

    op.execute('DROP TRIGGER IF EXISTS trg_maintenance_room_system_equipment_updated_at ON maintenance_room_system_equipment')
    op.drop_index('ix_maintenance_room_system_equipment_room_equipment_id', table_name='maintenance_room_system_equipment')
    op.drop_index('ix_maintenance_room_system_equipment_procurement_detail_id', table_name='maintenance_room_system_equipment')
    op.drop_index('ix_maintenance_room_system_equipment_check_group_id', table_name='maintenance_room_system_equipment')
    op.drop_index('ix_maintenance_room_system_equipment_system_id', table_name='maintenance_room_system_equipment')
    op.drop_index('ix_maintenance_room_system_equipment_room_id', table_name='maintenance_room_system_equipment')
    op.drop_table('maintenance_room_system_equipment')

    op.drop_index('ix_maintenance_room_system_check_items_check_group_id', table_name='maintenance_room_system_check_items')
    op.drop_table('maintenance_room_system_check_items')

    op.drop_index('ix_maintenance_room_system_check_groups_system_id', table_name='maintenance_room_system_check_groups')
    op.drop_table('maintenance_room_system_check_groups')
    op.drop_table('maintenance_room_systems')
