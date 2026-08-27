from sqlalchemy import Boolean, Column, Table, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import object_session
from app.main import db
from app.staff.models import StaffAccount


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


def _staff_position(staff):
    personal_info = getattr(staff, "personal_info", None)
    job_position = getattr(personal_info, "job_position", None)
    return getattr(job_position, "position", None)


def _staff_role(staff):
    role_names = {
        role.role_need
        for role in (getattr(staff, "roles", None) or [])
        if getattr(role, "role_need", None)
    }
    for role_name in ("finance", "secretary", "staff", "cash_management_coordinator", "borrower"):
        if role_name in role_names:
            return role_name
    return next(iter(role_names), "staff")


if not hasattr(StaffAccount, "name"):
    StaffAccount.name = property(_staff_name)
if not hasattr(StaffAccount, "department"):
    StaffAccount.department = property(_staff_department)
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


class CashAdvanceBorrowingTicket(db.Model):
    __tablename__ = "cash_advance_borrowing_tickets"

    id = Column(Integer, primary_key=True)
    number = Column(Integer, nullable=True)
    creator_id = Column(Integer, ForeignKey("staff_account.id"), nullable=False)
    borrower_id = Column(Integer, ForeignKey("staff_account.id"), nullable=False)
    status = Column(String(64), nullable=False, default="กำลังส่งคำขอ")
    borrowing_ticket_purpose = Column(String(255), nullable=False)
    required_budget = Column(Numeric(12, 2), nullable=False)
    account_number = Column(String(100), nullable=False)
    bank_account_info_id = Column(Integer, ForeignKey("cash_mng_bank_account_infos.id"), nullable=True)
    borrowing_ticket_start_date = Column(Date, nullable=False)
    borrowing_ticket_end_date = Column(Date, nullable=False)
    finance_verified = Column(Boolean, nullable=False, default=False)
    due_date = Column(Date, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    approved_at = Column(DateTime, nullable=True)
    closed_date = Column(DateTime, nullable=True)
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


class Document(db.Model):
    __tablename__ = "cash_mng_documents"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False, default="#")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ReturnDetail(db.Model):
    __tablename__ = "cash_advance_return_details" # use cash_advance_payment_receipt_detail

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("cash_advance_borrowing_tickets.id"), nullable=False)
    amount_spent = Column(Numeric(12, 2), nullable=False, default=0)
    proof_reference = Column(String(255), nullable=False, default="")
    status = Column(String(32), nullable=False, default="รอตรวจสอบ")
    old_closing_document_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    rejection_comment = Column(String(4000), nullable=True)
    closing_document_id = Column(Integer, ForeignKey("cash_mng_closing_documents.id"), nullable=True)

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
    def closing_document(self):
        cached_document = getattr(self, "_closing_document", None)
        if cached_document is not None:
            return cached_document
        return _session_get(object_session(self), ClosingDocument, self.closing_document_id)

    @closing_document.setter
    def closing_document(self, value):
        self._closing_document = value

    @property
    def closing_document_name(self):
        if self.closing_document is not None:
            return self.closing_document.document_number
        return None

    @property
    def old_document_number(self):
        return self.old_closing_document_name

    @property
    def documents(self):
        return _query_many_to_many_list(self, document_return_association, "return_id", Document)


class ReturnReceiptItem(db.Model):
    __tablename__ = "cash_advance_return_receipt_items"

    id = Column(Integer, primary_key=True)
    return_detail_id = Column(Integer, ForeignKey("cash_advance_return_details.id"), nullable=False)
    receipt_date = Column(Date, nullable=False)
    store_name = Column(String(255), nullable=False, default="")
    description = Column(String(255), nullable=False, default="")
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    @property
    def proof_files(self):
        return _query_related_list(self, ReturnProofFile, "return_receipt_item_id")


class ReturnProofFile(db.Model):
    __tablename__ = "cash_advance_return_proof_files"

    id = Column(Integer, primary_key=True)
    return_detail_id = Column(Integer, ForeignKey("cash_advance_return_details.id"), nullable=False)
    return_receipt_item_id = Column(Integer, ForeignKey("cash_advance_return_receipt_items.id"), nullable=True)
    proof_reference = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    @property
    def receipt_item(self):
        cached_item = getattr(self, "_receipt_item", None)
        if cached_item is not None:
            return cached_item
        return _session_get(object_session(self), ReturnReceiptItem, self.return_receipt_item_id)

    @receipt_item.setter
    def receipt_item(self, value):
        self._receipt_item = value


class ParcelReturnDetail(db.Model):
    __tablename__ = "cash_mng_parcel_return_details"

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("cash_advance_borrowing_tickets.id"), nullable=True)
    fund_request_id = Column(Integer, ForeignKey("petty_cash_fund_requests.id"), nullable=True)
    amount_spent = Column(Numeric(12, 2), nullable=False, default=0)
    items_description = Column(String(1000), nullable=False)
    sent_date = Column(Date, nullable=False)
    status = Column(String(32), nullable=False, default="รอตรวจสอบ")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    closing_document_id = Column(Integer, ForeignKey("cash_mng_closing_documents.id"), nullable=True)
    old_closing_document_name = Column(String(255), nullable=True)
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

    @property
    def closing_document(self):
        cached_document = getattr(self, "_closing_document", None)
        if cached_document is not None:
            return cached_document
        return _session_get(object_session(self), ClosingDocument, self.closing_document_id)

    @closing_document.setter
    def closing_document(self, value):
        self._closing_document = value

    @property
    def closing_document_name(self):
        if self.closing_document is not None:
            return self.closing_document.document_number
        return None

    @property
    def old_document_number(self):
        return self.old_closing_document_name


