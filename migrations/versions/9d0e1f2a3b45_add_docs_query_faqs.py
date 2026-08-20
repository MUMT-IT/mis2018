"""add FAQ entries to docs query

Revision ID: 9d0e1f2a3b45
Revises: 9a7c2e1f4b6d
Create Date: 2026-08-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '9d0e1f2a3b45'
down_revision = '9a7c2e1f4b6d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'docs_query_faqs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('docs_query_faqs')
