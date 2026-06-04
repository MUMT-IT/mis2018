"""placeholder migration for procurement_details image column

Revision ID: 7b0d1f6c2a9e
Revises: 49b45fefcab4
Create Date: 2026-05-30 12:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b0d1f6c2a9e'
down_revision = '49b45fefcab4'
branch_labels = None
depends_on = None


def upgrade():
    # Keep the legacy column until data migration to S3 is fully complete.
    pass


def downgrade():
    pass
