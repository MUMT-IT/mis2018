"""add organization to bank account records

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""

from alembic import op
import sqlalchemy as sa


revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("cash_mng_bank_account_infos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("org_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_cash_mng_bank_account_infos_org_id", ["org_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_cash_mng_bank_account_infos_org_id_orgs",
            "orgs",
            ["org_id"],
            ["id"],
        )

    op.execute(
        sa.text(
            "UPDATE cash_mng_bank_account_infos "
            "SET org_id = (SELECT orgs.id FROM orgs "
            "WHERE orgs.name = cash_mng_bank_account_infos.thai_name LIMIT 1) "
            "WHERE org_id IS NULL AND EXISTS (SELECT 1 FROM orgs "
            "WHERE orgs.name = cash_mng_bank_account_infos.thai_name)"
        )
    )


def downgrade():
    with op.batch_alter_table("cash_mng_bank_account_infos", schema=None) as batch_op:
        batch_op.drop_constraint("fk_cash_mng_bank_account_infos_org_id_orgs", type_="foreignkey")
        batch_op.drop_index("ix_cash_mng_bank_account_infos_org_id")
        batch_op.drop_column("org_id")
