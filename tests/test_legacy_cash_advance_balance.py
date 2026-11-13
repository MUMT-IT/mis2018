"""Opening-balance regression checks without importing the Flask app."""

import ast
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _load_helpers():
    source = ast.parse((ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig"))
    names = {
        "_money_decimal", "_ticket_opening_budget", "_ticket_accounting_opening_balance",
        "_legacy_verification_display_summary", "_allocate_settled_records_to_tickets",
        "_ticket_has_imported_reduction", "_recalculate_borrowing_ticket_status",
    }
    module = ast.Module(
        body=[node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names],
        type_ignores=[],
    )
    context = {"Decimal": Decimal}
    exec(compile(module, "views.py", "exec"), context)
    return context


class LegacyOpeningBalanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = _load_helpers()

    def test_normal_ticket_uses_original_amount(self):
        ticket = SimpleNamespace(required_budget=Decimal("100.00"), opening_balance_amount=None)
        self.assertEqual(self.helpers["_ticket_opening_budget"](ticket), Decimal("100.00"))

    def test_imported_ticket_uses_j_even_when_zero(self):
        ticket = SimpleNamespace(required_budget=Decimal("100.00"), opening_balance_amount=Decimal("0.00"))
        self.assertEqual(self.helpers["_ticket_opening_budget"](ticket), Decimal("0.00"))

    def test_accounting_balance_keeps_pending_requisition_as_debt(self):
        ticket = SimpleNamespace(required_budget=Decimal("100.00"))
        source = SimpleNamespace(repaid_amount=Decimal("70.00"))
        self.assertEqual(
            self.helpers["_ticket_accounting_opening_balance"](ticket, source),
            Decimal("30.00"),
        )

    def test_reduced_imported_balance_marks_partial_return(self):
        reduced = SimpleNamespace(
            required_budget=Decimal("100.00"), opening_balance_amount=Decimal("50.00")
        )
        untouched = SimpleNamespace(
            required_budget=Decimal("100.00"), opening_balance_amount=Decimal("100.00")
        )
        normal = SimpleNamespace(
            required_budget=Decimal("100.00"), opening_balance_amount=None
        )
        self.assertTrue(self.helpers["_ticket_has_imported_reduction"](reduced))
        self.assertFalse(self.helpers["_ticket_has_imported_reduction"](untouched))
        self.assertFalse(self.helpers["_ticket_has_imported_reduction"](normal))

    def test_recalculation_keeps_imported_partial_status_without_new_returns(self):
        ticket = SimpleNamespace(
            status_id=1, import_batch_id=10, required_budget=Decimal("100.00"),
            opening_balance_amount=Decimal("50.00"), closed_date=None,
        )
        context = self.helpers
        context["db"] = SimpleNamespace(session=SimpleNamespace(
            query=lambda model: SimpleNamespace(filter_by=lambda **kwargs: SimpleNamespace(
                first=lambda: ticket
            ))
        ))
        context["BorrowingTicket"] = object()
        context["_ticket_has_bounced_return"] = lambda ticket_id: False
        context["_calculate_ticket_return_totals"] = lambda ticket_id: {
            "cumulative_total": Decimal("0.00"), "budget": Decimal("50.00"),
        }
        context["_status_id"] = lambda group, code: {
            "APPROVED": 1, "PARTIAL_RETURN": 2, "CLOSED": 3,
        }[code]
        context["_status_ids"] = lambda group, codes: {
            {"APPROVED": 1, "PARTIAL_RETURN": 2, "CLOSED": 3}.get(code)
            for code in codes
        }
        result = context["_recalculate_borrowing_ticket_status"](
            9, commit=False, notify=False, recalculate_settlement=False
        )
        self.assertEqual(result, 2)
        self.assertEqual(ticket.status_id, 2)

    def test_settlement_closes_at_imported_opening_balance(self):
        result = self.helpers["_allocate_settled_records_to_tickets"](
            {5: Decimal("60.00")},
            [{"record_key": ("return", 7), "amount": Decimal("60.00"),
              "ticket_ids": {5}, "settled_at": "settled"}],
        )
        self.assertEqual(result["remaining_by_ticket"][5], Decimal("0.00"))
        self.assertEqual(result["allocated_by_ticket"][5], Decimal("60.00"))
        self.assertEqual(result["anomalies"], [])

    def test_zero_imported_balance_stays_closed_after_recalculation(self):
        ticket = SimpleNamespace(
            status_id=2, import_batch_id=10, required_budget=Decimal("100.00"),
            opening_balance_amount=Decimal("0.00"), closed_date=None,
        )
        context = self.helpers
        context["db"] = SimpleNamespace(session=SimpleNamespace(
            query=lambda model: SimpleNamespace(filter_by=lambda **kwargs: SimpleNamespace(
                first=lambda: ticket
            ))
        ))
        context["BorrowingTicket"] = object()
        context["_ticket_has_bounced_return"] = lambda ticket_id: False
        context["_calculate_ticket_return_totals"] = lambda ticket_id: {
            "cumulative_total": Decimal("0.00"), "budget": Decimal("0.00"),
        }
        context["_status_id"] = lambda group, code: {
            "APPROVED": 1, "PARTIAL_RETURN": 2, "CLOSED": 3,
        }[code]
        result = context["_recalculate_borrowing_ticket_status"](
            9, commit=False, notify=False, recalculate_settlement=False
        )
        self.assertEqual(result, 3)
        self.assertIsNone(ticket.closed_date)

    def test_verification_cards_show_historical_and_current_amounts(self):
        summary = {
            "budget": Decimal("100.00"),
            "cumulative_total": Decimal("0.00"),
            "pending_amount": Decimal("0.00"),
            "unsubmitted_amount": Decimal("100.00"),
        }
        ticket = SimpleNamespace(required_budget=Decimal("65000.00"))
        source = SimpleNamespace(
            repaid_amount=Decimal("64900.00"),
            pending_documents_amount=Decimal("0.00"),
        )
        display = self.helpers["_legacy_verification_display_summary"](
            summary, ticket, source,
            settled_amount=Decimal("0.00"), documented_amount=Decimal("0.00"),
        )
        self.assertEqual(
            (display["budget"], display["cumulative_total"],
             display["pending_amount"], display["unsubmitted_amount"]),
            (Decimal("65000.00"), Decimal("64900.00"),
             Decimal("0.00"), Decimal("100.00")),
        )
        self.assertEqual(summary["budget"], Decimal("100.00"))

    def test_verification_cards_include_pending_document_amount(self):
        summary = {
            "budget": Decimal("100.00"),
            "cumulative_total": Decimal("20.00"),
            "pending_amount": Decimal("10.00"),
            "unsubmitted_amount": Decimal("70.00"),
        }
        ticket = SimpleNamespace(required_budget=Decimal("1000.00"))
        source = SimpleNamespace(
            repaid_amount=Decimal("800.00"),
            pending_documents_amount=Decimal("100.00"),
        )
        display = self.helpers["_legacy_verification_display_summary"](
            summary, ticket, source,
            settled_amount=Decimal("10.00"), documented_amount=Decimal("30.00"),
        )
        self.assertEqual(display["cumulative_total"], Decimal("810.00"))
        self.assertEqual(display["pending_amount"], Decimal("120.00"))
        self.assertEqual(
            display["cumulative_total"] + display["pending_amount"]
            + display["unsubmitted_amount"],
            display["budget"],
        )


if __name__ == "__main__":
    unittest.main()
