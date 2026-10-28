"""Regression tests for annual petty-cash top-up transfer records."""

import ast
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _load_helpers():
    source = (ROOT / "app/advance_payment/views.py").read_text(encoding="utf-8-sig")
    module = ast.parse(source)
    helper_names = {
        "_petty_cash_top_up_difference",
        "_petty_cash_top_up_amount",
        "_partition_petty_cash_transfer_rows",
        "_apply_petty_cash_transfer_direction",
    }
    helper_module = ast.Module(
        body=[
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ],
        type_ignores=[],
    )
    context = {"Decimal": Decimal}
    exec(compile(helper_module, "views.py", "exec"), context)
    return context


class PettyCashFiscalYearTopUpTransferTests(unittest.TestCase):
    def test_default_transfer_amount_is_current_budget_minus_previous_budget(self):
        difference = _load_helpers()["_petty_cash_top_up_difference"]

        self.assertEqual(
            difference("150000.00", "125000.00"), Decimal("25000.00")
        )
        self.assertEqual(
            difference("100000.00", "125000.00"), Decimal("-25000.00")
        )

    def test_missing_previous_budget_is_treated_as_zero(self):
        difference = _load_helpers()["_petty_cash_top_up_difference"]

        self.assertEqual(
            difference(Decimal("80000.00"), None), Decimal("80000.00")
        )

    def test_finance_can_save_an_edited_signed_transfer_amount(self):
        parse_amount = _load_helpers()["_petty_cash_top_up_amount"]

        self.assertEqual(parse_amount("24,500.75"), Decimal("24500.75"))
        self.assertEqual(parse_amount("-500.00"), Decimal("-500.00"))
        with self.assertRaisesRegex(ValueError, "กรุณาระบุส่วนต่าง"):
            parse_amount("")

    def test_rows_are_partitioned_by_effective_transfer_amount(self):
        partition_rows = _load_helpers()["_partition_petty_cash_transfer_rows"]
        rows = [
            SimpleNamespace(name="increase", transfer_amount=Decimal("500.00")),
            SimpleNamespace(name="unchanged", transfer_amount=Decimal("0.00")),
            SimpleNamespace(name="reduction", transfer_amount=Decimal("-250.00")),
        ]

        top_up_rows, reduction_rows = partition_rows(rows)

        self.assertEqual([row.name for row in top_up_rows], ["increase", "unchanged"])
        self.assertEqual([row.name for row in reduction_rows], ["reduction"])

    def test_displayed_absolute_amount_keeps_persisted_direction(self):
        apply_direction = _load_helpers()["_apply_petty_cash_transfer_direction"]

        self.assertEqual(
            apply_direction(Decimal("250.00"), "reduction"),
            Decimal("-250.00"),
        )
        self.assertEqual(
            apply_direction(Decimal("250.00"), "top_up"),
            Decimal("250.00"),
        )
        with self.assertRaisesRegex(ValueError, "ประเภทการปรับวงเงินไม่ถูกต้อง"):
            apply_direction(Decimal("250.00"), "unknown")

    def test_transfer_page_has_required_columns_edit_action_and_last_edit(self):
        template = (
            ROOT
            / "app/templates/advance_payment/petty_cash_fiscal_year_top_up_transfers.html"
        ).read_text(encoding="utf-8-sig")

        for heading in (
            "หน่วยงานเงินสดย่อย",
            "งบประมาณปีการศึกษา",
            "ส่วนต่าง (บาท)",
            "วันที่โอนเงินสำเร็จ",
        ):
            self.assertIn(heading, template)
        self.assertIn("แก้ไขข้อมูล", template)
        self.assertIn("last_edit(transfer_records)", template)
        self.assertIn("รายการลดวงเงิน", template)
        self.assertIn("transfer_rows(top_up_rows", template)
        self.assertIn("transfer_rows(reduction_rows", template)
        self.assertIn('class="transfer-read-only', template)
        self.assertIn("transfer-edit-control d-none", template)
        self.assertIn("readOnlyValues.forEach", template)
        self.assertIn('name="transfer_direction[]"', template)
        self.assertIn("row.display_transfer_amount", template)

    def test_transfer_model_uses_finance_edit_mixin(self):
        models_source = (ROOT / "app/advance_payment/models.py").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "class PettyCashFiscalYearTopUpTransfer(FinanceEditMixin, db.Model):",
            models_source,
        )

    def test_previous_budget_comes_from_matching_carryover(self):
        views_source = (ROOT / "app/advance_payment/views.py").read_text(
            encoding="utf-8-sig"
        )
        route_source = views_source[
            views_source.index("def petty_cash_fiscal_year_top_up_transfers():"):
            views_source.index('@bp.route("/petty-cash/fiscal-year-carryover"')
        ]

        self.assertIn("db.session.query(PettyCashFiscalYearCarryover)", route_source)
        self.assertIn(
            "PettyCashFiscalYearCarryover.source_fiscal_year == previous_fiscal_year",
            route_source,
        )
        self.assertIn(
            "PettyCashFiscalYearCarryover.target_fiscal_year == current_fiscal_year",
            route_source,
        )
        self.assertIn("previous_carryover.finance_budget", route_source)

    def test_reduction_fund_requests_are_loaded_for_current_settings(self):
        views_source = (ROOT / "app/advance_payment/views.py").read_text(
            encoding="utf-8-sig"
        )
        route_source = views_source[
            views_source.index("def petty_cash_fiscal_year_top_up_transfers():"):
            views_source.index('@bp.route("/petty-cash/fiscal-year-carryover"')
        ]
        template = (
            ROOT
            / "app/templates/advance_payment/petty_cash_fiscal_year_top_up_transfers.html"
        ).read_text(encoding="utf-8-sig")

        self.assertIn(
            'FUND_REQUEST_FORM_REDUCTION = "reduction"',
            views_source,
        )
        self.assertIn(
            "FundRequest.form_type == FUND_REQUEST_FORM_REDUCTION",
            route_source,
        )
        self.assertIn(
            "FundRequest.petty_cash_setting_id.in_(list(settings_by_id))",
            route_source,
        )
        self.assertIn("reduction_requests=reduction_requests", route_source)
        self.assertIn('id="reduction-fund-requests"', template)
        self.assertIn("ข้อมูลการเบิกลดวงเงิน", template)

    def test_fund_request_form_type_supports_reduction_value(self):
        models_source = (ROOT / "app/advance_payment/models.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("form_type = Column(String(10), nullable=False)", models_source)

    def test_reduction_form_forces_other_category_type(self):
        views_source = (ROOT / "app/advance_payment/views.py").read_text(
            encoding="utf-8-sig"
        )
        form_template = (
            ROOT / "app/templates/advance_payment/staff_fund_request.html"
        ).read_text(encoding="utf-8-sig")

        self.assertIn('value="reduction"', form_template)
        self.assertIn("เบิกลดวงเงิน", form_template)
        self.assertIn('if (isActive) select.value = "5";', form_template)
        self.assertIn(
            "if form_type == FUND_REQUEST_FORM_REDUCTION",
            views_source,
        )
        self.assertIn("category_type=(", views_source)


if __name__ == "__main__":
    unittest.main()
