"""Regression coverage for petty-cash claim item prefill and removal."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PettyCashClaimItemPrefillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = (
            ROOT / "app/templates/advance_payment/submit_petty_cash_claim.html"
        ).read_text(encoding="utf-8-sig")
        cls.views = (ROOT / "app/advance_payment/views.py").read_text(
            encoding="utf-8-sig"
        )

    def test_fund_request_items_prefill_only_when_there_is_no_draft(self):
        self.assertIn(
            "claim_detail.items if claim_detail else "
            "(selected_fund_request.items if selected_fund_request else [])",
            self.template,
        )
        self.assertIn("{% for item in claim_form_items %}", self.template)
        self.assertIn("{% elif not claim_detail %}", self.template)

    def test_current_amount_is_rendered_from_the_saved_draft(self):
        self.assertIn(
            "claim_detail.total_amount if claim_detail and "
            "claim_detail.total_amount is not none",
            self.template,
        )
        self.assertIn(
            'id="grandTotalDisplay" value="{{ \'{:,.2f}\'.format('
            "claim_form_amount or 0) }}\"",
            self.template,
        )

    def test_last_claim_row_can_be_removed(self):
        remove_row_source = self.template[
            self.template.index("function removeRow(btn)"):
            self.template.index("function updateIndices()")
        ]

        self.assertIn("btn.closest('tr').remove();", remove_row_source)
        self.assertNotIn("length > 1", remove_row_source)
        self.assertNotIn("ต้องมีรายการอย่างน้อย 1 รายการ", remove_row_source)

    def test_saving_a_draft_renders_the_claim_form_again(self):
        submit_source = self.views[
            self.views.index("def submit_petty_cash_claim"):
        ]
        draft_return = """if is_draft:
            flash("บันทึกฉบับร่างเรียบร้อยแล้ว", "success")
            return submit_petty_cash_claim(
                _render_after_post=True,
                _forced_fund_request_id=fund_request_id,
            )"""

        self.assertIn(draft_return, submit_source)


if __name__ == "__main__":
    unittest.main()
