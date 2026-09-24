"""Add Skill to YLO mappings.

Revision ID: 7c3d4e5f6071
Revises: 6b2c3d4e5f60
"""

from alembic import op
import sqlalchemy as sa


revision = "7c3d4e5f6071"
down_revision = "6b2c3d4e5f60"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "eduqa_skill_ylo_assoc",
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("year_learning_outcome_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["eduqa_skills.id"]),
        sa.ForeignKeyConstraint(
            ["year_learning_outcome_id"],
            ["eduqa_year_learning_outcomes.id"],
        ),
        sa.PrimaryKeyConstraint("skill_id", "year_learning_outcome_id"),
    )


def downgrade():
    op.drop_table("eduqa_skill_ylo_assoc")
