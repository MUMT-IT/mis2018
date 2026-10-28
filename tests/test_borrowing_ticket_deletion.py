"""Regression coverage for deleting pending borrowing tickets."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BorrowingTicketDeletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views = (ROOT / "app/advance_payment/views.py").read_text(
            encoding="utf-8-sig"
        )
        cls.verification = (
            ROOT / "app/templates/advance_payment/verification.html"
        ).read_text(encoding="utf-8-sig")

    def test_delete_permission_requires_creator_and_pending_status(self):
        helper_start = self.views.index("def _can_delete_borrowing_ticket")
        helper_end = self.views.index("def _can_edit_parcel_return", helper_start)
        helper_source = self.views[helper_start:helper_end]

        self.assertIn("user_id == borrowing_ticket.creator_id", helper_source)
        self.assertIn('== "กำลังส่งคำขอ"', helper_source)

    def test_delete_route_is_post_only_and_rechecks_permission(self):
        route_start = self.views.index(
            '@bp.route("/tickets/<int:ticket_id>/delete", methods=["POST"])'
        )
        route_end = self.views.index('@bp.route("/api/login"', route_start)
        route_source = self.views[route_start:route_end]

        self.assertIn("def delete_borrowing_ticket(ticket_id):", route_source)
        self.assertIn("_can_delete_borrowing_ticket(", route_source)
        self.assertIn("db.session.delete(borrowing_ticket)", route_source)

    def test_verification_uses_confirmation_popup_for_delete(self):
        self.assertIn("{% if can_delete_borrowing_ticket %}", self.verification)
        self.assertIn(
            "/advance_payment/tickets/{{ borrowing_ticket.id }}/delete",
            self.verification,
        )
        self.assertIn('data-popup-confirm-class="btn-danger"', self.verification)


if __name__ == "__main__":
    unittest.main()
