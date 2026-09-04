from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import object_session

from .models import (
    BorrowingTicket,
    ClosingDocument,
    BankAccountInfo,
    Document,
    FundRequest,
    FundRequestItem,
    ParcelReturnDetail,
    PettyCashClaimDetail,
    PettyCashClaimItem,
    PettyCashClaimProofFile,
    PettyCashSetting,
    ReturnDetail,
    ReturnProofFile,
    ReturnReceiptItem,
    StaffAccount,
    document_return_association,
)
from app.models import Org


def _money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _first(session, model, **filters):
    return session.query(model).filter_by(**filters).first()


def _existing_user(session, *, email):
    user = _first(session, StaffAccount, email=email)
    if user is None:
        raise RuntimeError(f"Missing init user: {email}")
    return user


INIT_USER_EMAILS = {
    "borrower": "borrower@example.com",
    "borrower2": "borrower2@example.com",
    "coordinator_ops": "pensi@example.com",
    "custodian": "staff_patsadu@example.com",
    "staff": "staff_clerk@example.com",
}

def _ensure_setting(session, *, staff, fiscal_year, department_name, custodian_name, budget, account_number, valid=True):
    org = session.query(Org).filter(
        (Org.name == department_name) | (Org.en_name == department_name)
    ).first()
    if not org:
        return None
    setting = _first(session, PettyCashSetting, org_id=org.id, fiscal_year=fiscal_year)
    if setting:
        return setting
    bank_account_info = _first(session, BankAccountInfo, account_number=account_number)

    setting = PettyCashSetting(
        fiscal_year=fiscal_year,
        org_id=org.id,
        budget=_money(budget),
        bank_account_info_id=bank_account_info.id if bank_account_info else None,
        valid=valid,
        custodian_id=staff.id,
    )
    session.add(setting)
    session.flush()
    return setting


def _ensure_document(session, *, title, file_path):
    document = _first(session, Document, title=title)
    if document:
        return document

    document = Document(title=title, file_path=file_path, created_at=datetime.now())
    session.add(document)
    session.flush()
    return document


def _ensure_closing_document(session, *, document_number, filing_date, total_amount):
    closing_document = _first(session, ClosingDocument, document_number=document_number)
    if closing_document:
        return closing_document

    closing_document = ClosingDocument(
        document_number=document_number,
        filing_date=filing_date,
        total_amount=_money(total_amount),
        created_at=datetime.now(),
    )
    session.add(closing_document)
    session.flush()
    return closing_document


def _ensure_borrowing_ticket(
    session,
    *,
    user,
    number,
    borrower_name,
    borrower_email,
    borrowing_ticket_purpose,
    required_budget,
    account_number,
    start_date,
    end_date,
    status,
    aip_ref_no,
    aip_ref_date,
    due_date,
    finance_verified=False,
    approved_at=None,
    closed_date=None,
):
    ticket = _first(session, BorrowingTicket, aip_ref_no=aip_ref_no)
    if ticket:
        return ticket

    borrower_user = _first(session, StaffAccount, email=borrower_email) or user

    ticket = BorrowingTicket(
        number=number,
        creator_id=user.id,
        borrower_id=borrower_user.id,
        borrower_name=borrower_name,
        creator_name=user.name,
        borrower_email=borrower_email,
        borrowing_ticket_purpose=borrowing_ticket_purpose,
        required_budget=_money(required_budget),
        account_number=account_number,
        borrowing_ticket_start_date=start_date,
        borrowing_ticket_end_date=end_date,
        status=status,
        finance_verified=finance_verified,
        due_date=due_date,
        approved_at=approved_at,
        closed_date=closed_date,
        aip_ref_no=aip_ref_no,
        aip_ref_date=aip_ref_date,
    )
    session.add(ticket)
    session.flush()
    return ticket


def _ensure_return_detail(
    session,
    *,
    ticket,
    amount_spent,
    proof_reference,
    status,
    old_closing_document_name=None,
    closing_document=None,
    rejection_comment=None,
):
    return_detail = (
        session.query(ReturnDetail)
        .filter_by(ticket_id=ticket.id, proof_reference=proof_reference)
        .first()
    )
    if return_detail:
        return return_detail

    return_detail = ReturnDetail(
        ticket_id=ticket.id,
        amount_spent=_money(amount_spent),
        proof_reference=proof_reference,
        status=status,
        old_closing_document_name=old_closing_document_name,
        rejection_comment=rejection_comment,
    )
    if closing_document:
        return_detail.closing_document = closing_document

    session.add(return_detail)
    session.flush()
    return return_detail


