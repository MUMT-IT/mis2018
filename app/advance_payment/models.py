from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, CheckConstraint, Column, Index, Table, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func, text
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


def _query_related_list(parent, model, fk_column_name):
    session = object_session(parent)
    parent_id = getattr(parent, "id", None)
    if session is None or parent_id is None:
        return []

    fk_column = getattr(model, fk_column_name)
    return session.query(model).filter(fk_column == parent_id).order_by(model.id.asc()).all()


def _query_many_to_many_list(parent, association_table, parent_fk_name, model):
    session = object_session(parent)
    parent_id = getattr(parent, "id", None)
    if session is None or parent_id is None:
        return []

    return (
        session.query(model)
        .join(association_table, model.id == association_table.c.document_id)
        .filter(association_table.c[parent_fk_name] == parent_id)
        .order_by(model.id.asc())
        .all()
    )


class FinanceEditMixin:
    """Latest finance edit, persisted in the same transaction as the change."""

    last_edited_at = Column(DateTime(timezone=True), nullable=True)

    @declared_attr
    def last_edited_by_id(cls):
        return Column(Integer, ForeignKey("staff_account.id"), nullable=True)


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
    reject_approved_at = Column(DateTime, nullable=True)
    rejection_comment = Column(String(1000), nullable=True)
    finance_note = Column(String(2000), nullable=True)
    aip_ref_no = Column(String(255), nullable=False)
    aip_ref_date = Column(Date, nullable=False)
    last_notified_type = Column(String(50), nullable=True)
    last_notified_date = Column(Date, nullable=True)

    @property
    def bank_account_info(self):
        cached_account = getattr(self, "_bank_account_info", None)
        if cached_account is not None:
            return cached_account
        return _session_get(object_session(self), BankAccountInfo, self.bank_account_info_id)

    @bank_account_info.setter
    def bank_account_info(self, value):
        self._bank_account_info = value

    @property
    def creator_user(self):
        cached_user = getattr(self, "_creator_user", None)
        if cached_user is not None:
            return cached_user
        return _session_get(object_session(self), StaffAccount, self.creator_id)

    @creator_user.setter
    def creator_user(self, value):
        self._creator_user = value

    @property
    def borrower_user(self):
        cached_user = getattr(self, "_borrower_user", None)
        if cached_user is not None:
            return cached_user
        return _session_get(object_session(self), StaffAccount, self.borrower_id)

    @borrower_user.setter
    def borrower_user(self, value):
        self._borrower_user = value

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

    @property
    def ticket(self):
        cached_ticket = getattr(self, "_ticket", None)
        if cached_ticket is not None:
            return cached_ticket
        return _session_get(object_session(self), CashAdvanceBorrowingTicket, self.ticket_id)

    @ticket.setter
    def ticket(self, value):
        self._ticket = value


Notifications = CashManagementNotifications


