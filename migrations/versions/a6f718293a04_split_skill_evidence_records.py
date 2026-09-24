"""Split reusable SkillEvidence from student evidence records.

Revision ID: a6f718293a04
Revises: 9e5f60718293
"""

from alembic import op
import sqlalchemy as sa


revision = "a6f718293a04"
down_revision = "9e5f60718293"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "eduqa_student_skill_evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("endorsed", sa.Boolean(), nullable=False),
        sa.Column("endorsed_by_id", sa.Integer(), nullable=True),
        sa.Column("endorsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["evidence_id"], ["eduqa_skill_evidence.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["eduqa_students.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["staff_account.id"]),
        sa.ForeignKeyConstraint(["endorsed_by_id"], ["staff_account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Existing records were stored as one combined definition/submission.
    # Keep each original row as a SkillEvidence and copy its student fields
    # into the corresponding StudentSkillEvidence row.
    op.execute(
        """
        INSERT INTO eduqa_student_skill_evidence
            (id, evidence_id, student_id, url, created_by_id, created_at,
             endorsed, endorsed_by_id, endorsed_at)
        SELECT id, id, student_id, url, created_by_id, created_at,
               endorsed, endorsed_by_id, endorsed_at
        FROM eduqa_skill_evidence
        """
    )

    op.drop_column("eduqa_skill_evidence", "student_id")
    op.drop_column("eduqa_skill_evidence", "url")
    op.drop_column("eduqa_skill_evidence", "endorsed")
    op.drop_column("eduqa_skill_evidence", "endorsed_by_id")
    op.drop_column("eduqa_skill_evidence", "endorsed_at")


def downgrade():
    op.add_column("eduqa_skill_evidence", sa.Column("student_id", sa.Integer(), nullable=True))
    op.add_column("eduqa_skill_evidence", sa.Column("url", sa.String(length=1024), nullable=True))
    op.add_column("eduqa_skill_evidence", sa.Column("endorsed", sa.Boolean(), nullable=True))
    op.add_column("eduqa_skill_evidence", sa.Column("endorsed_by_id", sa.Integer(), nullable=True))
    op.add_column("eduqa_skill_evidence", sa.Column("endorsed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE eduqa_skill_evidence AS evidence
        SET student_id = submission.student_id,
            url = submission.url,
            endorsed = submission.endorsed,
            endorsed_by_id = submission.endorsed_by_id,
            endorsed_at = submission.endorsed_at
        FROM eduqa_student_skill_evidence AS submission
        WHERE submission.evidence_id = evidence.id
        """
    )
    op.alter_column("eduqa_skill_evidence", "student_id", nullable=False)
    op.alter_column("eduqa_skill_evidence", "endorsed", nullable=False)
    op.drop_table("eduqa_student_skill_evidence")
