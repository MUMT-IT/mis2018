"""Last finance edit metadata, written in the business transaction.

Only authenticated finance views set the request actor. Background jobs and
other roles leave the last finance edit intact. This is latest-edit metadata,
not an append-only history. Bulk SQL writes bypass this ORM listener.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import g, has_request_context
from sqlalchemy import Column, DateTime, ForeignKey, Integer, event
from sqlalchemy.orm import Session, declared_attr


class FinanceEditMixin:
    last_edited_at = Column(DateTime(timezone=True), nullable=True)

    @declared_attr
    def last_edited_by_id(cls):
        return Column(Integer, ForeignKey("staff_account.id"), nullable=True)


@event.listens_for(Session, "before_flush")
def stamp_finance_edits(session, flush_context, instances):
    if not has_request_context():
        return
    actor_id = getattr(g, "advance_payment_finance_actor_id", None)
    if actor_id is None:
        return

    # Store an aware ICT timestamp. A flush shares one time for all records.
    edited_at = datetime.now(ZoneInfo("Asia/Bangkok"))
    for record in set(session.new).union(session.dirty):
        if not isinstance(record, FinanceEditMixin) or record in session.deleted:
            continue
        if record in session.new or session.is_modified(record, include_collections=True):
            record.last_edited_at = edited_at
            record.last_edited_by_id = actor_id
