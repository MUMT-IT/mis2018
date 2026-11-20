"""Add an optional operator to procurement plans."""
from alembic import op
import sqlalchemy as sa

revision = 'd1456789abcd'
down_revision = 'c03456789abc'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('procurement_plans', sa.Column('operator_staff_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_procurement_plan_operator_staff', 'procurement_plans',
                          'staff_account', ['operator_staff_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_procurement_plan_operator_staff', 'procurement_plans', type_='foreignkey')
    op.drop_column('procurement_plans', 'operator_staff_id')
