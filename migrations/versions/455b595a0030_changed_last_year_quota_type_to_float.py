"""changed last year quota type to Float

Revision ID: 455b595a0030
Revises: f36790081696
Create Date: 2020-06-30 10:50:17.296228

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '455b595a0030'
down_revision = 'f36790081696'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('staff_leave_remain_quota', 'last_year_quota', type_=sa.Float())


def downgrade():
    op.alter_column('staff_leave_remain_quota', 'last_year_quota', type_=sa.Integer())
