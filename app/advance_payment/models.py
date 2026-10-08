from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, CheckConstraint, Column, Index, Table, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func, inspect, select, text
from flask import g, has_request_context
from sqlalchemy import event
from sqlalchemy.orm import Session, declared_attr, object_session, relationship
from app.main import db
from app.staff.models import StaffAccount


MONEY_DEFAULT = Decimal("0.00")


def _current_fiscal_year():
    today = datetime.now().date()
    return today.year + 1 if today.month >= 10 else today.year


def _staff_name(staff):
    if staff is None:
        return None
    try:
        return staff.fullname or staff.email
    except (AttributeError, TypeError):
        return staff.email


def _staff_department(staff):
    personal_info = getattr(staff, "personal_info", None)
    organization = getattr(personal_info, "org", None)
    return getattr(organization, "name", None)


def _staff_org(staff):
    personal_info = getattr(staff, "personal_info", None)
    return getattr(personal_info, "org", None)


def _staff_position(staff):
    personal_info = getattr(staff, "personal_info", None)
    return (
        getattr(personal_info, "position", None)
        or getattr(getattr(personal_info, "job_position", None), "position", None)
    )


def _staff_role(staff):
    role_names = {
        role.role_need
        for role in (getattr(staff, "roles", None) or [])
        if getattr(role, "role_need", None)
    }
    for role_name in ("finance", "secretary", "cash_management_coordinator"):
        if role_name in role_names:
            return role_name
    return None


if not hasattr(StaffAccount, "name"):
    StaffAccount.name = property(_staff_name)
if not hasattr(StaffAccount, "department"):
    StaffAccount.department = property(_staff_department)
if not hasattr(StaffAccount, "org"):
    StaffAccount.org = property(_staff_org)
if not hasattr(StaffAccount, "position"):
    StaffAccount.position = property(_staff_position)
if not hasattr(StaffAccount, "role"):
    StaffAccount.role = property(_staff_role)
if not hasattr(StaffAccount, "check_password"):
    StaffAccount.check_password = StaffAccount.verify_password
if not hasattr(StaffAccount, "set_password"):
    StaffAccount.set_password = lambda staff, password: setattr(staff, "password", password)


def _session_get(session, model, primary_key):
    if session is None or primary_key is None:
        return None

    getter = getattr(session, "get", None)
    if callable(getter):
        return getter(model, primary_key)
    return session.query(model).get(primary_key)


class FinanceEditMixin:
    """Latest finance edit, persisted in the same transaction as the change."""

    last_edited_at = Column(DateTime(timezone=True), nullable=True)

    @declared_attr
    def last_edited_by_id(cls):
        return Column(Integer, ForeignKey("staff_account.id"), nullable=True)

    @declared_attr
    def last_edited_by(cls):
        return relationship(
            StaffAccount,
            foreign_keys=lambda: [cls.last_edited_by_id],
        )


@event.listens_for(Session, "before_flush")
def _stamp_finance_edits(session, flush_context, instances):
    if not has_request_context():
        return
    actor_id = getattr(g, "advance_payment_finance_actor_id", None)
    if actor_id is None:
        return
    edited_at = datetime.now(ZoneInfo("Asia/Bangkok"))
    for record in set(session.new).union(session.dirty):
        if not isinstance(record, FinanceEditMixin) or record in session.deleted:
            continue
        if record in session.new or session.is_modified(record, include_collections=True):
            record.last_edited_at = edited_at
            record.last_edited_by_id = actor_id


