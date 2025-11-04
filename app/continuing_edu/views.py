
from app.staff.models import StaffAccount
from werkzeug.security import check_password_hash


from werkzeug.security import generate_password_hash

from flask import  render_template, request, jsonify, flash, redirect, url_for, make_response, session, Response

from . import ce_bp
from .models import (
    CertificateType,
    db,
    Member,
    EventEntity,
    EntityCategory,
    MemberRegistration,
    EventRegistrationFee,
    RegisterPayment,
    RegisterPaymentStatus,
    Organization,
    OrganizationType,
    Occupation,
    MemberAddress,
)
from sqlalchemy import or_, and_, func
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound

from app.main import mail
from flask_mail import Message
try:
    from weasyprint import HTML
except Exception:
    HTML = None

import os, secrets, time
from urllib.parse import urljoin
from requests_oauthlib import OAuth2Session
from datetime import datetime, timezone

from werkzeug.utils import secure_filename
from textwrap import shorten

from . import translations as tr  # Import translations from local package
from .status_utils import get_registration_status, get_certificate_status
from .certificate_utils import issue_certificate, can_issue_certificate

current_lang = 'en'  # This should be dynamically set based on user preference or request


COUNTRY_OPTIONS = [
    {'code': 'TH', 'name': 'Thailand'},
    {'code': 'SG', 'name': 'Singapore'},
    {'code': 'MY', 'name': 'Malaysia'},
    {'code': 'VN', 'name': 'Vietnam'},
    {'code': 'LA', 'name': 'Laos'},
    {'code': 'KH', 'name': 'Cambodia'},
    {'code': 'MM', 'name': 'Myanmar'},
    {'code': 'PH', 'name': 'Philippines'},
    {'code': 'ID', 'name': 'Indonesia'},
    {'code': 'BN', 'name': 'Brunei Darussalam'},
    {'code': 'CN', 'name': 'China'},
    {'code': 'HK', 'name': 'Hong Kong'},
    {'code': 'JP', 'name': 'Japan'},
    {'code': 'KR', 'name': 'South Korea'},
    {'code': 'IN', 'name': 'India'},
    {'code': 'AE', 'name': 'United Arab Emirates'},
    {'code': 'QA', 'name': 'Qatar'},
    {'code': 'SA', 'name': 'Saudi Arabia'},
    {'code': 'AU', 'name': 'Australia'},
    {'code': 'NZ', 'name': 'New Zealand'},
    {'code': 'GB', 'name': 'United Kingdom'},
    {'code': 'US', 'name': 'United States'},
    {'code': 'CA', 'name': 'Canada'},
    {'code': 'DE', 'name': 'Germany'},
    {'code': 'FR', 'name': 'France'},
    {'code': 'CH', 'name': 'Switzerland'},
    {'code': 'SE', 'name': 'Sweden'},
    {'code': 'NO', 'name': 'Norway'},
    {'code': 'FI', 'name': 'Finland'},
]


def _default_address_entries():
    return [
        {
            'type': 'current',
            'type_other': '',
            'label': '',
            'line1': '',
            'line2': '',
            'city': '',
            'state': '',
            'postal': '',
            'country_code': 'TH',
            'country_other': '',
        },
        {
            'type': 'billing',
            'type_other': '',
            'label': '',
            'line1': '',
            'line2': '',
            'city': '',
            'state': '',
            'postal': '',
            'country_code': 'TH',
            'country_other': '',
        },
    ]


def _collect_address_entries_from_form(form):
    if not form:
        return []

    def _safe_list(key):
        return [value.strip() for value in form.getlist(key)]

    address_types = _safe_list('address_type[]')
    address_type_custom = _safe_list('address_type_other[]')
    address_labels = _safe_list('address_label[]')
    line1_list = _safe_list('address_line1[]')
    line2_list = _safe_list('address_line2[]')
    city_list = _safe_list('address_city[]')
    state_list = _safe_list('address_state[]')
    postal_list = _safe_list('address_postal[]')
    country_codes = _safe_list('address_country[]')
    country_other = _safe_list('address_country_other[]')

    max_len = max(
        len(address_types),
        len(address_type_custom),
        len(address_labels),
        len(line1_list),
        len(line2_list),
        len(city_list),
        len(state_list),
        len(postal_list),
        len(country_codes),
        len(country_other),
    ) if form else 0

    entries = []
    for idx in range(max_len):
        entries.append({
            'type': address_types[idx] if idx < len(address_types) else '',
            'type_other': address_type_custom[idx] if idx < len(address_type_custom) else '',
            'label': address_labels[idx] if idx < len(address_labels) else '',
            'line1': line1_list[idx] if idx < len(line1_list) else '',
            'line2': line2_list[idx] if idx < len(line2_list) else '',
            'city': city_list[idx] if idx < len(city_list) else '',
            'state': state_list[idx] if idx < len(state_list) else '',
            'postal': postal_list[idx] if idx < len(postal_list) else '',
            'country_code': country_codes[idx] if idx < len(country_codes) else '',
            'country_other': country_other[idx] if idx < len(country_other) else '',
        })

    return entries


def get_current_user():
    user_id = session.get('member_id')
    if user_id:
        return Member.query.filter_by(id=user_id).first()
    return None


def is_early_bird_active(event: EventEntity):
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)
    if event.early_bird_end and now > event.early_bird_end:
        return False
    if event.early_bird_start and now < event.early_bird_start:
        return False
    return bool(event.early_bird_start or event.early_bird_end)


def _price_for_member(event: EventEntity, member: Member):
    fee = None
    if member and member.member_type_id:
        fee = EventRegistrationFee.query.filter_by(event_entity_id=event.id, member_type_id=member.member_type_id).first()
    if not fee:
        return None, None
    eb_active = is_early_bird_active(event)
    price = fee.early_bird_price if (eb_active and fee.early_bird_price is not None) else fee.price
    return fee, price

