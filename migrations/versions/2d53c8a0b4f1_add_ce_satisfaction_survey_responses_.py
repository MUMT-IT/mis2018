"""add ce_satisfaction_survey_responses table

Revision ID: 2d53c8a0b4f1
Revises: 6b3d0ea47a6e
Create Date: 2026-02-26 12:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2d53c8a0b4f1'
down_revision = '6b3d0ea47a6e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ce_satisfaction_survey_responses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('registration_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('event_entity_id', sa.Integer(), nullable=False),
        sa.Column('survey_name', sa.String(length=255), nullable=False),
        sa.Column('overall_rating', sa.Integer(), nullable=False),
        sa.Column('content_rating', sa.Integer(), nullable=False),
        sa.Column('instructor_rating', sa.Integer(), nullable=False),
        sa.Column('platform_rating', sa.Integer(), nullable=False),
        sa.Column('recommend_to_others', sa.Boolean(), nullable=True),
        sa.Column('comment_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['event_entity_id'], ['ce_event_entities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['ce_members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['registration_id'], ['ce_member_registrations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('registration_id'),
    )
    op.create_index(op.f('ix_ce_satisfaction_survey_responses_registration_id'), 'ce_satisfaction_survey_responses', ['registration_id'], unique=False)
    op.create_index(op.f('ix_ce_satisfaction_survey_responses_member_id'), 'ce_satisfaction_survey_responses', ['member_id'], unique=False)
    op.create_index(op.f('ix_ce_satisfaction_survey_responses_event_entity_id'), 'ce_satisfaction_survey_responses', ['event_entity_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_ce_satisfaction_survey_responses_event_entity_id'), table_name='ce_satisfaction_survey_responses')
    op.drop_index(op.f('ix_ce_satisfaction_survey_responses_member_id'), table_name='ce_satisfaction_survey_responses')
    op.drop_index(op.f('ix_ce_satisfaction_survey_responses_registration_id'), table_name='ce_satisfaction_survey_responses')
    op.drop_table('ce_satisfaction_survey_responses')
