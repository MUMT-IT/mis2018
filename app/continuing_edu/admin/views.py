from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired

from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from app.staff.models import StaffAccount
from werkzeug.security import check_password_hash


from app.continuing_edu.models import (
    EventEntity,
    Member,
    RegisterPayment,
    RegisterPaymentStatus,
    RegisterPaymentReceipt,
    MemberRegistration,
    MemberType,
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
from app.main import db

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
        if not RegisterPaymentStatus.query.filter_by(name_en=name_en).first():
            s = RegisterPaymentStatus(name_en=name_en, name_th=name_th, css_badge=badge)
            db.session.add(s)
            created.append(f'RegisterPaymentStatus:{name_en}')
    # Seed RegistrationStatus values
    for name_en, name_th, badge in [
        ('registered', 'ลงทะเบียนแล้ว', 'is-info'),
        ('cancelled', 'ยกเลิก', 'is-light'),
    ]:
        if not RegistrationStatus.query.filter_by(name_en=name_en).first():
            s = RegistrationStatus(name_en=name_en, name_th=name_th, css_badge=badge)
            db.session.add(s)
            created.append(f'RegistrationStatus:{name_en}')
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
    event.poster_image_url = request.form.get('poster_image_url')
    event.cover_image_url = request.form.get('cover_image_url')
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
