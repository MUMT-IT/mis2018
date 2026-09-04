"""Flask blueprint for AdvancePayment features."""
from datetime import date, datetime

from flask import Blueprint


advance_payment = Blueprint(
    "advance_payment",
    __name__,
    url_prefix="/advance_payment",
)


@advance_payment.app_template_filter("thai_date")
def thai_date(value):
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        thai_year = value.year + 543
        return value.strftime(f"%d/%m/{thai_year}")
    return value

# Import routes and models after the blueprint is defined so decorators can
# register against the same blueprint object.
from . import models  # noqa: E402,F401
from . import views  # noqa: E402,F401
