"""Regression coverage for personal notes on petty-cash fund requests."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FundRequestPersonalNoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = (
            ROOT / "app/templates/advance_payment/staff_fund_request.html"
        ).read_text(encoding="utf-8-sig")
        cls.view_source = (ROOT / "app/advance_payment/views.py").read_text(
            encoding="utf-8-sig"
        )

    def test_personal_note_is_shared_with_borrowing_form(self):
        self.assertEqual(self.template.count('id="personal_note"'), 1)
        self.assertIn('id="personal_note_section"', self.template)
        self.assertIn(
            'personalNoteSection.style.display = isInterestForm ? "none" : "flex";',
            self.template,
        )

    def test_personal_note_is_saved_for_create_and_edit(self):
        assignment = (
            'personal_note=(form.personal_note.data or "").strip() or None'
        )
        self.assertIn(
            'new_request.personal_note = (form.personal_note.data or "").strip() or None',
            self.view_source,
        )
        self.assertIn(assignment, self.view_source)


if __name__ == "__main__":
    unittest.main()
