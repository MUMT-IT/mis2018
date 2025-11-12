"""
Continuing Education Admin Blueprint
"""
# Import the blueprint from views.py (defined there to avoid circular import issues)
from app.continuing_edu.admin.views import admin_bp

# Import additional view modules to register their routes
from app.continuing_edu.admin import admin_management_views  # noqa: F401
from app.continuing_edu.admin import staff_role_views  # noqa: F401

__all__ = ['admin_bp']
