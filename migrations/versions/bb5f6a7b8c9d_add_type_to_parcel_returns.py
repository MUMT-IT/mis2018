"""Add the circular type to parcel return details."""

from alembic import op
import sqlalchemy as sa


revision = "bb5f6a7b8c9d"
down_revision = "aa4e5f6a7b8c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("cash_mng_parcel_return_details", schema=None) as batch_op:
        batch_op.add_column(sa.Column("type", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "ck_cash_mng_parcel_return_details_type",
            "type IS NULL OR type IN (1, 5)",
        )


def downgrade():
    with op.batch_alter_table("cash_mng_parcel_return_details", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_cash_mng_parcel_return_details_type",
            type_="check",
        )
        batch_op.drop_column("type")
