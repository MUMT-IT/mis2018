"""add Typhoon summaries to docs query documents

Revision ID: 7b9c0d1e2f34
Revises: 6a8b9c0d1e23
Create Date: 2026-08-01 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '7b9c0d1e2f34'
down_revision = '6a8b9c0d1e23'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('docs_query_documents', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column(
        'docs_query_documents',
        sa.Column('summary_generated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column('docs_query_documents', sa.Column('summary_error', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('docs_query_documents', 'summary_error')
    op.drop_column('docs_query_documents', 'summary_generated_at')
    op.drop_column('docs_query_documents', 'summary')
