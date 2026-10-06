"""Regression tests for the fund-request approval workflow."""

import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FundRequestApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views_text = (
            ROOT / "app/advance_payment/views.py"
        ).read_text(encoding="utf-8-sig")
        cls.pdf_text = (
            ROOT / "app/advance_payment/pdf_utils.py"
        ).read_text(encoding="utf-8-sig")
        wanted_helpers = {
            "_staff_accounts_match",
            "_fund_request_signature_state",
            "_fund_request_expected_confirmer_id",
            "_fund_request_is_fully_approved",
            "_sync_fund_request_approval_status",
        }
        parsed = ast.parse(cls.views_text)
        helper_nodes = [
            node
            for node in parsed.body
            if isinstance(node, ast.FunctionDef) and node.name in wanted_helpers
        ]
        namespace = {
            "_fund_request_custodian_id": lambda fund_request: fund_request.custodian_id,
            "_fund_request_requester_is_org_head": (
                lambda fund_request: getattr(fund_request, "requester_is_head", False)
            ),
            "_apply_delegated_head_requester_confirmation": lambda _fund_request: False,
        }
        exec(compile(ast.Module(helper_nodes, type_ignores=[]), "workflow_helpers", "exec"), namespace)
        cls.workflow = SimpleNamespace(**namespace)

    def test_all_signatures_are_required_before_approval(self):
        self.assertIn("def _fund_request_is_fully_approved", self.views_text)
        self.assertIn('signatures["requester_signed"]', self.views_text)
        self.assertIn('signatures["custodian_signed"]', self.views_text)
        self.assertIn('getattr(fund_request, "approved_by_id", None)', self.views_text)
        self.assertIn('fund_request.status = "อนุมัติแล้ว"', self.views_text)

    def test_confirmation_and_approval_record_the_actor(self):
        self.assertIn("fund_req.confirmed_at = acted_at", self.views_text)
        self.assertIn("fund_req.confirmed_by_id = staff.id", self.views_text)
        self.assertIn("fund_req.approved_at = acted_at", self.views_text)
        self.assertIn("fund_req.approved_by_id = staff.id", self.views_text)

    def test_head_can_confirm_after_custodian_has_already_approved(self):
        self.assertIn(
            'not current_is_head\n            or getattr(verification_fund_request, "approved_at", None)',
            self.views_text,
        )

    def test_head_identity_matches_linked_account_records(self):
        resolved_head = SimpleNamespace(
            id=10,
            personal_id=100,
            email="prasit.man@mahidol.ac.th",
        )
        login_by_email = SimpleNamespace(
            id=20,
            personal_id=None,
            email="PRASIT.MAN@MAHIDOL.AC.TH",
        )
        login_by_personal_record = SimpleNamespace(
            id=30,
            personal_id=100,
            email="different@example.org",
        )

        self.assertTrue(
            self.workflow._staff_accounts_match(
                resolved_head,
                login_by_email,
            )
        )
        self.assertTrue(
            self.workflow._staff_accounts_match(
                resolved_head,
                login_by_personal_record,
            )
        )

    def test_head_lookup_matches_pdf_signature_resolution(self):
        source = self.views_text[
            self.views_text.index("def _fund_request_org_head"):
            self.views_text.index("def _staff_accounts_match")
        ]
        email_lookup = ".filter(StaffAccount.email == head_identifier)"
        position_lookup = (
            "StaffHeadPosition.staff_account_id == head_account.id"
        )
        personal_lookup = "StaffPersonalInfo.id == personal_id"

        self.assertIn(email_lookup, source)
        self.assertIn(position_lookup, source)
        self.assertIn(personal_lookup, source)
        self.assertLess(source.index(email_lookup), source.index(position_lookup))

    def test_fund_request_pdf_uses_head_and_custodian_names_directly(self):
        source = self.pdf_text[
            self.pdf_text.index("def generate_fund_request_pdf"):
            self.pdf_text.index("def generate_petty_cash_ledger_pdf")
        ]
        self.assertNotIn("approver_name", source)
        self.assertNotIn("approver_position", source)
        self.assertNotIn("keeper_name", source)
        self.assertNotIn("keeper_pos", source)
        self.assertIn("( {head_name} )", source)
        self.assertIn("( {custodian_name} )", source)
        self.assertIn("delegated_requester_confirmation", source)
        self.assertIn(
            "requester_signature_line = requester if requester_signed_at else signature_placeholder",
            source,
        )
        self.assertIn(
            "custodian_signature_line = custodian_name if custodian_signed_at else signature_placeholder",
            source,
        )
        self.assertIn(
            "head_signature_line = head_name if approved_at else signature_placeholder",
            source,
        )
        self.assertIn("<br/>{requester_signature_line}<br/>", source)
        self.assertIn("<br/>{custodian_signature_line}<br/>", source)
        self.assertIn("<br/>{head_signature_line}<br/>", source)

    def test_requester_creator_waits_for_custodian_then_approval(self):
        created_at = datetime(2026, 10, 5, 9, 0)
        confirmed_at = datetime(2026, 10, 5, 10, 0)
        approved_at = datetime(2026, 10, 5, 11, 0)
        fund_request = SimpleNamespace(
            creator_id=10,
            requester_id=10,
            custodian_id=20,
            created_at=created_at,
            confirmed_at=None,
            confirmed_by_id=None,
            approved_at=None,
            approved_by_id=None,
            status="รอการอนุมัติ",
        )

        self.assertEqual(
            self.workflow._fund_request_expected_confirmer_id(fund_request),
            20,
        )
        fund_request.confirmed_at = confirmed_at
        fund_request.confirmed_by_id = 20
        self.assertIsNone(
            self.workflow._fund_request_expected_confirmer_id(fund_request)
        )
        self.assertEqual(
            self.workflow._sync_fund_request_approval_status(fund_request),
            "รอการอนุมัติ",
        )

        fund_request.approved_at = approved_at
        fund_request.approved_by_id = 30
        self.assertEqual(
            self.workflow._sync_fund_request_approval_status(fund_request),
            "อนุมัติแล้ว",
        )

    def test_creator_holding_both_roles_needs_no_counterparty_confirmation(self):
        fund_request = SimpleNamespace(
            creator_id=10,
            requester_id=10,
            custodian_id=10,
            created_at=datetime(2026, 10, 5, 9, 0),
            confirmed_at=None,
            confirmed_by_id=None,
            approved_at=None,
            approved_by_id=None,
            status="รอการอนุมัติ",
        )

        signatures = self.workflow._fund_request_signature_state(fund_request)
        self.assertTrue(signatures["requester_signed"])
        self.assertTrue(signatures["custodian_signed"])
        self.assertIsNone(
            self.workflow._fund_request_expected_confirmer_id(fund_request)
        )

    def test_custodian_delegated_approval_satisfies_head_requester_role(self):
        acted_at = datetime(2026, 10, 6, 9, 0)
        fund_request = SimpleNamespace(
            creator_id=20,
            requester_id=10,
            custodian_id=20,
            requester_is_head=True,
            created_at=datetime(2026, 10, 5, 9, 0),
            confirmed_at=acted_at,
            confirmed_by_id=20,
            approved_at=acted_at,
            approved_by_id=20,
            status="รอการอนุมัติ",
        )

        signatures = self.workflow._fund_request_signature_state(fund_request)
        self.assertTrue(signatures["requester_signed"])
        self.assertTrue(signatures["custodian_signed"])
        self.assertEqual(
            self.workflow._sync_fund_request_approval_status(fund_request),
            "อนุมัติแล้ว",
        )

        approve_source = self.views_text[
            self.views_text.index("def approve_fund_request"):
            self.views_text.index("def record_fund_request_withdrawal")
        ]
        self.assertIn("delegated_head_requester", approve_source)
        self.assertIn("_fund_request_requester_is_org_head(fund_req)", approve_source)

    def test_existing_delegated_approval_is_reconciled_on_open(self):
        helper_source = self.views_text[
            self.views_text.index("def _apply_delegated_head_requester_confirmation"):
            self.views_text.index("def _sync_fund_request_approval_status")
        ]
        self.assertIn("approved_by_id == custodian_id", helper_source)
        self.assertIn("fund_request.confirmed_at = approved_at", helper_source)
        self.assertIn("fund_request.confirmed_by_id = approved_by_id", helper_source)
        self.assertIn(
            "_sync_fund_request_approval_status(selected_fund_request)",
            self.views_text,
        )

    def test_withdrawal_requires_complete_approval(self):
        withdrawal_source = self.views_text[
            self.views_text.index("def record_fund_request_withdrawal"):
            self.views_text.index("def reject_fund_request")
        ]
        self.assertIn("_fund_request_is_fully_approved(fund_req)", withdrawal_source)
        self.assertIn('fund_req.status = "เบิกเงินแล้ว"', withdrawal_source)
        self.assertIn("fund_req.request_date = request_date", withdrawal_source)
        self.assertIn("FUND_REQUEST_FORM_INTEREST", withdrawal_source)

    def test_status_recalculation_cannot_bypass_withdrawal_recording(self):
        recalculation_source = self.views_text[
            self.views_text.index("def _recalculate_fund_request_submission_status"):
            self.views_text.index("def submit_parcel_return")
        ]
        allowed_statuses = recalculation_source[
            recalculation_source.index("if fund_request_status not in {"):
            recalculation_source.index("claims = (")
        ]
        self.assertNotIn('"อนุมัติแล้ว"', allowed_statuses)
        self.assertIn('"เบิกเงินแล้ว"', allowed_statuses)

    def test_new_requests_start_pending_and_keep_number_assignment(self):
        self.assertIn('status="รอการอนุมัติ"', self.views_text)
        self.assertIn(
            "reference_date=created_at.date()",
            self.views_text,
        )
        self.assertIn(
            '(selected_fund_request.status or "").strip() != "เบิกเงินแล้ว"',
            self.views_text,
        )
        self.assertIn("or not selected_fund_request.request_date", self.views_text)
        self.assertIn(
            'in {"รอการอนุมัติ", "อนุมัติแล้ว"}',
            self.views_text,
        )

    def test_creating_fund_request_does_not_download_pdf(self):
        create_source = self.views_text[
            self.views_text.index("def staff_fund_request"):
            self.views_text.index("def confirm_fund_request")
        ]
        form_template = (
            ROOT / "app/templates/advance_payment/staff_fund_request.html"
        ).read_text(encoding="utf-8-sig")

        self.assertNotIn("generate_fund_request_pdf(new_request)", create_source)
        self.assertNotIn("Fund_Request.pdf", form_template)
        self.assertNotIn("return res.blob()", form_template)
        self.assertIn(
            "if form_type != FUND_REQUEST_FORM_PETTY_CASH:",
            create_source,
        )
        self.assertIn("return staff_fund_request_history()", create_source)
        self.assertIn("return submit_petty_cash_claim(", create_source)
        self.assertIn("_render_after_post=True", create_source)
        self.assertIn("_forced_fund_request_id=new_request.id", create_source)
        self.assertIn('submitBtn.innerText = "กำลังบันทึก..."', form_template)

    def test_approval_and_rejection_controls_only_exist_on_claim_page(self):
        claim_template = (
            ROOT / "app/templates/advance_payment/submit_petty_cash_claim.html"
        ).read_text(encoding="utf-8-sig")
        history_template = (
            ROOT / "app/templates/advance_payment/staff_fund_request_history.html"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("advance_payment.confirm_fund_request", claim_template)
        self.assertIn("advance_payment.approve_fund_request", claim_template)
        self.assertIn("advance_payment.record_fund_request_withdrawal", claim_template)
        self.assertIn("advance_payment.reject_fund_request", claim_template)
        self.assertIn('data-popup-input-name="rejection_comment"', claim_template)
        self.assertNotIn("advance_payment.approve_fund_request", history_template)
        self.assertIn('data-popup-input-required="true"', claim_template)

    def test_rejection_closes_without_transfer_date(self):
        reject_source = self.views_text[
            self.views_text.index("def reject_fund_request"):
            self.views_text.index("def cancel_fund_request")
        ]
        self.assertIn("is_head = _is_fund_request_org_head(staff, fund_req)", reject_source)
        self.assertIn("not (is_head or is_custodian)", reject_source)
        self.assertIn("fund_req.cancel_at = datetime.now()", reject_source)
        self.assertIn("fund_req.rejection_comment = rejection_comment", reject_source)
        self.assertNotIn("cancel_transferred_at", reject_source)

    def test_only_custodian_can_record_withdrawal(self):
        withdrawal_source = self.views_text[
            self.views_text.index("def record_fund_request_withdrawal"):
            self.views_text.index("def reject_fund_request")
        ]
        self.assertIn("_is_petty_cash_custodian(staff, setting)", withdrawal_source)
        self.assertNotIn("is_head =", withdrawal_source)

    def test_post_approval_buttons_match_withdrawal_button_height(self):
        claim_template = (
            ROOT / "app/templates/advance_payment/submit_petty_cash_claim.html"
        ).read_text(encoding="utf-8-sig")
        self.assertIn(
            'class="d-flex flex-wrap justify-content-end align-items-end gap-2"',
            claim_template,
        )
        self.assertIn(
            'class="btn btn-outline-danger btn-sm fw-bold px-3 py-2"',
            claim_template,
        )

    def test_withdrawal_details_are_collected_in_modal(self):
        claim_template = (
            ROOT / "app/templates/advance_payment/submit_petty_cash_claim.html"
        ).read_text(encoding="utf-8-sig")
        self.assertIn('data-bs-target="#fundRequestWithdrawalModal', claim_template)
        self.assertIn('id="fundRequestWithdrawalModal{{', claim_template)
        self.assertIn("advance_payment.record_fund_request_withdrawal", claim_template)
        self.assertIn('name="request_date"', claim_template)
        self.assertIn('name="withdrawal_proof_file"', claim_template)

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

    def test_confirmation_migration_makes_request_date_nullable(self):
        migration = (
            ROOT
            / "migrations/versions/e04a52c8d9f1_add_fund_request_confirmation_fields.py"
        ).read_text(encoding="utf-8-sig")
        self.assertIn('sa.Column("confirmed_at", sa.DateTime(), nullable=True)', migration)
        self.assertIn('sa.Column("confirmed_by_id", sa.Integer(), nullable=True)', migration)
        self.assertIn('sa.Column("approved_by_id", sa.Integer(), nullable=True)', migration)
        self.assertIn('"request_date",', migration)
        self.assertIn("nullable=True", migration)
        self.assertIn("SET status = 'เบิกเงินแล้ว'", migration)
        self.assertIn("WHERE status = 'อนุมัติแล้ว'", migration)


if __name__ == "__main__":
    unittest.main()
