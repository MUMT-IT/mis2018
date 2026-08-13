"""normalize docs query tags into a many-to-many relationship

Revision ID: 6a8b9c0d1e23
Revises: 5f7a9b0c1d23
Create Date: 2026-08-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '6a8b9c0d1e23'
down_revision = '5f7a9b0c1d23'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'docs_query_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index(
        'ix_docs_query_tags_name',
        'docs_query_tags',
        ['name'],
        unique=False,
    )
    op.create_table(
        'docs_query_document_tags',
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['document_id'],
            ['docs_query_documents.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['tag_id'],
            ['docs_query_tags.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('document_id', 'tag_id'),
    )
    op.create_index(
        'ix_docs_query_document_tags_tag_id',
        'docs_query_document_tags',
        ['tag_id'],
        unique=False,
    )

    # Preserve the existing JSON tag arrays before removing the old column.
    op.execute(sa.text("""
        INSERT INTO docs_query_tags (name)
        SELECT DISTINCT trim(tag_name)
        FROM docs_query_documents AS document
        CROSS JOIN LATERAL json_array_elements_text(
            COALESCE(document.tags, '[]'::json)
        ) AS tag_values(tag_name)
        WHERE trim(tag_name) <> ''
        ON CONFLICT (name) DO NOTHING
    """))
    op.execute(sa.text("""
        INSERT INTO docs_query_document_tags (document_id, tag_id)
        SELECT DISTINCT document.id, tag.id
        FROM docs_query_documents AS document
        CROSS JOIN LATERAL json_array_elements_text(
            COALESCE(document.tags, '[]'::json)
        ) AS tag_values(tag_name)
        JOIN docs_query_tags AS tag ON tag.name = trim(tag_values.tag_name)
        ON CONFLICT (document_id, tag_id) DO NOTHING
    """))
    op.drop_column('docs_query_documents', 'tags')


def downgrade():
    op.add_column(
        'docs_query_documents',
        sa.Column('tags', sa.JSON(), nullable=True),
    )
    op.execute(sa.text("""
        UPDATE docs_query_documents AS document
        SET tags = COALESCE(
            (
                SELECT json_agg(tag.name ORDER BY tag.name)
                FROM docs_query_document_tags AS document_tag
                JOIN docs_query_tags AS tag ON tag.id = document_tag.tag_id
                WHERE document_tag.document_id = document.id
            ),
            '[]'::json
        )
    """))
    op.alter_column(
        'docs_query_documents',
        'tags',
        existing_type=sa.JSON(),
        nullable=False,
    )
    op.drop_index(
        'ix_docs_query_document_tags_tag_id',
        table_name='docs_query_document_tags',
    )
    op.drop_table('docs_query_document_tags')
    op.drop_index('ix_docs_query_tags_name', table_name='docs_query_tags')
    op.drop_table('docs_query_tags')
