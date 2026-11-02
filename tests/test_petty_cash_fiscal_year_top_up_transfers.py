"""Regression tests for annual petty-cash top-up transfer records."""

import ast
from contextlib import closing
from decimal import Decimal
from pathlib import Path
import sqlite3
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
        "_petty_cash_transfer_type",
        "_single_reduction_request",
    }
    helper_module = ast.Module(
        body=[
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name in helper_names
        ],
        type_ignores=[],
    )
    context = {
        "Decimal": Decimal,
        "PETTY_CASH_TRANSFER_NONE": 0,
        "PETTY_CASH_TRANSFER_TOP_UP": 1,
        "PETTY_CASH_TRANSFER_REDUCTION": 2,
    }
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

    def test_finance_can_save_an_unsigned_transfer_amount(self):
        parse_amount = _load_helpers()["_petty_cash_top_up_amount"]

        self.assertEqual(parse_amount("24,500.75"), Decimal("24500.75"))
        self.assertEqual(parse_amount("0.00"), Decimal("0.00"))
        with self.assertRaisesRegex(ValueError, "ต้องไม่ติดลบ"):
            parse_amount("-500.00")
        with self.assertRaisesRegex(ValueError, "กรุณาระบุส่วนต่าง"):
            parse_amount("")

    def test_rows_are_partitioned_by_transfer_type(self):
        partition_rows = _load_helpers()["_partition_petty_cash_transfer_rows"]
        rows = [
            SimpleNamespace(name="increase", transfer_type=1),
            SimpleNamespace(name="unchanged", transfer_type=0),
            SimpleNamespace(name="reduction", transfer_type=2),
        ]

        top_up_rows, reduction_rows = partition_rows(rows)

        self.assertEqual([row.name for row in top_up_rows], ["increase", "unchanged"])
        self.assertEqual([row.name for row in reduction_rows], ["reduction"])

    def test_type_and_amount_must_agree(self):
        parse_type = _load_helpers()["_petty_cash_transfer_type"]

        self.assertEqual(parse_type("0", Decimal("0.00")), 0)
        self.assertEqual(parse_type("1", Decimal("250.00")), 1)
        self.assertEqual(parse_type("2", Decimal("250.00")), 2)
        with self.assertRaisesRegex(ValueError, "ไม่สอดคล้องกัน"):
            parse_type("0", Decimal("250.00"))
        with self.assertRaisesRegex(ValueError, "ไม่สอดคล้องกัน"):
            parse_type("2", Decimal("0.00"))
        with self.assertRaisesRegex(ValueError, "ประเภทการปรับวงเงินไม่ถูกต้อง"):
            parse_type("unknown", Decimal("250.00"))

    def test_reduction_request_must_be_unique_for_setting(self):
        select_request = _load_helpers()["_single_reduction_request"]
        fund_request = SimpleNamespace(id=42)

        self.assertIs(select_request({7: [fund_request]}, 7), fund_request)
        with self.assertRaisesRegex(ValueError, "เพียงหนึ่งใบ"):
            select_request({}, 7)
        with self.assertRaisesRegex(ValueError, "เพียงหนึ่งใบ"):
            select_request({7: [fund_request, SimpleNamespace(id=43)]}, 7)

    def test_migration_links_only_unambiguous_reduction_requests(self):
        migration = ast.parse((
            ROOT / "migrations/versions/f4b1d3e9a7c2_link_reduction_transfer_requests.py"
        ).read_text(encoding="utf-8"))
        upgrade = next(
            node for node in migration.body
            if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
        )
        statements = [
            ast.literal_eval(node.value.args[0].args[0])
            for node in upgrade.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "execute"
        ]

        with closing(sqlite3.connect(":memory:")) as connection:
            connection.executescript("""
                CREATE TABLE petty_cash_fund_requests (
                    id INTEGER, petty_cash_setting_id INTEGER,
                    form_type TEXT, is_legacy_import BOOLEAN, request_date TEXT
                );
                CREATE TABLE petty_cash_fiscal_year_top_up_transfers (
                    id INTEGER, petty_cash_setting_id INTEGER,
                    transfer_type INTEGER, fund_request_id INTEGER, transferred_at TEXT
                );
                INSERT INTO petty_cash_fund_requests VALUES
                    (11, 1, 'reduction', 0, '2026-10-10'),
                    (21, 2, 'reduction', 0, '2026-10-11'),
                    (22, 2, 'reduction', 0, '2026-10-12'),
                    (31, 3, 'petty_cash', 0, '2026-10-13');
                INSERT INTO petty_cash_fiscal_year_top_up_transfers VALUES
                    (1, 1, 2, NULL, NULL),
                    (2, 2, 2, NULL, NULL),
                    (3, 3, 2, NULL, NULL);
            """)
            for statement in statements:
                connection.execute(statement)
            rows = connection.execute("""
                SELECT fund_request_id, transferred_at
                FROM petty_cash_fiscal_year_top_up_transfers ORDER BY id
            """).fetchall()

        self.assertEqual(rows, [(11, "2026-10-10"), (None, None), (None, None)])

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
        self.assertIn("แก้ไข", template)
        self.assertIn("last_edit(transfer_records)", template)
        self.assertIn("รายการลดวงเงิน", template)
        self.assertIn("transfer_rows(top_up_rows", template)
        self.assertIn("transfer_rows(reduction_rows", template)
        self.assertNotIn('id="no-transfer-section"', template)
        self.assertIn('class="transfer-read-only', template)
        self.assertIn("transfer-edit-control", template)
        self.assertIn('name="transfer_type"', template)
        self.assertIn('name="setting_id"', template)
        self.assertIn("ยังไม่บันทึก (ค่าแนะนำ)", template)
        self.assertIn("row.display_transferred_at", template)
        self.assertIn("จากใบเบิก", template)

    def test_transfer_model_uses_finance_edit_mixin(self):
        models_source = (ROOT / "app/advance_payment/models.py").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "class PettyCashFiscalYearTopUpTransfer(FinanceEditMixin, db.Model):",
            models_source,
        )
        self.assertIn("transfer_type = Column(Integer, nullable=False)", models_source)
        self.assertIn("fund_request_id = Column(", models_source)

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
        self.assertNotIn("reduction_requests=reduction_requests", route_source)
        self.assertIn("transferred_at = reduction_request.request_date", route_source)
        self.assertIn("transfer.fund_request_id = reduction_request.id", route_source)
        self.assertNotIn('id="reduction-fund-requests"', template)
        self.assertIn("จากใบเบิก", template)

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
