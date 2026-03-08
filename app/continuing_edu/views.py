
from app.staff.models import StaffAccount
from werkzeug.security import check_password_hash


from werkzeug.security import generate_password_hash

from flask import  render_template, request, jsonify, flash, redirect, url_for, make_response, session, Response, current_app

from . import ce_bp
from .models import (
    CECertificateType,
    db,
    CEMember,
    CEEventEntity,
    CEEntityCategory,
    CEMemberRegistration,
    CEEventRegistrationFee,
    CERegisterPayment,
    CEContinuingInvoice,
    CERegisterPaymentStatus,
    CERegistrationStatus,
    CEOrganization,
    CEOrganizationType,
    CEOccupation,
    CEMemberAddress,
    CEMemberType,
    CEGender,
    CEAgeRange,
    CESpeakerProfile,
    CEEventSpeaker,
    CESatisfactionSurveyResponse,
    CESatisfactionSurveyAccessToken,
)
from app.comhealth.models import ComHealthOrg
from sqlalchemy import or_, and_, func
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound

from app.main import mail, csrf
from flask_mail import Message
try:
    from weasyprint import HTML
except Exception:
    HTML = None

import os, secrets, time
import hashlib
import re
from urllib.parse import urljoin, urlparse
from requests_oauthlib import OAuth2Session
from datetime import datetime, timezone, timedelta
from itsdangerous.url_safe import URLSafeTimedSerializer as TimedJSONWebSignatureSerializer
from itsdangerous.exc import SignatureExpired, BadSignature

from werkzeug.utils import secure_filename
from textwrap import shorten

from . import translations as tr  # Import translations from local package
import arrow
from .status_utils import get_registration_status, get_certificate_status
from .certificate_utils import (
    issue_certificate,
    can_issue_certificate,
    build_certificate_context,
    build_satisfaction_form_name,
    requires_post_course_survey,
)

current_lang = 'en'  # This should be dynamically set based on user preference or request
SATISFACTION_TOKEN_SALT = 'ce-satisfaction-access-v1'
SATISFACTION_TOKEN_MAX_AGE = int(os.getenv('CE_SATISFACTION_TOKEN_MAX_AGE', '1209600'))  # 14 days
CHECKIN_QR_PREFIX = 'CECHECKIN:'
CHECKIN_TOKEN_SALT = 'continuing-edu-checkin'


def _satisfaction_serializer():
    secret_key = current_app.config.get('SECRET_KEY') or os.getenv('SECRET_KEY') or 'ce-dev-secret'
    return TimedJSONWebSignatureSerializer(secret_key=secret_key, salt=SATISFACTION_TOKEN_SALT)


def _checkin_serializer():
    secret_key = current_app.config.get('SECRET_KEY') or os.getenv('SECRET_KEY') or 'ce-dev-secret'
    return TimedJSONWebSignatureSerializer(secret_key=secret_key, salt=CHECKIN_TOKEN_SALT)


def _build_attendance_checkin_payload(registration: CEMemberRegistration) -> str:
    token = _checkin_serializer().dumps(
        {
            'registration_id': registration.id,
            'event_id': registration.event_entity_id,
        }
    )
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return f'{CHECKIN_QR_PREFIX}{token}'


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


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

    address_names = _safe_list('address_name[]')  # New field
    address_types = _safe_list('address_type[]')
    address_type_custom = _safe_list('address_type_other[]')
    address_labels = _safe_list('address_label[]')
    line1_list = _safe_list('address_line1[]')
    line2_list = _safe_list('address_line2[]')
    city_list = _safe_list('address_city[]')
    state_list = _safe_list('address_state[]')
    postal_list = _safe_list('address_postal[]')
    subdistrict_list = _safe_list('address_subdistrict[]')  # Thai address field
    district_list = _safe_list('address_district[]')  # Thai address field
    province_list = _safe_list('address_province[]')  # New field
    zipcode_list = _safe_list('address_zipcode[]')  # New field
    country_codes = _safe_list('address_country[]')
    country_other = _safe_list('address_country_other[]')

    max_len = max(
        len(address_names),
        len(address_types),
        len(address_type_custom),
        len(address_labels),
        len(line1_list),
        len(line2_list),
        len(city_list),
        len(state_list),
        len(postal_list),
        len(subdistrict_list),
        len(district_list),
        len(province_list),
        len(zipcode_list),
        len(country_codes),
        len(country_other),
    ) if form else 0

    entries = []
    for idx in range(max_len):
        # Use address_name as label if provided, otherwise use address_labels
        address_name = address_names[idx] if idx < len(address_names) else ''
        address_label = address_labels[idx] if idx < len(address_labels) else ''
        final_label = address_name or address_label
        
        # Use province if provided, otherwise use state
        province = province_list[idx] if idx < len(province_list) else ''
        state = state_list[idx] if idx < len(state_list) else ''
        final_state = province or state
        
        # Use zipcode if provided, otherwise use postal
        zipcode = zipcode_list[idx] if idx < len(zipcode_list) else ''
        postal = postal_list[idx] if idx < len(postal_list) else ''
        final_postal = zipcode or postal
        
        # Get subdistrict and district (Thai address fields)
        subdistrict = subdistrict_list[idx] if idx < len(subdistrict_list) else ''
        district = district_list[idx] if idx < len(district_list) else ''

        line2 = line2_list[idx] if idx < len(line2_list) else ''
        city = city_list[idx] if idx < len(city_list) else ''
        final_line2 = line2 or subdistrict
        final_city = city or district
        
        entries.append({
            'type': address_types[idx] if idx < len(address_types) else '',
            'type_other': address_type_custom[idx] if idx < len(address_type_custom) else '',
            'label': final_label,
            'line1': line1_list[idx] if idx < len(line1_list) else '',
            'line2': final_line2,
            'city': final_city,
            'state': final_state,
            'province': final_state,
            'postal': final_postal,
            'zipcode': final_postal,
            'subdistrict': subdistrict,
            'district': district,
            'country_code': country_codes[idx] if idx < len(country_codes) else '',
            'country_other': country_other[idx] if idx < len(country_other) else '',
        })

    return entries


def get_current_user():
    user_id = session.get('member_id')
    if user_id:
        return CEMember.query.filter_by(id=user_id).first()
    return None


def _sync_member_legacy_address_fields(member: CEMember) -> None:
    """Keep legacy Member.address/province/zip_code/country in sync.

    The codebase still reads these fields in several places (invoice, exports, etc).
    Prefer billing address, then current, then first available.
    """
    if not member:
        return

    addresses = list(getattr(member, 'addresses', []) or [])
    if not addresses:
        member.address = None
        member.province = None
        member.zip_code = None
        member.country = None
        return

    preferred = None
    for addr in addresses:
        if (addr.address_type or '').lower() == 'billing':
            preferred = addr
            break
    if preferred is None:
        for addr in addresses:
            if (addr.address_type or '').lower() == 'current':
                preferred = addr
                break
    if preferred is None:
        preferred = addresses[0]

    member.address = preferred.line1
    member.province = preferred.state
    member.zip_code = preferred.postal_code
    member.country = preferred.country_name


def is_early_bird_active(event: CEEventEntity):
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)
    if event.early_bird_end and now > event.early_bird_end:
        return False
    if event.early_bird_start and now < event.early_bird_start:
        return False
    return bool(event.early_bird_start or event.early_bird_end)


def _price_for_member(event: CEEventEntity, member: CEMember):
    fee = None
    if member and member.member_type_id:
        fee = CEEventRegistrationFee.query.filter_by(event_entity_id=event.id, member_type_id=member.member_type_id).first()
    if not fee:
        return None, None
    eb_active = is_early_bird_active(event)
    price = fee.early_bird_price if (eb_active and fee.early_bird_price is not None) else fee.price
    return fee, price


def _event_max_participants(event: CEEventEntity) -> int | None:
    raw = getattr(event, 'max_participants', None)
    if raw in (None, ''):
        return None
    try:
        value = int(raw)
        return value if value > 0 else None
    except Exception:
        return None


def _event_active_registration_count(event_id: int) -> int:
    cancelled = or_(
        func.lower(func.coalesce(CERegistrationStatus.registration_status_code, '')).like('%cancel%'),
        func.lower(func.coalesce(CERegistrationStatus.name_en, '')).like('%cancel%'),
    )
    count = (
        db.session.query(func.count(CEMemberRegistration.id))
        .outerjoin(CERegistrationStatus, CEMemberRegistration.status_id == CERegistrationStatus.id)
        .filter(CEMemberRegistration.event_entity_id == event_id)
        .filter(~cancelled)
        .scalar()
    )
    return int(count or 0)


def _is_event_registration_full(event: CEEventEntity) -> tuple[bool, int | None, int]:
    max_participants = _event_max_participants(event)
    total_registered = _event_active_registration_count(event.id)
    if max_participants is None:
        return False, None, total_registered
    return total_registered >= max_participants, max_participants, total_registered

# --- Member Login ---
@ce_bp.route('/login', methods=['GET', 'POST'])
def login():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    next_url = request.args.get('next') or request.form.get('next')
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        print( f"Login attempt: email={email}, password={'*' * len(password)}" )
        
        if not email or not password:
            flash('กรุณากรอกอีเมลและรหัสผ่าน' if lang == 'th' else 'Please enter email and password', 'error')
            return render_template('continueing_edu/login.html', texts=texts, current_lang=lang, logged_in_user=get_current_user(), next=next_url)
        
        # Find member by email
        member = CEMember.query.filter_by(email=email).first()
        
        if not member:
            # Track failed login attempts
            failed_attempts = session.get('failed_login_attempts', 0) + 1
            session['failed_login_attempts'] = failed_attempts
            
            if failed_attempts >= 3:
                flash('คุณพยายามเข้าระบบโดยใช้รหัสผ่านไม่ถูกต้อง กรุณากดลืมรหัสผ่านเพื่อตั้งรหัสใหม่' if lang == 'th' 
                      else 'You have attempted to login with an incorrect password. Please click Forgot Password to reset your password.', 
                      'login_failed_limit')
                session['failed_login_attempts'] = 0  # Reset counter
            else:
                flash('อีเมลหรือรหัสผ่านไม่ถูกต้อง' if lang == 'th' else 'Invalid email or password', 'error')
            return render_template('continueing_edu/login.html', texts=texts, current_lang=lang, logged_in_user=get_current_user(), next=next_url)
        
        # Check password
        if not check_password_hash(member.password_hash, password):
            # Track failed login attempts
            failed_attempts = session.get('failed_login_attempts', 0) + 1
            session['failed_login_attempts'] = failed_attempts
            
            if failed_attempts >= 3:
                flash('คุณพยายามเข้าระบบโดยใช้รหัสผ่านไม่ถูกต้อง กรุณากดลืมรหัสผ่านเพื่อตั้งรหัสใหม่' if lang == 'th' 
                      else 'You have attempted to login with an incorrect password. Please click Forgot Password to reset your password.', 
                      'login_failed_limit')
                session['failed_login_attempts'] = 0  # Reset counter
            else:
                flash('อีเมลหรือรหัสผ่านไม่ถูกต้อง' if lang == 'th' else 'Invalid email or password', 'error')
            return render_template('continueing_edu/login.html', texts=texts, current_lang=lang, logged_in_user=get_current_user(), next=next_url)
        
        # Login successful - reset failed attempts counter
        session.pop('failed_login_attempts', None)
        session['member_id'] = member.id
        user = get_current_user()
        
        welcome_name = member.full_name_th or member.full_name_en or member.username
        flash(f"ยินดีต้อนรับ {welcome_name}!" if lang == 'th' else f"Welcome {welcome_name}!", 'success')
        
        return redirect(next_url or url_for('continuing_edu.index', lang=lang, logged_in_user=user))
    
    return render_template('continueing_edu/login.html', texts=texts, current_lang=lang, logged_in_user=get_current_user(), next=next_url)





# --- Member callback ---
@ce_bp.route('/callback')
def callback():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    flash('เข้าสู่ระบบสำเร็จ' if lang == 'th' else 'Logged in successfully.', 'success')
    return redirect(url_for('continuing_edu.index', lang=lang))


# --- Member Logout ---
@ce_bp.route('/logout')
def logout():
    lang = request.args.get('lang', 'en')
    session.pop('member_id', None)
    session.pop('username', None)
    flash('ออกจากระบบสำเร็จ' if lang == 'th' else 'Logged out successfully.', 'success')
    return redirect(url_for('continuing_edu.index', lang=lang))

# --- Test Google Sign-up ---
@ce_bp.route('/test-google-signup')
def test_google_signup():
    """Test page for Google Sign-up flow"""
    return render_template('continueing_edu/test_google_signup.html')

