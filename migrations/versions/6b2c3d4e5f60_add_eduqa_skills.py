"""Add EduQA skills and PLO mappings.

Revision ID: 6b2c3d4e5f60
Revises: 6a1b2c3d4e5f
"""

from alembic import op
import sqlalchemy as sa


revision = "6b2c3d4e5f60"
down_revision = "6a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "eduqa_skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["revision_id"], ["eduqa_curriculum_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_eduqa_skills_code"),
    )
    op.create_table(
        "eduqa_skill_plo_assoc",
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("plo_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["eduqa_skills.id"]),
        sa.ForeignKeyConstraint(["plo_id"], ["eduqa_plos.id"]),
        sa.PrimaryKeyConstraint("skill_id", "plo_id"),
    )


def downgrade():
    op.drop_table("eduqa_skill_plo_assoc")
    op.drop_table("eduqa_skills")
