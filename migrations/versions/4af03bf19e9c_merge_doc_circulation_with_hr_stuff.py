"""merge doc circulation with HR stuff

Revision ID: 4af03bf19e9c
Revises: bc23388b34bd, afb505109941
Create Date: 2021-06-02 13:11:47.967544

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4af03bf19e9c'
down_revision = ('bc23388b34bd', 'afb505109941')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
