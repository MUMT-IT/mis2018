"""add semantic-search embeddings to FAQ questions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS vector')
        op.execute(
            'ALTER TABLE docs_query_faqs '
            'ADD COLUMN embedding vector(1024)'
        )
        op.execute(
            'CREATE INDEX ix_docs_query_faqs_embedding_hnsw '
            'ON docs_query_faqs USING hnsw (embedding vector_cosine_ops)'
        )
    else:
        op.add_column(
            'docs_query_faqs',
            sa.Column('embedding', sa.Text(), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('DROP INDEX IF EXISTS ix_docs_query_faqs_embedding_hnsw')
        op.execute('ALTER TABLE docs_query_faqs DROP COLUMN embedding')
    else:
        op.drop_column('docs_query_faqs', 'embedding')
