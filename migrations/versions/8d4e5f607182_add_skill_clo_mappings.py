"""Add Skill to CLO mappings.

Revision ID: 8d4e5f607182
Revises: 7c3d4e5f6071
"""

from alembic import op
import sqlalchemy as sa


revision = "8d4e5f607182"
down_revision = "7c3d4e5f6071"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "eduqa_skill_clo_assoc",
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("clo_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["eduqa_skills.id"]),
        sa.ForeignKeyConstraint(
            ["clo_id"],
            ["eduqa_course_learning_outcomes.id"],
        ),
        sa.PrimaryKeyConstraint("skill_id", "clo_id"),
    )


def downgrade():
    op.drop_table("eduqa_skill_clo_assoc")
