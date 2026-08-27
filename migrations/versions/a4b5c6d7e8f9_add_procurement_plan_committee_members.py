"""Add procurement plan committee members

Revision ID: a4b5c6d7e8f9
Revises: 9e3f4a5b6c7d
"""
from alembic import op
import sqlalchemy as sa


revision = 'a4b5c6d7e8f9'
down_revision = '9e3f4a5b6c7d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'procurement_plan_committee_members',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['procurement_plans.id']),
        sa.ForeignKeyConstraint(['staff_id'], ['staff_account.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_id', 'staff_id', name='uq_procurement_plan_committee_member'),
    )
    op.create_index(
        'ix_procurement_plan_committee_members_plan_id',
        'procurement_plan_committee_members',
        ['plan_id'],
    )


def downgrade():
    op.drop_index(
        'ix_procurement_plan_committee_members_plan_id',
        table_name='procurement_plan_committee_members',
    )
    op.drop_table('procurement_plan_committee_members')
