"""Move advance payment document links to docs-query and remove the legacy catalog.

Revision ID: e83f9a1b2c4d
Revises: d72d68d9af22
"""

import re

from alembic import op
import sqlalchemy as sa


revision = "e83f9a1b2c4d"
down_revision = "d72d68d9af22"
branch_labels = None
depends_on = None


LINKS = (
    ("cash_mng_document_return_association", "cash_mng_docs_query_return_association",
     "return_id", "cash_advance_return_details"),
    ("cash_mng_document_petty_claim_association", "cash_mng_docs_query_petty_claim_association",
     "claim_id", "petty_cash_claim_details"),
)


def _create_link_table(name, record_column, record_table, document_table):
    op.create_table(
        name,
        sa.Column("document_id", sa.Integer(), sa.ForeignKey(f"{document_table}.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(record_column, sa.Integer(), sa.ForeignKey(f"{record_table}.id", ondelete="CASCADE"), primary_key=True),
    )


def _source_key(file_path):
    match = re.match(r"https://drive\.google\.com/file/d/([^/]+)/view(?:\?.*)?$", file_path or "")
    return match.group(1) if match else (file_path or "")


def upgrade():
    bind = op.get_bind()
    legacy_documents = sa.Table("cash_mng_documents", sa.MetaData(), autoload_with=bind)
    source_documents = sa.Table("docs_query_documents", sa.MetaData(), autoload_with=bind)
    source_rows = bind.execute(sa.select(source_documents.c.id, source_documents.c.drive_file_id,
                                         source_documents.c.document_title, source_documents.c.filename)).all()
    by_file_id = {row.drive_file_id: row.id for row in source_rows}
    by_title = {}
    for row in source_rows:
        for title in (row.document_title, row.filename):
            if title:
                by_title.setdefault(title.strip().casefold(), set()).add(row.id)

    mapping = {}
    for row in bind.execute(sa.select(legacy_documents.c.id, legacy_documents.c.title,
                                      legacy_documents.c.file_path)):
        source_id = by_file_id.get(_source_key(row.file_path))
        if source_id is None:
            matches = by_title.get((row.title or "").strip().casefold(), set())
            if len(matches) == 1:
                source_id = next(iter(matches))
        mapping[row.id] = source_id

    legacy_links = {}
    missing = set()
    for old_name, _, record_column, _ in LINKS:
        old_table = sa.Table(old_name, sa.MetaData(), autoload_with=bind)
        old_rows = bind.execute(sa.select(old_table.c.document_id, old_table.c[record_column])).all()
        legacy_links[old_name] = old_rows
        missing.update(row.document_id for row in old_rows if mapping.get(row.document_id) is None)
    if missing:
        raise RuntimeError(
            "Cannot map cash_mng_documents IDs to docs_query_documents: "
            + ", ".join(map(str, sorted(missing)))
        )

    for old_name, new_name, record_column, record_table in LINKS:
        _create_link_table(new_name, record_column, record_table, "docs_query_documents")
        new_table = sa.Table(new_name, sa.MetaData(), autoload_with=bind)
        links = {(mapping[row.document_id], getattr(row, record_column)) for row in legacy_links[old_name]}
        if links:
            bind.execute(new_table.insert(), [
                {"document_id": document_id, record_column: record_id}
                for document_id, record_id in links
            ])

    # All referenced documents have been copied. Unreferenced legacy rows have
    # no advance-payment relationship to retain.
    for old_name, _, _, _ in LINKS:
        op.drop_table(old_name)
    op.drop_table("cash_mng_documents")


def downgrade():
    raise RuntimeError(
        "This migration deletes the legacy cash_mng_documents catalog; "
        "restore a database backup to recover its original records."
    )
