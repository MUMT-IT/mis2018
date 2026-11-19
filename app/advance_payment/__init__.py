"""Flask blueprint for AdvancePayment features."""
from flask import Blueprint
from .categories import PETTY_CASH_EXPENSE_CHOICES, RETURN_EXPENSE_CHOICES, CATEGORY_LABELS
from .date_utils import reference_date_form, reference_date_short, thai_date


advance_payment = Blueprint(
    "advance_payment",
    __name__,
    url_prefix="/advance_payment",
)


advance_payment.add_app_template_filter(thai_date, "thai_date")
advance_payment.add_app_template_filter(reference_date_short, "claim_reference_date")
advance_payment.add_app_template_filter(reference_date_form, "claim_reference_date_form")


@advance_payment.app_context_processor
def finance_category_choices():
    return {
        "petty_cash_expense_choices": PETTY_CASH_EXPENSE_CHOICES,
        "return_expense_choices": RETURN_EXPENSE_CHOICES,
        "finance_category_labels": CATEGORY_LABELS,
    }

# Import routes and models after the blueprint is defined so decorators can
# register against the same blueprint object.
from . import models  # noqa: E402,F401
from . import views  # noqa: E402,F401
