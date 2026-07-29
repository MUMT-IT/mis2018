"""add document metadata to docs query

Revision ID: 3d5e7f8a9b10
Revises: 2c4d5e6f7a89
Create Date: 2026-07-29 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '3d5e7f8a9b10'
down_revision = '2c4d5e6f7a89'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('docs_query_documents', sa.Column('tags', sa.JSON(), nullable=True))
    op.add_column('docs_query_documents', sa.Column('note', sa.Text(), nullable=True))
    op.add_column('docs_query_documents', sa.Column('is_expired', sa.Boolean(), nullable=True))

    op.execute("UPDATE docs_query_documents SET tags = '[]' WHERE tags IS NULL")
    op.execute("UPDATE docs_query_documents SET is_expired = FALSE WHERE is_expired IS NULL")

    with op.batch_alter_table('docs_query_documents', schema=None) as batch_op:
        batch_op.alter_column('tags', existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column('is_expired', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_index(
            batch_op.f('ix_docs_query_documents_is_expired'),
            ['is_expired'],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table('docs_query_documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_docs_query_documents_is_expired'))

    op.drop_column('docs_query_documents', 'is_expired')
    op.drop_column('docs_query_documents', 'note')
    op.drop_column('docs_query_documents', 'tags')
