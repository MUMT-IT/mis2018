"""added scopus link and publication name fields

Revision ID: 6f31d823928e
Revises: 8041def1e1ef
Create Date: 2020-11-09 05:27:21.304325

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f31d823928e'
down_revision = '8041def1e1ef'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('research_pub', sa.Column('publication_name', sa.String(), nullable=True))
    op.add_column('research_pub', sa.Column('scopus_link', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('research_pub', 'scopus_link')
    op.drop_column('research_pub', 'publication_name')
    # ### end Alembic commands ###
