"""added note field

Revision ID: ff0fafc1a5a6
Revises: 8e5a223a6c67
Create Date: 2021-10-13 12:48:38.161100

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ff0fafc1a5a6'
down_revision = '8e5a223a6c67'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('doc_document_reaches', sa.Column('note', sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('doc_document_reaches', 'note')
    # ### end Alembic commands ###
