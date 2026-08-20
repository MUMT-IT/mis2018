"""add FAQ creator and editor avatar snapshots

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('docs_query_faqs', sa.Column('creator_avatar_url', sa.String(length=1024), nullable=True))
    op.add_column('docs_query_faqs', sa.Column('editor_avatar_url', sa.String(length=1024), nullable=True))
    op.add_column('docs_query_faqs_version', sa.Column('creator_avatar_url', sa.String(length=1024), nullable=True))
    op.add_column('docs_query_faqs_version', sa.Column('editor_avatar_url', sa.String(length=1024), nullable=True))


def downgrade():
    op.drop_column('docs_query_faqs_version', 'editor_avatar_url')
    op.drop_column('docs_query_faqs_version', 'creator_avatar_url')
    op.drop_column('docs_query_faqs', 'editor_avatar_url')
    op.drop_column('docs_query_faqs', 'creator_avatar_url')
