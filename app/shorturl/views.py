from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from nanoid import generate

from app.main import db

from . import shorturl
from .models import ShortUrlMapping

BANGKOK_TZ = ZoneInfo('Asia/Bangkok')


def _to_bangkok(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BANGKOK_TZ)


def _is_valid_long_url(value):
    parsed = urlparse((value or '').strip())
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def _parse_expiration_date(value):
    if not value:
        return None
    try:
        if len(value) == 10:
            expiration_date = datetime.strptime(value, '%Y-%m-%d').replace(
                hour=23,
                minute=59,
                second=59,
                tzinfo=BANGKOK_TZ,
            )
        else:
            expiration_date = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError('รูปแบบวันหมดอายุไม่ถูกต้อง')
    if expiration_date.tzinfo is None:
        expiration_date = expiration_date.replace(tzinfo=BANGKOK_TZ)
    if expiration_date <= datetime.now(BANGKOK_TZ):
        raise ValueError('วันหมดอายุต้องอยู่ในอนาคต')
    return expiration_date.astimezone(timezone.utc)


@shorturl.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """Render the form for creating a short URL."""
    long_url = request.form.get('long_url', '') if request.method == 'POST' else ''
    expiration_date = request.form.get('expiration_date', '') if request.method == 'POST' else ''
    short_url = None
    expires_at = None

    if request.method == 'POST':
        long_url = long_url.strip()
        if not _is_valid_long_url(long_url):
            flash('กรุณาระบุ URL ที่ถูกต้อง โดยต้องขึ้นต้นด้วย http:// หรือ https://', 'warning')
        else:
            try:
                expires_at = _parse_expiration_date(expiration_date)
            except ValueError as error:
                flash(str(error), 'warning')
            else:
                short_code = generate(size=10)
                while ShortUrlMapping.query.filter_by(short_code=short_code).first():
                    short_code = generate(size=10)
                mapping = ShortUrlMapping(
                    short_code=short_code,
                    long_url=long_url,
                    staff_account_id=current_user.id,
                    expires_at=expires_at,
                )
                db.session.add(mapping)
                db.session.commit()
                short_url = url_for('shorturl.redirect_short_url', short_code=short_code, _external=True)
                long_url = ''
                expiration_date = ''
                flash('สร้างลิงก์ย่อเรียบร้อยแล้ว', 'success')

    return render_template(
        'shorturl/index.html',
        long_url=long_url,
        expiration_date=expiration_date,
        short_url=short_url,
        expires_at=expires_at,
        bangkok_tz=BANGKOK_TZ,
        to_bangkok=_to_bangkok,
    )


@shorturl.get('/manage')
@login_required
def manage():
    """List short URLs created by the current staff member."""
    mappings = (
        ShortUrlMapping.query
        .filter_by(staff_account_id=current_user.id)
        .order_by(ShortUrlMapping.created_at.desc())
        .all()
    )
    return render_template(
        'shorturl/manage.html',
        mappings=mappings,
        to_bangkok=_to_bangkok,
        bangkok_tz=BANGKOK_TZ,
    )


@shorturl.post('/manage/<int:mapping_id>/edit')
@login_required
def edit_mapping(mapping_id):
    """Update the expiration of a short URL owned by the current staff member."""
    mapping = ShortUrlMapping.query.filter_by(
        id=mapping_id,
        staff_account_id=current_user.id,
    ).first_or_404()
    expiration_date = request.form.get('expiration_date', '').strip()

    try:
        mapping.expires_at = _parse_expiration_date(expiration_date)
    except ValueError as error:
        flash(str(error), 'warning')
        return redirect(url_for('shorturl.manage'))

    db.session.commit()
    flash('แก้ไขวันหมดอายุเรียบร้อยแล้ว', 'success')
    return redirect(url_for('shorturl.manage'))


@shorturl.post('/manage/<int:mapping_id>/delete')
@login_required
def delete_mapping(mapping_id):
    """Delete a short URL owned by the current staff member."""
    mapping = ShortUrlMapping.query.filter_by(
        id=mapping_id,
        staff_account_id=current_user.id,
    ).first_or_404()
    db.session.delete(mapping)
    db.session.commit()
    flash('ลบลิงค์เรียบร้อยแล้ว', 'success')
    return redirect(url_for('shorturl.manage'))


@shorturl.get('/<short_code>/expired')
def expired_short_url(short_code):
    """Show an explanatory page for an expired short URL."""
    mapping = ShortUrlMapping.query.filter_by(short_code=short_code).first_or_404()
    return render_template(
        'shorturl/expired.html',
        mapping=mapping,
        to_bangkok=_to_bangkok,
    ), 410


@shorturl.get('/<short_code>')
def redirect_short_url(short_code):
    """Redirect through an active short URL and increment its click count."""
    mapping = ShortUrlMapping.query.filter_by(short_code=short_code).first_or_404()
    now = datetime.now(timezone.utc)
    expires_at = mapping.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at <= now:
        return redirect(url_for('shorturl.expired_short_url', short_code=short_code))

    ShortUrlMapping.query.filter_by(id=mapping.id).update(
        {ShortUrlMapping.click_count: ShortUrlMapping.click_count + 1},
        synchronize_session=False,
    )
    db.session.commit()
    return redirect(mapping.long_url)
