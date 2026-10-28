"""Regression coverage for finance-created legacy petty-cash claims."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
VIEWS_PATH = ROOT / "app/advance_payment/views.py"
TEMPLATE_PATH = ROOT / "app/templates/advance_payment/petty_cash_claim_history.html"
DETAIL_TEMPLATE_PATH = ROOT / "app/templates/advance_payment/petty_cash_claim_detail.html"


class PettyCashLegacyClaimEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views = VIEWS_PATH.read_text(encoding="utf-8-sig")
        cls.template = TEMPLATE_PATH.read_text(encoding="utf-8-sig")
        cls.detail_template = DETAIL_TEMPLATE_PATH.read_text(encoding="utf-8-sig")

    def test_finance_route_creates_a_direct_transferred_claim(self):
        route_source = self.views[
            self.views.index("def create_legacy_petty_cash_claim():"):
            self.views.index("def _parcel_return_history_fallback")
        ]

        self.assertIn("PettyCashSetting.fiscal_year == current_fiscal_year", route_source)
        self.assertIn("fund_request_id=None", route_source)
        self.assertIn("claim_number=claim_number", route_source)
        self.assertIn("status=CASH_TRANSFER_STATUS", route_source)
        self.assertIn("fiscal_year=setting.fiscal_year", route_source)
        self.assertIn("receipt_date=transferred_at", route_source)

    def test_history_form_only_requests_the_minimum_legacy_fields(self):
        for field_name in (
            "claim_number",
            "petty_cash_setting_id",
            "category_type",
            "amount",
            "transferred_at",
        ):
            self.assertIn(f'name="{field_name}"', self.template)

        self.assertIn("{% for setting in legacy_claim_settings %}", self.template)
        self.assertIn("รายการโอนเงินของรายการค้างจ่ายปีงบ", self.template)

    def test_ledger_uses_entered_claim_number_without_a_fund_request(self):
        self.assertIn(
            'else (claim.claim_number or f"PC-{claim.id}")',
            self.views,
        )
        self.assertIn(
            'description=f"งานคลังคืนเงินสดย่อย ({claim_reference})"',
            self.views,
        )

    def test_detail_uses_claim_number_when_fund_request_is_absent(self):
        self.assertIn(
            "{% if claim_detail.fund_request_id and claim_detail.fund_request",
            self.detail_template,
        )
        self.assertIn("{{ claim_detail.claim_number or '-' }}", self.detail_template)

    def test_staff_summary_excludes_direct_legacy_claims(self):
        helper_source = self.views[
            self.views.index("def _exclude_legacy_fund_request_claims(query):"):
            self.views.index("def _org_account_controller")
        ]

        self.assertIn("DIRECT_LEGACY_CLAIM_NOTE", helper_source)
        self.assertIn("PettyCashClaimDetail.note", helper_source)


if __name__ == "__main__":
    unittest.main()