class ClosingDocument(db.Model):
    __tablename__ = "cash_mng_closing_documents"

    id = Column(Integer, primary_key=True)
    document_number = Column(String(255), nullable=False, unique=True)
    filing_date = Column(Date, nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(String(32), nullable=False, default="ใช้งานอยู่")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class PettyCashSetting(db.Model):
    __tablename__ = "petty_cash_settings"

    id = Column(Integer, primary_key=True)
    fiscal_year = Column(Integer, nullable=False)
    department_name = Column(String(255), nullable=False, unique=True)
    custodian_name = Column(String(255), nullable=True) # delete
    budget = Column(Numeric(12, 2), nullable=False, default=0)
    account_number = Column(String(100), nullable=False)
    bank_account_info_id = Column(Integer, ForeignKey("cash_mng_bank_account_infos.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    valid = Column(Boolean, nullable=False, default=True)
    is_enabled = Column(Boolean, nullable=False, default=True) # which one which
    custodian_id = Column(Integer, ForeignKey("staff_account.id"), nullable=True, unique=True)

    @property
    def bank_account_info(self):
        cached_account = getattr(self, "_bank_account_info", None)
        if cached_account is not None:
            return cached_account
        return _session_get(object_session(self), BankAccountInfo, self.bank_account_info_id)

    @bank_account_info.setter
    def bank_account_info(self, value):
        self._bank_account_info = value


class BankAccountInfo(db.Model):
    __tablename__ = "cash_mng_bank_account_infos"
    __table_args__ = (
        UniqueConstraint(
            "record_type",
            "thai_name",
            name="uq_cash_mng_bank_account_infos_record_type_thai_name",
        ),
    )

    id = Column(Integer, primary_key=True)
    record_type = Column(String(32), nullable=False)
    thai_name = Column(String(255), nullable=False)
    english_name = Column(String(255), nullable=False) #delete
    account_number = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now()) # editable


class FundRequest(db.Model):
    __tablename__ = "petty_cash_fund_requests"

    id = Column(Integer, primary_key=True)
    requester_id = Column(Integer, ForeignKey("staff_account.id"), nullable=False)
    borrowing_ticket_id = Column(Integer, ForeignKey("cash_advance_borrowing_tickets.id"), nullable=True)
    form_type = Column(String(10), nullable=False)
    requester_name = Column(String(255), nullable=False) # del
    requester_position = Column(String(255), nullable=False) # del
    department_name = Column(String(255), nullable=False) # del
    account_number = Column(String(100), nullable=False) # del
    ticket_number = Column(String(64), nullable=True)
    request_date = Column(Date, nullable=False)
    fund_in_date = Column(Date, nullable=True) # receive_interest
    withdrawal_date = Column(Date, nullable=True) # withdraw_intrest
    status = Column(String(64), nullable=False, default="กำลังดำเนินการ")
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
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


class FundRequestItem(db.Model):
    __tablename__ = "petty_cash_fund_request_items"

    id = Column(Integer, primary_key=True)
    fund_request_id = Column(Integer, ForeignKey("petty_cash_fund_requests.id"), nullable=False)
    description = Column(String(255), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    category_type = Column(Integer, nullable=False, default=1) # use id instead


document_petty_claim_association = Table(
    "cash_mng_document_petty_claim_association",
    db.metadata,
    Column("document_id", Integer, ForeignKey("cash_mng_documents.id"), primary_key=True),
    Column("claim_id", Integer, ForeignKey("petty_cash_claim_details.id"), primary_key=True),
)


class PettyCashClaimDetail(db.Model):
    __tablename__ = "petty_cash_claim_details" # use petty_cash_payment_receipt_detail

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("staff_account.id"), nullable=False)
    claim_number = Column("Claim_number", String(255), nullable=True)
    status = Column(String(32), nullable=False, default="ฉบับร่าง")
    petty_cash_setting_id = Column(Integer, ForeignKey("petty_cash_settings.id"), nullable=False)
    fund_request_id = Column(Integer, ForeignKey("petty_cash_fund_requests.id"), nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=False, default=0)
    rejection_comment = Column(String(4000), nullable=True)
    transferred_at = Column(Date, nullable=True)
    closing_document_id = Column(Integer, ForeignKey("cash_mng_closing_documents.id"), nullable=True)
    old_closing_document_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

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
    def closing_document(self):
        cached_document = getattr(self, "_closing_document", None)
        if cached_document is not None:
            return cached_document
        return _session_get(object_session(self), ClosingDocument, self.closing_document_id)

    @closing_document.setter
    def closing_document(self, value):
        self._closing_document = value

    @property
    def items(self):
        return _query_related_list(self, PettyCashClaimItem, "claim_id")

    @property
    def documents(self):
        return _query_many_to_many_list(self, document_petty_claim_association, "claim_id", Document)


class PettyCashClaimItem(db.Model):
    __tablename__ = "petty_cash_claim_items"

    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("petty_cash_claim_details.id"), nullable=False)
    receipt_date = Column(Date, nullable=False)
    description = Column(String(255), nullable=False, default="")
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    category_type = Column(Integer, nullable=False, default=1)

    @property
    def proof_files(self):
        return _query_related_list(self, PettyCashClaimProofFile, "claim_item_id")


class PettyCashClaimProofFile(db.Model):
    __tablename__ = "petty_cash_claim_proof_files"

    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("petty_cash_claim_details.id"), nullable=False)
    claim_item_id = Column(Integer, ForeignKey("petty_cash_claim_items.id"), nullable=True)
    proof_reference = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    @property
    def claim_item(self):
        cached_item = getattr(self, "_claim_item", None)
        if cached_item is not None:
            return cached_item
        return _session_get(object_session(self), PettyCashClaimItem, self.claim_item_id)

    @claim_item.setter
    def claim_item(self, value):
        self._claim_item = value
