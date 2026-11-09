"""add room system check equipment snapshots

Revision ID: m5e6f7g8h9i0
Revises: m4d5e6f7g8h9
Create Date: 2026-10-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'm5e6f7g8h9i0'
down_revision = 'm4d5e6f7g8h9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'maintenance_room_system_check_submission_equipment',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('check_group_id', sa.Integer(), nullable=False),
        sa.Column('procurement_detail_id', sa.Integer(), nullable=True),
        sa.Column('erp_code_snapshot', sa.String(length=32), nullable=True),
        sa.Column('item_name_snapshot', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['submission_id'], ['maintenance_room_system_check_submissions.id']),
        sa.ForeignKeyConstraint(['check_group_id'], ['maintenance_room_system_check_groups.id']),
        sa.ForeignKeyConstraint(['procurement_detail_id'], ['procurement_details.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_mrscse_submission_id',
        'maintenance_room_system_check_submission_equipment', ['submission_id'], unique=False
    )
    op.create_index(
        'ix_mrscse_check_group_id',
        'maintenance_room_system_check_submission_equipment', ['check_group_id'], unique=False
    )
    op.create_index(
        'ix_mrscse_procurement_detail_id',
        'maintenance_room_system_check_submission_equipment', ['procurement_detail_id'], unique=False
    )
    op.create_index(
        'ix_mrscse_erp_code_snapshot',
        'maintenance_room_system_check_submission_equipment', ['erp_code_snapshot'], unique=False
    )


def downgrade():
    op.drop_index('ix_mrscse_erp_code_snapshot', table_name='maintenance_room_system_check_submission_equipment')
    op.drop_index('ix_mrscse_procurement_detail_id', table_name='maintenance_room_system_check_submission_equipment')
    op.drop_index('ix_mrscse_check_group_id', table_name='maintenance_room_system_check_submission_equipment')
    op.drop_index('ix_mrscse_submission_id', table_name='maintenance_room_system_check_submission_equipment')
    op.drop_table('maintenance_room_system_check_submission_equipment')