def _ensure_return_receipt_item(session, *, return_detail, receipt_date, store_name, description, amount):
    item = (
        session.query(ReturnReceiptItem)
        .filter_by(return_detail_id=return_detail.id, store_name=store_name, description=description)
        .first()
    )
    if item:
        return item

    item = ReturnReceiptItem(
        return_detail_id=return_detail.id,
        receipt_date=receipt_date,
        store_name=store_name,
        description=description,
        amount=_money(amount),
    )
    session.add(item)
    session.flush()
    return item


def _ensure_return_proof_file(session, *, return_detail, receipt_item, proof_reference, filename):
    proof_file = (
        session.query(ReturnProofFile)
        .filter_by(proof_reference=proof_reference)
        .first()
    )
    if proof_file:
        return proof_file

    proof_file = ReturnProofFile(
        return_detail_id=return_detail.id,
        return_receipt_item_id=receipt_item.id if receipt_item else None,
        proof_reference=proof_reference,
        filename=filename,
    )
    session.add(proof_file)
    session.flush()
    return proof_file


def _append_document_once(return_detail, document):
    if not document or not getattr(return_detail, "id", None):
        return

    session = object_session(return_detail)
    if session is None:
        return

    linked = session.execute(
        document_return_association.select().where(
            document_return_association.c.return_id == return_detail.id,
            document_return_association.c.document_id == document.id,
        )
    ).first()
    if linked:
        return

    session.execute(
        document_return_association.insert().values(
            document_id=document.id,
            return_id=return_detail.id,
        )
    )


def _ensure_bank_account_info(session, *, record_type, thai_name, created_at, account_number):
    record = (
        session.query(BankAccountInfo)
        .filter_by(record_type=record_type, thai_name=thai_name)
        .first()
    )
    if record:
        return record

    record = BankAccountInfo(
        record_type=record_type,
        thai_name=thai_name,
        created_at=created_at,
    )
    session.add(record)
    session.flush()
    return record


def _ensure_parcel_return(session, *, ticket, amount_spent, items_description, sent_date, status, closing_document=None):
    parcel = (
        session.query(ParcelReturnDetail)
        .filter_by(ticket_id=ticket.id, items_description=items_description)
        .first()
    )
    if parcel:
        return parcel

    parcel = ParcelReturnDetail(
        ticket_id=ticket.id,
        amount_spent=_money(amount_spent),
        items_description=items_description,
        sent_date=sent_date,
        status=status,
    )
    if closing_document:
        parcel.closing_document = closing_document

    session.add(parcel)
    session.flush()
    return parcel


def _ensure_fund_request(
    session,
    *,
    user,
    form_type,
    requester_name,
    requester_position,
    department_name,
    account_number,
    ticket_number,
    request_date,
    amount,
    purpose=None,
    period_year=None,
    status="กำลังดำเนินการ",
    withdrawal_proof_reference=None,
):
    fund_request = (
        session.query(FundRequest)
        .filter_by(requester_id=user.id, form_type=form_type, ticket_number=ticket_number)
        .first()
    )
    if fund_request:
        return fund_request

    fund_request = FundRequest(
        requester_id=user.id,
        form_type=form_type,
        ticket_number=ticket_number,
        request_date=request_date,
        amount=_money(amount),
        purpose=purpose,
        period_year=period_year,
        withdrawal_proof_reference=withdrawal_proof_reference,
        created_at=datetime.now(),
        status=status,
    )
    session.add(fund_request)
    session.flush()
    return fund_request


def _ensure_fund_request_item(session, *, fund_request, description, amount, category_type):
    item = (
        session.query(FundRequestItem)
        .filter_by(fund_request_id=fund_request.id, description=description)
        .first()
    )
    if item:
        return item

    item = FundRequestItem(
        fund_request_id=fund_request.id,
        description=description,
        amount=_money(amount),
        category_type=category_type,
        created_at=datetime.now(),
    )
    session.add(item)
    session.flush()
    return item


