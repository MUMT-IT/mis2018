"""Regression coverage for deleting pending borrowing tickets."""
import ast
from pathlib import Path
from types import SimpleNamespace
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
        self.assertIn('_status_id_for_record(borrowing_ticket, "PENDING")', helper_source)

    def test_edit_and_delete_permissions_follow_selected_system(self):
        source = ast.parse(self.views)
        helpers = [
            node for node in source.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"_can_edit_borrowing_ticket", "_can_delete_borrowing_ticket"}
        ]
        selected = {"system": "finance"}
        namespace = {
            "ADVANCE_PAYMENT_SYSTEM": "advance_payment",
            "_selected_system": lambda: selected["system"],
            "_status_id_for_record": lambda ticket, code: code,
        }
        exec(compile(ast.Module(body=helpers, type_ignores=[]), "views.py", "exec"), namespace)
        ticket = SimpleNamespace(
            creator_id=1, borrower_id=2, status_id="PENDING",
            approved_at=None, rejection_comment=None,
        )

        self.assertFalse(namespace["_can_edit_borrowing_ticket"](1, ticket))
        self.assertFalse(namespace["_can_delete_borrowing_ticket"](1, ticket))
        selected["system"] = "advance_payment"
        self.assertTrue(namespace["_can_edit_borrowing_ticket"](1, ticket))
        self.assertTrue(namespace["_can_delete_borrowing_ticket"](1, ticket))
        self.assertFalse(namespace["_can_delete_borrowing_ticket"](2, ticket))

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
