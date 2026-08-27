"""Add procurement planning, funding source, and vendor models

Revision ID: 7c1d2e3f4a5b
Revises: f6a7b8c9d0e1
"""
from alembic import op
import sqlalchemy as sa


revision = '7c1d2e3f4a5b'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'procurement_funding_sources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'procurement_vendors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('tax_id', sa.String(length=32), nullable=True),
        sa.Column('branch_name', sa.String(length=255), nullable=True),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=64), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tax_id'),
    )
    op.create_table(
        'procurement_plans',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('funding_source_id', sa.Integer(), nullable=False),
        sa.Column('output_project_report', sa.Text(), nullable=False),
        sa.Column('cost_center_id', sa.String(length=12), nullable=False),
        sa.Column('procurement_method', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('fund_code', sa.String(length=64), nullable=True),
        sa.Column('responsible_staff_id', sa.Integer(), nullable=False),
        sa.Column('vendor_id', sa.Integer(), nullable=True),
        sa.Column('procurement_detail_id', sa.Integer(), nullable=True),
        sa.Column('principle_approval_date', sa.Date(), nullable=True),
        sa.Column('tor_completed_date', sa.Date(), nullable=True),
        sa.Column('quotation_submission_date', sa.Date(), nullable=True),
        sa.Column('contract_signed_date', sa.Date(), nullable=True),
        sa.Column('inspection_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=64), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['cost_center_id'], ['cost_centers.id']),
        sa.ForeignKeyConstraint(['funding_source_id'], ['procurement_funding_sources.id']),
        sa.ForeignKeyConstraint(['procurement_detail_id'], ['procurement_details.id']),
        sa.ForeignKeyConstraint(['responsible_staff_id'], ['staff_account.id']),
        sa.ForeignKeyConstraint(['vendor_id'], ['procurement_vendors.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_procurement_plans_fiscal_year', 'procurement_plans', ['fiscal_year'])
    op.create_index('ix_procurement_plans_status', 'procurement_plans', ['status'])
    op.create_table(
        'procurement_plan_activities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('activity_type', sa.String(length=128), nullable=False),
        sa.Column('activity_date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['procurement_plans.id']),
        sa.ForeignKeyConstraint(['updated_by_id'], ['staff_account.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_procurement_plan_activities_plan_id', 'procurement_plan_activities', ['plan_id'])


def downgrade():
    op.drop_index('ix_procurement_plan_activities_plan_id', table_name='procurement_plan_activities')
    op.drop_table('procurement_plan_activities')
    op.drop_index('ix_procurement_plans_status', table_name='procurement_plans')
    op.drop_index('ix_procurement_plans_fiscal_year', table_name='procurement_plans')
    op.drop_table('procurement_plans')
    op.drop_table('procurement_vendors')
    op.drop_table('procurement_funding_sources')
