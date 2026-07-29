"""add ce_satisfaction_survey_access_tokens table

Revision ID: 9c8e7f42b2d1
Revises: 2d53c8a0b4f1
Create Date: 2026-02-26 13:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c8e7f42b2d1'
down_revision = '2d53c8a0b4f1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ce_satisfaction_survey_access_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('registration_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('event_entity_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['event_entity_id'], ['ce_event_entities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['ce_members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['registration_id'], ['ce_member_registrations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index(op.f('ix_ce_satisfaction_survey_access_tokens_registration_id'), 'ce_satisfaction_survey_access_tokens', ['registration_id'], unique=False)
    op.create_index(op.f('ix_ce_satisfaction_survey_access_tokens_member_id'), 'ce_satisfaction_survey_access_tokens', ['member_id'], unique=False)
    op.create_index(op.f('ix_ce_satisfaction_survey_access_tokens_event_entity_id'), 'ce_satisfaction_survey_access_tokens', ['event_entity_id'], unique=False)
    op.create_index(op.f('ix_ce_satisfaction_survey_access_tokens_token_hash'), 'ce_satisfaction_survey_access_tokens', ['token_hash'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_ce_satisfaction_survey_access_tokens_token_hash'), table_name='ce_satisfaction_survey_access_tokens')
    op.drop_index(op.f('ix_ce_satisfaction_survey_access_tokens_event_entity_id'), table_name='ce_satisfaction_survey_access_tokens')
    op.drop_index(op.f('ix_ce_satisfaction_survey_access_tokens_member_id'), table_name='ce_satisfaction_survey_access_tokens')
    op.drop_index(op.f('ix_ce_satisfaction_survey_access_tokens_registration_id'), table_name='ce_satisfaction_survey_access_tokens')
    op.drop_table('ce_satisfaction_survey_access_tokens')
