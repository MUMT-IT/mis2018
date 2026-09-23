"""Store the date and time a closing document was settled.

Revision ID: n2b3c4d5e6f7
Revises: d4e8a91f0c72
"""

from alembic import op
import sqlalchemy as sa


revision = "n2b3c4d5e6f7"
down_revision = "d4e8a91f0c72"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "cash_mng_closing_documents",
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("cash_mng_closing_documents", "settled_at")
