"""added stage field to the document model

Revision ID: a858e3ab5ed7
Revises: e38783b106a3
Create Date: 2021-05-19 02:46:00.097852

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a858e3ab5ed7'
down_revision = 'e38783b106a3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('doc_documents', sa.Column('stage', sa.String(length=255), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('doc_documents', 'stage')
    # ### end Alembic commands ###
