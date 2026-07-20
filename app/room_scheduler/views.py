import calendar
import dateutil.parser
import arrow
import json
import os
import pytz
import re
import requests
from datetime import datetime, timedelta
from dateutil import parser
from flask import render_template, jsonify, request, flash, redirect, url_for, current_app, make_response
from flask_login import login_required, current_user
from app.linebot_compat import LineBotApiError, TextSendMessage
from psycopg2.extras import DateTimeRange
from sqlalchemy import or_
from sqlalchemy.sql import text
from app.main import mail
from .forms import RoomEventForm
from ..auth.views import line_bot_api
from ..complaint_tracker.models import ComplaintRecord, ComplaintStatus, ComplaintTopic
from ..main import db
from . import roombp as room
from .models import RoomResource, RoomEvent, EventCategory, room_coordinator_assoc
from .normalizer import normalize_user_request
from ..models import IOCode
from flask_mail import Message

from ..staff.models import StaffAccount, StaffGroupDetail

localtz = pytz.timezone('Asia/Bangkok')


def _ics_escape(value):
    if not value:
        return ''
    return str(value).replace('\\', '\\\\').replace(';', r'\;').replace(',', r'\,').replace('\n', r'\n')


def _ics_timestamp(dt):
    return dt.astimezone(pytz.utc).strftime('%Y%m%dT%H%M%SZ')


def _ics_param_escape(value):
    if not value:
        return ''
    return str(value).replace('\\', '\\\\').replace(';', r'\;').replace(',', r'\,').replace('"', r'\"')


def build_room_event_ics(events, method='REQUEST'):
    if not events:
        return None

    timestamp = _ics_timestamp(arrow.now('Asia/Bangkok').datetime)
    lines = [
        'BEGIN:VCALENDAR',
        'PRODID:-//MUMT-MIS//Room Scheduler//EN',
        'VERSION:2.0',
        'CALSCALE:GREGORIAN',
        f'METHOD:{method}',
    ]
    system_mail = os.getenv('MAIL_USERNAME') or 'no-reply@mt.mahidol.ac.th'

    for event in events:
        start_dt = event.start if event.start.tzinfo else localtz.localize(event.start)
        end_dt = event.end if event.end.tzinfo else localtz.localize(event.end)
        room_name = f'{event.room.number} {event.room.location}'
        organizer = event.creator or current_user
        organizer_email = system_mail
        organizer_name = _ics_param_escape('MUMT-MIS')
        description_parts = []
        if event.note:
            description_parts.append(event.note)
        description_parts.append(f'Room: {room_name}')
        if getattr(organizer, 'fullname', None):
            description_parts.append(f'Booked by: {organizer.fullname}')
        description = _ics_escape('\n'.join(description_parts))

        lines.extend([
            'BEGIN:VEVENT',
            f'UID:room-event-{event.id}@mt.mahidol.ac.th',
            f'DTSTAMP:{timestamp}',
            f'DTSTART:{_ics_timestamp(start_dt)}',
            f'DTEND:{_ics_timestamp(end_dt)}',
            f'SUMMARY:{_ics_escape(event.title)}',
            f'LOCATION:{_ics_escape(room_name)}',
            f'DESCRIPTION:{description}',
            'STATUS:CONFIRMED',
            'TRANSP:OPAQUE',
            'SEQUENCE:0',
            f'ORGANIZER;CN={organizer_name}:MAILTO:{organizer_email}',
        ])
        attendees = {}
        for participant in event.participants or []:
            if not getattr(participant, 'email', None):
                continue
            attendee_email = f'{participant.email}@mahidol.ac.th'
            attendees[attendee_email.lower()] = _ics_param_escape(getattr(participant, 'fullname', participant.email))

        for attendee_email, attendee_name in attendees.items():
            lines.append(
                f'ATTENDEE;CN={attendee_name};CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:MAILTO:{attendee_email}'
            )
        lines.append('END:VEVENT')

    lines.append('END:VCALENDAR')
    return '\r\n'.join(lines).encode('utf-8')


def send_mail(recp, title, message, attachments=None):
    message = Message(subject=title, body=message, recipients=recp)
    for attachment in attachments or []:
        message.attach(
            filename=attachment['filename'],
            data=attachment['data'],
            content_type=attachment['content_type'],
            headers=attachment.get('headers'),
        )
    mail.send(message)


def _extract_json_payload(raw_text):
    if not raw_text:
        raise ValueError('Empty Typhoon response.')
    payload = raw_text.strip()
    if payload.startswith('```'):
        payload = re.sub(r'^```(?:json)?\s*', '', payload)
        payload = re.sub(r'\s*```$', '', payload)
    match = re.search(r'\{.*\}', payload, flags=re.DOTALL)
    if match:
        payload = match.group(0)
    return json.loads(payload)


def _normalize_assumptions(value):
    if not value:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        items = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                items.append(text)
        return list(dict.fromkeys(items))
    text = str(value).strip()
    return [text] if text else []