document_return_association = Table(
    "cash_mng_document_return_association",
    db.metadata,
    Column("document_id", Integer, ForeignKey("cash_mng_documents.id"), primary_key=True),
    Column("return_id", Integer, ForeignKey("cash_advance_return_details.id"), primary_key=True),
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
    reject_approved_at = Column(DateTime, nullable=True)
    rejection_comment = Column(String(4000), nullable=True)
    reference_number = Column(String(255), nullable=True)
    reference_date = Column(Date, nullable=True)
    product_code_id = Column(String(12), ForeignKey("product_codes.id"), nullable=True)
    cost_center_id = Column(String(12), ForeignKey("cost_centers.id"), nullable=True)
    iocode_id = Column(String(16), ForeignKey("iocodes.id"), nullable=True)
    fiscal_year = Column(Integer, nullable=False, default=_current_fiscal_year)
    product_code = relationship("ProductCode")
    cost_center = relationship("CostCenter")
    iocode = relationship("IOCode")

    @property
    def borrowing_ticket(self):
        cached_ticket = getattr(self, "_borrowing_ticket", None)
        if cached_ticket is not None:
            return cached_ticket
        return _session_get(object_session(self), CashAdvanceBorrowingTicket, self.ticket_id)

    @borrowing_ticket.setter
    def borrowing_ticket(self, value):
        self._borrowing_ticket = value

    @property
    def receipt_items(self):
        return _query_related_list(self, ReturnReceiptItem, "return_detail_id")

    @property
    def closing_amount(self):
        """Amount eligible for a closing document, excluding cash returns."""
        items = self.receipt_items
        if not items:
            return Decimal(str(self.amount_spent or 0))
        return sum(
            (Decimal(str(item.amount or 0)) for item in items if not item.is_cash),
            Decimal("0"),
        )

    @property
    def documents(self):
        return _query_many_to_many_list(self, document_return_association, "return_id", Document)


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

    @property
    def proof_files(self):
        return _query_related_list(self, ReturnProofFile, "return_receipt_item_id")


class ReturnProofFile(FinanceEditMixin, db.Model):
    __tablename__ = "cash_advance_return_proof_files"

    id = Column(Integer, primary_key=True)
    return_detail_id = Column(Integer, ForeignKey("cash_advance_return_details.id"), nullable=False)
    return_receipt_item_id = Column(Integer, ForeignKey("cash_advance_return_receipt_items.id"), nullable=True)
    proof_reference = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now())

    @property
    def receipt_item(self):
        cached_item = getattr(self, "_receipt_item", None)
        if cached_item is not None:
            return cached_item
        return _session_get(object_session(self), ReturnReceiptItem, self.return_receipt_item_id)

    @receipt_item.setter
    def receipt_item(self, value):
        self._receipt_item = value


class ParcelReturnDetail(ClosingDocumentRecordMixin, db.Model):
    _closing_fk = "parcel_return_id"
    _closing_record = "parcel_return"
    __tablename__ = "cash_mng_parcel_return_details"

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("cash_advance_borrowing_tickets.id"), nullable=True)
    fund_request_id = Column(Integer, ForeignKey("petty_cash_fund_requests.id"), nullable=True)
    amount_spent = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=MONEY_DEFAULT)
    items_description = Column(String(1000), nullable=False)
    sent_date = Column(Date, nullable=False)
    status = Column(String(32), nullable=False, default="รอตรวจสอบ")
    created_at = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now())
    approved_at = Column(DateTime, nullable=True)
    rejection_comment = Column(String(4000), nullable=True)

    @property
    def borrowing_ticket(self):
        cached_ticket = getattr(self, "_borrowing_ticket", None)
        if cached_ticket is not None:
            return cached_ticket
        return _session_get(object_session(self), CashAdvanceBorrowingTicket, self.ticket_id)

    @borrowing_ticket.setter
    def borrowing_ticket(self, value):
        self._borrowing_ticket = value

    @property
    def fund_request(self):
        cached_request = getattr(self, "_fund_request", None)
        if cached_request is not None:
            return cached_request
        return _session_get(object_session(self), FundRequest, self.fund_request_id)

    @fund_request.setter
    def fund_request(self, value):
        self._fund_request = value


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

    @property
    def department_name(self):
        from app.models import Org
        org = _session_get(object_session(self), Org, self.org_id)
        return getattr(org, "name", None)

    @property
    def org(self):
        from app.models import Org
        return _session_get(object_session(self), Org, self.org_id)

    @property
    def custodian_name(self):
        custodian = _session_get(object_session(self), StaffAccount, self.custodian_id)
        return getattr(custodian, "name", None) or getattr(custodian, "fullname", None)

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

    @property
    def bank_account_info(self):
        cached_account = getattr(self, "_bank_account_info", None)
        if cached_account is not None:
            return cached_account
        return _session_get(object_session(self), BankAccountInfo, self.bank_account_info_id)

    @bank_account_info.setter
    def bank_account_info(self, value):
        self._bank_account_info = value


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

    @property
    def org(self):
        from app.models import Org
        return _session_get(object_session(self), Org, self.org_id)


