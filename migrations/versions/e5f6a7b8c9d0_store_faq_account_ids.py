"""store FAQ creator and editor account IDs

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('docs_query_faqs', sa.Column('creator_id', sa.Integer(), nullable=True))
    op.add_column('docs_query_faqs', sa.Column('editor_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_docs_query_faqs_creator_id_staff_account',
        'docs_query_faqs', 'staff_account', ['creator_id'], ['id'],
    )
    op.create_foreign_key(
        'fk_docs_query_faqs_editor_id_staff_account',
        'docs_query_faqs', 'staff_account', ['editor_id'], ['id'],
    )
    op.add_column('docs_query_faqs_version', sa.Column('creator_id', sa.Integer(), nullable=True))
    op.add_column('docs_query_faqs_version', sa.Column('editor_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_docs_query_faqs_version_creator_id_staff_account',
        'docs_query_faqs_version', 'staff_account', ['creator_id'], ['id'],
    )
    op.create_foreign_key(
        'fk_docs_query_faqs_version_editor_id_staff_account',
        'docs_query_faqs_version', 'staff_account', ['editor_id'], ['id'],
    )
    op.drop_column('docs_query_faqs_version', 'editor_avatar_url')
    op.drop_column('docs_query_faqs_version', 'creator_avatar_url')
    op.drop_column('docs_query_faqs', 'editor_avatar_url')
    op.drop_column('docs_query_faqs', 'creator_avatar_url')


def downgrade():
    op.add_column('docs_query_faqs', sa.Column('creator_avatar_url', sa.String(length=1024), nullable=True))
    op.add_column('docs_query_faqs', sa.Column('editor_avatar_url', sa.String(length=1024), nullable=True))
    op.add_column('docs_query_faqs_version', sa.Column('creator_avatar_url', sa.String(length=1024), nullable=True))
    op.add_column('docs_query_faqs_version', sa.Column('editor_avatar_url', sa.String(length=1024), nullable=True))
    op.drop_constraint('fk_docs_query_faqs_version_editor_id_staff_account', 'docs_query_faqs_version', type_='foreignkey')
    op.drop_constraint('fk_docs_query_faqs_version_creator_id_staff_account', 'docs_query_faqs_version', type_='foreignkey')
    op.drop_column('docs_query_faqs_version', 'editor_id')
    op.drop_column('docs_query_faqs_version', 'creator_id')
    op.drop_constraint('fk_docs_query_faqs_editor_id_staff_account', 'docs_query_faqs', type_='foreignkey')
    op.drop_constraint('fk_docs_query_faqs_creator_id_staff_account', 'docs_query_faqs', type_='foreignkey')
    op.drop_column('docs_query_faqs', 'editor_id')
    op.drop_column('docs_query_faqs', 'creator_id')
