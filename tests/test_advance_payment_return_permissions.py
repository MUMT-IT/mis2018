"""Regression tests for cash-advance return ownership checks."""
import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReturnDetailPermissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ast.parse(
            (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
        )
        helper = ast.Module(
            body=[
                node
                for node in source.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "_can_access_return_detail"
            ],
            type_ignores=[],
        )
        cls.context = {
            "_get_borrowing_ticket_by_id": lambda ticket_id: SimpleNamespace(id=ticket_id),
            "_can_submit_return_detail": lambda user_id, ticket: (
                user_id == 22 and getattr(ticket, "id", None) == 32
            ),
        }
        exec(compile(helper, "views.py", "exec"), cls.context)
        cls.check = staticmethod(cls.context["_can_access_return_detail"])

    def test_return_creator_can_access_when_not_ticket_owner(self):
        detail = SimpleNamespace(id=23, ticket_id=32, creator_id=689)
        ticket = SimpleNamespace(id=32, creator_id=688, borrower_id=688)

        self.assertTrue(self.check(689, detail, ticket))

    def test_ticket_submitter_can_access_another_users_return(self):
        detail = SimpleNamespace(id=23, ticket_id=32, creator_id=689)
        ticket = SimpleNamespace(id=32)

        self.assertTrue(self.check(22, detail, ticket))

    def test_unrelated_user_is_denied(self):
        detail = SimpleNamespace(id=23, ticket_id=32, creator_id=689)
        ticket = SimpleNamespace(id=32)

        self.assertFalse(self.check(999, detail, ticket))

    def test_missing_user_or_return_is_denied(self):
        detail = SimpleNamespace(id=23, ticket_id=32, creator_id=689)

        self.assertFalse(self.check(None, detail))
        self.assertFalse(self.check(689, None))

    def test_new_return_requires_advance_payment_and_actionable_status(self):
        source = ast.parse(
            (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
        )
        helper = next(
            node for node in source.body
            if isinstance(node, ast.FunctionDef) and node.name == "_can_submit_return"
        )
        selected = {"system": "finance"}
        context = {
            "ADVANCE_PAYMENT_SYSTEM": "advance_payment",
            "_selected_system": lambda: selected["system"],
            "_status_ids_for_record": lambda ticket, codes: set(codes),
            "_can_submit_return_detail": lambda user_id, ticket: user_id == ticket.creator_id,
        }
        exec(compile(ast.Module(body=[helper], type_ignores=[]), "views.py", "exec"), context)
        can_submit = context["_can_submit_return"]
        ticket = SimpleNamespace(creator_id=22, status_id="APPROVED")

        self.assertFalse(can_submit(22, ticket))
        selected["system"] = "advance_payment"
        self.assertTrue(can_submit(22, ticket))
        ticket.status_id = "PARTIAL_RETURN"
        self.assertTrue(can_submit(22, ticket))
        self.assertFalse(can_submit(23, ticket))
        ticket.status_id = "CLOSED"
        self.assertFalse(can_submit(22, ticket))

    def test_verification_button_uses_new_return_permission(self):
        template = (
            ROOT / "app/templates/advance_payment/verification.html"
        ).read_text(encoding="utf-8-sig")
        self.assertIn("{% if can_submit_return %}", template)
        self.assertNotIn(
            'borrowing_ticket.status|lower == "อนุมัติจ่ายเงิน" and advance_payment_role != \'finance\'',
            template,
        )

    def test_pdf_route_requires_approval_even_for_finance(self):
        source = ast.parse(
            (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
        )
        route = next(
            node for node in source.body
            if isinstance(node, ast.FunctionDef) and node.name == "export_ticket_return_pdf"
        )
        route.decorator_list = []
        detail = SimpleNamespace(ticket_id=32, status_id="APPROVED", approved_at=None)
        ticket = SimpleNamespace(id=32)
        context = {
            "db": SimpleNamespace(session=SimpleNamespace(query=lambda model: SimpleNamespace(
                get=lambda record_id: detail if model == "return" else ticket
            ))),
            "ReturnDetail": "return",
            "BorrowingTicket": "ticket",
            "FINANCE_SYSTEM": "finance",
            "ADVANCE_PAYMENT_SYSTEM": "advance_payment",
            "_selected_system": lambda: "finance",
            "_status_id_for_record": lambda record, code: code,
            "abort": lambda status: (_ for _ in ()).throw(PermissionError(status)),
            "request": SimpleNamespace(method="GET"),
            "redirect": lambda url: url,
            "url_for": lambda endpoint, **kwargs: endpoint,
        }
        exec(compile(ast.Module(body=[route], type_ignores=[]), "views.py", "exec"), context)

        with self.assertRaisesRegex(PermissionError, "403"):
            context["export_ticket_return_pdf"](23)

        detail.approved_at = datetime(2026, 10, 30)
        self.assertEqual(
            context["export_ticket_return_pdf"](23),
            "advance_payment.return_proof_detail",
        )


if __name__ == "__main__":
    unittest.main()
