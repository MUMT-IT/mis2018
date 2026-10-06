"""Regression coverage for pending amounts on advance-payment summary cards."""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PendingAmountSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views_source = (
            ROOT / "app/advance_payment/views.py"
        ).read_text(encoding="utf-8-sig")
        cls.views_tree = ast.parse(cls.views_source)
        cls.verification_template = (
            ROOT / "app/templates/advance_payment/verification.html"
        ).read_text(encoding="utf-8-sig")
        cls.petty_cash_template = (
            ROOT / "app/templates/advance_payment/submit_petty_cash_claim.html"
        ).read_text(encoding="utf-8-sig")

    def test_verification_summary_shows_all_five_amount_columns(self):
        for label in (
            "ยอดเงินยืม",
            "ยอดคืนแล้ว",
            "ยอดรอตรวจสอบ",
            "ยอดคงค้าง",
            "วันครบกำหนด",
        ):
            self.assertIn(label, self.verification_template)
        self.assertIn("summary.pending_amount", self.verification_template)
        self.assertIn("summary.unsubmitted_amount", self.verification_template)
        summary_position = self.verification_template.rindex(
            "<strong>ยอดเงินยืม</strong>"
        )
        self.assertGreater(
            summary_position,
            self.verification_template.index('class="status-flow"'),
        )
        self.assertLess(
            summary_position,
            self.verification_template.index(
                "{% if advance_payment_role == 'finance' %}",
                summary_position,
            ),
        )

    def test_petty_cash_summary_uses_status_split_helper(self):
        helper = next(
            node
            for node in self.views_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_calculate_fund_request_display_summary"
        )
        helper_source = ast.unparse(helper)
        self.assertIn("if claim.approved_at", helper_source)
        self.assertIn("if parcel_return.approved_at", helper_source)
        self.assertNotIn("pending_statuses", helper_source)

        submit_view = next(
            node
            for node in self.views_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "submit_petty_cash_claim"
        )
        helper_calls = [
            node
            for node in ast.walk(submit_view)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_calculate_fund_request_display_summary"
        ]
        self.assertEqual(len(helper_calls), 1)

        for label in (
            "ยอดที่ขอไป",
            "ยอดส่งเบิกแล้ว",
            "ยอดรอตรวจสอบ",
            "ยอดคงค้าง",
        ):
            self.assertIn(label, self.petty_cash_template)
        self.assertIn("fund_request_total_info.approved_total", self.petty_cash_template)
        self.assertIn("fund_request_total_info.pending_total", self.petty_cash_template)
        self.assertIn("fund_request_total_info.unsubmitted_amount", self.petty_cash_template)
        summary_position = self.petty_cash_template.index(
            "<strong>ยอดที่ขอไป</strong>"
        )
        self.assertGreater(
            summary_position,
            self.petty_cash_template.index('class="status-flow"'),
        )
        self.assertLess(
            summary_position,
            self.petty_cash_template.index(
                "{% if verification_fund_request %}", summary_position
            ),
        )
        self.assertIn(
            "fund_request_total_info is defined and verification_fund_request "
            "and verification_fund_request.approved_at",
            self.petty_cash_template,
        )

    def test_fund_request_note_and_rejection_visibility(self):
        self.assertIn(
            "{{ verification_fund_request.personal_note or '-' }}",
            self.petty_cash_template,
        )
        self.assertIn(
            "{% if not verification_fund_request.approved_at and "
            "verification_fund_request.rejection_comment %}",
            self.petty_cash_template,
        )

    def test_cash_return_only_claims_receive_an_approval_timestamp(self):
        submit_view = next(
            node
            for node in self.views_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "submit_petty_cash_claim"
        )
        submit_source = ast.unparse(submit_view)
        self.assertIn(
            "if is_cash_return_only:\n            claim_detail.approved_at = datetime.now()",
            submit_source,
        )


if __name__ == "__main__":
    unittest.main()
