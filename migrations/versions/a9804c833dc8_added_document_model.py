"""added document model

Revision ID: a9804c833dc8
Revises: ebe9c3a17077
Create Date: 2021-05-18 02:29:45.084078

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9804c833dc8'
down_revision = 'ebe9c3a17077'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('doc_categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('doc_documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('round_id', sa.Integer(), nullable=True),
    sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
    sa.Column('addedAt', sa.DateTime(timezone=True), nullable=True),
    sa.Column('url', sa.String(length=255), nullable=True),
    sa.Column('priority', sa.String(length=255), nullable=True),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['doc_categories.id'], ),
    sa.ForeignKeyConstraint(['round_id'], ['doc_rounds.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('doc_documents')
    op.drop_table('doc_categories')
    # ### end Alembic commands ###
