"""Create short URL mappings.

Revision ID: f1a2b3c4d5e6
Revises: e0d5c6b7a8f9
"""

from alembic import op
import sqlalchemy as sa


revision = 'f1a2b3c4d5e6'
down_revision = 'e0d5c6b7a8f9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'shorturl_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('short_code', sa.String(length=32), nullable=False),
        sa.Column('long_url', sa.Text(), nullable=False),
        sa.Column('click_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('staff_account_id', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['staff_account_id'], ['staff_account.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('short_code'),
    )
    op.create_index('ix_shorturl_mappings_created_at', 'shorturl_mappings', ['created_at'], unique=False)
    op.create_index('ix_shorturl_mappings_staff_account_id', 'shorturl_mappings', ['staff_account_id'], unique=False)
    op.create_index('ix_shorturl_mappings_expires_at', 'shorturl_mappings', ['expires_at'], unique=False)


def downgrade():
    op.drop_index('ix_shorturl_mappings_expires_at', table_name='shorturl_mappings')
    op.drop_index('ix_shorturl_mappings_staff_account_id', table_name='shorturl_mappings')
    op.drop_index('ix_shorturl_mappings_created_at', table_name='shorturl_mappings')
    op.drop_table('shorturl_mappings')