# --- Member Registration ---
@ce_bp.route('/register', methods=['GET', 'POST'])
def register():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    next_url = request.args.get('next') or request.form.get('next')

    form_values = request.form.to_dict() if request.method == 'POST' else {}
    address_entries = _collect_address_entries_from_form(request.form) if request.method == 'POST' else _default_address_entries()
    if not address_entries:
        address_entries = _default_address_entries()

    organization_types = CEOrganizationType.query.order_by(CEOrganizationType.name_en.asc()).all()
    occupations = CEOccupation.query.order_by(CEOccupation.name_en.asc()).all()
    organizations = CEOrganization.query.order_by(CEOrganization.name.asc()).limit(50).all()
    member_types = CEMemberType.query.order_by(CEMemberType.name_en.asc()).all()
    genders = CEGender.query.order_by(CEGender.id.asc()).all()
    age_ranges = CEAgeRange.query.order_by(CEAgeRange.id.asc()).all()
    google_client_id = os.getenv('GOOGLE_CLIENT_ID', '206836986017-1dctro1ehrqta2r91e5appn5j78spn9h.apps.googleusercontent.com')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = (request.form.get('email') or '').strip() or None
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        accept_privacy = bool(request.form.get('accept_privacy'))
        accept_terms = bool(request.form.get('accept_terms'))
        accept_news = bool(request.form.get('accept_news'))
        not_bot = (request.form.get('not_bot') or '').strip().lower()

        member_type_choice = (request.form.get('member_type_id') or '').strip()
        member_type_other = (request.form.get('member_type_other') or '').strip()
        # template names: age_range and gender
        age_ranges_choice = (request.form.get('age_range') or '').strip()
        genders_choice = (request.form.get('gender') or '').strip()

        member_type_id = member_type_choice
        age_range_id = age_ranges_choice
        gender_id = genders_choice
      
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

        # Validate full name (at least one language) as shown in the form
        full_name_th = (request.form.get('full_name_th') or '').strip()
        full_name_en = (request.form.get('full_name_en') or '').strip()
        if not (full_name_th or full_name_en):
            errors.append(texts.get('name_requirement', 'Please provide your name in Thai or English.'))

        # Organization and occupation are required by the form templates
        if not organization_name:
            errors.append(texts.get('organization_placeholder', 'Please provide an organization name.'))
        if not occupation_choice:
            errors.append(texts.get('occupation_label', 'Please select or specify an occupation.'))

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

        if username and CEMember.query.filter_by(username=username).first():
            errors.append(texts.get('register_error_exists', 'Username already exists.'))
        if email and CEMember.query.filter_by(email=email).first():
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
                'continueing_edu/register_modern.html',
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
                organization_type = (CEOrganizationType.query
                                     .filter(func.lower(CEOrganizationType.name_en) == lookup)
                                     .first())
                if not organization_type:
                    organization_type = (CEOrganizationType.query
                                         .filter(func.lower(CEOrganizationType.name_th) == lookup)
                                         .first())
                if not organization_type:
                    organization_type = CEOrganizationType(
                        name_en=organization_type_other,
                        name_th=organization_type_other,
                        is_user_defined=True,
                    )
                    db.session.add(organization_type)
                    db.session.flush()
            else:
                try:
                    organization_type = CEOrganizationType.query.get(int(organization_type_choice))
                except (ValueError, TypeError):
                    organization_type = None

        occupation = None
        if occupation_choice:
            if occupation_choice == 'other' and occupation_other:
                lookup = occupation_other.lower()
                occupation = (CEOccupation.query
                              .filter(func.lower(CEOccupation.name_en) == lookup)
                              .first())
                if not occupation:
                    occupation = (CEOccupation.query
                                  .filter(func.lower(CEOccupation.name_th) == lookup)
                                  .first())
                if not occupation:
                    occupation = CEOccupation(
                        name_en=occupation_other,
                        name_th=occupation_other,
                        is_user_defined=True,
                    )
                    db.session.add(occupation)
                    db.session.flush()
            else:
                try:
                    occupation = CEOccupation.query.get(int(occupation_choice))
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
            organization = (CEOrganization.query
                            .filter(func.lower(CEOrganization.name) == organization_name.lower())
                            .first())
            if not organization:
                organization = CEOrganization(
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

        # prepare nullable integer ids
        try:
            mt_id = int(member_type_id) if member_type_id else None
        except (ValueError, TypeError):
            mt_id = None
        try:
            ag_id = int(age_range_id) if age_range_id else None
        except (ValueError, TypeError):
            ag_id = None
        try:
            g_id = int(gender_id) if gender_id else None
        except (ValueError, TypeError):
            g_id = None

        member = CEMember(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            organization=organization,
            occupation=occupation,
            received_news=accept_news,
            full_name_th=full_name_th or None,
            full_name_en=full_name_en or None,
            phone_no=(request.form.get('phone_no') or None),
            member_type_id=mt_id,
            age_range_id=ag_id,
            gender_id=g_id,
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

            address = CEMemberAddress(
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

        # Final server-side validation using model helper
        if not member.is_profile_complete():
            db.session.rollback()
            flash(texts.get('register_error_complete_form', 'Please complete all required fields in the form.'), 'danger')
            return render_template(
                'continueing_edu/register_modern.html',
                texts=texts,
                current_lang=lang,
                form_values=form_values,
                organization_types=organization_types,
                occupations=occupations,
                organizations=organizations,
                address_entries=address_entries,
                country_options=COUNTRY_OPTIONS,
            )

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
        if next_url:
            session['register_next_url'] = next_url
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

        return render_template('continueing_edu/otp_verify.html', username=username, current_lang=lang, texts=texts, next=next_url)

    # Use modern template if requested
    use_modern = request.args.get('modern', '1') == '1'
    template = 'continueing_edu/register_modern.html' if use_modern else 'continueing_edu/register.html'
    
    return render_template(
        template,
        texts=texts,
        current_lang=lang,
        form_values=form_values,
        organization_types=organization_types,
        occupations=occupations,
        organizations=organizations,
        address_entries=address_entries,
        country_options=COUNTRY_OPTIONS,
        member_types=member_types,
        genders=genders,
        age_ranges=age_ranges,
        google_client_id=google_client_id,
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
        from .models import CEMember
        import random
        member = CEMember.query.filter_by(email=email).first()
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
        from .models import CEMember
        member = CEMember.query.filter_by(username=username).first()
        if member:
            member.is_verified = True  # You must add this field in your model/migration
            db.session.commit()
            
        # Get next_url from session
        next_url = session.pop('register_next_url', None)
        
        session.pop('otp_code', None)
        session.pop('otp_username', None)
        session.pop('otp_email', None)
        
        flash('ยืนยัน OTP สำเร็จ! สมัครสมาชิกสมบูรณ์' if lang == 'th' else 'OTP verification successful! Registration complete', 'success')
        
        # If there's a next_url, auto-login and redirect
        if next_url and member:
            session['member_id'] = member.id
            flash(f"ยินดีต้อนรับ {member.full_name_th or member.username}!" if lang == 'th' else f"Welcome {member.full_name_en or member.username}!", 'success')
            return redirect(next_url)
        
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
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash('กรุณากรอกอีเมล' if lang == 'th' else 'Please enter your email.', 'danger')
            return render_template('continueing_edu/forgot_password.html', current_lang=lang, texts=texts)
        from .models import CEMember
        user = CEMember.query.filter_by(email=email).first()
        if not user:
            # Don't reveal if email exists (security)
            flash('หากอีเมลนี้มีในระบบ คุณจะได้รับรหัส OTP' if lang == 'th' else 'If this email exists, you will receive an OTP code.', 'success')
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
        return redirect(url_for('continuing_edu.verify_reset_otp', lang=lang, username=user.username))
    return render_template('continueing_edu/forgot_password.html', current_lang=lang, texts=texts)


# --- Verify Reset OTP (Step 2 of 3) ---
@ce_bp.route('/verify_reset_otp', methods=['GET', 'POST'])
def verify_reset_otp():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    username = request.args.get('username') or session.get('reset_username')
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        otp_input = request.form.get('otp_code', '').strip()
        
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
            return render_template('continueing_edu/verify_reset_otp.html', current_lang=lang, texts=texts, username=username)
        
        # OTP is valid - generate reset token
        import secrets
        reset_token = secrets.token_urlsafe(32)
        session['reset_token'] = reset_token
        session['reset_token_expires'] = int(time.time()) + 900  # 15 minutes
        
        flash('ยืนยัน OTP สำเร็จ' if lang == 'th' else 'OTP verified successfully.', 'success')
        return redirect(url_for('continuing_edu.set_new_password', lang=lang, token=reset_token))
    
    return render_template('continueing_edu/verify_reset_otp.html', current_lang=lang, texts=texts, username=username)


# --- Set New Password (Step 3 of 3) ---
@ce_bp.route('/set_new_password', methods=['GET', 'POST'])
def set_new_password():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    token = request.args.get('token') or request.form.get('reset_token')
    
    # Verify reset token
    expected_token = session.get('reset_token')
    token_exp = session.get('reset_token_expires')
    
    import time
    if not expected_token or token != expected_token:
        flash('โทเคนรีเซ็ตรหัสผ่านไม่ถูกต้อง' if lang == 'th' else 'Invalid reset token.', 'danger')
        return redirect(url_for('continuing_edu.forgot_password', lang=lang))
    
    if token_exp and time.time() > token_exp:
        flash('โทเคนหมดอายุแล้ว' if lang == 'th' else 'Reset token has expired.', 'danger')
        return redirect(url_for('continuing_edu.forgot_password', lang=lang))
    
    if request.method == 'POST':
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')
        
        if not new_pw or new_pw != confirm_pw:
            flash('รหัสผ่านใหม่ไม่ตรงกัน' if lang == 'th' else 'New passwords do not match.', 'danger')
            return render_template('continueing_edu/set_new_password.html', current_lang=lang, texts=texts, reset_token=token)
        
        # Validate password strength
        import re
        if len(new_pw) < 8:
            flash('รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร' if lang == 'th' else 'Password must be at least 8 characters.', 'danger')
            return render_template('continueing_edu/set_new_password.html', current_lang=lang, texts=texts, reset_token=token)
        
        if not re.search(r'[A-Z]', new_pw):
            flash('รหัสผ่านต้องมีตัวพิมพ์ใหญ่อย่างน้อย 1 ตัว' if lang == 'th' else 'Password must contain at least one uppercase letter.', 'danger')
            return render_template('continueing_edu/set_new_password.html', current_lang=lang, texts=texts, reset_token=token)
        
        if not re.search(r'[a-z]', new_pw):
            flash('รหัสผ่านต้องมีตัวพิมพ์เล็กอย่างน้อย 1 ตัว' if lang == 'th' else 'Password must contain at least one lowercase letter.', 'danger')
            return render_template('continueing_edu/set_new_password.html', current_lang=lang, texts=texts, reset_token=token)
        
        if not re.search(r'\d', new_pw):
            flash('รหัสผ่านต้องมีตัวเลขอย่างน้อย 1 ตัว' if lang == 'th' else 'Password must contain at least one number.', 'danger')
            return render_template('continueing_edu/set_new_password.html', current_lang=lang, texts=texts, reset_token=token)
        
        if not re.search(r'[@$!%*?&]', new_pw):
            flash('รหัสผ่านต้องมีอักขระพิเศษอย่างน้อย 1 ตัว (@$!%*?&)' if lang == 'th' else 'Password must contain at least one special character (@$!%*?&).', 'danger')
            return render_template('continueing_edu/set_new_password.html', current_lang=lang, texts=texts, reset_token=token)
        
        # Update password
        from .models import CEMember
        username = session.get('reset_username')
        user = CEMember.query.filter_by(username=username).first()
        
        if not user:
            flash('ไม่พบบัญชี' if lang == 'th' else 'Account not found.', 'danger')
            return redirect(url_for('continuing_edu.forgot_password', lang=lang))
        
        user.password_hash = generate_password_hash(new_pw)
        db.session.add(user)
        db.session.commit()
        
        # Clear all reset session data
        session.pop('reset_otp', None)
        session.pop('reset_username', None)
        session.pop('reset_email', None)
        session.pop('reset_expires', None)
        session.pop('reset_token', None)
        session.pop('reset_token_expires', None)
        
        flash('เปลี่ยนรหัสผ่านเรียบร้อยแล้ว กรุณาเข้าสู่ระบบด้วยรหัสผ่านใหม่' if lang == 'th' else 'Your password has been reset successfully. Please login with your new password.', 'success')
        return redirect(url_for('continuing_edu.login', lang=lang))
    
    return render_template('continueing_edu/set_new_password.html', current_lang=lang, texts=texts, reset_token=token)


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
        from .models import CEMember
        user = CEMember.query.filter_by(username=username).first()
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

    user = CEMember.query.filter_by(google_sub=sub).first()
    if not user and email:
        user = CEMember.query.filter_by(email=email).first()
        if user and not user.google_sub:
            user.google_sub = sub
    if not user:
        pwd = secrets.token_urlsafe(12)
        user = CEMember(username=email.split('@')[0] if email else f'user_{sub[:6]}',
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


@ce_bp.route('/google-signup-callback', methods=['POST'])
def google_signup_callback():
    """Handle Google Sign-up with JWT ID token"""
    import jwt
    from jwt import PyJWKClient
    
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    
    credential = request.form.get('credential')
    if not credential:
        flash(texts.get('google_error', 'Google authentication failed'), 'danger')
        return redirect(url_for('continuing_edu.register', lang=lang))
    
    try:
        # Verify JWT token
        google_client_id = os.getenv('GOOGLE_CLIENT_ID', '206836986017-1dctro1ehrqta2r91e5appn5j78spn9h.apps.googleusercontent.com')
        jwks_url = 'https://www.googleapis.com/oauth2/v3/certs'
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(credential)
        
        data = jwt.decode(
            credential,
            signing_key.key,
            algorithms=['RS256'],
            audience=google_client_id,
        )
        
        google_sub = data.get('sub')
        email = data.get('email')
        name = data.get('name')
        email_verified = data.get('email_verified', False)
        
        if not email_verified:
            flash(texts.get('email_not_verified', 'กรุณายืนยันอีเมล Google ของคุณก่อน' if lang == 'th' else 'Please verify your Google email first'), 'warning')
            return redirect(url_for('continuing_edu.register', lang=lang))
        
        # Check if user already exists
        existing_user = CEMember.query.filter(
            or_(CEMember.google_sub == google_sub, CEMember.email == email)
        ).first()
        
        if existing_user:
            # User exists, just log them in
            if not existing_user.google_sub:
                existing_user.google_sub = google_sub
                existing_user.google_connected_at = datetime.now(timezone.utc)
                db.session.commit()
            
            session['member_id'] = existing_user.id
            flash(texts.get('login_success', 'เข้าสู่ระบบสำเร็จ' if lang == 'th' else 'Login successful!'), 'success')
            return redirect(url_for('continuing_edu.index', lang=lang))
        
        # Create new user account
        username = email.split('@')[0] if email else f'google_{google_sub[:8]}'
        # Check if username exists, make it unique
        base_username = username
        counter = 1
        while CEMember.query.filter_by(username=username).first():
            username = f'{base_username}{counter}'
            counter += 1
        
        pwd = secrets.token_urlsafe(16)
        new_member = CEMember(
            username=username,
            email=email,
            password_hash=generate_password_hash(pwd),
            full_name_en=name,
            google_sub=google_sub,
            google_connected_at=datetime.now(timezone.utc),
            is_verified=True,  # Google emails are pre-verified
            policy_accepted=True,
            terms_condition_accepted=True,
        )
        
        db.session.add(new_member)
        db.session.commit()
        
        session['member_id'] = new_member.id
        session['needs_profile_completion'] = True
        
        flash(texts.get('google_signup_success', 'ลงทะเบียนสำเร็จ! กรุณากรอกข้อมูลส่วนตัวเพิ่มเติม' if lang == 'th' else 'Registration successful! Please complete your profile'), 'success')
        return redirect(url_for('continuing_edu.complete_profile', lang=lang))
        
    except Exception as e:
        flash(f'{texts.get("google_error", "Google authentication error")}: {str(e)}', 'danger')
        return redirect(url_for('continuing_edu.register', lang=lang))


@ce_bp.route('/complete-profile', methods=['GET', 'POST'])
def complete_profile():
    """Profile completion page after Google sign-up"""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    
    member_id = session.get('member_id')
    if not member_id:
        flash(texts.get('login_required', 'กรุณาเข้าสู่ระบบ' if lang == 'th' else 'Please log in'), 'warning')
        return redirect(url_for('continuing_edu.login', lang=lang))
    
    member = CEMember.query.get(member_id)
    if not member:
        session.pop('member_id', None)
        flash(texts.get('member_not_found', 'ไม่พบข้อมูลสมาชิก' if lang == 'th' else 'Member not found'), 'danger')
        return redirect(url_for('continuing_edu.register', lang=lang))
    
    if request.method == 'POST':
        # Update member profile
        member.member_type_id = request.form.get('member_type_id') or None
        member.gender_id = request.form.get('gender_id') or None
        member.age_range_id = request.form.get('age_range_id') or None
        member.full_name_th = request.form.get('full_name_th') or None
        member.phone_no = request.form.get('phone_no') or None
        member.organization_id = request.form.get('organization_id') or None
        member.occupation_id = request.form.get('occupation_id') or None
        member.country = request.form.get('country') or None
        
        # Handle address (persist to MemberAddress; also sync legacy fields)
        address_line1 = (request.form.get('address_line1') or '').strip()
        address_province = (request.form.get('address_province') or '').strip() or None
        address_zipcode = (request.form.get('address_zipcode') or '').strip() or None
        country_name = (request.form.get('country') or '').strip() or None
        if address_line1:
            # Upsert a "current" address as the primary one for simple flows.
            current_addr = (CEMemberAddress.query
                            .filter_by(member_id=member.id, address_type='current')
                            .order_by(CEMemberAddress.id.asc())
                            .first())
            if not current_addr:
                current_addr = CEMemberAddress(
                    member=member,
                    address_type='current',
                    label=None,
                    line1=address_line1,
                    line2=None,
                    city=None,
                    state=address_province,
                    postal_code=address_zipcode,
                    country_code=None,
                    country_name=country_name,
                )
                db.session.add(current_addr)
            else:
                current_addr.line1 = address_line1
                current_addr.state = address_province
                current_addr.postal_code = address_zipcode
                current_addr.country_name = country_name
            _sync_member_legacy_address_fields(member)
        
        db.session.commit()
        session.pop('needs_profile_completion', None)
        
        flash(texts.get('profile_updated', 'อัปเดตข้อมูลสำเร็จ' if lang == 'th' else 'Profile updated successfully'), 'success')
        return redirect(url_for('continuing_edu.index', lang=lang))
    
    # GET request - show form
    member_types = CEMemberType.query.order_by(CEMemberType.name_en.asc()).all()
    genders = CEGender.query.order_by(CEGender.id.asc()).all()
    age_ranges = CEAgeRange.query.order_by(CEAgeRange.id.asc()).all()
    organizations = CEOrganization.query.order_by(CEOrganization.name.asc()).limit(50).all()
    occupations = CEOccupation.query.order_by(CEOccupation.name_en.asc()).all()
    
    return render_template(
        'continueing_edu/complete_profile.html',
        texts=texts,
        current_lang=lang,
        member=member,
        member_types=member_types,
        genders=genders,
        age_ranges=age_ranges,
        organizations=organizations,
        occupations=occupations,
    )


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

    # Backward-compat: older accounts may have legacy address fields but no MemberAddress rows.
    # Create a starter "current" address so multi-address management works immediately.
    if (not user.addresses or len(user.addresses) == 0) and (user.address or user.province or user.zip_code or user.country):
        line1 = (user.address or '').strip()
        if line1:
            starter = CEMemberAddress(
                member=user,
                address_type='current',
                label=None,
                line1=line1,
                line2=None,
                city=None,
                state=(user.province or None),
                postal_code=(user.zip_code or None),
                country_code=None,
                country_name=(user.country or None),
            )
            db.session.add(starter)
            db.session.commit()
    return render_template(
        'continueing_edu/account_settings.html',
        user=user,
        logged_in_user=user,
        texts=texts,
        current_lang=lang,
        addresses=list(user.addresses or []),
    )


@ce_bp.route('/account/profile', methods=['POST'])
def account_update_profile():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    # Basic editable fields (legacy keys)
    for field in ['email','full_name_en','full_name_th','phone_no','country','title_name_en','title_name_th']:
        if field in request.form:
            setattr(user, field, request.form.get(field))
    db.session.add(user)
    db.session.commit()
    flash(texts.get('profile_updated', 'Profile updated.'), 'success')
    return redirect(url_for('continuing_edu.account_settings', lang=lang))


@ce_bp.route('/account/addresses/new', methods=['GET', 'POST'])
def account_address_new():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))

    if request.method == 'POST':
        address_type = (request.form.get('address_type') or 'current').strip() or 'current'
        label = (request.form.get('label') or '').strip() or None
        line1 = (request.form.get('line1') or '').strip()
        line2 = (request.form.get('line2') or '').strip() or None

        # Thai address autocomplete fields (same keys as register_modern)
        subdistrict = (request.form.get('address_subdistrict[]') or request.form.get('address_subdistrict') or '').strip() or None
        district = (request.form.get('address_district[]') or request.form.get('address_district') or '').strip() or None
        province = (request.form.get('address_province[]') or request.form.get('address_province') or request.form.get('state') or '').strip() or None
        zipcode = (request.form.get('address_zipcode[]') or request.form.get('address_zipcode') or request.form.get('postal_code') or '').strip() or None

        city = district
        state = province
        postal_code = zipcode
        if not line2 and subdistrict:
            line2 = subdistrict

        if not line1:
            flash(texts.get('address_required_message', 'Please provide at least one address.'), 'danger')
            return render_template(
                'continueing_edu/account_address_form.html',
                texts=texts,
                current_lang=lang,
                mode='new',
                address=None,
                form_values=request.form,
                country_options=COUNTRY_OPTIONS,
            )

        country_code = (request.form.get('country_code') or request.form.get('address_country') or '').strip() or None
        country_other = (request.form.get('country_other') or request.form.get('address_country_other') or '').strip() or None
        if country_code == 'OTHER' and country_other:
            country_name = country_other
            country_code_value = None
        elif country_code:
            country_name = next((item['name'] for item in COUNTRY_OPTIONS if item['code'] == country_code), country_code)
            country_code_value = country_code
        else:
            country_name = (request.form.get('country_name') or '').strip() or None
            country_code_value = None

        addr = CEMemberAddress(
            member=user,
            address_type=address_type,
            label=label,
            line1=line1,
            line2=line2,
            city=city,
            state=state,
            postal_code=postal_code,
            country_code=country_code_value,
            country_name=country_name,
        )
        db.session.add(addr)
        _sync_member_legacy_address_fields(user)
        db.session.commit()
        flash(texts.get('profile_updated', 'Saved.'), 'success')
        return redirect(url_for('continuing_edu.account_settings', lang=lang))

    return render_template(
        'continueing_edu/account_address_form.html',
        texts=texts,
        current_lang=lang,
        mode='new',
        address=None,
        form_values=None,
        country_options=COUNTRY_OPTIONS,
    )


@ce_bp.route('/account/addresses/<int:address_id>/edit', methods=['GET', 'POST'])
def account_address_edit(address_id: int):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))

    addr = CEMemberAddress.query.filter_by(id=address_id, member_id=user.id).first()
    if not addr:
        raise NotFound()

    if request.method == 'POST':
        address_type = (request.form.get('address_type') or addr.address_type or 'current').strip() or 'current'
        label = (request.form.get('label') or '').strip() or None
        line1 = (request.form.get('line1') or '').strip()
        line2 = (request.form.get('line2') or '').strip() or None

        # Thai address autocomplete fields (same keys as register_modern)
        subdistrict = (request.form.get('address_subdistrict[]') or request.form.get('address_subdistrict') or '').strip() or None
        district = (request.form.get('address_district[]') or request.form.get('address_district') or '').strip() or None
        province = (request.form.get('address_province[]') or request.form.get('address_province') or request.form.get('state') or '').strip() or None
        zipcode = (request.form.get('address_zipcode[]') or request.form.get('address_zipcode') or request.form.get('postal_code') or '').strip() or None

        city = district
        state = province
        postal_code = zipcode
        if not line2 and subdistrict:
            line2 = subdistrict

        if not line1:
            flash(texts.get('address_required_message', 'Please provide at least one address.'), 'danger')
            return render_template(
                'continueing_edu/account_address_form.html',
                texts=texts,
                current_lang=lang,
                mode='edit',
                address=addr,
                form_values=request.form,
                country_options=COUNTRY_OPTIONS,
            )

        country_code = (request.form.get('country_code') or request.form.get('address_country') or '').strip() or None
        country_other = (request.form.get('country_other') or request.form.get('address_country_other') or '').strip() or None
        if country_code == 'OTHER' and country_other:
            country_name = country_other
            country_code_value = None
        elif country_code:
            country_name = next((item['name'] for item in COUNTRY_OPTIONS if item['code'] == country_code), country_code)
            country_code_value = country_code
        else:
            country_name = (request.form.get('country_name') or '').strip() or None
            country_code_value = None

        addr.address_type = address_type
        addr.label = label
        addr.line1 = line1
        addr.line2 = line2
        addr.city = city
        addr.state = state
        addr.postal_code = postal_code
        addr.country_code = country_code_value
        addr.country_name = country_name

        _sync_member_legacy_address_fields(user)
        db.session.add(addr)
        db.session.commit()
        flash(texts.get('profile_updated', 'Saved.'), 'success')
        return redirect(url_for('continuing_edu.account_settings', lang=lang))

    return render_template(
        'continueing_edu/account_address_form.html',
        texts=texts,
        current_lang=lang,
        mode='edit',
        address=addr,
        form_values=None,
        country_options=COUNTRY_OPTIONS,
    )


@ce_bp.route('/account/addresses/<int:address_id>/delete', methods=['POST'])
def account_address_delete(address_id: int):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))

    addr = CEMemberAddress.query.filter_by(id=address_id, member_id=user.id).first()
    if not addr:
        raise NotFound()

    db.session.delete(addr)
    db.session.flush()
    _sync_member_legacy_address_fields(user)
    db.session.commit()
    flash(texts.get('profile_updated', 'Deleted.'), 'success')
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


