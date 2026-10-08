"""Finance emails trigger only when workflow events enter the pending queue."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FinanceNotificationTriggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views_source = (
            ROOT / "app/advance_payment/views.py"
        ).read_text(encoding="utf-8-sig")
        tree = ast.parse(cls.views_source)
        wanted_nodes = [
            node
            for node in tree.body
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name)
                    and target.id == "FINANCE_PENDING_NOTIFICATION_STATUSES"
                    for target in node.targets
                )
            )
            or (
                isinstance(node, ast.FunctionDef)
                and node.name == "_should_notify_finance_on_status_change"
            )
        ]
        namespace = {}
        exec(
            compile(ast.Module(wanted_nodes, type_ignores=[]), "trigger_helpers", "exec"),
            namespace,
        )
        cls.is_pending = staticmethod(
            namespace["_should_notify_finance_on_status_change"]
        )

    def test_every_dashboard_pending_status_triggers_finance_email(self):
        pending_statuses = {
            "ticket": ("กำลังส่งคำขอ", "รอตรวจสอบ"),
            "return": ("รอตรวจสอบ",),
            "parcel_return": ("กำลังส่งคำขอ", "รอตรวจสอบ"),
            "petty_claim": ("รอตรวจสอบ",),
        }
        for object_type, statuses in pending_statuses.items():
            for status in statuses:
                with self.subTest(object_type=object_type, status=status):
                    self.assertTrue(
                        self.is_pending(SimpleNamespace(status=status), object_type)
                    )

    def test_finance_action_statuses_do_not_trigger_finance_email(self):
        finance_action_statuses = (
            "กำลังดำเนินการ",
            "กำลังตรวจสอบ",
            "พัสดุกำลังดำเนินการ",
            "ผ่านการตรวจสอบ",
            "ได้รับเอกสารแล้ว",
            "ยืนยันการตรวจสอบ",
        )
        for object_type in ("ticket", "return", "parcel_return", "petty_claim"):
            for status in finance_action_statuses:
                with self.subTest(object_type=object_type, status=status):
                    self.assertFalse(
                        self.is_pending(SimpleNamespace(status=status), object_type)
                    )

    def test_ticket_notifications_are_connected_to_finance_trigger(self):
        self.assertIn(
            'if object_type in {"ticket", "return", "petty_claim", "parcel_return"}',
            self.views_source,
        )
        self.assertIn('"document_type": "สัญญาเงินยืม"', self.views_source)


if __name__ == "__main__":
    unittest.main()
