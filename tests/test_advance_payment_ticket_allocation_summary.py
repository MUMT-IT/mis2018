"""Regression tests for displaying a grouped return as per-ticket totals."""
import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TicketAllocationSummaryTests(unittest.TestCase):
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
                and node.name == "_ticket_allocation_rows"
            ],
            type_ignores=[],
        )
        context = {"datetime": datetime}
        exec(compile(helper, "views.py", "exec"), context)
        cls.build_rows = staticmethod(context["_ticket_allocation_rows"])

    def test_group_total_is_split_across_tickets_in_approval_order(self):
        later_ticket = SimpleNamespace(
            id=2,
            number="2/2569",
            required_budget=6000,
            approved_at=datetime(2026, 1, 2),
        )
        first_ticket = SimpleNamespace(
            id=1,
            number="1/2569",
            required_budget=5000,
            approved_at=datetime(2026, 1, 1),
        )

        rows = self.build_rows(
            [later_ticket, first_ticket],
            {"allocated_by_ticket": {1: 5000, 2: 2000}},
        )

        self.assertEqual([row["ticket_id"] for row in rows], [1, 2])
        self.assertEqual(rows[0]["cumulative_total"], 5000)
        self.assertEqual(rows[0]["remaining_amount"], 0)
        self.assertEqual(rows[1]["cumulative_total"], 2000)
        self.assertEqual(rows[1]["remaining_amount"], 4000)


if __name__ == "__main__":
    unittest.main()
