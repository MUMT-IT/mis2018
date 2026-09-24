"""add ComHealth online-result access tokens

Revision ID: 6b81b393ec5a
Revises: 47d873dd8e77
Create Date: 2026-09-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '6b81b393ec5a'
down_revision = '47d873dd8e77'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'comhealth_online_result_access_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index(
        op.f('ix_comhealth_online_result_access_tokens_email'),
        'comhealth_online_result_access_tokens',
        ['email'],
        unique=False,
    )
    op.create_index(
        op.f('ix_comhealth_online_result_access_tokens_expires_at'),
        'comhealth_online_result_access_tokens',
        ['expires_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_comhealth_online_result_access_tokens_token_hash'),
        'comhealth_online_result_access_tokens',
        ['token_hash'],
        unique=True,
    )


def downgrade():
    op.drop_index(
        op.f('ix_comhealth_online_result_access_tokens_token_hash'),
        table_name='comhealth_online_result_access_tokens',
    )
    op.drop_index(
        op.f('ix_comhealth_online_result_access_tokens_expires_at'),
        table_name='comhealth_online_result_access_tokens',
    )
    op.drop_index(
        op.f('ix_comhealth_online_result_access_tokens_email'),
        table_name='comhealth_online_result_access_tokens',
    )
    op.drop_table('comhealth_online_result_access_tokens')
