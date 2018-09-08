"""changed varchar size of the name field of the subdistrict model

Revision ID: d3faa3475522
Revises: fb7910f29cba
Create Date: 2018-01-24 08:23:25.061830

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3faa3475522'
down_revision = 'fb7910f29cba'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('subdistricts', 'name', type_=sa.String(80))


def downgrade():
    op.alter_column('subdistricts', 'name', type_=sa.String(40))
