"""Selected-system boundaries for Advance Payment write routes."""
import ast
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SystemPermissionTests(unittest.TestCase):
    def setUp(self):
        source = ast.parse(
            (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
        )
        decorators = [
            node for node in source.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"module_system_required", "module_role_required"}
        ]
        self.state = {"system": "finance", "method": "POST"}
        request = SimpleNamespace(method="POST")
        self.request = request
        user = SimpleNamespace(is_authenticated=True)
        self.context = {
            "wraps": wraps,
            "request": request,
            "current_user": user,
            "flask_login_required": lambda view: view,
            "_selected_system": lambda: self.state["system"],
            "_set_selected_system": lambda system: self.state.update(system=system),
            "_can_use_module_system": lambda staff, system: True,
            "_current_module_role": lambda: self.state["system"],
            "_is_cash_mng_finance_open": lambda: True,
            "abort": lambda status: (_ for _ in ()).throw(PermissionError(status)),
            "ADVANCE_PAYMENT_SYSTEM": "advance_payment",
            "PETTY_CASH_SYSTEM": "petty_cash",
            "FINANCE_SYSTEM": "finance",
        }
        exec(compile(ast.Module(body=decorators, type_ignores=[]), "views.py", "exec"), self.context)

    def test_system_route_does_not_switch_on_post(self):
        view = self.context["module_system_required"]("advance_payment")(
            lambda: "written"
        )
        with self.assertRaisesRegex(PermissionError, "403"):
            view()
        self.assertEqual(self.state["system"], "finance")

        self.state["system"] = "advance_payment"
        self.assertEqual(view(), "written")

    def test_system_route_can_select_system_for_get(self):
        self.request.method = "GET"
        view = self.context["module_system_required"]("advance_payment")(
            lambda: "page"
        )
        self.assertEqual(view(), "page")
        self.assertEqual(self.state["system"], "advance_payment")

    def test_role_route_does_not_switch_on_post(self):
        permission = SimpleNamespace(require=lambda: lambda view: view)
        view = self.context["module_role_required"](
            permission, "finance", "finance"
        )(lambda: "written")
        self.state["system"] = "advance_payment"
        with self.assertRaisesRegex(PermissionError, "403"):
            view()
        self.assertEqual(self.state["system"], "advance_payment")

        self.state["system"] = "finance"
        self.assertEqual(view(), "written")


if __name__ == "__main__":
    unittest.main()
