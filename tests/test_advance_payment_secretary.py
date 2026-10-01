"""Exercise authorization helpers without importing the application's services."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PettyCashOrganizationScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ast.parse(
            (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
        )
        helpers = ast.Module(
            body=[
                node
                for node in source.body
                if isinstance(node, ast.FunctionDef)
                and node.name in {
                    "_is_petty_cash_custodian",
                    "_can_access_petty_cash_setting",
                    "_can_manage_petty_cash_claim",
                }
            ],
            type_ignores=[],
        )
        cls.context = {
            "_current_petty_cash_fiscal_year": lambda: 2026,
            "_get_staff_org": lambda user: getattr(user, "org", None),
        }
        exec(compile(helpers, "views.py", "exec"), cls.context)
        cls.is_custodian = staticmethod(cls.context["_is_petty_cash_custodian"])
        cls.can_access = staticmethod(cls.context["_can_access_petty_cash_setting"])
        cls.can_manage_claim = staticmethod(cls.context["_can_manage_petty_cash_claim"])

    def setUp(self):
        self.org = SimpleNamespace(id=10)
        self.user = SimpleNamespace(id=7, org=self.org)
        self.setting = SimpleNamespace(
            id=1,
            org_id=10,
            custodian_id=8,
            valid=True,
            fiscal_year=2026,
        )

    def test_staff_can_access_only_their_organization_setting(self):
        self.assertTrue(self.can_access(self.user, self.setting))

        other_setting = SimpleNamespace(**vars(self.setting))
        other_setting.org_id = 11
        self.assertFalse(self.can_access(self.user, other_setting))

        old_setting = SimpleNamespace(**vars(self.setting))
        old_setting.fiscal_year = 2025
        self.assertFalse(self.can_access(self.user, old_setting))

    def test_assigned_custodian_can_access_managed_setting(self):
        self.setting.custodian_id = self.user.id
        self.setting.org_id = 11

        self.assertTrue(self.is_custodian(self.user, self.setting))
        self.assertTrue(self.can_access(self.user, self.setting))

    def test_custodian_status_does_not_depend_on_secretary_role(self):
        self.setting.custodian_id = self.user.id
        self.user.roles = []
        self.assertTrue(self.is_custodian(self.user, self.setting))

        self.setting.custodian_id = 99
        self.user.roles = [SimpleNamespace(role_need="secretary")]
        self.assertFalse(self.is_custodian(self.user, self.setting))

    def test_invalid_custodian_assignments_are_denied(self):
        self.setting.custodian_id = self.user.id
        for field, value in (
            ("valid", False),
            ("fiscal_year", 2025),
            ("custodian_id", None),
            ("id", None),
        ):
            with self.subTest(field=field):
                setting = SimpleNamespace(**vars(self.setting))
                setattr(setting, field, value)
                self.assertFalse(self.is_custodian(self.user, setting))

    def test_claim_management_is_narrower_than_organization_visibility(self):
        unrelated_claim = SimpleNamespace(
            user_id=9,
            fund_request=SimpleNamespace(creator_id=12),
        )
        own_claim = SimpleNamespace(
            user_id=self.user.id,
            fund_request=SimpleNamespace(creator_id=12),
        )
        created_request_claim = SimpleNamespace(
            user_id=9,
            fund_request=SimpleNamespace(creator_id=self.user.id),
        )

        self.assertFalse(self.can_manage_claim(self.user, unrelated_claim, self.setting))
        self.assertTrue(self.can_manage_claim(self.user, own_claim, self.setting))
        self.assertTrue(self.can_manage_claim(self.user, created_request_claim, self.setting))

    def test_custodian_can_manage_claims_for_the_setting(self):
        self.setting.custodian_id = self.user.id
        claim = SimpleNamespace(user_id=9, fund_request=SimpleNamespace(creator_id=12))

        self.assertTrue(self.can_manage_claim(self.user, claim, self.setting))


class AdvancePaymentCoordinatorAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ast.parse(
            (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
        )
        helpers = ast.Module(
            body=[
                node
                for node in source.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "_can_use_coordinator_dashboard"
            ],
            type_ignores=[],
        )
        cls.state = {
            "system": "advance_payment",
            "is_coordinator": False,
            "settings": [],
        }
        cls.user = SimpleNamespace(id=7, is_authenticated=True, roles=[])
        cls.context = {
            "ADVANCE_PAYMENT_SYSTEM": "advance_payment",
            "current_user": cls.user,
            "_selected_system": lambda: cls.state["system"],
            "_is_current_coordinator": lambda: cls.state["is_coordinator"],
            "_petty_cash_settings_for_custodian": lambda user: cls.state["settings"],
        }
        exec(compile(helpers, "views.py", "exec"), cls.context)
        cls.can_use_dashboard = staticmethod(
            cls.context["_can_use_coordinator_dashboard"]
        )

    def setUp(self):
        self.state.update(
            system="advance_payment",
            is_coordinator=False,
            settings=[],
        )
        self.user.is_authenticated = True
        self.user.roles = []

    def test_assigned_custodian_can_use_coordinator_dashboard(self):
        self.state["settings"] = [SimpleNamespace(id=1, org_id=10)]

        self.assertTrue(self.can_use_dashboard())

    def test_secretary_role_without_custodian_assignment_is_denied(self):
        self.user.roles = [SimpleNamespace(role_need="secretary")]

        self.assertFalse(self.can_use_dashboard())

    def test_coordinator_role_keeps_dashboard_access(self):
        self.state["is_coordinator"] = True

        self.assertTrue(self.can_use_dashboard())

    def test_custodian_access_only_applies_in_advance_payment_system(self):
        self.state["settings"] = [SimpleNamespace(id=1, org_id=10)]
        self.state["system"] = "petty_cash"

        self.assertFalse(self.can_use_dashboard())


class CoordinatorDashboardOrganizationScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ast.parse(
            (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
        )
        helper = next(
            node
            for node in source.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_get_coordinator_dashboard_users"
        )
        cls.state = {
            "is_coordinator": False,
            "users": [],
            "settings": [],
        }
        cls.context = {
            "COORDINATOR_ROLE": "cash_management_coordinator",
            "_current_module_role": lambda: (
                "cash_management_coordinator"
                if cls.state["is_coordinator"]
                else None
            ),
            "_get_staff_accounts_from_directory": lambda: cls.state["users"],
            "_petty_cash_settings_for_custodian": lambda staff: cls.state["settings"],
        }
        exec(
            compile(ast.Module(body=[helper], type_ignores=[]), "views.py", "exec"),
            cls.context,
        )
        cls.get_dashboard_users = staticmethod(
            cls.context["_get_coordinator_dashboard_users"]
        )

    def setUp(self):
        self.staff = SimpleNamespace(id=99)
        self.state["is_coordinator"] = False
        self.state["users"] = [
            SimpleNamespace(id=1, personal_info=SimpleNamespace(org_id=10)),
            SimpleNamespace(id=2, personal_info=SimpleNamespace(org_id=20)),
            SimpleNamespace(id=3, personal_info=SimpleNamespace(org_id=30)),
            SimpleNamespace(id=4, personal_info=SimpleNamespace(org_id=40)),
        ]
        self.state["settings"] = [
            SimpleNamespace(org_id=10),
            SimpleNamespace(org_id=20),
            SimpleNamespace(org_id=30),
        ]

    def test_custodian_can_choose_staff_from_every_managed_org(self):
        users = self.get_dashboard_users(self.staff)

        self.assertEqual([user.id for user in users], [1, 2, 3])

    def test_coordinator_still_sees_all_directory_users(self):
        self.state["is_coordinator"] = True

        users = self.get_dashboard_users(self.staff)

        self.assertEqual([user.id for user in users], [1, 2, 3, 4])

    def test_non_custodian_cannot_receive_all_directory_users(self):
        self.state["settings"] = []

        users = self.get_dashboard_users(self.staff)

        self.assertEqual([user.id for user in users], [self.staff.id])


if __name__ == "__main__":
    unittest.main()
