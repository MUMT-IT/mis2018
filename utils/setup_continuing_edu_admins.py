"""
Script to add continuing_edu_admin role and assign it to initial administrators.
Run this script once to set up the continuing education admin permissions.

Usage:
    python utils/setup_continuing_edu_admins.py
"""
import sys
import os

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app, db
from app.staff.models import Role, StaffAccount

def create_continuing_edu_role():
    """Create the continuing_edu_admin role if it doesn't exist."""
    with app.app_context():
        # Check if role already exists
        role = Role.query.filter_by(
            role_need='continuing_edu_admin',
            action_need=None,
            resource_id=None
        ).first()
        
        if role:
            print(f"✓ Role 'continuing_edu_admin' already exists (ID: {role.id})")
            return role
        
        # Create new role
        role = Role(
            role_need='continuing_edu_admin',
            action_need=None,
            resource_id=None
        )
        db.session.add(role)
        db.session.commit()
        print(f"✓ Created role 'continuing_edu_admin' (ID: {role.id})")
        return role


def assign_admin_role(email, role):
    """Assign continuing_edu_admin role to a staff member by email."""
    with app.app_context():
        staff = StaffAccount.query.filter_by(email=email).first()
        
        if not staff:
            print(f"✗ Staff with email '{email}' not found")
            return False
        
        # Check if already has the role
        if role in staff.roles:
            print(f"✓ {staff.fullname} ({email}) already has continuing_edu_admin role")
            return True
        
        # Assign role
        staff.roles.append(role)
        db.session.commit()
        print(f"✓ Assigned continuing_edu_admin role to {staff.fullname} ({email})")
        return True


def main():
    """Main function to set up continuing edu admins."""
    print("=" * 70)
    print("Setting up Continuing Education Admin Permissions")
    print("=" * 70)
    print()
    
    # Step 1: Create role
    print("Step 1: Creating continuing_edu_admin role...")
    role = create_continuing_edu_role()
    print()
    
    # Step 2: Assign to initial admins
    print("Step 2: Assigning role to initial administrators...")
    print()
    
    # TODO: Add your email addresses here
    initial_admins = [
        # Example:
         'vikornsak.rak',
        'another.admin',
    ]
    
    if not initial_admins:
        print("⚠ No initial admins specified!")
        print("Please edit this script and add email addresses to the 'initial_admins' list")
        print()
        print("Or assign roles manually using:")
        print("  >>> from app.staff.models import Role, StaffAccount")
        print("  >>> role = Role.query.filter_by(role_need='continuing_edu_admin').first()")
        print("  >>> staff = StaffAccount.query.filter_by(email='your.email@mahidol.ac.th').first()")
        print("  >>> staff.roles.append(role)")
        print("  >>> db.session.commit()")
    else:
        success_count = 0
        for email in initial_admins:
            if assign_admin_role(email, role):
                success_count += 1
        
        print()
        print(f"✓ Successfully assigned role to {success_count}/{len(initial_admins)} staff members")
    
    print()
    print("=" * 70)
    print("Setup Complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Restart the Flask application to load the new permission")
    print("2. Staff with continuing_edu_admin role can now access /continuing_edu/admin/")
    print("3. Use the admin UI to manage additional administrators")
    print()


if __name__ == '__main__':
    main()
