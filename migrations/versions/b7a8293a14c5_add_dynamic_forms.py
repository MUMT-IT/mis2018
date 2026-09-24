"""Add reusable dynamic form builder tables.

Revision ID: b7a8293a14c5
Revises: a6f718293a04
"""

from alembic import op
import sqlalchemy as sa


revision = "b7a8293a14c5"
down_revision = "a6f718293a04"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("dynamic_forms",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("name", sa.String(length=255), nullable=False),
                    sa.Column("description", sa.Text()),
                    sa.Column("status", sa.String(length=32), nullable=False),
                    sa.Column("created_by_id", sa.Integer(), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                    sa.ForeignKeyConstraint(["created_by_id"], ["staff_account.id"]))
    op.create_table("dynamic_form_versions",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("form_id", sa.Integer(), nullable=False),
                    sa.Column("version", sa.Integer(), nullable=False),
                    sa.Column("status", sa.String(length=32), nullable=False),
                    sa.Column("created_by_id", sa.Integer(), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                    sa.Column("published_at", sa.DateTime(timezone=True)),
                    sa.ForeignKeyConstraint(["form_id"], ["dynamic_forms.id"]),
                    sa.ForeignKeyConstraint(["created_by_id"], ["staff_account.id"]))
    op.create_table("dynamic_form_fields",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("version_id", sa.Integer(), nullable=False),
                    sa.Column("key", sa.String(length=128), nullable=False),
                    sa.Column("label", sa.String(length=255), nullable=False),
                    sa.Column("field_type", sa.String(length=32), nullable=False),
                    sa.Column("required", sa.Boolean(), nullable=False),
                    sa.Column("display_order", sa.Integer(), nullable=False),
                    sa.Column("help_text", sa.Text()), sa.Column("config", sa.JSON()),
                    sa.ForeignKeyConstraint(["version_id"], ["dynamic_form_versions.id"]))
    op.create_table("dynamic_form_options",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("field_id", sa.Integer(), nullable=False),
                    sa.Column("value", sa.String(length=255), nullable=False),
                    sa.Column("label", sa.String(length=255), nullable=False),
                    sa.Column("display_order", sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(["field_id"], ["dynamic_form_fields.id"]))
    op.create_table("dynamic_form_submissions",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("version_id", sa.Integer(), nullable=False),
                    sa.Column("respondent_type", sa.String(length=128), nullable=False),
                    sa.Column("respondent_id", sa.Integer(), nullable=False),
                    sa.Column("subject_type", sa.String(length=128), nullable=False),
                    sa.Column("subject_id", sa.Integer(), nullable=False),
                    sa.Column("status", sa.String(length=32), nullable=False),
                    sa.Column("submitted_at", sa.DateTime(timezone=True)),
                    sa.ForeignKeyConstraint(["version_id"], ["dynamic_form_versions.id"]))
    op.create_table("dynamic_form_answers",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("submission_id", sa.Integer(), nullable=False),
                    sa.Column("field_id", sa.Integer(), nullable=False),
                    sa.Column("value", sa.JSON()),
                    sa.ForeignKeyConstraint(["submission_id"], ["dynamic_form_submissions.id"]),
                    sa.ForeignKeyConstraint(["field_id"], ["dynamic_form_fields.id"]))


def downgrade():
    op.drop_table("dynamic_form_answers")
    op.drop_table("dynamic_form_submissions")
    op.drop_table("dynamic_form_options")
    op.drop_table("dynamic_form_fields")
    op.drop_table("dynamic_form_versions")
    op.drop_table("dynamic_forms")
