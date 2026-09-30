"""Regression tests for typed parcel-return records."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ParcelReturnTypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ast.parse(
            (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
        )
        helper = ast.Module(
            body=[
                node
                for node in source.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "_create_parcel_return_record"
            ],
            type_ignores=[],
        )
        cls.helper_code = compile(helper, "views.py", "exec")

    def _create_record(self, parcel_type=None):
        saved = []
        session = SimpleNamespace(
            add=saved.append,
            flush=lambda: None,
            commit=lambda: None,
        )
        context = {
            "PARCEL_RETURN_TYPE_LABELS": {1: "ว-119", 5: "ว-5763"},
            "ParcelReturnDetail": lambda **kwargs: SimpleNamespace(id=99, **kwargs),
            "db": SimpleNamespace(session=session),
            "datetime": SimpleNamespace(now=lambda: "now"),
            "parcel_borrowing_ticket_association": None,
            "_send_notification_email": lambda *args, **kwargs: None,
            "_recalculate_borrowing_ticket_status": lambda *args: None,
            "_recalculate_fund_request_submission_status": lambda *args: None,
        }
        exec(self.helper_code, context)
        record = context["_create_parcel_return_record"](
            amount=12000,
            items_description="ทดสอบ",
            sent_date="2026-09-30",
            parcel_type=parcel_type,
        )
        self.assertIs(record, saved[0])
        return record

    def test_legacy_parcel_return_keeps_null_type(self):
        self.assertIsNone(self._create_record().type)

    def test_supported_circular_type_is_saved_without_amount_cap(self):
        self.assertEqual(self._create_record(parcel_type=1).type, 1)

    def test_unsupported_circular_type_is_rejected(self):
        with self.assertRaises(ValueError):
            self._create_record(parcel_type=2)


class CircularReturnReferenceTests(unittest.TestCase):
    def test_reference_uses_docs_query_drive_id_and_view_url(self):
        views_source = (ROOT / "app/advance_payment/views.py").read_text(
            encoding="utf-8-sig"
        )
        tooltip_source = (
            ROOT
            / "app/templates/advance_payment/partials/circular_return_reference_tooltip.html"
        ).read_text(encoding="utf-8-sig")

        self.assertIn(
            'CIRCULAR_RETURN_REFERENCE_DRIVE_ID = "1ZhYI4pAD4sOSV0LlkaTAM--HnA4ugatE"',
            views_source,
        )
        self.assertIn("DocsQueryDocument.drive_file_id", views_source)
        self.assertIn(
            "circular_return_reference_document.drive_view_url",
            tooltip_source,
        )


if __name__ == "__main__":
    unittest.main()
