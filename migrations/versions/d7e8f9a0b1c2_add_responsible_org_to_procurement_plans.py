"""Add responsible organization to procurement plans

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
"""
from alembic import op
import sqlalchemy as sa


revision = 'd7e8f9a0b1c2'
down_revision = 'c6d7e8f9a0b1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('procurement_plans', sa.Column('responsible_org_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_procurement_plans_responsible_org_id_orgs',
        'procurement_plans', 'orgs',
        ['responsible_org_id'], ['id']
    )


def downgrade():
    op.drop_constraint(
        'fk_procurement_plans_responsible_org_id_orgs',
        'procurement_plans', type_='foreignkey'
    )
    op.drop_column('procurement_plans', 'responsible_org_id')
