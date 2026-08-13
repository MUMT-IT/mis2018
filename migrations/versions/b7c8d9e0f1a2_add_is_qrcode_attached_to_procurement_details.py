"""Add is_qrcode_attached to procurement_details.

Revision ID: b7c8d9e0f1a2
Revises: 9a7e2d4c1f60
Create Date: 2026-08-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c8d9e0f1a2'
down_revision = '9a7e2d4c1f60'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'procurement_details',
        sa.Column(
            'is_qrcode_attached',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_column('procurement_details', 'is_qrcode_attached')
