"""changed status field in the status model to string

Revision ID: 1e3c87ab5e70
Revises: 1a9deee603b9
Create Date: 2023-04-27 00:16:19.418796

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1e3c87ab5e70'
down_revision = '1a9deee603b9'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('complaint_statuses', 'status', type_=sa.String())


def downgrade():
    op.alter_column('complaint_statuses', 'status', type_=sa.Integer())
