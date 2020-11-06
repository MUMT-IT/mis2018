"""added autoincrement to the country ID field

Revision ID: eaa4f4fd6100
Revises: 21cd1facad8a
Create Date: 2020-11-06 18:25:53.375181

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eaa4f4fd6100'
down_revision = '21cd1facad8a'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SEQUENCE research_countries_id_seq")
    op.execute("ALTER TABLE research_countries ALTER COLUMN id "
               "SET DEFAULT nextval('research_countries_id_seq'::regclass)")


def downgrade():
    op.execute("DROP SEQUENCE research_countries_id_seq")
    op.execute("ALTER TABLE research_countries ALTER COLUMN id "
               "SET DEFAULT NULL")