class CashAdvanceBorrowingTicket(FinanceEditMixin, db.Model):
    __tablename__ = "cash_advance_borrowing_tickets"
    __table_args__ = (
        Index(
            "ix_cash_advance_borrowing_tickets_settled_approved",
            "settled_at",
            "approved_at",
        ),
    )

    id = Column(Integer, primary_key=True)
    number = Column(String, nullable=True)
    borrowing_approval_ref_no = Column(String(255), nullable=True)
    borrowing_approval_date = Column(Date, nullable=True)
    creator_id = Column(Integer, ForeignKey("staff_account.id"), nullable=False)
    borrower_id = Column(Integer, ForeignKey("staff_account.id"), nullable=False)
    status = Column(String(64), nullable=False, default="กำลังส่งคำขอ")
    borrowing_ticket_purpose = Column(String(255), nullable=False)
    required_budget = Column(Numeric(12, 2, asdecimal=True), nullable=False)
    account_number = Column(String(100), nullable=False)
    bank_account_info_id = Column(Integer, ForeignKey("cash_mng_bank_account_infos.id"), nullable=True)
    borrowing_ticket_start_date = Column(Date, nullable=False)
    borrowing_ticket_end_date = Column(Date, nullable=False)
    finance_verified = Column(Boolean, nullable=False, default=False)
    due_date = Column(Date, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    approved_at = Column(DateTime, nullable=True)
    closed_date = Column(DateTime, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    reject_approved_at = Column(DateTime, nullable=True)
    rejection_comment = Column(String(1000), nullable=True)
    finance_note = Column(String(2000), nullable=True)
    aip_ref_no = Column(String(255), nullable=False)
    aip_ref_date = Column(Date, nullable=False)
    last_notified_type = Column(String(50), nullable=True)
    last_notified_date = Column(Date, nullable=True)

    bank_account_info = relationship(
        "BankAccountInfo",
        foreign_keys=[bank_account_info_id],
    )
    creator_user = relationship(
        StaffAccount,
        foreign_keys=[creator_id],
    )
    borrower_user = relationship(
        StaffAccount,
        foreign_keys=[borrower_id],
    )
    notification = relationship(
        "CashManagementNotifications",
        back_populates="ticket",
        uselist=False,
    )

    @property
    def borrower_name(self):
        cached_name = getattr(self, "_borrower_name", None)
        if cached_name is not None:
            return cached_name
        borrower_user = self.borrower_user
        return _staff_name(borrower_user)

    @borrower_name.setter
    def borrower_name(self, value):
        self._borrower_name = value

    @property
    def creator_name(self):
        cached_name = getattr(self, "_creator_name", None)
        if cached_name is not None:
            return cached_name
        creator_user = self.creator_user
        return _staff_name(creator_user)

    @creator_name.setter
    def creator_name(self, value):
        self._creator_name = value

    @property
    def borrower_email(self):
        cached_email = getattr(self, "_borrower_email", None)
        if cached_email is not None:
            return cached_email
        borrower_user = self.borrower_user
        return borrower_user.email if borrower_user else None

    @borrower_email.setter
    def borrower_email(self, value):
        self._borrower_email = value

    @property
    def borrowing_ticket_name(self):
        return self.borrowing_ticket_purpose

    @borrowing_ticket_name.setter
    def borrowing_ticket_name(self, value):
        self.borrowing_ticket_purpose = value

BorrowingTicket = CashAdvanceBorrowingTicket

class CashManagementNotifications(db.Model):
    __tablename__ = "cash_mng_notifications"

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("cash_advance_borrowing_tickets.id"), nullable=False, unique=True)
    borrower_id = Column(Integer, ForeignKey("staff_account.id"), nullable=False)

    ticket = relationship(
        "CashAdvanceBorrowingTicket",
        back_populates="notification",
        foreign_keys=[ticket_id],
    )
    borrower = relationship(
        StaffAccount,
        foreign_keys=[borrower_id],
    )


Notifications = CashManagementNotifications


document_return_association = Table(
    "cash_mng_document_return_association",
    db.metadata,
    Column("document_id", Integer, ForeignKey("cash_mng_documents.id"), primary_key=True),
    Column("return_id", Integer, ForeignKey("cash_advance_return_details.id"), primary_key=True),
)


# A return ticket may settle receipts from more than one borrowing ticket.
# ``ReturnDetail.ticket_id`` is kept for backwards compatibility and stores the
# first/primary ticket; this table is the source of the additional links.
return_borrowing_ticket_association = Table(
    "cash_advance_return_borrowing_ticket_association",
    db.metadata,
    Column("return_id", Integer, ForeignKey("cash_advance_return_details.id"), primary_key=True),
    Column("ticket_id", Integer, ForeignKey("cash_advance_borrowing_tickets.id"), primary_key=True),
)

parcel_borrowing_ticket_association = Table(
    "cash_advance_parcel_borrowing_ticket_association",
    db.metadata,
    Column("parcel_return_id", Integer, ForeignKey("cash_mng_parcel_return_details.id"), primary_key=True),
    Column("ticket_id", Integer, ForeignKey("cash_advance_borrowing_tickets.id"), primary_key=True),
)


class Document(FinanceEditMixin, db.Model):
    __tablename__ = "cash_mng_documents"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False, default="#")
    created_at = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now())


