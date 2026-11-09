"""Backfill finance settlement timestamps and record review issues.

Revision ID: r1b2c3d4e5f6
Revises: q0a1b2c3d4e5
Create Date: 2026-10-08
"""

from decimal import Decimal

from alembic import op
import sqlalchemy as sa


revision = "r1b2c3d4e5f6"
down_revision = "q0a1b2c3d4e5"
branch_labels = None
depends_on = None


ISSUE_TABLE = "cash_mng_settlement_backfill_issues"
CENT = Decimal("0.01")


def _money(value):
    return Decimal(str(value or 0)).quantize(CENT)


def _datetime_key(value):
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def upgrade():
    op.create_table(
        ISSUE_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("issue_code", sa.String(length=64), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "issue_code",
            name="uq_settlement_backfill_issue_entity_code",
        ),
    )
    op.create_index(
        "ix_settlement_backfill_issue_entity_type",
        ISSUE_TABLE,
        ["entity_type"],
    )
    op.create_index(
        "ix_settlement_backfill_issue_entity_id",
        ISSUE_TABLE,
        ["entity_id"],
    )

    connection = op.get_bind()
    metadata = sa.MetaData()
    tables = {
        name: sa.Table(name, metadata, autoload_with=connection)
        for name in (
            ISSUE_TABLE,
            "cash_advance_borrowing_tickets",
            "cash_advance_return_details",
            "cash_advance_return_receipt_items",
            "cash_mng_parcel_return_details",
            "petty_cash_claim_details",
            "petty_cash_claim_items",
            "cash_mng_closing_documents",
            "cash_mng_closing_document_links",
            "cash_advance_return_borrowing_ticket_association",
            "cash_advance_parcel_borrowing_ticket_association",
        )
    }
    reported = set()

    def report(entity_type, entity_id, issue_code, details):
        key = (entity_type, int(entity_id), issue_code)
        if key in reported:
            return
        reported.add(key)
        connection.execute(
            tables[ISSUE_TABLE].insert().values(
                entity_type=entity_type,
                entity_id=int(entity_id),
                issue_code=issue_code,
                details=details,
            )
        )

    _backfill_cash_returns(connection, tables, report)
    _backfill_category_six_claims(connection, tables, report)
    _backfill_active_settled_closing_documents(connection, tables, report)
    _recalculate_borrowing_ticket_settlement(connection, tables, report)


def _backfill_cash_returns(connection, tables, report):
    returns = tables["cash_advance_return_details"]
    items = tables["cash_advance_return_receipt_items"]
    item_rows = connection.execute(
        sa.select(
            items.c.return_detail_id,
            items.c.is_cash,
            items.c.store_name,
            items.c.description,
        )
    ).mappings()
    items_by_return = {}
    for item in item_rows:
        items_by_return.setdefault(item["return_detail_id"], []).append(item)

    approved_returns = connection.execute(
        sa.select(returns.c.id, returns.c.approved_at).where(
            returns.c.approved_at.is_not(None)
        )
    ).mappings()
    for return_detail in approved_returns:
        return_items = items_by_return.get(return_detail["id"], [])
        if not return_items:
            report(
                "return_detail",
                return_detail["id"],
                "approved_return_without_items",
                "ไม่พบรายการย่อย จึงไม่สามารถระบุว่าเป็นเงินคืนหรือค่าใช้จ่ายได้",
            )
            continue
        cash_flags = [
            bool(item["is_cash"])
            or (
                (item["store_name"] or "").strip() == "-"
                and (item["description"] or "").strip()
                == "เงินเหลือส่งใช้เงินยืม"
            )
            for item in return_items
        ]
        if all(cash_flags):
            connection.execute(
                returns.update()
                .where(returns.c.id == return_detail["id"])
                .values(settled_at=return_detail["approved_at"])
            )
        elif any(cash_flags):
            report(
                "return_detail",
                return_detail["id"],
                "mixed_cash_and_non_cash_items",
                "พบทั้งรายการเงินคืนและค่าใช้จ่ายใน ReturnDetail เดียวกัน",
            )


