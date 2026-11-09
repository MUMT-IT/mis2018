"""Add skill evaluation bundles and shared evaluation sessions."""
from alembic import op
import sqlalchemy as sa

revision = 'f5a6b7c8d9e0'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('eduqa_evaluation_bundles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('eduqa_courses.id'), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('staff_account.id'), nullable=False))
    op.create_table('eduqa_evaluation_bundle_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('bundle_id', sa.Integer(), sa.ForeignKey('eduqa_evaluation_bundles.id'), nullable=False),
        sa.Column('assignment_id', sa.Integer(), sa.ForeignKey('dynamic_form_assignments.id'), nullable=False),
        sa.UniqueConstraint('bundle_id', 'assignment_id'))
    op.create_table('eduqa_evaluation_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('bundle_id', sa.Integer(), sa.ForeignKey('eduqa_evaluation_bundles.id'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('eduqa_students.id'), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('staff_account.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table('eduqa_evaluation_session_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('eduqa_evaluation_sessions.id'), nullable=False),
        sa.Column('submission_id', sa.Integer(), sa.ForeignKey('dynamic_form_submissions.id'), nullable=False))


def downgrade():
    for table in ('eduqa_evaluation_session_results', 'eduqa_evaluation_sessions',
                  'eduqa_evaluation_bundle_items', 'eduqa_evaluation_bundles'):
        op.drop_table(table)
