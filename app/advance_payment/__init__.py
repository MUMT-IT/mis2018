"""Flask blueprint for AdvancePayment features."""

from flask import Blueprint


advance_payment = Blueprint(
    "advance_payment",
    __name__,
    url_prefix="/advance_payment",
)

# Import routes and models after the blueprint is defined so decorators can
# register against the same blueprint object.
from . import models  # noqa: E402,F401
from . import views  # noqa: E402,F401
