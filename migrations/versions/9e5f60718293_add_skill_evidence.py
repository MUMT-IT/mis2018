"""Add student evidence for skills and CLOs.

Revision ID: 9e5f60718293
Revises: 8d4e5f607182
"""

from alembic import op
import sqlalchemy as sa


revision = "9e5f60718293"
down_revision = "8d4e5f607182"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "eduqa_skill_evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("clo_id", sa.Integer(), nullable=False),
        sa.Column("assessment_pair_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("endorsed", sa.Boolean(), nullable=False),
        sa.Column("endorsed_by_id", sa.Integer(), nullable=True),
        sa.Column("endorsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["eduqa_students.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["eduqa_skills.id"]),
        sa.ForeignKeyConstraint(["clo_id"], ["eduqa_course_learning_outcomes.id"]),
        sa.ForeignKeyConstraint(["assessment_pair_id"], ["eduqa_course_learning_activity_assessment_pairs.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["staff_account.id"]),
        sa.ForeignKeyConstraint(["endorsed_by_id"], ["staff_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("eduqa_skill_evidence")