class FundRequest(FinanceEditMixin, db.Model):
    __tablename__ = "petty_cash_fund_requests"

    id = Column(Integer, primary_key=True)
    requester_id = Column(Integer, ForeignKey("staff_account.id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("staff_account.id"), nullable=True, index=True)
    org_id = Column(Integer, ForeignKey("orgs.id"), nullable=True, index=True)
    borrowing_ticket_id = Column(Integer, ForeignKey("cash_advance_borrowing_tickets.id"), nullable=True)
    form_type = Column(String(10), nullable=False)
    ticket_number = Column(String(64), nullable=True)
    request_date = Column(Date, nullable=False)
    receive_interest = Column(Date, nullable=True)
    withdraw_intrest = Column(Date, nullable=True)
    status = Column(String(64), nullable=False, default="อนุมัติแล้ว")
    amount = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=MONEY_DEFAULT)
    created_at = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now())
    cancel_at = Column(DateTime, nullable=True)
    cancel_transferred_at = Column(Date, nullable=True)
    purpose = Column(String(1000), nullable=True)
    period_year = Column(String(10), nullable=True)
    withdrawal_proof_reference = Column(String(500), nullable=True)
    withdrawal_proof_filename = Column(String(255), nullable=True)

    @property
    def borrowing_ticket(self):
        cached_ticket = getattr(self, "_borrowing_ticket", None)
        if cached_ticket is not None:
            return cached_ticket
        return _session_get(object_session(self), CashAdvanceBorrowingTicket, self.borrowing_ticket_id)

    @borrowing_ticket.setter
    def borrowing_ticket(self, value):
        self._borrowing_ticket = value

    @property
    def items(self):
        return _query_related_list(self, FundRequestItem, "fund_request_id")

    @property
    def org(self):
        from app.models import Org
        return _session_get(object_session(self), Org, self.org_id)

    @property
    def department_name(self):
        org = self.org
        return getattr(org, "name", None)

    @property
    def requester_name(self):
        requester = _session_get(object_session(self), StaffAccount, self.requester_id)
        ticket = self.borrowing_ticket
        return (
            getattr(ticket, "borrower_name", None)
            or getattr(requester, "name", None)
            or getattr(requester, "fullname", None)
        )

    @property
    def requester_position(self):
        requester = _session_get(object_session(self), StaffAccount, self.requester_id)
        return getattr(requester, "position", None)

    @property
    def creator(self):
        return _session_get(object_session(self), StaffAccount, self.creator_id)

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

    @property
    def fund_in_date(self):
        return self.receive_interest

    @property
    def withdrawal_date(self):
        return self.withdraw_intrest


class FundRequestItem(FinanceEditMixin, db.Model):
    __tablename__ = "petty_cash_fund_request_items"

    id = Column(Integer, primary_key=True)
    fund_request_id = Column(Integer, ForeignKey("petty_cash_fund_requests.id"), nullable=False)
    description = Column(String(255), nullable=False)
    amount = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=MONEY_DEFAULT)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    category_type = Column(Integer, nullable=False, default=1) # use id instead


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
    rejection_comment = Column(String(4000), nullable=True)
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

    @property
    def fund_request(self):
        cached_request = getattr(self, "_fund_request", None)
        if cached_request is not None:
            return cached_request
        return _session_get(object_session(self), FundRequest, self.fund_request_id)

    @fund_request.setter
    def fund_request(self, value):
        self._fund_request = value

    @property
    def items(self):
        return _query_related_list(self, PettyCashClaimItem, "claim_id")

    @property
    def documents(self):
        return _query_many_to_many_list(self, document_petty_claim_association, "claim_id", Document)

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

    @property
    def proof_files(self):
        return _query_related_list(self, PettyCashClaimProofFile, "claim_item_id")


class PettyCashClaimProofFile(FinanceEditMixin, db.Model):
    __tablename__ = "petty_cash_claim_proof_files"

    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("petty_cash_claim_details.id"), nullable=False)
    claim_item_id = Column(Integer, ForeignKey("petty_cash_claim_items.id"), nullable=True)
    proof_reference = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now())

    @property
    def claim_item(self):
        cached_item = getattr(self, "_claim_item", None)
        if cached_item is not None:
            return cached_item
        return _session_get(object_session(self), PettyCashClaimItem, self.claim_item_id)

    @claim_item.setter
    def claim_item(self, value):
        self._claim_item = value
