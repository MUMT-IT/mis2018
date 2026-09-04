"""bind fund requests to organizations

Revision ID: e3a7f1b2c4d5
Revises: d1f608410bd4
Create Date: 2026-09-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e3a7f1b2c4d5"
down_revision = "d1f608410bd4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("petty_cash_fund_requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("org_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_petty_cash_fund_requests_org_id", ["org_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_petty_cash_fund_requests_org_id_orgs",
            "orgs",
            ["org_id"],
            ["id"],
        )

    # Backfill existing requests using the historical department label.
    op.execute(
        sa.text(
            """
            UPDATE petty_cash_fund_requests AS fr
            SET org_id = org.id
            FROM orgs AS org
            WHERE fr.org_id IS NULL
              AND (fr.department_name = org.name OR fr.department_name = org.en_name)
            """
        )
    )


def downgrade():
    with op.batch_alter_table("petty_cash_fund_requests", schema=None) as batch_op:
        batch_op.drop_constraint("fk_petty_cash_fund_requests_org_id_orgs", type_="foreignkey")
        batch_op.drop_index("ix_petty_cash_fund_requests_org_id")
        batch_op.drop_column("org_id")
