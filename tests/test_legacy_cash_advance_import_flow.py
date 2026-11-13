"""Exercise automatic XLS import without loading the full Flask application."""

import ast
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import uuid
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]


def _import_route(context):
    source = ast.parse((ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig"))
    function = next(
        node for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name == "legacy_import"
    )
    function.decorator_list = []
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, "views.py", "exec"), context)
    return context["legacy_import"]


class FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, record):
        self.added.append(record)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class LegacyImportFlowTests(unittest.TestCase):
    def _run_upload(self, checks):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            db_session = FakeSession()
            report = SimpleNamespace(rows=[check.row for check in checks])
            context = {
                "request": SimpleNamespace(
                    method="POST",
                    files={"file": SimpleNamespace(
                        filename="old.xls", read=lambda size: b"old xls bytes"
                    )},
                ),
                "LEGACY_XLS_MAX_FILE_BYTES": 5 * 1024 * 1024,
                "parse_legacy_cash_advance_xls": lambda content: report,
                "_legacy_import_schema_ready": lambda: True,
                "_legacy_contract_checks": lambda parsed: checks,
                "_status_id": lambda group, code: {
                    "APPROVED": 7, "PARTIAL_RETURN": 8, "CLOSED": 9,
                }[code],
                "current_app": SimpleNamespace(
                    instance_path=temp_dir,
                    logger=SimpleNamespace(info=lambda *args: None, exception=lambda *args: None),
                ),
                "current_user": SimpleNamespace(id=3),
                "db": SimpleNamespace(session=db_session),
                "CashAdvanceImportBatch": lambda **values: SimpleNamespace(
                    kind="batch", id=10, **values
                ),
                "BorrowingTicket": lambda **values: SimpleNamespace(kind="ticket", **values),
                "jsonify": lambda values: values,
                "datetime": datetime,
                "ZoneInfo": ZoneInfo,
                "uuid": uuid,
                "os": __import__("os"),
                "ValueError": ValueError,
                "SQLAlchemyError": type("SQLAlchemyError", (Exception,), {}),
                "OSError": OSError,
                "LookupError": LookupError,
                "LegacyXlsError": type("LegacyXlsError", (ValueError,), {}),
            }
            result = _import_route(context)()
            source_files = list((Path(temp_dir) / "legacy_cash_advance_sources").glob("*.xls")) if (
                Path(temp_dir) / "legacy_cash_advance_sources"
            ).exists() else []
            file_contents = [path.read_bytes() for path in source_files]
            return result, db_session, file_contents

    def test_creates_only_passing_rows_immediately(self):
        row = SimpleNamespace(
            source_row=5, ticket_number="77/68", purpose="test",
            borrowed_amount=Decimal("100.00"),
            opening_balance_amount=Decimal("50.00"),
            due_date=date(2025, 12, 1), borrow_date=date(2025, 5, 14),
        )
        checks = [
            SimpleNamespace(row=row, ready_after_migration=True, borrower_ids=[20]),
            SimpleNamespace(
                row=SimpleNamespace(
                    source_row=6, ticket_number="88/68", borrower_name="Rejected Person"
                ),
                ready_after_migration=False, reasons=["เลขที่ยืมซ้ำในระบบ"],
            ),
        ]
        result, db_session, files = self._run_upload(checks)
        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(db_session.commits, 1)
        self.assertEqual([record.kind for record in db_session.added], ["batch", "ticket"])
        self.assertEqual(db_session.added[1].number, "77/68")
        self.assertEqual(db_session.added[1].status_id, 8)
        self.assertFalse(hasattr(db_session.added[1], "import_source_row"))
        self.assertEqual(files, [b"old xls bytes"])
        self.assertEqual(result["found_count"], 2)
        self.assertEqual(result["rejected"], [{
            "source_row": 6,
            "ticket_number": "88/68",
            "borrower_name": "Rejected Person",
            "reasons": ["เลขที่ยืมซ้ำในระบบ"],
        }])
        self.assertNotIn("77/68", str(result["rejected"]))

    def test_no_passing_rows_creates_no_batch_or_file(self):
        checks = [SimpleNamespace(
            row=SimpleNamespace(
                source_row=6, ticket_number="88/68", borrower_name="Rejected Person"
            ),
            ready_after_migration=False, reasons=["เลขที่ยืมซ้ำในระบบ"],
        )]
        result, db_session, files = self._run_upload(checks)
        self.assertEqual(result["imported_count"], 0)
        self.assertEqual(db_session.commits, 0)
        self.assertEqual(db_session.added, [])
        self.assertEqual(files, [])
        self.assertEqual(len(result["rejected"]), 1)

    def test_zero_net_balance_imports_as_closed_without_settlement_date(self):
        row = SimpleNamespace(
            source_row=5, ticket_number="77/68", purpose="test",
            borrowed_amount=Decimal("100.00"),
            opening_balance_amount=Decimal("0.00"),
            due_date=date(2025, 12, 1), borrow_date=date(2025, 5, 14),
        )
        checks = [SimpleNamespace(
            row=row, ready_after_migration=True, borrower_ids=[20]
        )]
        result, session, _ = self._run_upload(checks)
        ticket = session.added[1]
        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(ticket.status_id, 9)
        self.assertEqual(ticket.opening_balance_amount, Decimal("0.00"))
        self.assertIsNone(getattr(ticket, "settled_at", None))

    def test_missing_file_returns_json_error(self):
        route = _import_route({
            "request": SimpleNamespace(files={}),
            "jsonify": lambda values: values,
        })
        response, status = route()
        self.assertEqual(status, 400)
        self.assertIn("error", response)


if __name__ == "__main__":
    unittest.main()
