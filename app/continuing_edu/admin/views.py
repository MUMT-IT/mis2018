from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired

from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from app.staff.models import StaffAccount
from werkzeug.security import check_password_hash, generate_password_hash


from app.continuing_edu.models import (
    EventEntity,
    Member,
    RegisterPayment,
    RegisterPaymentStatus,
    RegisterPaymentReceipt,
    MemberRegistration,
    MemberType,
    RegistrationStatus,
    EntityCategory,
    MemberCertificateStatus,
    EventSpeaker,
    SpeakerProfile,
    EventAgenda,
    EventMaterial,
    EventRegistrationFee,
    EventEditor,
    EventRegistrationReviewer,
    EventPaymentApprover,
    EventReceiptIssuer,
    EventCertificateManager,
)
from sqlalchemy import func
import datetime
from app.main import db, mail

admin_bp = Blueprint('continuing_edu_admin', __name__, url_prefix='/continuing_edu/admin')


class EventCreateStep1Form(FlaskForm):
    event_type = SelectField('Event Type', choices=[('course', 'Course'), ('webinar', 'Webinar')], validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired()])
    submit = SubmitField('Next')

@admin_bp.route('/events/create', methods=['GET', 'POST'])
def create_event():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    form = EventCreateStep1Form()
    if form.validate_on_submit():
        # Create EventEntity row with minimal info
        event = EventEntity(event_type=form.event_type.data, title_en=form.title.data, staff_id=admin.id)
        db.session.add(event)
        db.session.commit()
        # Redirect to edit page with tabs for further info
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id))
    return render_template('continueing_edu/admin/event_create_step1.html', form=form, logged_in_admin=admin)

