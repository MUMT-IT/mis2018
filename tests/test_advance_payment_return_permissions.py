"""Regression tests for cash-advance return ownership checks."""
import ast
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


if __name__ == "__main__":
    unittest.main()