class ClosingDocumentRecordMixin(FinanceEditMixin):
    """Current association and history come from links, never copied document names."""

    @declared_attr
    def closing_links(cls):
        return relationship(
            "ClosingDocumentLink",
            foreign_keys="ClosingDocumentLink." + cls._closing_fk,
            back_populates=cls._closing_record,
            order_by="ClosingDocumentLink.id",
        )

    @property
    def closing_document(self):
        return next((link.document for link in self.closing_links
                     if link.is_active and link.document.is_active is not False), None)

    @closing_document.setter
    def closing_document(self, document):
        if document is not None and document.is_active is False:
            raise ValueError("Cannot attach a record to a cancelled closing document")
        if self.closing_document is document:
            return
        for link in self.closing_links:
            link.is_active = False
        session = object_session(self)
        if session is not None:
            session.flush()  # Release the unique active association before inserting.
        if document is not None:
            link = next((link for link in self.closing_links if link.document is document), None)
            if link is None:
                self.closing_links.append(ClosingDocumentLink(document=document, is_active=True))
            else:
                link.is_active = True

    @property
    def closing_document_id(self):
        document = self.closing_document
        return document.id if document else None

    @property
    def closing_document_name(self):
        document = self.closing_document
        return document.document_number if document else None

    @property
    def historical_closing_documents(self):
        return [link.document for link in self.closing_links
                if not link.is_active or link.document.is_active is False]

    @property
    def old_document_number(self):
        return ", ".join(doc.document_number for doc in self.historical_closing_documents)


class ReturnDetail(ClosingDocumentRecordMixin, db.Model):
    _closing_fk = "ticket_return_id"
    _closing_record = "ticket_return"
    __tablename__ = "cash_advance_return_details" # use cash_advance_payment_receipt_detail

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("cash_advance_borrowing_tickets.id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("staff_account.id"), nullable=True, index=True)
    amount_spent = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=MONEY_DEFAULT)
    proof_reference = Column(String(255), nullable=False, default="")
    status = Column(String(32), nullable=False, default="รอตรวจสอบ")
    created_at = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now())
    approved_at = Column(DateTime, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    reject_approved_at = Column(DateTime, nullable=True)
    rejection_comment = Column(String(4000), nullable=True)
    note = Column(String(2000), nullable=True)
    reference_number = Column(String(255), nullable=True)
    reference_date = Column(Date, nullable=True)
    product_code_id = Column(String(12), ForeignKey("product_codes.id"), nullable=True)
    cost_center_id = Column(String(12), ForeignKey("cost_centers.id"), nullable=True)
    iocode_id = Column(String(16), ForeignKey("iocodes.id"), nullable=True)
    fiscal_year = Column(Integer, nullable=False, default=_current_fiscal_year)
    product_code = relationship("ProductCode")
    cost_center = relationship("CostCenter")
    iocode = relationship("IOCode")
    borrowing_ticket = relationship(
        "CashAdvanceBorrowingTicket",
        foreign_keys=[ticket_id],
    )
    creator = relationship(
        StaffAccount,
        foreign_keys=[creator_id],
    )
    linked_borrowing_tickets = relationship(
        "CashAdvanceBorrowingTicket",
        secondary=return_borrowing_ticket_association,
        order_by="CashAdvanceBorrowingTicket.id",
    )
    receipt_items = relationship(
        "ReturnReceiptItem",
        back_populates="return_detail",
        foreign_keys="ReturnReceiptItem.return_detail_id",
        order_by="ReturnReceiptItem.id",
    )
    proof_files = relationship(
        "ReturnProofFile",
        back_populates="return_detail",
        foreign_keys="ReturnProofFile.return_detail_id",
        order_by="ReturnProofFile.id",
    )
    documents = relationship(
        "Document",
        secondary=document_return_association,
        order_by="Document.id",
    )

    @property
    def borrowing_tickets(self):
        """All borrowing tickets settled by this return, including legacy data."""
        session = object_session(self)
        if session is None or self.id is None:
            return [self.borrowing_ticket] if self.borrowing_ticket else []
        tickets = []
        if self.ticket_id:
            ticket = _session_get(session, CashAdvanceBorrowingTicket, self.ticket_id)
            if ticket:
                tickets.append(ticket)
        linked = (
            session.query(CashAdvanceBorrowingTicket)
            .join(
                return_borrowing_ticket_association,
                CashAdvanceBorrowingTicket.id == return_borrowing_ticket_association.c.ticket_id,
            )
            .filter(return_borrowing_ticket_association.c.return_id == self.id)
            .order_by(CashAdvanceBorrowingTicket.id.asc())
            .all()
        )
        seen = {ticket.id for ticket in tickets}
        tickets.extend(ticket for ticket in linked if ticket.id not in seen)
        return tickets

    @property
    def closing_amount(self):
        """Amount eligible for a closing document, excluding cash returns."""
        items = self.receipt_items
        if not items:
            return Decimal(str(self.amount_spent or 0))
        return sum(
            (
                Decimal(str(item.amount or 0))
                for item in items
                if not item.is_cash
                and not (
                    (item.store_name or "").strip() == "-"
                    and (item.description or "").strip() == "เงินเหลือส่งใช้เงินยืม"
                )
            ),
            Decimal("0"),
        )

class ReturnReceiptItem(FinanceEditMixin, db.Model):
    __tablename__ = "cash_advance_return_receipt_items"

    id = Column(Integer, primary_key=True)
    return_detail_id = Column(Integer, ForeignKey("cash_advance_return_details.id"), nullable=False)
    receipt_date = Column(Date, nullable=False)
    store_name = Column(String(255), nullable=False, default="")
    description = Column(String(255), nullable=False, default="")
    amount = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=MONEY_DEFAULT)
    created_at = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now())
    is_cash = Column(Boolean, nullable=False, default=False, server_default=text("false"))

    return_detail = relationship(
        "ReturnDetail",
        back_populates="receipt_items",
        foreign_keys=[return_detail_id],
    )
    proof_files = relationship(
        "ReturnProofFile",
        back_populates="receipt_item",
        foreign_keys="ReturnProofFile.return_receipt_item_id",
        order_by="ReturnProofFile.id",
    )


