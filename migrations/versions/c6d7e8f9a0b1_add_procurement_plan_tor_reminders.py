"""Add procurement plan TOR reminder log

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
"""
from alembic import op
import sqlalchemy as sa


revision = 'c6d7e8f9a0b1'
down_revision = 'b5c6d7e8f9a0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'procurement_plan_tor_reminders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_by_id', sa.Integer(), nullable=True),
        sa.Column('recipients_count', sa.Integer(), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('tor_due_date', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['procurement_plans.id']),
        sa.ForeignKeyConstraint(['sent_by_id'], ['staff_account.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_procurement_plan_tor_reminders_plan_id',
                    'procurement_plan_tor_reminders', ['plan_id'])


def downgrade():
    op.drop_index('ix_procurement_plan_tor_reminders_plan_id', table_name='procurement_plan_tor_reminders')
    op.drop_table('procurement_plan_tor_reminders')
