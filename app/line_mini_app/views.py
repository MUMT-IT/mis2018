from flask import abort, current_app, jsonify, render_template, request, session, url_for
from flask_login import current_user, login_user, login_required
from flask_principal import Identity, identity_changed

from . import bp
from .services import (CHECKIN_PLACES, CHECKIN_MAX_DISTANCE_KM, LineIdentityError, is_internal_staff,
                       verify_id_token, verify_access_token, validate_checkin_location)


@bp.after_request
def prevent_caching(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.route('/')
def index():
    staff_access = is_internal_staff(current_user)
    today_checkin_status = None
    today_calendar = None
    if staff_access:
        from datetime import datetime, timezone
        from pytz import timezone as local_timezone
        from app.main import (get_home_checkin_status, get_home_calendar_records,
                              build_home_today_calendar)
        tz = local_timezone('Asia/Bangkok')
        now = datetime.now(timezone.utc).astimezone(tz)
        today_checkin_status = get_home_checkin_status(current_user, now)
        month_start = tz.localize(datetime(now.year, now.month, 1))
        events, registrations = get_home_calendar_records(current_user, month_start)
        today_calendar = build_home_today_calendar(now, events, registrations, tz)
    return render_template(
        'line_mini_app/index.html',
        liff_id=current_app.config.get('LINE_MINI_APP_LIFF_ID'),
        staff_access=staff_access,
        today_checkin_status=today_checkin_status,
        today_calendar=today_calendar,
    )


@bp.route('/attendance/checkin', methods=['GET', 'POST'])
@login_required
def checkin():
    if not is_internal_staff(current_user):
        abort(403)
    if request.method == 'GET':
        return render_template('line_mini_app/checkin.html',
                               checkin_places=CHECKIN_PLACES,
                               max_distance_km=CHECKIN_MAX_DISTANCE_KM)
    payload = request.get_json(silent=True)
    try:
        validate_checkin_location(payload.get('data') if isinstance(payload, dict) else None)
    except ValueError as exc:
        return jsonify(message=str(exc)), 400
    # Reuse MIS recording, early-checkout confirmation, and LINE notification.
    from app.staff.views import geo_checkin
    return geo_checkin()


@bp.route('/attendance/requests')
@login_required
def attendance_requests():
    if not is_internal_staff(current_user):
        abort(403)
    from app.staff.models import StaffRequestWorkLogin
    from zoneinfo import ZoneInfo

    records = StaffRequestWorkLogin.query.filter_by(
        staff_account_id=current_user.id,
    ).order_by(
        StaffRequestWorkLogin.requested_at.desc(),
        StaffRequestWorkLogin.id.desc(),
    ).limit(20).all()
    items = []
    for record in records:
        work_time = record.work_datetime
        # PostgreSQL stores these timestamps with timezone information.
        if work_time is not None:
            if work_time.tzinfo is None:
                work_time = work_time.replace(tzinfo=ZoneInfo('UTC'))
            work_time = work_time.astimezone(ZoneInfo('Asia/Bangkok'))
        state = 'approved' if record.approved_at else 'closed' if record.cancelled_at else 'pending'
        items.append({
            'kind': 'รับรองเวลาเข้างาน' if record.is_checkin else 'รับรองเวลาออกงาน',
            'date': work_time.strftime('%d/%m/%Y') if work_time else 'ไม่ระบุวันที่',
            'time': work_time.strftime('%H:%M') if work_time else '—',
            'reason': record.reason or 'ไม่ระบุเหตุผล',
            'state': state,
            'status': {'approved': 'อนุมัติแล้ว', 'closed': 'ปิดคำขอ', 'pending': 'รออนุมัติ'}[state],
        })
    return render_template('line_mini_app/attendance_requests.html', items=items)


@bp.route('/auth', methods=['POST'])
def authenticate():
    # Keep Flask-WTF CSRF protection enabled for this session-creating endpoint.
    channel_id = current_app.config.get('LINE_MINI_APP_CHANNEL_ID')
    if not channel_id:
        return jsonify(message='ยังไม่ได้ตั้งค่าการเข้าสู่ระบบ LINE'), 503
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(message='ข้อมูลเข้าสู่ระบบไม่ถูกต้อง'), 400
    try:
        if payload.get('id_token'):
            line_id = verify_id_token(payload['id_token'], channel_id)
        else:
            line_id = verify_access_token(payload.get('access_token'), channel_id)
    except LineIdentityError:
        return jsonify(message='ตรวจสอบบัญชี LINE ไม่สำเร็จ กรุณาลองใหม่'), 401

    from app.staff.models import StaffAccount
    user = StaffAccount.query.filter_by(line_id=line_id).first()
    if user is None:
        return jsonify(
            message='กรุณาเข้าสู่ระบบ MIS และเชื่อมบัญชี LINE ในหน้าบัญชีผู้ใช้ก่อน แล้วกลับมาเปิดเมนูนี้อีกครั้ง',
            link_url=url_for('auth.account'),
        ), 403
    if not is_internal_staff(user):
        return jsonify(message='บริการนี้สำหรับบุคลากรภายในที่มีบัญชีใช้งานอยู่'), 403
    if current_user.is_authenticated and current_user.get_id() != user.get_id():
        return jsonify(message='บัญชี MIS ที่เปิดอยู่ไม่ตรงกับบัญชี LINE กรุณาออกจากระบบ MIS ก่อนแล้วลองใหม่'), 409
    if not login_user(user):
        return jsonify(message='ไม่สามารถเข้าสู่ระบบด้วยบัญชีนี้ได้'), 403
    session['user_type'] = 'staff'
    identity_changed.send(current_app._get_current_object(), identity=Identity(user.id))
    return jsonify(redirect_url=url_for('line_mini_app.index'))
