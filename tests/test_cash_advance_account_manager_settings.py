import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CashAdvanceAccountManagerSettingsTests(unittest.TestCase):
    def test_finance_route_validates_org_account_and_staff(self):
        source = (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")

        self.assertIn(
            '@bp.route("/finance/cash-advance-account-managers", methods=["GET", "POST"])',
            source,
        )
        self.assertIn('.filter_by(record_type="cash_advance")', source)
        self.assertIn("account.org_id != org_id", source)
        self.assertIn("manager_org_id != org_id", source)
        self.assertIn("CashAdvanceAccountManager(", source)
        self.assertIn(
            "return cash_advance_account_manager_settings(_render_after_post=True)",
            source,
        )
        self.assertNotIn(
            'return redirect(url_for("advance_payment.cash_advance_account_manager_settings"))',
            source,
        )

    def test_staff_picker_and_navigation_are_available(self):
        template = (
            ROOT
            / "app/templates/advance_payment/cash_advance_account_manager_settings.html"
        ).read_text(encoding="utf-8-sig")
        navigation = (ROOT / "app/templates/advance_payment/base.html").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn('id="staffPickerModal"', template)
        self.assertIn('name="manager_ids[]"', template)
        self.assertIn("เลือกทั้งหมดจากผลการค้นหา", template)
        self.assertIn("cash_advance_account_manager_settings", navigation)
        self.assertIn("เพิ่มข้อมูลบัญชีธนาคาร", navigation)

    def test_manager_model_enforces_unique_account_staff_pair(self):
        source = (ROOT / "app/advance_payment/models.py").read_text(encoding="utf-8-sig")

        self.assertIn("class CashAdvanceAccountManager", source)
        self.assertIn('name="uq_cash_advance_account_manager"', source)
        self.assertIn('ForeignKey("cash_mng_bank_account_infos.id"', source)
        self.assertIn('ForeignKey("staff_account.id"', source)


if __name__ == "__main__":
    unittest.main()
