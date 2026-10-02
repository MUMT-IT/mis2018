"""Regression tests for the fund-request approval workflow."""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FundRequestApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views_text = (
            ROOT / "app/advance_payment/views.py"
        ).read_text(encoding="utf-8-sig")
        source = ast.parse(cls.views_text)
        helper = ast.Module(
            body=[
                node
                for node in source.body
                if isinstance(node, ast.FunctionDef)
                and node.name in {
                    "_approved_fund_request_status",
                    "_closed_fund_request_status",
                }
            ],
            type_ignores=[],
        )
        context = {"FUND_REQUEST_FORM_PETTY_CASH": "petty_cash"}
        exec(compile(helper, "views.py", "exec"), context)
        cls.approved_status = staticmethod(
            context["_approved_fund_request_status"]
        )
        cls.closed_status = staticmethod(context["_closed_fund_request_status"])

    def test_approved_status_depends_on_form_type(self):
        self.assertEqual(self.approved_status("petty_cash"), "อนุมัติแล้ว")
        self.assertEqual(self.approved_status("interest"), "เบิกเงินแล้ว")
        self.assertEqual(self.approved_status("borrowing"), "เบิกเงินแล้ว")

    def test_closed_status_depends_on_approval_timestamp(self):
        pending = type("FundRequest", (), {"approved_at": None})()
        approved = type("FundRequest", (), {"approved_at": object()})()

        self.assertEqual(self.closed_status(pending), "ใบเบิกถูกปฏิเสธ")
        self.assertEqual(self.closed_status(approved), "ยกเลิกใบเบิก")

    def test_new_requests_start_pending_and_keep_number_assignment(self):
        self.assertIn('status="รอการอนุมัติ"', self.views_text)
        self.assertIn(
            "_assign_fund_request_ticket_number(new_request, reference_date=req_date)",
            self.views_text,
        )
        self.assertIn(
            '(selected_fund_request.status or "").strip() != "อนุมัติแล้ว"',
            self.views_text,
        )
        self.assertIn("or not selected_fund_request.approved_at", self.views_text)
        self.assertIn(
            'and (selected_fund_request_context.status or "").strip() == "รอการอนุมัติ"',
            self.views_text,
        )

    def test_approval_and_rejection_controls_only_exist_on_claim_page(self):
        claim_template = (
            ROOT / "app/templates/advance_payment/submit_petty_cash_claim.html"
        ).read_text(encoding="utf-8-sig")
        history_template = (
            ROOT / "app/templates/advance_payment/staff_fund_request_history.html"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("advance_payment.approve_fund_request", claim_template)
        self.assertIn("advance_payment.reject_fund_request", claim_template)
        self.assertIn('data-popup-input-name="rejection_comment"', claim_template)
        self.assertNotIn("advance_payment.approve_fund_request", history_template)
        self.assertIn('data-popup-input-required="true"', claim_template)

    def test_rejection_closes_without_transfer_date(self):
        reject_source = self.views_text[
            self.views_text.index("def reject_fund_request"):
            self.views_text.index("def cancel_fund_request")
        ]
        self.assertIn("fund_req.cancel_at = datetime.now()", reject_source)
        self.assertIn("fund_req.rejection_comment = rejection_comment", reject_source)
        self.assertNotIn("cancel_transferred_at", reject_source)

    def test_migration_backfills_approved_at_from_created_at(self):
        migration = (
            ROOT
            / "migrations/versions/a4f7c9e2b6d1_add_fund_request_approval_timestamp.py"
        ).read_text(encoding="utf-8-sig")
        rejection_migration = (
            ROOT
            / "migrations/versions/b5d8e1f3a7c2_add_fund_request_rejection_comment.py"
        ).read_text(encoding="utf-8-sig")
        self.assertIn('sa.Column("approved_at", sa.DateTime(), nullable=True)', migration)
        self.assertIn(
            'sa.Column("rejection_comment", sa.String(length=4000), nullable=True)',
            rejection_migration,
        )
        self.assertIn("SET approved_at = created_at", migration)
        self.assertIn("TRIM(ticket_number) <> ''", migration)


if __name__ == "__main__":
    unittest.main()