@admin_bp.route('/events/<int:event_id>/edit', methods=['GET'])
def edit_event(event_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    event = EventEntity.query.get_or_404(event_id)

    # Load related data for all tabs
    speakers = EventSpeaker.query.filter_by(event_entity_id=event.id).all()
    agendas = EventAgenda.query.filter_by(event_entity_id=event.id).order_by(EventAgenda.order.asc()).all()
    materials = EventMaterial.query.filter_by(event_entity_id=event.id).order_by(EventMaterial.order.asc()).all()
    fees = EventRegistrationFee.query.filter_by(event_entity_id=event.id).all()
    # Staff list for role assignments
    staff_list = StaffAccount.query.all()
    member_types = MemberType.query.order_by(MemberType.name_en.asc()).all()

    # Current staff role assignments
    editors = EventEditor.query.filter_by(event_entity_id=event.id).all()
    registration_reviewers = EventRegistrationReviewer.query.filter_by(event_entity_id=event.id).all()
    payment_approvers = EventPaymentApprover.query.filter_by(event_entity_id=event.id).all()
    receipt_issuers = EventReceiptIssuer.query.filter_by(event_entity_id=event.id).all()
    certificate_managers = EventCertificateManager.query.filter_by(event_entity_id=event.id).all()

    # Speaker pool (existing speakers from any event) for reuse
    speakers_pool = SpeakerProfile.query.filter_by(is_active=True).order_by(SpeakerProfile.name_en.asc()).all()

    active_tab = request.args.get('tab', 'general')

    return render_template(
        'continueing_edu/admin/event_edit_tabs.html',
        event=event,
        speakers=speakers,
        agendas=agendas,
        materials=materials,
        fees=fees,
        staff_list=staff_list,
        member_types=member_types,
        speakers_pool=speakers_pool,
        editors=editors,
        registration_reviewers=registration_reviewers,
        payment_approvers=payment_approvers,
        receipt_issuers=receipt_issuers,
        certificate_managers=certificate_managers,
        active_tab=active_tab,
        logged_in_admin=admin,
    )

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
    events = EventEntity.query.order_by(EventEntity.created_at.desc()).all()
    return render_template('continueing_edu/admin/events.html', logged_in_admin=admin, events=events)


@admin_bp.route('/progress')
def progress_index():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    events = EventEntity.query.order_by(EventEntity.created_at.desc()).all()
    # Build simple stats per event
    stats = {}
    for e in events:
        regs = MemberRegistration.query.filter_by(event_entity_id=e.id).all()
        started = len([r for r in regs if r.started_at])
        completed = len([r for r in regs if r.completed_at])
        issued = len([r for r in regs if r.certificate_issued_date])
        stats[e.id] = {
            'registrations': len(regs),
            'started': started,
            'completed': completed,
            'cert_issued': issued,
        }
    return render_template('continueing_edu/admin/progress_index.html', logged_in_admin=admin, events=events, stats=stats)


@admin_bp.route('/promotions')
def promotions_index():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    events = EventEntity.query.order_by(EventEntity.created_at.desc()).all()
    return render_template('continueing_edu/admin/promotions_index.html', logged_in_admin=admin, events=events)


# -----------------------------
# Members Management (CRUD)
# -----------------------------
@admin_bp.route('/members')
def members_index():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    q = request.args.get('q', '').strip()
    member_type_id = request.args.get('member_type_id')
    is_verified = request.args.get('is_verified')
    received_news = request.args.get('received_news')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = Member.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Member.username.ilike(like)) |
            (Member.email.ilike(like)) |
            (Member.full_name_en.ilike(like)) |
            (Member.full_name_th.ilike(like))
        )
    if member_type_id:
        try:
            query = query.filter_by(member_type_id=int(member_type_id))
        except Exception:
            pass
    if is_verified in ('0', '1'):
        query = query.filter_by(is_verified=(is_verified == '1'))
    if received_news in ('0', '1'):
        query = query.filter_by(received_news=(received_news == '1'))

    pagination = query.order_by(Member.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    members = pagination.items
    member_types = MemberType.query.order_by(MemberType.name_en.asc()).all()
    return render_template('continueing_edu/admin/members.html',
                           logged_in_admin=admin,
                           members=members,
                           pagination=pagination,
                           q=q,
                           member_type_id=str(member_type_id) if member_type_id else '',
                           is_verified=is_verified or '',
                           received_news=received_news or '',
                           member_types=member_types)


@admin_bp.route('/members/create', methods=['GET', 'POST'])
def members_create():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip() or None
        password = request.form.get('password', '').strip()
        member_type_id = request.form.get('member_type_id') or None
        full_name_en = request.form.get('full_name_en') or None
        full_name_th = request.form.get('full_name_th') or None
        phone_no = request.form.get('phone_no') or None
        address = request.form.get('address') or None
        is_verified = request.form.get('is_verified') == 'on'
        received_news = request.form.get('received_news') == 'on'

        # Basic validations
        if not username:
            flash('Username is required.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_create'))
        if Member.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_create'))
        if email and Member.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_create'))
        if not password:
            flash('Password is required.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_create'))

        try:
            member = Member(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                member_type_id=int(member_type_id) if member_type_id else None,
                full_name_en=full_name_en,
                full_name_th=full_name_th,
                phone_no=phone_no,
                address=address,
                is_verified=is_verified,
                received_news=received_news,
            )
            db.session.add(member)
            db.session.commit()
            flash('Member created.', 'success')
            return redirect(url_for('continuing_edu_admin.members_index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating member: {e}', 'danger')

    member_types = MemberType.query.order_by(MemberType.name_en.asc()).all()
    return render_template('continueing_edu/admin/member_form.html',
                           logged_in_admin=admin,
                           member=None,
                           member_types=member_types,
                           form_action=url_for('continuing_edu_admin.members_create'))


@admin_bp.route('/members/<int:member_id>/edit', methods=['GET', 'POST'])
def members_edit(member_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    member = Member.query.get_or_404(member_id)
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip() or None
        password = request.form.get('password', '').strip()
        member_type_id = request.form.get('member_type_id') or None
        full_name_en = request.form.get('full_name_en') or None
        full_name_th = request.form.get('full_name_th') or None
        phone_no = request.form.get('phone_no') or None
        address = request.form.get('address') or None
        is_verified = request.form.get('is_verified') == 'on'
        received_news = request.form.get('received_news') == 'on'

        if not username:
            flash('Username is required.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_edit', member_id=member.id))
        # Ensure username/email uniqueness
        if username != member.username and Member.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_edit', member_id=member.id))
        if email and email != member.email and Member.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('continuing_edu_admin.members_edit', member_id=member.id))

        try:
            member.username = username
            member.email = email
            if password:
                member.password_hash = generate_password_hash(password)
            member.member_type_id = int(member_type_id) if member_type_id else None
            member.full_name_en = full_name_en
            member.full_name_th = full_name_th
            member.phone_no = phone_no
            member.address = address
            member.is_verified = is_verified
            member.received_news = received_news
            db.session.add(member)
            db.session.commit()
            flash('Member updated.', 'success')
            return redirect(url_for('continuing_edu_admin.members_index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating member: {e}', 'danger')

    member_types = MemberType.query.order_by(MemberType.name_en.asc()).all()
    return render_template('continueing_edu/admin/member_form.html',
                           logged_in_admin=admin,
                           member=member,
                           member_types=member_types,
                           form_action=url_for('continuing_edu_admin.members_edit', member_id=member.id))


@admin_bp.route('/members/<int:member_id>/delete', methods=['POST'])
def members_delete(member_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    member = Member.query.get_or_404(member_id)
    try:
        db.session.delete(member)
        db.session.commit()
        flash('Member deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete member: {e}', 'danger')
    return redirect(url_for('continuing_edu_admin.members_index'))


# -----------------------------
# General Settings: Member Types
# -----------------------------
@admin_bp.route('/settings/member_types', methods=['GET', 'POST'])
def settings_member_types():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    if request.method == 'POST':
        name_en = request.form.get('name_en', '').strip()
        name_th = request.form.get('name_th', '').strip()
        code = request.form.get('code', '').strip() or None
        if not name_en or not name_th:
            flash('Both English and Thai names are required.', 'danger')
        else:
            mt = MemberType(name_en=name_en, name_th=name_th, member_type_code=code)
            db.session.add(mt)
            try:
                db.session.commit()
                flash('Member type added.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {e}', 'danger')
        return redirect(url_for('continuing_edu_admin.settings_member_types'))
    mtypes = MemberType.query.order_by(MemberType.name_en.asc()).all()
    return render_template('continueing_edu/admin/settings_member_types.html', logged_in_admin=admin, items=mtypes)


@admin_bp.route('/settings/member_types/<int:item_id>/edit', methods=['GET', 'POST'])
def settings_member_types_edit(item_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    mt = MemberType.query.get_or_404(item_id)
    if request.method == 'POST':
        mt.name_en = request.form.get('name_en', mt.name_en)
        mt.name_th = request.form.get('name_th', mt.name_th)
        code = request.form.get('code', '').strip() or None
        mt.member_type_code = code
        db.session.add(mt)
        try:
            db.session.commit()
            flash('Member type updated.', 'success')
            return redirect(url_for('continuing_edu_admin.settings_member_types'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')
    return render_template('continueing_edu/admin/settings_member_types_form.html', logged_in_admin=admin, item=mt)


@admin_bp.route('/settings/member_types/<int:item_id>/delete', methods=['POST'])
def settings_member_types_delete(item_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    mt = MemberType.query.get_or_404(item_id)
    try:
        db.session.delete(mt)
        db.session.commit()
        flash('Member type deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete: {e}', 'danger')
    return redirect(url_for('continuing_edu_admin.settings_member_types'))


# -----------------------------
# General Settings: Registration Statuses
# -----------------------------
@admin_bp.route('/settings/registration_statuses', methods=['GET', 'POST'])
def settings_registration_statuses():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    if request.method == 'POST':
        name_en = request.form.get('name_en', '').strip()
        name_th = request.form.get('name_th', '').strip()
        code = request.form.get('code', '').strip() or None
        css_badge = request.form.get('css_badge', '').strip() or None
        if not name_en or not name_th:
            flash('Both English and Thai names are required.', 'danger')
        else:
            st = RegistrationStatus(name_en=name_en, name_th=name_th, css_badge=css_badge,
                                    registration_status_code=code)
            db.session.add(st)
            try:
                db.session.commit()
                flash('Registration status added.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {e}', 'danger')
        return redirect(url_for('continuing_edu_admin.settings_registration_statuses'))
    items = RegistrationStatus.query.order_by(RegistrationStatus.name_en.asc()).all()
    return render_template('continueing_edu/admin/settings_registration_statuses.html', logged_in_admin=admin, items=items)


@admin_bp.route('/settings/registration_statuses/<int:item_id>/edit', methods=['GET', 'POST'])
def settings_registration_statuses_edit(item_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    st = RegistrationStatus.query.get_or_404(item_id)
    if request.method == 'POST':
        st.name_en = request.form.get('name_en', st.name_en)
        st.name_th = request.form.get('name_th', st.name_th)
        st.css_badge = request.form.get('css_badge', st.css_badge)
        st.registration_status_code = request.form.get('code', '').strip() or None
        db.session.add(st)
        try:
            db.session.commit()
            flash('Registration status updated.', 'success')
            return redirect(url_for('continuing_edu_admin.settings_registration_statuses'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')
    return render_template('continueing_edu/admin/settings_registration_statuses_form.html', logged_in_admin=admin, item=st)


@admin_bp.route('/settings/registration_statuses/<int:item_id>/delete', methods=['POST'])
def settings_registration_statuses_delete(item_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    st = RegistrationStatus.query.get_or_404(item_id)
    try:
        db.session.delete(st)
        db.session.commit()
        flash('Registration status deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete: {e}', 'danger')
    return redirect(url_for('continuing_edu_admin.settings_registration_statuses'))


# -----------------------------
# General Settings: Payment Statuses
# -----------------------------
@admin_bp.route('/settings/payment_statuses', methods=['GET', 'POST'])
def settings_payment_statuses():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    if request.method == 'POST':
        name_en = request.form.get('name_en', '').strip()
        name_th = request.form.get('name_th', '').strip()
        code = request.form.get('code', '').strip() or None
        css_badge = request.form.get('css_badge', '').strip() or None
        if not name_en or not name_th:
            flash('Both English and Thai names are required.', 'danger')
        else:
            st = RegisterPaymentStatus(name_en=name_en, name_th=name_th, css_badge=css_badge,
                                       register_payment_status_code=code)
            db.session.add(st)
            try:
                db.session.commit()
                flash('Payment status added.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {e}', 'danger')
        return redirect(url_for('continuing_edu_admin.settings_payment_statuses'))
    items = RegisterPaymentStatus.query.order_by(RegisterPaymentStatus.name_en.asc()).all()
    return render_template('continueing_edu/admin/settings_payment_statuses.html', logged_in_admin=admin, items=items)


@admin_bp.route('/settings/payment_statuses/<int:item_id>/edit', methods=['GET', 'POST'])
def settings_payment_statuses_edit(item_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    st = RegisterPaymentStatus.query.get_or_404(item_id)
    if request.method == 'POST':
        st.name_en = request.form.get('name_en', st.name_en)
        st.name_th = request.form.get('name_th', st.name_th)
        st.css_badge = request.form.get('css_badge', st.css_badge)
        st.register_payment_status_code = request.form.get('code', '').strip() or None
        db.session.add(st)
        try:
            db.session.commit()
            flash('Payment status updated.', 'success')
            return redirect(url_for('continuing_edu_admin.settings_payment_statuses'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')
    return render_template('continueing_edu/admin/settings_payment_statuses_form.html', logged_in_admin=admin, item=st)


@admin_bp.route('/settings/payment_statuses/<int:item_id>/delete', methods=['POST'])
def settings_payment_statuses_delete(item_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    st = RegisterPaymentStatus.query.get_or_404(item_id)
    try:
        db.session.delete(st)
        db.session.commit()
        flash('Payment status deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete: {e}', 'danger')
    return redirect(url_for('continuing_edu_admin.settings_payment_statuses'))


# -----------------------------
# General Settings: Entity Categories
# -----------------------------
@admin_bp.route('/settings/entity_categories', methods=['GET', 'POST'])
def settings_entity_categories():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    if request.method == 'POST':
        name_en = request.form.get('name_en', '').strip()
        name_th = request.form.get('name_th', '').strip()
        code = request.form.get('code', '').strip() or None
        description = request.form.get('description', '').strip()
        if not name_en or not name_th:
            flash('Both English and Thai names are required.', 'danger')
        else:
            cat = EntityCategory(name_en=name_en, name_th=name_th, description=description, entity_category_code=code)
            db.session.add(cat)
            try:
                db.session.commit()
                flash('Entity category added.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error: {e}', 'danger')
        return redirect(url_for('continuing_edu_admin.settings_entity_categories'))
    items = EntityCategory.query.order_by(EntityCategory.name_en.asc()).all()
    return render_template('continueing_edu/admin/settings_entity_categories.html', logged_in_admin=admin, items=items)


@admin_bp.route('/settings/entity_categories/<int:item_id>/edit', methods=['GET', 'POST'])
def settings_entity_categories_edit(item_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    cat = EntityCategory.query.get_or_404(item_id)
    if request.method == 'POST':
        cat.name_en = request.form.get('name_en', cat.name_en)
        cat.name_th = request.form.get('name_th', cat.name_th)
        cat.description = request.form.get('description', cat.description)
        cat.entity_category_code = request.form.get('code', '').strip() or None
        db.session.add(cat)
        try:
            db.session.commit()
            flash('Entity category updated.', 'success')
            return redirect(url_for('continuing_edu_admin.settings_entity_categories'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')
    return render_template('continueing_edu/admin/settings_entity_categories_form.html', logged_in_admin=admin, item=cat)


@admin_bp.route('/settings/entity_categories/<int:item_id>/delete', methods=['POST'])
def settings_entity_categories_delete(item_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    cat = EntityCategory.query.get_or_404(item_id)
    try:
        db.session.delete(cat)
        db.session.commit()
        flash('Entity category deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Cannot delete: {e}', 'danger')
    return redirect(url_for('continuing_edu_admin.settings_entity_categories'))


@admin_bp.route('/events/<int:event_id>/notify', methods=['GET','POST'])
def event_notify(event_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    event = EventEntity.query.get_or_404(event_id)
    # Audience filters
    only_optin = (request.values.get('only_optin', '1') in ('1','true','yes','on'))
    only_verified = (request.values.get('only_verified', '1') in ('1','true','yes','on'))
    member_type_ids = request.values.getlist('member_type_id')
    # Build recipients query
    q = Member.query
    if only_optin:
        q = q.filter_by(received_news=True)
    if only_verified:
        q = q.filter_by(is_verified=True)
    if member_type_ids:
        try:
            ids = [int(i) for i in member_type_ids]
            q = q.filter(Member.member_type_id.in_(ids))
        except Exception:
            pass
    q = q.filter(Member.email.isnot(None))
    recipients = [m.email for m in q.all()]

    # Build event link
    try:
        if event.event_type == 'course':
            link = url_for('continuing_edu.course_detail', course_id=event.id, lang='en', _external=True)
        else:
            link = url_for('continuing_edu.webinar_detail', webinar_id=event.id, lang='en', _external=True)
    except Exception:
        link = ''

    subject_default = f"[CE] New Event: {event.title_en or event.title_th or 'Event'}"
    email_html_tpl = (
        "<div style=\"font-family:Arial,sans-serif;font-size:14px;color:#333;\">"
        "<h2 style=\"margin:0 0 8px 0;\">{{ event.title_en or event.title_th }}</h2>"
        "{% set img = event.cover_presigned_url() or event.poster_presigned_url() or event.image_url %}"
        "{% if img %}<div style=\"margin:10px 0;\"><img src=\"{{ img }}\" style=\"max-width:100%;height:auto;\"></div>{% endif %}"
        "{% if event.description_en %}<h3>About (EN)</h3><p>{{ event.description_en }}</p>{% endif %}"
        "{% if event.description_th %}<hr><h3>รายละเอียด (TH)</h3><p>{{ event.description_th }}</p>{% endif %}"
        "{% if link %}<p style=\"margin-top:16px;\"><a href=\"{{ link }}\" style=\"background:#4f46e5;color:#fff;padding:10px 16px;text-decoration:none;border-radius:4px;\">View / Register</a></p>{% endif %}"
        "<p style=\"color:#888;font-size:12px;margin-top:24px;\">You receive this because you opted in. Update preferences to unsubscribe.</p>"
        "</div>"
    )

    if request.method == 'GET':
        # Preview inline using a small template string to avoid filesystem writes
        from flask import render_template_string
        subject = request.values.get('subject', subject_default)
        recipients_count = len(recipients)
        if recipients_count == 0:
            flash('No recipients matched the selected filters.', 'warning')
            return redirect(url_for('continuing_edu_admin.manage_events'))
        html_preview = render_template_string(email_html_tpl, event=event, link=link)
        # Render a minimal preview page with filters
        page_tpl = (
            "{% extends 'continueing_edu/admin/base.html' %}{% block content %}"
            "<div class=container><h1 class=\"title is-3\">Notify Subscribers: {{ event.title_en or event.title_th }}</h1>"
            "<form method=GET class=\"box\">"
            "<div class=\"field\"><label class=label>Subject</label><input class=input name=subject value=\"{{ subject }}\"></div>"
            "<div class=\"field is-grouped\">"
            "<label class=\"checkbox\"><input type=checkbox name=only_optin {% if only_optin %}checked{% endif %}> Only opted-in</label>"
            "<label class=\"checkbox ml-4\"><input type=checkbox name=only_verified {% if only_verified %}checked{% endif %}> Only verified</label>"
            "</div>"
            "<div class=\"field\"><label class=label>Member Types</label><div class=select multiple><select multiple name=member_type_id>"
            "{% for mt in MemberType.query.order_by(MemberType.name_en.asc()).all() %}"
            "<option value=\"{{ mt.id }}\" {% if mt.id|string in member_type_ids %}selected{% endif %}>{{ mt.name_en }} / {{ mt.name_th }}</option>"
            "{% endfor %}"
            "</select></div></div>"
            "<div class=\"field is-grouped\"><div class=control>"
            "<button class=\"button is-link\" type=submit>Update Preview</button>"
            "</div>"
            "<div class=control><form method=POST><input type=hidden name=subject value=\"{{ subject }}\">"
            "{% for mtid in member_type_ids %}<input type=hidden name=member_type_id value=\"{{ mtid }}\">{% endfor %}"
            "<input type=hidden name=only_optin value=\"{{ 1 if only_optin else 0 }}\"><input type=hidden name=only_verified value=\"{{ 1 if only_verified else 0 }}\">"
            "<button class=\"button is-primary\" type=submit onclick=\"return confirm('Send to '+{{ recipients_count }}+' recipients?')\">Send Notification</button></form></div>"
            "<div class=control><a class=\"button\" href=\"{{ url_for('continuing_edu_admin.manage_events') }}\">Cancel</a></div></div>"
            "</form>"
            "<hr><h2 class=\"title is-5\">Preview ({{ recipients_count }} recipients)</h2><div class=box style=\"max-width:860px;\">{{ html_preview|safe }}</div></div>"
            "{% endblock %}"
        )
        return render_template_string(page_tpl, event=event, subject=subject, html_preview=html_preview,
                                      recipients_count=recipients_count, only_optin=only_optin, only_verified=only_verified,
                                      member_type_ids=member_type_ids, MemberType=MemberType)
    else:
        subject = request.form.get('subject') or subject_default
        if not recipients:
            flash('No recipients matched the selected filters.', 'warning')
            return redirect(url_for('continuing_edu_admin.manage_events'))
        from flask_mail import Message
        sent = 0
        chunk_size = 50
        from flask import render_template_string
        for i in range(0, len(recipients), chunk_size):
            chunk = recipients[i:i+chunk_size]
            try:
                html_body = render_template_string(email_html_tpl, event=event, link=link)
                msg = Message(subject=subject, recipients=chunk)
                msg.body = f"New event: {event.title_en or event.title_th}\n{link}"
                msg.html = html_body
                mail.send(msg)
                sent += len(chunk)
            except Exception as e:
                flash(f'Error sending to some recipients: {e}', 'danger')
                break
        flash(f'Notification sent to {sent} subscribers.', 'success')
        return redirect(url_for('continuing_edu_admin.manage_events'))


# -----------------------------
# Admin Payments Review
# -----------------------------
@admin_bp.route('/payments')
def payments_index():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = RegisterPayment.query
    if status:
        # Prefer code match, fallback to name_en for backward compatibility
        st = RegisterPaymentStatus.query.filter_by(register_payment_status_code=status).first()
        if not st:
            st = RegisterPaymentStatus.query.filter_by(name_en=status).first()
        if st:
            query = query.filter_by(payment_status_id=st.id)
    if q:
        like = f"%{q}%"
        query = query.join(Member, RegisterPayment.member).join(EventEntity, RegisterPayment.event_entity).filter(
            (Member.username.ilike(like)) | (Member.email.ilike(like)) | (EventEntity.title_en.ilike(like))
        )
    # Date range filter
    from datetime import datetime, timedelta
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(RegisterPayment.payment_date >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            query = query.filter(RegisterPayment.payment_date <= end_dt)
        except ValueError:
            pass

    pagination = query.order_by(RegisterPayment.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    payments = pagination.items
    statuses = RegisterPaymentStatus.query.order_by(RegisterPaymentStatus.name_en.asc()).all()
    # Totals summary
    total_amount = sum([p.payment_amount or 0 for p in payments])
    total_count = len(payments)
    status_counts = {}
    for p in payments:
        key = (p.payment_status_ref.name_en if p.payment_status_ref else 'N/A')
        status_counts[key] = status_counts.get(key, 0) + 1
    return render_template(
        'continueing_edu/admin/payments.html',
        payments=payments,
        statuses=statuses,
        current_status=status,
        q=q,
        start_date=start_date,
        end_date=end_date,
        pagination=pagination,
        per_page=per_page,
        total_amount=total_amount,
        total_count=total_count,
        status_counts=status_counts,
        logged_in_admin=admin,
    )


@admin_bp.route('/payments/<int:payment_id>/receipt')
def payment_receipt(payment_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    pay = RegisterPayment.query.get_or_404(payment_id)
    rc = pay.receipt
    if not rc:
        flash('No receipt issued for this payment.', 'warning')
        return redirect(url_for('continuing_edu_admin.payments_index'))
    member = pay.member
    return render_template('continueing_edu/receipt.html', receipt=rc, payment=pay, member=member, texts={}, current_lang='en')


def _set_payment_status(pay: RegisterPayment, status_en: str, staff_id: int):
    # status_en now treated as code; fallback to name_en
    st = RegisterPaymentStatus.query.filter_by(register_payment_status_code=status_en).first()
    if not st:
        st = RegisterPaymentStatus.query.filter_by(name_en=status_en).first()
    from datetime import datetime
    if st:
        pay.payment_status_id = st.id
    pay.approved_by_staff_id = staff_id
    pay.approval_date = datetime.utcnow()
    db.session.add(pay)
    # Auto-issue receipt on approval
    if status_en == 'approved' and not pay.receipt:
        number = f"RCPT-{datetime.utcnow().strftime('%Y%m%d')}-{pay.id}"
        receipt = RegisterPaymentReceipt(register_payment_id=pay.id, receipt_number=number, issued_by_staff_id=staff_id)
        db.session.add(receipt)
    db.session.commit()


@admin_bp.route('/payments/<int:payment_id>/approve', methods=['POST'])
def payment_approve(payment_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    pay = RegisterPayment.query.get_or_404(payment_id)
    _set_payment_status(pay, 'approved', admin.id)
    flash('Payment approved.', 'success')
    return redirect(url_for('continuing_edu_admin.payments_index'))


@admin_bp.route('/payments/<int:payment_id>/reject', methods=['POST'])
def payment_reject(payment_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    pay = RegisterPayment.query.get_or_404(payment_id)
    _set_payment_status(pay, 'rejected', admin.id)
    flash('Payment rejected.', 'warning')
    return redirect(url_for('continuing_edu_admin.payments_index'))


@admin_bp.route('/payments/export')
def payments_export_csv():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    from datetime import datetime, timedelta
    import csv
    from io import StringIO
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    query = RegisterPayment.query
    if status:
        st = RegisterPaymentStatus.query.filter_by(name_en=status).first()
        if st:
            query = query.filter_by(payment_status_id=st.id)
    if q:
        like = f"%{q}%"
        query = query.join(Member, RegisterPayment.member).join(EventEntity, RegisterPayment.event_entity).filter(
            (Member.username.ilike(like)) | (Member.email.ilike(like)) | (EventEntity.title_en.ilike(like))
        )
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(RegisterPayment.payment_date >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            query = query.filter(RegisterPayment.payment_date <= end_dt)
        except ValueError:
            pass
    rows = query.order_by(RegisterPayment.id.desc()).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Member','Email','Event','Amount','Status','Payment Date','Proof URL','Receipt Number'])
    for p in rows:
        writer.writerow([
            p.id,
            p.member.username if p.member else '',
            p.member.email if p.member else '',
            p.event_entity.title_en if p.event_entity else '',
            p.payment_amount or 0,
            p.payment_status_ref.name_en if p.payment_status_ref else '',
            p.payment_date,
            p.payment_proof_url or '',
            p.receipt.receipt_number if p.receipt else '',
        ])
    from flask import make_response
    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename="payments_export.csv"'
    return resp


@admin_bp.route('/bootstrap_defaults')
def bootstrap_defaults():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    created = []
    # Seed RegisterPaymentStatus values
    for name_en, name_th, badge in [
        ('pending', 'รอดำเนินการ', 'is-light'),
        ('submitted', 'ส่งหลักฐานแล้ว', 'is-info'),
        ('approved', 'อนุมัติแล้ว', 'is-success'),
        ('rejected', 'ปฏิเสธ', 'is-danger'),
    ]:
        s = RegisterPaymentStatus.query.filter_by(name_en=name_en).first()
        if not s:
            s = RegisterPaymentStatus(name_en=name_en, name_th=name_th, css_badge=badge,
                                      register_payment_status_code=name_en)
            db.session.add(s)
            created.append(f'RegisterPaymentStatus:{name_en}')
        elif not s.register_payment_status_code:
            s.register_payment_status_code = name_en
            db.session.add(s)
    # Seed RegistrationStatus values
    for name_en, name_th, badge in [
        ('registered', 'ลงทะเบียนแล้ว', 'is-info'),
        ('cancelled', 'ยกเลิก', 'is-light'),
    ]:
        s = RegistrationStatus.query.filter_by(name_en=name_en).first()
        if not s:
            s = RegistrationStatus(name_en=name_en, name_th=name_th, css_badge=badge,
                                   registration_status_code=name_en)
            db.session.add(s)
            created.append(f'RegistrationStatus:{name_en}')
        elif not s.registration_status_code:
            s.registration_status_code = name_en
            db.session.add(s)
    # Seed MemberCertificateStatus values
    for name_en, name_th, badge in [
        ('issued', 'ออกแล้ว', 'is-success'),
        ('not_applicable', 'ไม่เกี่ยวข้อง', 'is-light'),
        ('pending', 'รอดำเนินการ', 'is-info'),
    ]:
        if not MemberCertificateStatus.query.filter_by(name_en=name_en).first():
            s = MemberCertificateStatus(name_en=name_en, name_th=name_th, css_badge=badge)
            db.session.add(s)
            created.append(f'MemberCertificateStatus:{name_en}')
    db.session.commit()
    flash('Bootstrapped defaults: ' + (', '.join(created) if created else 'nothing to add'), 'success')
    return redirect(url_for('continuing_edu_admin.dashboard'))


# -----------------------------
# General Info Tab Handlers
# -----------------------------
@admin_bp.route('/events/<int:event_id>/update_general', methods=['POST'])
def update_event_general(event_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    event = EventEntity.query.get_or_404(event_id)

    # Basic fields; extend as needed
    title_en = request.form.get('title_en')
    if not title_en:
        flash('Title (EN) is required.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='general'))
    event.title_en = title_en
    event.title_th = request.form.get('title_th') or event.title_th
    event.description_en = request.form.get('description_en')
    event.description_th = request.form.get('description_th')
    event.location_en = request.form.get('location_en')
    event.location_th = request.form.get('location_th')
    event.duration_en = request.form.get('duration_en')
    event.duration_th = request.form.get('duration_th')
    event.format_en = request.form.get('format_en')
    event.format_th = request.form.get('format_th')
    # Handle image uploads or manual URLs
    poster_url_input = request.form.get('poster_image_url')
    cover_url_input = request.form.get('cover_image_url')
    poster_file = request.files.get('poster_image_file')
    cover_file = request.files.get('cover_image_file')

    import time
    from werkzeug.utils import secure_filename

    # Upload poster image if provided
    # Lazy import to avoid circular imports at module import time
    from app.main import allowed_file, s3, S3_BUCKET_NAME
    if poster_file and allowed_file(poster_file.filename):
        filename = secure_filename(poster_file.filename)
        ext = filename.rsplit('.', 1)[-1].lower()
        key = f"continuing_edu/events/{event.id}/poster_{int(time.time())}.{ext}"
        file_data = poster_file.read()
        content_type = poster_file.mimetype or 'application/octet-stream'
        s3.put_object(Bucket=S3_BUCKET_NAME, Key=key, Body=file_data, ContentType=content_type)
        event.poster_image_url = key
    elif poster_url_input is not None:
        event.poster_image_url = poster_url_input or None

    # Upload cover image if provided
    if cover_file and allowed_file(cover_file.filename):
        filename = secure_filename(cover_file.filename)
        ext = filename.rsplit('.', 1)[-1].lower()
        key = f"continuing_edu/events/{event.id}/cover_{int(time.time())}.{ext}"
        file_data = cover_file.read()
        content_type = cover_file.mimetype or 'application/octet-stream'
        s3.put_object(Bucket=S3_BUCKET_NAME, Key=key, Body=file_data, ContentType=content_type)
        event.cover_image_url = key
    elif cover_url_input is not None:
        event.cover_image_url = cover_url_input or None
    event.certificate_name_en = request.form.get('certificate_name_en')
    event.certificate_name_th = request.form.get('certificate_name_th')
    ce_val = request.form.get('continue_education_score')
    if ce_val is not None and ce_val != '':
        try:
            ce_num = float(ce_val)
            if ce_num < 0 or ce_num > 1000:
                raise ValueError('out_of_range')
            event.continue_education_score = ce_num
        except Exception:
            flash('CE Score must be a number between 0 and 1000.', 'danger')
            return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='general'))

    # Early bird period
    eb_start = request.form.get('early_bird_start')
    eb_end = request.form.get('early_bird_end')
    from_date = _parse_dt(eb_start) if eb_start else None
    to_date = _parse_dt(eb_end) if eb_end else None
    if from_date and to_date and to_date <= from_date:
        flash('Early bird end must be after start.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='general'))
    event.early_bird_start = from_date
    event.early_bird_end = to_date

    db.session.add(event)
    db.session.commit()
    flash('General information updated.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='general'))


# -----------------------------
# Speakers Tab Handlers
# -----------------------------
@admin_bp.route('/events/<int:event_id>/speakers/add', methods=['POST'])
def add_event_speaker(event_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    event = EventEntity.query.get_or_404(event_id)

    required = ['title_en','title_th','name_th','name_en','email','phone','institution_th','institution_en']
    missing = [f for f in required if not (request.form.get(f) and request.form.get(f).strip())]
    if missing:
        flash('Missing required speaker fields: ' + ', '.join(missing), 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))

    sp = EventSpeaker(
        event_entity_id=event.id,
        title_en=request.form.get('title_en', ''),
        title_th=request.form.get('title_th', ''),
        name_th=request.form.get('name_th', ''),
        name_en=request.form.get('name_en', ''),
        email=request.form.get('email', ''),
        phone=request.form.get('phone', ''),
        position_th=request.form.get('position_th'),
        position_en=request.form.get('position_en'),
        institution_th=request.form.get('institution_th', ''),
        institution_en=request.form.get('institution_en', ''),
        image_url=request.form.get('image_url'),
        bio_th=request.form.get('bio_th'),
        bio_en=request.form.get('bio_en'),
    )
    db.session.add(sp)
    db.session.commit()
    flash('Speaker added.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='speakers'))


@admin_bp.route('/events/<int:event_id>/speakers/attach', methods=['POST'])
def attach_existing_speaker(event_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    src_id = request.form.get('speaker_id')
    if not src_id:
        flash('Please select a speaker to attach.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))
    src = SpeakerProfile.query.get(src_id)
    if not src:
        flash('Speaker not found.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))

    # Prevent duplicate by email within the same event
    dup = EventSpeaker.query.filter_by(event_entity_id=event_id, email=src.email).first()
    if dup:
        flash('This speaker already exists for the event.', 'warning')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))

    new_sp = EventSpeaker(
        event_entity_id=event_id,
        title_en=src.title_en,
        title_th=src.title_th,
        name_th=src.name_th,
        name_en=src.name_en,
        email=src.email,
        phone=src.phone,
        position_th=src.position_th,
        position_en=src.position_en,
        institution_th=src.institution_th,
        institution_en=src.institution_en,
        image_url=src.image_url,
        bio_th=src.bio_th,
        bio_en=src.bio_en,
    )
    db.session.add(new_sp)
    db.session.commit()
    flash('Speaker attached to event.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))


# -----------------------------
# Admin SpeakerProfile Management
# -----------------------------
@admin_bp.route('/speakers')
def speakers_index():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    q = request.args.get('q', '').strip()
    query = SpeakerProfile.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (SpeakerProfile.name_en.ilike(like)) |
            (SpeakerProfile.name_th.ilike(like)) |
            (SpeakerProfile.email.ilike(like)) |
            (SpeakerProfile.institution_en.ilike(like)) |
            (SpeakerProfile.institution_th.ilike(like))
        )
    profiles = query.order_by(SpeakerProfile.name_en.asc()).all()
    return render_template('continueing_edu/admin/speakers_list.html', profiles=profiles, q=q, logged_in_admin=admin)


@admin_bp.route('/speakers/<int:profile_id>')
def speakers_view(profile_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    sp = SpeakerProfile.query.get_or_404(profile_id)
    return render_template('continueing_edu/admin/speakers_profile.html', profile=sp, logged_in_admin=admin)


@admin_bp.route('/speakers/new', methods=['GET', 'POST'])
def speakers_new():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    if request.method == 'POST':
        required = ['title_en','title_th','name_en','name_th','email','institution_en','institution_th']
        missing = [f for f in required if not (request.form.get(f) and request.form.get(f).strip())]
        if missing:
            flash('Missing required fields: ' + ', '.join(missing), 'danger')
            return render_template('continueing_edu/admin/speakers_form.html', mode='new', data=request.form, logged_in_admin=admin)
        if SpeakerProfile.query.filter_by(email=request.form.get('email')).first():
            flash('Email already exists in speaker profiles.', 'danger')
            return render_template('continueing_edu/admin/speakers_form.html', mode='new', data=request.form, logged_in_admin=admin)

        sp = SpeakerProfile(
            title_en=request.form.get('title_en'),
            title_th=request.form.get('title_th'),
            name_en=request.form.get('name_en'),
            name_th=request.form.get('name_th'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            position_en=request.form.get('position_en'),
            position_th=request.form.get('position_th'),
            institution_en=request.form.get('institution_en'),
            institution_th=request.form.get('institution_th'),
            image_url=request.form.get('image_url'),
            bio_en=request.form.get('bio_en'),
            bio_th=request.form.get('bio_th'),
            is_active=True,
        )
        db.session.add(sp)
        db.session.commit()
        flash('Speaker profile created.', 'success')
        return redirect(url_for('continuing_edu_admin.speakers_index'))

    return render_template('continueing_edu/admin/speakers_form.html', mode='new', data=None, logged_in_admin=admin)


@admin_bp.route('/speakers/<int:profile_id>/edit', methods=['GET', 'POST'])
def speakers_edit(profile_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    sp = SpeakerProfile.query.get_or_404(profile_id)
    if request.method == 'POST':
        # Basic validation
        email = request.form.get('email')
        if not email:
            flash('Email is required.', 'danger')
            return render_template('continueing_edu/admin/speakers_form.html', mode='edit', data=sp, logged_in_admin=admin)
        exists = SpeakerProfile.query.filter(SpeakerProfile.email == email, SpeakerProfile.id != sp.id).first()
        if exists:
            flash('Another profile already uses this email.', 'danger')
            return render_template('continueing_edu/admin/speakers_form.html', mode='edit', data=sp, logged_in_admin=admin)

        # Update fields
        for field in ['title_en','title_th','name_en','name_th','email','phone','position_en','position_th','institution_en','institution_th','image_url','bio_en','bio_th']:
            setattr(sp, field, request.form.get(field))
        sp.is_active = bool(request.form.get('is_active'))
        db.session.add(sp)
        db.session.commit()
        flash('Speaker profile updated.', 'success')
        return redirect(url_for('continuing_edu_admin.speakers_index'))

    return render_template('continueing_edu/admin/speakers_form.html', mode='edit', data=sp, logged_in_admin=admin)


@admin_bp.route('/speakers/<int:profile_id>/delete', methods=['POST'])
def speakers_delete(profile_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    sp = SpeakerProfile.query.get_or_404(profile_id)
    db.session.delete(sp)
    db.session.commit()
    flash('Speaker profile deleted.', 'success')
    return redirect(url_for('continuing_edu_admin.speakers_index'))


@admin_bp.route('/events/<int:event_id>/speakers/<int:speaker_id>/update', methods=['POST'])
def update_event_speaker(event_id, speaker_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    sp = EventSpeaker.query.filter_by(id=speaker_id, event_entity_id=event_id).first_or_404()
    for field in [
        'title_en','title_th','name_th','name_en','email','phone','position_th','position_en',
        'institution_th','institution_en','image_url','bio_th','bio_en']:
        if field in request.form:
            setattr(sp, field, request.form.get(field))
    db.session.add(sp)
    db.session.commit()
    flash('Speaker updated.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))


@admin_bp.route('/events/<int:event_id>/speakers/<int:speaker_id>/delete', methods=['POST'])
def delete_event_speaker(event_id, speaker_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    sp = EventSpeaker.query.filter_by(id=speaker_id, event_entity_id=event_id).first_or_404()
    db.session.delete(sp)
    db.session.commit()
    flash('Speaker deleted.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='speakers'))


# -----------------------------
# Agenda Tab Handlers
# -----------------------------
def _parse_dt(val):
    # Expect input type datetime-local: 'YYYY-MM-DDTHH:MM'
    if not val:
        return None
    try:
        return datetime.datetime.strptime(val, '%Y-%m-%dT%H:%M')
    except Exception:
        return None


@admin_bp.route('/events/<int:event_id>/agendas/add', methods=['POST'])
def add_event_agenda(event_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    event = EventEntity.query.get_or_404(event_id)
    title_en = request.form.get('title_en', '')
    title_th = request.form.get('title_th', '')
    st = _parse_dt(request.form.get('start_time'))
    et = _parse_dt(request.form.get('end_time'))
    if not title_en or not title_th or not st or not et:
        flash('Agenda title and start/end time are required.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='agenda'))
    if et <= st:
        flash('Agenda end time must be after start time.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='agenda'))

    ag = EventAgenda(
        event_entity_id=event.id,
        title_th=title_th,
        title_en=title_en,
        description_th=request.form.get('description_th'),
        description_en=request.form.get('description_en'),
        start_time=st,
        end_time=et,
        order=int(request.form.get('order') or 0),
    )
    db.session.add(ag)
    db.session.commit()
    flash('Agenda item added.', 'success')
    if request.headers.get('HX-Request'):
        return _render_agenda_partial(event.id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='agenda'))


@admin_bp.route('/events/<int:event_id>/agendas/<int:agenda_id>/update', methods=['POST'])
def update_event_agenda(event_id, agenda_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    ag = EventAgenda.query.filter_by(id=agenda_id, event_entity_id=event_id).first_or_404()
    ag.title_th = request.form.get('title_th', ag.title_th)
    ag.title_en = request.form.get('title_en', ag.title_en)
    ag.description_th = request.form.get('description_th')
    ag.description_en = request.form.get('description_en')
    st = _parse_dt(request.form.get('start_time'))
    et = _parse_dt(request.form.get('end_time'))
    # Validate only if provided
    if st and et and et <= st:
        flash('Agenda end time must be after start time.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='agenda'))
    if st:
        ag.start_time = st
    if et:
        ag.end_time = et
    ag.order = int(request.form.get('order') or ag.order or 0)
    db.session.add(ag)
    db.session.commit()
    flash('Agenda item updated.', 'success')
    if request.headers.get('HX-Request'):
        return _render_agenda_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='agenda'))


@admin_bp.route('/events/<int:event_id>/agendas/<int:agenda_id>/delete', methods=['POST'])
def delete_event_agenda(event_id, agenda_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    ag = EventAgenda.query.filter_by(id=agenda_id, event_entity_id=event_id).first_or_404()
    db.session.delete(ag)
    db.session.commit()
    flash('Agenda item deleted.', 'success')
    if request.headers.get('HX-Request'):
        return _render_agenda_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='agenda'))


# -----------------------------
# Materials Tab Handlers
# -----------------------------
@admin_bp.route('/events/<int:event_id>/materials/add', methods=['POST'])
def add_event_material(event_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    event = EventEntity.query.get_or_404(event_id)
    title_en = request.form.get('title_en')
    title_th = request.form.get('title_th')
    url = request.form.get('material_url')
    if not title_en or not title_th or not url:
        flash('Material title (EN/TH) and URL are required.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='materials'))
    mt = EventMaterial(
        event_entity_id=event.id,
        order=int(request.form.get('order') or 0),
        title_th=request.form.get('title_th', ''),
        title_en=request.form.get('title_en', ''),
        description_th=request.form.get('description_th'),
        description_en=request.form.get('description_en'),
        material_url=request.form.get('material_url', ''),
    )
    db.session.add(mt)
    db.session.commit()
    flash('Material added.', 'success')
    if request.headers.get('HX-Request'):
        return _render_materials_partial(event.id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='materials'))


@admin_bp.route('/events/<int:event_id>/materials/<int:material_id>/update', methods=['POST'])
def update_event_material(event_id, material_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    mt = EventMaterial.query.filter_by(id=material_id, event_entity_id=event_id).first_or_404()
    mt.order = int(request.form.get('order') or mt.order or 0)
    mt.title_th = request.form.get('title_th', mt.title_th)
    mt.title_en = request.form.get('title_en', mt.title_en)
    mt.description_th = request.form.get('description_th')
    mt.description_en = request.form.get('description_en')
    mt.material_url = request.form.get('material_url', mt.material_url)
    db.session.add(mt)
    db.session.commit()
    flash('Material updated.', 'success')
    if request.headers.get('HX-Request'):
        return _render_materials_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='materials'))


@admin_bp.route('/events/<int:event_id>/materials/<int:material_id>/delete', methods=['POST'])
def delete_event_material(event_id, material_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    mt = EventMaterial.query.filter_by(id=material_id, event_entity_id=event_id).first_or_404()
    db.session.delete(mt)
    db.session.commit()
    flash('Material deleted.', 'success')
    if request.headers.get('HX-Request'):
        return _render_materials_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='materials'))


# -----------------------------
# Registration Fees Tab Handlers
# -----------------------------
@admin_bp.route('/events/<int:event_id>/fees/add', methods=['POST'])
def add_event_fee(event_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    event = EventEntity.query.get_or_404(event_id)
    member_type_id = request.form.get('member_type_id')
    price = request.form.get('price')
    if not member_type_id or not price:
        flash('Member type and price are required.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='fees'))
    try:
        price_val = float(price)
        if price_val < 0:
            raise ValueError('negative')
    except Exception:
        flash('Price must be a positive number.', 'danger')
        return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='fees'))
    early = request.form.get('early_bird_price')
    early_val = None
    if early is not None and early != '':
        try:
            early_val = float(early)
            if early_val < 0:
                raise ValueError('negative')
        except Exception:
            flash('Early bird price must be a positive number.', 'danger')
            return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='fees'))
    fee = EventRegistrationFee(event_entity_id=event.id, member_type_id=int(member_type_id), price=price_val, early_bird_price=early_val)
    db.session.add(fee)
    try:
        db.session.commit()
        flash('Registration fee added.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding fee: {e}', 'danger')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event.id, tab='fees'))


# -----------------------------
# HTMX Partials and Ordering
# -----------------------------
def _render_agenda_partial(event_id):
    event = EventEntity.query.get_or_404(event_id)
    agendas = EventAgenda.query.filter_by(event_entity_id=event.id).order_by(EventAgenda.order.asc()).all()
    return render_template('continueing_edu/admin/_agenda_list.html', event=event, agendas=agendas)


def _render_materials_partial(event_id):
    event = EventEntity.query.get_or_404(event_id)
    materials = EventMaterial.query.filter_by(event_entity_id=event.id).order_by(EventMaterial.order.asc()).all()
    return render_template('continueing_edu/admin/_materials_list.html', event=event, materials=materials)


@admin_bp.route('/events/<int:event_id>/agendas/partial')
def agendas_partial(event_id):
    return _render_agenda_partial(event_id)


@admin_bp.route('/events/<int:event_id>/materials/partial')
def materials_partial(event_id):
    return _render_materials_partial(event_id)


def _swap_order(queryset, current, direction):
    # direction: 'up' or 'down'
    if direction == 'up':
        neighbor = next((x for x in reversed(queryset) if x.order < current.order), None)
    else:
        neighbor = next((x for x in queryset if x.order > current.order), None)
    if not neighbor:
        return False
    current.order, neighbor.order = neighbor.order, current.order
    db.session.add(current)
    db.session.add(neighbor)
    db.session.commit()
    return True


@admin_bp.route('/events/<int:event_id>/agendas/<int:agenda_id>/move', methods=['POST'])
def move_agenda(event_id, agenda_id):
    direction = request.form.get('direction', 'up')
    agendas = EventAgenda.query.filter_by(event_entity_id=event_id).order_by(EventAgenda.order.asc()).all()
    ag = next((a for a in agendas if a.id == agenda_id), None)
    if ag:
        _swap_order(agendas, ag, direction)
    if request.headers.get('HX-Request'):
        return _render_agenda_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='agenda'))


@admin_bp.route('/events/<int:event_id>/materials/<int:material_id>/move', methods=['POST'])
def move_material(event_id, material_id):
    direction = request.form.get('direction', 'up')
    materials = EventMaterial.query.filter_by(event_entity_id=event_id).order_by(EventMaterial.order.asc()).all()
    mt = next((m for m in materials if m.id == material_id), None)
    if mt:
        _swap_order(materials, mt, direction)
    if request.headers.get('HX-Request'):
        return _render_materials_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='materials'))


@admin_bp.route('/events/<int:event_id>/agendas/reorder', methods=['POST'])
def reorder_agendas(event_id):
    order_ids = []
    if request.is_json:
        data = request.get_json(silent=True) or {}
        order_ids = data.get('order', [])
    else:
        # Accept order[]=id1&order[]=id2 ... or comma-separated 'order'
        order_ids = request.form.getlist('order[]') or request.form.get('order', '').split(',')
    try:
        order_ids = [int(i) for i in order_ids if str(i).strip()]
    except Exception:
        order_ids = []

    agendas = {a.id: a for a in EventAgenda.query.filter_by(event_entity_id=event_id).all()}
    order = 1
    for aid in order_ids:
        ag = agendas.get(aid)
        if ag:
            ag.order = order
            db.session.add(ag)
            order += 1
    db.session.commit()
    if request.headers.get('HX-Request'):
        return _render_agenda_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='agenda'))


@admin_bp.route('/events/<int:event_id>/materials/reorder', methods=['POST'])
def reorder_materials(event_id):
    order_ids = []
    if request.is_json:
        data = request.get_json(silent=True) or {}
        order_ids = data.get('order', [])
    else:
        order_ids = request.form.getlist('order[]') or request.form.get('order', '').split(',')
    try:
        order_ids = [int(i) for i in order_ids if str(i).strip()]
    except Exception:
        order_ids = []

    materials = {m.id: m for m in EventMaterial.query.filter_by(event_entity_id=event_id).all()}
    order = 1
    for mid in order_ids:
        mt = materials.get(mid)
        if mt:
            mt.order = order
            db.session.add(mt)
            order += 1
    db.session.commit()
    if request.headers.get('HX-Request'):
        return _render_materials_partial(event_id)
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='materials'))


@admin_bp.route('/events/<int:event_id>/fees/<int:fee_id>/update', methods=['POST'])
def update_event_fee(event_id, fee_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    fee = EventRegistrationFee.query.filter_by(id=fee_id, event_entity_id=event_id).first_or_404()
    if 'member_type_id' in request.form:
        fee.member_type_id = int(request.form.get('member_type_id'))
    if 'price' in request.form:
        fee.price = float(request.form.get('price'))
    if 'early_bird_price' in request.form:
        ebp = request.form.get('early_bird_price')
        fee.early_bird_price = float(ebp) if ebp not in (None, '') else None
    db.session.add(fee)
    db.session.commit()
    flash('Registration fee updated.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='fees'))


@admin_bp.route('/events/<int:event_id>/fees/<int:fee_id>/delete', methods=['POST'])
def delete_event_fee(event_id, fee_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    fee = EventRegistrationFee.query.filter_by(id=fee_id, event_entity_id=event_id).first_or_404()
    db.session.delete(fee)
    db.session.commit()
    flash('Registration fee deleted.', 'success')
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='fees'))


# -----------------------------
# Staff Roles Tab Handlers
# -----------------------------
def _add_staff_role(model_cls, event_id, staff_id):
    exists = model_cls.query.filter_by(event_entity_id=event_id, staff_id=staff_id).first()
    if not exists:
        db.session.add(model_cls(event_entity_id=event_id, staff_id=staff_id))


def _remove_staff_role(model_cls, role_id, event_id):
    rec = model_cls.query.filter_by(id=role_id, event_entity_id=event_id).first_or_404()
    db.session.delete(rec)


@admin_bp.route('/events/<int:event_id>/roles/update', methods=['POST'])
def update_event_roles(event_id):
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))

    # Add roles from selects (single add per submit)
    to_add_type = request.form.get('role_type')
    staff_id = request.form.get('staff_id')
    if to_add_type and staff_id:
        staff_id = int(staff_id)
        if to_add_type == 'editor':
            _add_staff_role(EventEditor, event_id, staff_id)
        elif to_add_type == 'registration_reviewer':
            _add_staff_role(EventRegistrationReviewer, event_id, staff_id)
        elif to_add_type == 'payment_approver':
            _add_staff_role(EventPaymentApprover, event_id, staff_id)
        elif to_add_type == 'receipt_issuer':
            _add_staff_role(EventReceiptIssuer, event_id, staff_id)
        elif to_add_type == 'certificate_manager':
            _add_staff_role(EventCertificateManager, event_id, staff_id)
        db.session.commit()
        flash('Role assignment updated.', 'success')

    # Handle removals (if present)
    for key, val in request.form.items():
        if key.startswith('remove_role_'):
            parts = val.split(':')  # e.g., 'editor:5'
            if len(parts) == 2:
                role_name, rid = parts[0], int(parts[1])
                if role_name == 'editor':
                    _remove_staff_role(EventEditor, rid, event_id)
                elif role_name == 'registration_reviewer':
                    _remove_staff_role(EventRegistrationReviewer, rid, event_id)
                elif role_name == 'payment_approver':
                    _remove_staff_role(EventPaymentApprover, rid, event_id)
                elif role_name == 'receipt_issuer':
                    _remove_staff_role(EventReceiptIssuer, rid, event_id)
                elif role_name == 'certificate_manager':
                    _remove_staff_role(EventCertificateManager, rid, event_id)
    db.session.commit()
    return redirect(url_for('continuing_edu_admin.edit_event', event_id=event_id, tab='roles'))
