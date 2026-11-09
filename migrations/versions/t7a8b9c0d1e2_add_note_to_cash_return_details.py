"""Add optional notes for receipts shared with parcel returns."""

from alembic import op
import sqlalchemy as sa


revision = "t7a8b9c0d1e2"
down_revision = "r5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "cash_advance_return_details",
        sa.Column("note", sa.String(length=2000), nullable=True),
    )
    op.add_column(
        "petty_cash_claim_details",
        sa.Column("note", sa.String(length=2000), nullable=True),
    )


def downgrade():
    op.drop_column("petty_cash_claim_details", "note")
    op.drop_column("cash_advance_return_details", "note")
