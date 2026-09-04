"""normalize petty cash settings to organization and foreign-key references

Revision ID: a7c4e9f2b6d8
Revises: f4a8c2d9e6b1
"""
from alembic import op
import sqlalchemy as sa


revision = "a7c4e9f2b6d8"
down_revision = "f4a8c2d9e6b1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("petty_cash_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("org_id", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint("uq_petty_cash_settings_org_id", ["org_id"])
        batch_op.create_foreign_key(
            "fk_petty_cash_settings_org_id_orgs", "orgs", ["org_id"], ["id"]
        )

    op.execute(
        sa.text(
            """
            UPDATE petty_cash_settings AS pcs
            SET org_id = org.id
            FROM orgs AS org
            WHERE pcs.department_name = org.name OR pcs.department_name = org.en_name
            """
        )
    )

    # Preserve legacy account and enabled-state values before removing the
    # denormalized columns below.
    op.execute(
        sa.text(
            """
            UPDATE petty_cash_settings AS pcs
            SET bank_account_info_id = bai.id
            FROM cash_mng_bank_account_infos AS bai
            WHERE pcs.bank_account_info_id IS NULL
              AND pcs.account_number IS NOT NULL
              AND regexp_replace(pcs.account_number, '[^0-9]', '', 'g')
                  = regexp_replace(bai.account_number, '[^0-9]', '', 'g')
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE petty_cash_settings
            SET valid = is_enabled
            WHERE is_enabled IS NOT NULL
            """
        )
    )

    with op.batch_alter_table("petty_cash_settings", schema=None) as batch_op:
        batch_op.alter_column("org_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("is_enabled")
        batch_op.drop_column("custodian_name")
        batch_op.drop_column("account_number")
        batch_op.drop_column("department_name")


def downgrade():
    with op.batch_alter_table("petty_cash_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("department_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("custodian_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("account_number", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("is_enabled", sa.Boolean(), nullable=True))
        batch_op.drop_constraint("fk_petty_cash_settings_org_id_orgs", type_="foreignkey")
        batch_op.drop_constraint("uq_petty_cash_settings_org_id", type_="unique")
        batch_op.drop_column("org_id")
