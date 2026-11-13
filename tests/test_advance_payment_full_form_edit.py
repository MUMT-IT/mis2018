"""Regression coverage for full-form return and petty-cash claim editing."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FullFormEditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views = (ROOT / "app/advance_payment/views.py").read_text(
            encoding="utf-8-sig"
        )
        cls.return_detail = (
            ROOT / "app/templates/advance_payment/return_proof_detail.html"
        ).read_text(encoding="utf-8-sig")
        cls.return_form = (
            ROOT / "app/templates/advance_payment/partials/return_ticket_form.html"
        ).read_text(encoding="utf-8-sig")
        cls.claim_detail = (
            ROOT / "app/templates/advance_payment/petty_cash_claim_detail.html"
        ).read_text(encoding="utf-8-sig")
        cls.claim_form = (
            ROOT / "app/templates/advance_payment/submit_petty_cash_claim.html"
        ).read_text(encoding="utf-8-sig")
        cls.verification = (
            ROOT / "app/templates/advance_payment/verification.html"
        ).read_text(encoding="utf-8-sig")
        cls.borrower_dashboard = (
            ROOT / "app/templates/advance_payment/borrower_dashboard.html"
        ).read_text(encoding="utf-8-sig")
        cls.coordinator_dashboard = (
            ROOT / "app/templates/advance_payment/coordinator_dashboard.html"
        ).read_text(encoding="utf-8-sig")

    def test_detail_pages_link_to_the_existing_create_forms(self):
        self.assertIn("edit_return_id=return_detail.id", self.return_detail)
        self.assertIn("edit_claim_id=claim_detail.id", self.claim_detail)
        self.assertIn('name="edit_return_id"', self.return_form)
        self.assertIn('name="edit_claim_id"', self.claim_form)

    def test_inline_and_full_form_edits_share_permission_helpers(self):
        self.assertIn("def _can_edit_return_detail", self.views)
        self.assertIn("def _can_edit_petty_cash_claim", self.views)
        self.assertIn("{% if can_edit_return_detail %}", self.return_detail)
        self.assertIn("{% if can_edit_claim %}", self.claim_detail)

    def test_editing_reuses_the_record_and_requires_confirmation(self):
        self.assertIn("else edit_return_detail", self.views)
        self.assertIn("existing_draft = edit_claim_detail", self.views)
        self.assertGreaterEqual(self.views.count('"รอยืนยันการแก้ไข"'), 3)

    def test_edit_mode_does_not_offer_draft_autosave(self):
        self.assertIn("if not return_edit_detail|default(none)", self.return_form)
        self.assertIn("if not claim_edit_mode|default(false)", self.claim_form)
        self.assertIn(
            "if ({{ 'true' if claim_edit_mode|default(false) else 'false' }}) return;",
            self.claim_form,
        )

    def test_borrowing_ticket_edit_entry_is_on_verification_only(self):
        edit_link = "edit_ticket_id=borrowing_ticket.id"
        self.assertNotIn(edit_link, self.borrower_dashboard)
        self.assertNotIn(edit_link, self.coordinator_dashboard)
        self.assertIn(edit_link, self.verification)
        self.assertIn("{% if can_edit_borrowing_ticket %}", self.verification)

    def test_parcel_return_edit_uses_the_same_permission_rule(self):
        self.assertIn("def _can_edit_parcel_return", self.views)
        self.assertIn("{% if pr.can_edit %}", self.verification)
        route_start = self.views.index(
            '@bp.route("/coordinator/parcel-returns/<int:parcel_return_id>/edit"'
        )
        route_end = self.views.index(
            '@bp.route("/finance/parcel-returns/', route_start
        )
        route_source = self.views[route_start:route_end]
        self.assertIn("@module_system_required(ADVANCE_PAYMENT_SYSTEM)", route_source)
        self.assertNotIn("@module_role_required", route_source)
        self.assertIn("_can_edit_parcel_return(", route_source)


if __name__ == "__main__":
    unittest.main()
