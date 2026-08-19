"""add daily staff attendance snapshot

Revision ID: 9a7c2e1f4b6d
Revises: b7c8d9e0f1a2
Create Date: 2026-08-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '9a7c2e1f4b6d'
down_revision = 'b7c8d9e0f1a2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('staff_work_logins', sa.Column('request_id', sa.Integer(), nullable=True))
    op.add_column('staff_work_logins', sa.Column('approved_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_staff_work_logins_request_id',
        'staff_work_logins',
        'staff_request_work_logins',
        ['request_id'],
        ['id'],
    )
    op.create_foreign_key(
        'fk_staff_work_logins_approved_by_id',
        'staff_work_logins',
        'staff_account',
        ['approved_by_id'],
        ['id'],
    )

    op.create_table(
        'staff_daily_attendance',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('attendance_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('first_checkin_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_checkout_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(length=30), nullable=True),
        sa.Column('source_record_id', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('approved_by_id', sa.Integer(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['staff_id'], ['staff_account.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['staff_account.id']),
        sa.ForeignKeyConstraint(['approved_by_id'], ['staff_account.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('staff_id', 'attendance_date', name='uq_staff_daily_attendance_staff_date'),
    )
    op.create_index(
        'ix_staff_daily_attendance_date_status',
        'staff_daily_attendance',
        ['attendance_date', 'status'],
    )


def downgrade():
    op.drop_index('ix_staff_daily_attendance_date_status', table_name='staff_daily_attendance')
    op.drop_table('staff_daily_attendance')
    op.drop_constraint('fk_staff_work_logins_approved_by_id', 'staff_work_logins', type_='foreignkey')
    op.drop_constraint('fk_staff_work_logins_request_id', 'staff_work_logins', type_='foreignkey')
    op.drop_column('staff_work_logins', 'approved_by_id')
    op.drop_column('staff_work_logins', 'request_id')
