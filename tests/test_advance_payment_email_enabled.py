"""Email delivery defaults and explicit environment overrides."""

import ast
import os
from pathlib import Path
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def _load_email_enabled_helper():
    source = (ROOT / "app/advance_payment/views.py").read_text(
        encoding="utf-8-sig"
    )
    tree = ast.parse(source)
    helper = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_advance_payment_email_enabled"
    )
    namespace = {"os": os}
    exec(
        compile(ast.Module([helper], type_ignores=[]), "email_enabled_helper", "exec"),
        namespace,
    )
    return namespace["_advance_payment_email_enabled"]


class AdvancePaymentEmailEnabledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.email_enabled = staticmethod(_load_email_enabled_helper())

    def test_email_is_enabled_when_environment_variable_is_missing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(self.email_enabled())

    def test_explicit_false_values_disable_email(self):
        for value in ("false", "0", "no", "off", "unexpected"):
            with self.subTest(value=value), mock.patch.dict(
                os.environ,
                {"ADVANCE_PAYMENT_EMAIL_ENABLED": value},
                clear=True,
            ):
                self.assertFalse(self.email_enabled())

    def test_explicit_true_values_enable_email_case_insensitively(self):
        for value in ("true", "1", "yes", "on", " TRUE "):
            with self.subTest(value=value), mock.patch.dict(
                os.environ,
                {"ADVANCE_PAYMENT_EMAIL_ENABLED": value},
                clear=True,
            ):
                self.assertTrue(self.email_enabled())


if __name__ == "__main__":
    unittest.main()
