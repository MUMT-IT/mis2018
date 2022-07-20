"""changed note date type from string to text

Revision ID: 54b7a7ea651d
Revises: aefb45638b1e
Create Date: 2022-02-27 15:04:05.937323

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '54b7a7ea651d'
down_revision = 'aefb45638b1e'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('kpis', 'note', type_=sa.Text())


def downgrade():
    op.alter_column('kpis', 'note', type_=sa.String())