@ce_bp.route('/api/organizations_by_type/<int:org_type_id>', methods=['GET'])
def get_organizations_by_type(org_type_id):
    """API endpoint to fetch organizations based on organization type.
    For type_id 7 or 1: returns client organizations from comhealth_orgs
    For other types: returns from organizations table
    """
    try:
        if org_type_id in [7, 1]:
            # Fetch from client organizations (comhealth_orgs)
            orgs = ComHealthOrg.query.order_by(ComHealthOrg.name.asc()).all()
            result = [{'id': org.id, 'name': org.name, 'source': 'client'} for org in orgs]
        else:
            # Fetch from regular organizations with matching type
            orgs = CEOrganization.query.filter_by(organization_type_id=org_type_id).order_by(CEOrganization.name.asc()).all()
            result = [{'id': org.id, 'name': org.name, 'source': 'regular'} for org in orgs]
        
        return jsonify({'success': True, 'organizations': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ce_bp.route('/why_register')
def why_register():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    return render_template('continueing_edu/why_register.html', texts=texts, current_lang=lang)


@ce_bp.route('/all-events')
def all_events():
    """Landing page: List all event entities."""
    events = CEEventEntity.query.order_by(CEEventEntity.created_at.desc()).all()
    texts = tr[current_lang]
    user = get_current_user()
    registered_ids = set()
    if user:
        regs = CEMemberRegistration.query.with_entities(CEMemberRegistration.event_entity_id).filter_by(member_id=user.id).all()
        registered_ids = {r[0] for r in regs}
    return render_template('continueing_edu/all_events.html', events=events, active_menu='All Events', texts=texts, lang=current_lang, logged_in_user=user, registered_ids=registered_ids)


@ce_bp.route('/', endpoint='index', methods=['GET'])
def dashboard():
    """Landing page: List all event entities (replaces course/webinar lists)."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    events = CEEventEntity.query.order_by(CEEventEntity.created_at.desc()).all()
    user = get_current_user()
    registered_ids = set()
    if user:
        regs = CEMemberRegistration.query.with_entities(CEMemberRegistration.event_entity_id).filter_by(member_id=user.id).all()
        registered_ids = {r[0] for r in regs}
    # Optional filter: show only events the user registered for
    registered_only = request.args.get('registered_only') in ('1', 'true', 'yes')
    if registered_only and user:
        events = [e for e in events if e.id in registered_ids]

    hero_query = CEEventEntity.query
    is_active_column = getattr(CEEventEntity, 'is_active', None)
    if is_active_column is not None:
        hero_query = hero_query.filter(is_active_column.is_(True))
    hero_events = (hero_query
                   .order_by(CEEventEntity.created_at.desc())
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
    courses = CEEventEntity.query.filter_by(event_type='course').all()
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
    webinars = CEEventEntity.query.filter_by(event_type='webinar').all()
    return render_template('continueing_edu/webinars.html',
                           active_menu='Webinar List',
                           webinars=webinars,
                           texts=texts,
                           current_lang=lang)

@ce_bp.route('/course_detail/<int:course_id>')
def course_detail(course_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    course = CEEventEntity.query.filter_by(id=course_id, event_type='course').first_or_404()
    user = get_current_user()
    already_registered = False
    approved_payment = False
    if user:
        reg = CEMemberRegistration.query.filter_by(member_id=user.id, event_entity_id=course.id).first()
        already_registered = reg is not None
        if reg:
            from app.continuing_edu.models import RegisterPaymentStatus, RegisterPayment
            ap = RegisterPayment.query \
                .join(RegisterPaymentStatus, RegisterPayment.payment_status_ref) \
                .filter(
                    RegisterPayment.member_id == user.id,
                    RegisterPayment.event_entity_id == course.id,
                    (
                        (RegisterPaymentStatus.register_payment_status_code.in_(['approved', 'paid'])) |
                        (RegisterPaymentStatus.name_en.in_(['approved', 'paid']))
                    )
                ).order_by(RegisterPayment.id.desc()).first()
            approved_payment = ap is not None
    _, max_seats, total_registered = _is_event_registration_full(course)
    return render_template(
        'continueing_edu/course_detail.html',
        course=course,
        texts=texts,
        current_lang=lang,
        logged_in_user=user,
        already_registered=already_registered,
        approved_payment=approved_payment,
        max_seats=max_seats,
        total_registered=total_registered,
    )


@ce_bp.route('/course/<int:course_id>/learn')
def course_learn(course_id):
    """Member-only learning view: requires registration + approved/paid payment."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    course = CEEventEntity.query.filter_by(id=course_id, event_type='course').first_or_404()
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang, next=request.full_path))

    reg = CEMemberRegistration.query.filter_by(member_id=user.id, event_entity_id=course.id).first()
    if not reg:
        flash(texts.get('not_registered', 'You are not registered for this course.'), 'warning')
        return redirect(url_for('continuing_edu.course_detail', course_id=course.id, lang=lang))

    from app.continuing_edu.models import RegisterPaymentStatus, RegisterPayment
    ap = RegisterPayment.query \
        .join(RegisterPaymentStatus, RegisterPayment.payment_status_ref) \
        .filter(
            RegisterPayment.member_id == user.id,
            RegisterPayment.event_entity_id == course.id,
            (
                (RegisterPaymentStatus.register_payment_status_code.in_(['approved', 'paid'])) |
                (RegisterPaymentStatus.name_en.in_(['approved', 'paid']))
            )
        ).order_by(RegisterPayment.id.desc()).first()
    if not ap:
        flash(texts.get('payment_not_approved', 'This page requires an approved payment.'), 'warning')
        return redirect(url_for('continuing_edu.course_detail', course_id=course.id, lang=lang))

    survey_required = requires_post_course_survey(reg)
    satisfaction_form_name = build_satisfaction_form_name(course, lang=lang)

    return render_template(
        'continueing_edu/course_learn.html',
        course=course,
        registration=reg,
        survey_required=survey_required,
        satisfaction_form_name=satisfaction_form_name,
        texts=texts,
        current_lang=lang,
        logged_in_user=user,
        member=user,
    )

