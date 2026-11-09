"""Regression coverage for advance-payment deletion boundaries."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdvancePaymentCascadeConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = (ROOT / "app/advance_payment/models.py").read_text(
            encoding="utf-8-sig"
        )
        cls.migration = (
            ROOT
            / "migrations/versions/q0d1e2f3a4b5_cascade_advance_payment_children.py"
        ).read_text(encoding="utf-8-sig")

    def test_aggregate_children_use_database_cascade(self):
        expected_targets = (
            "cash_advance_return_details.id",
            "cash_advance_return_receipt_items.id",
            "petty_cash_fund_requests.id",
            "petty_cash_claim_details.id",
            "petty_cash_claim_items.id",
            "cash_mng_parcel_return_details.id",
            "cash_mng_closing_documents.id",
            "docs_query_documents.id",
        )

        for target in expected_targets:
            self.assertIn(
                f'ForeignKey("{target}", ondelete="CASCADE")',
                self.models,
            )

    def test_borrowing_ticket_transaction_foreign_keys_remain_restrictive(self):
        for field in ("ticket_id", "borrowing_ticket_id"):
            self.assertNotIn(
                f'{field} = Column(Integer, ForeignKey('
                '"cash_advance_borrowing_tickets.id", ondelete="CASCADE")',
                self.models,
            )

        self.assertNotIn(
            "cash_advance_return_details_ticket_id_fkey",
            self.migration,
        )
        self.assertNotIn(
            "petty_cash_fund_requests_borrowing_ticket_id_fkey",
            self.migration,
        )

    def test_migration_is_reversible(self):
        self.assertIn('down_revision = "p9c8t7u6v5w4"', self.migration)
        self.assertIn('def upgrade():', self.migration)
        self.assertIn('_replace_foreign_keys(ondelete="CASCADE")', self.migration)
        self.assertIn('def downgrade():', self.migration)
        self.assertIn('_replace_foreign_keys()', self.migration)


if __name__ == "__main__":
    unittest.main()
