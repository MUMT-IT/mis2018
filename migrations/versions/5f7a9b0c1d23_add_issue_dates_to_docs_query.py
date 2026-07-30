"""add issue dates to docs query documents

Revision ID: 5f7a9b0c1d23
Revises: 4e6f8a9b0c12
Create Date: 2026-07-30 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '5f7a9b0c1d23'
down_revision = '4e6f8a9b0c12'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('docs_query_documents', sa.Column('issue_date', sa.Date(), nullable=True))
    op.add_column('docs_query_documents', sa.Column('issue_date_raw', sa.String(length=255), nullable=True))
    op.add_column('docs_query_documents', sa.Column('date_extraction_method', sa.String(length=32), nullable=True))
    op.add_column('docs_query_documents', sa.Column('date_extracted_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        'ix_docs_query_documents_issue_date',
        'docs_query_documents',
        ['issue_date'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_docs_query_documents_issue_date', table_name='docs_query_documents')
    op.drop_column('docs_query_documents', 'date_extracted_at')
    op.drop_column('docs_query_documents', 'date_extraction_method')
    op.drop_column('docs_query_documents', 'issue_date_raw')
    op.drop_column('docs_query_documents', 'issue_date')
