"""Regression tests for the petty-cash settings history summary."""

import ast
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def _load_history_budget_helper():
    source = (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
    module = ast.parse(source)
    helper = ast.Module(
        body=[
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_petty_cash_history_budget"
        ],
        type_ignores=[],
    )
    context = {"Decimal": Decimal}
    exec(compile(helper, "views.py", "exec"), context)
    return context["_petty_cash_history_budget"]


def test_history_budget_uses_linked_setting_and_returns_decimal():
    history_budget = _load_history_budget_helper()
    request = SimpleNamespace(
        petty_cash_setting_id=17,
        petty_cash_setting=SimpleNamespace(budget="12345.67"),
    )

    assert history_budget(request) == Decimal("12345.67")


def test_history_budget_is_absent_when_request_has_no_setting():
    history_budget = _load_history_budget_helper()
    request = SimpleNamespace(petty_cash_setting_id=None, petty_cash_setting=None)

    assert history_budget(request) is None


def test_history_query_excludes_legacy_imports():
    source = (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
    history_query = source[
        source.index("    history_requests = ("):
        source.index("    for fund_request in history_requests:")
    ]

    assert "FundRequest.is_legacy_import.is_(False)" in history_query
