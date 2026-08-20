"""add FAQ creator metadata and SQLAlchemy-Continuum audit history

Revision ID: a1b2c3d4e5f6
Revises: 9d0e1f2a3b45
Create Date: 2026-08-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '9d0e1f2a3b45'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('docs_query_faqs', sa.Column('creator_name', sa.String(length=255), nullable=True))
    op.add_column('docs_query_faqs', sa.Column('editor_name', sa.String(length=255), nullable=True))
    op.add_column('docs_query_faqs', sa.Column('create_datetime', sa.DateTime(timezone=True), nullable=True))
    op.add_column('docs_query_faqs', sa.Column('edit_datetime', sa.DateTime(timezone=True), nullable=True))

    # Existing FAQ rows predate creator metadata. Use a neutral value and the
    # migration time so the new non-null model contract is safe for old data.
    op.execute("""
        UPDATE docs_query_faqs
        SET creator_name = COALESCE(creator_name, 'ระบบเดิม'),
            editor_name = COALESCE(editor_name, 'ระบบเดิม'),
            create_datetime = COALESCE(create_datetime, CURRENT_TIMESTAMP),
            edit_datetime = COALESCE(edit_datetime, CURRENT_TIMESTAMP)
    """)
    op.alter_column('docs_query_faqs', 'creator_name', nullable=False)
    op.alter_column('docs_query_faqs', 'editor_name', nullable=False)
    op.alter_column('docs_query_faqs', 'create_datetime', nullable=False)
    op.alter_column('docs_query_faqs', 'edit_datetime', nullable=False)
    op.drop_column('docs_query_faqs', 'created_at')
    op.drop_column('docs_query_faqs', 'updated_at')

    op.create_table(
        'transaction',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('issued_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'docs_query_faqs_version',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question', sa.Text(), nullable=True),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('creator_name', sa.String(length=255), nullable=True),
        sa.Column('editor_name', sa.String(length=255), nullable=True),
        sa.Column('create_datetime', sa.DateTime(timezone=True), nullable=True),
        sa.Column('edit_datetime', sa.DateTime(timezone=True), nullable=True),
        sa.Column('transaction_id', sa.BigInteger(), nullable=False),
        sa.Column('end_transaction_id', sa.BigInteger(), nullable=True),
        sa.Column('operation_type', sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(['transaction_id'], ['transaction.id']),
        sa.ForeignKeyConstraint(['end_transaction_id'], ['transaction.id']),
        sa.PrimaryKeyConstraint('id', 'transaction_id'),
    )
    op.create_index(
        'ix_docs_query_faqs_version_transaction_id',
        'docs_query_faqs_version',
        ['transaction_id'],
    )
    op.create_index(
        'ix_docs_query_faqs_version_end_transaction_id',
        'docs_query_faqs_version',
        ['end_transaction_id'],
    )
    op.create_index(
        'ix_docs_query_faqs_version_operation_type',
        'docs_query_faqs_version',
        ['operation_type'],
    )


def downgrade():
    op.drop_index('ix_docs_query_faqs_version_operation_type', table_name='docs_query_faqs_version')
    op.drop_index('ix_docs_query_faqs_version_end_transaction_id', table_name='docs_query_faqs_version')
    op.drop_index('ix_docs_query_faqs_version_transaction_id', table_name='docs_query_faqs_version')
    op.drop_table('docs_query_faqs_version')
    op.drop_table('transaction')
    op.drop_column('docs_query_faqs', 'edit_datetime')
    op.drop_column('docs_query_faqs', 'create_datetime')
    op.drop_column('docs_query_faqs', 'editor_name')
    op.drop_column('docs_query_faqs', 'creator_name')
    op.add_column('docs_query_faqs', sa.Column('created_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('docs_query_faqs', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
