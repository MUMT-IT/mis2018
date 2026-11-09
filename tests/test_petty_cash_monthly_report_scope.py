"""Monthly report summary includes history through the selected month."""

import ast
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


class _ParcelField:
    def in_(self, ids):
        return ids


class _ParcelReturn:
    fund_request_id = _ParcelField()


class _Query:
    def __init__(self, parcels):
        self.parcels = parcels

    def filter(self, *_conditions):
        return self

    def all(self):
        return self.parcels


def _load_summary(parcels):
    source = (ROOT / "app/advance_payment/pdf_utils.py").read_text(encoding="utf-8-sig")
    module = ast.parse(source)
    function = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "summarize_petty_cash_month"
    )
    session = SimpleNamespace(query=lambda _model: _Query(parcels))
    context = {
        "Decimal": Decimal,
        "FUND_REQUEST_FORM_PETTY_CASH": "petty_cash",
        "ParcelReturnDetail": _ParcelReturn,
        "db": SimpleNamespace(session=session),
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), "pdf_utils.py", "exec"), context)
    return context["summarize_petty_cash_month"]


def test_monthly_summary_includes_history_but_excludes_next_month():
    requests = [
        SimpleNamespace(id=1, request_date=date(2026, 10, 1), form_type="petty_cash", amount=100),
        SimpleNamespace(id=2, request_date=date(2026, 10, 31), form_type="petty_cash", amount=100),
        SimpleNamespace(id=3, request_date=date(2026, 9, 30), form_type="petty_cash", amount=100),
        SimpleNamespace(id=4, request_date=date(2026, 11, 1), form_type="petty_cash", amount=100),
        SimpleNamespace(id=5, request_date=date(2026, 8, 1), form_type="petty_cash", amount=100),
    ]

    def claim(request_id, created, amount):
        item = SimpleNamespace(amount=amount, category_type=1, receipt_date=created.date())
        return SimpleNamespace(
            fund_request_id=request_id, created_at=created, status="รอตรวจสอบ", items=[item]
        )

    claims = [
        claim(1, datetime(2026, 10, 1), 40),
        claim(2, datetime(2026, 10, 31), 20),
        claim(3, datetime(2026, 9, 30), 10),
        claim(1, datetime(2026, 11, 1), 10),
        claim(3, datetime(2026, 10, 10), 50),
        claim(5, datetime(2026, 8, 1), 20),
    ]
    parcels = [
        SimpleNamespace(fund_request_id=1, sent_date=date(2026, 10, 31), status="รอตรวจสอบ", amount_spent=30),
        SimpleNamespace(fund_request_id=3, sent_date=date(2026, 10, 10), status="รอตรวจสอบ", amount_spent=15),
        SimpleNamespace(fund_request_id=3, sent_date=date(2026, 9, 30), status="รอตรวจสอบ", amount_spent=10),
        SimpleNamespace(fund_request_id=1, sent_date=date(2026, 11, 1), status="รอตรวจสอบ", amount_spent=10),
        SimpleNamespace(fund_request_id=5, sent_date=date(2026, 8, 1), status="รอตรวจสอบ", amount_spent=10),
    ]

    summary = _load_summary(parcels)(date(2026, 10, 1), requests, claims)

    assert summary == {
        "submitted_count": 9,
        "submitted_amount": Decimal("140.00"),
        "submitted_parcel_amount": Decimal("65.00"),
        "pending_count": 4,
        "pending_amount": Decimal("195.00"),
    }
