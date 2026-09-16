"""add budget proposer to procurement plans

Revision ID: aa912e7104d8
Revises: 6b81b393ec5a
Create Date: 2026-09-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'aa912e7104d8'
down_revision = '6b81b393ec5a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'procurement_plans',
        sa.Column('budget_proposer_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_procurement_plans_budget_proposer_id_staff_account',
        'procurement_plans',
        'staff_account',
        ['budget_proposer_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade():
    op.drop_constraint(
        'fk_procurement_plans_budget_proposer_id_staff_account',
        'procurement_plans',
        type_='foreignkey',
    )
    op.drop_column('procurement_plans', 'budget_proposer_id')
