"""International Relations participant and administration module."""

from flask import Blueprint


bp = Blueprint(
    'international_relations',
    __name__,
    url_prefix='/international-relations',
)


from . import views  # noqa: E402,F401

