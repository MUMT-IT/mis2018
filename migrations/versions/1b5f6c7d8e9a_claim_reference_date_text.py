"""Allow free-text reference dates on petty cash claims.

Revision ID: 1b5f6c7d8e9a
Revises: 0a4e6b8c2d1f
"""

from datetime import date

from alembic import op
import sqlalchemy as sa


revision = "1b5f6c7d8e9a"
down_revision = "0a4e6b8c2d1f"
branch_labels = None
depends_on = None

TABLE = "petty_cash_claim_details"
COLUMN = "reference_date"


def upgrade():
    # PostgreSQL formats DATE -> text as YYYY-MM-DD; NULL stays NULL.
    # This also works when the table has no rows.
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            TABLE, COLUMN,
            existing_type=sa.Date(), type_=sa.String(), existing_nullable=True,
            postgresql_using="reference_date::text",
        )
    else:
        with op.batch_alter_table(TABLE) as batch:
            batch.alter_column(
                COLUMN, existing_type=sa.Date(), type_=sa.String(),
                existing_nullable=True,
            )


def downgrade():
    connection = op.get_bind()
    values = connection.execute(
        sa.text(f"SELECT {COLUMN} FROM {TABLE} WHERE {COLUMN} IS NOT NULL")
    )
    for (value,) in values:
        try:
            date.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValueError(
                "Cannot downgrade claim reference_date while free-text values exist"
            ) from None

    if connection.dialect.name == "postgresql":
        op.alter_column(
            TABLE, COLUMN,
            existing_type=sa.String(), type_=sa.Date(), existing_nullable=True,
            postgresql_using="reference_date::date",
        )
    else:
        with op.batch_alter_table(TABLE) as batch:
            batch.alter_column(
                COLUMN, existing_type=sa.String(), type_=sa.Date(),
                existing_nullable=True,
            )