def _backfill_category_six_claims(connection, tables, report):
    claims = tables["petty_cash_claim_details"]
    items = tables["petty_cash_claim_items"]
    claim_items = {}
    for item in connection.execute(
        sa.select(items.c.claim_id, items.c.category_type)
    ).mappings():
        claim_items.setdefault(item["claim_id"], []).append(item["category_type"])

    for claim in connection.execute(
        sa.select(claims.c.id, claims.c.status, claims.c.created_at)
    ).mappings():
        categories = claim_items.get(claim["id"], [])
        if categories and all(int(category or 0) == 6 for category in categories):
            if claim["created_at"] is None:
                report(
                    "petty_cash_claim",
                    claim["id"],
                    "category_six_missing_submission_time",
                    "เป็น category 6 ทั้งชุด แต่ไม่มี created_at ที่ใช้เป็นเวลาส่งรายการ",
                )
            else:
                connection.execute(
                    claims.update()
                    .where(claims.c.id == claim["id"])
                    .values(settled_at=claim["created_at"])
                )
        elif categories and any(int(category or 0) == 6 for category in categories):
            report(
                "petty_cash_claim",
                claim["id"],
                "mixed_category_six_and_ordinary_items",
                "พบ category 6 ปะปนกับหมวดค่าใช้จ่ายใน claim เดียวกัน",
            )
        elif not categories and (claim["status"] or "").strip() != "ฉบับร่าง":
            report(
                "petty_cash_claim",
                claim["id"],
                "submitted_claim_without_items",
                "claim ไม่ใช่ฉบับร่างแต่ไม่พบ PettyCashClaimItem",
            )


def _backfill_active_settled_closing_documents(connection, tables, report):
    documents = tables["cash_mng_closing_documents"]
    links = tables["cash_mng_closing_document_links"]
    returns = tables["cash_advance_return_details"]
    parcels = tables["cash_mng_parcel_return_details"]
    claims = tables["petty_cash_claim_details"]

    active_links = connection.execute(
        sa.select(
            links.c.id,
            links.c.ticket_return_id,
            links.c.parcel_return_id,
            links.c.claim_id,
            documents.c.settled_at,
        )
        .select_from(links.join(documents, links.c.document_id == documents.c.id))
        .where(
            links.c.is_active.is_(True),
            documents.c.is_active.is_(True),
            documents.c.settled_at.is_not(None),
        )
    ).mappings()

    for link in active_links:
        target = next(
            (
                (table, record_id)
                for table, record_id in (
                    (returns, link["ticket_return_id"]),
                    (parcels, link["parcel_return_id"]),
                    (claims, link["claim_id"]),
                )
                if record_id is not None
            ),
            None,
        )
        if target is None:
            report(
                "closing_link",
                link["id"],
                "active_settled_link_without_record",
                "active link ของฎีกาที่ settled แล้วไม่ชี้ไปยังรายการต้นทาง",
            )
            continue
        table, record_id = target
        connection.execute(
            table.update()
            .where(table.c.id == record_id)
            .values(settled_at=link["settled_at"])
        )