def _sanitize_room_query_text(value):
    if not value:
        return ''
    text = re.sub(r'<[^>]+>', ' ', str(value))
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _safe_parse_date(date_value):
    if not date_value:
        return None
    try:
        return datetime.strptime(date_value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _safe_parse_time(time_value):
    if not time_value:
        return None
    cleaned = str(time_value).strip()
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(cleaned, fmt).time()
        except ValueError:
            continue
    return None


def _parse_thai_relative_date(text_value):
    if not text_value:
        return None
    text_raw = str(text_value)
    text_lower = text_raw.lower()
    today = arrow.now('Asia/Bangkok').date()
    if 'วันนี้' in text_lower:
        return today
    if 'พรุ่งนี้' in text_lower:
        return today + timedelta(days=1)
    if 'มะรืน' in text_lower or 'วันมะรืน' in text_lower:
        return today + timedelta(days=2)
    if 'สัปดาห์หน้า' in text_lower:
        return today + timedelta(days=7)

    weekday_map = {
        0: ['จันทร์', 'จันทร์บดี', 'monday'],
        1: ['อังคาร', 'tuesday'],
        2: ['พุธ', 'wednesday'],
        3: ['พฤหัส', 'พฤหัสบดี', 'thursday'],
        4: ['ศุกร์', 'friday'],
        5: ['เสาร์', 'saturday'],
        6: ['อาทิตย์', 'อาทิตย์์', 'sunday'],
    }
    current_week_start = today - timedelta(days=today.weekday())
    next_week_start = current_week_start + timedelta(days=7)
    for weekday, aliases in weekday_map.items():
        if any((f'วัน{alias}นี้' in text_raw) or (f'{alias}นี้' in text_raw) or (f'this {alias}' in text_lower) for alias in aliases):
            return current_week_start + timedelta(days=weekday)
        if any((f'วัน{alias}หน้า' in text_raw) or (f'{alias}หน้า' in text_raw) or (f'next {alias}' in text_lower) for alias in aliases):
            return next_week_start + timedelta(days=weekday)
        if any((f'วัน{alias}' in text_raw) or re.search(rf'\b{re.escape(alias)}\b', text_lower) for alias in aliases):
            delta = weekday - today.weekday()
            if delta < 0:
                delta += 7
            return today + timedelta(days=delta)
    return None


def _parse_message_date(text_value):
    if not text_value:
        return None
    relative_date = _parse_thai_relative_date(text_value)
    if relative_date:
        return relative_date

    iso_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', text_value)
    if iso_match:
        return _safe_parse_date(iso_match.group(1))

    thai_match = re.search(r'\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})\b', text_value)
    if thai_match:
        day, month, year = [int(part) for part in thai_match.groups()]
        if year < 100:
            year += 2000
        if year > 2400:
            year -= 543
        try:
            return datetime(year, month, day).date()
        except ValueError:
            return None
    return None


def _resolve_room_request_date(normalized_text, resolved_date=None, raw_text=None):
    raw_parsed_date = _parse_message_date(raw_text)
    if raw_parsed_date:
        return raw_parsed_date

    parsed_resolved_date = _safe_parse_date(resolved_date) if resolved_date else None
    if parsed_resolved_date:
        return parsed_resolved_date

    return _parse_message_date(normalized_text)


def _contains_relative_or_weekday_reference(text_value):
    if not text_value:
        return False
    text_raw = str(text_value)
    text_lower = text_raw.lower()
    weekday_tokens = [
        'จันทร์', 'อังคาร', 'พุธ', 'พฤหัส', 'พฤหัสบดี', 'ศุกร์', 'เสาร์', 'อาทิตย์',
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'
    ]
    relative_tokens = ['วันนี้', 'พรุ่งนี้', 'มะรืน', 'วันมะรืน', 'สัปดาห์หน้า', 'this ', 'next ']
    return any(token in text_raw for token in weekday_tokens) or any(token in text_lower for token in relative_tokens)


def _parse_duration_hours(text_value):
    if not text_value:
        return None
    match = re.search(r'(\d+(?:\.\d+)?)\s*ชั่วโมง', text_value)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    if 'ครึ่งวัน' in text_value:
        return 4.0
    return None


def _default_duration_hours():
    return 3.0


def _time_from_parts(hour_text, minute_text=None):
    hour = int(hour_text)
    minute = int(minute_text) if minute_text is not None else 0
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return datetime.strptime(f'{hour:02d}:{minute:02d}', '%H:%M').time()
    return None


def _parse_message_times(text_value):
    if not text_value:
        return None, None

    range_match = re.search(
        r'(\d{1,2})(?:[:\.](\d{2}))?\s*(?:-|ถึง|to)\s*(\d{1,2})(?:[:\.](\d{2}))?',
        text_value
    )
    if range_match:
        start_time = _time_from_parts(range_match.group(1), range_match.group(2))
        end_time = _time_from_parts(range_match.group(3), range_match.group(4))
        return start_time, end_time

    single_time_match = re.search(r'(?:เวลา|เริ่ม|ตอน)\s*(\d{1,2})(?:[:\.](\d{2}))?', text_value)
    if single_time_match:
        start_time = _time_from_parts(single_time_match.group(1), single_time_match.group(2))
        duration_hours = _parse_duration_hours(text_value) or _default_duration_hours()
        if start_time and duration_hours:
            start_dt = datetime.combine(datetime.today().date(), start_time)
            end_dt = start_dt + timedelta(hours=duration_hours)
            return start_time, end_dt.time()
        return start_time, None

    part_of_day_map = {
        'ตอนเช้า': ('09:00', '12:00'),
        'ช่วงเช้า': ('09:00', '12:00'),
        'เช้า': ('09:00', '12:00'),
        'ตอนบ่าย': ('13:00', '16:00'),
        'ช่วงบ่าย': ('13:00', '16:00'),
        'บ่าย': ('13:00', '16:00'),
        'ตอนเย็น': ('16:00', '19:00'),
        'ช่วงเย็น': ('16:00', '19:00'),
        'เย็น': ('16:00', '19:00'),
    }
    for phrase, (start_text, end_text) in part_of_day_map.items():
        if phrase in text_value:
            return _safe_parse_time(start_text), _safe_parse_time(end_text)
    return None, None


def _parse_capacity_from_message(text_value):
    if not text_value:
        return None
    match = re.search(r'(\d+)\s*(?:คน|ท่าน|ที่นั่ง)', text_value)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _parse_floor_from_message(text_value):
    if not text_value:
        return None

    digit_match = re.search(r'ชั้น\s*(\d+)', text_value)
    if digit_match:
        return digit_match.group(1)

    thai_number_map = {
        'หนึ่ง': '1',
        'สอง': '2',
        'สาม': '3',
        'สี่': '4',
        'ห้า': '5',
        'หก': '6',
        'เจ็ด': '7',
        'แปด': '8',
        'เก้า': '9',
        'สิบ': '10',
    }
    for thai_word, digit in thai_number_map.items():
        if f'ชั้น{thai_word}' in text_value or f'ชั้น {thai_word}' in text_value:
            return digit

    floor_word_match = re.search(r'floor\s*(\d+)', str(text_value).lower())
    if floor_word_match:
        return floor_word_match.group(1)

    return None


def _infer_location_from_message(text_value, current_location=None):
    if current_location:
        return current_location
    if not text_value:
        return 'ศาลายา'
    text_lower = str(text_value).lower()
    if 'ศิริราช' in text_value or 'siriraj' in text_lower:
        return 'ศิริราช'
    if 'พญาไท' in text_value or 'phayathai' in text_lower or 'phyathai' in text_lower:
        return 'พญาไท'
    if 'ศาลายา' in text_value or 'salaya' in text_lower:
        return 'ศาลายา'
    return 'ศาลายา'


def _location_is_explicitly_mentioned(text_value):
    if not text_value:
        return False
    text_lower = str(text_value).lower()
    return any(keyword in text_lower for keyword in ['ศาลายา', 'salaya', 'ศิริราช', 'siriraj', 'พญาไท', 'phayathai', 'phyathai'])


def _infer_purpose_from_message(text_value, current_purpose=None):
    user_text = (text_value or '').strip()
    if not user_text and not current_purpose:
        return None
    purpose_patterns = [
        ('สอน', r'ห้องเรียน|หาห้องเรียน|classroom'),
        ('สอน', r'ห้องปฏิบัติการ|ห้องแลบ|lab room|laboratory'),
        ('ประชุม', r'ประชุมคณะกรรมการ'),
        ('ประชุมทีมบริหาร', r'ประชุมทีมบริหาร|ทีมบริหาร'),
        ('อบรมเชิงปฏิบัติการ', r'อบรมเชิงปฏิบัติการ|workshop'),
        ('ประชุม', r'ประชุม|meeting'),
        ('สอน', r'สอน|เรียน|class|lecture'),
        ('อบรม', r'อบรม|training'),
        ('สัมมนา', r'สัมมนา|seminar'),
        ('สอบ', r'สอบ|exam'),
        ('นำเสนอ', r'นำเสนอ|presentation|pitch'),
    ]
    for label, pattern in purpose_patterns:
        if re.search(pattern, user_text, flags=re.IGNORECASE):
            return label

    source_text = current_purpose.strip() if current_purpose and len(current_purpose.strip()) <= 40 else user_text
    for label, pattern in purpose_patterns:
        if re.search(pattern, source_text, flags=re.IGNORECASE):
            return label
    return source_text.strip()[:80]


def _normalize_location_terms(location_value):
    location = (location_value or 'ศาลายา').strip() or 'ศาลายา'
    location_lower = location.lower()
    if 'ศาลายา' in location or 'salaya' in location_lower:
        return location, '%ศาลายา%', '%salaya%'
    if 'ศิริราช' in location or 'siriraj' in location_lower:
        return location, '%ศิริราช%', '%siriraj%'
    if 'พญาไท' in location or 'phayathai' in location_lower or 'phyathai' in location_lower:
        return location, '%พญาไท%', '%phayathai%'
    english_pattern = f'%{location}%' if re.search(r'[A-Za-z]', location) else None
    return location, f'%{location}%', english_pattern


def _tokenize_search_text(text_value):
    if not text_value:
        return []
    tokens = []
    for token in re.split(r'[\s,;/()]+', str(text_value).strip()):
        token = token.strip()
        if len(token) >= 2:
            tokens.append(token)
    return tokens[:5]


def _expand_purpose_tokens(purpose):
    tokens = _tokenize_search_text(purpose)
    purpose_lower = (purpose or '').lower()
    expansion_map = {
        'ประชุม': ['meeting', 'conference', 'กรรมการ'],
        'สอน': ['เรียน', 'class', 'lecture'],
        'อบรม': ['training', 'workshop', 'ปฏิบัติการ'],
        'สัมมนา': ['seminar'],
        'สอบ': ['exam', 'test'],
        'นำเสนอ': ['presentation', 'pitch'],
    }
    for key, related_tokens in expansion_map.items():
        if key in (purpose or '') or key in purpose_lower:
            tokens.extend(related_tokens)
    deduped = []
    seen = set()
    for token in tokens:
        normalized = token.lower()
        if normalized not in seen:
            deduped.append(token)
            seen.add(normalized)
    return deduped[:5]


def _is_generic_purpose(purpose):
    purpose_text = (purpose or '').strip().lower()
    generic_purposes = {
        'ประชุม', 'meeting',
        'สอน', 'เรียน', 'class', 'lecture',
        'อบรม', 'training',
        'สัมมนา', 'seminar',
        'สอบ', 'exam', 'test',
        'นำเสนอ', 'presentation', 'pitch',
        'ประชุมทีมบริหาร'
    }
    return purpose_text in generic_purposes


def _derive_required_room_types(purpose):
    purpose_text = (purpose or '').strip().lower()
    if not purpose_text:
        return []

    if any(keyword in purpose for keyword in ['ประชุม']) or 'meeting' in purpose_text:
        return ['%ประชุม%', '%meeting%', '%conference%']

    if any(keyword in purpose for keyword in ['ห้องเรียน']) or 'classroom' in purpose_text:
        return ['%เรียน%', '%class%', '%lecture%']

    if any(keyword in purpose for keyword in ['ห้องปฏิบัติการ', 'ห้องแลบ']) or any(keyword in purpose_text for keyword in ['lab', 'laboratory']):
        return ['%ปฏิบัติการ%', '%lab%', '%laboratory%']

    if any(keyword in purpose for keyword in ['สอน', 'เรียน']) or any(keyword in purpose_text for keyword in ['class', 'lecture']):
        return ['%เรียน%', '%class%', '%lecture%', '%ปฏิบัติการ%', '%lab%']

    return []


def _fallback_room_query_sql():
    return text("""
        SELECT
            r.id,
            r.number,
            r.location,
            r.floor,
            r.occupancy,
            COALESCE(r."desc", '') AS description,
            COALESCE(a.availability, '') AS availability,
            COALESCE(t.type, '') AS room_type,
            r.business_hour_start,
            r.business_hour_end
        FROM scheduler_room_resources AS r
        LEFT JOIN scheduler_room_avails AS a ON a.id = r.availability_id
        LEFT JOIN scheduler_room_types AS t ON t.id = r.type_id
        WHERE r.availability_id IS NOT NULL
          AND (
            :location_keyword IS NULL
            OR COALESCE(r.location, '') ILIKE :location_keyword
            OR COALESCE(r.location, '') ILIKE :location_keyword_en
            OR COALESCE(r."desc", '') ILIKE :location_keyword
            OR COALESCE(r."desc", '') ILIKE :location_keyword_en
          )
          AND (:capacity IS NULL OR r.occupancy >= :capacity)
          AND (
            :floor_keyword IS NULL
            OR COALESCE(r.floor, '') ILIKE :floor_keyword
          )
          AND (
            :start_time IS NULL
            OR r.business_hour_start IS NULL
            OR r.business_hour_start <= :start_time
          )
          AND (
            :end_time IS NULL
            OR r.business_hour_end IS NULL
            OR r.business_hour_end >= :end_time
          )
          AND (
            :purpose_keyword IS NULL
            OR COALESCE(r.number, '') ILIKE :purpose_keyword
            OR COALESCE(r.location, '') ILIKE :purpose_keyword
            OR COALESCE(r."desc", '') ILIKE :purpose_keyword
            OR COALESCE(t.type, '') ILIKE :purpose_keyword
          )
          AND (
            :purpose_token_1 IS NULL
            OR COALESCE(r.number, '') ILIKE :purpose_token_1
            OR COALESCE(r."desc", '') ILIKE :purpose_token_1
            OR COALESCE(t.type, '') ILIKE :purpose_token_1
          )
          AND (
            :purpose_token_2 IS NULL
            OR COALESCE(r.number, '') ILIKE :purpose_token_2
            OR COALESCE(r."desc", '') ILIKE :purpose_token_2
            OR COALESCE(t.type, '') ILIKE :purpose_token_2
          )
          AND (
            :purpose_token_3 IS NULL
            OR COALESCE(r.number, '') ILIKE :purpose_token_3
            OR COALESCE(r."desc", '') ILIKE :purpose_token_3
            OR COALESCE(t.type, '') ILIKE :purpose_token_3
          )
          AND (
            :purpose_token_4 IS NULL
            OR COALESCE(r.number, '') ILIKE :purpose_token_4
            OR COALESCE(r."desc", '') ILIKE :purpose_token_4
            OR COALESCE(t.type, '') ILIKE :purpose_token_4
          )
          AND (
            :purpose_token_5 IS NULL
            OR COALESCE(r.number, '') ILIKE :purpose_token_5
            OR COALESCE(r."desc", '') ILIKE :purpose_token_5
            OR COALESCE(t.type, '') ILIKE :purpose_token_5
          )
          AND (
            :required_room_type_1 IS NULL
            OR COALESCE(t.type, '') ILIKE :required_room_type_1
            OR COALESCE(t.type, '') ILIKE :required_room_type_2
            OR COALESCE(t.type, '') ILIKE :required_room_type_3
            OR COALESCE(t.type, '') ILIKE :required_room_type_4
            OR COALESCE(t.type, '') ILIKE :required_room_type_5
          )
          AND (
            :start_at IS NULL
            OR :end_at IS NULL
            OR NOT EXISTS (
                SELECT 1
                FROM scheduler_room_reservations AS e
                WHERE e.room_id = r.id
                  AND e.cancelled_at IS NULL
                  AND e.datetime && tsrange(:start_at, :end_at, '[]')
            )
          )
        ORDER BY
            r.occupancy ASC,
            r.location ASC,
            r.number ASC
    """)


def _format_room_rows(rows):
    formatted = []
    for row in rows:
        formatted.append({
            'id': row['id'],
            'number': row['number'],
            'location': row['location'],
            'floor': row['floor'],
            'occupancy': row['occupancy'],
            'description': row['description'],
            'availability': row['availability'],
            'room_type': row['room_type'],
            'business_hour_start': row['business_hour_start'].strftime('%H:%M') if row['business_hour_start'] else None,
            'business_hour_end': row['business_hour_end'].strftime('%H:%M') if row['business_hour_end'] else None,
            'reserve_url': url_for('room.room_reserve', room_id=row['id']),
        })
    return formatted


def _build_reserve_url(room_id, criteria):
    query = {}
    if criteria.get('purpose'):
        query['title'] = criteria.get('purpose')
    if criteria.get('capacity'):
        query['occupancy'] = criteria.get('capacity')
    if criteria.get('date') and criteria.get('start_time'):
        query['start'] = f"{criteria['date']} {criteria['start_time']}"
    if criteria.get('date') and criteria.get('end_time'):
        query['end'] = f"{criteria['date']} {criteria['end_time']}"
    return url_for('room.room_reserve', room_id=room_id, **query)


def _attach_reserve_urls(rooms, criteria):
    for room in rooms:
        room['reserve_url'] = _build_reserve_url(room['id'], criteria)
    return rooms


def _prefill_room_reserve_form(form):
    title = request.args.get('title', '').strip()
    occupancy = request.args.get('occupancy', type=int)
    start_value = request.args.get('start', '').strip()
    end_value = request.args.get('end', '').strip()

    if title:
        form.title.data = title
    if occupancy:
        form.occupancy.data = occupancy

    if start_value:
        try:
            form.start.data = datetime.strptime(start_value, '%Y-%m-%d %H:%M')
        except ValueError:
            pass

    if end_value:
        try:
            form.end.data = datetime.strptime(end_value, '%Y-%m-%d %H:%M')
        except ValueError:
            pass

    category = _infer_event_category(title)
    if category:
        form.category.data = category


def _infer_event_category(purpose):
    if not purpose:
        return None

    purpose_text = str(purpose).strip().lower()
    category_preferences = []

    if any(keyword in purpose for keyword in ['สอน', 'เรียน', 'ห้องเรียน', 'ห้องปฏิบัติการ']) or any(keyword in purpose_text for keyword in ['class', 'lecture', 'classroom', 'lab', 'laboratory']):
        category_preferences = ['การเรียนการสอน', 'เรียน', 'สอน']
    elif any(keyword in purpose for keyword in ['ประชุม']) or 'meeting' in purpose_text:
        category_preferences = ['การประชุม', 'ประชุม']
    elif any(keyword in purpose for keyword in ['อบรม']) or 'training' in purpose_text:
        category_preferences = ['อบรม', 'การฝึกอบรม']
    elif any(keyword in purpose for keyword in ['สัมมนา']) or 'seminar' in purpose_text:
        category_preferences = ['สัมมนา']

    if not category_preferences:
        return None

    categories = EventCategory.query.all()
    for preferred in category_preferences:
        for category in categories:
            if preferred in (category.category or ''):
                return category
    return None


def _parse_room_criteria(normalized_text, resolved_date=None, raw_text=None):
    criteria = {}
    criteria['purpose'] = _infer_purpose_from_message(normalized_text)
    criteria['location'] = _infer_location_from_message(normalized_text)
    criteria['location_explicit'] = _location_is_explicitly_mentioned(normalized_text)
    criteria['floor'] = _parse_floor_from_message(normalized_text)
    criteria['relative_date_explicit'] = _contains_relative_or_weekday_reference(normalized_text)

    parsed_date = _resolve_room_request_date(normalized_text, resolved_date=resolved_date, raw_text=raw_text)
    if parsed_date:
        criteria['date'] = parsed_date.isoformat()

    parsed_start_time, parsed_end_time = _parse_message_times(normalized_text)
    if parsed_start_time:
        criteria['start_time'] = parsed_start_time.strftime('%H:%M')
    if parsed_end_time:
        criteria['end_time'] = parsed_end_time.strftime('%H:%M')

    parsed_capacity = _parse_capacity_from_message(normalized_text)
    if parsed_capacity:
        criteria['capacity'] = parsed_capacity

    if criteria.get('start_time') and not criteria.get('end_time'):
        start_time = _safe_parse_time(criteria.get('start_time'))
        duration_hours = _parse_duration_hours(normalized_text) or _default_duration_hours()
        if start_time and duration_hours:
            start_dt = datetime.combine(datetime.today().date(), start_time)
            criteria['end_time'] = (start_dt + timedelta(hours=duration_hours)).time().strftime('%H:%M')

    assumptions = []
    if not criteria['location_explicit']:
        assumptions.append('ไม่ได้ระบุสถานที่ จึงใช้ศาลายาเป็นค่าเริ่มต้น')
    criteria['assumptions'] = _normalize_assumptions(assumptions)
    return criteria


def _build_room_query_params(criteria):
    normalized_location, location_keyword, location_keyword_en = _normalize_location_terms(criteria.get('location'))
    purpose = (criteria.get('purpose') or '').strip()
    purpose_tokens = _expand_purpose_tokens(purpose)
    required_room_types = _derive_required_room_types(purpose)
    generic_purpose = _is_generic_purpose(purpose)
    floor = str(criteria.get('floor')).strip() if criteria.get('floor') not in (None, '') else None
    meeting_date = _safe_parse_date(criteria.get('date'))
    start_time = _safe_parse_time(criteria.get('start_time'))
    end_time = _safe_parse_time(criteria.get('end_time'))
    capacity = criteria.get('capacity')
    try:
        capacity = int(capacity) if capacity not in (None, '', 0, '0') else None
    except (TypeError, ValueError):
        capacity = None

    start_at = None
    end_at = None
    if meeting_date and start_time and end_time:
        start_at = datetime.combine(meeting_date, start_time)
        end_at = datetime.combine(meeting_date, end_time)

    params = {
        'location_keyword': location_keyword,
        'location_keyword_en': location_keyword_en,
        'purpose_keyword': f'%{purpose}%' if purpose and not generic_purpose else None,
        'capacity': capacity,
        'floor_keyword': f'%{floor}%' if floor else None,
        'start_time': start_time,
        'end_time': end_time,
        'start_at': start_at,
        'end_at': end_at,
        'required_room_type_1': required_room_types[0] if len(required_room_types) > 0 else None,
        'required_room_type_2': required_room_types[1] if len(required_room_types) > 1 else None,
        'required_room_type_3': required_room_types[2] if len(required_room_types) > 2 else None,
        'required_room_type_4': required_room_types[3] if len(required_room_types) > 3 else None,
        'required_room_type_5': required_room_types[4] if len(required_room_types) > 4 else None,
    }
    for idx in range(5):
        token = purpose_tokens[idx] if idx < len(purpose_tokens) and not generic_purpose else None
        params[f'purpose_token_{idx + 1}'] = f'%{token}%' if token else None

    criteria['location'] = normalized_location
    criteria['capacity'] = capacity
    criteria['floor'] = floor
    criteria['date'] = meeting_date.isoformat() if meeting_date else None
    criteria['start_time'] = start_time.strftime('%H:%M') if start_time else None
    criteria['end_time'] = end_time.strftime('%H:%M') if end_time else None
    return params


def _summarize_room_request(criteria, rooms):
    segments = []
    if criteria.get('purpose'):
        segments.append(f"วัตถุประสงค์ '{criteria['purpose']}'")
    if criteria.get('location'):
        segments.append(f"สถานที่ {criteria['location']}")
    if criteria.get('floor'):
        segments.append(f"ชั้น {criteria['floor']}")
    if criteria.get('date'):
        segments.append(f"วันที่ {criteria['date']}")
    if criteria.get('start_time') and criteria.get('end_time'):
        segments.append(f"เวลา {criteria['start_time']}-{criteria['end_time']}")
    if criteria.get('capacity'):
        segments.append(f"รองรับอย่างน้อย {criteria['capacity']} คน")
    criteria_text = ' | '.join(segments) if segments else 'ตามข้อความที่ส่งมา'
    if rooms:
        return f'พบห้องที่ตรงเงื่อนไข {len(rooms)} ห้อง สำหรับ {criteria_text}'
    return f'ไม่พบห้องที่ตรงเงื่อนไข สำหรับ {criteria_text}'


def _execute_ai_room_search(criteria):
    params = _build_room_query_params(criteria)
    rows = db.session.execute(_fallback_room_query_sql(), params).mappings().all()
    rooms = _attach_reserve_urls(_format_room_rows(rows), criteria)
    fallback_used = False

    if not rooms and not criteria.get('location_explicit'):
        relaxed_params = dict(params)
        relaxed_params['location_keyword'] = None
        relaxed_params['location_keyword_en'] = None
        rows = db.session.execute(_fallback_room_query_sql(), relaxed_params).mappings().all()
        rooms = _attach_reserve_urls(_format_room_rows(rows), criteria)
        fallback_used = bool(rooms)

    return rooms, fallback_used


def create_event(startdatetime, enddatetime, repeat_end, master_id, room_id, form):
    event = RoomEvent()
    form.populate_obj(event)
    event.datetime = DateTimeRange(lower=startdatetime, upper=enddatetime, bounds='[]')
    event.start = startdatetime
    event.end = enddatetime
    event.repeat_end = repeat_end
    event.created_at = arrow.now('Asia/Bangkok').datetime
    event.creator = current_user
    event.room_id = room_id
    event.master_id = master_id
    if request.form.getlist('groups'):
        for group_id in request.form.getlist('groups'):
            group = StaffGroupDetail.query.get(group_id)
            for g in group.group_members:
                event.participants.append(g.staff)
    db.session.add(event)
    db.session.commit()
    return event


def _collect_booking_series(event):
    master_id = event.master_id or event.id
    events = RoomEvent.query.filter(
        or_(RoomEvent.master_id == master_id, RoomEvent.id == master_id)
    ).order_by(RoomEvent.start).all()
    return events or [event]


def _build_room_event_attachment(event):
    ics_data = build_room_event_ics(_collect_booking_series(event))
    if not ics_data:
        return []
    return [{
        'filename': f'room-booking-{event.id}.ics',
        'data': ics_data,
        'content_type': 'text/calendar; charset=utf-8; method=REQUEST',
        'headers': [('Content-Class', 'urn:content-classes:calendarmessage')],
    }]

@room.route('/api/iocodes')
@login_required
def get_iocodes():
    codes = []
    for code in IOCode.query.all():
        codes.append(code.to_dict())

    return jsonify(codes)


@room.route('/api/rooms')
@login_required
def get_rooms():
    query = request.args.get('query', 'all')
    if query == 'coordinators':
        rooms = current_user.rooms
    else:
        rooms = RoomResource.query.all()
    resources = []
    for rm in rooms:
        if query == 'reservable':
            if not rm.availability:
                continue
        resources.append({
            'id': rm.id,
            'location': rm.location,
            'title': rm.number,
            'occupancy': rm.occupancy,
            'businessHours': {
                'start': rm.business_hour_start.strftime('%H:%M') if rm.business_hour_start else None,
                'end': rm.business_hour_end.strftime('%H:%M') if rm.business_hour_end else None,
            }
        })
    return jsonify(resources)


@room.route('/api/events')
@login_required
def get_events():
    cal_query = request.args.get('query', 'all')
    cal_start = request.args.get('start')
    cal_end = request.args.get('end')
    if cal_start:
        cal_start = parser.isoparse(cal_start)
    if cal_end:
        cal_end = parser.isoparse(cal_end)
    all_events = []
    query = RoomEvent.query.filter(RoomEvent.datetime.op('&&')(DateTimeRange(lower=cal_start, upper=cal_end, bounds='[]')))
    text_color = '#000000'
    for event in query.filter_by(cancelled_at=None):
        if cal_query == 'some' and event.room not in current_user.rooms:
            # only return event with the room coordinated by the user.
            continue

        # The event object is a dict object with a 'summary' key.
        start = localtz.localize(event.datetime.lower)
        end = localtz.localize(event.datetime.upper)
        room = event.room

        evt = {
            'location': room.location,
            'title': u'({} {})({}) {} ({} คน): {}'.format(room.number, room.location, event.creator.fullname[:14] + '..' if len(event.creator.fullname) >= 14 else event.creator.fullname, event.title, event.occupancy, event.note),
            'description': event.note,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'resourceId': room.id,
            'status': event.approved,
            'borderColor': '#000000',
            'backgroundColor': room.type.color if room.type else '#fafbfc',
            'textColor': text_color,
            'id': event.id,
        }
        all_events.append(evt)
    return jsonify(all_events)


@room.route('/')
@login_required
def index():
    cutoff = arrow.now('Asia/Bangkok').shift(days=-30).datetime
    recent_reservations = current_user.room_reservations \
        .filter(RoomEvent.created_at >= cutoff) \
        .order_by(RoomEvent.created_at.desc())
    return render_template('scheduler/room_main.html', recent_reservations=recent_reservations)


@room.route('/ai-room-search')
@login_required
def ai_room_search():
    return render_template('scheduler/ai_room_search.html')


@room.route('/api/ai-room-search', methods=['POST'])
@login_required
def ai_room_search_api():
    payload = request.get_json(silent=True) or {}
    user_message = _sanitize_room_query_text(payload.get('message'))
    if not user_message:
        return jsonify({'error': 'กรุณาระบุรายละเอียดที่ต้องการค้นหาห้อง'}), 400

    try:
        current_app.logger.info('AI_ROOM_SEARCH_RAW_INPUT %s', json.dumps({
            'raw_input': user_message,
        }, ensure_ascii=False))
        normalization_result = normalize_user_request(user_message)
        current_app.logger.info('AI_ROOM_SEARCH_NORMALIZED %s', json.dumps({
            'current_date': normalization_result.get('current_date'),
            'current_day': normalization_result.get('current_day'),
            'normalized_text': normalization_result.get('normalized_text'),
            'resolved_date': normalization_result.get('resolved_date'),
            'inferred_context': normalization_result.get('inferred_context') or [],
            'uncertain_items': normalization_result.get('uncertain_items') or [],
        }, ensure_ascii=False))

        parsed_criteria = _parse_room_criteria(
            normalization_result['normalized_text'],
            resolved_date=normalization_result.get('resolved_date'),
            raw_text=user_message,
        )
        current_app.logger.info('AI_ROOM_SEARCH_PARSER_OUTPUT %s', json.dumps({
            'purpose': parsed_criteria.get('purpose'),
            'location': parsed_criteria.get('location'),
            'location_explicit': parsed_criteria.get('location_explicit'),
            'floor': parsed_criteria.get('floor'),
            'date': parsed_criteria.get('date'),
            'start_time': parsed_criteria.get('start_time'),
            'end_time': parsed_criteria.get('end_time'),
            'capacity': parsed_criteria.get('capacity'),
        }, ensure_ascii=False))
        rooms, fallback_used = _execute_ai_room_search(parsed_criteria)
    except requests.RequestException as exc:
        return jsonify({'error': f'ไม่สามารถเชื่อมต่อ Typhoon API ได้: {exc}'}), 502
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 503
    except (KeyError, ValueError, TypeError) as exc:
        return jsonify({'error': f'ระบบตีความคำขอไม่สำเร็จ: {exc}'}), 422

    assumptions = _normalize_assumptions(normalization_result.get('inferred_context'))
    assumptions.extend(_normalize_assumptions(parsed_criteria.get('assumptions')))
    if fallback_used:
        assumptions.append('ไม่พบห้องในศาลายาตามเงื่อนไข จึงขยายผลลัพธ์ไปทุกวิทยาเขต')
    parsed_criteria['assumptions'] = _normalize_assumptions(assumptions)

    return jsonify({
        'assistant_message': _summarize_room_request(parsed_criteria, rooms),
        'requirements': {
            'purpose': parsed_criteria.get('purpose'),
            'location': parsed_criteria.get('location'),
            'date': parsed_criteria.get('date'),
            'start_time': parsed_criteria.get('start_time'),
            'end_time': parsed_criteria.get('end_time'),
            'capacity': parsed_criteria.get('capacity'),
            'floor': parsed_criteria.get('floor'),
        },
        'assumptions': parsed_criteria.get('assumptions') or [],
        'uncertain_items': normalization_result.get('uncertain_items') or [],
        'rooms': rooms,
    })


@room.route('/events/<list_type>')
@login_required
def event_list(list_type='timelineDay'):
    return render_template('scheduler/event_list.html', list_type=list_type)


@room.route('/events/new')
@login_required
def new_event():
    return render_template('scheduler/new_event.html')


@room.route('/events/<int:event_id>', methods=['POST', 'GET'])
@login_required
def show_event_detail(event_id=None):
    if event_id:
        event = RoomEvent.query.get(event_id)
        master_id = event.master_id or event.id
        if event.master_id or event.secondary:
            repeat_events = RoomEvent.query.filter(or_(RoomEvent.master_id == master_id, RoomEvent.id == master_id)).order_by(RoomEvent.start)
        else:
            repeat_events = None
        if event:
            return render_template('scheduler/event_detail.html', event=event, repeat_events=repeat_events,
                                   event_start=localtz.localize(event.datetime.lower),
                                   event_end=localtz.localize(event.datetime.upper),
                                   )
    else:
        return 'No event ID specified.'


@room.route('/events/cancel/<int:event_id>')
@login_required
def cancel(event_id=None):
    repeat = request.args.get('repeat', 'false')
    if not event_id:
        return redirect(url_for('room.index'))

    cancelled_datetime = arrow.now('Asia/Bangkok').datetime
    event = RoomEvent.query.get(event_id)
    if not event:
        flash('ไม่พบรายการจองที่ต้องการยกเลิก', 'danger')
        return redirect(url_for('room.index'))

    event.cancelled_at = cancelled_datetime
    event.cancelled_by = current_user.id
    flash('ยกเลิกการจองห้องเรียบร้อยแล้ว', 'success')
    db.session.add(event)
    db.session.commit()

    start = localtz.localize(event.datetime.lower)
    end = localtz.localize(event.datetime.upper)
    event_time = f'{start.strftime("%d/%m/%Y %H:%M")} - {end.strftime("%d/%m/%Y %H:%M")}'
    text = f' เวลา {event_time}'
    msg = f'{event.creator.fullname} ได้ยกเลิกการจอง {event.room.number} สำหรับ {event.title} เวลา {event_time}.'
    if not current_app.debug:
        if event.note:
            for coord in event.room.coordinators:
                try:
                    line_bot_api.push_message(to=coord.line_id, messages=TextSendMessage(text=msg))
                except LineBotApiError:
                    pass
        if event.participants and event.notify_participants:
            participant_emails = [f'{account.email}@mahidol.ac.th' for account in event.participants]
            title = f'แจ้งยกเลิกการนัดหมาย{event.category}'
            message = f'ขอแจ้งยกเลิกคำเชิญเข้าร่วม {event.title}'
            message += text
            message += f' ณ ห้อง {event.room.number} {event.room.location}'
            message += f'\n\nขออภัยในความไม่สะดวก'
            send_mail(participant_emails, title, message)
    else:
        print(msg, event.room.coordinator)
    if repeat == 'true' and event.master_id:
        return redirect(url_for('room.show_event_detail', event_id=event.master_id))
    else:
        return redirect(url_for('room.index'))


@room.route('/events/approve/<int:event_id>')
@login_required
def approve_event(event_id):
    event = RoomEvent.query.get(event_id)
    event.approved = True
    event.approved_by = current_user.id
    event.approved_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(event)
    db.session.commit()
    flash(u'อนุมัติการจองห้องเรียบร้อยแล้ว', 'success')
    return redirect(url_for('room.index'))


@room.route('/events/edit/<int:event_id>', methods=['POST', 'GET'])
@login_required
def edit_detail(event_id):
    new_events = []
    event = RoomEvent.query.get(event_id)
    master_id = event.master_id or event.id
    old_booking = event.booking
    old_start = arrow.get(event.start, 'Asia/Bangkok').datetime
    old_end = arrow.get(event.end, 'Asia/Bangkok').datetime
    old_repeat_end = arrow.get(event.repeat_end, 'Asia/Bangkok').date() if event.repeat_end else None
    repeat_end = arrow.get(event.repeat_end, 'Asia/Bangkok').date() if event.repeat_end else None
    complaints = ComplaintRecord.query.filter(ComplaintRecord.topic.has(ComplaintTopic.code.in_(['room', 'runied'])),
                                              or_(ComplaintRecord.status.has(ComplaintStatus.code != 'completed'),
                                                  ComplaintRecord.status == None),
                                              or_(ComplaintRecord.room_id == event.room_id,
                                                  ComplaintRecord.procurement_location_id == event.room_id)).all()
    form = RoomEventForm(obj=event)
    start = localtz.localize(event.datetime.lower)
    end = localtz.localize(event.datetime.upper)
    if form.validate_on_submit():
        start = arrow.get(form.start.data, 'Asia/Bangkok')
        end = arrow.get(form.end.data, 'Asia/Bangkok')
        event_start = arrow.get(form.start.data, 'Asia/Bangkok').datetime
        event_end = arrow.get(form.end.data, 'Asia/Bangkok').datetime
        overlaps = get_overlaps(event.room.id, event_start, event_end)
        overlaps = [evt for evt in overlaps if evt.id != event_id]
        if overlaps:
            flash(f'ไม่สามารถจองได้เนื่องจากมีการจองในช่วงเวลาเดียวกัน', 'danger')
            return redirect(url_for('room.edit_detail', event_id=event_id))

        form.populate_obj(event)
        repeat_end = arrow.get(form.repeat_end.data, 'Asia/Bangkok').date() if form.repeat_end.data else None
        event.datetime = DateTimeRange(lower=event_start, upper=event_end, bounds='[]')
        event.start = event_start
        event.end = event_end
        event.updated_at = arrow.now('Asia/Bangkok').datetime
        event.updated_by = current_user.id

        if not form.is_repeat_booking.data:
            event.booking = None
            event.repeat_end = None
        else:
            event.booking = form.booking.data
            event.repeat_end = repeat_end

        if request.form.getlist('groups'):
            for group_id in request.form.getlist('groups'):
                group = StaffGroupDetail.query.get(group_id)
                for g in group.group_members:
                    event.participants.append(g.staff)
        db.session.add(event)
        if (form.is_repeat_booking.data and form.booking.data and form.repeat_end.data) and ((form.booking.data != old_booking) or (repeat_end != old_repeat_end) or (event_start != old_start)
            or (event_end != old_end)):
            db.session.commit()
            day = 7 if form.booking.data == 'ทุกสัปดาห์' else 1
            current_start = start.shift(days=day)
            current_end = end.shift(days=day)
            while (current_start.date() <= repeat_end and current_end.date() <= repeat_end):
                if form.booking.data == 'ทุกวัน (ไม่รวมเสาร์-อาทิตย์)':
                    if calendar.weekday(current_start.year, current_start.month, current_start.day) < 5:
                        current_startdatetime = current_start.datetime
                        current_enddatetime = current_end.datetime
                        event_overlaps = get_overlaps(event.room_id, current_startdatetime, current_enddatetime)
                        if not event_overlaps:
                            new_evts = create_event(current_startdatetime, current_enddatetime, repeat_end, master_id,
                                                    event.room_id, form)
                            new_events.append(new_evts)
                else:
                    current_startdatetime = current_start.datetime
                    current_enddatetime = current_end.datetime
                    event_overlaps = get_overlaps(event.room_id, current_startdatetime, current_enddatetime)
                    if not event_overlaps:
                        new_evts = create_event(current_startdatetime, current_enddatetime, repeat_end, master_id,
                                                    event.room_id, form)
                        new_events.append(new_evts)
                current_start = current_start.shift(days=day)
                current_end = current_end.shift(days=day)
        else:
            db.session.commit()

        if event.participants and event.notify_participants:
            participant_emails = [f'{account.email}@mahidol.ac.th' for account in event.participants]
            title = f'แจ้งแก้ไขการนัดหมาย{event.category}'
            message = f'ท่านได้รับเชิญให้เข้าร่วม {event.title}'
            message += f' เวลา {event_start.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - {event_end.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}'
            message += f' ณ ห้อง {event.room.number} {event.room.location}'
            message += f'\n\nขอความอนุเคราะห์เข้าร่วมในวันและเวลาดังกล่าว'
            if not current_app.debug:
                send_mail(
                    participant_emails,
                    title,
                    message,
                    attachments=_build_room_event_attachment(event),
                )
            else:
                print(message)

        msg = (f'{event.creator.fullname} ได้แก้ไขการจองห้อง {event.room} สำหรับ {event.title} '
                   f'เวลา {event_start.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - '
                   f'{event_end.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}.')
        if event.note:
            msg += f'\nมีความต้องการเพิ่มเติมคือ {event.note}'

        if not current_app.debug:
            coordinators = []
            if event.room.coordinator:
                coordinators.append(event.room.coordinator)
            coordinators.extend(event.room.coordinators)
            sent_ids = set()
            for coord in coordinators:
                if coord and coord.line_id and coord.id not in sent_ids:
                    try:
                        line_bot_api.push_message(to=coord.line_id, messages=TextSendMessage(text=msg))
                        sent_ids.add(coord.id)
                    except LineBotApiError:
                        pass
        else:
            print(msg, event.room.coordinator)

        if new_events and new_events[0].participants and new_events[0].notify_participants:
            new_event_times = ', '.join(
                f"{arrow.get(new_event.start, 'Asia/Bangkok').datetime.astimezone(localtz).strftime('%d/%m/%Y %H:%M')} - "
                f"{arrow.get(new_event.end, 'Asia/Bangkok').datetime.astimezone(localtz).strftime('%d/%m/%Y %H:%M')}"
                for new_event in new_events
            )
            participant_emails = [f'{account.email}@mahidol.ac.th' for account in new_events[0].participants]
            msg = (f'{new_events[0].creator.fullname} ได้จองห้อง {new_events[0].room.number} สำหรับ {new_events[0].title} '
                   f'เวลา {new_event_times}.'
                   f'มีความต้องการเพิ่มเติมคือ {new_events[0].note}'
                   )
            title = f'แจ้งนัดหมาย{new_events[0].category}'
            message = f'ท่านได้รับเชิญให้เข้าร่วม {new_events[0].title}'
            message += f' เวลา {new_event_times}'
            message += f' ณ ห้อง {new_events[0].room.number} {new_events[0].room.location}'
            message += f'\n\nขอความอนุเคราะห์เข้าร่วมในวันและเวลาดังกล่าว'
            if not current_app.debug:
                if new_events[0].note:
                    for coord in new_events[0].room.coordinators:
                            try:
                                line_bot_api.push_message(to=coord.line_id, messages=TextSendMessage(text=msg))
                            except LineBotApiError:
                                pass
                send_mail(participant_emails, title, message, attachments=_build_room_event_attachment(new_events[0]))
            else:
                print(msg, [coord.line_id for coord in new_events[0].room.coordinators], new_events[0].note)
                print(message, participant_emails)


        flash(u'อัพเดตรายการเรียบร้อย', 'success')
        return redirect(url_for('room.index'))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')
    return render_template('scheduler/reserve_form.html', event=event, form=form, room=event.room,
                           start=start, end=end, complaints=complaints, repeat_end=repeat_end)


@room.route('/list', methods=['POST', 'GET'])
@login_required
def room_list():
    if request.method == 'GET':
        rooms = RoomResource.query.all()
    else:
        room_number = request.form.get('room_number', None)
        users = request.form.get('users', 0)
        if room_number:
            rooms = RoomResource.query.filter(RoomResource.number.like('%{}%'.format(room_number)))
        else:
            rooms = []
        if request.headers.get('HX-Request') == 'true':
            if rooms:
                return render_template('scheduler/partials/room_list.html', rooms=rooms)
            else:
                return ''

    return render_template('scheduler/room_list.html', rooms=rooms)


@room.route('/reserve/<room_id>', methods=['GET', 'POST'])
@login_required
def room_reserve(room_id):
    form = RoomEventForm()
    start = None
    end = None
    if request.method == 'GET':
        _prefill_room_reserve_form(form)
        start = form.start.data
        end = form.end.data
    room = RoomResource.query.get(room_id)
    complaints = ComplaintRecord.query.filter(ComplaintRecord.topic.has(ComplaintTopic.code.in_(['room', 'runied'])),
                                              or_(ComplaintRecord.status.has(ComplaintStatus.code!='completed'),
                                                  ComplaintRecord.status==None),
                                              or_(ComplaintRecord.room_id==room_id, ComplaintRecord.procurement_location_id==room_id)).all()
    if form.validate_on_submit():
        new_event = RoomEvent()
        if form.start.data:
            start = arrow.get(form.start.data, 'Asia/Bangkok')
            startdatetime = arrow.get(form.start.data, 'Asia/Bangkok').datetime
        else:
            start = None
            startdatetime = None

        if form.end.data:
            end = arrow.get(form.end.data, 'Asia/Bangkok')
            enddatetime = arrow.get(form.end.data, 'Asia/Bangkok').datetime
        else:
            end = None
            enddatetime = None

        if room_id and startdatetime and enddatetime:
            if get_overlaps(room_id, startdatetime, enddatetime):
                flash(f'ไม่สามารถจองได้เนื่องจากมีการจองในช่วงเวลาเดียวกัน', 'danger')
                return render_template('scheduler/reserve_form.html', room=room, form=form, start=start, end=end)

            form.populate_obj(new_event)
            repeat_end = arrow.get(form.repeat_end.data, 'Asia/Bangkok').date() if form.repeat_end.data else None
            new_event.datetime = DateTimeRange(lower=startdatetime, upper=enddatetime, bounds='[]')
            new_event.start = startdatetime
            new_event.end = enddatetime
            new_event.created_at = arrow.now('Asia/Bangkok').datetime
            new_event.creator = current_user
            new_event.room_id = room.id

            if not form.is_repeat_booking.data:
                new_event.booking = None
                new_event.repeat_end = None
            else:
                new_event.booking = form.booking.data
                new_event.repeat_end = repeat_end

            if request.form.getlist('groups'):
                for group_id in request.form.getlist('groups'):
                    group = StaffGroupDetail.query.get(group_id)
                    for g in group.group_members:
                        new_event.participants.append(g.staff)
            db.session.add(new_event)

            if form.is_repeat_booking.data and form.booking.data and form.repeat_end.data:
                db.session.commit()
                day = 7 if form.booking.data == 'ทุกสัปดาห์' else 1
                current_start = start.shift(days=day)
                current_end = end.shift(days=day)
                while (current_start.date() <= repeat_end and current_end.date() <= repeat_end):
                    if form.booking.data == 'ทุกวัน (ไม่รวมเสาร์-อาทิตย์)':
                        if calendar.weekday(current_start.year, current_start.month, current_start.day) < 5:
                            current_startdatetime = current_start.datetime
                            current_enddatetime = current_end.datetime
                            event_overlaps = get_overlaps(room_id, current_startdatetime, current_enddatetime)
                            if not event_overlaps:
                                create_event(current_startdatetime, current_enddatetime, repeat_end, new_event.id,
                                             room_id, form)
                    else:
                        current_startdatetime = current_start.datetime
                        current_enddatetime = current_end.datetime
                        event_overlaps = get_overlaps(room_id, current_startdatetime, current_enddatetime)
                        if not event_overlaps:
                            create_event(current_startdatetime, current_enddatetime, repeat_end, new_event.id, room_id,
                                         form)
                    current_start = current_start.shift(days=day)
                    current_end = current_end.shift(days=day)
            else:
                db.session.commit()

            if new_event.secondary:
                event_times = ', '.join(
                    f"{arrow.get(other_event.start, 'Asia/Bangkok').datetime.astimezone(localtz).strftime('%d/%m/%Y %H:%M')} - "
                    f"{arrow.get(other_event.end, 'Asia/Bangkok').datetime.astimezone(localtz).strftime('%d/%m/%Y %H:%M')}"
                    for other_event in new_event.secondary
                    )
            else:
                event_times = None

            if new_event.participants and new_event.notify_participants:
                participant_emails = [f'{account.email}@mahidol.ac.th' for account in new_event.participants]
                title = f'แจ้งนัดหมาย{new_event.category}'
                message = f'ท่านได้รับเชิญให้เข้าร่วม {new_event.title}'
                if event_times:
                    message += f' เวลา {startdatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - {enddatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}, {event_times}'
                else:
                    message += f' เวลา {startdatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - {enddatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}'
                message += f' ณ ห้อง {room.number} {room.location}'
                message += f'\n\nขอความอนุเคราะห์เข้าร่วมในวันและเวลาดังกล่าว'
                if not current_app.debug:
                    send_mail(
                        participant_emails,
                        title,
                        message,
                        attachments=_build_room_event_attachment(new_event),
                    )
                else:
                    print(message)
            if event_times:
                msg = (f'{new_event.creator.fullname} ได้จองห้อง {room} สำหรับ {new_event.title} '
                       f'เวลา {startdatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - {enddatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}, {event_times}.'
                       f'มีความต้องการเพิ่มเติมคือ {new_event.note}'
                       )
            else:
                msg = (f'{new_event.creator.fullname} ได้จองห้อง {room} สำหรับ {new_event.title} '
                       f'เวลา {startdatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")} - {enddatetime.astimezone(localtz).strftime("%d/%m/%Y %H:%M")}.'
                       f'มีความต้องการเพิ่มเติมคือ {new_event.note}'
                       )
            if not current_app.debug:
                if new_event.note:
                    for coord in room.coordinators:
                        try:
                            line_bot_api.push_message(to=coord.line_id, messages=TextSendMessage(text=msg))
                        except LineBotApiError:
                            pass
            else:
                print(msg, room.coordinators, new_event.note)
            flash(u'บันทึกการจองห้องเรียบร้อยแล้ว', 'success')
            return redirect(url_for('room.show_event_detail', event_id=new_event.id))
    else:
        for field, error in form.errors.items():
            flash(f'{field}: {error}', 'danger')

    if room:
        return render_template('scheduler/reserve_form.html',
                               room=room, complaints=complaints, form=form, start=start, end=end)
    else:
        flash('Room not found.', 'danger')


@room.route('/api/admin/events')
@login_required
def get_room_event_list():
    room_query = request.args.get('query', 'all')
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = RoomEvent.query.order_by(RoomEvent.start.desc())
    # search filter
    search = request.args.get('search[value]')
    room = RoomResource.query.filter_by(number=search).first()
    if room_query == 'some':
        query = query.join(RoomResource).join(room_coordinator_assoc).join(StaffAccount).filter_by(email=current_user.email)
    if search:
        query = query.filter(db.or_(
            RoomEvent.room.has(RoomEvent.room == room),
            RoomEvent.title.like(f'%{search}%')
        ))
    total_filtered = query.count()
    query = query.offset(start).limit(length)

    return {
        'data': [d.to_dict() for d in query],
        'recordsFiltered': total_filtered,
        'recordsTotal': RoomEvent.query.count(),
        'draw': request.args.get('draw', type=int),
    }


@room.route('/coordinators')
@login_required
def room_event_list():
    today = datetime.today()
    enddate = today + timedelta(days=7)
    _daterange = DateTimeRange(lower=today, upper=enddate, bounds='[]')
    query = RoomEvent.query.filter(RoomEvent.datetime.op('&&')(_daterange)).filter_by(cancelled_at=None)
    for event in query:
        if event.note:
            flash(f'ห้อง{event.room} เวลา{event.start.astimezone(pytz.timezone("Asia/Bangkok")).strftime("%d/%m %H:%M")} ต้องการ{event.note}', 'warning')
    return render_template('scheduler/room_event_list.html')


@room.route('/coordinators/remove/<int:room_id>', methods=['DELETE'])
@login_required
def remove_coordinated_room(room_id):
    room = RoomResource.query.get(room_id)
    current_user.rooms.remove(room)
    db.session.add(current_user)
    db.session.commit()
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


def get_overlaps(room_id, start, end, session_id=None, session_attr=None, no_cancellation=True):
    query = RoomEvent.query.filter_by(room_id=room_id)
    events = set()
    for evt in query.filter(RoomEvent.datetime.op('&&')(DateTimeRange(lower=start, upper=end, bounds='[]'))):
        events.add(evt)
    if no_cancellation:
        return set([e for e in events if e.cancelled_at is None])
    return events


@room.route('/api/room-availability')
@login_required
def check_room_availability():
    session_attr = request.args.get('session_attr')
    session_id = request.args.get('session_id', type=int)
    room_id = request.args.get('room', type=int)
    event_id = request.args.get('event_id', type=int)
    start = request.args.get('start')
    end = request.args.get('end')
    start = dateutil.parser.isoparse(start).astimezone(pytz.timezone('Asia/Bangkok'))
    end = dateutil.parser.isoparse(end).astimezone(pytz.timezone('Asia/Bangkok'))
    if start < end:
        overlaps = get_overlaps(room_id, start, end, session_id, session_attr)
        overlaps = [evt for evt in overlaps if evt.id != event_id]
    else:
        overlaps = None
    if overlaps:
        temp = '<span class="tag is-warning">{}-{} {}</span>'
        template = '<span class="tag is-danger">ห้องไม่ว่าง</span>'
        template += '<span id="overlaps" hx-swap-oob="true" class="tags">'
        template += ''.join([temp.format(localtz.localize(evt.datetime.lower).strftime('%H:%M'),
                                         localtz.localize(evt.datetime.upper).strftime('%H:%M'),
                                         evt.title) for evt in overlaps])
        template += '</span>'
    else:
        template = '<span class="tag is-success">ห้องว่าง</span>'
        template += '<span id="overlaps" hx-swap-oob="true" class="tags"></span>'
    resp = make_response(template)
    return resp


@room.route('/api/room-availability/clear')
@login_required
def clear_status():
    template = '<span id="overlaps" hx-swap-oob="true" class="tags"></span>'
    resp = make_response(template)
    return resp


@room.route('/<int:room_id>/scan-qrcode/view', methods=['GET', 'POST'])
def view_feature_after_scan_qrcode_room(room_id):
    room = RoomResource.query.get(room_id)
    return render_template('scheduler/view_feature_after_scan_qrcode_room.html', room=room)