# --- Member Login ---
@ce_bp.route('/login', methods=['GET', 'POST'])
def login():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    next_url = request.args.get('next') or request.form.get('next')
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        member = Member.query.filter_by(email=username).first()
        if member and check_password_hash(member.password_hash, password):
            session['member_id'] = member.id
            user = get_current_user()
            flash(texts.get('login_success', 'เข้าสู่ระบบสำเร็จ!' if lang == 'th' else 'Login successful!'), 'success')
            return redirect(next_url or url_for('continuing_edu.index', lang=lang, logged_in_user=user))
        else:
            flash(texts.get('login_error', 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง' if lang == 'th' else 'Invalid username or password.'), 'danger')
    return render_template('continueing_edu/login.html', texts=texts, current_lang=lang, logged_in_user=get_current_user(), next=next_url)





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

    form_values = request.form.to_dict() if request.method == 'POST' else {}
    address_entries = _collect_address_entries_from_form(request.form) if request.method == 'POST' else _default_address_entries()
    if not address_entries:
        address_entries = _default_address_entries()

    organization_types = OrganizationType.query.order_by(OrganizationType.name_en.asc()).all()
    occupations = Occupation.query.order_by(Occupation.name_en.asc()).all()
    organizations = Organization.query.order_by(Organization.name.asc()).limit(50).all()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = (request.form.get('email') or '').strip() or None
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        accept_privacy = bool(request.form.get('accept_privacy'))
        accept_terms = bool(request.form.get('accept_terms'))
        accept_news = bool(request.form.get('accept_news'))
        not_bot = (request.form.get('not_bot') or '').strip().lower()

        organization_name = (request.form.get('organization_name') or '').strip()
        organization_type_choice = (request.form.get('organization_type_id') or '').strip()
        organization_type_other = (request.form.get('organization_type_other') or '').strip()
        organization_country_code = (request.form.get('organization_country') or '').strip()
        organization_country_other = (request.form.get('organization_country_other') or '').strip()

        occupation_choice = (request.form.get('occupation_id') or '').strip()
        occupation_other = (request.form.get('occupation_other') or '').strip()

        errors = []
        if not username or not password:
            errors.append(texts.get('register_error_required', 'Username and password required.'))
        if password and password != confirm_password:
            errors.append('รหัสผ่านและยืนยันรหัสผ่านไม่ตรงกัน' if lang == 'th' else 'Passwords do not match.')
        if not accept_privacy:
            errors.append('กรุณายอมรับนโยบายความเป็นส่วนตัว' if lang == 'th' else 'Please accept the privacy policy.')
        if not accept_terms:
            errors.append('กรุณายอมรับข้อกำหนดและเงื่อนไข' if lang == 'th' else 'Please accept the terms and conditions.')
        if not (not_bot and not_bot in ('มนุษย์', 'human')):
            errors.append('กรุณายืนยันว่าคุณไม่ใช่บอท โดยพิมพ์คำว่า "มนุษย์" หรือ "human"' if lang == 'th' else 'Please confirm you are not a bot by typing "มนุษย์" or "human".')

        if organization_type_choice == 'other' and not organization_type_other:
            errors.append(texts.get('organization_type_other_placeholder', 'Please specify organization type.'))
        if occupation_choice == 'other' and not occupation_other:
            errors.append(texts.get('occupation_other_placeholder', 'Please specify occupation.'))

        # Address validations
        meaningful_addresses = []
        for entry in address_entries:
            has_content = bool(entry.get('line1'))
            if has_content:
                meaningful_addresses.append(entry)
            if entry.get('type') == 'other' and has_content and not entry.get('type_other'):
                errors.append(texts.get('address_type_other_prompt', 'Please specify address type for custom entries.'))
            if entry.get('country_code') == 'OTHER' and has_content and not entry.get('country_other'):
                errors.append(texts.get('address_country_other_prompt', 'Please specify country name.'))

        if not meaningful_addresses:
            errors.append(texts.get('address_required_message', 'Please provide at least one address.'))

        if username and Member.query.filter_by(username=username).first():
            errors.append(texts.get('register_error_exists', 'Username already exists.'))
        if email and Member.query.filter_by(email=email).first():
            return render_template(
                'continueing_edu/email_already_registered.html',
                email=email,
                current_lang=lang,
                texts=texts,
            )

        if errors:
            for message in errors:
                flash(message, 'danger')
            return render_template(
                'continueing_edu/register.html',
                texts=texts,
                current_lang=lang,
                form_values=form_values,
                organization_types=organization_types,
                occupations=occupations,
                organizations=organizations,
                address_entries=address_entries,
                country_options=COUNTRY_OPTIONS,
            )

        organization_type = None
        if organization_type_choice:
            if organization_type_choice == 'other' and organization_type_other:
                lookup = organization_type_other.lower()
                organization_type = (OrganizationType.query
                                     .filter(func.lower(OrganizationType.name_en) == lookup)
                                     .first())
                if not organization_type:
                    organization_type = (OrganizationType.query
                                         .filter(func.lower(OrganizationType.name_th) == lookup)
                                         .first())
                if not organization_type:
                    organization_type = OrganizationType(
                        name_en=organization_type_other,
                        name_th=organization_type_other,
                        is_user_defined=True,
                    )
                    db.session.add(organization_type)
                    db.session.flush()
            else:
                try:
                    organization_type = OrganizationType.query.get(int(organization_type_choice))
                except (ValueError, TypeError):
                    organization_type = None

        occupation = None
        if occupation_choice:
            if occupation_choice == 'other' and occupation_other:
                lookup = occupation_other.lower()
                occupation = (Occupation.query
                              .filter(func.lower(Occupation.name_en) == lookup)
                              .first())
                if not occupation:
                    occupation = (Occupation.query
                                  .filter(func.lower(Occupation.name_th) == lookup)
                                  .first())
                if not occupation:
                    occupation = Occupation(
                        name_en=occupation_other,
                        name_th=occupation_other,
                        is_user_defined=True,
                    )
                    db.session.add(occupation)
                    db.session.flush()
            else:
                try:
                    occupation = Occupation.query.get(int(occupation_choice))
                except (ValueError, TypeError):
                    occupation = None

        organization_country_name = None
        organization_country_code_final = None
        if organization_country_code == 'OTHER' and organization_country_other:
            organization_country_name = organization_country_other
        elif organization_country_code:
            organization_country_code_final = organization_country_code
            organization_country_name = next(
                (item['name'] for item in COUNTRY_OPTIONS if item['code'] == organization_country_code),
                organization_country_code,
            )

        organization = None
        if organization_name:
            organization = (Organization.query
                            .filter(func.lower(Organization.name) == organization_name.lower())
                            .first())
            if not organization:
                organization = Organization(
                    name=organization_name,
                    organization_type=organization_type,
                    country=organization_country_name,
                    is_user_defined=True,
                )
                db.session.add(organization)
                db.session.flush()
            else:
                if organization_type and not organization.organization_type_id:
                    organization.organization_type = organization_type
                if organization_country_name and not organization.country:
                    organization.country = organization_country_name

        member = Member(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            organization=organization,
            occupation=occupation,
            received_news=accept_news,
        )
        db.session.add(member)
        db.session.flush()

        created_addresses = []
        for entry in address_entries:
            line1 = entry.get('line1')
            if not line1:
                continue

            address_type_value = entry.get('type') or ''
            if address_type_value == 'other' and entry.get('type_other'):
                address_type_value = entry['type_other']

            country_code = entry.get('country_code') or ''
            country_other_value = entry.get('country_other') or ''
            if country_code == 'OTHER' and country_other_value:
                country_name = country_other_value
                country_code_value = None
            elif country_code:
                country_name = next((item['name'] for item in COUNTRY_OPTIONS if item['code'] == country_code), country_code)
                country_code_value = country_code
            else:
                country_name = None
                country_code_value = None

            address = MemberAddress(
                member=member,
                address_type=address_type_value or 'other',
                label=entry.get('label') or None,
                line1=line1,
                line2=entry.get('line2') or None,
                city=entry.get('city') or None,
                state=entry.get('state') or None,
                postal_code=entry.get('postal') or None,
                country_code=country_code_value,
                country_name=country_name,
            )
            db.session.add(address)
            created_addresses.append(address)

        if created_addresses and not member.address:
            member.address = created_addresses[0].line1
            member.province = created_addresses[0].state
            member.zip_code = created_addresses[0].postal_code
            member.country = created_addresses[0].country_name

        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            flash(texts.get('register_error_generic', 'We could not complete your registration. Please try again.'), 'danger')
            return render_template(
                'continueing_edu/register.html',
                texts=texts,
                current_lang=lang,
                form_values=form_values,
                organization_types=organization_types,
                occupations=occupations,
                organizations=organizations,
                address_entries=address_entries,
                country_options=COUNTRY_OPTIONS,
            )

        import random

        otp_code = '{:06d}'.format(random.randint(0, 999999))
        session['otp_code'] = otp_code
        session['otp_username'] = username
        session['otp_email'] = email
        try:
            if email:
                send_mail(
                    [email],
                    'รหัส OTP สำหรับการลงทะเบียนของคุณ' if lang == 'th' else 'Your Registration OTP Code',
                    f'รหัส OTP ของคุณคือ: {otp_code}' if lang == 'th' else f'Your OTP code is: {otp_code}',
                )
            else:
                flash(
                    texts.get('otp_email_missing', 'Please provide an email address to receive your OTP code.'),
                    'warning',
                )
        except Exception as e:
            flash(
                f'ไม่สามารถส่งอีเมล OTP ได้: {e}' if lang == 'th' else f'Unable to send OTP email: {e}',
                'danger',
            )

        return render_template('continueing_edu/otp_verify.html', username=username, current_lang=lang, texts=texts)

    return render_template(
        'continueing_edu/register.html',
        texts=texts,
        current_lang=lang,
        form_values=form_values,
        organization_types=organization_types,
        occupations=occupations,
        organizations=organizations,
        address_entries=address_entries,
        country_options=COUNTRY_OPTIONS,
    )




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
        # Redirect to forgot password page
        return redirect(url_for('continuing_edu.forgot_password', texts=texts, lang=lang))
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


# --- Forgot Password (request OTP) ---
@ce_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        if not identifier:
            flash('กรุณากรอกอีเมลหรือชื่อผู้ใช้' if lang == 'th' else 'Please enter your email or username.', 'danger')
            return render_template('continueing_edu/forgot_password.html', current_lang=lang, texts=texts)
        from .models import Member
        user = Member.query.filter((Member.email == identifier) | (Member.username == identifier)).first()
        if not user or not user.email:
            flash('ไม่พบบัญชีที่ใช้อีเมลนี้' if lang == 'th' else 'No account found for that email/username.', 'danger')
            return render_template('continueing_edu/forgot_password.html', current_lang=lang, texts=texts)
        # Generate OTP and set expiry (10 minutes)
        import random, time
        otp_code = '{:06d}'.format(random.randint(0, 999999))
        session['reset_otp'] = otp_code
        session['reset_username'] = user.username
        session['reset_email'] = user.email
        session['reset_expires'] = int(time.time()) + 600
        try:
            send_mail([user.email],
                     'รหัส OTP สำหรับรีเซ็ตรหัสผ่าน' if lang == 'th' else 'Your Password Reset OTP',
                     f'รหัส OTP ของคุณคือ: {otp_code} (หมดอายุใน 10 นาที)' if lang == 'th' else f'Your OTP code is: {otp_code} (expires in 10 minutes)')
            flash('เราได้ส่งรหัส OTP ไปยังอีเมลของคุณแล้ว' if lang == 'th' else 'We sent an OTP to your email.', 'success')
        except Exception as e:
            flash((f'ส่งอีเมลไม่สำเร็จ: {e}') if lang == 'th' else f'Failed to send email: {e}', 'danger')
        return redirect(url_for('continuing_edu.reset_password', lang=lang, username=user.username))
    return render_template('continueing_edu/forgot_password.html', current_lang=lang, texts=texts)


# --- Reset Password (confirm OTP and set new password) ---
@ce_bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    preset_username = request.args.get('username') or session.get('reset_username')
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        otp_input = request.form.get('otp_code', '').strip()
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')
        # Validate session OTP
        otp_expected = session.get('reset_otp')
        otp_user = session.get('reset_username')
        otp_exp = session.get('reset_expires')
        import time
        if not otp_expected or not otp_user or username != otp_user:
            flash('เซสชัน OTP หมดอายุหรือไม่ถูกต้อง' if lang == 'th' else 'OTP session expired or invalid.', 'danger')
            return redirect(url_for('continuing_edu.forgot_password', lang=lang))
        if otp_exp and time.time() > otp_exp:
            flash('OTP หมดอายุแล้ว' if lang == 'th' else 'OTP has expired.', 'danger')
            return redirect(url_for('continuing_edu.forgot_password', lang=lang))
        if otp_input != otp_expected:
            flash('รหัส OTP ไม่ถูกต้อง' if lang == 'th' else 'Invalid OTP code.', 'danger')
            return render_template('continueing_edu/reset_password.html', current_lang=lang, texts=texts, username=username)
        if not new_pw or new_pw != confirm_pw:
            flash('รหัสผ่านใหม่ไม่ตรงกัน' if lang == 'th' else 'New passwords do not match.', 'danger')
            return render_template('continueing_edu/reset_password.html', current_lang=lang, texts=texts, username=username)
        # Update password
        from .models import Member
        user = Member.query.filter_by(username=username).first()
        if not user:
            flash('ไม่พบบัญชี' if lang == 'th' else 'Account not found.', 'danger')
            return redirect(url_for('continuing_edu.forgot_password', lang=lang))
        user.password_hash = generate_password_hash(new_pw)
        db.session.add(user)
        db.session.commit()
        # Clear OTP session
        session.pop('reset_otp', None)
        session.pop('reset_username', None)
        session.pop('reset_email', None)
        session.pop('reset_expires', None)
        flash('เปลี่ยนรหัสผ่านเรียบร้อยแล้ว' if lang == 'th' else 'Your password has been reset.', 'success')
        return redirect(url_for('continuing_edu.login', lang=lang))
    return render_template('continueing_edu/reset_password.html', current_lang=lang, texts=texts, username=preset_username)


def _google_oauth_session(redirect_uri, state=None, token=None):
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    scope = [
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'openid',
    ]
    return OAuth2Session(client_id=client_id, redirect_uri=redirect_uri, scope=scope, state=state, token=token)


@ce_bp.route('/oauth/google/login')
def google_login():
    lang = request.args.get('lang', 'en')
    next_url = request.args.get('next')
    redirect_uri = os.getenv('GOOGLE_REDIRECT_URI') or urljoin(request.host_url, '/continuing_edu/oauth/google/callback')
    oauth = _google_oauth_session(redirect_uri)
    authorization_base_url = 'https://accounts.google.com/o/oauth2/v2/auth'
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    if next_url:
        session['oauth_next'] = next_url
    authorization_url, _ = oauth.authorization_url(authorization_base_url, state=state, prompt='consent', access_type='offline', include_granted_scopes='true')
    return redirect(authorization_url)


@ce_bp.route('/oauth/google/callback')
def google_callback():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    state = request.args.get('state')
    if not state or state != session.get('oauth_state'):
        flash('Invalid OAuth state.', 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    redirect_uri = os.getenv('GOOGLE_REDIRECT_URI') or urljoin(request.host_url, '/continuing_edu/oauth/google/callback')
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    token_url = 'https://oauth2.googleapis.com/token'
    oauth = _google_oauth_session(redirect_uri, state=state)
    try:
        token = oauth.fetch_token(token_url=token_url, client_secret=client_secret, authorization_response=request.url)
        resp = oauth.get('https://www.googleapis.com/oauth2/v3/userinfo')
        data = resp.json()
        sub = data.get('sub')
        email = data.get('email')
        name = data.get('name')
    except Exception as e:
        flash(f'Google login error: {e}', 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))

    user = Member.query.filter_by(google_sub=sub).first()
    if not user and email:
        user = Member.query.filter_by(email=email).first()
        if user and not user.google_sub:
            user.google_sub = sub
    if not user:
        pwd = secrets.token_urlsafe(12)
        user = Member(username=email.split('@')[0] if email else f'user_{sub[:6]}',
                      email=email,
                      password_hash=generate_password_hash(pwd),
                      full_name_en=name)
        user.google_sub = sub

        user.google_connected_at = datetime.now(timezone.utc)
        db.session.add(user)
    db.session.commit()
    session['member_id'] = user.id
    next_url = session.pop('oauth_next', None)
    flash(texts.get('login_success', 'Login successful!'), 'success')
    return redirect(next_url or url_for('continuing_edu.index', lang=lang))


@ce_bp.route('/account/connect/google')
def account_connect_google():
    lang = request.args.get('lang', 'en')
    next_url = url_for('continuing_edu.account_settings', lang=lang)
    return redirect(url_for('continuing_edu.google_login', lang=lang, next=next_url))


@ce_bp.route('/account/disconnect/google', methods=['POST'])
def account_disconnect_google():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    user.google_sub = None
    user.google_connected_at = None
    db.session.add(user)
    db.session.commit()
    flash(texts.get('google_disconnected', 'Disconnected Google account.'), 'success')
    return redirect(url_for('continuing_edu.account_settings', lang=lang))


# -----------------------------
# My Account Settings
# -----------------------------
@ce_bp.route('/account', methods=['GET'])
def account_settings():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    return render_template('continueing_edu/account_settings.html', user=user, texts=texts, current_lang=lang)


@ce_bp.route('/account/profile', methods=['POST'])
def account_update_profile():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    # Basic editable fields
    for field in ['email','full_name_en','full_name_th','phone_no','address','province','zip_code','country','title_name_en','title_name_th']:
        if field in request.form:
            setattr(user, field, request.form.get(field))
    db.session.add(user)
    db.session.commit()
    flash(texts.get('profile_updated', 'Profile updated.'), 'success')
    return redirect(url_for('continuing_edu.account_settings', lang=lang))


@ce_bp.route('/account/password', methods=['POST'])
def account_change_password():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    current_pw = request.form.get('current_password')
    new_pw = request.form.get('new_password')
    confirm_pw = request.form.get('confirm_password')
    if not current_pw or not new_pw:
        flash(texts.get('password_required', 'Password fields are required.'), 'danger')
        return redirect(url_for('continuing_edu.account_settings', lang=lang))
    if not check_password_hash(user.password_hash, current_pw):
        flash(texts.get('password_incorrect', 'Current password is incorrect.'), 'danger')
        return redirect(url_for('continuing_edu.account_settings', lang=lang))
    if new_pw != confirm_pw:
        flash(texts.get('passwords_not_match', 'New passwords do not match.'), 'danger')
        return redirect(url_for('continuing_edu.account_settings', lang=lang))
    user.password_hash = generate_password_hash(new_pw)
    db.session.add(user)
    db.session.commit()
    flash(texts.get('password_changed', 'Password changed successfully.'), 'success')
    return redirect(url_for('continuing_edu.account_settings', lang=lang))


@ce_bp.route('/account/delete_request', methods=['POST'])
def account_request_delete():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    reason = request.form.get('reason', '')
    # Notify admins for manual processing
    try:
        admin_email = 'support@mumt.mahidol.ac.th'
        body = f"User {user.username} ({user.email}) requested account deletion. Reason: {reason}"
        send_mail([admin_email], 'Account deletion request', body)
    except Exception:
        pass
    flash(texts.get('delete_requested', 'Your account deletion request has been sent. We will contact you shortly.'), 'success')
    return redirect(url_for('continuing_edu.account_settings', lang=lang))


@ce_bp.route('/account/export', methods=['GET'])
def account_export_data():
    lang = request.args.get('lang', 'en')
    user = get_current_user()
    if not user:
        flash('Please login to continue.', 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    # Assemble JSON export
    data = {
        'member': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name_en': user.full_name_en,
            'full_name_th': user.full_name_th,
            'phone_no': user.phone_no,
            'address': user.address,
            'province': user.province,
            'zip_code': user.zip_code,
            'country': user.country,
            'member_type': user.member_type_ref.name_en if user.member_type_ref else None,
            'created_at': str(user.created_at),
        },
        'registrations': [
            {
                'event_id': r.event_entity_id,
                'event_title': r.event_entity.title_en if r.event_entity else None,
                'event_type': r.event_entity.event_type if r.event_entity else None,
                'registration_date': str(r.registration_date),
                'status': r.status_ref.name_en if r.status_ref else None,
            } for r in user.registrations
        ],
        'payments': [
            {
                'event_id': p.event_entity_id,
                'event_title': p.event_entity.title_en if p.event_entity else None,
                'amount': p.payment_amount,
                'status': p.payment_status_ref.name_en if p.payment_status_ref else None,
                'payment_date': str(p.payment_date),
                'transaction_id': p.transaction_id,
            } for p in user.payments
        ],
    }
    import json
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    resp = make_response(payload)
    resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename="my_data_{user.username}.json"'
    return resp


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
    user = get_current_user()
    registered_ids = set()
    if user:
        regs = MemberRegistration.query.with_entities(MemberRegistration.event_entity_id).filter_by(member_id=user.id).all()
        registered_ids = {r[0] for r in regs}
    return render_template('continueing_edu/all_events.html', events=events, active_menu='All Events', texts=texts, lang=current_lang, logged_in_user=user, registered_ids=registered_ids)


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
    user = get_current_user()
    registered_ids = set()
    if user:
        regs = MemberRegistration.query.with_entities(MemberRegistration.event_entity_id).filter_by(member_id=user.id).all()
        registered_ids = {r[0] for r in regs}
    # Optional filter: show only events the user registered for
    registered_only = request.args.get('registered_only') in ('1', 'true', 'yes')
    if registered_only and user:
        events = [e for e in events if e.id in registered_ids]

    hero_query = EventEntity.query
    is_active_column = getattr(EventEntity, 'is_active', None)
    if is_active_column is not None:
        hero_query = hero_query.filter(is_active_column.is_(True))
    hero_events = (hero_query
                   .order_by(EventEntity.created_at.desc())
                   .limit(5)
                   .all())
    if not hero_events:
        hero_events = events[:5]

    placeholder_image = 'https://placehold.co/1920x1080/1f2937/FFFFFF?text=Continuing+Education'
    hero_slides = []
    for ev in hero_events:
        image_candidates = [
            ev.cover_presigned_url() if hasattr(ev, 'cover_presigned_url') else None,
            getattr(ev, 'cover_image_url', None),
            ev.poster_presigned_url() if hasattr(ev, 'poster_presigned_url') else None,
            getattr(ev, 'poster_image_url', None),
            getattr(ev, 'image_url', None),
        ]
        image = next((img for img in image_candidates if img), None) or placeholder_image

        desc = (ev.description_en or ev.description_th or '')
        if desc:
            desc = shorten(desc, width=180, placeholder='…')

        speaker_names = []
        try:
            for sp in (ev.speakers or []):
                if getattr(sp, 'name_en', None):
                    speaker_names.append(sp.name_en)
                elif getattr(sp, 'name_th', None):
                    speaker_names.append(sp.name_th)
        except Exception:
            pass
        speakers_label = ', '.join(speaker_names[:3]) if speaker_names else ''

        if ev.event_type == 'course':
            detail_url = url_for('continuing_edu.course_detail', course_id=ev.id, lang=lang)
        elif ev.event_type == 'webinar':
            detail_url = url_for('continuing_edu.webinar_detail', webinar_id=ev.id, lang=lang)
        else:
            detail_url = url_for('continuing_edu.index', lang=lang)

        hero_slides.append({
            'id': ev.id,
            'title': ev.title_en or ev.title_th or f"Event #{ev.id}",
            'subtitle': desc,
            'image': image,
            'cta_url': detail_url,
            'cta_label': texts.get('hero_view_event', 'View Event'),
            'event_type': ev.event_type,
            'event_type_label': texts.get(f"event_type_{(ev.event_type or '').lower()}", (ev.event_type or 'Event').title()),
            'schedule_label': ev.created_at.strftime('%d %b %Y') if getattr(ev, 'created_at', None) else '',
            'speakers': speakers_label,
        })

    if not hero_slides:
        hero_slides.append({
            'id': 0,
            'title': texts.hero_title,
            'subtitle': texts.hero_subtitle,
            'image': placeholder_image,
            'cta_url': url_for('continuing_edu.index', lang=lang),
            'cta_label': texts.get('explore_courses_btn', 'Explore Courses'),
            'event_type': '',
            'event_type_label': '',
            'schedule_label': '',
            'speakers': '',
        })

    return render_template(
        'continueing_edu/index.html',
        events=events,
        active_menu='All Events',
        texts=texts,
        current_lang=lang,
        logged_in_user=user,
        registered_ids=registered_ids,
        registered_only=registered_only,
        hero_slides=hero_slides,
    )


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
    user = get_current_user()
    already_registered = False
    approved_payment = False
    if user:
        reg = MemberRegistration.query.filter_by(member_id=user.id, event_entity_id=course.id).first()
        already_registered = reg is not None
        if reg:
            from app.continuing_edu.models import RegisterPaymentStatus, RegisterPayment
            ap = RegisterPayment.query \
                .join(RegisterPaymentStatus, RegisterPayment.payment_status_ref) \
                .filter(RegisterPayment.member_id == user.id,
                        RegisterPayment.event_entity_id == course.id,
                        ((RegisterPaymentStatus.register_payment_status_code == 'approved') | (RegisterPaymentStatus.name_en == 'approved'))).first()
            approved_payment = ap is not None
    return render_template('continueing_edu/course_detail.html', course=course, texts=texts, current_lang=lang,
                           logged_in_user=user, already_registered=already_registered, approved_payment=approved_payment)

@ce_bp.route('/webinar_detail/<int:webinar_id>')
def webinar_detail(webinar_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    webinar = EventEntity.query.filter_by(id=webinar_id, event_type='webinar').first_or_404()
    user = get_current_user()
    already_registered = False
    approved_payment = False
    if user:
        reg = MemberRegistration.query.filter_by(member_id=user.id, event_entity_id=webinar.id).first()
        already_registered = reg is not None
        if reg:
            from app.continuing_edu.models import RegisterPaymentStatus, RegisterPayment
            ap = RegisterPayment.query \
                .join(RegisterPaymentStatus, RegisterPayment.payment_status_ref) \
                .filter(RegisterPayment.member_id == user.id,
                        RegisterPayment.event_entity_id == webinar.id,
                        ((RegisterPaymentStatus.register_payment_status_code == 'approved') | (RegisterPaymentStatus.name_en == 'approved'))).first()
            approved_payment = ap is not None
    return render_template('continueing_edu/webinar_detail.html', webinar=webinar, texts=texts, current_lang=lang,
                           logged_in_user=user, already_registered=already_registered, approved_payment=approved_payment)


# --- Event Registration ---
@ce_bp.route('/event/<int:event_id>/register', methods=['GET', 'POST'])
def register_event(event_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    event = EventEntity.query.get_or_404(event_id)
    member = get_current_user()
    if not member:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))

    # Already registered?
    existing = MemberRegistration.query.filter_by(member_id=member.id, event_entity_id=event.id).first()
    if existing:
        flash(texts.get('already_registered', 'You are already registered for this event.'), 'info')
        return redirect(url_for('continuing_edu.course_detail' if event.event_type=='course' else 'continuing_edu.webinar_detail', course_id=event.id if event.event_type=='course' else None, webinar_id=event.id if event.event_type=='webinar' else None, lang=lang))

    fee, price = _price_for_member(event, member)
    if not fee:
        flash(texts.get('no_fee_defined', 'No registration fee defined for your member type.'), 'danger')
        return redirect(url_for('continuing_edu.course_detail' if event.event_type=='course' else 'continuing_edu.webinar_detail', course_id=event.id if event.event_type=='course' else None, webinar_id=event.id if event.event_type=='webinar' else None, lang=lang))

    if request.method == 'POST':
        # Create registration and pending payment
        registered_status = get_registration_status('registered', 'registered', 'ลงทะเบียนแล้ว', 'is-info')
        pending_cert = get_certificate_status('pending', 'รอดำเนินการ', 'is-info')
        reg = MemberRegistration(member_id=member.id, event_entity_id=event.id,
                                 status_id=registered_status.id,
                                 certificate_status_id=pending_cert.id)
        db.session.add(reg)
        # payment status pending (id may be 1); try lookup by name_en
        pending = RegisterPaymentStatus.query.filter((RegisterPaymentStatus.register_payment_status_code=='pending') | (RegisterPaymentStatus.name_en=='pending')).first()
        pay = RegisterPayment(
            member_id=member.id,
            event_entity_id=event.id,
            payment_status_id=pending.id if pending else 1,
            payment_amount=price,
        )
        db.session.add(pay)
        db.session.commit()
        # Notify member by email (best-effort)
        try:
            subj = texts.get('registration_success', 'Registration submitted. Payment pending.')
            invoice_link = url_for('continuing_edu.view_invoice', payment_id=pay.id, lang=lang, _external=True)
            payments_link = url_for('continuing_edu.my_payments', lang=lang, _external=True)
            payment_gateway_url = os.environ.get('PAYMENT_GATEWAY_URL')
            body = (f"{texts['email_registered_for']}: {event.title_en or event.title_th}\n"
                    f"{texts['email_amount']}: {price} THB\n"
                    f"{texts['email_status']}: {texts['status_pending']}\n\n"
                    f"{texts['email_pay_now_or_view_invoice']}\n"
                    f"{texts['email_invoice']}: {invoice_link}\n"
                    f"{texts['email_my_payments']}: {payments_link}\n"
                    + (f"{texts['email_pay_online']}: {payment_gateway_url}\n" if payment_gateway_url else ""))

            # HTML Email with buttons
            email_html = render_template(
                'continueing_edu/_registration_email.html',
                event=event,
                amount=price,
                invoice_link=invoice_link,
                payments_link=payments_link,
                payment_gateway_url=payment_gateway_url,
                texts=texts,
                current_lang=lang,
            )

            msg = Message(subject=subj, body=body, html=email_html, recipients=[member.email]) if getattr(member, 'email', None) else None
            if msg:
                # Try attach PDF invoice
                if HTML is not None:
                    try:
                        payment_qr_url = os.environ.get('PAYMENT_QR_URL')
                        promptpay_id = os.environ.get('PROMPTPAY_ID')
                        bank_info = os.environ.get('BANK_INFO')
                        payment_instructions = os.environ.get('PAYMENT_INSTRUCTIONS')
                        html = render_template(
                            'continueing_edu/invoice.html',
                            payment=pay,
                            member=member,
                            texts=texts,
                            current_lang=lang,
                            payment_qr_url=payment_qr_url,
                            promptpay_id=promptpay_id,
                            bank_info=bank_info,
                            payment_instructions=payment_instructions,
                            pdf_available=True,
                        )
                        pdf_bytes = HTML(string=html, base_url=request.host_url).write_pdf()
                        msg.attach(f"invoice_INV-{pay.id}.pdf", 'application/pdf', pdf_bytes)
                    except Exception:
                        pass
                mail.send(msg)
        except Exception:
            pass
        flash(texts.get('registration_success', 'Registration submitted. Payment pending.'), 'success')
        return redirect(url_for('continuing_edu.course_detail' if event.event_type=='course' else 'continuing_edu.webinar_detail', course_id=event.id if event.event_type=='course' else None, webinar_id=event.id if event.event_type=='webinar' else None, lang=lang))

    return render_template('continueing_edu/register_event.html', event=event, member=member, fee=fee, price=price, texts=texts, current_lang=lang)

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


@ce_bp.route('/my-registrations')
def my_registrations():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    regs = MemberRegistration.query.filter_by(member_id=user.id).order_by(MemberRegistration.registration_date.desc()).all()
    payments = RegisterPayment.query.filter_by(member_id=user.id).order_by(RegisterPayment.id.desc()).all()
    pay_map = {}
    for p in payments:
        if p.event_entity_id not in pay_map:
            pay_map[p.event_entity_id] = p
    return render_template('continueing_edu/my_registrations.html', registrations=regs, payments_map=pay_map, texts=texts, current_lang=lang)


@ce_bp.route('/my-payments', methods=['GET'])
def my_payments():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    pays = RegisterPayment.query.filter_by(member_id=user.id).order_by(RegisterPayment.id.desc()).all()
    payment_gateway_url = os.environ.get('PAYMENT_GATEWAY_URL')
    return render_template('continueing_edu/my_payments.html', payments=pays, texts=texts, current_lang=lang,
                           payment_gateway_url=payment_gateway_url)


@ce_bp.route('/payment/<int:payment_id>/submit_proof', methods=['POST'])
def submit_payment_proof(payment_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    pay = RegisterPayment.query.get_or_404(payment_id)
    if pay.member_id != user.id:
        flash(texts.get('not_allowed', 'Not allowed.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    proof_url = request.form.get('payment_proof_url')
    if not proof_url:
        flash(texts.get('proof_required', 'Please provide a payment proof URL.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    # If replacing an existing S3 proof, delete the old object (best-effort)
    old = pay.payment_proof_url
    def _is_http(u):
        return isinstance(u, str) and (u.startswith('http://') or u.startswith('https://') or u.startswith('//'))
    try:
        if old and not _is_http(old) and old != proof_url:
            from app.main import s3, S3_BUCKET_NAME
            s3.delete_object(Bucket=S3_BUCKET_NAME, Key=old)
    except Exception:
        pass
    pay.payment_proof_url = proof_url
    # Optionally move to 'submitted' if such status exists
    submitted = RegisterPaymentStatus.query.filter((RegisterPaymentStatus.register_payment_status_code=='submitted') | (RegisterPaymentStatus.name_en=='submitted')).first()
    if submitted:
        pay.payment_status_id = submitted.id
    db.session.add(pay)
    db.session.commit()
    flash(texts.get('proof_received', 'Payment proof submitted.'), 'success')
    return redirect(url_for('continuing_edu.my_payments', lang=lang))


@ce_bp.route('/payment/<int:payment_id>/upload_proof', methods=['POST'])
def upload_payment_proof(payment_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    pay = RegisterPayment.query.get_or_404(payment_id)
    if pay.member_id != user.id:
        flash(texts.get('not_allowed', 'Not allowed.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    file = request.files.get('payment_proof_file')
    if not file or file.filename == '':
        flash(texts.get('proof_required', 'Please provide a payment proof file.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))

    # Upload to S3
    # Lazy import to avoid circular import at module load
    from app.main import allowed_file, s3, S3_BUCKET_NAME
    if not allowed_file(file.filename):
        flash(texts.get('proof_required', 'Please provide a payment proof file.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    safe_name = secure_filename(file.filename)
    ext = safe_name.rsplit('.', 1)[-1].lower() if '.' in safe_name else 'dat'
    key = f"continuing_edu/payments/{payment_id}/proof_{int(time.time())}.{ext}"
    content_type = file.mimetype or 'application/octet-stream'
    data = file.read()
    # If replacing an existing S3 proof, delete the old object (best-effort)
    old = pay.payment_proof_url
    try:
        s3.put_object(Bucket=S3_BUCKET_NAME, Key=key, Body=data, ContentType=content_type)
        if old and old != key:
            try:
                from urllib.parse import urlparse
                # delete old only if it is a key (not URL)
                if not (old.startswith('http://') or old.startswith('https://') or old.startswith('//')):
                    s3.delete_object(Bucket=S3_BUCKET_NAME, Key=old)
            except Exception:
                pass
        pay.payment_proof_url = key
    except Exception:
        flash(texts.get('proof_required', 'Please provide a payment proof file.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    submitted = RegisterPaymentStatus.query.filter((RegisterPaymentStatus.register_payment_status_code=='submitted') | (RegisterPaymentStatus.name_en=='submitted')).first()
    if submitted:
        pay.payment_status_id = submitted.id
    db.session.add(pay)
    db.session.commit()
    flash(texts.get('proof_received', 'Payment proof submitted.'), 'success')
    return redirect(url_for('continuing_edu.my_payments', lang=lang))


@ce_bp.route('/payment/<int:payment_id>/invoice')
def view_invoice(payment_id):
    """Simple invoice page for a single payment."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    pay = RegisterPayment.query.get_or_404(payment_id)
    if pay.member_id != user.id:
        flash(texts.get('not_allowed', 'You are not allowed to view this invoice.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    payment_qr_url = os.environ.get('PAYMENT_QR_URL')
    promptpay_id = os.environ.get('PROMPTPAY_ID')
    bank_info = os.environ.get('BANK_INFO')
    payment_instructions = os.environ.get('PAYMENT_INSTRUCTIONS')
    payment_gateway_url = os.environ.get('PAYMENT_GATEWAY_URL')
    return render_template('continueing_edu/invoice.html', payment=pay, member=user, texts=texts, current_lang=lang,
                           payment_qr_url=payment_qr_url, promptpay_id=promptpay_id, bank_info=bank_info,
                           payment_instructions=payment_instructions, payment_gateway_url=payment_gateway_url,
                           pdf_available=(HTML is not None))


@ce_bp.route('/payment/<int:payment_id>/invoice.pdf')
def download_invoice_pdf(payment_id):
    """Generate and download invoice as PDF."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    pay = RegisterPayment.query.get_or_404(payment_id)
    if pay.member_id != user.id:
        flash(texts.get('not_allowed', 'You are not allowed to view this invoice.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    if HTML is None:
        flash(texts.get('pdf_unavailable', 'PDF generation is currently unavailable.'), 'warning')
        return redirect(url_for('continuing_edu.view_invoice', payment_id=payment_id, lang=lang))
    payment_qr_url = os.environ.get('PAYMENT_QR_URL')
    promptpay_id = os.environ.get('PROMPTPAY_ID')
    bank_info = os.environ.get('BANK_INFO')
    payment_instructions = os.environ.get('PAYMENT_INSTRUCTIONS')
    html = render_template(
        'continueing_edu/invoice.html',
        payment=pay,
        member=user,
        texts=texts,
        current_lang=lang,
        payment_qr_url=payment_qr_url,
        promptpay_id=promptpay_id,
        bank_info=bank_info,
        payment_instructions=payment_instructions,
        payment_gateway_url=os.environ.get('PAYMENT_GATEWAY_URL'),
        pdf_available=True,
    )
    pdf_bytes = HTML(string=html, base_url=request.host_url).write_pdf()
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename="invoice_INV-{pay.id}.pdf"'
    return resp


@ce_bp.route('/receipt/<int:receipt_id>')
def view_receipt(receipt_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    from .models import RegisterPaymentReceipt
    rc = RegisterPaymentReceipt.query.get_or_404(receipt_id)
    pay = rc.payment
    if pay.member_id != user.id:
        flash(texts.get('not_allowed', 'Not allowed.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    return render_template('continueing_edu/receipt.html', receipt=rc, payment=pay, member=user, texts=texts, current_lang=lang)


@ce_bp.route('/receipt/<int:receipt_id>/pdf')
def view_receipt_pdf(receipt_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    from .models import RegisterPaymentReceipt
    rc = RegisterPaymentReceipt.query.get_or_404(receipt_id)
    pay = rc.payment
    if pay.member_id != user.id:
        flash(texts.get('not_allowed', 'Not allowed.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    if HTML is None:
        flash('PDF rendering library is not available on server.', 'danger')
        return redirect(url_for('continuing_edu.view_receipt', receipt_id=receipt_id, lang=lang))
    html = render_template('continueing_edu/receipt_pdf.html', receipt=rc, payment=pay, member=user, texts=texts, current_lang=lang)
    pdf = HTML(string=html, base_url=request.base_url).write_pdf()

    filename = f"receipt_{rc.receipt_number}.pdf"
    return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': f'inline; filename="{filename}"'})


# -----------------------------
# Member progress + certificates
# -----------------------------
def _get_registration_or_404(event_id, member_id):
    reg = MemberRegistration.query.filter_by(event_entity_id=event_id, member_id=member_id).first()
    if not reg:
        raise NotFound('Registration not found for this event')
    return reg


@ce_bp.route('/event/<int:event_id>/start_progress', methods=['POST'])
def start_progress(event_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    
    reg = _get_registration_or_404(event_id, user.id)
    if not reg.started_at:
        reg.started_at = datetime.now(timezone.utc)
        in_progress_status = get_registration_status('in_progress', 'in_progress', 'กำลังเรียน', 'is-info')
        reg.status_id = in_progress_status.id
        db.session.add(reg)
        db.session.commit()
    flash(texts.get('progress_started', 'Progress started.'), 'success')
    return redirect(url_for('continuing_edu.course_detail' if reg.event_entity.event_type=='course' else 'continuing_edu.webinar_detail', course_id=event_id if reg.event_entity.event_type=='course' else None, webinar_id=event_id if reg.event_entity.event_type=='webinar' else None, lang=lang))


@ce_bp.route('/event/<int:event_id>/complete_progress', methods=['POST'])
def complete_progress(event_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    reg = _get_registration_or_404(event_id, user.id)
   
    if not reg.completed_at:
        reg.completed_at = datetime.now(timezone.utc)
    completed_status = get_registration_status('completed', 'completed', 'สำเร็จแล้ว', 'is-success')
    reg.status_id = completed_status.id
    # Optionally accept assessment result
    passed = request.form.get('passed') or request.args.get('passed')
    if passed is not None:
        reg.assessment_passed = True if str(passed).lower() in ('1','true','yes','y','passed') else False
    # Issue certificate if completed and passed AND payment approved
    if reg.assessment_passed:
        pending = get_certificate_status('pending', 'รอดำเนินการ', 'is-info')
        reg.certificate_status_id = pending.id
        approved = can_issue_certificate(reg)
        if approved:
            issue_certificate(reg, lang=lang, base_url=request.base_url)
            flash(texts.get('certificate_issued', 'Certificate issued.'), 'success')
        else:
            db.session.add(reg)
            db.session.commit()
            flash(texts.get('payment_not_approved', 'Certificate requires approved payment.'), 'warning')
    else:
        db.session.add(reg)
        db.session.commit()
        flash(texts.get('progress_completed', 'Progress completed.'), 'success')
    return redirect(url_for('continuing_edu.course_detail' if reg.event_entity.event_type=='course' else 'continuing_edu.webinar_detail', course_id=event_id if reg.event_entity.event_type=='course' else None, webinar_id=event_id if reg.event_entity.event_type=='webinar' else None, lang=lang))


@ce_bp.route('/certificate/<int:reg_id>/pdf')
def certificate_pdf(reg_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    reg = MemberRegistration.query.get_or_404(reg_id)
    if reg.member_id != user.id:
        flash(texts.get('not_allowed', 'Not allowed.'), 'danger')
        return redirect(url_for('continuing_edu.my_registrations', lang=lang))
    # If already generated, redirect to stored location
    if reg.certificate_url:
        url = reg.certificate_presigned_url()
        return redirect(url or reg.certificate_url)
    if HTML is None:
        flash('PDF rendering library is not available on server.', 'danger')
        return redirect(url_for('continuing_edu.my_registrations', lang=lang))
    # Generate on the fly
    html = render_template('continueing_edu/certificate_pdf.html', reg=reg, event=reg.event_entity, member=reg.member, current_lang=lang)
    pdf = HTML(string=html, base_url=request.base_url).write_pdf()
   
    filename = f"certificate_{reg.member_id}_{reg.event_entity_id}.pdf"
    return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': f'inline; filename="{filename}"'})


@ce_bp.route('/certificate/<int:reg_id>/view')
def certificate_view(reg_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    reg = MemberRegistration.query.get_or_404(reg_id)
    if reg.member_id != user.id:
        flash(texts.get('not_allowed', 'Not allowed.'), 'danger')
        return redirect(url_for('continuing_edu.my_registrations', lang=lang))
    return render_template('continueing_edu/certificate_view.html', reg=reg, event=reg.event_entity, member=reg.member, current_lang=lang)


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
