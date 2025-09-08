from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from app.staff.models import StaffAccount
from werkzeug.security import check_password_hash


from app.continuing_edu.models import EventEntity, Member, RegisterPayment, MemberRegistration
from sqlalchemy import func
import datetime

admin_bp = Blueprint('continuing_edu_admin', __name__, url_prefix='/continuing_edu/admin')

def get_current_admin():
    admin_id = session.get('admin_id')
    if admin_id:
        return StaffAccount.query.get(admin_id)
    return None

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].split('@')[0]  # Use part before '@' as username
        password = request.form['password']
        print('Username:', username)
    latest_courses = EventEntity.query.filter_by(event_type='course').order_by(EventEntity.created_at.desc()).limit(5).all()

    # Attach .limit property if not present, and ensure payments/registrations are loaded
    for course in latest_courses:
        if not hasattr(course, 'limit'):
            # You can replace this with the real field if exists
            course.limit = getattr(course, 'max_registrations', None) or '-'  # fallback if not set
        # Force load relationships if lazy
        _ = course.registrations
        _ = course.payments

        staff = StaffAccount.query.filter_by(email=username).first()
        if staff and staff.verify_password(password):
            session['admin_id'] = staff.id
            flash('Login successful', 'success')
            return redirect(url_for('continuing_edu_admin.dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('continueing_edu/admin/login.html')

@admin_bp.route('/logout')
def logout():
    session.pop('admin_id', None)
    flash('Logged out', 'success')
    return redirect(url_for('continuing_edu_admin.login'))



@admin_bp.route('/')
def dashboard():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    # Summary counts
    current_date = datetime.date.today().strftime('%A %d %B %Y')

    course_count = EventEntity.query.filter_by(event_type='course').count()
    member_count = Member.query.count()
    payment_sum = RegisterPayment.query.with_entities(func.sum(RegisterPayment.payment_amount)).scalar() or 0
    registration_count = MemberRegistration.query.count()

    # Latest courses (limit 5)
    latest_courses = EventEntity.query.filter_by(event_type='course').order_by(EventEntity.created_at.desc()).limit(5).all()

    return render_template(
        'continueing_edu/admin/dashboard.html',
        logged_in_admin=admin,
        course_count=course_count,
        member_count=member_count,
        payment_sum=payment_sum,
        registration_count=registration_count,
        latest_courses=latest_courses,
        current_date=current_date
    )

@admin_bp.route('/events')
def manage_events():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    # TODO: Query events for admin management
    return render_template('continueing_edu/admin/events.html', logged_in_admin=admin)
