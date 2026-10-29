"""Advance-payment status codes and application-level defaults.

Change ``DEFAULT_STATUS_CODES`` when a workflow's initial status changes. Codes
are uppercase identifiers stored in the status catalog.
The values are catalog ``code`` values, not ``advance_payment_statuses.id``.
"""

from sqlalchemy import text


DEFAULT_STATUS_CODES = {
    "borrowing_ticket": "PENDING",
    "return_detail": "PENDING",
    "parcel_return": "PENDING",
    "fund_request": "PENDING",
    "petty_cash_claim": "DRAFT",
}


def resolve_status_id_for_connection(connection, status_group, code=None):
    """Resolve a catalog code to its primary key on the current connection."""
    code = code if code is not None else DEFAULT_STATUS_CODES[status_group]
    result = connection.execute(
        text(
            "SELECT id FROM advance_payment_statuses "
            "WHERE status_group = :status_group AND code = :code"
        ),
        {"status_group": status_group, "code": code},
    ).scalar_one_or_none()
    if result is None:
        raise LookupError(
            f"Status code {code} is missing for status_group {status_group}"
        )
    return result
