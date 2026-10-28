"""Exercise parcel draft persistence without importing the full web app."""

import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String, Table, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


ROOT = Path(__file__).resolve().parents[1]


class ParcelDraftTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        base = declarative_base()

        class ParcelReturnDetail(base):
            __tablename__ = "parcel_returns"
            id = Column(Integer, primary_key=True)
            ticket_id = Column(Integer)
            fund_request_id = Column(Integer)
            amount_spent = Column(Numeric(12, 2))
            items_description = Column(String)
            sent_date = Column(Date)
            type = Column(Integer)
            status = Column(String)
            created_at = Column(DateTime)

        class FundRequest(base):
            __tablename__ = "fund_requests"
            id = Column(Integer, primary_key=True)

        association = Table(
            "parcel_ticket_links",
            base.metadata,
            Column("parcel_return_id", Integer),
            Column("ticket_id", Integer),
        )
        base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        self.messages = []
        self.recalculations = []
        self.fund_recalculations = []
        self.session.add(FundRequest(id=88))
        self.session.commit()

        source = ast.parse((ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig"))
        helper = next(
            node for node in source.body
            if isinstance(node, ast.FunctionDef) and node.name == "_create_parcel_return_record"
        )
        namespace = {
            "datetime": datetime,
            "db": SimpleNamespace(session=self.session),
            "ParcelReturnDetail": ParcelReturnDetail,
            "FundRequest": FundRequest,
            "_fund_request_is_borrowing_passthrough": lambda fund_request: False,
            "parcel_borrowing_ticket_association": association,
            "PARCEL_RETURN_TYPE_LABELS": {1: "ว-119", 5: "ว-5763"},
            "_send_notification_email": lambda *args, **kwargs: self.messages.append(args),
            "_recalculate_borrowing_ticket_status": lambda ticket_id: self.recalculations.append(ticket_id),
            "_recalculate_fund_request_submission_status": lambda fund_request_id: self.fund_recalculations.append(fund_request_id),
        }
        exec(compile(ast.Module(body=[helper], type_ignores=[]), "views.py", "exec"), namespace)
        self.save = namespace["_create_parcel_return_record"]
        self.model = ParcelReturnDetail

    def tearDown(self):
        self.session.close()

    def test_standard_and_typed_drafts_update_then_submit_without_duplicates(self):
        standard = self.save(
            ticket_id=45, amount=100, items_description="first", sent_date=datetime(2026, 10, 27).date(),
            status="ฉบับร่าง",
        )
        typed = self.save(
            ticket_id=45, amount=200, items_description="typed", sent_date=datetime(2026, 10, 27).date(),
            parcel_type=1, status="ฉบับร่าง",
        )
        self.session.commit()
        self.assertEqual(self.messages, [])
        self.assertEqual(self.recalculations, [])

        updated = self.save(
            ticket_id=45, amount=150, items_description="updated", sent_date=datetime(2026, 10, 28).date(),
            status="ฉบับร่าง",
        )
        switched_type = self.save(
            ticket_id=45, amount=250, items_description="typed updated", sent_date=datetime(2026, 10, 28).date(),
            parcel_type=5, status="ฉบับร่าง",
        )
        self.session.commit()
        self.assertEqual((updated.id, switched_type.id), (standard.id, typed.id))
        self.assertEqual(self.session.query(self.model).count(), 2)

        submitted = self.save(
            ticket_id=45, amount=150, items_description="updated", sent_date=datetime(2026, 10, 28).date(),
            status="รอตรวจสอบ", reuse_draft=True,
        )
        submitted_typed = self.save(
            ticket_id=45, amount=250, items_description="typed updated", sent_date=datetime(2026, 10, 28).date(),
            parcel_type=5, status="รอตรวจสอบ", reuse_draft=True,
        )
        self.assertEqual(submitted.id, standard.id)
        self.assertEqual(submitted_typed.id, typed.id)
        self.assertEqual(self.session.query(self.model).count(), 2)
        self.assertEqual(len(self.messages), 2)
        self.assertEqual(self.recalculations, [45, 45])

    def test_fund_request_parcel_drafts_stay_hidden_until_submission(self):
        standard = self.save(
            fund_request_id=88, amount=100, items_description="standard",
            sent_date=datetime(2026, 10, 27).date(), status="ฉบับร่าง",
        )
        typed = self.save(
            fund_request_id=88, amount=200, items_description="circular",
            sent_date=datetime(2026, 10, 27).date(), parcel_type=1, status="ฉบับร่าง",
        )
        self.session.commit()
        self.assertEqual(self.messages, [])
        self.assertEqual(self.fund_recalculations, [])
        self.assertEqual(self.session.query(self.model).filter(self.model.status != "ฉบับร่าง").count(), 0)

        updated = self.save(
            fund_request_id=88, amount=125, items_description="updated",
            sent_date=datetime(2026, 10, 28).date(), status="ฉบับร่าง",
        )
        self.session.commit()
        self.assertEqual(updated.id, standard.id)

        submitted = self.save(
            fund_request_id=88, amount=125, items_description="updated",
            sent_date=datetime(2026, 10, 28).date(), status="รอตรวจสอบ", reuse_draft=True,
        )
        submitted_typed = self.save(
            fund_request_id=88, amount=200, items_description="circular",
            sent_date=datetime(2026, 10, 27).date(), parcel_type=1,
            status="รอตรวจสอบ", reuse_draft=True,
        )
        self.assertEqual((submitted.id, submitted_typed.id), (standard.id, typed.id))
        self.assertEqual(self.session.query(self.model).count(), 2)
        self.assertEqual(len(self.messages), 2)
        self.assertEqual(self.fund_recalculations, [88, 88])


if __name__ == "__main__":
    unittest.main()
