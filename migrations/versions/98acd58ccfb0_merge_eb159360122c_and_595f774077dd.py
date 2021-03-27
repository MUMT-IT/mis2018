"""merge eb159360122c and 595f774077dd

Revision ID: 98acd58ccfb0
Revises: 595f774077dd, eb159360122c
Create Date: 2021-03-27 09:16:48.057443

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '98acd58ccfb0'
down_revision = ('595f774077dd', 'eb159360122c')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
