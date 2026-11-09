"""Flask blueprint for AdvancePayment features."""
from flask import Blueprint
from .date_utils import reference_date_form, reference_date_short, thai_date


advance_payment = Blueprint(
    "advance_payment",
    __name__,
    url_prefix="/advance_payment",
)


advance_payment.add_app_template_filter(thai_date, "thai_date")
advance_payment.add_app_template_filter(reference_date_short, "claim_reference_date")
advance_payment.add_app_template_filter(reference_date_form, "claim_reference_date_form")

# Import routes and models after the blueprint is defined so decorators can
# register against the same blueprint object.
from . import models  # noqa: E402,F401
from . import views  # noqa: E402,F401