def _ensure_claim(session, *, user, setting, fund_request, status, total_amount=0, rejection_comment=None, transferred_at=None, closing_document=None):
    claim = session.query(PettyCashClaimDetail).filter_by(fund_request_id=fund_request.id if fund_request else None).first()
    if claim:
        return claim

    claim = PettyCashClaimDetail(
        user_id=user.id,
        petty_cash_setting_id=setting.id if setting else None,
        fund_request_id=fund_request.id if fund_request else None,
        total_amount=_money(total_amount),
        status=status,
        rejection_comment=rejection_comment,
        transferred_at=transferred_at,
    )
    if closing_document:
        claim.closing_document = closing_document

    session.add(claim)
    session.flush()
    return claim


def _ensure_claim_item(session, *, claim, receipt_date, description, amount, category_type):
    item = (
        session.query(PettyCashClaimItem)
        .filter_by(claim_id=claim.id, description=description, receipt_date=receipt_date)
        .first()
    )
    if item:
        return item

    item = PettyCashClaimItem(
        claim_id=claim.id,
        receipt_date=receipt_date,
        description=description,
        amount=_money(amount),
        category_type=category_type,
    )
    session.add(item)
    session.flush()
    return item


def _ensure_claim_proof_file(session, *, claim, claim_item, proof_reference, filename):
    proof_file = (
        session.query(PettyCashClaimProofFile)
        .filter_by(proof_reference=proof_reference)
        .first()
    )
    if proof_file:
        return proof_file

    proof_file = PettyCashClaimProofFile(
        claim_id=claim.id,
        claim_item_id=claim_item.id if claim_item else None,
        proof_reference=proof_reference,
        filename=filename,
    )
    session.add(proof_file)
    session.flush()
    return proof_file


