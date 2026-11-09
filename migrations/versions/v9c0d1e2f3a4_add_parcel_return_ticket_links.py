"""Add borrowing-ticket links for parcel returns."""

from alembic import op
import sqlalchemy as sa


revision = "v9c0d1e2f3a4"
down_revision = "7937dc649588"
branch_labels = None
depends_on = None


TABLE_NAME = "cash_advance_parcel_borrowing_ticket_association"


def upgrade():
    bind = op.get_bind()
    if sa.inspect(bind).has_table(TABLE_NAME):
        return
    op.create_table(
        TABLE_NAME,
        sa.Column("parcel_return_id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["parcel_return_id"], ["cash_mng_parcel_return_details.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["cash_advance_borrowing_tickets.id"]),
        sa.PrimaryKeyConstraint("parcel_return_id", "ticket_id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO cash_advance_parcel_borrowing_ticket_association "
            "(parcel_return_id, ticket_id) "
            "SELECT id, ticket_id FROM cash_mng_parcel_return_details "
            "WHERE ticket_id IS NOT NULL"
        )
    )


def downgrade():
    if sa.inspect(op.get_bind()).has_table(TABLE_NAME):
        op.drop_table(TABLE_NAME)
