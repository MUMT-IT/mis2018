"""Link BestTime polls to procurement plans

Revision ID: 0a1b2c3d4e5f
Revises: f9a0b1c2d3e4
"""
from alembic import op
import sqlalchemy as sa


revision = '0a1b2c3d4e5f'
down_revision = 'f9a0b1c2d3e4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'besttime_polls',
        sa.Column('procurement_plan_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_besttime_polls_procurement_plan_id',
        'besttime_polls',
        'procurement_plans',
        ['procurement_plan_id'],
        ['id'],
    )


def downgrade():
    op.drop_constraint(
        'fk_besttime_polls_procurement_plan_id',
        'besttime_polls',
        type_='foreignkey',
    )
    op.drop_column('besttime_polls', 'procurement_plan_id')
