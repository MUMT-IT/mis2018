from flask import Blueprint

docs_query = Blueprint('docs_query', __name__, url_prefix='/docs-query')

from .models import DocsQueryChunk, DocsQueryDocument
from . import views
