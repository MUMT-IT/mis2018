"""Regression tests for totals shown on the ticket verification page."""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class VerificationTotalsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ast.parse(
            (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
        )
        cls.verification_view = next(
            node
            for node in source.body
            if isinstance(node, ast.FunctionDef) and node.name == "verification_view"
        )

    def test_display_uses_approved_totals_and_form_keeps_submitted_totals(self):
        assignments = {
            target.id: value
            for node in ast.walk(self.verification_view)
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
            for value in [node.value]
        }

        approved_call = assignments["approved_return_totals"]
        form_call = assignments["return_form_totals"]
        allocation_call = assignments["ticket_allocation_rows"]

        self.assertEqual(approved_call.func.id, "_calculate_ticket_group_totals")
        self.assertEqual(form_call.func.id, "_calculate_return_form_group_totals")
        self.assertEqual(allocation_call.args[1].id, "approved_return_totals")

        render_call = next(
            node
            for node in ast.walk(self.verification_view)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "render_template"
        )
        render_args = {keyword.arg: keyword.value for keyword in render_call.keywords}

        self.assertEqual(render_args["group_summary"].id, "approved_return_totals")
        self.assertEqual(render_args["return_form_summary"].id, "return_form_summary")

    def test_summary_splits_approved_pending_and_unsubmitted_amounts(self):
        assignments = {
            target.slice.value: value
            for node in ast.walk(self.verification_view)
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Name)
            and target.value.id == "summary"
            and isinstance(target.slice, ast.Constant)
            for value in [node.value]
        }

        self.assertIn("pending_amount", assignments)
        self.assertIn("unsubmitted_amount", assignments)

        pending_expression = ast.unparse(assignments["pending_amount"])
        unsubmitted_expression = ast.unparse(assignments["unsubmitted_amount"])
        self.assertIn("submitted_ticket_total - approved_ticket_total", pending_expression)
        self.assertIn("summary['budget']", unsubmitted_expression)
        self.assertIn("submitted_ticket_total", unsubmitted_expression)


if __name__ == "__main__":
    unittest.main()
