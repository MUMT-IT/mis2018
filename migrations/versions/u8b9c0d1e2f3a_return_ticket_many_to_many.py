"""Allow one return ticket to reference multiple borrowing tickets."""

from alembic import op
import sqlalchemy as sa


revision = "u8b9c0d1e2f3a"
down_revision = "t7a8b9c0d1e2"
branch_labels = None
depends_on = None


TABLE_NAME = "cash_advance_return_borrowing_ticket_association"
PARCEL_TABLE_NAME = "cash_advance_parcel_borrowing_ticket_association"


def upgrade():
    op.create_table(
        TABLE_NAME,
        sa.Column("return_id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["return_id"], ["cash_advance_return_details.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["cash_advance_borrowing_tickets.id"]),
        sa.PrimaryKeyConstraint("return_id", "ticket_id"),
    )

    # Backfill the legacy one-ticket relationship so every existing return is
    # immediately visible through the new many-to-many link as well.
    op.execute(
        sa.text(
            f"INSERT INTO {TABLE_NAME} (return_id, ticket_id) "
            "SELECT id, ticket_id FROM cash_advance_return_details "
            "WHERE ticket_id IS NOT NULL"
        )
    )
    op.create_table(
        PARCEL_TABLE_NAME,
        sa.Column("parcel_return_id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["parcel_return_id"], ["cash_mng_parcel_return_details.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["cash_advance_borrowing_tickets.id"]),
        sa.PrimaryKeyConstraint("parcel_return_id", "ticket_id"),
    )
    op.execute(
        sa.text(
            f"INSERT INTO {PARCEL_TABLE_NAME} (parcel_return_id, ticket_id) "
            "SELECT id, ticket_id FROM cash_mng_parcel_return_details "
            "WHERE ticket_id IS NOT NULL"
        )
    )


def downgrade():
    op.drop_table(PARCEL_TABLE_NAME)
    op.drop_table(TABLE_NAME)