@ce_bp.route('/webinar_detail/<int:webinar_id>')
def webinar_detail(webinar_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    webinar = CEEventEntity.query.filter_by(id=webinar_id, event_type='webinar').first_or_404()
    user = get_current_user()
    already_registered = False
    approved_payment = False
    current_registration = None
    satisfaction_form_name = build_satisfaction_form_name(webinar, lang=lang)
    if user:
        reg = CEMemberRegistration.query.filter_by(member_id=user.id, event_entity_id=webinar.id).first()
        current_registration = reg
        already_registered = reg is not None
        if reg:
            from app.continuing_edu.models import CERegisterPaymentStatus, CERegisterPayment
            ap = CERegisterPayment.query \
                .join(CERegisterPaymentStatus, CERegisterPayment.payment_status_ref) \
                .filter(CERegisterPayment.member_id == user.id,
                        CERegisterPayment.event_entity_id == webinar.id,
                        (
                            (func.lower(CERegisterPaymentStatus.register_payment_status_code).in_(['approved', 'paid'])) |
                            (func.lower(CERegisterPaymentStatus.name_en).in_(['approved', 'paid']))
                        )).first()
            approved_payment = ap is not None
    _, max_seats, total_registered = _is_event_registration_full(webinar)
    return render_template(
        'continueing_edu/webinar_detail.html',
        webinar=webinar,
        texts=texts,
        current_lang=lang,
        logged_in_user=user,
        already_registered=already_registered,
        approved_payment=approved_payment,
        max_seats=max_seats,
        total_registered=total_registered,
        current_registration=current_registration,
        survey_required=bool(current_registration and requires_post_course_survey(current_registration)),
        satisfaction_form_name=satisfaction_form_name,
    )


# --- Event Registration Confirmation Page ---
@ce_bp.route('/event/<int:event_id>/register', methods=['GET'])
def register_event(event_id):
    """Show registration confirmation page before actual registration"""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    event = CEEventEntity.query.get_or_404(event_id)
    member = get_current_user()

    print(f"[REGISTER_EVENT] Event ID: {event_id}, Member ID: {member.id if member else 'None'}")
    
    # Redirect to login if not authenticated
    if not member:
        print(f"[REGISTER_EVENT] Member not logged in, redirecting to login")
        flash(texts.get('login_required', 'กรุณาเข้าสู่ระบบก่อนลงทะเบียน' if lang == 'th' else 'Please login to register.'), 'warning')
        next_url = url_for('continuing_edu.register_event', event_id=event_id, lang=lang)
        return redirect(url_for('continuing_edu.login', lang=lang, next=next_url))

    # Check if member has member_type_id set
    if not member.member_type_id:
        print(f"[REGISTER_EVENT] Member has no member_type_id, redirecting to complete profile")
        flash(texts.get('complete_profile_required', 'กรุณาเลือกประเภทสมาชิกก่อนลงทะเบียน' if lang == 'th' else 'Please complete your profile (member type) before registering.'), 'warning')
        return redirect(url_for('continuing_edu.complete_profile', lang=lang, next=url_for('continuing_edu.register_event', event_id=event_id, lang=lang)))
    
    # Already registered?
    existing = CEMemberRegistration.query.filter_by(member_id=member.id, event_entity_id=event.id).first()
    if existing:
        print(f"[REGISTER_EVENT] Already registered - Registration ID: {existing.id}")
        flash(texts.get('already_registered', 'You are already registered for this event.'), 'info')
        return redirect(url_for('continuing_edu.course_detail' if event.event_type=='course' else 'continuing_edu.webinar_detail', course_id=event.id if event.event_type=='course' else None, webinar_id=event.id if event.event_type=='webinar' else None, lang=lang))

    is_full, _, _ = _is_event_registration_full(event)
    if is_full:
        flash(texts.get('seats_full', 'ที่นั่งเต็มแล้ว' if lang == 'th' else 'Seats Full'), 'danger')
        return redirect(url_for('continuing_edu.course_detail' if event.event_type=='course' else 'continuing_edu.webinar_detail', course_id=event.id if event.event_type=='course' else None, webinar_id=event.id if event.event_type=='webinar' else None, lang=lang))

    fee, price = _price_for_member(event, member)
    print(f"[REGISTER_EVENT] Member type: {member.member_type_id}, Fee: {fee}, Price: {price}")
    
    if not fee:
        print(f"[REGISTER_EVENT] No fee found for member type: {member.member_type_id}, redirecting back")
        flash(texts.get('no_fee_defined', 'ไม่พบข้อมูลค่าลงทะเบียนสำหรับประเภทสมาชิกของคุณ กรุณาติดต่อผู้ดูแลระบบ' if lang == 'th' else 'No registration fee defined for your member type. Please contact administrator.'), 'danger')
        return redirect(url_for('continuing_edu.course_detail' if event.event_type=='course' else 'continuing_edu.webinar_detail', course_id=event.id if event.event_type=='course' else None, webinar_id=event.id if event.event_type=='webinar' else None, lang=lang))

    # Check if early bird is active
    is_early_bird = is_early_bird_active(event)

    print(f"[REGISTER_EVENT] Showing confirmation page for event: {event.title_en}")
    # Show confirmation page
    return render_template('continueing_edu/registration_confirmation.html', 
                         event=event, 
                         member=member, 
                         fee=fee, 
                         price=price,
                         is_early_bird=is_early_bird,
                         texts=texts, 
                         current_lang=lang,
                         logged_in_user=member)


# --- Confirm Registration (POST) ---
@ce_bp.route('/event/<int:event_id>/confirm-registration', methods=['POST'])
def confirm_registration(event_id):
    """Process the actual registration after confirmation"""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    event = CEEventEntity.query.get_or_404(event_id)
    member = get_current_user()
    
    print(f"[CONFIRM_REGISTRATION] Event ID: {event_id}, Member: {member.id if member else 'None'}")
    
    if not member:
        flash(texts.get('login_required', 'กรุณาเข้าสู่ระบบก่อนลงทะเบียน' if lang == 'th' else 'Please login to register.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    
    # Check if already registered
    existing = CEMemberRegistration.query.filter_by(member_id=member.id, event_entity_id=event.id).first()
    if existing:
        print(f"[CONFIRM_REGISTRATION] Already registered - Registration ID: {existing.id}")
        latest_payment = (
            CERegisterPayment.query
            .filter_by(member_id=member.id, event_entity_id=event.id)
            .order_by(CERegisterPayment.id.desc())
            .first()
        )
        if latest_payment and _can_member_update_payment_proof(latest_payment):
            flash(
                texts.get(
                    'already_registered_continue_payment',
                    'คุณลงทะเบียนแล้ว กรุณาดำเนินการชำระเงินต่อ' if lang == 'th'
                    else 'You are already registered. Please continue payment.',
                ),
                'info',
            )
            method = (latest_payment.payment_method or 'promptpay').strip().lower()
            if method == 'bank_transfer':
                return redirect(
                    url_for(
                        'continuing_edu.view_invoice',
                        payment_id=latest_payment.id,
                        lang=lang,
                        next=url_for('continuing_edu.my_payments', lang=lang),
                    )
                )
            return redirect(
                url_for(
                    'continuing_edu.payment_process',
                    payment_id=latest_payment.id,
                    payment_method=method or 'promptpay',
                    lang=lang,
                )
            )

        flash(texts.get('already_registered', 'คุณได้ลงทะเบียนแล้ว' if lang == 'th' else 'You are already registered for this event.'), 'info')
        return redirect(url_for('continuing_edu.course_detail' if event.event_type=='course' else 'continuing_edu.webinar_detail', course_id=event.id if event.event_type=='course' else None, webinar_id=event.id if event.event_type=='webinar' else None, lang=lang))

    is_full, _, _ = _is_event_registration_full(event)
    if is_full:
        flash(texts.get('seats_full', 'ที่นั่งเต็มแล้ว' if lang == 'th' else 'Seats Full'), 'danger')
        return redirect(url_for('continuing_edu.course_detail' if event.event_type=='course' else 'continuing_edu.webinar_detail', course_id=event.id if event.event_type=='course' else None, webinar_id=event.id if event.event_type=='webinar' else None, lang=lang))
    
    fee, price = _price_for_member(event, member)
    print(f"[CONFIRM_REGISTRATION] Member type: {member.member_type_id}, Fee: {fee}, Price: {price}")
    
    if not fee:
        print(f"[CONFIRM_REGISTRATION] No fee found for member type: {member.member_type_id}")
        flash(texts.get('no_fee_defined', 'ไม่พบข้อมูลค่าลงทะเบียนสำหรับประเภทสมาชิกของคุณ' if lang == 'th' else 'No registration fee defined for your member type.'), 'danger')
        return redirect(url_for('continuing_edu.course_detail' if event.event_type=='course' else 'continuing_edu.webinar_detail', course_id=event.id if event.event_type=='course' else None, webinar_id=event.id if event.event_type=='webinar' else None, lang=lang))

    if request.method == 'POST':
        # Get payment method from form
        payment_method = request.form.get('payment_method', 'promptpay')
        terms_accepted = request.form.get('terms_accepted')
        
        print(f"[CONFIRM_REGISTRATION] Creating registration and payment...")
        print(f"[CONFIRM_REGISTRATION] Payment method: {payment_method}, Terms accepted: {terms_accepted}")
        
        # Validate terms acceptance
        if not terms_accepted:
            flash(texts.get('terms_required', 'กรุณายอมรับข้อตกลงและเงื่อนไข' if lang == 'th' else 'Please accept the terms and conditions.'), 'warning')
            return redirect(url_for('continuing_edu.register_event', event_id=event_id, lang=lang))
        
        # Create registration and pending payment
        registered_status = get_registration_status('registered', 'registered', 'ลงทะเบียนแล้ว', 'is-info')
        pending_cert = get_certificate_status('pending', 'รอดำเนินการ', 'is-info')
        reg = CEMemberRegistration(member_id=member.id, event_entity_id=event.id,
                                   status_id=registered_status.id,
                                   certificate_status_id=pending_cert.id)
        db.session.add(reg)
        # create invoice record to be used across payment methods
        try:
            inv = CEContinuingInvoice(member_id=member.id, event_entity_id=event.id, amount=price, status='pending')
            db.session.add(inv)
            db.session.commit()
            # set invoice number after we have id
            inv.invoice_no = f"INV{inv.id:06d}"
            db.session.commit()
        except Exception:
            db.session.rollback()
            inv = None

        # Ensure pending status exists; never rely on hard-coded ID fallback.
        pending = _get_or_create_payment_status(
            'pending',
            name_th='รอดำเนินการ',
            css_badge='is-light',
        )
        pay = CERegisterPayment(
            member_id=member.id,
            event_entity_id=event.id,
            payment_status_id=pending.id,
            payment_amount=price,
            invoice_id=inv.id if inv else None,
            payment_method=payment_method,
        )
        db.session.add(pay)
        db.session.commit()
        print(f"[CONFIRM_REGISTRATION] Registration created - Reg ID: {reg.id}, Payment ID: {pay.id}")
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
                        # Build invoice context for PDF (seller info + VAT breakdown)
                        invoice = getattr(pay, 'invoice', None)
                        invoice_no = None
                        if invoice and getattr(invoice, 'invoice_no', None):
                            invoice_no = invoice.invoice_no
                        else:
                            fallback_id = (invoice.id if invoice else pay.id)
                            invoice_no = f"INV{int(fallback_id):06d}"
                        vat_rate_raw = os.getenv('INVOICE_VAT_RATE', os.getenv('VAT_RATE', '0'))
                        try:
                            vat_rate = float(vat_rate_raw) if vat_rate_raw not in (None, '') else 0.0
                        except Exception:
                            vat_rate = 0.0
                        vat_included = (os.getenv('INVOICE_VAT_INCLUDED', 'false').strip().lower() in ('1', 'true', 'yes', 'y'))
                        amount_total = float(getattr(pay, 'payment_amount', 0) or 0)
                        if vat_rate > 0:
                            if vat_included:
                                subtotal = amount_total / (1.0 + vat_rate)
                                vat_amount = amount_total - subtotal
                                total = amount_total
                            else:
                                subtotal = amount_total
                                vat_amount = subtotal * vat_rate
                                total = subtotal + vat_amount
                        else:
                            subtotal = amount_total
                            vat_amount = 0.0
                            total = amount_total
                        invoice_meta = {
                            'invoice_no': invoice_no,
                            'invoice_date': (invoice.created_at if invoice and getattr(invoice, 'created_at', None) else pay.payment_date),
                            'due_date': (invoice.created_at if invoice and getattr(invoice, 'created_at', None) else pay.payment_date),
                            'due_days': 0,
                            'vat_rate': vat_rate,
                            'vat_included': vat_included,
                            'subtotal': round(subtotal, 2),
                            'vat_amount': round(vat_amount, 2),
                            'total': round(total, 2),
                        }
                        seller = {
                            'name_th': os.getenv('INVOICE_SELLER_NAME_TH', ''),
                            'name_en': os.getenv('INVOICE_SELLER_NAME_EN', ''),
                            'address_th': os.getenv('INVOICE_SELLER_ADDRESS_TH', ''),
                            'address_en': os.getenv('INVOICE_SELLER_ADDRESS_EN', ''),
                            'tax_id': os.getenv('INVOICE_SELLER_TAX_ID', ''),
                            'branch': os.getenv('INVOICE_SELLER_BRANCH', ''),
                            'phone': os.getenv('INVOICE_SELLER_PHONE', ''),
                            'email': os.getenv('INVOICE_SELLER_EMAIL', ''),
                        }

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
                            invoice_meta=invoice_meta,
                            seller=seller,
                        )
                        pdf_bytes = HTML(string=html, base_url=request.host_url).write_pdf()
                        msg.attach(f"invoice_{invoice_no}.pdf", 'application/pdf', pdf_bytes)
                    except Exception:
                        pass
                mail.send(msg)
        except Exception:
            pass
        flash(texts.get('registration_success', 'Registration submitted. Payment pending.'), 'success')
        # Route user to the immediate next payment screen:
        # - PromptPay: QR payment page
        # - Bank transfer: invoice with bank details
        if payment_method == 'bank_transfer':
            print(f"[CONFIRM_REGISTRATION] Redirecting to invoice for payment ID: {pay.id}")
            return redirect(
                url_for(
                    'continuing_edu.view_invoice',
                    payment_id=pay.id,
                    lang=lang,
                    next=url_for('continuing_edu.my_payments', lang=lang),
                )
            )

        print(f"[CONFIRM_REGISTRATION] Redirecting to payment page for payment ID: {pay.id}, method: {payment_method}")
        return redirect(url_for('continuing_edu.payment_process', payment_id=pay.id, payment_method=payment_method, lang=lang))

    return render_template('continueing_edu/register_event.html', event=event, member=member, fee=fee, price=price, texts=texts, current_lang=lang)


@ce_bp.route('/payment/<int:payment_id>/process')
def payment_process(payment_id):
    """Display payment processing page based on payment method"""
    lang = request.args.get('lang', 'en')
    payment_method = request.args.get('payment_method', 'promptpay')
    texts = tr.get(lang, tr['en'])
    
    # Get current user
    member = get_current_user()
    if not member:
        flash(texts.get('login_required', 'กรุณาเข้าสู่ระบบก่อนดำเนินการ' if lang == 'th' else 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    
    # Get payment record
    payment = CERegisterPayment.query.get_or_404(payment_id)
    
    # Verify ownership
    if payment.member_id != member.id:
        flash(texts.get('not_allowed', 'คุณไม่ได้รับอนุญาตให้เข้าถึงหน้านี้' if lang == 'th' else 'You are not allowed to access this page.'), 'danger')
        return redirect(url_for('continuing_edu.index', lang=lang))

    if not _can_member_update_payment_proof(payment):
        flash(texts.get('message_payments_locked', 'Payment is approved. Editing proof is locked.'), 'warning')
        return redirect(request.referrer or url_for('continuing_edu.my_payments', lang=lang))
    
    # Get event details
    event = payment.event_entity

 
    # SCB gateway configuration (if enabled)
    BILLERID = os.environ.get('BILLERID')
    REF3 = os.environ.get('SCB_REF3')
    SCB_INQUIRY_LAST_AT = os.environ.get('QR30_INQUIRY')

    # payment_gateway = (os.environ.get('PAYMENT_GATEWAY') or '').lower()
   
    # Fallback QR generator (non-SCB): should be an IMAGE/QR generator URL
    payment_qr_url = os.environ.get('QR30_INQUIRY')

    # Prepare defaults so template variables always exist
    scb_qr_image = None
    scb_ref1 = None
    scb_ref2 = None
    qr_error = None

    def _ensure_scb_record(ref1: str, ref2: str, amount: float):
        try:
            from app.scb_payment_service.models import ScbPaymentRecord
            record = ScbPaymentRecord.query.filter_by(bill_payment_ref1=ref1, bill_payment_ref2=ref2).first()
            if not record:
                record = ScbPaymentRecord(
                    bill_payment_ref1=ref1,
                    bill_payment_ref2=ref2,
                    bill_payment_ref3=(REF3 or os.environ.get('SCB_REF3') or os.environ.get('REF3')),
                    service='Training',
                    customer1=str(member.id),
                    customer2=str(payment.id),
                    amount=amount,
                )
                db.session.add(record)
                db.session.commit()
            # allow to payment

            else:
                if record.transcation_date_time:
                     flash(f'คุณได้ชำระเงินแล้ว' if lang == 'th' 
                      else f'[PAYMENT_PROCESS] SCB Payment Record already paid: Ref1={ref1}, Ref2={ref2}, Amount={record.amount}, Transaction DateTime={record.transcation_date_time}', 
                      'info')    
           
        except Exception as e:
            print(f"[PAYMENT_PROCESS] Failed to ensure ScbPaymentRecord: {e}")

    # Attempt SCB QR generation only when SCB gateway is enabled
    if payment_method == 'promptpay':
        try:
            from app.scb_payment_service.views import generate_qrcode
            invoice = getattr(payment, 'invoice', None)
            if not invoice and payment.invoice_id:
                from .models import CEContinuingInvoice as _CI
                invoice = _CI.query.get(payment.invoice_id)
            scb_ref1 = invoice.invoice_no if invoice and invoice.invoice_no else (f"INV{(invoice.id if invoice else payment.id):06d}")
            scb_ref2 = "TRAINING"
            ref3 = REF3 or 'MUMTEDU'
            expire_dt = arrow.utcnow().to('Asia/Bangkok').shift(hours=+1).format('YYYY-MM-DD HH:mm:ss')
            amount = float(payment.payment_amount) if payment.payment_amount is not None else 0.0

            _ensure_scb_record(scb_ref1, scb_ref2, amount)

            qrcode_data = generate_qrcode(amount, ref1=scb_ref1, ref2=scb_ref2, ref3=ref3, expired_at=expire_dt)
            print(f"[PAYMENT_PROCESS] SCB QR Return Data: {qrcode_data}")
            if qrcode_data:
                scb_qr_image = qrcode_data['qrImage']
            else:
                qr_error = f"SCB QR API error: {qrcode_data}"
        except Exception as e:
            qr_error = f"SCB QR generation exception: {e}"

    return render_template('continueing_edu/payment_process.html',
                         payment=payment,
                         event=event,
                         member=member,
                         payment_method=payment_method,
                         texts=texts,
                         current_lang=lang,
                         payment_qr_url=payment_qr_url,
                         promptpay_id=BILLERID,
                       
                         scb_qr_image=scb_qr_image,
                         scb_ref1=scb_ref1,
                         scb_ref2=scb_ref2,
                         qr_error=qr_error,
                         logged_in_user=member)


_SCB_INQUIRY_LAST_AT = {}



def _is_paid_status(payment: 'CERegisterPayment') -> bool:
    st = getattr(payment, 'payment_status_ref', None)
    code = (getattr(st, 'register_payment_status_code', None) or getattr(st, 'name_en', None) or '').lower()
    return code in ('paid', 'approved')


@ce_bp.route('/payment/<int:payment_id>/status', methods=['GET'])
def payment_status_api(payment_id):
    """Return current payment status for frontend polling.

    If SCB gateway is enabled and webhook hasn't arrived, may perform an inquiry after a threshold.
    """
    member = get_current_user()
    if not member:
        return jsonify({'message': 'login required'}), 403

    payment = CERegisterPayment.query.get_or_404(payment_id)
    if payment.member_id != member.id:
        return jsonify({'message': 'not allowed'}), 403

    payment_gateway = (os.environ.get('PAYMENT_GATEWAY') or '').lower()
    allow_inquiry = request.args.get('allow_inquiry', '1') in ('1', 'true', 'yes')
    inquiry_after = int(os.environ.get('PAYMENT_INQUIRY_AFTER_SECONDS') or 45)
    inquiry_min_interval = int(os.environ.get('PAYMENT_INQUIRY_MIN_INTERVAL_SECONDS') or 15)

    def _maybe_inquire_scb():
        if not allow_inquiry or payment_gateway != 'scb':
            return
        if _is_paid_status(payment):
            return
        payment_dt = getattr(payment, 'payment_date', None)
        if not payment_dt:
            return
        age_seconds = (datetime.now(payment_dt.tzinfo) - payment_dt).total_seconds() if getattr(payment_dt, 'tzinfo', None) else (datetime.now() - payment_dt).total_seconds()
        if age_seconds < inquiry_after:
            return
        last_at = _SCB_INQUIRY_LAST_AT.get(payment.id)
        if last_at and (datetime.now() - last_at).total_seconds() < inquiry_min_interval:
            return

        # Determine refs consistent with QR generation
        invoice = getattr(payment, 'invoice', None)
        if not invoice and payment.invoice_id:
            from .models import CEContinuingInvoice as _CI
            invoice = _CI.query.get(payment.invoice_id)
        ref1 = invoice.invoice_no if invoice and invoice.invoice_no else (f"INV{(invoice.id if invoice else payment.id):06d}")
        ref2 = f"RP{payment.id}"

        try:
            from app.scb_payment_service.models import ScbPaymentRecord
            rec = ScbPaymentRecord.query.filter_by(bill_payment_ref1=ref1, bill_payment_ref2=ref2).first()
            if not rec:
                rec = ScbPaymentRecord(bill_payment_ref1=ref1, bill_payment_ref2=ref2, service='continuing_edu', amount=float(payment.payment_amount or 0.0))
                db.session.add(rec)
                db.session.commit()

            # Call SCB inquiry API
            auth_url = os.environ.get('SCB_AUTH_URL')
            inquiry_url = os.environ.get('QR30_INQUIRY')
            app_key = os.environ.get('SCB_APP_KEY')
            app_secret = os.environ.get('SCB_APP_SECRET')
            biller_id = os.environ.get('BILLERID')
            if not (auth_url and inquiry_url and app_key and app_secret and biller_id):
                return

            import uuid
            import requests

            headers = {
                'Content-Type': 'application/json',
                'requestUId': str(uuid.uuid4()),
                'resourceOwnerId': app_key,
            }
            token_resp = requests.post(auth_url, headers=headers, json={'applicationKey': app_key, 'applicationSecret': app_secret}, timeout=15)
            token_resp.raise_for_status()
            access_token = token_resp.json().get('data', {}).get('accessToken')
            if not access_token:
                return
            headers['authorization'] = f'Bearer {access_token}'

            tx_date = (getattr(rec, 'created_datetime', None) or payment_dt).strftime('%Y-%m-%d')
            resp = requests.get(
                inquiry_url,
                params={'billerId': biller_id, 'reference1': ref1, 'transactionDate': tx_date, 'eventCode': '00300100'},
                headers=headers,
                timeout=15,
            )
            data = resp.json() if resp is not None else {}
            payload = data.get('data') if isinstance(data, dict) else None
            if payload:
                # Best-effort: set a transaction_id if inquiry returns one
                txn_id = None
                if isinstance(payload, dict):
                    txn_id = payload.get('transactionId') or payload.get('transaction_id') or payload.get('txnId')
                    trans_date = payload.get('transDate')
                    trans_time = payload.get('transTime')
                    if not txn_id and trans_date and trans_time:
                        txn_id = f"INQ-{ref2}-{trans_date}{trans_time}"

                if txn_id and not payment.transaction_id:
                    payment.transaction_id = txn_id
                if not _is_paid_status(payment):
                    _mark_payment_paid_and_notify(payment.id, lang=request.args.get('lang', 'en'))
        except Exception as e:
            print(f"[PAYMENT_STATUS] SCB inquiry failed: {e}")
        finally:
            _SCB_INQUIRY_LAST_AT[payment.id] = datetime.now()

    _maybe_inquire_scb()
    # reload status after inquiry
    payment = CERegisterPayment.query.get(payment_id) or payment

    st = getattr(payment, 'payment_status_ref', None)
    status_code = (getattr(st, 'register_payment_status_code', None) or getattr(st, 'name_en', None) or '').lower()
    status_name = getattr(st, 'name_en', None) or getattr(st, 'name_th', None) or status_code or 'unknown'
    is_paid = _is_paid_status(payment)

    return jsonify({
        'payment_id': payment.id,
        'status_code': status_code,
        'status_name': status_name,
        'is_paid': is_paid,
        'transaction_id': payment.transaction_id,
        'paid_at': payment.payment_date.isoformat() if (is_paid and getattr(payment, 'payment_date', None)) else None,
        'next_url': url_for('continuing_edu.my_payments', lang=request.args.get('lang', 'en')) if is_paid else None,
    })


def _payment_proof_is_public_url_or_path(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    return (
        value.startswith('http://')
        or value.startswith('https://')
        or value.startswith('//')
        or value.startswith('/')
    )


def _payment_status_code(payment: CERegisterPayment) -> str:
    st = getattr(payment, 'payment_status_ref', None)
    return (
        (getattr(st, 'register_payment_status_code', None) or getattr(st, 'name_en', None) or '')
        .strip()
        .lower()
    )


def _get_or_create_payment_status(
    code: str,
    *,
    name_th: str | None = None,
    css_badge: str | None = None,
) -> CERegisterPaymentStatus:
    normalized = (code or '').strip().lower()
    st = CERegisterPaymentStatus.query.filter(
        (func.lower(CERegisterPaymentStatus.register_payment_status_code) == normalized) |
        (func.lower(CERegisterPaymentStatus.name_en) == normalized)
    ).first()
    if st:
        if not st.register_payment_status_code:
            st.register_payment_status_code = normalized
            db.session.add(st)
            db.session.flush()
        return st

    st = CERegisterPaymentStatus(
        name_en=normalized,
        name_th=name_th or normalized,
        css_badge=css_badge or 'is-light',
        register_payment_status_code=normalized,
    )
    db.session.add(st)
    db.session.flush()
    return st


def _can_member_update_payment_proof(payment: CERegisterPayment) -> bool:
    # Block only finalized statuses so misconfigured intermediate statuses
    # do not prevent users from reaching the payment page after registration.
    return _payment_status_code(payment) not in {'approved', 'paid', 'cancelled', 'canceled'}


def _can_member_upload_payment_proof(payment: CERegisterPayment) -> bool:
    """Allow proof upload for any payment status."""
    return True


def _set_status_on_proof_submission(payment: CERegisterPayment) -> None:
    """Move to submitted for re-review unless payment is already finalized."""
    if _payment_status_code(payment) in {'approved', 'paid', 'cancelled', 'canceled'}:
        return

    submitted = _get_or_create_payment_status(
        'submitted',
        name_th='ส่งหลักฐานแล้ว',
        css_badge='is-info',
    )
    payment.payment_status_id = submitted.id


def _delete_old_payment_proof_reference(old_reference: str | None) -> None:
    """Best-effort cleanup for previous proof (local file or S3 key)."""
    if not old_reference:
        return

    if old_reference.startswith('/static/'):
        try:
            local_path = os.path.join(current_app.root_path, old_reference.lstrip('/'))
            if os.path.isfile(local_path):
                os.remove(local_path)
        except Exception:
            pass
        return

    if _payment_proof_is_public_url_or_path(old_reference):
        return

    try:
        from app.main import s3, S3_BUCKET_NAME
        if S3_BUCKET_NAME:
            s3.delete_object(Bucket=S3_BUCKET_NAME, Key=old_reference)
    except Exception:
        pass


def _store_payment_proof_file(file_storage, payment_id: int) -> str:
    """Store payment proof on S3 when configured, otherwise fallback to local static uploads."""
    from app.main import allowed_file

    if not file_storage or not file_storage.filename:
        raise ValueError('missing_file')
    if not allowed_file(file_storage.filename):
        raise ValueError('invalid_file_type')

    safe_name = secure_filename(file_storage.filename)
    ext = safe_name.rsplit('.', 1)[-1].lower() if '.' in safe_name else 'dat'
    content_type = file_storage.mimetype or 'application/octet-stream'
    payload = file_storage.read()
    if not payload:
        raise ValueError('empty_file')

    timestamp = int(time.time())
    nonce = secrets.token_hex(4)
    filename = f"proof_{timestamp}_{nonce}.{ext}"
    s3_key = f"continuing_edu/payments/{payment_id}/{filename}"

    # Try S3 first if bucket configured.
    try:
        from app.main import s3, S3_BUCKET_NAME
        if S3_BUCKET_NAME:
            s3.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_key,
                Body=payload,
                ContentType=content_type,
            )
            return s3_key
    except Exception:
        # Fallback to local below.
        pass

    # Local fallback for development/non-S3 environments.
    relative_dir = os.path.join('uploads', 'continuing_edu', 'payments', str(payment_id))
    absolute_dir = os.path.join(current_app.static_folder, relative_dir)
    os.makedirs(absolute_dir, exist_ok=True)
    absolute_file = os.path.join(absolute_dir, filename)

    with open(absolute_file, 'wb') as output:
        output.write(payload)

    return url_for('static', filename=f"{relative_dir}/{filename}")


@ce_bp.route('/payment/<int:payment_id>/upload-slip', methods=['POST'])
def upload_payment_slip(payment_id):
    """Upload payment slip for verification"""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    
    # Get current user
    member = get_current_user()
    if not member:
        flash(texts.get('login_required', 'กรุณาเข้าสู่ระบบก่อนดำเนินการ' if lang == 'th' else 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    
    # Get payment record
    payment = CERegisterPayment.query.get_or_404(payment_id)
    
    # Verify ownership
    if payment.member_id != member.id:
        flash(texts.get('not_allowed', 'คุณไม่ได้รับอนุญาตให้เข้าถึงหน้านี้' if lang == 'th' else 'You are not allowed to access this page.'), 'danger')
        return redirect(url_for('continuing_edu.index', lang=lang))
    
    file = request.files.get('slip')
    if not file or file.filename == '':
        flash(texts.get('proof_required', 'Please provide a payment proof file.'), 'danger')
        return redirect(request.referrer or url_for('continuing_edu.my_payments', lang=lang))

    try:
        old_reference = payment.payment_proof_url
        new_reference = _store_payment_proof_file(file, payment.id)

        payment.payment_proof_url = new_reference
        _set_status_on_proof_submission(payment)
        db.session.add(payment)
        db.session.commit()

        if old_reference and old_reference != new_reference:
            _delete_old_payment_proof_reference(old_reference)

        # Send notification email to member that proof was uploaded
        try:
            subj = texts.get('slip_uploaded', 'Payment slip uploaded')
            invoice_link = url_for('continuing_edu.view_invoice', payment_id=payment.id, lang=lang, _external=True)
            body = (f"{texts.get('email_registered_for', 'Registered for')}: {payment.event_entity.title_en or payment.event_entity.title_th}\n"
                    f"{texts.get('email_amount', 'Amount')}: {payment.payment_amount} THB\n"
                    f"{texts.get('email_status', 'Status')}: {texts.get('status_submitted', 'Submitted')}\n\n"
                    f"{texts.get('email_invoice', 'Invoice')}: {invoice_link}\n")
            email_html = render_template('continueing_edu/_slip_uploaded_email.html', payment=payment, event=payment.event_entity, member=member, texts=texts, current_lang=lang)
            msg = Message(subject=subj, body=body, html=email_html, recipients=[member.email]) if getattr(member, 'email', None) else None
            if msg:
                mail.send(msg)
        except Exception:
            pass

        flash(texts.get('proof_received', 'Payment proof submitted.'), 'success')
    except Exception as e:
        print(f"Error uploading slip: {e}")
        flash(texts.get('upload_error', 'Error uploading file.'), 'danger')
    
    return redirect(request.referrer or url_for('continuing_edu.my_payments', lang=lang))


@ce_bp.route('/payment/webhook/mock', methods=['POST'])
def mock_payment_webhook():
    """Mock webhook to simulate payment provider callback for development.
    Accepts JSON with either `billPaymentRef2`, `payment_ref` or `payment_id`.
    If `billPaymentRef2` like `RP{payment.id}` is provided, it maps back to the RegisterPayment.
    """
    data = request.get_json(silent=True) or request.form or {}
    ref2 = data.get('billPaymentRef2') or data.get('payment_ref') or data.get('payment_id')
    if not ref2:
        return jsonify({'message': 'payment reference required (billPaymentRef2 or payment_id)'}), 400

    # support multiple reference formats: INV{invoice_id}, RP{payment_id}, or plain payment id
    payment = None
    m_inv = re.search(r'INV(\d+)', str(ref2))
    if m_inv:
        inv_id = int(m_inv.group(1))
        invoice = CEContinuingInvoice.query.get(inv_id)
        if not invoice:
            return jsonify({'message': 'invoice not found'}), 404
        payment = CERegisterPayment.query.filter_by(invoice_id=invoice.id).first()
    else:
        m = re.search(r'RP(\d+)', str(ref2))
        if m:
            payment_id = int(m.group(1))
            payment = CERegisterPayment.query.get(payment_id)
        else:
            try:
                payment_id = int(str(ref2))
                payment = CERegisterPayment.query.get(payment_id)
            except Exception:
                return jsonify({'message': 'invalid payment reference format'}), 400
    if not payment:
        return jsonify({'message': 'payment not found'}), 404

    # mark as paid and notify using helper
    try:
        _mark_payment_paid_and_notify(payment.id, request.args.get('lang', 'en'))
    except Exception:
        return jsonify({'message': 'failed to mark payment'}), 500
    return jsonify({'message': 'ok', 'payment_id': payment.id})


def _mark_payment_paid_and_notify(payment_id, lang='en'):
    """Helper to mark a RegisterPayment as paid and send notification email.
    Intended for internal use by mock webhook and admin test page.
    """
    """Mark payment as paid and send notification email to member."""

    texts = tr.get(lang, tr['en'])
    payment = CERegisterPayment.query.get(payment_id)
    if not payment:
        raise ValueError('payment not found')
    paid_status = _get_or_create_payment_status(
        'paid',
        name_th='ชำระแล้ว',
        css_badge='is-success',
    )
    payment.payment_status_id = paid_status.id
    payment.payment_date = datetime.now()
    db.session.add(payment)
    db.session.commit()

    # send notification
    member = CEMember.query.get(payment.member_id)
    subj = texts.get('payment_success', 'Payment successful!')
    invoice_link = url_for('continuing_edu.view_invoice', payment_id=payment.id, lang=lang, _external=True)
    payments_link = url_for('continuing_edu.my_payments', lang=lang, _external=True)
    body = (f"{texts.get('email_registered_for', 'Registered for')}: {payment.event_entity.title_en or payment.event_entity.title_th}\n"
            f"{texts.get('email_amount', 'Amount')}: {payment.payment_amount} THB\n"
            f"{texts.get('email_status', 'Status')}: {texts.get('status_paid', 'Paid')}\n\n"
            f"{texts.get('email_invoice', 'Invoice')}: {invoice_link}\n"
            f"{texts.get('email_my_payments', 'My payments')}: {payments_link}\n")
    email_html = render_template('continueing_edu/_payment_success_email.html', payment=payment, event=payment.event_entity, member=member, texts=texts, current_lang=lang)
    msg = Message(subject=subj, body=body, html=email_html, recipients=[member.email]) if getattr(member, 'email', None) else None
    if msg:
        if HTML is not None:
            try:
                payment_qr_url = os.environ.get('PAYMENT_QR_URL')
                promptpay_id = os.environ.get('PROMPTPAY_ID')
                bank_info = os.environ.get('BANK_INFO')
                payment_instructions = os.environ.get('PAYMENT_INSTRUCTIONS')
                html = render_template(
                    'continueing_edu/invoice.html',
                    payment=payment,
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
                msg.attach(f"invoice_INV-{payment.id}.pdf", 'application/pdf', pdf_bytes)
            except Exception:
                pass
        mail.send(msg)



@ce_bp.route('/admin/test-payment', methods=['GET', 'POST'])
def admin_test_payment():
    """Admin-only small page to trigger mock payment webhook locally.
    Access controlled by environment variable `DEV_PAYMENT_ADMINS` which is a comma-separated list of allowed emails.
    """
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    allowed_env = os.environ.get('DEV_PAYMENT_ADMINS')
    allowed = []
    if allowed_env:
        allowed = [e.strip().lower() for e in allowed_env.split(',') if e.strip()]

    if not user or (allowed and (not getattr(user, 'email', '').lower() in allowed)):
        flash('Not allowed', 'danger')
        return redirect(url_for('continuing_edu.index', lang=lang))

    result = None
    if request.method == 'POST':
        payment_ref = request.form.get('payment_ref')
        # reuse mock webhook parsing logic
        data = {'billPaymentRef2': payment_ref}
        # call internal function
        # accept INV{invoice_id}, RP{payment_id} or plain numeric payment id
        m_inv = re.search(r'INV(\d+)', str(payment_ref))
        m = re.search(r'RP(\d+)', str(payment_ref))
        pid = None
        try:
            if m_inv:
                inv_id = int(m_inv.group(1))
                inv = CEContinuingInvoice.query.get(inv_id)
                if not inv:
                    raise ValueError('invoice not found')
                payment_obj = CERegisterPayment.query.filter_by(invoice_id=inv.id).first()
                if not payment_obj:
                    raise ValueError('payment for invoice not found')
                pid = payment_obj.id
            elif m:
                pid = int(m.group(1))
            else:
                pid = int(str(payment_ref))
            _mark_payment_paid_and_notify(pid, lang=lang)
            result = {'status': 'ok', 'payment_id': pid}
        except Exception as e:
            result = {'status': 'error', 'error': str(e)}

    return render_template('continueing_edu/admin_test_payment.html', result=result, texts=texts, current_lang=lang)


@ce_bp.route('/payment/<int:payment_id>/process-credit-card', methods=['POST'])
def process_credit_card(payment_id):
    """Process credit card payment"""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    
    # Get current user
    member = get_current_user()
    if not member:
        flash(texts.get('login_required', 'กรุณาเข้าสู่ระบบก่อนดำเนินการ' if lang == 'th' else 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    
    # Get payment record
    payment = CERegisterPayment.query.get_or_404(payment_id)
    
    # Verify ownership
    if payment.member_id != member.id:
        flash(texts.get('not_allowed', 'คุณไม่ได้รับอนุญาตให้เข้าถึงหน้านี้' if lang == 'th' else 'You are not allowed to access this page.'), 'danger')
        return redirect(url_for('continuing_edu.index', lang=lang))
    
    # Get form data
    card_number = request.form.get('card_number')
    card_holder = request.form.get('card_holder')
    expiry = request.form.get('expiry')
    cvv = request.form.get('cvv')
    
    # Validate form data
    if not all([card_number, card_holder, expiry, cvv]):
        flash(texts.get('incomplete_data', 'กรุณากรอกข้อมูลให้ครบถ้วน' if lang == 'th' else 'Please fill in all fields.'), 'warning')
        return redirect(url_for('continuing_edu.payment_process', payment_id=payment_id, payment_method='credit_card', lang=lang))
    
    try:
        # TODO: Implement actual payment gateway integration here
        # For now, just simulate success and update status
        
        # Update payment status to paid
        paid_status = _get_or_create_payment_status(
            'paid',
            name_th='ชำระแล้ว',
            css_badge='is-success',
        )
        payment.payment_status_id = paid_status.id
        payment.payment_date = datetime.now()
        db.session.commit()
        # Send payment success email with invoice/receipt
        try:
            subj = texts.get('payment_success', 'Payment successful!')
            invoice_link = url_for('continuing_edu.view_invoice', payment_id=payment.id, lang=lang, _external=True)
            payments_link = url_for('continuing_edu.my_payments', lang=lang, _external=True)
            body = (f"{texts.get('email_registered_for', 'Registered for')}: {payment.event_entity.title_en or payment.event_entity.title_th}\n"
                    f"{texts.get('email_amount', 'Amount')}: {payment.payment_amount} THB\n"
                    f"{texts.get('email_status', 'Status')}: {texts.get('status_paid', 'Paid')}\n\n"
                    f"{texts.get('email_invoice', 'Invoice')}: {invoice_link}\n"
                    f"{texts.get('email_my_payments', 'My payments')}: {payments_link}\n")
            # use dedicated payment success template
            email_html = render_template('continueing_edu/_payment_success_email.html', payment=payment, event=payment.event_entity, member=member, texts=texts, current_lang=lang)
            msg = Message(subject=subj, body=body, html=email_html, recipients=[member.email]) if getattr(member, 'email', None) else None
            if msg:
                if HTML is not None:
                    try:
                        payment_qr_url = os.environ.get('PAYMENT_QR_URL')
                        promptpay_id = os.environ.get('PROMPTPAY_ID')
                        bank_info = os.environ.get('BANK_INFO')
                        payment_instructions = os.environ.get('PAYMENT_INSTRUCTIONS')
                        html = render_template(
                            'continueing_edu/invoice.html',
                            payment=payment,
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
                        msg.attach(f"invoice_INV-{payment.id}.pdf", 'application/pdf', pdf_bytes)
                    except Exception:
                        pass
                mail.send(msg)
        except Exception:
            pass

        flash(texts.get('payment_success', 'ชำระเงินสำเร็จ' if lang == 'th' else 'Payment successful!'), 'success')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    except Exception as e:
        print(f"Error processing credit card: {e}")
        flash(texts.get('payment_error', 'เกิดข้อผิดพลาดในการชำระเงิน' if lang == 'th' else 'Payment processing error.'), 'danger')
        return redirect(url_for('continuing_edu.payment_process', payment_id=payment_id, payment_method='credit_card', lang=lang))


@ce_bp.route('/members')
def members_list():
    """Renders the members list page."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    members = CEMember.query.all()
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
    speakers = CESpeakerProfile.query.all()
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
    all_events = CEEventEntity.query.all()
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
    all_events = CEEventEntity.query.all()
    all_payment_statuses = PaymentStatus.query.all()
    return render_template('continueing_edu/payments.html',
                           active_menu='Payments',
                           all_events=all_events,
                           texts=texts,
                           current_lang=lang,
                           all_payment_statuses=all_payment_statuses)


@ce_bp.route('/dashboard')
def member_dashboard():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))

    regs = (CEMemberRegistration.query
            .filter_by(member_id=user.id)
            .order_by(CEMemberRegistration.registration_date.desc())
            .all())
    in_progress_regs = [r for r in regs if r.started_at and not r.completed_at]
    completed_regs = [r for r in regs if r.completed_at]

    payments = (CERegisterPayment.query
                .filter_by(member_id=user.id)
                .order_by(CERegisterPayment.id.desc())
                .all())
    latest_payment_by_event = {}
    for payment in payments:
        if payment.event_entity_id not in latest_payment_by_event:
            latest_payment_by_event[payment.event_entity_id] = payment
    payment_gateway_url = os.environ.get('PAYMENT_GATEWAY_URL')

    return render_template(
        'continueing_edu/dashboard.html',
        logged_in_user=user,
        texts=texts,
        current_lang=lang,
        in_progress_regs=in_progress_regs,
        completed_regs=completed_regs,
        payments=payments,
        payment_map=latest_payment_by_event,
        payment_gateway_url=payment_gateway_url,
    )


@ce_bp.route('/my-registrations')
def my_registrations():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    regs = CEMemberRegistration.query.filter_by(member_id=user.id).order_by(CEMemberRegistration.registration_date.desc()).all()
    attendance_qr_payloads = {}
    survey_required_by_reg = {}
    for reg in regs:
        status_name = (reg.status_ref.name_en or '').strip().lower() if reg.status_ref else ''
        is_cancelled = 'cancel' in status_name
        attendance_qr_payloads[reg.id] = {
            'allowed': not is_cancelled,
            'payload': _build_attendance_checkin_payload(reg),
            'reason': 'cancelled' if is_cancelled else '',
        }
        survey_required_by_reg[reg.id] = requires_post_course_survey(reg)
    return render_template(
        'continueing_edu/my_registrations.html',
        registrations=regs,
        attendance_qr_payloads=attendance_qr_payloads,
        survey_required_by_reg=survey_required_by_reg,
        texts=texts,
        current_lang=lang,
        logged_in_user=user,
        member=user,
    )


@ce_bp.route('/my-payments', methods=['GET'])
def my_payments():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    pays = CERegisterPayment.query.filter_by(member_id=user.id).order_by(CERegisterPayment.id.desc()).all()
    return render_template(
        'continueing_edu/my_payments.html',
        payments=pays,
        texts=texts,
        current_lang=lang,
        member=user,
        logged_in_user=user,
    )


@ce_bp.route('/payment/<int:payment_id>/cancel', methods=['POST'])
def cancel_payment(payment_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))

    pay = CERegisterPayment.query.get_or_404(payment_id)
    if pay.member_id != user.id:
        flash(texts.get('not_allowed', 'Not allowed.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))

    status_code = _payment_status_code(pay)
    if status_code in {'paid', 'approved'}:
        flash(texts.get('cannot_cancel_paid', 'Paid payments cannot be cancelled.'), 'warning')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))

    cancelled = _get_or_create_payment_status(
        'cancelled',
        name_th='ยกเลิก',
        css_badge='is-light',
    )

    try:
        # cancel invoice (if exists)
        inv = None
        if getattr(pay, 'invoice', None) is not None:
            inv = pay.invoice
        elif getattr(pay, 'invoice_id', None):
            inv = CEContinuingInvoice.query.get(pay.invoice_id)
        if inv is not None:
            inv.status = 'cancelled'
            db.session.add(inv)

        # cancel payment
        pay.payment_status_id = cancelled.id
        db.session.add(pay)

        # clear registration record for this event
        reg = CEMemberRegistration.query.filter_by(member_id=user.id, event_entity_id=pay.event_entity_id).first()
        if reg:
            db.session.delete(reg)

        db.session.commit()
        flash(texts.get('payment_cancelled', 'Payment cancelled.'), 'success')
    except Exception:
        db.session.rollback()
        flash(texts.get('payment_cancel_failed', 'Failed to cancel payment.'), 'danger')

    return redirect(url_for('continuing_edu.my_payments', lang=lang))


@ce_bp.route('/payment/<int:payment_id>/submit_proof', methods=['POST'])
def submit_payment_proof(payment_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    pay = CERegisterPayment.query.get_or_404(payment_id)
    if pay.member_id != user.id:
        flash(texts.get('not_allowed', 'Not allowed.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    if not _can_member_upload_payment_proof(pay):
        flash(
            texts.get(
                'proof_upload_pending_only',
                'Payment proof can be uploaded only when status is Pending.',
            ),
            'warning',
        )
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    proof_url = request.form.get('payment_proof_url')
    if not proof_url:
        flash(texts.get('proof_required', 'Please provide a payment proof URL.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    old = pay.payment_proof_url
    pay.payment_proof_url = proof_url
    _set_status_on_proof_submission(pay)
    db.session.add(pay)
    db.session.commit()
    if old and old != proof_url:
        _delete_old_payment_proof_reference(old)
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
    pay = CERegisterPayment.query.get_or_404(payment_id)
    if pay.member_id != user.id:
        flash(texts.get('not_allowed', 'Not allowed.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    if not _can_member_upload_payment_proof(pay):
        flash(
            texts.get(
                'proof_upload_pending_only',
                'Payment proof can be uploaded only when status is Pending.',
            ),
            'warning',
        )
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    file = request.files.get('payment_proof_file')
    if not file or file.filename == '':
        flash(texts.get('proof_required', 'Please provide a payment proof file.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    try:
        old = pay.payment_proof_url
        new_reference = _store_payment_proof_file(file, payment_id)
        pay.payment_proof_url = new_reference
        _set_status_on_proof_submission(pay)
        db.session.add(pay)
        db.session.commit()

        if old and old != new_reference:
            _delete_old_payment_proof_reference(old)

        flash(texts.get('proof_received', 'Payment proof submitted.'), 'success')
    except ValueError:
        flash(texts.get('proof_required', 'Please provide a payment proof file.'), 'danger')
    except Exception as e:
        print(f"Error uploading proof: {e}")
        flash(texts.get('upload_error', 'Error uploading file.'), 'danger')
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
    pay = CERegisterPayment.query.get_or_404(payment_id)
    if pay.member_id != user.id:
        flash(texts.get('not_allowed', 'You are not allowed to view this invoice.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))

    def _safe_back_url(raw: str | None) -> str | None:
        if not raw:
            return None
        try:
            parsed = urlparse(raw)
        except Exception:
            return None

        # Allow relative paths only. If it's an absolute URL, accept only same-host
        # then convert it to a relative URL (path + query).
        if parsed.scheme or parsed.netloc:
            try:
                if parsed.netloc and parsed.netloc != request.host:
                    return None
            except Exception:
                return None
            rel = parsed.path or '/'
            if parsed.query:
                rel = f"{rel}?{parsed.query}"
            return rel

        # Relative URL provided.
        if raw.startswith('/'):
            return raw
        return None

    back_url = _safe_back_url(request.args.get('next'))
    if not back_url:
        back_url = _safe_back_url(request.referrer)
    def _build_invoice_context(payment):
        invoice = getattr(payment, 'invoice', None)
        invoice_no = None
        if invoice and getattr(invoice, 'invoice_no', None):
            invoice_no = invoice.invoice_no
        else:
            fallback_id = (invoice.id if invoice else payment.id)
            invoice_no = f"INV{int(fallback_id):06d}"

        invoice_date = None
        if invoice and getattr(invoice, 'created_at', None):
            invoice_date = invoice.created_at
        elif getattr(payment, 'payment_date', None):
            invoice_date = payment.payment_date
        else:
            invoice_date = datetime.now(timezone.utc)

        due_days_raw = os.getenv('INVOICE_DUE_DAYS')
        try:
            due_days = int(due_days_raw) if due_days_raw is not None and due_days_raw != '' else 0
        except Exception:
            due_days = 0
        due_date = invoice_date + timedelta(days=due_days)

        vat_rate_raw = os.getenv('INVOICE_VAT_RATE', os.getenv('VAT_RATE', '0'))
        try:
            vat_rate = float(vat_rate_raw) if vat_rate_raw not in (None, '') else 0.0
        except Exception:
            vat_rate = 0.0
        vat_included = (os.getenv('INVOICE_VAT_INCLUDED', 'false').strip().lower() in ('1', 'true', 'yes', 'y'))

        amount_total = float(getattr(payment, 'payment_amount', 0) or 0)
        if vat_rate > 0:
            if vat_included:
                subtotal = amount_total / (1.0 + vat_rate)
                vat_amount = amount_total - subtotal
                total = amount_total
            else:
                subtotal = amount_total
                vat_amount = subtotal * vat_rate
                total = subtotal + vat_amount
        else:
            subtotal = amount_total
            vat_amount = 0.0
            total = amount_total

        invoice_meta = {
            'invoice_no': invoice_no,
            'invoice_date': invoice_date,
            'due_date': due_date,
            'due_days': due_days,
            'vat_rate': vat_rate,
            'vat_included': vat_included,
            'subtotal': round(subtotal, 2),
            'vat_amount': round(vat_amount, 2),
            'total': round(total, 2),
        }
        seller = {
            'name_th': os.getenv('INVOICE_SELLER_NAME_TH', ''),
            'name_en': os.getenv('INVOICE_SELLER_NAME_EN', ''),
            'address_th': os.getenv('INVOICE_SELLER_ADDRESS_TH', ''),
            'address_en': os.getenv('INVOICE_SELLER_ADDRESS_EN', ''),
            'tax_id': os.getenv('INVOICE_SELLER_TAX_ID', ''),
            'branch': os.getenv('INVOICE_SELLER_BRANCH', ''),
            'phone': os.getenv('INVOICE_SELLER_PHONE', ''),
            'email': os.getenv('INVOICE_SELLER_EMAIL', ''),
        }
        return invoice_meta, seller

    def _first_env(*keys: str) -> str:
        for key in keys:
            value = (os.getenv(key) or '').strip()
            if value:
                return value
        return ''

    def _extract_account_no(text: str | None) -> str:
        if not text:
            return ''
        match = re.search(r'(\d[\d\-\s]{6,}\d)', text)
        if not match:
            return ''
        candidate = match.group(1).strip()
        digits_only = re.sub(r'\D', '', candidate)
        return candidate if len(digits_only) >= 8 else ''

    def _build_invoice_payment_channel_context(payment, inv_meta):
        payment_instructions = _first_env('INVOICE_PAYMENT_INSTRUCTIONS', 'PAYMENT_INSTRUCTIONS')
        bank_info = _first_env('INVOICE_BANK_INFO', 'BANK_INFO')

        bank_name = _first_env('INVOICE_BANK_NAME', 'BANK_NAME')
        bank_branch = _first_env('INVOICE_BANK_BRANCH', 'BANK_BRANCH')
        bank_account_name = _first_env('INVOICE_BANK_ACCOUNT_NAME', 'BANK_ACCOUNT_NAME')
        bank_account_no = _first_env('INVOICE_BANK_ACCOUNT_NO', 'BANK_ACCOUNT_NO')
        if not bank_account_no:
            bank_account_no = _extract_account_no(bank_info)

        promptpay_id = _first_env('INVOICE_PROMPTPAY_ID', 'PROMPTPAY_ID', 'BILLERID')
        payment_qr_url = _first_env('INVOICE_PAYMENT_QR_URL', 'PAYMENT_QR_URL')

        # Optional template URL for QR generation from PromptPay ID
        # Example: https://example.com/qr?id={promptpay_id}&amount={amount}
        qr_template = _first_env('PROMPTPAY_QR_TEMPLATE_URL')
        if not payment_qr_url and promptpay_id and qr_template:
            try:
                amount = float(getattr(payment, 'payment_amount', 0) or 0)
            except Exception:
                amount = 0.0
            try:
                payment_qr_url = qr_template.format(
                    promptpay_id=promptpay_id,
                    amount=f'{amount:.2f}',
                    invoice_no=(inv_meta.get('invoice_no') if inv_meta else ''),
                    payment_id=getattr(payment, 'id', ''),
                )
            except Exception:
                payment_qr_url = ''

        payment_gateway_url = _first_env('PAYMENT_GATEWAY_URL')

        return {
            'payment_instructions': payment_instructions,
            'bank_info': bank_info,
            'bank_name': bank_name,
            'bank_branch': bank_branch,
            'bank_account_name': bank_account_name,
            'bank_account_no': bank_account_no,
            'promptpay_id': promptpay_id,
            'qr_url': payment_qr_url,
            'payment_gateway_url': payment_gateway_url,
        }

    invoice_meta, seller = _build_invoice_context(pay)
    payment_channel = _build_invoice_payment_channel_context(pay, invoice_meta)

    return render_template(
        'continueing_edu/invoice.html',
        payment=pay,
        member=user,
        logged_in_user=user,
        back_url=back_url,
        texts=texts,
        current_lang=lang,
        payment_qr_url=payment_channel.get('qr_url'),
        promptpay_id=payment_channel.get('promptpay_id'),
        bank_info=payment_channel.get('bank_info'),
        payment_instructions=payment_channel.get('payment_instructions'),
        payment_gateway_url=payment_channel.get('payment_gateway_url'),
        payment_channel=payment_channel,
        pdf_available=(HTML is not None),
        invoice_meta=invoice_meta,
        seller=seller,
    )


@ce_bp.route('/payment/<int:payment_id>/invoice.pdf')
def download_invoice_pdf(payment_id):
    """Generate and download invoice as PDF."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    pay = CERegisterPayment.query.get_or_404(payment_id)
    if pay.member_id != user.id:
        flash(texts.get('not_allowed', 'You are not allowed to view this invoice.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    if HTML is None:
        flash(texts.get('pdf_unavailable', 'PDF generation is currently unavailable.'), 'warning')
        return redirect(url_for('continuing_edu.view_invoice', payment_id=payment_id, lang=lang))
    def _build_invoice_context(payment):
        invoice = getattr(payment, 'invoice', None)
        invoice_no = None
        if invoice and getattr(invoice, 'invoice_no', None):
            invoice_no = invoice.invoice_no
        else:
            fallback_id = (invoice.id if invoice else payment.id)
            invoice_no = f"INV{int(fallback_id):06d}"

        invoice_date = None
        if invoice and getattr(invoice, 'created_at', None):
            invoice_date = invoice.created_at
        elif getattr(payment, 'payment_date', None):
            invoice_date = payment.payment_date
        else:
            invoice_date = datetime.now(timezone.utc)

        due_days_raw = os.getenv('INVOICE_DUE_DAYS')
        try:
            due_days = int(due_days_raw) if due_days_raw is not None and due_days_raw != '' else 0
        except Exception:
            due_days = 0
        due_date = invoice_date + timedelta(days=due_days)

        vat_rate_raw = os.getenv('INVOICE_VAT_RATE', os.getenv('VAT_RATE', '0'))
        try:
            vat_rate = float(vat_rate_raw) if vat_rate_raw not in (None, '') else 0.0
        except Exception:
            vat_rate = 0.0
        vat_included = (os.getenv('INVOICE_VAT_INCLUDED', 'false').strip().lower() in ('1', 'true', 'yes', 'y'))

        amount_total = float(getattr(payment, 'payment_amount', 0) or 0)
        if vat_rate > 0:
            if vat_included:
                subtotal = amount_total / (1.0 + vat_rate)
                vat_amount = amount_total - subtotal
                total = amount_total
            else:
                subtotal = amount_total
                vat_amount = subtotal * vat_rate
                total = subtotal + vat_amount
        else:
            subtotal = amount_total
            vat_amount = 0.0
            total = amount_total

        invoice_meta = {
            'invoice_no': invoice_no,
            'invoice_date': invoice_date,
            'due_date': due_date,
            'due_days': due_days,
            'vat_rate': vat_rate,
            'vat_included': vat_included,
            'subtotal': round(subtotal, 2),
            'vat_amount': round(vat_amount, 2),
            'total': round(total, 2),
        }
        seller = {
            'name_th': os.getenv('INVOICE_SELLER_NAME_TH', ''),
            'name_en': os.getenv('INVOICE_SELLER_NAME_EN', ''),
            'address_th': os.getenv('INVOICE_SELLER_ADDRESS_TH', ''),
            'address_en': os.getenv('INVOICE_SELLER_ADDRESS_EN', ''),
            'tax_id': os.getenv('INVOICE_SELLER_TAX_ID', ''),
            'branch': os.getenv('INVOICE_SELLER_BRANCH', ''),
            'phone': os.getenv('INVOICE_SELLER_PHONE', ''),
            'email': os.getenv('INVOICE_SELLER_EMAIL', ''),
        }
        return invoice_meta, seller

    def _first_env(*keys: str) -> str:
        for key in keys:
            value = (os.getenv(key) or '').strip()
            if value:
                return value
        return ''

    def _extract_account_no(text: str | None) -> str:
        if not text:
            return ''
        match = re.search(r'(\d[\d\-\s]{6,}\d)', text)
        if not match:
            return ''
        candidate = match.group(1).strip()
        digits_only = re.sub(r'\D', '', candidate)
        return candidate if len(digits_only) >= 8 else ''

    def _build_invoice_payment_channel_context(payment, inv_meta):
        payment_instructions = _first_env('INVOICE_PAYMENT_INSTRUCTIONS', 'PAYMENT_INSTRUCTIONS')
        bank_info = _first_env('INVOICE_BANK_INFO', 'BANK_INFO')

        bank_name = _first_env('INVOICE_BANK_NAME', 'BANK_NAME')
        bank_branch = _first_env('INVOICE_BANK_BRANCH', 'BANK_BRANCH')
        bank_account_name = _first_env('INVOICE_BANK_ACCOUNT_NAME', 'BANK_ACCOUNT_NAME')
        bank_account_no = _first_env('INVOICE_BANK_ACCOUNT_NO', 'BANK_ACCOUNT_NO')
        if not bank_account_no:
            bank_account_no = _extract_account_no(bank_info)

        promptpay_id = _first_env('INVOICE_PROMPTPAY_ID', 'PROMPTPAY_ID', 'BILLERID')
        payment_qr_url = _first_env('INVOICE_PAYMENT_QR_URL', 'PAYMENT_QR_URL')

        qr_template = _first_env('PROMPTPAY_QR_TEMPLATE_URL')
        if not payment_qr_url and promptpay_id and qr_template:
            try:
                amount = float(getattr(payment, 'payment_amount', 0) or 0)
            except Exception:
                amount = 0.0
            try:
                payment_qr_url = qr_template.format(
                    promptpay_id=promptpay_id,
                    amount=f'{amount:.2f}',
                    invoice_no=(inv_meta.get('invoice_no') if inv_meta else ''),
                    payment_id=getattr(payment, 'id', ''),
                )
            except Exception:
                payment_qr_url = ''

        payment_gateway_url = _first_env('PAYMENT_GATEWAY_URL')

        return {
            'payment_instructions': payment_instructions,
            'bank_info': bank_info,
            'bank_name': bank_name,
            'bank_branch': bank_branch,
            'bank_account_name': bank_account_name,
            'bank_account_no': bank_account_no,
            'promptpay_id': promptpay_id,
            'qr_url': payment_qr_url,
            'payment_gateway_url': payment_gateway_url,
        }

    invoice_meta, seller = _build_invoice_context(pay)
    payment_channel = _build_invoice_payment_channel_context(pay, invoice_meta)

    html = render_template(
        'continueing_edu/invoice.html',
        payment=pay,
        member=user,
        logged_in_user=user,
        texts=texts,
        current_lang=lang,
        payment_qr_url=payment_channel.get('qr_url'),
        promptpay_id=payment_channel.get('promptpay_id'),
        bank_info=payment_channel.get('bank_info'),
        payment_instructions=payment_channel.get('payment_instructions'),
        payment_gateway_url=payment_channel.get('payment_gateway_url'),
        payment_channel=payment_channel,
        pdf_available=True,
        invoice_meta=invoice_meta,
        seller=seller,
    )
    pdf_bytes = HTML(string=html, base_url=request.host_url).write_pdf()
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename="invoice_{invoice_meta.get("invoice_no", "INV%06d" % pay.id)}.pdf"'
    return resp


@ce_bp.route('/receipt/<int:receipt_id>')
def view_receipt(receipt_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    from .models import CERegisterPaymentReceipt
    rc = CERegisterPaymentReceipt.query.get_or_404(receipt_id)
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
    from .models import CERegisterPaymentReceipt
    rc = CERegisterPaymentReceipt.query.get_or_404(receipt_id)
    pay = rc.payment
    if pay.member_id != user.id:
        flash(texts.get('not_allowed', 'Not allowed.'), 'danger')
        return redirect(url_for('continuing_edu.my_payments', lang=lang))
    if HTML is None:
        flash('PDF rendering library is not available on server.', 'danger')
        return redirect(url_for('continuing_edu.view_receipt', receipt_id=receipt_id, lang=lang))
    html = render_template('continueing_edu/receipt_pdf.html', receipt=rc, payment=pay, member=user, texts=texts, current_lang=lang)
    pdf = HTML(string=html, base_url=request.url_root).write_pdf()

    filename = f"receipt_{rc.receipt_number}.pdf"
    return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': f'inline; filename="{filename}"'})


# -----------------------------
# Member progress + certificates
# -----------------------------
def _get_registration_or_404(event_id, member_id):
    reg = CEMemberRegistration.query.filter_by(event_entity_id=event_id, member_id=member_id).first()
    if not reg:
        raise NotFound('Registration not found for this event')
    return reg


def _event_detail_redirect(event_entity, lang):
    if event_entity.event_type == 'course':
        return redirect(url_for('continuing_edu.course_detail', course_id=event_entity.id, lang=lang))
    return redirect(url_for('continuing_edu.webinar_detail', webinar_id=event_entity.id, lang=lang))


def _has_approved_or_paid_payment(member_id: int, event_id: int) -> bool:
    from app.continuing_edu.models import CERegisterPaymentStatus, CERegisterPayment

    payment = (
        CERegisterPayment.query
        .join(CERegisterPaymentStatus, CERegisterPayment.payment_status_ref)
        .filter(
            CERegisterPayment.member_id == member_id,
            CERegisterPayment.event_entity_id == event_id,
            (
                (func.lower(CERegisterPaymentStatus.register_payment_status_code).in_(['approved', 'paid'])) |
                (func.lower(CERegisterPaymentStatus.name_en).in_(['approved', 'paid']))
            ),
        )
        .order_by(CERegisterPayment.id.desc())
        .first()
    )
    return payment is not None


def _build_satisfaction_access_link(reg: CEMemberRegistration, lang: str = 'en') -> str:
    serializer = _satisfaction_serializer()
    now_utc = datetime.now(timezone.utc)
    payload = {
        'reg_id': reg.id,
        'member_id': reg.member_id,
        'nonce': secrets.token_urlsafe(10),
        'iat': int(now_utc.timestamp()),
    }
    raw_token = serializer.dumps(payload)
    token = raw_token.decode('utf-8') if isinstance(raw_token, bytes) else str(raw_token)

    rec = CESatisfactionSurveyAccessToken(
        registration_id=reg.id,
        member_id=reg.member_id,
        event_entity_id=reg.event_entity_id,
        token_hash=_hash_token(token),
        expires_at=now_utc + timedelta(seconds=SATISFACTION_TOKEN_MAX_AGE),
    )
    db.session.add(rec)
    db.session.commit()

    return url_for('continuing_edu.satisfaction_survey_by_token', token=token, lang=lang, _external=True)


def _resolve_satisfaction_access_token(token: str):
    serializer = _satisfaction_serializer()
    try:
        payload = serializer.loads(token, max_age=SATISFACTION_TOKEN_MAX_AGE)
    except SignatureExpired:
        return None, None, 'expired'
    except BadSignature:
        return None, None, 'invalid'

    token_rec = CESatisfactionSurveyAccessToken.query.filter_by(token_hash=_hash_token(token)).first()
    if not token_rec:
        return None, None, 'invalid'

    now_utc = datetime.now(timezone.utc)
    expires_at = token_rec.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and now_utc > expires_at:
        return None, token_rec, 'expired'
    if token_rec.used_at:
        return None, token_rec, 'used'

    reg = CEMemberRegistration.query.get(token_rec.registration_id)
    if not reg:
        return None, token_rec, 'invalid'
    if payload.get('reg_id') != reg.id or payload.get('member_id') != reg.member_id:
        return None, token_rec, 'invalid'
    return reg, token_rec, None


def _render_satisfaction_form(
    reg: CEMemberRegistration,
    *,
    lang: str,
    texts,
    form_data=None,
    share_link: str | None = None,
    access_token: str | None = None,
):
    event = reg.event_entity
    survey_name = build_satisfaction_form_name(event, lang=lang)
    existing = CESatisfactionSurveyResponse.query.filter_by(registration_id=reg.id).first()
    form_action = (
        url_for('continuing_edu.satisfaction_survey_by_token', token=access_token, lang=lang)
        if access_token else
        url_for('continuing_edu.satisfaction_survey', event_id=event.id, lang=lang)
    )
    return render_template(
        'continueing_edu/satisfaction_survey.html',
        registration=reg,
        event=event,
        survey_name=survey_name,
        response=existing,
        form_data=form_data,
        form_action=form_action,
        share_link=share_link,
        texts=texts,
        current_lang=lang,
        logged_in_user=get_current_user(),
    )


def _handle_satisfaction_submission(
    reg: CEMemberRegistration,
    *,
    lang: str,
    texts,
    token_rec: CESatisfactionSurveyAccessToken | None = None,
    access_token: str | None = None,
):
    if not reg.completed_at:
        flash(
            texts.get(
                'questionnaire_complete_event_first',
                'Please complete your learning progress first.',
            ),
            'warning',
        )
        return _event_detail_redirect(reg.event_entity, lang)

    form = request.form

    def _parse_rating(field_name):
        raw = (form.get(field_name) or '').strip()
        try:
            value = int(raw)
        except Exception:
            return None
        if value < 1 or value > 5:
            return None
        return value

    overall = _parse_rating('overall_rating')
    content = _parse_rating('content_rating')
    instructor = _parse_rating('instructor_rating')
    platform = _parse_rating('platform_rating')

    if None in (overall, content, instructor, platform):
        flash(
            texts.get(
                'satisfaction_required_scores',
                'Please rate all required items from 1 to 5.',
            ),
            'danger',
        )
        return _render_satisfaction_form(
            reg,
            lang=lang,
            texts=texts,
            form_data=form,
            access_token=access_token,
        )

    recommend_raw = (form.get('recommend_to_others') or '').strip().lower()
    if recommend_raw in ('1', 'true', 'yes', 'y'):
        recommend = True
    elif recommend_raw in ('0', 'false', 'no', 'n'):
        recommend = False
    else:
        recommend = None

    event = reg.event_entity
    survey_name = build_satisfaction_form_name(event, lang=lang)
    existing = CESatisfactionSurveyResponse.query.filter_by(registration_id=reg.id).first()
    response = existing or CESatisfactionSurveyResponse(
        registration_id=reg.id,
        member_id=reg.member_id,
        event_entity_id=reg.event_entity_id,
    )
    response.survey_name = survey_name
    response.overall_rating = overall
    response.content_rating = content
    response.instructor_rating = instructor
    response.platform_rating = platform
    response.recommend_to_others = recommend
    response.comment_text = (form.get('comment_text') or '').strip() or None
    db.session.add(response)

    if not reg.questionnaire_completed_at:
        reg.questionnaire_completed_at = datetime.now(timezone.utc)

    if reg.assessment_passed:
        pending = get_certificate_status('pending', 'รอดำเนินการ', 'is-info')
        reg.certificate_status_id = pending.id

    if token_rec and not token_rec.used_at:
        token_rec.used_at = datetime.now(timezone.utc)
        db.session.add(token_rec)

    db.session.add(reg)

    if reg.certificate_url:
        db.session.commit()
        flash(texts.get('satisfaction_saved', 'Satisfaction survey saved.'), 'success')
    elif reg.assessment_passed and can_issue_certificate(reg):
        issue_certificate(reg, lang=lang, base_url=request.url_root)
        flash(
            texts.get(
                'questionnaire_completed_and_certificate_ready',
                'Satisfaction survey completed. Your certificate is now available.',
            ),
            'success',
        )
    else:
        db.session.commit()
        flash(texts.get('satisfaction_saved', 'Satisfaction survey saved.'), 'success')

    if access_token:
        return redirect(url_for('continuing_edu.satisfaction_survey_by_token', token=access_token, lang=lang, submitted='1'))
    if event.event_type == 'course':
        return redirect(url_for('continuing_edu.course_learn', course_id=event.id, lang=lang))
    return redirect(url_for('continuing_edu.webinar_detail', webinar_id=event.id, lang=lang))


@ce_bp.route('/event/<int:event_id>/start_progress', methods=['POST'])
def start_progress(event_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    
    reg = _get_registration_or_404(event_id, user.id)
    if not _has_approved_or_paid_payment(user.id, event_id):
        flash(texts.get('payment_not_approved', 'This page requires an approved payment.'), 'warning')
        return _event_detail_redirect(reg.event_entity, lang)
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
    if not _has_approved_or_paid_payment(user.id, event_id):
        flash(texts.get('payment_not_approved', 'This page requires an approved payment.'), 'warning')
        return _event_detail_redirect(reg.event_entity, lang)
   
    if not reg.completed_at:
        reg.completed_at = datetime.now(timezone.utc)
    completed_status = get_registration_status('completed', 'completed', 'สำเร็จแล้ว', 'is-success')
    reg.status_id = completed_status.id
    # Optionally accept assessment result
    passed = request.form.get('passed') or request.args.get('passed')
    if passed is not None:
        reg.assessment_passed = True if str(passed).lower() in ('1','true','yes','y','passed') else False
    # Issue certificate if completed, passed, questionnaire completed (for courses), and payment approved
    if reg.assessment_passed:
        pending = get_certificate_status('pending', 'รอดำเนินการ', 'is-info')
        reg.certificate_status_id = pending.id
        if requires_post_course_survey(reg) and not reg.questionnaire_completed_at:
            db.session.add(reg)
            db.session.commit()
            flash(
                texts.get(
                    'questionnaire_required_before_certificate',
                    'Please complete the satisfaction survey before receiving certificate.',
                ),
                'warning',
            )
            return redirect(url_for('continuing_edu.satisfaction_survey', event_id=event_id, lang=lang))
        approved = can_issue_certificate(reg)
        if approved:
            issue_certificate(reg, lang=lang, base_url=request.url_root)
            flash(texts.get('certificate_issued', 'Certificate issued.'), 'success')
        else:
            db.session.add(reg)
            db.session.commit()
            flash(texts.get('payment_not_approved', 'Certificate requires approved payment.'), 'warning')
    else:
        db.session.add(reg)
        db.session.commit()
        flash(texts.get('progress_completed', 'Progress completed.'), 'success')
    return _event_detail_redirect(reg.event_entity, lang)


@ce_bp.route('/event/<int:event_id>/satisfaction', methods=['GET', 'POST'])
def satisfaction_survey(event_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))

    reg = _get_registration_or_404(event_id, user.id)
    if not reg.completed_at:
        flash(
            texts.get(
                'questionnaire_complete_event_first',
                'Please complete your learning progress first.',
            ),
            'warning',
        )
        return _event_detail_redirect(reg.event_entity, lang)

    if request.method == 'POST':
        return _handle_satisfaction_submission(reg, lang=lang, texts=texts)
    share_link = request.args.get('share_link')
    return _render_satisfaction_form(reg, lang=lang, texts=texts, share_link=share_link)


@ce_bp.route('/event/<int:event_id>/satisfaction/share-link', methods=['POST'])
def generate_satisfaction_share_link(event_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))

    reg = _get_registration_or_404(event_id, user.id)
    if not requires_post_course_survey(reg):
        flash(texts.get('questionnaire_not_required', 'Satisfaction survey is not required for this event.'), 'info')
        return _event_detail_redirect(reg.event_entity, lang)
    if not reg.completed_at:
        flash(
            texts.get(
                'questionnaire_complete_event_first',
                'Please complete your learning progress first.',
            ),
            'warning',
        )
        return _event_detail_redirect(reg.event_entity, lang)

    share_link = _build_satisfaction_access_link(reg, lang=lang)
    flash(
        texts.get(
            'satisfaction_share_link_generated',
            'Share link generated. You can copy it below.',
        ),
        'success',
    )
    return redirect(url_for('continuing_edu.satisfaction_survey', event_id=event_id, lang=lang, share_link=share_link))


@ce_bp.route('/satisfaction/access/<token>', methods=['GET', 'POST'])
def satisfaction_survey_by_token(token):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])

    reg, token_rec, err = _resolve_satisfaction_access_token(token)

    if err == 'used' and request.args.get('submitted') == '1':
        event = token_rec.event_entity if token_rec else None
        return render_template('continueing_edu/satisfaction_submitted.html', event=event, texts=texts, current_lang=lang)

    if err:
        if err == 'expired':
            flash(texts.get('satisfaction_link_expired', 'This satisfaction link has expired.'), 'danger')
        elif err == 'used':
            flash(texts.get('satisfaction_link_used', 'This satisfaction link has already been used.'), 'warning')
        else:
            flash(texts.get('satisfaction_link_invalid', 'Invalid satisfaction link.'), 'danger')
        return redirect(url_for('continuing_edu.index', lang=lang))

    if not reg.completed_at:
        flash(
            texts.get(
                'questionnaire_complete_event_first',
                'Please complete your learning progress first.',
            ),
            'warning',
        )
        return redirect(url_for('continuing_edu.index', lang=lang))

    if request.method == 'POST':
        return _handle_satisfaction_submission(reg, lang=lang, texts=texts, token_rec=token_rec, access_token=token)
    return _render_satisfaction_form(reg, lang=lang, texts=texts, access_token=token)


@ce_bp.route('/event/<int:event_id>/complete_questionnaire', methods=['POST'])
def complete_questionnaire(event_id):
    """Backward-compatible endpoint: redirect to internal satisfaction form."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    _get_registration_or_404(event_id, user.id)
    return redirect(url_for('continuing_edu.satisfaction_survey', event_id=event_id, lang=lang))


@ce_bp.route('/certificate/<int:reg_id>/pdf')
def certificate_pdf(reg_id):
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    user = get_current_user()
    if not user:
        flash(texts.get('login_required', 'Please login to continue.'), 'danger')
        return redirect(url_for('continuing_edu.login', lang=lang))
    reg = CEMemberRegistration.query.get_or_404(reg_id)
    if reg.member_id != user.id:
        flash(texts.get('not_allowed', 'Not allowed.'), 'danger')
        return redirect(url_for('continuing_edu.my_registrations', lang=lang))

    if not reg.certificate_url and not can_issue_certificate(reg):
        if requires_post_course_survey(reg) and not reg.questionnaire_completed_at:
            flash(
                texts.get(
                    'questionnaire_required_before_certificate',
                    'Please complete the satisfaction survey before receiving certificate.',
                ),
                'warning',
            )
            return redirect(url_for('continuing_edu.satisfaction_survey', event_id=reg.event_entity_id, lang=lang))
        flash(texts.get('certificate_not_available_yet', 'Certificate is not available yet.'), 'warning')
        return redirect(url_for('continuing_edu.my_registrations', lang=lang))

    if not reg.certificate_url and can_issue_certificate(reg):
        issue_certificate(reg, lang=lang, base_url=request.url_root)

    # If already generated, redirect to stored location
    if reg.certificate_url:
        url = reg.certificate_presigned_url()
        return redirect(url or reg.certificate_url)
    if HTML is None:
        flash('PDF rendering library is not available on server.', 'danger')
        return redirect(url_for('continuing_edu.my_registrations', lang=lang))
    # Generate on the fly
    context = build_certificate_context(reg, lang=lang, base_url=request.url_root)
    html = render_template('continueing_edu/certificate_pdf.html', **context)
    pdf = HTML(string=html, base_url=request.url_root).write_pdf()
   
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
    reg = CEMemberRegistration.query.get_or_404(reg_id)
    if reg.member_id != user.id:
        flash(texts.get('not_allowed', 'Not allowed.'), 'danger')
        return redirect(url_for('continuing_edu.my_registrations', lang=lang))
    if not reg.certificate_url and not can_issue_certificate(reg):
        if requires_post_course_survey(reg) and not reg.questionnaire_completed_at:
            flash(
                texts.get(
                    'questionnaire_required_before_certificate',
                    'Please complete the satisfaction survey before receiving certificate.',
                ),
                'warning',
            )
            return redirect(url_for('continuing_edu.satisfaction_survey', event_id=reg.event_entity_id, lang=lang))
        flash(texts.get('certificate_not_available_yet', 'Certificate is not available yet.'), 'warning')
        return redirect(url_for('continuing_edu.my_registrations', lang=lang))

    if not reg.certificate_url and can_issue_certificate(reg):
        issue_certificate(reg, lang=lang, base_url=request.url_root)
        if not reg.certificate_url:
            flash(texts.get('certificate_not_available_yet', 'Certificate is not available yet.'), 'warning')
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

    # Build the query and join speakers for searching
    query = CEEventEntity.query
    query = query.outerjoin(CEEventSpeaker)

    # Apply type filter if provided
    if event_type_filter:
        query = query.filter_by(event_type=event_type_filter)

    # Apply search filter if provided
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(or_(
            CEEventEntity.title_en.like(search_pattern),
            CEEventEntity.title_th.like(search_pattern),
            CEEventEntity.course_code.like(search_pattern),
            CEEventEntity.location_en.like(search_pattern),
            CEEventSpeaker.name_en.like(search_pattern)
        ))

    # Paginate the results
    pagination = query.order_by(CEEventEntity.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

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
                'location_en': request.form.get('location_en'),
                'location_th': request.form.get('location_th'),
                'certificate_name_th': request.form.get('certificate_name_th'),
                'certificate_name_en': request.form.get('certificate_name_en'),
            })

        try:
            new_event = CEEventEntity(**data)
            # If basic speaker name provided, attach a minimal CEEventSpeaker before commit
            speaker_name_en = request.form.get('speaker_en')
            speaker_name_th = request.form.get('speaker_th')
            if speaker_name_en or speaker_name_th:
                new_event.speakers.append(CEEventSpeaker(
                    title_en='', title_th='',
                    name_en=speaker_name_en or '', name_th=speaker_name_th or '',
                    email='', phone='', institution_th='', institution_en=''
                ))
            db.session.add(new_event)
            db.session.commit()
            flash('Event added successfully!', 'success')
            return redirect(url_for('continuing_edu.events_management'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding event: {e}', 'danger')

    staff_accounts = StaffAccount.query.all()
    categories = request.form.get('category_id') or ""
    certificate_types = CECertificateType.query.all()
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

    event = CEEventEntity.query.get_or_404(event_id)
    if request.method == 'POST':
        try:
            event.title_en = request.form.get('title_en')
            event.title_th = request.form.get('title_th')
            event.description_en = request.form.get('description_en')
            event.description_th = request.form.get('description_th')
            event.staff_id = request.form.get('staff_id') or None  # Set to None if empty
            event.category_id = request.form.get('category_id') or None
            event.certificate_type_id = request.form.get('certificate_type_id') or None
            event.creating_institution = request.form.get('creating_institution')
            event.department_or_unit = request.form.get('department_or_unit')
            event.continue_education_score = request.form.get('continue_education_score', type=float)

            if event.event_type == 'course':
                event.course_code = request.form.get('course_code')
                event.image_url = request.form.get('image_url')
                event.long_description_en = request.form.get('long_description_en')
                event.long_description_th = request.form.get('long_description_th')
                event.duration_en = request.form.get('duration_en')
                event.duration_th = request.form.get('duration_th')
                event.format_en = request.form.get('format_en')
                event.format_th = request.form.get('format_th')
                event.certification_en = request.form.get('certification_en')
                event.certification_th = request.form.get('certification_th')
                event.location_en = request.form.get('location_en')
                event.location_th = request.form.get('location_th')
                event.degree_en = request.form.get('degree_en')
                event.degree_th = request.form.get('degree_th')
                event.department_owner = request.form.get('department_owner')
                event.created_by = request.form.get('created_by')
                event.certificate_name_th = request.form.get('certificate_name_th')
                event.certificate_name_en = request.form.get('certificate_name_en')
            elif event.event_type == 'webinar':
                event.long_description_en = request.form.get('long_description_en')
                event.long_description_th = request.form.get('long_description_th')
                event.date_en = request.form.get('date_en')
                event.date_th = request.form.get('date_th')
                event.time_en = request.form.get('time_en')
                event.time_th = request.form.get('time_th')
                # Speaker information moved to CEEventSpeaker model; update/create minimal speaker record
                speaker_name_en = request.form.get('speaker_en')
                speaker_name_th = request.form.get('speaker_th')
                if speaker_name_en or speaker_name_th:
                    if event.speakers:
                        sp = event.speakers[0]
                        sp.name_en = speaker_name_en or sp.name_en
                        sp.name_th = speaker_name_th or sp.name_th
                    else:
                        sp = CEEventSpeaker(
                            title_en='', title_th='',
                            name_en=speaker_name_en or '', name_th=speaker_name_th or '',
                            email='', phone='', institution_th='', institution_en=''
                        )
                        event.speakers.append(sp)
                event.location_en = request.form.get('location_en')
                event.location_th = request.form.get('location_th')
                event.certificate_name_th = request.form.get('certificate_name_th')
                event.certificate_name_en = request.form.get('certificate_name_en')

            db.session.commit()
            flash('Event updated successfully!', 'success')
            return redirect(url_for('continuing_edu.events_management'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating event: {e}', 'danger')

    staff_accounts = StaffAccount.query.all()
    categories = event.event_type # EventCategory.query.all()
    certificate_types = CECertificateType.query.all()
    return render_template('continueing_edu/event_form.html',
                           active_menu='Event Management',
                           form_title=f'Edit Event: {event.title_en}',
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

    event = CEEventEntity.query.get_or_404(event_id)
    try:
        db.session.delete(event)
        db.session.commit()
        flash('Event deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting event: {e}', 'danger')
    return redirect(url_for('continuing_edu.events_management', lang=lang))


@ce_bp.route('/api/registrations_data', methods=['GET'])
def get_registrations_data():
    """API endpoint to get paginated and filtered registration data."""
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    event_id = request.args.get('event_id', type=int)
    search_query = request.args.get('search', '').strip()

    query = Registration.query.join(CEMember).join(Event).join(Payment, isouter=True)

    if event_id:
        query = query.filter(Registration.event_id == event_id)

    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(or_(
            CEMember.username.like(search_pattern),
            CEMember.email.like(search_pattern),
            CEEventEntity.title_en.like(search_pattern),
            CEEventEntity.title_th.like(search_pattern)
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
            'event_title_en': reg.CEEventEntity.title_en,
            'event_type': reg.CEEventEntity.event_type,
            'registration_date': reg.registration_date.strftime('%Y-%m-%d %H:%M:%S'),
            'status_en': reg.registration_status_ref.name_en if reg.registration_status_ref else 'N/A',
            'status_badge_css': reg.registration_status_ref.name_en.lower() if reg.registration_status_ref else 'is-light',
            'payment_status_en': payment_status_name,
            'payment_status_badge_css': payment_badge_css,
            'ce_score': reg.CEEventEntity.continue_education_score,
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

    query = Payment.query.join(Registration).join(CEMember).join(Event).join(PaymentStatus)

    if event_id:
        query = query.filter(Registration.event_id == event_id)
    if payment_status_id:
        query = query.filter(Payment.payment_status_id == payment_status_id)

    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(or_(
            CEMember.username.like(search_pattern),
            CEMember.email.like(search_pattern),
            CEEventEntity.title_en.like(search_pattern),
            CEEventEntity.title_th.like(search_pattern),
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
            'event_title_en': pay.registration.CEEventEntity.title_en,
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
        event = CEEventEntity.query.get_or_404(event_id)
        # Check if the event is a course or a webinar
        if CEEventEntity.event_type == 'course':
            template_name = 'continueing_edu/course_details.html'
        elif CEEventEntity.event_type == 'webinar':
            template_name = 'continueing_edu/webinar_details.html'
        else:
            # Handle unknown event type
            return "Unknown event type", 404

        return render_template(template_name, active_menu='Event Details', event=event)
    except NotFound:
        flash('Event not found.', 'danger')
        return redirect(url_for('continuing_edu.events_management'))
    

@ce_bp.route('/events' , methods=['GET'])
def admin_events():
    lang = request.args.get('lang', 'en')
    texts = tr.get(lang, tr['en'])
    print("Admin Events")
    events = CEEventEntity.query.order_by(CEEventEntity.created_at.desc()).all()
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
    event = CEEventEntity.query.get_or_404(event_id)
    if request.method == 'POST':
        # TODO: Add form processing logic
        flash('Event updated (stub)', 'success')
        return redirect(url_for('continuing_edu.admin_events'))
    return render_template('continueing_edu/event_form.html', event=event, form_title='Edit Event')

@ce_bp.route('/event/delete/<int:event_id>', methods=['POST'])
def admin_delete_event(event_id):
    event = CEEventEntity.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted', 'success')
