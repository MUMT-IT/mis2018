"""Preserve closing document membership and history as associations.

Revision ID: d9e02f3a5b71
Revises: c8d91e2f4a60
"""
from alembic import op
import sqlalchemy as sa

revision = "d9e02f3a5b71"
down_revision = "c8d91e2f4a60"
branch_labels = None
depends_on = None

DOCUMENTS = "cash_mng_closing_documents"
LINKS = "cash_mng_closing_document_links"
RECORDS = (
    ("ticket_return_id", "cash_advance_return_details"),
    ("parcel_return_id", "cash_mng_parcel_return_details"),
    ("claim_id", "petty_cash_claim_details"),
)
NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def _table(bind, name):
    return sa.Table(name, sa.MetaData(), autoload_with=bind)


def upgrade():
    bind = op.get_bind()
    documents = _table(bind, DOCUMENTS)
    docs = {row.id: row for row in bind.execute(sa.select(documents))}
    by_number = {row.document_number: row for row in docs.values()}
    links = {}
    # Resolve every historical name before dropping any legacy data. Unknown names
    # need explicit repair; inventing a dated financial document would be misleading.
    for fk, name in RECORDS:
        records = _table(bind, name)
        for row in bind.execute(sa.select(records)):
            history = (row.old_closing_document_name or "").strip()
            numbers = [history] if history in by_number else [n.strip() for n in history.split(",") if n.strip()]
            for number in numbers:
                if number not in by_number:
                    raise RuntimeError(f"Cannot migrate {name} id={row.id}: unknown historical closing document {number!r}")
                doc = by_number[number]
                links[(doc.id, fk, row.id)] = False
            if row.closing_document_id is not None:
                if row.closing_document_id not in docs:
                    raise RuntimeError(f"Cannot migrate {name} id={row.id}: missing closing document FK")
                doc = docs[row.closing_document_id]
                links[(doc.id, fk, row.id)] = doc.status != "ถูกยกเลิก"

    op.add_column(DOCUMENTS, sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.execute(sa.text(f"UPDATE {DOCUMENTS} SET is_active = false WHERE status = 'ถูกยกเลิก'"))
    op.create_table(
        LINKS,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey(f"{DOCUMENTS}.id"), nullable=False),
        *(sa.Column(fk, sa.Integer(), sa.ForeignKey(f"{name}.id"), nullable=True) for fk, name in RECORDS),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "(CASE WHEN ticket_return_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN parcel_return_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN claim_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_closing_link_one_record",
        ),
        *(sa.UniqueConstraint("document_id", fk, name="uq_closing_link_doc_" + fk) for fk, _ in RECORDS),
    )
    op.create_index("ix_cash_mng_closing_document_links_document_id", LINKS, ["document_id"])
    for fk, _ in RECORDS:
        op.create_index("uq_closing_link_active_" + fk, LINKS, [fk], unique=True,
                        postgresql_where=sa.text("is_active"), sqlite_where=sa.text("is_active = 1"))
    table = _table(bind, LINKS)
    for (doc_id, fk, record_id), active in links.items():
        bind.execute(table.insert().values(document_id=doc_id, **{fk: record_id}, is_active=active))

    for _, name in RECORDS:
        constraints = sa.inspect(bind).get_foreign_keys(name)
        with op.batch_alter_table(name, naming_convention=NAMING) as batch:
            for constraint in constraints:
                if constraint["constrained_columns"] == ["closing_document_id"]:
                    constraint_name = constraint["name"] or f"fk_{name}_closing_document_id_{DOCUMENTS}"
                    batch.drop_constraint(constraint_name, type_="foreignkey")
            batch.drop_column("closing_document_id")
            batch.drop_column("old_closing_document_name")
    with op.batch_alter_table(DOCUMENTS) as batch:
        batch.drop_column("status")


def downgrade():
    bind = op.get_bind()
    documents = _table(bind, DOCUMENTS)
    docs = {row.id: row for row in bind.execute(sa.select(documents))}
    links = list(bind.execute(sa.select(_table(bind, LINKS)).order_by(sa.column("id"))))
    restored = {}
    for fk, name in RECORDS:
        for row in bind.execute(sa.select(_table(bind, name))):
            related = [link for link in links if getattr(link, fk) == row.id]
            active = [link for link in related if link.is_active and docs[link.document_id].is_active]
            history = ", ".join(docs[link.document_id].document_number for link in related if link not in active)
            if len(history) > 255:
                raise RuntimeError(f"Cannot downgrade {name} id={row.id}: history exceeds legacy 255-character limit")
            restored[(name, row.id)] = (active[0].document_id if active else None, history or None)

    op.add_column(DOCUMENTS, sa.Column("status", sa.String(32), nullable=False, server_default="ใช้งานอยู่"))
    op.execute(sa.text(f"UPDATE {DOCUMENTS} SET status = 'ถูกยกเลิก' WHERE is_active = false"))
    for _, name in RECORDS:
        with op.batch_alter_table(name) as batch:
            batch.add_column(sa.Column("closing_document_id", sa.Integer(), nullable=True))
            batch.add_column(sa.Column("old_closing_document_name", sa.String(255), nullable=True))
            batch.create_foreign_key(f"fk_{name}_closing_document_id_{DOCUMENTS}", DOCUMENTS, ["closing_document_id"], ["id"])
        table = _table(bind, name)
        for (record_table, record_id), (doc_id, history) in restored.items():
            if record_table == name:
                bind.execute(table.update().where(table.c.id == record_id).values(
                    closing_document_id=doc_id, old_closing_document_name=history))
    # Completion is derived from current member records in the new schema.
    for doc in docs.values():
        statuses = []
        for fk, name in RECORDS:
            table = _table(bind, name)
            ids = [getattr(link, fk) for link in links if link.document_id == doc.id and link.is_active and getattr(link, fk) is not None]
            if ids:
                statuses.extend(bind.execute(sa.select(table.c.status).where(table.c.id.in_(ids))).scalars())
        if doc.is_active and statuses and all(status in ("ล้างลูกหนี้เงินยืม", "เสร็จสิ้นกระบวนการ") for status in statuses):
            bind.execute(sa.text(f"UPDATE {DOCUMENTS} SET status = :status WHERE id = :id"),
                         {"status": "ล้างลูกหนี้เงินยืม", "id": doc.id})
    op.drop_table(LINKS)
    with op.batch_alter_table(DOCUMENTS) as batch:
        batch.drop_column("is_active")
