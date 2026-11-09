"""Regression coverage for petty-cash ledger row date handling."""

import ast
from datetime import date, datetime
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _load_normalize_ledger_row_dates():
    source = (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
    module = ast.parse(source)
    wanted_helpers = {"_coerce_date", "_normalize_ledger_row_dates"}
    helper_module = ast.Module(
        body=[
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name in wanted_helpers
        ],
        type_ignores=[],
    )
    context = {"date": date, "datetime": datetime}
    exec(compile(helper_module, "views.py", "exec"), context)
    return context["_normalize_ledger_row_dates"]


class PettyCashLedgerDateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normalize_dates = staticmethod(_load_normalize_ledger_row_dates())

    def test_undated_ledger_rows_are_omitted(self):
        self.assertIsNone(
            self.normalize_dates(None, datetime(2026, 10, 6, 8, 56))
        )

    def test_ledger_dates_are_normalized_for_sorting(self):
        self.assertEqual(
            self.normalize_dates(
                datetime(2026, 10, 5, 14, 30),
                date(2026, 10, 4),
            ),
            (
                date(2026, 10, 5),
                datetime(2026, 10, 4),
            ),
        )

    def test_missing_created_at_uses_the_transaction_date(self):
        self.assertEqual(
            self.normalize_dates(date(2026, 10, 5), None),
            (
                date(2026, 10, 5),
                datetime(2026, 10, 5),
            ),
        )


if __name__ == "__main__":
    unittest.main()
