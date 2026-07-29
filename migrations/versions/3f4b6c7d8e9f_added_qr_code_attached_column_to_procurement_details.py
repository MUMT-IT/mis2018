"""added qr_code_attached column to procurement_details

Revision ID: 3f4b6c7d8e9f
Revises: d655065274c1
Create Date: 2026-06-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3f4b6c7d8e9f'
down_revision = 'd655065274c1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'procurement_details',
        sa.Column('qr_code_attached', sa.Boolean(), nullable=False, server_default=sa.false())
    )


def downgrade():
    op.drop_column('procurement_details', 'qr_code_attached')
