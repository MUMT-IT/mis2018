"""expand procurement erp_code length

Revision ID: a7f3c9d2e8b1
Revises: 6562a23dd94e
Create Date: 2026-05-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7f3c9d2e8b1'
down_revision = '6562a23dd94e'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'procurement_details',
        'erp_code',
        existing_type=sa.String(length=22),
        type_=sa.String(length=32),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        'procurement_details',
        'erp_code',
        existing_type=sa.String(length=32),
        type_=sa.String(length=22),
        existing_nullable=True,
    )
