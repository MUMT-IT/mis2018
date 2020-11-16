"""changed a string of country ID to an autoincremental integer

Revision ID: dbdd19e00c5e
Revises: 9ec148b999a9
Create Date: 2020-11-06 16:36:44.478219

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dbdd19e00c5e'
down_revision = '9ec148b999a9'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('research_affils_country_id_fkey', 'research_affils', type_='foreignkey')
    op.execute("ALTER TABLE research_affils ALTER COLUMN country_id"
               " TYPE INTEGER USING id::INTEGER")
    op.execute("ALTER TABLE research_countries ALTER COLUMN id"
               " TYPE INTEGER USING id::INTEGER")
    op.create_foreign_key('research_affils_country_id_fkey',
                          'research_affils', 'research_countries', ['country_id'], ['id'])


def downgrade():
    op.drop_contraint('research_affils_country_id_fkey', 'research_affils', type_='foreignkey')
    op.execute("ALTER TABLE research_affils ALTER COLUMN id"
               " TYPE INTEGER USING id::VARCHAR(128)")
    op.execute("ALTER TABLE research_countries ALTER COLUMN id"
               " TYPE INTEGER USING id::VARCHAR(128)")
    op.create_foreign_key('research_affils_country_id_fkey',
                          'research_affils', 'research_countries', ['country_id'], ['id'])
