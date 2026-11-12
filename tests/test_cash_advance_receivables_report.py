"""Receivables export preserves the report's monetary relationships."""

import ast
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys
import unittest

import xlrd


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "app" / "advance_payment" / "receivables_report.py"
spec = importlib.util.spec_from_file_location("receivables_report_under_test", REPORT_PATH)
report_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = report_module
spec.loader.exec_module(report_module)


class ReceivablesReportTests(unittest.TestCase):
    def test_imported_and_current_amounts_reconcile(self):
        ticket = SimpleNamespace(
            number="77/67", borrower_name="ผู้ยืม ทดสอบ",
            approved_at=datetime(2024, 5, 14), due_date=date(2024, 8, 14),
            borrowing_ticket_purpose="ค่าเดินทาง",
            required_budget=Decimal("100.00"),
        )
        row = report_module.build_receivable_row(
            ticket,
            historical_repaid=Decimal("40.00"),
            historical_pending=Decimal("10.00"),
            approved_amount=Decimal("20.00"),
            pending_amount=Decimal("5.00"),
        )
        self.assertEqual(
            [row[key] for key in report_module.AMOUNT_KEYS],
            [Decimal(value) for value in ("100.00", "60.00", "40.00", "15.00", "25.00")],
        )

    def test_workbook_matches_source_layout_and_totals(self):
        ticket = SimpleNamespace(
            number="77/67", borrower_name="ผู้ยืม ทดสอบ",
            approved_at=datetime(2024, 5, 14), due_date=date(2024, 8, 14),
            borrowing_ticket_purpose="=1+1",
            required_budget=Decimal("100.00"),
        )
        first = report_module.build_receivable_row(
            ticket, historical_repaid=40, historical_pending=10,
            approved_amount=20, pending_amount=5,
        )
        ticket.number = "78/67"
        ticket.required_budget = Decimal("50.00")
        second = report_module.build_receivable_row(
            ticket, approved_amount=0, pending_amount=0,
        )
        data = report_module.generate_receivables_xls(
            [first, second], report_date=date(2026, 11, 12)
        )
        sheet = xlrd.open_workbook(file_contents=data).sheet_by_index(0)
        self.assertEqual(sheet.name, "พย.69")
        self.assertEqual(sheet.cell_value(0, 0), "รายงานลูกหนี้เงินยืม")
        self.assertEqual(sheet.cell_value(2, 0), "วันที่ยืม")
        self.assertEqual(sheet.cell_value(2, 2), "ชื่อผู้ยืม")
        self.assertEqual(sheet.cell_value(3, 1), "คืนเงินยืม")
        self.assertEqual(sheet.cell_value(3, 8), "รอเบิก")
        self.assertEqual(sheet.cell_value(4, 0), "พค.14")
        self.assertEqual(sheet.cell_type(4, 1), xlrd.XL_CELL_DATE)
        self.assertEqual(sheet.cell_value(4, 4), "77/67")
        self.assertEqual(sheet.cell_value(4, 9), 25)
        self.assertEqual(sheet.cell_type(4, 10), xlrd.XL_CELL_TEXT)
        self.assertEqual(
            [sheet.cell_value(7, col) for col in range(5, 10)],
            [150, 60, 90, 15, 75],
        )

    def test_41_tickets_keep_sample_subtotal_and_final_row_positions(self):
        ticket = SimpleNamespace(
            number="1/69", borrower_name="นายทดสอบ ตัวอย่าง",
            approved_at=datetime(2025, 10, 1), due_date=date(2025, 12, 1),
            borrowing_ticket_purpose="ทดสอบ", required_budget=Decimal("100.00"),
        )
        rows = [report_module.build_receivable_row(
            ticket, approved_amount=0, pending_amount=0
        ) for _ in range(41)]
        book = xlrd.open_workbook(file_contents=report_module.generate_receivables_xls(
            rows, report_date=date(2025, 10, 31)
        ), formatting_info=True)
        sheet = book.sheet_by_index(0)
        self.assertEqual(sheet.name, "ตค.68")
        self.assertEqual(sheet.cell_value(27, 2), "รวมเงิน")
        self.assertEqual(sheet.cell_value(28, 2), "ยอดยกมา")
        self.assertEqual(sheet.cell_value(49, 2), "รวมเงิน")
        self.assertEqual(sheet.cell_value(49, 5), 4100)
        for row in range(2, 50):
            for col in range(11):
                border = book.xf_list[sheet.cell(row, col).xf_index].border
                expected = (1, 1, 1, 1)
                if col in (1, 8) and row == 2:
                    expected = (1, 1, 1, 0)
                elif col in (1, 8) and row == 3:
                    expected = (1, 1, 0, 1)
                self.assertEqual(
                    (border.left_line_style, border.right_line_style,
                     border.top_line_style, border.bottom_line_style),
                    expected,
                    f"Missing border at row {row + 1}, column {col + 1}",
                )

    def test_report_rows_combine_source_and_current_returns(self):
        source = ast.parse(
            (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
        )
        function = next(
            node for node in source.body
            if isinstance(node, ast.FunctionDef) and node.name == "_receivables_report_rows"
        )
        ticket = SimpleNamespace(
            id=1, number="77/67", borrower_name="ผู้ยืม ทดสอบ",
            approved_at=datetime(2024, 5, 14), due_date=date(2024, 8, 14),
            borrowing_ticket_purpose="ค่าเดินทาง",
            required_budget=Decimal("100.00"),
        )
        context = {
            "Decimal": Decimal,
            "_ticket_group_ids": lambda ticket_id: {ticket_id},
            "_calculate_ticket_group_totals": lambda ids: {
                "allocated_by_ticket": {1: Decimal("20.00")}
            },
            "_calculate_return_form_group_totals": lambda ids: {
                "allocated_by_ticket": {1: Decimal("25.00")}
            },
            "_money_decimal": lambda value: Decimal(str(value or 0)),
            "_legacy_source_row_for_report": lambda ticket, cache: SimpleNamespace(
                repaid_amount=Decimal("40.00"),
                pending_documents_amount=Decimal("10.00"),
                first_name_with_title="ผู้ยืม",
                last_name="ทดสอบ",
                borrow_text="พค.14",
            ),
            "build_receivable_row": report_module.build_receivable_row,
        }
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), "views.py", "exec"),
            context,
        )
        row = context["_receivables_report_rows"]([ticket])[0]
        self.assertEqual(row["repaid"], Decimal("60.00"))
        self.assertEqual(row["pending"], Decimal("15.00"))
        self.assertEqual(row["remaining"], Decimal("25.00"))


if __name__ == "__main__":
    unittest.main()