def seed_demo_data(session):
    today = date.today()
    current_year_be = today.year + 543

    borrowers = {
        key: _existing_user(session, email=email)
        for key, email in INIT_USER_EMAILS.items()
    }
    borrower = borrowers["borrower"]
    borrower2 = borrowers["borrower2"]
    coordinator_ops = borrowers["coordinator_ops"]
    custodian = borrowers["custodian"]
    staff = borrowers["staff"]

    setting = _ensure_setting(
        session,
        staff=custodian,
        fiscal_year=current_year_be,
        department_name="งานพัสดุและจัดหา",
        custodian_name="นายพัสดุ คุมเงิน",
        budget="200000.00",
        account_number="123-4-56789-0",
        valid=True,
    )

    closing_doc_1 = _ensure_closing_document(
        session,
        document_number="0001/2569",
        filing_date=today - timedelta(days=18),
        total_amount="5600.00",
    )
    closing_doc_2 = _ensure_closing_document(
        session,
        document_number="0002/2569",
        filing_date=today - timedelta(days=6),
        total_amount="9400.00",
    )

    doc_receipt = _ensure_document(
        session,
        title="Receipt Bundle A",
        file_path="/static/dummy_documents/receipt_bundle_a.pdf",
    )
    doc_approval = _ensure_document(
        session,
        title="Approval Notice A",
        file_path="/static/dummy_documents/approval_notice_a.pdf",
    )
    doc_claim = _ensure_document(
        session,
        title="Claim Supporting Pack",
        file_path="/static/dummy_documents/claim_supporting_pack.pdf",
    )
    doc_reject = _ensure_document(
        session,
        title="Rejected Return Checklist",
        file_path="/static/dummy_documents/rejected_return_checklist.pdf",
    )
    doc_travel = _ensure_document(
        session,
        title="Travel Advance Supporting Set",
        file_path="/static/dummy_documents/travel_advance_supporting_set.pdf",
    )

    ticket_open = _ensure_borrowing_ticket(
        session,
        user=borrower2,
        number=1001,
        borrower_name=borrower.name,
        borrower_email=borrower.email,
        borrowing_ticket_purpose="Demo Lab Equipment Borrowing",
        required_budget="15000.00",
        account_number="016-300-325-6",
        start_date=today - timedelta(days=25),
        end_date=today - timedelta(days=21),
        status="อนุมัติจ่ายเงิน",
        aip_ref_no="001/69",
        aip_ref_date=today - timedelta(days=5),
        due_date=today - timedelta(days=6),
        finance_verified=True,
        approved_at=datetime.now() - timedelta(days=3),
    )
    ticket_partial = _ensure_borrowing_ticket(
        session,
        user=borrower,
        number=1002,
        borrower_name=borrower.name,
        borrower_email=borrower.email,
        borrowing_ticket_purpose="Demo Field Trip Advance",
        required_budget="12000.00",
        account_number="016-300-325-6",
        start_date=today - timedelta(days=20),
        end_date=today - timedelta(days=1),
        status="มียอดคงค้าง",
        aip_ref_no="002/69",
        aip_ref_date=today - timedelta(days=21),
        due_date=today - timedelta(days=6),
        finance_verified=True,
        approved_at=datetime.now() - timedelta(days=18),
    )
    ticket_returned = _ensure_borrowing_ticket(
        session,
        user=borrower2,
        number=2001,
        borrower_name=borrower2.name,
        borrower_email=borrower2.email,
        borrowing_ticket_purpose="Demo Training Budget",
        required_budget="8000.00",
        account_number="123-4-56789-1",
        start_date=today - timedelta(days=35),
        end_date=today - timedelta(days=20),
        status="เคลียร์ยอดแล้ว",
        aip_ref_no="003/69",
        aip_ref_date=today - timedelta(days=36),
        due_date=today - timedelta(days=5),
        finance_verified=True,
        approved_at=datetime.now() - timedelta(days=33),
        closed_date=datetime.now() - timedelta(days=7),
    )

    partial_return = _ensure_return_detail(
        session,
        ticket=ticket_partial,
        amount_spent="4200.00",
        proof_reference="001/69",
        status="ผ่านการตรวจสอบ",
        old_closing_document_name=closing_doc_1.document_number,
        closing_document=closing_doc_1,
    )
    partial_item_1 = _ensure_return_receipt_item(
        session,
        return_detail=partial_return,
        receipt_date=today - timedelta(days=14),
        store_name="Demo Stationery Shop",
        description="Workshop paper and markers",
        amount="1800.00",
    )
    partial_item_2 = _ensure_return_receipt_item(
        session,
        return_detail=partial_return,
        receipt_date=today - timedelta(days=13),
        store_name="Demo IT Store",
        description="USB cables and adapters",
        amount="2400.00",
    )
    _ensure_return_proof_file(
        session,
        return_detail=partial_return,
        receipt_item=partial_item_1,
        proof_reference="001/69-P1",
        filename="receipt-paper-markers.jpg",
    )
    _ensure_return_proof_file(
        session,
        return_detail=partial_return,
        receipt_item=partial_item_2,
        proof_reference="001/69-P2",
        filename="receipt-cables-adapters.jpg",
    )
    _append_document_once(partial_return, doc_receipt)

    full_return = _ensure_return_detail(
        session,
        ticket=ticket_returned,
        amount_spent="8000.00",
        proof_reference="002/69",
        status="เอกสารตั้งฎีกา",
        old_closing_document_name=closing_doc_2.document_number,
        closing_document=closing_doc_2,
    )
    full_item_1 = _ensure_return_receipt_item(
        session,
        return_detail=full_return,
        receipt_date=today - timedelta(days=30),
        store_name="Demo Supply Center",
        description="Training materials",
        amount="5000.00",
    )
    full_item_2 = _ensure_return_receipt_item(
        session,
        return_detail=full_return,
        receipt_date=today - timedelta(days=29),
        store_name="Demo Copy Center",
        description="Printed handouts",
        amount="3000.00",
    )
    _ensure_return_proof_file(
        session,
        return_detail=full_return,
        receipt_item=full_item_1,
        proof_reference="002/69-P1",
        filename="training-materials.pdf",
    )
    _ensure_return_proof_file(
        session,
        return_detail=full_return,
        receipt_item=full_item_2,
        proof_reference="002/69-P2",
        filename="printed-handouts.pdf",
    )
    _append_document_once(full_return, doc_approval)

    _ensure_parcel_return(
        session,
        ticket=ticket_open,
        amount_spent="750.00",
        items_description="Parcel return sample for finance review",
        sent_date=today - timedelta(days=3),
        status="ได้รับเอกสารแล้ว",
        closing_document=closing_doc_1,
    )

    borrower_self = borrower
    borrower_free = borrower2

    borrower_self_active = _ensure_borrowing_ticket(
        session,
        user=borrower_self,
        number=3001,
        borrower_name=borrower_self.name,
        borrower_email=borrower_self.email,
        borrowing_ticket_purpose="Conference Travel Advance",
        required_budget="14500.00",
        account_number="222-3-45678-9",
        start_date=today - timedelta(days=12),
        end_date=today + timedelta(days=3),
        status="อนุมัติจ่ายเงิน",
        aip_ref_no="B-001/2569",
        aip_ref_date=today - timedelta(days=2),
        due_date=today + timedelta(days=18),
        finance_verified=True,
        approved_at=datetime.now() - timedelta(days=1),
    )

    borrower_self_closed = _ensure_borrowing_ticket(
        session,
        user=borrower_self,
        number=3002,
        borrower_name=borrower_self.name,
        borrower_email=borrower_self.email,
        borrowing_ticket_purpose="Lab Consumables for Seminar",
        required_budget="6200.00",
        account_number="222-3-45678-9",
        start_date=today - timedelta(days=60),
        end_date=today - timedelta(days=40),
        status="เอกสารตั้งฎีกา",
        aip_ref_no="B-002/2569",
        aip_ref_date=today - timedelta(days=61),
        due_date=today - timedelta(days=25),
        finance_verified=True,
        approved_at=datetime.now() - timedelta(days=58),
        closed_date=datetime.now() - timedelta(days=18),
    )

    borrower_closed_return = _ensure_return_detail(
        session,
        ticket=borrower_self_closed,
        amount_spent="6200.00",
        proof_reference="B-002/69",
        status="เคลียร์ยอดแล้ว",
        old_closing_document_name=closing_doc_2.document_number,
        closing_document=closing_doc_2,
    )
    borrower_closed_item = _ensure_return_receipt_item(
        session,
        return_detail=borrower_closed_return,
        receipt_date=today - timedelta(days=44),
        store_name="Campus Supply Co.",
        description="Seminar materials and markers",
        amount="6200.00",
    )
    _ensure_return_proof_file(
        session,
        return_detail=borrower_closed_return,
        receipt_item=borrower_closed_item,
        proof_reference="B-002/69-P1",
        filename="seminar-materials.pdf",
    )
    _append_document_once(borrower_closed_return, doc_travel)

    borrower_free_ticket = _ensure_borrowing_ticket(
        session,
        user=borrower_free,
        number=3003,
        borrower_name=borrower_free.name,
        borrower_email=borrower_free.email,
        borrowing_ticket_purpose="New Member Orientation Budget",
        required_budget="9000.00",
        account_number="222-3-45678-9",
        start_date=today - timedelta(days=2),
        end_date=today + timedelta(days=10),
        status="กำลังส่งคำขอ",
        aip_ref_no="B-003/2569",
        aip_ref_date=today - timedelta(days=1),
        due_date=today + timedelta(days=25),
    )

    coordinator_review_ticket = _ensure_borrowing_ticket(
        session,
        user=coordinator_ops,
        number=4001,
        borrower_name=staff.name,
        borrower_email=staff.email,
        borrowing_ticket_purpose="Research Lab Supplies",
        required_budget="18500.00",
        account_number="555-9-87654-3",
        start_date=today - timedelta(days=18),
        end_date=today - timedelta(days=4),
        status="มียอดคงค้าง",
        aip_ref_no="C-001/2569",
        aip_ref_date=today - timedelta(days=19),
        due_date=today - timedelta(days=0),
        finance_verified=True,
        approved_at=datetime.now() - timedelta(days=16),
    )

    coordinator_reject_return = _ensure_return_detail(
        session,
        ticket=coordinator_review_ticket,
        amount_spent="5600.00",
        proof_reference="C-001/69",
        status="ปฏิเสธ",
        rejection_comment="รายการนี้ยังขาดใบเสร็จ 1 ใบและยอดเงินรวมไม่ตรงตามเอกสารแนบ",
    )
    coordinator_reject_item = _ensure_return_receipt_item(
        session,
        return_detail=coordinator_reject_return,
        receipt_date=today - timedelta(days=7),
        store_name="Lab Plus Store",
        description="Reagents and consumables",
        amount="5600.00",
    )
    _ensure_return_proof_file(
        session,
        return_detail=coordinator_reject_return,
        receipt_item=coordinator_reject_item,
        proof_reference="C-001/69-P1",
        filename="lab-consumables-reject.pdf",
    )
    _append_document_once(coordinator_reject_return, doc_reject)

    _ensure_parcel_return(
        session,
        ticket=borrower_self_active,
        amount_spent="1250.00",
        items_description="Parcel return waiting finance check",
        sent_date=today - timedelta(days=2),
        status="รอตรวจสอบ",
    )
    _ensure_parcel_return(
        session,
        ticket=coordinator_review_ticket,
        amount_spent="980.00",
        items_description="Parcel return already verified by finance",
        sent_date=today - timedelta(days=5),
        status="ได้รับเอกสารแล้ว",
        closing_document=closing_doc_1,
    )
    rejected_parcel = _ensure_parcel_return(
        session,
        ticket=borrower_self_closed,
        amount_spent="640.00",
        items_description="Parcel return rejected due to missing signature",
        sent_date=today - timedelta(days=6),
        status="ปฏิเสธ",
    )
    rejected_parcel.rejection_comment = "กรุณาแนบลายเซ็นผู้รับพัสดุให้ครบ"

    _ensure_fund_request(
        session,
        user=coordinator_ops,
        form_type="31",
        requester_name=coordinator_ops.name,
        requester_position=coordinator_ops.position or "ผู้ประสานงาน",
        department_name=coordinator_ops.department or "ฝ่ายวิจัย",
        account_number="555-9-87654-3",
        ticket_number="C-002/2569",
        request_date=today - timedelta(days=4),
        amount="11000.00",
        purpose="เดินทางประชุมชี้แจงโครงการ",
        period_year=f"06/{current_year_be}",
        status="กำลังดำเนินการ",
    )

    regular_request = _ensure_fund_request(
        session,
        user=custodian,
        form_type="30",
        requester_name=custodian.name,
        requester_position="เจ้าหน้าที่พัสดุ",
        department_name=setting.department_name,
        account_number=setting.account_number,
        ticket_number="0001/2569",
        request_date=today - timedelta(days=9),
        amount="4200.00",
        purpose="Office supplies for demo workflow",
        status="อนุมัติแล้ว",
    )
    _ensure_fund_request_item(
        session,
        fund_request=regular_request,
        description="Printer paper",
        amount="1200.00",
        category_type=3,
    )
    _ensure_fund_request_item(
        session,
        fund_request=regular_request,
        description="Name badges",
        amount="900.00",
        category_type=1,
    )
    _ensure_fund_request_item(
        session,
        fund_request=regular_request,
        description="Local delivery",
        amount="2100.00",
        category_type=2,
    )

    transferred_request = _ensure_fund_request(
        session,
        user=custodian,
        form_type="30",
        requester_name=custodian.name,
        requester_position="เจ้าหน้าที่พัสดุ",
        department_name=setting.department_name,
        account_number=setting.account_number,
        ticket_number="0003/2569",
        request_date=today - timedelta(days=12),
        amount="3600.00",
        purpose="Claim-linked demo request",
        status="โอนเงินสดย่อยสำเร็จ",
    )
    _ensure_fund_request_item(
        session,
        fund_request=transferred_request,
        description="Coffee and meeting refreshments",
        amount="1600.00",
        category_type=4,
    )
    _ensure_fund_request_item(
        session,
        fund_request=transferred_request,
        description="Printing services",
        amount="2000.00",
        category_type=5,
    )

    draft_request = _ensure_fund_request(
        session,
        user=custodian,
        form_type="30",
        requester_name=custodian.name,
        requester_position="เจ้าหน้าที่พัสดุ",
        department_name=setting.department_name,
        account_number=setting.account_number,
        ticket_number="0004/2569",
        request_date=today - timedelta(days=2),
        amount="1800.00",
        purpose="Draft request for testing",
        status="กำลังดำเนินการ",
    )
    _ensure_fund_request_item(
        session,
        fund_request=draft_request,
        description="Internet accessories",
        amount="1800.00",
        category_type=5,
    )

    draft_claim = _ensure_claim(
        session,
        user=custodian,
        setting=setting,
        fund_request=regular_request,
        status="ฉบับร่าง",
        total_amount="0.00",
    )
    _ensure_claim_item(
        session,
        claim=draft_claim,
        receipt_date=today - timedelta(days=5),
        description="Draft claim item",
        amount="1200.00",
        category_type=1,
    )
    _append_document_once(draft_claim, doc_claim)

    transferred_claim = _ensure_claim(
        session,
        user=custodian,
        setting=setting,
        fund_request=transferred_request,
        status="เอกสารตั้งฎีกา",
        total_amount="3600.00",
        transferred_at=today - timedelta(days=4),
        closing_document=closing_doc_1,
    )
    transferred_item_1 = _ensure_claim_item(
        session,
        claim=transferred_claim,
        receipt_date=today - timedelta(days=11),
        description="Refreshments for meeting",
        amount="1600.00",
        category_type=4,
    )
    transferred_item_2 = _ensure_claim_item(
        session,
        claim=transferred_claim,
        receipt_date=today - timedelta(days=10),
        description="Printing charges",
        amount="2000.00",
        category_type=3,
    )
    _ensure_claim_proof_file(
        session,
        claim=transferred_claim,
        claim_item=transferred_item_1,
        proof_reference="001/69-P1",
        filename="refreshments-receipt.jpg",
    )
    _ensure_claim_proof_file(
        session,
        claim=transferred_claim,
        claim_item=transferred_item_2,
        proof_reference="001/69-P2",
        filename="printing-receipt.jpg",
    )
    _append_document_once(transferred_claim, doc_claim)

    _ensure_bank_account_info(
        session,
        record_type="petty_cash",
        thai_name="เงินสดย่อย งานคลังและพัสดุ",
        created_at=datetime.now(),
        account_number="123-4-56789-0",
    )
    _ensure_bank_account_info(
        session,
        record_type="petty_cash",
        thai_name="เงินสดย่อย งานการศึกษา",
        created_at=datetime.now(),
        account_number="123-4-56789-1",
    )
    _ensure_bank_account_info(
        session,
        record_type="cash_advance",
        thai_name="เงินยืม หน่วยอาคารสถานที่ ยานพาหนะ",
        created_at=datetime.now(),
        account_number="123-4-56789-2",
    )
    _ensure_bank_account_info(
        session,
        record_type="cash_advance",
        thai_name="เงินยืม หน่วยพัฒนาบุคลากรฯ",
        created_at=datetime.now(),
        account_number="123-4-56789-3",
    )
    _ensure_bank_account_info(
        session,
        record_type="cash_advance",
        thai_name="เงินยืม ภาควิชารังสีเทคนิค",
        created_at=datetime.now(),
        account_number="123-4-56789-4",
    )
    _ensure_bank_account_info(
        session,
        record_type="cash_advance",
        thai_name="เงินยืม งานยุทธศาสตร์ฯ",
        created_at=datetime.now(),
        account_number="123-4-56789-5",
    )
    _ensure_bank_account_info(
        session,
        record_type="cash_advance",
        thai_name="เงินยืม ฝ่ายการเงินและบัญชี",
        created_at=datetime.now(),
        account_number="123-4-56789-6",
    )

    session.commit()

    return {
        "users": session.query(StaffAccount).count(),
        "settings": session.query(PettyCashSetting).count(),
        "closing_documents": session.query(ClosingDocument).count(),
        "documents": session.query(Document).count(),
        "borrowing_tickets": session.query(BorrowingTicket).count(),
        "return_details": session.query(ReturnDetail).count(),
        "parcel_return_details": session.query(ParcelReturnDetail).count(),
        "fund_requests": session.query(FundRequest).count(),
        "fund_request_items": session.query(FundRequestItem).count(),
        "petty_cash_claim_details": session.query(PettyCashClaimDetail).count(),
        "petty_cash_claim_items": session.query(PettyCashClaimItem).count(),
        "bank_account_infos": session.query(BankAccountInfo).count(),
    }
