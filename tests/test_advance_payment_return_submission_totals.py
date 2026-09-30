"""Regression tests for linked-ticket return submission limits."""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReturnSubmissionTotalsTests(unittest.TestCase):
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
                and node.name == "_calculate_return_submission_totals"
            ],
            type_ignores=[],
        )
        cls.helper_code = compile(helper, "views.py", "exec")

    def test_limit_uses_every_ticket_in_the_linked_group(self):
        captured = {}

        def ticket_group_ids(ticket_id):
            return {32, 33} if ticket_id in {32, 33} else {ticket_id}

        def calculate_group_totals(ticket_ids):
            captured["ticket_ids"] = set(ticket_ids)
            return {
                "cumulative_total": 9000,
                "budget": 11000,
                "remaining_amount": 2000,
            }

        context = {
            "_ticket_group_ids": ticket_group_ids,
            "_calculate_return_form_group_totals": calculate_group_totals,
        }
        exec(self.helper_code, context)

        totals = context["_calculate_return_submission_totals"]({33})

        self.assertEqual(captured["ticket_ids"], {32, 33})
        self.assertEqual(totals["remaining_amount"], 2000)


if __name__ == "__main__":
    unittest.main()
