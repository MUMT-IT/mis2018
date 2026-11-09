"""Link petty-cash fund requests to their originating setting."""

from datetime import date, datetime

from alembic import op
import sqlalchemy as sa


revision = "r5e6f7a8b9c0"
down_revision = "q4d5e6f7a8b9"
branch_labels = None
depends_on = None


TABLE_NAME = "petty_cash_fund_requests"
COLUMN_NAME = "petty_cash_setting_id"
INDEX_NAME = "ix_petty_cash_fund_requests_petty_cash_setting_id"
FK_NAME = "fk_petty_cash_fund_requests_petty_cash_setting_id"


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


def upgrade():
    op.add_column(
        TABLE_NAME,
        sa.Column(COLUMN_NAME, sa.Integer(), nullable=True),
    )
    op.create_index(INDEX_NAME, TABLE_NAME, [COLUMN_NAME], unique=False)
    op.create_foreign_key(
        FK_NAME,
        TABLE_NAME,
        "petty_cash_settings",
        [COLUMN_NAME],
        ["id"],
    )

    # Backfill historical requests using the normalized organization and the
    # fiscal year derived from request_date. Keep the column nullable because
    # legacy rows without an organization cannot be mapped safely.
    bind = op.get_bind()
    fund_requests = sa.table(
        TABLE_NAME,
        sa.column("id", sa.Integer()),
        sa.column("org_id", sa.Integer()),
        sa.column("request_date", sa.Date()),
        sa.column("created_at", sa.DateTime()),
        sa.column(COLUMN_NAME, sa.Integer()),
    )
    settings = sa.table(
        "petty_cash_settings",
        sa.column("id", sa.Integer()),
        sa.column("org_id", sa.Integer()),
        sa.column("fiscal_year", sa.Integer()),
    )

    rows = bind.execute(
        sa.select(
            fund_requests.c.id,
            fund_requests.c.org_id,
            fund_requests.c.request_date,
            fund_requests.c.created_at,
        ).where(fund_requests.c[COLUMN_NAME].is_(None))
    )
    for row in rows:
        if not row.org_id:
            continue
        request_date = _as_date(row.request_date) or _as_date(row.created_at)
        if not request_date:
            continue
        fiscal_year = request_date.year + 1 if request_date.month >= 10 else request_date.year
        setting_id = bind.execute(
            sa.select(settings.c.id)
            .where(
                settings.c.org_id == row.org_id,
                settings.c.fiscal_year == fiscal_year,
            )
            .order_by(settings.c.id.desc())
            .limit(1)
        ).scalar()
        if setting_id:
            bind.execute(
                fund_requests.update()
                .where(fund_requests.c.id == row.id)
                .values(**{COLUMN_NAME: setting_id})
            )


def downgrade():
    op.drop_constraint(FK_NAME, TABLE_NAME, type_="foreignkey")
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
    op.drop_column(TABLE_NAME, COLUMN_NAME)
