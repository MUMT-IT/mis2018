"""Exercise the legacy cancellation mapping against a real SQL database."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa


def test_legacy_cancellation_maps_only_to_fund_request_catalog_status():
    path = Path(__file__).resolve().parents[1] / "migrations/versions/d72d68d9af22_consolidate_advance_payment_statuses.py"
    spec = importlib.util.spec_from_file_location("status_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "CREATE TABLE advance_payment_statuses "
            "(id INTEGER PRIMARY KEY, status_group TEXT, code TEXT)"
        ))
        connection.execute(sa.text(
            "CREATE TABLE petty_cash_fund_requests "
            "(id INTEGER PRIMARY KEY, status TEXT, status_id INTEGER)"
        ))
        connection.execute(sa.text(
            "INSERT INTO advance_payment_statuses VALUES "
            "(1, 'other_group', 'CLAIM_CANCELLED'), "
            "(2, 'fund_request', 'CLAIM_CANCELLED'), "
            "(3, 'fund_request', 'APPROVED')"
        ))
        connection.execute(sa.text(
            "INSERT INTO petty_cash_fund_requests VALUES "
            "(1, 'ยกเลิก', NULL), (2, 'อนุมัติแล้ว', 3), "
            "(3, 'unknown', NULL), (4, NULL, NULL), (5, 'ยกเลิก', 3)"
        ))

        migration._map_legacy_fund_request_cancellations(connection)
        # Repeating the mapping must preserve existing status assignments.
        migration._map_legacy_fund_request_cancellations(connection)

        rows = connection.execute(sa.text(
            "SELECT id, status, status_id FROM petty_cash_fund_requests ORDER BY id"
        )).fetchall()
        assert [tuple(row) for row in rows] == [
            (1, "ยกเลิก", 2), (2, "อนุมัติแล้ว", 3),
            (3, "unknown", None), (4, None, None), (5, "ยกเลิก", 3),
        ]
