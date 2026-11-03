"""Verify LINE identity on the server; never trust browser-supplied profiles."""
import requests
import math


CHECKIN_PLACES = {
    'salaya': ('ศาลายา', 13.798807859072065, 100.32312238370811),
    'siriraj': ('คณะเทคนิคการแพทย์ (ศิริราช)', 13.757932973700862, 100.48625575304426),
    'opd': ('สถานเวชศาสตร์ชันสูตร (ศิริราช)', 13.756927312875076, 100.48351451567528),
    'gj': ('ศูนย์การแพทย์กาญจนาภิเษก', 13.78719247243879, 100.32144635840142),
}
CHECKIN_MAX_DISTANCE_KM = 0.5


def validate_checkin_location(data):
    if (not isinstance(data, dict) or not isinstance(data.get('place'), str)
            or data['place'] not in CHECKIN_PLACES):
        raise ValueError('กรุณาเลือกสถานที่ปฏิบัติงาน')
    try:
        if isinstance(data.get('lat'), bool) or isinstance(data.get('lon'), bool):
            raise ValueError()
        lat, lon = float(data['lat']), float(data['lon'])
        if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise ValueError('ไม่พบพิกัด GPS ที่ถูกต้อง กรุณารับตำแหน่งอีกครั้ง')
    _, target_lat, target_lon = CHECKIN_PLACES[data['place']]
    dlat, dlon = math.radians(target_lat - lat), math.radians(target_lon - lon)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat)) * math.cos(math.radians(target_lat)) * math.sin(dlon / 2) ** 2
    # Match the distance calculation and 0.5 km threshold in MIS geo_checkin.
    distance = 2 * 6571 * math.asin(math.sqrt(min(1, max(0, a))))
    if distance > CHECKIN_MAX_DISTANCE_KM:
        raise ValueError('คุณอยู่นอกพื้นที่ลงเวลา กรุณาตรวจสอบสถานที่และพิกัด GPS (รัศมี 500 เมตร)')
    if not isinstance(data.get('confirm_checkout', False), bool):
        raise ValueError('ข้อมูลยืนยันการออกงานไม่ถูกต้อง')


class LineIdentityError(ValueError):
    pass


def verify_id_token(id_token, channel_id):
    if not isinstance(id_token, str) or not id_token or len(id_token) > 16384:
        raise LineIdentityError('Invalid LINE ID token')
    try:
        response = requests.post(
            'https://api.line.me/oauth2/v2.1/verify',
            data={'id_token': id_token, 'client_id': channel_id},
            timeout=10,
        )
        if response.status_code != 200:
            raise LineIdentityError('LINE rejected the ID token')
        claims = response.json()
        if not isinstance(claims, dict) or not isinstance(claims.get('sub'), str) or not claims['sub']:
            raise LineIdentityError('LINE identity is missing')
        return claims['sub']
    except (requests.RequestException, ValueError) as exc:
        raise LineIdentityError('Unable to verify LINE identity') from exc


def verify_access_token(access_token, channel_id):
    if not isinstance(access_token, str) or not access_token or len(access_token) > 16384:
        raise LineIdentityError('Invalid LINE access token')
    try:
        response = requests.get(
            'https://api.line.me/oauth2/v2.1/verify',
            params={'access_token': access_token}, timeout=10,
        )
        if response.status_code != 200:
            raise LineIdentityError('LINE rejected the access token')
        claims = response.json()
        if (not isinstance(claims, dict)
                or str(claims.get('client_id')) != str(channel_id)
                or float(claims.get('expires_in', 0)) <= 0
                or 'profile' not in claims.get('scope', '').split()):
            raise LineIdentityError('Wrong channel, expired token, or missing profile permission')
        profile = requests.get(
            'https://api.line.me/v2/profile',
            headers={'Authorization': 'Bearer ' + access_token}, timeout=10,
        )
        if profile.status_code != 200:
            raise LineIdentityError('Unable to retrieve verified LINE profile')
        data = profile.json()
        if not isinstance(data, dict) or not isinstance(data.get('userId'), str) or not data['userId']:
            raise LineIdentityError('LINE identity is missing')
        return data['userId']
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise LineIdentityError('Unable to verify LINE identity') from exc


def is_internal_staff(user):
    if not user.is_authenticated or not user.is_active:
        return False
    info = getattr(user, 'personal_info', None)
    org = getattr(info, 'org', None)
    return bool(info and org and not org.is_external)
