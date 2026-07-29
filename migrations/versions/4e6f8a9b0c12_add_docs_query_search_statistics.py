"""add docs query search statistics

Revision ID: 4e6f8a9b0c12
Revises: 3d5e7f8a9b10
Create Date: 2026-07-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '4e6f8a9b0c12'
down_revision = '3d5e7f8a9b10'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'docs_query_searches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('query_text', sa.String(length=1000), nullable=False),
        sa.Column('result_count', sa.Integer(), nullable=False),
        sa.Column('related_document_count', sa.Integer(), nullable=False),
        sa.Column('search_method', sa.String(length=32), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_docs_query_searches_created_at',
        'docs_query_searches',
        ['created_at'],
        unique=False,
    )
    op.create_table(
        'docs_query_clicks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('search_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['docs_query_documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['search_id'], ['docs_query_searches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_docs_query_clicks_search_id', 'docs_query_clicks', ['search_id'], unique=False)
    op.create_index('ix_docs_query_clicks_document_id', 'docs_query_clicks', ['document_id'], unique=False)
    op.create_index('ix_docs_query_clicks_clicked_at', 'docs_query_clicks', ['clicked_at'], unique=False)


def downgrade():
    op.drop_index('ix_docs_query_clicks_clicked_at', table_name='docs_query_clicks')
    op.drop_index('ix_docs_query_clicks_document_id', table_name='docs_query_clicks')
    op.drop_index('ix_docs_query_clicks_search_id', table_name='docs_query_clicks')
    op.drop_table('docs_query_clicks')
    op.drop_index('ix_docs_query_searches_created_at', table_name='docs_query_searches')
    op.drop_table('docs_query_searches')
