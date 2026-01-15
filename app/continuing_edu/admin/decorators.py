"""
Authorization decorators for continuing education admin area.
Uses Flask-Login from main MIS system and Flask-Principal for role-based permissions.
"""
from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user
from flask_principal import Permission

from app.continuing_edu.models import (
    EventEditor, 
    EventRegistrationReviewer, 
    EventPaymentApprover,
    EventReceiptIssuer,
    EventCertificateManager
)

# Import the continuing_edu permission from the global roles module
try:
    from app.roles import continuing_edu_admin_permission
except ImportError:
    # Fallback if roles not loaded yet
    continuing_edu_admin_permission = Permission()


def admin_required(f):
    """
    Decorator to ensure user has continuing_edu_admin role.
    Uses Flask-Principal permission system from main MIS.
    
    This replaces the old custom admin check with the standard MIS role system.
    Staff must have 'continuing_edu_admin' role in the roles table.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First check if user is authenticated
        if not current_user.is_authenticated:
            flash('กรุณาเข้าสู่ระบบก่อนเข้าใช้งาน', 'warning')
            return redirect(url_for('auth.login', next=url_for('continuing_edu_admin.dashboard')))
        
        # Check if user has continuing_edu_admin role using Flask-Principal
        with continuing_edu_admin_permission.require(http_exception=403):
            return f(*args, **kwargs)
    
    return decorated_function


def get_current_staff():
    """
    Helper function to get current logged-in staff account.
    Returns StaffAccount object or None.
    
    In MIS system, current_user IS the StaffAccount object directly.
    """
    if not current_user.is_authenticated:
        return None
    
    # In MIS system, current_user is already a StaffAccount instance
    # Check if it's a StaffAccount by verifying it has the expected attributes
    if hasattr(current_user, 'personal_info') or hasattr(current_user, 'email'):
        return current_user
    
    # Fallback: check if it has a staff_account attribute (for compatibility)
    if hasattr(current_user, 'staff_account'):
        return current_user.staff_account
    
    return None


def has_role_for_event(staff_id, event_id, role_class):
    """
    Check if staff has specific role for an event.
    
    Args:
        staff_id: StaffAccount ID
        event_id: EventEntity ID
        role_class: One of the role model classes (EventEditor, EventRegistrationReviewer, etc.)
    
    Returns:
        Boolean indicating if staff has the role
    """
    return role_class.query.filter_by(
        staff_id=staff_id,
        event_entity_id=event_id
    ).first() is not None


def is_event_editor(staff_id, event_id):
    """Check if staff is an editor for the event."""
    return has_role_for_event(staff_id, event_id, EventEditor)


def is_registration_reviewer(staff_id, event_id):
    """Check if staff is a registration reviewer for the event."""
    return has_role_for_event(staff_id, event_id, EventRegistrationReviewer)


def is_payment_approver(staff_id, event_id):
    """Check if staff is a payment approver for the event."""
    return has_role_for_event(staff_id, event_id, EventPaymentApprover)


def is_receipt_issuer(staff_id, event_id):
    """Check if staff is a receipt issuer for the event."""
    return has_role_for_event(staff_id, event_id, EventReceiptIssuer)


def is_certificate_manager(staff_id, event_id):
    """Check if staff is a certificate manager for the event."""
    return has_role_for_event(staff_id, event_id, EventCertificateManager)


def has_any_role_for_event(staff_id, event_id):
    """
    Check if staff has ANY role for an event.
    Useful for determining if staff should see the event at all.
    """
    return (
        is_event_editor(staff_id, event_id) or
        is_registration_reviewer(staff_id, event_id) or
        is_payment_approver(staff_id, event_id) or
        is_receipt_issuer(staff_id, event_id) or
        is_certificate_manager(staff_id, event_id)
    )


def require_event_role(*allowed_roles):
    """
    Decorator to require specific role(s) for an event.
    
    Usage:
        @require_event_role('editor', 'payment_approver')
        def edit_event(event_id):
            ...
    
    Allowed roles:
        - 'editor': EventEditor
        - 'registration_reviewer': EventRegistrationReviewer
        - 'payment_approver': EventPaymentApprover
        - 'receipt_issuer': EventReceiptIssuer
        - 'certificate_manager': EventCertificateManager
        - 'any': Any role (staff just needs to be assigned to the event)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please login to access this page.', 'error')
                return redirect(url_for('auth.login'))
            
            staff = get_current_staff()
            if not staff:
                flash('Access denied. Staff account required.', 'error')
                abort(403)
            
            # Get event_id from kwargs or args
            event_id = kwargs.get('event_id') or kwargs.get('id')
            if not event_id and args:
                event_id = args[0]
            
            if not event_id:
                flash('Event ID not specified.', 'error')
                abort(400)
            
            # Check roles
            role_checks = {
                'editor': lambda: is_event_editor(staff.id, event_id),
                'registration_reviewer': lambda: is_registration_reviewer(staff.id, event_id),
                'payment_approver': lambda: is_payment_approver(staff.id, event_id),
                'receipt_issuer': lambda: is_receipt_issuer(staff.id, event_id),
                'certificate_manager': lambda: is_certificate_manager(staff.id, event_id),
                'any': lambda: has_any_role_for_event(staff.id, event_id)
            }
            
            # Check if user has any of the allowed roles
            has_permission = False
            for role in allowed_roles:
                if role in role_checks and role_checks[role]():
                    has_permission = True
                    break
            
            if not has_permission:
                flash('You do not have permission to perform this action.', 'error')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def can_manage_registrations(f):
    """
    Decorator to check if staff can manage registrations.
    Checks if staff has registration reviewer or editor role for any event.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        staff = get_current_staff()
        if not staff:
            flash('Staff account not found.', 'error')
            abort(403)
        
        # Get event_id from kwargs or args if available
        event_id = kwargs.get('event_id') or kwargs.get('registration_id')
        
        # Check if staff has registration reviewer or editor role
        has_permission = False
        
        if event_id:
            # Check for specific event
            has_permission = (
                is_registration_reviewer(staff.id, event_id) or 
                is_event_editor(staff.id, event_id)
            )
        else:
            # Check if staff has role for any event
            has_permission = (
                EventRegistrationReviewer.query.filter_by(staff_id=staff.id).first() is not None or
                EventEditor.query.filter_by(staff_id=staff.id).first() is not None
            )
        
        if not has_permission:
            flash('You do not have permission to manage registrations.', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def check_can_manage_registrations(staff_id, event_id=None):
    """
    Helper function to check if staff can manage registrations.
    Use this for programmatic checks (not as decorator).
    """
    if event_id:
        return is_registration_reviewer(staff_id, event_id) or is_event_editor(staff_id, event_id)
    
    return (
        EventRegistrationReviewer.query.filter_by(staff_id=staff_id).first() is not None or
        EventEditor.query.filter_by(staff_id=staff_id).first() is not None
    )


def can_manage_payments(f):
    """
    Decorator to check if staff can manage payments.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        staff = get_current_staff()
        if not staff:
            flash('Staff account not found.', 'error')
            abort(403)
        
        event_id = kwargs.get('event_id') or kwargs.get('payment_id')
        
        has_permission = False
        if event_id:
            has_permission = (
                is_payment_approver(staff.id, event_id) or 
                is_event_editor(staff.id, event_id)
            )
        else:
            has_permission = (
                EventPaymentApprover.query.filter_by(staff_id=staff.id).first() is not None or
                EventEditor.query.filter_by(staff_id=staff.id).first() is not None
            )
        
        if not has_permission:
            flash('You do not have permission to manage payments.', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def check_can_manage_payments(staff_id, event_id=None):
    """
    Helper function to check if staff can manage payments.
    """
    if event_id:
        return is_payment_approver(staff_id, event_id) or is_event_editor(staff_id, event_id)
    
    return (
        EventPaymentApprover.query.filter_by(staff_id=staff_id).first() is not None or
        EventEditor.query.filter_by(staff_id=staff_id).first() is not None
    )


def can_issue_receipts(staff_id, event_id=None):
    """
    Check if staff can issue receipts.
    """
    if event_id:
        return is_receipt_issuer(staff_id, event_id) or is_event_editor(staff_id, event_id)
    
    return (
        EventReceiptIssuer.query.filter_by(staff_id=staff_id).first() is not None or
        EventEditor.query.filter_by(staff_id=staff_id).first() is not None
    )


def can_manage_certificates(staff_id, event_id=None):
    """
    Check if staff can manage certificates.
    """
    if event_id:
        return is_certificate_manager(staff_id, event_id) or is_event_editor(staff_id, event_id)
    
    return (
        EventCertificateManager.query.filter_by(staff_id=staff_id).first() is not None or
        EventEditor.query.filter_by(staff_id=staff_id).first() is not None
    )


def get_staff_permissions(staff_id):
    """
    Get a summary of all permissions for a staff member.
    Returns a dictionary with permission flags.
    """
    return {
        'can_create_events': True,  # All staff can create events
        'can_manage_registrations': can_manage_registrations(staff_id),
        'can_manage_payments': can_manage_payments(staff_id),
        'can_issue_receipts': can_issue_receipts(staff_id),
        'can_manage_certificates': can_manage_certificates(staff_id),
        'events_as_editor': [e.event_entity_id for e in EventEditor.query.filter_by(staff_id=staff_id).all()],
        'events_as_registration_reviewer': [e.event_entity_id for e in EventRegistrationReviewer.query.filter_by(staff_id=staff_id).all()],
        'events_as_payment_approver': [e.event_entity_id for e in EventPaymentApprover.query.filter_by(staff_id=staff_id).all()],
        'events_as_receipt_issuer': [e.event_entity_id for e in EventReceiptIssuer.query.filter_by(staff_id=staff_id).all()],
        'events_as_certificate_manager': [e.event_entity_id for e in EventCertificateManager.query.filter_by(staff_id=staff_id).all()],
    }


def filter_events_by_permission(staff_id, events, permission_type='any'):
    """
    Filter events list to only show those staff has permission for.
    
    Args:
        staff_id: StaffAccount ID
        events: List of EventEntity objects
        permission_type: 'any', 'editor', 'registration', 'payment', 'receipt', 'certificate'
    
    Returns:
        Filtered list of events
    """
    if permission_type == 'any':
        return [e for e in events if has_any_role_for_event(staff_id, e.id)]
    elif permission_type == 'editor':
        return [e for e in events if is_event_editor(staff_id, e.id)]
    elif permission_type == 'registration':
        return [e for e in events if can_manage_registrations(staff_id, e.id)]
    elif permission_type == 'payment':
        return [e for e in events if can_manage_payments(staff_id, e.id)]
    elif permission_type == 'receipt':
        return [e for e in events if can_issue_receipts(staff_id, e.id)]
    elif permission_type == 'certificate':
        return [e for e in events if can_manage_certificates(staff_id, e.id)]
    
    return events
