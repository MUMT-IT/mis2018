"""add maintenance inspection tables

Revision ID: c4d7a8e1f2b3
Revises: b7a50d9c8e12
Create Date: 2026-07-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d7a8e1f2b3'
down_revision = 'b7a50d9c8e12'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'maintenance_inspection_submissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('submitted_by_id', sa.Integer(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['room_id'], ['scheduler_room_resources.id']),
        sa.ForeignKeyConstraint(['submitted_by_id'], ['staff_account.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_maintenance_inspection_submissions_room_id',
        'maintenance_inspection_submissions', ['room_id'], unique=False
    )
    op.create_index(
        'ix_maintenance_inspection_submissions_submitted_by_id',
        'maintenance_inspection_submissions', ['submitted_by_id'], unique=False
    )
    op.execute("""
        CREATE TRIGGER trg_maintenance_inspection_submissions_updated_at
        BEFORE UPDATE ON maintenance_inspection_submissions
        FOR EACH ROW
        EXECUTE FUNCTION maintenance_set_updated_at()
    """)

    op.create_table(
        'maintenance_inspection_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('procurement_detail_id', sa.Integer(), nullable=True),
        sa.Column('room_equipment_id', sa.Integer(), nullable=True),
        sa.Column('inspector_id', sa.Integer(), nullable=False),
        sa.Column('result', sa.String(length=16), nullable=False),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('equipment_name_snapshot', sa.String(length=255), nullable=False),
        sa.Column('equipment_type_snapshot', sa.String(length=100), nullable=False),
        sa.Column('erp_code_snapshot', sa.String(length=32), nullable=True),
        sa.Column('serial_number_snapshot', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint(
            "(procurement_detail_id IS NOT NULL AND room_equipment_id IS NULL) OR "
            "(procurement_detail_id IS NULL AND room_equipment_id IS NOT NULL)",
            name='ck_maintenance_inspection_item_equipment_source'
        ),
        sa.CheckConstraint(
            "result IN ('normal', 'issue')",
            name='ck_maintenance_inspection_item_result'
        ),
        sa.CheckConstraint(
            "result <> 'issue' OR (remark IS NOT NULL AND btrim(remark) <> '')",
            name='ck_maintenance_inspection_item_issue_remark'
        ),
        sa.ForeignKeyConstraint(['inspector_id'], ['staff_account.id']),
        sa.ForeignKeyConstraint(['procurement_detail_id'], ['procurement_details.id']),
        sa.ForeignKeyConstraint(['room_equipment_id'], ['maintenance_room_equipment.id']),
        sa.ForeignKeyConstraint(['submission_id'], ['maintenance_inspection_submissions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_maintenance_inspection_items_submission_id',
        'maintenance_inspection_items', ['submission_id'], unique=False
    )
    op.create_index(
        'ix_maintenance_inspection_items_procurement_detail_id',
        'maintenance_inspection_items', ['procurement_detail_id'], unique=False
    )
    op.create_index(
        'ix_maintenance_inspection_items_room_equipment_id',
        'maintenance_inspection_items', ['room_equipment_id'], unique=False
    )
    op.create_index(
        'ix_maintenance_inspection_items_inspector_id',
        'maintenance_inspection_items', ['inspector_id'], unique=False
    )


def downgrade():
    op.drop_index('ix_maintenance_inspection_items_inspector_id', table_name='maintenance_inspection_items')
    op.drop_index('ix_maintenance_inspection_items_room_equipment_id', table_name='maintenance_inspection_items')
    op.drop_index('ix_maintenance_inspection_items_procurement_detail_id', table_name='maintenance_inspection_items')
    op.drop_index('ix_maintenance_inspection_items_submission_id', table_name='maintenance_inspection_items')
    op.drop_table('maintenance_inspection_items')
    op.execute(
        'DROP TRIGGER IF EXISTS trg_maintenance_inspection_submissions_updated_at '
        'ON maintenance_inspection_submissions'
    )
    op.drop_index(
        'ix_maintenance_inspection_submissions_submitted_by_id',
        table_name='maintenance_inspection_submissions'
    )
    op.drop_index(
        'ix_maintenance_inspection_submissions_room_id',
        table_name='maintenance_inspection_submissions'
    )
    op.drop_table('maintenance_inspection_submissions')
