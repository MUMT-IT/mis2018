"""Record cash returns explicitly instead of inferring from descriptions.

Revision ID: e0f13a4b6c82
Revises: d9e02f3a5b71
"""
from alembic import op
import sqlalchemy as sa

revision = "e0f13a4b6c82"
down_revision = "d9e02f3a5b71"
branch_labels = None
depends_on = None

TABLE = "cash_advance_return_receipt_items"


def upgrade():
    op.add_column(TABLE, sa.Column("is_cash", sa.Boolean(), nullable=False, server_default=sa.false()))
    receipts = sa.table(TABLE, sa.column("description", sa.String()), sa.column("is_cash", sa.Boolean()))
    # Preserve the classification of existing records once during migration.
    op.execute(receipts.update().where(receipts.c.description.contains("เงินเหลือส่งใช้เงินยืม")).values(is_cash=True))


def downgrade():
    op.drop_column(TABLE, "is_cash")