def _validate_return_receipt_item_cash_type(existing_types, is_cash):
    """Reject mixed cash and non-cash items within one ReturnDetail."""
    expected_type = bool(is_cash)
    if any(bool(existing_type) != expected_type for existing_type in existing_types):
        raise ValueError(
            "ReturnReceiptItem rows in one ReturnDetail must all have the same is_cash value"
        )


@event.listens_for(Session, "before_flush")
def _enforce_return_receipt_item_cash_invariant(session, flush_context, instances):
    tracked_items = {
        item
        for item in set(session.new).union(session.dirty).union(session.deleted)
        if isinstance(item, ReturnReceiptItem)
    }
    if not tracked_items:
        return

    affected_detail_ids = {
        item.return_detail_id
        for item in tracked_items
        if item.return_detail_id is not None
    }
    for item in tracked_items:
        history = inspect(item).attrs.return_detail_id.history
        affected_detail_ids.update(
            detail_id for detail_id in history.deleted if detail_id is not None
        )

    tracked_item_ids = {
        item.id for item in tracked_items if item.id is not None
    }
    for return_detail_id in affected_detail_ids:
        statement = select(ReturnReceiptItem.is_cash).where(
            ReturnReceiptItem.return_detail_id == return_detail_id
        )
        if tracked_item_ids:
            statement = statement.where(
                ReturnReceiptItem.id.notin_(tracked_item_ids)
            )

        item_types = [row[0] for row in session.execute(statement)]
        item_types.extend(
            item.is_cash
            for item in tracked_items
            if item not in session.deleted
            and item.return_detail_id == return_detail_id
        )
        if item_types:
            _validate_return_receipt_item_cash_type(
                item_types[1:],
                item_types[0],
            )


class ReturnProofFile(FinanceEditMixin, db.Model):
    __tablename__ = "cash_advance_return_proof_files"

    id = Column(Integer, primary_key=True)
    return_detail_id = Column(Integer, ForeignKey("cash_advance_return_details.id"), nullable=False)
    return_receipt_item_id = Column(Integer, ForeignKey("cash_advance_return_receipt_items.id"), nullable=True)
    proof_reference = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now())

    return_detail = relationship(
        "ReturnDetail",
        back_populates="proof_files",
        foreign_keys=[return_detail_id],
    )
    receipt_item = relationship(
        "ReturnReceiptItem",
        back_populates="proof_files",
        foreign_keys=[return_receipt_item_id],
    )


