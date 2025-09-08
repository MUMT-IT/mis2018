from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from app.staff.models import StaffAccount
from werkzeug.security import check_password_hash

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def get_current_admin():
    admin_id = session.get('admin_id')
    if admin_id:
        return StaffAccount.query.get(admin_id)
    return None

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        staff = StaffAccount.query.filter_by(username=username).first()
        if staff and check_password_hash(staff.password_hash, password):
            session['admin_id'] = staff.id
            flash('Login successful', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('admin/login.html')

@admin_bp.route('/logout')
def logout():
    session.pop('admin_id', None)
    flash('Logged out', 'success')
    return redirect(url_for('admin.login'))

@admin_bp.route('/')
def dashboard():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('admin.login'))
    return render_template('admin/dashboard.html', logged_in_admin=admin)

# Example admin management page
@admin_bp.route('/events')
def manage_events():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('admin.login'))
    # TODO: Query events for admin management
    return render_template('admin/events.html', logged_in_admin=admin)
