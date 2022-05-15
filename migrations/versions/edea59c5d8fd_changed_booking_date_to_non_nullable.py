"""changed booking date to non-nullable

Revision ID: edea59c5d8fd
Revises: 55b3ae10b1f9
Create Date: 2022-02-28 08:00:38.738936

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'edea59c5d8fd'
down_revision = '55b3ae10b1f9'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('tracker_accounts', 'booking_date', nullable=False)


def downgrade():
    op.alter_column('tracker_accounts', 'booking_date', nullable=True)