class ParcelReturnDetail(ClosingDocumentRecordMixin, db.Model):
    _closing_fk = "parcel_return_id"
    _closing_record = "parcel_return"
    __tablename__ = "cash_mng_parcel_return_details"
    __table_args__ = (
        CheckConstraint(
            "type IS NULL OR type IN (1, 5)",
            name="ck_cash_mng_parcel_return_details_type",
        ),
        CheckConstraint(
            "(ticket_id IS NOT NULL AND fund_request_id IS NULL) OR "
            "(ticket_id IS NULL AND fund_request_id IS NOT NULL)",
            name="ck_cash_mng_parcel_return_details_exactly_one_parent",
        ),
    )

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("cash_advance_borrowing_tickets.id"), nullable=True)
    fund_request_id = Column(Integer, ForeignKey("petty_cash_fund_requests.id"), nullable=True)
    amount_spent = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=MONEY_DEFAULT)
    items_description = Column(String(1000), nullable=False)
    sent_date = Column(Date, nullable=False)
    type = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False, default="รอตรวจสอบ")
    created_at = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now())
    approved_at = Column(DateTime, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    transferred_at = Column(Date, nullable=True)
    rejection_comment = Column(String(4000), nullable=True)

    borrowing_ticket = relationship(
        "CashAdvanceBorrowingTicket",
        foreign_keys=[ticket_id],
    )
    fund_request = relationship(
        "FundRequest",
        foreign_keys=[fund_request_id],
    )
    linked_borrowing_tickets = relationship(
        "CashAdvanceBorrowingTicket",
        secondary=parcel_borrowing_ticket_association,
        order_by="CashAdvanceBorrowingTicket.id",
    )


class ClosingDocument(FinanceEditMixin, db.Model):
    __tablename__ = "cash_mng_closing_documents"

    id = Column(Integer, primary_key=True)
    document_number = Column(String(255), nullable=False, unique=True)
    filing_date = Column(Date, nullable=False)
    total_amount = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=MONEY_DEFAULT)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    settled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    links = relationship("ClosingDocumentLink", back_populates="document", order_by="ClosingDocumentLink.id")

    @property
    def is_settled(self):
        return self.settled_at is not None


class ClosingDocumentLink(FinanceEditMixin, db.Model):
    __tablename__ = "cash_mng_closing_document_links"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN ticket_return_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN parcel_return_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN claim_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_closing_link_one_record",
        ),
        *tuple(constraint for field in ("ticket_return_id", "parcel_return_id", "claim_id")
               for constraint in (
                   UniqueConstraint("document_id", field, name="uq_closing_link_doc_" + field),
                   Index("uq_closing_link_active_" + field, field, unique=True,
                         postgresql_where=text("is_active"), sqlite_where=text("is_active = 1")),
               )),
    )

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("cash_mng_closing_documents.id"), nullable=False, index=True)
    ticket_return_id = Column(Integer, ForeignKey("cash_advance_return_details.id"), nullable=True)
    parcel_return_id = Column(Integer, ForeignKey("cash_mng_parcel_return_details.id"), nullable=True)
    claim_id = Column(Integer, ForeignKey("petty_cash_claim_details.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    document = relationship("ClosingDocument", back_populates="links")
    ticket_return = relationship("ReturnDetail", back_populates="closing_links")
    parcel_return = relationship("ParcelReturnDetail", back_populates="closing_links")
    claim = relationship("PettyCashClaimDetail", back_populates="closing_links")

    @property
    def record(self):
        return self.ticket_return or self.parcel_return or self.claim


class PettyCashSetting(FinanceEditMixin, db.Model):
    __tablename__ = "petty_cash_settings"
    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "fiscal_year",
            name="uq_petty_cash_settings_org_fiscal_year",
        ),
    )

    id = Column(Integer, primary_key=True)
    fiscal_year = Column(Integer, nullable=False)
    org_id = Column(Integer, ForeignKey("orgs.id"), nullable=False)
    budget = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=MONEY_DEFAULT)
    bank_account_info_id = Column(Integer, ForeignKey("cash_mng_bank_account_infos.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    valid = Column(Boolean, nullable=False, default=True)
    custodian_id = Column(Integer, ForeignKey("staff_account.id"), nullable=True)

    org = relationship(
        "Org",
        foreign_keys=[org_id],
    )
    bank_account_info = relationship(
        "BankAccountInfo",
        foreign_keys=[bank_account_info_id],
    )
    custodian = relationship(
        StaffAccount,
        foreign_keys=[custodian_id],
    )

    @property
    def department_name(self):
        return getattr(self.org, "name", None)

    @property
    def custodian_name(self):
        return getattr(self.custodian, "name", None) or getattr(self.custodian, "fullname", None)

    @property
    def account_number(self):
        account = self.bank_account_info
        if account is not None:
            return getattr(account, "account_number", None)

        # Keep legacy settings usable when the FK was not backfilled.
        session = object_session(self)
        if session is not None and self.org_id:
            account = (
                session.query(BankAccountInfo)
                .filter_by(org_id=self.org_id, record_type="petty_cash")
                .order_by(BankAccountInfo.id.asc())
                .first()
            )
            if account is not None:
                return account.account_number
        return None

class PettyCashFiscalYearCarryover(FinanceEditMixin, db.Model):
    """ข้อมูลยกยอดเงินสดย่อยที่กรอกโดยฝ่ายการเงิน."""

    __tablename__ = "petty_cash_fiscal_year_carryovers"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "source_fiscal_year", "target_fiscal_year",
            name="uq_petty_cash_carryover_org_years",
        ),
    )

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("orgs.id"), nullable=False, index=True)
    source_fiscal_year = Column(Integer, nullable=False)
    target_fiscal_year = Column(Integer, nullable=False)
    finance_budget = Column(Numeric(12, 2), nullable=True)
    finance_pending_transfer = Column(Numeric(12, 2), nullable=True)
    custodian_bank_balance = Column(Numeric(12, 2), nullable=True)
    custodian_cash_on_hand = Column(Numeric(12, 2), nullable=True)
    custodian_pending_budget = Column(Numeric(12, 2), nullable=True)
    finance_updated_at = Column(DateTime(timezone=True), nullable=True)
    custodian_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    org = relationship(
        "Org",
        foreign_keys=[org_id],
    )

    @property
    def department_name(self):
        return getattr(self.org, "name", None)

    @property
    def is_complete(self):
        return all(
            value is not None
            for value in (
                self.finance_budget,
                self.finance_pending_transfer,
                self.custodian_bank_balance,
                self.custodian_cash_on_hand,
                self.custodian_pending_budget,
            )
        )

    @property
    def reconciliation_amount(self):
        if not self.is_complete:
            return None
        return (
            self.finance_budget
            - (
                self.custodian_bank_balance
                + self.custodian_cash_on_hand
                + self.custodian_pending_budget
                + self.finance_pending_transfer
            )
        )


