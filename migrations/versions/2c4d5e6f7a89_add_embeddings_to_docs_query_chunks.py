"""add embeddings to docs query chunks

Revision ID: 2c4d5e6f7a89
Revises: f9e48eb8988f
Create Date: 2026-07-29 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '2c4d5e6f7a89'
down_revision = 'f9e48eb8988f'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS vector')
        op.execute(
            'ALTER TABLE docs_query_chunks '
            'ADD COLUMN embedding vector(1024)'
        )
        op.execute(
            'CREATE INDEX ix_docs_query_chunks_embedding_hnsw '
            'ON docs_query_chunks USING hnsw (embedding vector_cosine_ops)'
        )
    else:
        # Keep local SQLite development databases migratable. Semantic search
        # is enabled only when PostgreSQL/pgvector is available.
        op.add_column(
            'docs_query_chunks',
            sa.Column('embedding', sa.Text(), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('DROP INDEX IF EXISTS ix_docs_query_chunks_embedding_hnsw')
        op.execute('ALTER TABLE docs_query_chunks DROP COLUMN embedding')
    else:
        op.drop_column('docs_query_chunks', 'embedding')
