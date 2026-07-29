from flask import Blueprint

docs_query = Blueprint('docs_query', __name__, url_prefix='/docs-query')

from .models import DocsQueryDocument
from . import views
