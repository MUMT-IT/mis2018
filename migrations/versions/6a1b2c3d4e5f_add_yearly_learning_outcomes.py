"""Add yearly learning outcomes and PLO mappings.

Revision ID: 6a1b2c3d4e5f
Revises: 5f8a9c1d2e3b
"""

from alembic import op
import sqlalchemy as sa


revision = "6a1b2c3d4e5f"
down_revision = "5f8a9c1d2e3b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "eduqa_year_learning_outcomes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("year_level", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["revision_id"], ["eduqa_curriculum_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "eduqa_year_learning_outcome_plo_assoc",
        sa.Column("year_learning_outcome_id", sa.Integer(), nullable=False),
        sa.Column("plo_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["year_learning_outcome_id"],
            ["eduqa_year_learning_outcomes.id"],
        ),
        sa.ForeignKeyConstraint(["plo_id"], ["eduqa_plos.id"]),
        sa.PrimaryKeyConstraint("year_learning_outcome_id", "plo_id"),
    )


def downgrade():
    op.drop_table("eduqa_year_learning_outcome_plo_assoc")
    op.drop_table("eduqa_year_learning_outcomes")