class BankAccountInfo(FinanceEditMixin, db.Model):
    __tablename__ = "cash_mng_bank_account_infos"
    __table_args__ = (
        UniqueConstraint(
            "record_type",
            "thai_name",
            name="uq_cash_mng_bank_account_infos_record_type_thai_name",
        ),
        UniqueConstraint(
            "account_number",
            name="uq_cash_mng_bank_account_infos_account_number",
        ),
    )

    id = Column(Integer, primary_key=True)
    record_type = Column(String(32), nullable=False)
    org_id = Column(Integer, ForeignKey("orgs.id"), nullable=True, index=True)
    thai_name = Column(String(255), nullable=False)
    account_number = Column(String(10), nullable=False)
    closed_at = Column(DateTime, nullable=True)

    org = relationship(
        "Org",
        foreign_keys=[org_id],
    )

    @property
    def cash_advance_managers(self):
        return [
            link.staff
            for link in self.cash_advance_manager_links
            if link.staff is not None
        ]


class CashAdvanceAccountManager(db.Model):
    """Staff accounts allowed to manage an organization's cash-advance account."""

    __tablename__ = "cash_advance_account_managers"
    __table_args__ = (
        UniqueConstraint(
            "bank_account_info_id",
            "staff_account_id",
            name="uq_cash_advance_account_manager",
        ),
    )

    id = Column(Integer, primary_key=True)
    bank_account_info_id = Column(
        Integer,
        ForeignKey("cash_mng_bank_account_infos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    staff_account_id = Column(
        Integer,
        ForeignKey("staff_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    bank_account = relationship(
        "BankAccountInfo",
        backref=db.backref(
            "cash_advance_manager_links",
            cascade="all, delete-orphan",
            order_by="CashAdvanceAccountManager.id",
        ),
    )
    staff = relationship(StaffAccount)


class FundRequest(FinanceEditMixin, db.Model):
    __tablename__ = "petty_cash_fund_requests"

    id = Column(Integer, primary_key=True)
    requester_id = Column(Integer, ForeignKey("staff_account.id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("staff_account.id"), nullable=True, index=True)
    org_id = Column(Integer, ForeignKey("orgs.id"), nullable=True, index=True)
    petty_cash_setting_id = Column(Integer, ForeignKey("petty_cash_settings.id"), nullable=True, index=True)
    borrowing_ticket_id = Column(Integer, ForeignKey("cash_advance_borrowing_tickets.id"), nullable=True)
    form_type = Column(String(10), nullable=False)
    ticket_number = Column(String(64), nullable=True)
    request_date = Column(Date, nullable=True)
    status = Column(String(64), nullable=False, default="รอการอนุมัติ")
    amount = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=MONEY_DEFAULT)
    is_legacy_import = Column(Boolean, nullable=False, default=False, server_default=text("false"), index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now())
    confirmed_at = Column(DateTime, nullable=True)
    confirmed_by_id = Column(Integer, ForeignKey("staff_account.id"), nullable=True, index=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by_id = Column(Integer, ForeignKey("staff_account.id"), nullable=True, index=True)
    cancel_at = Column(DateTime, nullable=True)
    cancel_transferred_at = Column(Date, nullable=True)
    rejection_comment = Column(String(4000), nullable=True)
    purpose = Column(String(1000), nullable=True)
    personal_note = Column(String(2000), nullable=True)
    period_year = Column(String(10), nullable=True)
    withdrawal_proof_reference = Column(String(500), nullable=True)
    withdrawal_proof_filename = Column(String(255), nullable=True)

    requester = relationship(StaffAccount, foreign_keys=[requester_id])
    creator = relationship(StaffAccount, foreign_keys=[creator_id])
    confirmed_by = relationship(StaffAccount, foreign_keys=[confirmed_by_id])
    approved_by = relationship(StaffAccount, foreign_keys=[approved_by_id])
    org = relationship(
        "Org",
        foreign_keys=[org_id],
    )
    petty_cash_setting = relationship(
        "PettyCashSetting",
        foreign_keys=[petty_cash_setting_id],
    )
    borrowing_ticket = relationship(
        "CashAdvanceBorrowingTicket",
        foreign_keys=[borrowing_ticket_id],
    )
    items = relationship(
        "FundRequestItem",
        back_populates="fund_request",
        foreign_keys="FundRequestItem.fund_request_id",
        order_by="FundRequestItem.id",
    )

    @property
    def department_name(self):
        org = self.org
        return getattr(org, "name", None)

    @property
    def requester_name(self):
        ticket = self.borrowing_ticket
        return (
            getattr(ticket, "borrower_name", None)
            or getattr(self.requester, "name", None)
            or getattr(self.requester, "fullname", None)
        )

    @property
    def requester_position(self):
        return getattr(self.requester, "position", None)

    @property
    def account_number(self):
        ticket = self.borrowing_ticket
        if ticket and getattr(ticket, "account_number", None):
            return ticket.account_number

        setting_org = self.org
        if setting_org is None:
            return None

        session = object_session(self)
        if session is None:
            return None

        today = datetime.now().date()
        current_fiscal_year = today.year + 1 if today.month >= 10 else today.year
        setting = (
            session.query(PettyCashSetting)
            .filter_by(org_id=getattr(setting_org, "id", None), fiscal_year=current_fiscal_year, valid=True)
            .first()
        )
        if setting is not None:
            return getattr(setting, "account_number", None)
        return None

class FundRequestItem(FinanceEditMixin, db.Model):
    __tablename__ = "petty_cash_fund_request_items"

    id = Column(Integer, primary_key=True)
    fund_request_id = Column(Integer, ForeignKey("petty_cash_fund_requests.id"), nullable=False)
    description = Column(String(255), nullable=False)
    amount = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=MONEY_DEFAULT)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    category_type = Column(Integer, nullable=False, default=1) # use id instead

    fund_request = relationship(
        "FundRequest",
        back_populates="items",
        foreign_keys=[fund_request_id],
    )


document_petty_claim_association = Table(
    "cash_mng_document_petty_claim_association",
    db.metadata,
    Column("document_id", Integer, ForeignKey("cash_mng_documents.id"), primary_key=True),
    Column("claim_id", Integer, ForeignKey("petty_cash_claim_details.id"), primary_key=True),
)


class PettyCashClaimDetail(ClosingDocumentRecordMixin, db.Model):
    _closing_fk = "claim_id"
    _closing_record = "claim"
    __tablename__ = "petty_cash_claim_details" # use petty_cash_payment_receipt_detail

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("staff_account.id"), nullable=False)
    claim_number = Column("Claim_number", String(255), nullable=True)
    status = Column(String(32), nullable=False, default="ฉบับร่าง")
    petty_cash_setting_id = Column(Integer, ForeignKey("petty_cash_settings.id"), nullable=False)
    fund_request_id = Column(Integer, ForeignKey("petty_cash_fund_requests.id"), nullable=True)
    total_amount = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=MONEY_DEFAULT)
    approved_at = Column(DateTime, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    rejection_comment = Column(String(4000), nullable=True)
    note = Column(String(2000), nullable=True)
    transferred_at = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now())
    reference_number = Column(String(255), nullable=True)
    reference_date = Column(Date, nullable=True)
    product_code_id = Column(String(12), ForeignKey("product_codes.id"), nullable=True)
    cost_center_id = Column(String(12), ForeignKey("cost_centers.id"), nullable=True)
    iocode_id = Column(String(16), ForeignKey("iocodes.id"), nullable=True)
    fiscal_year = Column(Integer, nullable=False, default=_current_fiscal_year)
    product_code = relationship("ProductCode")
    cost_center = relationship("CostCenter")
    iocode = relationship("IOCode")
    user = relationship(
        StaffAccount,
        foreign_keys=[user_id],
    )
    petty_cash_setting = relationship(
        "PettyCashSetting",
        foreign_keys=[petty_cash_setting_id],
    )
    fund_request = relationship(
        "FundRequest",
        foreign_keys=[fund_request_id],
    )
    items = relationship(
        "PettyCashClaimItem",
        back_populates="claim",
        foreign_keys="PettyCashClaimItem.claim_id",
        order_by="PettyCashClaimItem.id",
    )
    proof_files = relationship(
        "PettyCashClaimProofFile",
        back_populates="claim",
        foreign_keys="PettyCashClaimProofFile.claim_id",
        order_by="PettyCashClaimProofFile.id",
    )
    documents = relationship(
        "Document",
        secondary=document_petty_claim_association,
        order_by="Document.id",
    )

    @property
    def reference_files(self):
        """Files attached to the principle-approval reference, not to a receipt item."""
        session = object_session(self)
        if session is None or self.id is None:
            return []
        return (
            session.query(PettyCashClaimProofFile)
            .filter(
                PettyCashClaimProofFile.claim_id == self.id,
                PettyCashClaimProofFile.claim_item_id.is_(None),
            )
            .order_by(PettyCashClaimProofFile.id.asc())
            .all()
        )


class PettyCashClaimItem(FinanceEditMixin, db.Model):
    __tablename__ = "petty_cash_claim_items"

    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("petty_cash_claim_details.id"), nullable=False)
    receipt_date = Column(Date, nullable=False)
    description = Column(String(255), nullable=False, default="")
    amount = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=MONEY_DEFAULT)
    created_at = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now())
    category_type = Column(Integer, nullable=False, default=1)

    claim = relationship(
        "PettyCashClaimDetail",
        back_populates="items",
        foreign_keys=[claim_id],
    )
    proof_files = relationship(
        "PettyCashClaimProofFile",
        back_populates="claim_item",
        foreign_keys="PettyCashClaimProofFile.claim_item_id",
        order_by="PettyCashClaimProofFile.id",
    )


