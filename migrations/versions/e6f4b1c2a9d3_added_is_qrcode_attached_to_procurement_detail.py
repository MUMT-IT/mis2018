"""Added is_qrcode_attached to ProcurementDetail

Revision ID: e6f4b1c2a9d3
Revises: d4c1a9e2f630
Create Date: 2026-05-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6f4b1c2a9d3'
down_revision = 'd4c1a9e2f630'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'procurement_details',
        sa.Column(
            'is_qrcode_attached',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false()
        )
    )
    op.alter_column('procurement_details', 'is_qrcode_attached', server_default=None)


def downgrade():
    op.drop_column('procurement_details', 'is_qrcode_attached')
