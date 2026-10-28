"""Link advance-payment tables to the status catalog."""

from alembic import op
import sqlalchemy as sa


revision = "t3u4v5w6x7y8"
down_revision = "s2t3u4v5w6x7"
branch_labels = None
depends_on = None


TABLES = (
    "cash_advance_borrowing_tickets",
    "cash_advance_return_details",
    "cash_mng_parcel_return_details",
    "petty_cash_fund_requests",
    "petty_cash_claim_details",
)


def upgrade():
    for table_name in TABLES:
        op.add_column(
            table_name,
            sa.Column("status_id", sa.Integer(), nullable=True),
        )
        op.create_index(
            f"ix_{table_name}_status_id",
            table_name,
            ["status_id"],
            unique=False,
        )
        op.create_foreign_key(
            f"fk_{table_name}_status_id",
            table_name,
            "advance_payment_statuses",
            ["status_id"],
            ["id"],
        )

    connection = op.get_bind()
    for table_name, status_group in (
        ("cash_advance_borrowing_tickets", "borrowing_ticket"),
        ("cash_advance_return_details", "return_detail"),
        ("cash_mng_parcel_return_details", "parcel_return"),
        ("petty_cash_fund_requests", "fund_request"),
        ("petty_cash_claim_details", "petty_cash_claim"),
    ):
        connection.execute(
            sa.text(
                f"""
                UPDATE {table_name} AS target
                SET status_id = catalog.id
                FROM advance_payment_statuses AS catalog
                WHERE catalog.status_group = :status_group
                  AND catalog.name = target.status
                """
            ),
            {"status_group": status_group},
        )


def downgrade():
    for table_name in reversed(TABLES):
        op.drop_constraint(
            f"fk_{table_name}_status_id",
            table_name,
            type_="foreignkey",
        )
        op.drop_index(f"ix_{table_name}_status_id", table_name=table_name)
        op.drop_column(table_name, "status_id")