def _recalculate_borrowing_ticket_settlement(connection, tables, report):
    tickets_table = tables["cash_advance_borrowing_tickets"]
    returns = tables["cash_advance_return_details"]
    parcels = tables["cash_mng_parcel_return_details"]
    return_links = tables["cash_advance_return_borrowing_ticket_association"]
    parcel_links = tables["cash_advance_parcel_borrowing_ticket_association"]

    tickets = list(
        connection.execute(
            sa.select(
                tickets_table.c.id,
                tickets_table.c.required_budget,
                tickets_table.c.approved_at,
                tickets_table.c.closed_date,
            )
        ).mappings()
    )
    ticket_by_id = {ticket["id"]: ticket for ticket in tickets}
    ticket_order = sorted(
        ticket_by_id,
        key=lambda ticket_id: (
            ticket_by_id[ticket_id]["approved_at"] is None,
            _datetime_key(ticket_by_id[ticket_id]["approved_at"]),
            ticket_id,
        ),
    )
    priority = {ticket_id: index for index, ticket_id in enumerate(ticket_order)}
    budgets = {
        ticket_id: _money(ticket_by_id[ticket_id]["required_budget"])
        for ticket_id in ticket_order
    }
    remaining = dict(budgets)
    allocated = {ticket_id: Decimal("0.00") for ticket_id in ticket_order}
    latest_settled_at = {ticket_id: None for ticket_id in ticket_order}
    anomalous_ticket_ids = set()

    return_ticket_ids = {}
    for link in connection.execute(
        sa.select(return_links.c.return_id, return_links.c.ticket_id)
    ).mappings():
        return_ticket_ids.setdefault(link["return_id"], set()).add(link["ticket_id"])
    parcel_ticket_ids = {}
    for link in connection.execute(
        sa.select(parcel_links.c.parcel_return_id, parcel_links.c.ticket_id)
    ).mappings():
        parcel_ticket_ids.setdefault(link["parcel_return_id"], set()).add(link["ticket_id"])

    records = []
    for record in connection.execute(
        sa.select(
            returns.c.id,
            returns.c.ticket_id,
            returns.c.amount_spent,
            returns.c.settled_at,
        ).where(returns.c.settled_at.is_not(None))
    ).mappings():
        linked_ids = set(return_ticket_ids.get(record["id"], set()))
        if record["ticket_id"] is not None:
            linked_ids.add(record["ticket_id"])
        records.append(("return_detail", record, linked_ids))
    for record in connection.execute(
        sa.select(
            parcels.c.id,
            parcels.c.ticket_id,
            parcels.c.amount_spent,
            parcels.c.settled_at,
        ).where(parcels.c.settled_at.is_not(None))
    ).mappings():
        linked_ids = set(parcel_ticket_ids.get(record["id"], set()))
        if record["ticket_id"] is not None:
            linked_ids.add(record["ticket_id"])
        records.append(("parcel_return", record, linked_ids))

    records.sort(
        key=lambda entry: (
            _datetime_key(entry[1]["settled_at"]),
            entry[0],
            entry[1]["id"],
        )
    )
    for entity_type, record, linked_ids in records:
        linked_ids = {
            ticket_id for ticket_id in linked_ids if ticket_id in ticket_by_id
        }
        if not linked_ids:
            report(
                entity_type,
                record["id"],
                "settled_record_without_borrowing_ticket",
                "รายการมี settled_at แต่ไม่พบ BorrowingTicket ที่เชื่อมอยู่",
            )
            continue
        amount = _money(record["amount_spent"])
        if amount < 0:
            anomalous_ticket_ids.update(linked_ids)
            report(
                entity_type,
                record["id"],
                "negative_settled_amount",
                f"ยอด settled เป็นค่าติดลบ {amount}",
            )
            continue

        unallocated = amount
        ordered_linked_ids = sorted(
            linked_ids,
            key=lambda ticket_id: priority[ticket_id],
        )
        for ticket_id in ordered_linked_ids:
            if unallocated <= 0:
                break
            portion = min(
                unallocated,
                max(remaining[ticket_id], Decimal("0.00")),
            )
            if portion <= 0:
                continue
            allocated[ticket_id] += portion
            remaining[ticket_id] -= portion
            latest_settled_at[ticket_id] = record["settled_at"]
            unallocated -= portion

        if unallocated > 0:
            anomalous_ticket_ids.update(linked_ids)
            report(
                entity_type,
                record["id"],
                "settled_amount_exceeds_linked_budgets",
                f"มียอดเกินวงเงินของสัญญาที่เชื่อมอยู่ {unallocated} บาท",
            )

    for ticket_id in ticket_order:
        ticket = ticket_by_id[ticket_id]
        budget = budgets[ticket_id]
        settled_at = None
        if budget <= 0:
            report(
                "borrowing_ticket",
                ticket_id,
                "invalid_required_budget",
                f"required_budget ต้องมากกว่า 0 แต่พบ {budget}",
            )
        elif (
            ticket_id not in anomalous_ticket_ids
            and ticket["approved_at"] is not None
            and allocated[ticket_id] == budget
        ):
            settled_at = latest_settled_at[ticket_id]

        connection.execute(
            tickets_table.update()
            .where(tickets_table.c.id == ticket_id)
            .values(settled_at=settled_at)
        )

        if ticket["closed_date"] is not None and allocated[ticket_id] != budget:
            report(
                "borrowing_ticket",
                ticket_id,
                "borrower_closed_finance_settlement_incomplete",
                "closed_date ระบุว่าผู้ยืมส่งใช้ครบ แต่ยอดที่ settled ทางการเงิน "
                f"คือ {allocated[ticket_id]} จาก required_budget {budget}",
            )


def downgrade():
    # Backfilled timestamps are intentionally retained.  Downgrading the prior
    # schema migration removes those columns if a full rollback is required.
    op.drop_index(
        "ix_settlement_backfill_issue_entity_id",
        table_name=ISSUE_TABLE,
    )
    op.drop_index(
        "ix_settlement_backfill_issue_entity_type",
        table_name=ISSUE_TABLE,
    )
    op.drop_table(ISSUE_TABLE)
