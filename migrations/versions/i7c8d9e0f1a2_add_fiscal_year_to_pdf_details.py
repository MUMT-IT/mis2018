"""add fiscal year to PDF detail records

Revision ID: i7c8d9e0f1a2
Revises: h6b7c8d9e0f1
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "i7c8d9e0f1a2"
down_revision = "h6b7c8d9e0f1"
branch_labels = None
depends_on = None


def _current_fiscal_year():
    today = datetime.now().date()
    return today.year + 1 if today.month >= 10 else today.year


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fiscal_year = _current_fiscal_year()

    for table_name in ("petty_cash_claim_details", "cash_advance_return_details"):
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "fiscal_year" not in columns:
            op.add_column(
                table_name,
                sa.Column("fiscal_year", sa.Integer(), nullable=True),
            )

        bind.execute(
            sa.text(f"UPDATE {table_name} SET fiscal_year = :fiscal_year"),
            {"fiscal_year": fiscal_year},
        )
        op.alter_column(
            table_name,
            "fiscal_year",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in ("cash_advance_return_details", "petty_cash_claim_details"):
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "fiscal_year" in columns:
            op.drop_column(table_name, "fiscal_year")