def _validate_petty_cash_claim_item_category_group(existing_categories, category_type):
    """Reject mixing category 6 with ordinary items in one claim."""
    is_cash_return = int(category_type or 0) == 6
    if any((int(category or 0) == 6) != is_cash_return for category in existing_categories):
        raise ValueError(
            "PettyCashClaimItem rows in one PettyCashClaimDetail must be all "
            "category 6 or all non-category 6"
        )


@event.listens_for(Session, "before_flush")
def _enforce_petty_cash_claim_item_category_invariant(session, flush_context, instances):
    tracked_items = {
        item
        for item in set(session.new).union(session.dirty).union(session.deleted)
        if isinstance(item, PettyCashClaimItem)
    }
    if not tracked_items:
        return

    affected_claim_ids = {
        item.claim_id
        for item in tracked_items
        if item.claim_id is not None
    }
    for item in tracked_items:
        history = inspect(item).attrs.claim_id.history
        affected_claim_ids.update(
            claim_id for claim_id in history.deleted if claim_id is not None
        )

    tracked_item_ids = {
        item.id for item in tracked_items if item.id is not None
    }
    for claim_id in affected_claim_ids:
        statement = select(PettyCashClaimItem.category_type).where(
            PettyCashClaimItem.claim_id == claim_id
        )
        if tracked_item_ids:
            statement = statement.where(
                PettyCashClaimItem.id.notin_(tracked_item_ids)
            )

        category_types = [row[0] for row in session.execute(statement)]
        category_types.extend(
            item.category_type
            for item in tracked_items
            if item not in session.deleted
            and item.claim_id == claim_id
        )
        if category_types:
            _validate_petty_cash_claim_item_category_group(
                category_types[1:],
                category_types[0],
            )


class PettyCashClaimProofFile(FinanceEditMixin, db.Model):
    __tablename__ = "petty_cash_claim_proof_files"

    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("petty_cash_claim_details.id"), nullable=False)
    claim_item_id = Column(Integer, ForeignKey("petty_cash_claim_items.id"), nullable=True)
    proof_reference = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now())

    claim = relationship(
        "PettyCashClaimDetail",
        back_populates="proof_files",
        foreign_keys=[claim_id],
    )
    claim_item = relationship(
        "PettyCashClaimItem",
        back_populates="proof_files",
        foreign_keys=[claim_item_id],
    )
