"""allow a petty-cash custodian to be reused across fiscal years

Revision ID: j8d9e0f1a2b3
Revises: i7c8d9e0f1a2
"""

from alembic import op
import sqlalchemy as sa


revision = "j8d9e0f1a2b3"
down_revision = "i7c8d9e0f1a2"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "petty_cash_settings_custodian_id_key"


def upgrade():
    # A custodian may manage the same department in multiple fiscal years.
    # Uniqueness is enforced by (org_id, fiscal_year) instead.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            f"ALTER TABLE petty_cash_settings "
            f"DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}"
        )
    )


def downgrade():
    # This can fail if rows created after upgrade reuse a custodian across
    # fiscal years. That is expected because the old rule disallows that data.
    op.create_unique_constraint(
        CONSTRAINT_NAME,
        "petty_cash_settings",
        ["custodian_id"],
    )
