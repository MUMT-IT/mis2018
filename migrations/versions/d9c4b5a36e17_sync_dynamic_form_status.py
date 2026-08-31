"""Synchronize Dynamic Form version status with form status.

Revision ID: d9c4b5a36e17
Revises: c8b93a4b25d6
"""

from alembic import op


revision = "d9c4b5a36e17"
down_revision = "c8b93a4b25d6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE dynamic_form_versions AS version
        SET status = form.status,
            published_at = CASE
                WHEN form.status = 'Published' THEN COALESCE(version.published_at, NOW())
                ELSE version.published_at
            END
        FROM dynamic_forms AS form
        WHERE version.form_id = form.id
        """
    )


def downgrade():
    pass
