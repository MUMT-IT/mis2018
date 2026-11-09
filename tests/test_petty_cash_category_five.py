"""Regression coverage for the shared petty-cash category 5 option."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PettyCashCategoryFiveTests(unittest.TestCase):
    def test_fund_request_exposes_category_five_without_borrowing_gate(self):
        template = (
            ROOT / "app/templates/advance_payment/staff_fund_request.html"
        ).read_text(encoding="utf-8-sig")

        self.assertGreaterEqual(template.count('<option value="5">'), 2)
        self.assertNotIn("updateBorrowingCategoryOptions", template)
        self.assertNotIn("selected_form_type != 'borrowing' %} hidden disabled", template)

    def test_claim_exposes_category_five_for_existing_new_and_added_rows(self):
        template = (
            ROOT / "app/templates/advance_payment/submit_petty_cash_claim.html"
        ).read_text(encoding="utf-8-sig")

        self.assertEqual(template.count('<option value="5"'), 3)
        self.assertIn("item.category_type|string == '5'", template)

    def test_ledger_maps_category_five_amount_and_description(self):
        source = (ROOT / "app/advance_payment/views.py").read_text(
            encoding="utf-8-sig"
        )

        self.assertGreaterEqual(
            source.count('str(item.category_type) == "5"'),
            2,
        )
        self.assertIn("cat_11=cat_11", source)
        self.assertIn("custom_category=custom_category", source)


if __name__ == "__main__":
    unittest.main()
