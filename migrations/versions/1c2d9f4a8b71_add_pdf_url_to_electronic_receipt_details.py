"""add pdf_url to electronic_receipt_details

Revision ID: 1c2d9f4a8b71
Revises: 7b0d1f6c2a9e
Create Date: 2026-05-30 13:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1c2d9f4a8b71'
down_revision = '7b0d1f6c2a9e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('electronic_receipt_details', sa.Column('pdf_url', sa.String(), nullable=True))


def downgrade():
    op.drop_column('electronic_receipt_details', 'pdf_url')
