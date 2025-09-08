
from app.staff.models import StaffAccount
from werkzeug.security import check_password_hash
from flask import session

from werkzeug.security import generate_password_hash

from flask import  render_template, request, jsonify, flash, redirect, url_for

from . import ce_bp
from .models import CertificateType, db, Member, EventEntity, EntityCategory
from sqlalchemy import or_, and_
from werkzeug.exceptions import NotFound

from app.main import mail
from flask_mail import Message

from . import translations as tr  # Import translations from local package

current_lang = 'en'  # This should be dynamically set based on user preference or request


def get_current_user():
    user_id = session.get('member_id')
    if user_id:
        return Member.query.filter_by(id=user_id).first()
    return None

# --- Member Login ---
@ce_bp.route('/login', methods=['GET', 'POST'])
def login():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        member = Member.query.filter_by(username=username).first()
        if member and check_password_hash(member.password_hash, password):
            session['member_id'] = member.id
            # session['username'] = member.username

            user = get_current_user()  # Assuming 'member' is the user object you want to pass
            flash(texts.get('login_success', 'เข้าสู่ระบบสำเร็จ!' if lang == 'th' else 'Login successful!'), 'success')
            return redirect(url_for('continuing_edu.index', lang=lang, logged_in_user=user))
        else:
            flash(texts.get('login_error', 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง' if lang == 'th' else 'Invalid username or password.'), 'danger')
    return render_template('continueing_edu/login.html', texts=texts, current_lang=lang, logged_in_user=get_current_user())





# --- Member callback ---
@ce_bp.route('/callback')
def callback():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    flash('เข้าสู่ระบบสำเร็จ' if lang == 'th' else 'Logged in successfully.', 'success')
    return redirect(url_for('continuing_edu.index', lang=lang, texts=texts))


# --- Member Logout ---
@ce_bp.route('/logout')
def logout():
    lang = request.args.get('lang', 'en')
    session.pop('member_id', None)
    session.pop('username', None)
    flash('ออกจากระบบสำเร็จ' if lang == 'th' else 'Logged out successfully.', 'success')
    return redirect(url_for('continuing_edu.index', lang=lang))
# --- Member Registration ---
@ce_bp.route('/register', methods=['GET', 'POST'])
def register():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        accept_privacy = request.form.get('accept_privacy')
        accept_terms = request.form.get('accept_terms')
        accept_news = request.form.get('accept_news')
        not_bot = request.form.get('not_bot')

        # Basic required fields
        if not username or not password:
            flash(texts.get('register_error_required',  'Username and password required.' if lang == 'en' else 'ชื่อผู้ใช้และรหัสผ่านจำเป็นต้องกรอก'), 'danger')

        # Confirm password
        elif password != confirm_password:

            flash( 'รหัสผ่านและยืนยันรหัสผ่านไม่ตรงกัน' if lang == 'th' else 'Passwords do not match.', 'danger')
        # Privacy policy
        elif not accept_privacy:
            flash('กรุณายอมรับนโยบายความเป็นส่วนตัว' if lang == 'th' else 'Please accept the privacy policy.', 'danger')
        # Terms of service
        elif not accept_terms:
            flash('กรุณายอมรับข้อกำหนดและเงื่อนไข' if lang == 'th' else 'Please accept the terms and conditions.', 'danger')
        # Anti-bot
        elif not not_bot or not_bot.strip().lower() != 'มนุษย์' and not_bot.strip().lower() != 'human':
            flash('กรุณายืนยันว่าคุณไม่ใช่บอท โดยพิมพ์คำว่า "มนุษย์" หรือ "human"' if lang == 'th' else 'Please confirm you are not a bot by typing "มนุษย์" or "human".', 'danger')
        else:
            from .models import Member
            import random
            if Member.query.filter_by(username=username).first():
                flash(texts.get('register_error_exists', 'Username already exists.'), 'danger')
            elif Member.query.filter_by(email=email).first():
                # Email already registered, show comeback options
                return render_template('continueing_edu/email_already_registered.html', email=email, current_lang=lang, texts=texts)
            else:
                member = Member(
                    username=username,
                    email=email,
                    password_hash=generate_password_hash(password)
                )
                db.session.add(member)
                db.session.commit()
                # Generate OTP and send email
                otp_code = '{:06d}'.format(random.randint(0, 999999))
                session['otp_code'] = otp_code
                session['otp_username'] = username
                session['otp_email'] = email
                try:

                    send_mail([email], 'รหัส OTP สำหรับการลงทะเบียนของคุณ' if lang == 'th' else 'Your Registration OTP Code', f'รหัส OTP ของคุณคือ: {otp_code}' if lang == 'th' else f'Your OTP code is: {otp_code}')
                except Exception as e:
                    flash(f'ไม่สามารถส่งอีเมล OTP ได้: {e}' if lang == 'th' else f'Unable to send OTP email: {e}', 'danger')
                return render_template('continueing_edu/otp_verify.html', username=username, current_lang=lang, texts=texts)
    return render_template('continueing_edu/register.html', texts=texts, current_lang=lang)




# --- Comeback options for already registered email ---
@ce_bp.route('/comeback_options', methods=['POST'])
def comeback_options():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    email = request.form.get('email')
    action = request.form.get('action')
    if action == 'otp':
        # Send OTP to email for verification (reuse OTP logic or implement as needed)
        from .models import Member
        import random
        member = Member.query.filter_by(email=email).first()
        if member:
            otp_code = '{:06d}'.format(random.randint(0, 999999))
            session['otp_code'] = otp_code
            session['otp_username'] = member.username
            session['otp_email'] = email
            try:
                send_mail([email], 'รหัส OTP สำหรับการเข้าสู่ระบบของคุณ' if lang == 'th' else 'Your Login OTP Code', f'รหัส OTP ของคุณคือ: {otp_code}' if lang == 'th' else f'Your OTP code is: {otp_code}')
            except Exception as e:
                flash(f'ไม่สามารถส่งอีเมล OTP ได้: {e}' if lang == 'th' else f'Unable to send OTP email: {e}', 'danger')
            return render_template('continueing_edu/otp_verify.html',  username=member.username, current_lang=lang, texts=texts)
        else:
            flash('ไม่พบอีเมลนี้ในระบบ' if lang == 'th' else 'Email not found in the system', 'danger')
            return redirect(url_for('continuing_edu.register', texts=texts, lang=lang))
    elif action == 'forgot':
        # Redirect to forgot password page (implement as needed)
        return redirect(url_for('continuing_edu.login', texts=texts, lang=lang))
    else:
        flash('ไม่สามารถดำเนินการได้' if lang == 'th' else 'Unable to process request', 'danger')
        return redirect(url_for('continuing_edu.register', texts=texts, lang=lang))


# --- OTP Verification ---
@ce_bp.route('/otp_verify', methods=['POST'])
def otp_verify():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    input_otp = request.form.get('otp_code')
    username = request.form.get('username')
    otp_code = session.get('otp_code')
    otp_username = session.get('otp_username')
    if not otp_code or not otp_username or username != otp_username:
        flash('เซสชัน OTP หมดอายุหรือไม่ถูกต้อง กรุณาลงทะเบียนอีกครั้ง' if lang == 'th' else 'OTP session expired or invalid. Please register again.', 'danger')
        return redirect(url_for('continuing_edu.register', lang=lang))
    if input_otp == otp_code:
        # Mark user as verified (add a field in Member if needed)
        from .models import Member
        member = Member.query.filter_by(username=username).first()
        if member:
            member.is_verified = True  # You must add this field in your model/migration
            db.session.commit()
        session.pop('otp_code', None)
        session.pop('otp_username', None)
        session.pop('otp_email', None)
        flash('ยืนยัน OTP สำเร็จ! สมัครสมาชิกสมบูรณ์' if lang == 'th' else 'OTP verification successful! Registration complete', 'success')
        return redirect(url_for('continuing_edu.login', lang=lang, texts=texts))
    else:
        flash('OTP ไม่ถูกต้อง กรุณาลองใหม่' if lang == 'th' else 'Invalid OTP. Please try again.', 'danger')
        return render_template('continueing_edu/otp_verify.html', username=username, current_lang=lang, texts=texts)



def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


@ce_bp.route('/why_register')
def why_register():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    return render_template('continueing_edu/why_register.html', texts=texts, current_lang=lang)


@ce_bp.route('/all-events')
def all_events():
    """Landing page: List all event entities."""
    events = EventEntity.query.order_by(EventEntity.created_at.desc()).all()
    texts = tr[current_lang]
    return render_template('continueing_edu/all_events.html', events=events, active_menu='All Events', texts=texts, lang=current_lang)


@ce_bp.route('/', endpoint='index', methods=['GET'])
def dashboard():
    """Landing page: List all event entities (replaces course/webinar lists)."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    events = EventEntity.query.order_by(EventEntity.created_at.desc()).all()
    if not events:
        # Add sample data if no events exist
        sample1 = EventEntity(
            event_type='course',
            title_en='Sample Course',
            title_th='ตัวอย่างหลักสูตร',
            description_en='This is a sample course for demonstration.',
            description_th='นี่คือตัวอย่างหลักสูตรสำหรับการสาธิต',
            course_code='SAMP101',
            duration_en='2 days',
            format_en='Online',
            certification_en='Certificate of Completion',
            location_en='Online',
            speaker_en='Dr. John Doe',
            speaker_th='ดร. จอห์น โด',
            agenda_en='Introduction to Sample Course',
            agenda_th='บทนำสู่หลักสูตรตัวอย่าง',
            prerequisites_en='None',
            prerequisites_th='ไม่มี',
            additional_info_en='This is a sample course for demonstration purposes.',
            additional_info_th='นี่คือตัวอย่างหลักสูตรสำหรับวัตถุประสงค์ในการสาธิต',
            registration_fee= {'amount': 100.0, 'currency': 'USD'},
            duration= {'amount': 2, 'unit': 'days'},
            format= {'en': 'Online', 'th': 'ออนไลน์'},

        )
        sample2 = EventEntity(
            event_type='webinar',
            title_en='Sample Webinar',
            title_th='ตัวอย่างสัมมนา',
            description_en='This is a sample webinar for demonstration.',
            description_th='นี่คือตัวอย่างสัมมนาสำหรับการสาธิต',
            location_en='Online',
            speaker_en='Dr. John Doe',
            speaker_th='ดร. จอห์น โด',
            agenda_en='Introduction to Sample Webinar',
            agenda_th='บทนำสู่การสัมมนาตัวอย่าง',
            duration_en='1 hour',
            duration_th='1 ชั่วโมง',
            location_th='ออนไลน์',

        )
        db.session.add_all([sample1, sample2])
        db.session.commit()
        events = EventEntity.query.order_by(EventEntity.created_at.desc()).all()
    return render_template('continueing_edu/index.html', events=events, active_menu='All Events', texts=texts, current_lang=lang)


@ce_bp.route('/courses')
def courses_list():
    """Renders the courses list page."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    courses = EventEntity.query.filter_by(event_type='course').all()
    return render_template('continueing_edu/courses.html',
                           active_menu='Courses List',
                           courses=courses,
                           texts=texts,
                           current_lang=lang)


@ce_bp.route('/webinars')
def webinars_list():
    """Renders the webinars list page."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    webinars = EventEntity.query.filter_by(event_type='webinar').all()
    return render_template('continueing_edu/webinars.html',
                           active_menu='Webinar List',
                           webinars=webinars,
                           texts=texts,
                           current_lang=lang)

@ce_bp.route('/course_detail/<int:course_id>')
def course_detail(course_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    course = EventEntity.query.filter_by(id=course_id, event_type='course').first_or_404()
    return render_template('continueing_edu/course_detail.html', course=course, texts=texts, current_lang=lang)

@ce_bp.route('/webinar_detail/<int:webinar_id>')
def webinar_detail(webinar_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    webinar = EventEntity.query.filter_by(id=webinar_id, event_type='webinar').first_or_404()
    return render_template('continueing_edu/webinar_detail.html', webinar=webinar, texts=texts, current_lang=lang)

@ce_bp.route('/members')
def members_list():
    """Renders the members list page."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    members = Member.query.all()
    return render_template('continueing_edu/members.html',
                           active_menu='Members',
                           members=members,
                           texts=texts,
                           current_lang=lang)


@ce_bp.route('/instructors_speakers')
def instructors_speakers():
    """Renders the instructors and speakers list page."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    speakers = InstructorSpeaker.query.all()
    return render_template('continueing_edu/instructors_speakers.html',
                           active_menu='Instructors & Speaker',
                           speakers=speakers,
                           texts=texts,
                           current_lang=lang)


@ce_bp.route('/registrations')
def registrations_list():
    """Renders the registrations list page."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    all_events = EventEntity.query.all()
    return render_template('continueing_edu/registrations.html',
                           active_menu='Registrations',
                           all_events=all_events,
                           texts=texts,
                           current_lang=lang)


@ce_bp.route('/payments')
def payments_list():
    """Renders the payments list page."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    all_events = EventEntity.query.all()
    all_payment_statuses = PaymentStatus.query.all()
    return render_template('continueing_edu/payments.html',
                           active_menu='Payments',
                           all_events=all_events,
                           texts=texts,
                           current_lang=lang,
                           all_payment_statuses=all_payment_statuses)


@ce_bp.route('/event_management')
def events_management():
    
    """Renders the event management page with a table that can be filtered dynamically."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    return render_template('continueing_edu/event_management.html',
                           active_menu='Event Management',
                           texts=texts,
                           current_lang=lang)


@ce_bp.route('/api/get_events_table_data', methods=['GET'])
def get_events_table_data():
    """API endpoint to get paginated and filtered event data for HTMX."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    event_type_filter = request.args.get('event_type_filter', '')
    per_page = 10

    # Build the query
    query = EventEntity.query

    # Apply type filter if provided
    if event_type_filter:
        query = query.filter_by(event_type=event_type_filter)

    # Apply search filter if provided
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(or_(
            EventEntity.title_en.like(search_pattern),
            EventEntity.title_th.like(search_pattern),
            EventEntity.course_code.like(search_pattern),
            EventEntity.location_en.like(search_pattern),
            EventEntity.speaker_en.like(search_pattern)
        ))

    # Paginate the results
    pagination = query.order_by(EventEntity.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('continueing_edu/event_table_partial.html',
                           events=pagination.items,
                           pagination=pagination,
                           texts=texts,
                           current_lang=lang)


@ce_bp.route('/event/add', methods=['GET', 'POST'])
def add_event():
    """Handles adding a new event (course or webinar)."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])

    if request.method == 'POST':
        event_type = request.form.get('event_type')

        # Create a dictionary of form data
        data = {
            'event_type': event_type,
            'title_en': request.form.get('title_en'),
            'title_th': request.form.get('title_th'),
            'description_en': request.form.get('description_en'),
            'description_th': request.form.get('description_th'),
            'staff_id': request.form.get('staff_id'),
            'category_id': request.form.get('category_id'),
            'certificate_type_id': request.form.get('certificate_type_id'),
            'creating_institution': request.form.get('creating_institution'),
            'department_or_unit': request.form.get('department_or_unit'),
            'continue_education_score': request.form.get('continue_education_score', type=float)
        }

        if event_type == 'course':
            # Add course-specific fields
            data.update({
                'course_code': request.form.get('course_code'),
                'image_url': request.form.get('image_url'),
                'long_description_en': request.form.get('long_description_en'),
                'long_description_th': request.form.get('long_description_th'),
                'duration_en': request.form.get('duration_en'),
                'duration_th': request.form.get('duration_th'),
                'format_en': request.form.get('format_en'),
                'format_th': request.form.get('format_th'),
                'certification_en': request.form.get('certification_en'),
                'certification_th': request.form.get('certification_th'),
                'location_en': request.form.get('location_en'),
                'location_th': request.form.get('location_th'),
                'degree_en': request.form.get('degree_en'),
                'degree_th': request.form.get('degree_th'),
                'department_owner': request.form.get('department_owner'),
                'created_by': request.form.get('created_by'),
                'certificate_name_th': request.form.get('certificate_name_th'),
                'certificate_name_en': request.form.get('certificate_name_en'),
            })
        elif event_type == 'webinar':
            # Add webinar-specific fields
            data.update({
                'long_description_en': request.form.get('long_description_en'),
                'long_description_th': request.form.get('long_description_th'),
                'date_en': request.form.get('date_en'),
                'date_th': request.form.get('date_th'),
                'time_en': request.form.get('time_en'),
                'time_th': request.form.get('time_th'),
                'speaker_en': request.form.get('speaker_en'),
                'speaker_th': request.form.get('speaker_th'),
                'location_en': request.form.get('location_en'),
                'location_th': request.form.get('location_th'),
                'certificate_name_th': request.form.get('certificate_name_th'),
                'certificate_name_en': request.form.get('certificate_name_en'),
            })

        try:
            new_event = Event(**data)
            db.session.add(new_event)
            db.session.commit()
            flash('Event added successfully!', 'success')
            return redirect(url_for('continueing_edu.events_management'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding event: {e}', 'danger')

    staff_accounts = StaffAccount.query.all()
    categories = request.form.get('category_id') or ""
    certificate_types = CertificateType.query.all()
    return render_template('continueing_edu/event_form.html',
                           active_menu='Event Management',
                           form_title='Add New Event',
                           staff_accounts=staff_accounts,
                           categories=categories,
                           certificate_types=certificate_types,
                           texts=texts,
                           current_lang=lang
                           )


@ce_bp.route('/event/edit/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    """Handles editing an existing EventEntity."""

    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])

    event = EventEntity.query.get_or_404(event_id)
    if request.method == 'POST':
        try:
            EventEntity.title_en = request.form.get('title_en')
            EventEntity.title_th = request.form.get('title_th')
            EventEntity.description_en = request.form.get('description_en')
            EventEntity.description_th = request.form.get('description_th')
            EventEntity.staff_id = request.form.get('staff_id') or None  # Set to None if empty
            EventEntity.category_id = request.form.get('category_id') or None
            EventEntity.certificate_type_id = request.form.get('certificate_type_id') or None
            EventEntity.creating_institution = request.form.get('creating_institution')
            EventEntity.department_or_unit = request.form.get('department_or_unit')
            EventEntity.continue_education_score = request.form.get('continue_education_score', type=float)

            if EventEntity.event_type == 'course':
                EventEntity.course_code = request.form.get('course_code')
                EventEntity.image_url = request.form.get('image_url')
                EventEntity.long_description_en = request.form.get('long_description_en')
                EventEntity.long_description_th = request.form.get('long_description_th')
                EventEntity.duration_en = request.form.get('duration_en')
                EventEntity.duration_th = request.form.get('duration_th')
                EventEntity.format_en = request.form.get('format_en')
                EventEntity.format_th = request.form.get('format_th')
                EventEntity.certification_en = request.form.get('certification_en')
                EventEntity.certification_th = request.form.get('certification_th')
                EventEntity.location_en = request.form.get('location_en')
                EventEntity.location_th = request.form.get('location_th')
                EventEntity.degree_en = request.form.get('degree_en')
                EventEntity.degree_th = request.form.get('degree_th')
                EventEntity.department_owner = request.form.get('department_owner')
                EventEntity.created_by = request.form.get('created_by')
                EventEntity.certificate_name_th = request.form.get('certificate_name_th')
                EventEntity.certificate_name_en = request.form.get('certificate_name_en')
            elif EventEntity.event_type == 'webinar':
                EventEntity.long_description_en = request.form.get('long_description_en')
                EventEntity.long_description_th = request.form.get('long_description_th')
                EventEntity.date_en = request.form.get('date_en')
                EventEntity.date_th = request.form.get('date_th')
                EventEntity.time_en = request.form.get('time_en')
                EventEntity.time_th = request.form.get('time_th')
                EventEntity.speaker_en = request.form.get('speaker_en')
                EventEntity.speaker_th = request.form.get('speaker_th')
                EventEntity.location_en = request.form.get('location_en')
                EventEntity.location_th = request.form.get('location_th')
                EventEntity.certificate_name_th = request.form.get('certificate_name_th')
                EventEntity.certificate_name_en = request.form.get('certificate_name_en')

            db.session.commit()
            flash('Event updated successfully!', 'success')
            return redirect(url_for('continueing_edu.events_management'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating event: {e}', 'danger')

    staff_accounts = StaffAccount.query.all()
    categories = EventEntity.event_type # EventCategory.query.all()
    certificate_types = CertificateType.query.all()
    return render_template('continueing_edu/event_form.html',
                           active_menu='Event Management',
                           form_title=f'Edit Event: {EventEntity.title_en}',
                           event=event,
                           staff_accounts=staff_accounts,
                           categories=categories,
                           certificate_types=certificate_types,
                           texts=texts,
                           current_lang=lang
                           )


@ce_bp.route('/event/delete/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    """Handles deleting an existing EventEntity."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])

    event = EventEntity.query.get_or_404(event_id)
    try:
        db.session.delete(event)
        db.session.commit()
        flash('Event deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting event: {e}', 'danger')
    return redirect(url_for('continueing_edu.events_management', lang=lang))


@ce_bp.route('/api/registrations_data', methods=['GET'])
def get_registrations_data():
    """API endpoint to get paginated and filtered registration data."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    event_id = request.args.get('event_id', type=int)
    search_query = request.args.get('search', '').strip()

    query = Registration.query.join(Member).join(Event).join(Payment, isouter=True)

    if event_id:
        query = query.filter(Registration.event_id == event_id)

    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(or_(
            Member.username.like(search_pattern),
            Member.email.like(search_pattern),
            EventEntity.title_en.like(search_pattern),
            EventEntity.title_th.like(search_pattern)
        ))

    pagination = query.order_by(Registration.registration_date.desc()).paginate(page=page, per_page=per_page,
                                                                                error_out=False)

    registrations_data = []
    for reg in pagination.items:
        payment = reg.payment
        payment_status_name = payment.payment_status_ref.name_en if payment and payment.payment_status_ref else 'N/A'

        # Determine badge color based on payment status
        if payment_status_name == 'Paid':
            payment_badge_css = 'is-success'
        elif payment_status_name == 'Pending':
            payment_badge_css = 'is-warning'
        else:
            payment_badge_css = 'is-light'

        registrations_data.append({
            'id': reg.id,
            'member_username': reg.member.username,
            'member_email': reg.member.email,
            'event_title_en': reg.EventEntity.title_en,
            'event_type': reg.EventEntity.event_type,
            'registration_date': reg.registration_date.strftime('%Y-%m-%d %H:%M:%S'),
            'status_en': reg.registration_status_ref.name_en if reg.registration_status_ref else 'N/A',
            'status_badge_css': reg.registration_status_ref.name_en.lower() if reg.registration_status_ref else 'is-light',
            'payment_status_en': payment_status_name,
            'payment_status_badge_css': payment_badge_css,
            'ce_score': reg.EventEntity.continue_education_score,
            'actions': '...'
        })

    return jsonify({
        'data': registrations_data,
        'total_pages': pagination.pages,
        'current_page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })



@ce_bp.route('/api/payments_data', methods=['GET'])
def get_payments_data():
    """API endpoint to get paginated and filtered payments data."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    event_id = request.args.get('event_id', type=int)
    payment_status_id = request.args.get('payment_status_id', type=int)
    search_query = request.args.get('search', '').strip()

    query = Payment.query.join(Registration).join(Member).join(Event).join(PaymentStatus)

    if event_id:
        query = query.filter(Registration.event_id == event_id)
    if payment_status_id:
        query = query.filter(Payment.payment_status_id == payment_status_id)

    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(or_(
            Member.username.like(search_pattern),
            Member.email.like(search_pattern),
            EventEntity.title_en.like(search_pattern),
            EventEntity.title_th.like(search_pattern),
            Payment.transaction_id.like(search_pattern),
            Payment.receipt_number.like(search_pattern)
        ))

    pagination = query.order_by(Payment.payment_date.desc()).paginate(page=page, per_page=per_page, error_out=False)

    payments_data = []
    for pay in pagination.items:
        payment_status_name = pay.payment_status_ref.name_en

        # Determine badge color based on payment status
        if payment_status_name == 'Paid':
            payment_badge_css = 'is-success'
        elif payment_status_name == 'Pending':
            payment_badge_css = 'is-warning'
        else:
            payment_badge_css = 'is-light'

        payments_data.append({
            'id': pay.id,
            'member_username': pay.registration.member.username,
            'member_email': pay.registration.member.email,
            'event_title_en': pay.registration.EventEntity.title_en,
            'payment_amount': pay.payment_amount,
            'payment_date': pay.payment_date.strftime('%Y-%m-%d %H:%M:%S'),
            'payment_status_en': payment_status_name,
            'payment_status_badge_css': payment_badge_css,
            'transaction_id': pay.transaction_id if pay.transaction_id else 'N/A',
            'receipt_number': pay.receipt_number if pay.receipt_number else 'N/A',
            'receipt_url': pay.receipt_url,
            'approved_by_staff': pay.staff_account.username if pay.staff_account else 'N/A',
            'actions': '...'
        })

    return jsonify({
        'data': payments_data,
        'total_pages': pagination.pages,
        'current_page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })


@ce_bp.route('/event/<int:event_id>')
def event_details(event_id):
    """Renders the detailed page for a specific EventEntity."""
    try:
        event = EventEntity.query.get_or_404(event_id)
        # Check if the event is a course or a webinar
        if EventEntity.event_type == 'course':
            template_name = 'continueing_edu/course_details.html'
        elif EventEntity.event_type == 'webinar':
            template_name = 'continueing_edu/webinar_details.html'
        else:
            # Handle unknown event type
            return "Unknown event type", 404

        return render_template(template_name, active_menu='Event Details', event=event)
    except NotFound:
        flash('Event not found.', 'danger')
        return redirect(url_for('continueing_edu.events_management'))
    

@ce_bp.route('/events' , methods=['GET'])
def admin_events():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    print("Admin Events")
    events = EventEntity.query.order_by(EventEntity.created_at.desc()).all()
    return render_template('continueing_edu/events_list.html', events=events, texts=texts)

@ce_bp.route('/event/add', methods=['GET', 'POST'])
def admin_add_event():
    if request.method == 'POST':
        # TODO: Add form processing logic
        flash('Event added (stub)', 'success')
        return redirect(url_for('continuing_edu.admin_events'))
    return render_template('continueing_edu/event_form.html', form_title='Add Event')

@ce_bp.route('/event/edit/<int:event_id>', methods=['GET', 'POST'])
def admin_edit_event(event_id):
    event = EventEntity.query.get_or_404(event_id)
    if request.method == 'POST':
        # TODO: Add form processing logic
        flash('Event updated (stub)', 'success')
        return redirect(url_for('continuing_edu.admin_events'))
    return render_template('continueing_edu/event_form.html', event=event, form_title='Edit Event')

@ce_bp.route('/event/delete/<int:event_id>', methods=['POST'])
def admin_delete_event(event_id):
    event = EventEntity.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted', 'success')

