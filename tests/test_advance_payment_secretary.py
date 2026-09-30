"""Exercise authorization helpers without importing the application's services."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SecretaryPermissionTests(unittest.TestCase):
    def setUp(self):
        source = ast.parse((ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig"))
        helpers = ast.Module(body=[
            node for node in source.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"_available_module_roles", "_is_current_secretary"}
        ], type_ignores=[])
        self.user = SimpleNamespace(id=7, roles=[SimpleNamespace(role_need="secretary")])
        self.setting = SimpleNamespace(id=1, custodian_id=7, valid=True, fiscal_year=2026)
        self.context = {
            "SECRETARY_ROLE": "secretary", "COORDINATOR_ROLE": "coordinator",
            "FINANCE_SYSTEM": "finance", "PETTY_CASH_SYSTEM": "petty_cash",
            "_selected_system": lambda: "petty_cash",
            "_module_user_from_session": lambda: self.user,
            "_resolve_petty_cash_setting": lambda user: self.setting,
            "_current_petty_cash_fiscal_year": lambda: 2026,
            "session": {"user_role": None},
        }
        exec(compile(helpers, "views.py", "exec"), self.context)
        self.check = self.context["_is_current_secretary"]

    def test_current_role_works_with_missing_or_other_session_role(self):
        for role in (None, "coordinator", "secretary"):
            with self.subTest(role=role):
                self.context["session"]["user_role"] = role
                self.assertTrue(self.check())

    def test_role_alone_does_not_grant_access(self):
        self.setting.custodian_id = 8
        self.assertFalse(self.check())

    def test_custodian_alone_or_stale_session_does_not_grant_access(self):
        self.user.roles = []
        self.context["session"]["user_role"] = "secretary"
        self.assertFalse(self.check())

    def test_direct_role_supported(self):
        self.user.roles = []
        self.user.role = "secretary"
        self.assertTrue(self.check(self.user, self.setting))

    def test_invalid_assignments_denied(self):
        for field, value in (("valid", False), ("fiscal_year", 2025),
                             ("custodian_id", None), ("id", None)):
            with self.subTest(field=field):
                setting = SimpleNamespace(**vars(self.setting))
                setattr(setting, field, value)
                self.assertFalse(self.check(self.user, setting))

    def test_missing_user_or_setting_denied(self):
        self.setting = None
        self.assertFalse(self.check())
        self.user = None
        self.assertFalse(self.check())

    def test_other_system_denied(self):
        self.context["_selected_system"] = lambda: "advance_payment"
        self.assertFalse(self.check())


if __name__ == "__main__":
    unittest.main()
