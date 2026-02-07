"""
Add @login_required and @admin_required decorators to routes that don't have them yet.
"""
import re

def add_decorators_to_routes(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        
        # Check if this is a route decorator line
        if line.strip().startswith('@admin_bp.route('):
            # Check if the next lines already have decorators
            has_login_required = False
            has_admin_or_role_required = False
            j = i + 1
            
            # Look ahead at the next few lines
            while j < len(lines) and lines[j].strip().startswith('@'):
                if '@login_required' in lines[j]:
                    has_login_required = True
                if '@admin_required' in lines[j] or '@require_event_role' in lines[j]:
                    has_admin_or_role_required = True
                j += 1
            
            # If no decorators, add them before the function definition
            if not has_login_required:
                new_lines.append('@login_required\n')
            if not has_admin_or_role_required:
                new_lines.append('@admin_required\n')
        
        i += 1
    
    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    
    print("Added decorators to routes")

if __name__ == '__main__':
    views_file = '/Users/vikornsak/PycharmProjects/2025/mis2018/app/continuing_edu/admin/views.py'
    add_decorators_to_routes(views_file)
