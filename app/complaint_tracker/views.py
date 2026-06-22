# -*- coding:utf-8 -*-
from html import escape
import json
import uuid
from collections import defaultdict
from datetime import datetime, date, timedelta
from io import BytesIO
import arrow
import gviz_api
import requests
from bahttext import bahttext
from flask import render_template, flash, redirect, url_for, request, make_response, jsonify, current_app, send_file, abort
from flask_login import current_user
from flask_login import login_required
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import joinedload, selectinload
from app.auth.views import line_bot_api
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive
from app.complaint_tracker import complaint_tracker
from app.complaint_tracker.forms import *
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, PageBreak, TableStyle, Table, Spacer, KeepTogether, \
    HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.complaint_tracker.models import *
from app.main import mail
from ..main import csrf
from flask_mail import Message
from ..models import Org
from ..procurement.models import ProcurementDetail
from ..roles import admin_permission
from ..staff.models import StaffPersonalInfo, StaffCostCenterAuthority

sarabun_font = TTFont('Sarabun', 'app/static/fonts/THSarabunNew.ttf')
pdfmetrics.registerFont(sarabun_font)
pdfmetrics.registerFont(TTFont('SarabunBold', 'app/static/fonts/THSarabunNewBold.ttf'))
pdfmetrics.registerFont(TTFont('DejaVuSans', 'app/static/fonts/DejaVuSans.ttf'))
style_sheet = getSampleStyleSheet()
style_sheet.add(ParagraphStyle(name='ThaiStyle', fontName='Sarabun'))
style_sheet.add(ParagraphStyle(name='ThaiStyleBold', fontName='SarabunBold'))
style_sheet.add(ParagraphStyle(name='ThaiStyleNumber', fontName='Sarabun', alignment=TA_RIGHT))
style_sheet.add(ParagraphStyle(name='ThaiStyleCenter', fontName='Sarabun', alignment=TA_CENTER))

localtz = timezone('Asia/Bangkok')
TYPHOON_API_URL = 'https://api.opentyphoon.ai/v1/chat/completions'
TYPHOON_MODEL = os.getenv('SCB_TYPHOON_MODEL', 'typhoon-v2.5-30b-a3b-instruct')

# FOLDER_ID = '1832el0EAqQ6NVz2wB7Ade6wRe-PsHQsu'
#
# json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        page = self._pageNumber
        self.setFont("SarabunBold", 12)
        self.drawRightString(200*mm, 15*mm, f"{page}/{page_count}")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_url(file_url):
    url = s3.generate_presigned_url('get_object',
                                    Params={'Bucket': S3_BUCKET_NAME, 'Key': file_url},
                                    ExpiresIn=3600)
    return url


def get_organization(org, form):
    if org.parent and org.parent.parent:
        form.organization.data = f'{org.name} {org.parent} {org.parent.parent}'
    elif org.parent and not org.parent.parent:
        form.organization.data = f'{org.name} {org.parent}'
    else:
        form.organization.data = org.name


def get_fiscal_date(date):
    if date.month >= 10:
        start_fiscal_date = datetime(date.year, 10, 1)
        end_fiscal_date = datetime(date.year + 1, 9, 30, 23, 59, 59, 0)
    else:
        start_fiscal_date = datetime(date.year - 1, 10, 1)
        end_fiscal_date = datetime(date.year, 9, 30, 23, 59, 59, 0)
    return start_fiscal_date, end_fiscal_date


def _apply_topic_code_filter(query, code):
    if code and code != 'null':
        return query.join(ComplaintTopic, ComplaintRecord.topic_id == ComplaintTopic.id).filter(ComplaintTopic.code == code)
    return query


def _build_calendar_chart_json(date_column, status_code=None, include_unset_status=False, code=None):
    description = {'date': ('date', 'Day'), 'heads': ('number', 'heads')}
    start_fiscal_date, end_fiscal_date = get_fiscal_date(datetime.today())

    query = db.session.query(
        func.date(date_column).label('record_date'),
        func.count(ComplaintRecord.id).label('heads')
    ).filter(date_column.between(start_fiscal_date, end_fiscal_date))

    query = _apply_topic_code_filter(query, code)

    if include_unset_status:
        query = query.filter(ComplaintRecord.status_id.is_(None))
    elif status_code:
        query = query.join(ComplaintStatus, ComplaintRecord.status_id == ComplaintStatus.id).filter(
            ComplaintStatus.code == status_code
        )

    rows = query.group_by('record_date').order_by('record_date').all()
    count_data = [{'date': row.record_date, 'heads': row.heads} for row in rows]

    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon(columns_order=('date', 'heads'))


def send_mail(recp, title, message, html=None):
    message = Message(subject=title, body=message, recipients=recp, html=html)
    mail.send(message)


def _normalize_internal_email(email_value):
    if not email_value:
        return None
    email_value = email_value.strip()
    if not email_value:
        return None
    if '@' not in email_value:
        email_value = f'{email_value}@mahidol.ac.th'
    return email_value


def _request_flag(name, default=False):
    raw_value = request.values.get(name)
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _mask_line_id(line_id):
    if not line_id:
        return None
    if len(line_id) <= 6:
        return '***'
    return f'{line_id[:3]}***{line_id[-3:]}'


def _is_valid_summary_scheduler_request():
    configured_token = os.environ.get('JOB_TOKEN')
    request_token = request.values.get('job_token')
    return bool(configured_token and request_token and request_token == configured_token)


def _get_high_level_admin_recipients():
    recipients = {}
    for admin in ComplaintAdmin.query.filter_by(is_supervisor=True).all():
        email = _normalize_internal_email(admin.admin.email if admin.admin else None)
        if not email:
            continue
        if email not in recipients:
            recipients[email] = {
                'email': email,
                'staff_name': admin.admin.fullname if admin.admin else email,
                'topic_ids': set(),
                'topic_names': set(),
            }
        if admin.topic_id:
            recipients[email]['topic_ids'].add(admin.topic_id)
        if admin.topic and admin.topic.topic:
            recipients[email]['topic_names'].add(admin.topic.topic)

    normalized = []
    for recipient in recipients.values():
        normalized.append({
            'email': recipient['email'],
            'staff_name': recipient['staff_name'],
            'topic_ids': sorted(recipient['topic_ids']),
            'topic_names': sorted(recipient['topic_names']),
        })
    return sorted(normalized, key=lambda item: item['email'])


def _group_high_level_admin_recipients_by_topic_scope(recipients):
    grouped = {}
    for recipient in recipients:
        topic_ids = tuple(recipient.get('topic_ids') or [])
        if topic_ids not in grouped:
            grouped[topic_ids] = {
                'email': recipient['email'],
                'emails': [],
                'staff_name': '',
                'staff_names': [],
                'topic_ids': list(topic_ids),
                'topic_names': set(),
            }
        grouped_recipient = grouped[topic_ids]
        grouped_recipient['emails'].append(recipient['email'])
        grouped_recipient['staff_names'].append(recipient['staff_name'])
        grouped_recipient['topic_names'].update(recipient.get('topic_names') or [])

    normalized = []
    for grouped_recipient in grouped.values():
        emails = sorted(set(grouped_recipient['emails']))
        staff_names = sorted(set(grouped_recipient['staff_names']))
        normalized.append({
            'email': emails[0],
            'emails': emails,
            'staff_name': ', '.join(staff_names),
            'staff_names': staff_names,
            'topic_ids': grouped_recipient['topic_ids'],
            'topic_names': sorted(grouped_recipient['topic_names']),
        })
    return sorted(normalized, key=lambda item: (item['topic_ids'], item['email']))


def _get_low_level_line_recipients():
    recipients = {}
    admins = ComplaintAdmin.query.filter_by(is_supervisor=False).join(ComplaintAdmin.admin).all()
    for admin in admins:
        line_id = admin.admin.line_id if admin.admin else None
        if not line_id:
            continue
        if line_id not in recipients:
            recipients[line_id] = {
                'line_id': line_id,
                'staff_name': admin.admin.fullname if admin.admin else line_id,
                'topic_ids': set(),
                'topic_names': set(),
            }
        if admin.topic_id:
            recipients[line_id]['topic_ids'].add(admin.topic_id)
        if admin.topic and admin.topic.topic:
            recipients[line_id]['topic_names'].add(admin.topic.topic)

    normalized = []
    for recipient in recipients.values():
        normalized.append({
            'line_id': recipient['line_id'],
            'staff_name': recipient['staff_name'],
            'topic_ids': sorted(recipient['topic_ids']),
            'topic_names': sorted(recipient['topic_names']),
        })
    return sorted(normalized, key=lambda item: item['staff_name'])


def _get_low_level_line_recipient_stats():
    admins = ComplaintAdmin.query.filter_by(is_supervisor=False).join(ComplaintAdmin.admin).all()
    total_admin_rows = len(admins)
    admins_with_line = 0
    unique_line_ids = set()
    missing_line = []

    for admin in admins:
        line_id = admin.admin.line_id if admin.admin else None
        if line_id:
            admins_with_line += 1
            unique_line_ids.add(line_id)
        else:
            missing_line.append(admin.admin.fullname if admin.admin else 'Unknown')

    return {
        'total_admin_rows': total_admin_rows,
        'admins_with_line': admins_with_line,
        'unique_recipients': len(unique_line_ids),
        'missing_line_names': missing_line,
    }


def _build_today_no_status_records_snapshot(topic_ids=None):
    now = arrow.now('Asia/Bangkok')
    start_of_day = now.floor('day').datetime
    end_of_day = now.ceil('day').datetime

    if topic_ids is not None and not topic_ids:
        return {
            'date_label': now.strftime('%d/%m/%Y'),
            'total_records': 0,
            'records': [],
            'topic_counts': {},
        }

    records_query = ComplaintRecord.query.filter(
        ComplaintRecord.created_at >= start_of_day,
        ComplaintRecord.created_at < end_of_day,
        ComplaintRecord.status_id.is_(None)
    )
    if topic_ids:
        records_query = records_query.filter(ComplaintRecord.topic_id.in_(topic_ids))

    records = records_query.order_by(ComplaintRecord.created_at.asc()).yield_per(200)
    items = []
    topic_counts = defaultdict(int)
    total_records = 0
    preview_limit = 200
    for record in records:
        total_records += 1
        topic_label = record.topic.topic if record.topic else 'ไม่ระบุหัวข้อ'
        topic_counts[topic_label] += 1
        if len(items) < preview_limit:
            items.append({
                'id': record.id,
                'topic': topic_label,
                'created_at': record.created_at.astimezone(localtz).strftime('%H:%M') if record.created_at else '-',
            })

    return {
        'date_label': now.strftime('%d/%m/%Y'),
        'total_records': total_records,
        'records': items,
        'topic_counts': dict(sorted(topic_counts.items(), key=lambda item: (-item[1], item[0]))),
    }


def _build_low_level_line_reminder_message(recipient, snapshot):
    if not snapshot['records']:
        return None

    topic_summary = ', '.join(
        f"{topic} {count} เรื่อง" for topic, count in list(snapshot['topic_counts'].items())[:3]
    ) or 'ไม่มีรายละเอียดหัวข้อ'
    record_ids_preview_limit = 50
    preview_ids = [str(item['id']) for item in snapshot['records'][:record_ids_preview_limit]]
    record_ids = ', '.join(preview_ids)
    if snapshot['total_records'] > record_ids_preview_limit:
        record_ids += f" ... และอีก {snapshot['total_records'] - record_ids_preview_limit} รายการ"

    return (
        f"แจ้งเตือนรายการแจ้งปัญหา/ซ่อมบำรุงใหม่ยังไม่ได้ตรวจสอบ วันที่ {snapshot['date_label']}\n"
        f"มีทั้งหมด {snapshot['total_records']} เรื่อง ในส่วนงานที่ท่านรับผิดชอบ\n"
        f"หัวข้อหลัก: {topic_summary}\n"
        f"รหัสรายการ: {record_ids}"
    )


def _build_low_level_line_reminder_package(recipient, snapshot_cache=None):
    snapshot_cache = snapshot_cache if snapshot_cache is not None else {}
    topic_ids = recipient.get('topic_ids')
    if not topic_ids:
        snapshot = {
            'date_label': arrow.now('Asia/Bangkok').strftime('%d/%m/%Y'),
            'total_records': 0,
            'records': [],
            'topic_counts': {},
        }
    else:
        cache_key = tuple(topic_ids)
        snapshot = snapshot_cache.get(cache_key)
        if snapshot is None:
            snapshot = _build_today_no_status_records_snapshot(topic_ids=topic_ids)
            snapshot_cache[cache_key] = snapshot
    message = _build_low_level_line_reminder_message(recipient, snapshot)
    return {
        'recipient': recipient,
        'snapshot': snapshot,
        'message': message,
    }


def _render_line_reminder_dry_run_html(
        packages,
        matched_packages=None,
        should_send=False,
        stats=None,
        global_snapshot=None):
    matched_packages = matched_packages or []
    stats = stats or {
        'unique_recipients': len(packages),
        'total_admin_rows': len(packages),
        'admins_with_line': len(packages),
        'missing_line_names': [],
    }
    global_snapshot = global_snapshot or {
        'total_records': 0,
        'date_label': arrow.now('Asia/Bangkok').strftime('%d/%m/%Y'),
    }
    cards = []
    for package in packages:
        recipient = package['recipient']
        snapshot = package['snapshot']
        records_html = ''.join(
            f"<li>#{item['id']} {escape(item['topic'])} เวลา {item['created_at']}</li>"
            for item in snapshot['records'][:10]
        ) or '<li>ไม่มีรายการ</li>'
        cards.append(f"""
        <div class="summary-card">
            <h3>{escape(recipient['staff_name'])}</h3>
            <div class="summary-metrics">
                <span><strong>{snapshot['total_records']}</strong> เรื่อง</span>
                <span>LINE ID: {escape(recipient['line_id'])}</span>
            </div>
            <p><strong>ข้อความที่จะส่ง</strong></p>
            <pre>{escape(package['message'] or 'ไม่มีข้อความ')}</pre>
            <p><strong>รายการตัวอย่าง</strong></p>
            <ul>{records_html}</ul>
        </div>
        """)

    html = f"""
    <!doctype html>
    <html lang="th">
    <head>
      <meta charset="utf-8">
      <title>Dry Run: Low-Level Line Reminder</title>
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#f8fafc; color:#0f172a; margin:0; }}
        .container {{ max-width: 1080px; margin: 0 auto; padding: 24px; }}
        .summary-card {{ background: #ffffff; border: 1px solid #cbd5e1; border-radius: 14px; padding: 14px 16px; margin-bottom: 18px; }}
        .summary-card h3 {{ margin: 0 0 10px; font-size: 16px; }}
        .summary-metrics {{ display: flex; flex-wrap: wrap; gap: 10px 18px; margin-bottom: 10px; }}
        .summary-metrics span {{ color: #475569; font-size: 14px; }}
        .summary-metrics strong {{ color: #0f172a; font-size: 20px; margin-right: 4px; }}
        pre {{ white-space: pre-wrap; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; }}
      </style>
    </head>
    <body>
      <div class="container">
        <h1>Dry Run: Low-Level Line Reminder</h1>
        <p>Recipients with line_id: {stats['unique_recipients']} | matched recipients: {len(matched_packages)} | send={str(should_send).lower()}</p>
        <div class="summary-card">
            <h3>Diagnostic Summary</h3>
            <div class="summary-metrics">
                <span><strong>{stats['total_admin_rows']}</strong> admin rows</span>
                <span><strong>{stats['admins_with_line']}</strong> admin rows with line_id</span>
                <span><strong>{global_snapshot['total_records']}</strong> requests today with no status</span>
                <span>Date: {global_snapshot['date_label']}</span>
            </div>
            <p><strong>Admins missing line_id</strong></p>
            <pre>{escape(', '.join(stats['missing_line_names']) if stats['missing_line_names'] else 'None')}</pre>
        </div>
        {''.join(cards) if cards else '<p>ไม่พบผู้รับหรือไม่พบเรื่องที่เข้าเงื่อนไข</p>'}
      </div>
    </body>
    </html>
    """
    response = make_response(html)
    response.mimetype = 'text/html'
    return response


def _build_unfinished_records_snapshot(topic_ids=None):
    now = arrow.now('Asia/Bangkok').datetime
    due_soon_limit = now + timedelta(days=3)
    completed_since = now - timedelta(days=7)
    records_query = ComplaintRecord.query.filter(
        ComplaintRecord.closed_at.is_(None),
        or_(ComplaintRecord.status.has(ComplaintStatus.code != 'completed'),
            ComplaintRecord.status == None)
    )
    completed_query = ComplaintRecord.query.filter(
        ComplaintRecord.closed_at.isnot(None),
        ComplaintRecord.closed_at >= completed_since,
        ComplaintRecord.status.has(ComplaintStatus.code == 'completed')
    )
    if topic_ids:
        records_query = records_query.filter(ComplaintRecord.topic_id.in_(topic_ids))
        completed_query = completed_query.filter(ComplaintRecord.topic_id.in_(topic_ids))

    status_counts = defaultdict(int)
    category_counts = defaultdict(int)
    topic_counts = defaultdict(int)
    org_counts = defaultdict(int)
    priority_counts = defaultdict(int)
    tag_counts = defaultdict(int)
    completed_category_counts = defaultdict(int)
    completed_topic_counts = defaultdict(int)
    completed_org_counts = defaultdict(int)
    completed_tag_counts = defaultdict(int)

    overdue_count = 0
    due_today_count = 0
    due_soon_count = 0
    no_deadline_count = 0
    no_owner_count = 0
    no_status_count = 0
    aged_7_plus = 0
    aged_14_plus = 0
    aged_30_plus = 0
    oldest_open_days = 0
    total_open_records = 0
    completed_last_7_days = 0

    for record in records_query.yield_per(200):
        total_open_records += 1
        status_label = record.status.status if record.status else 'ยังไม่ระบุสถานะ'
        status_counts[status_label] += 1
        category_counts[record.topic.category.category if record.topic and record.topic.category else 'ไม่ระบุหมวด'] += 1
        topic_counts[record.topic.topic if record.topic else 'ไม่ระบุหัวข้อ'] += 1
        org_counts[record.organization or 'ไม่ระบุหน่วยงาน'] += 1
        priority_counts[record.priority.priority_text if record.priority else 'ไม่ระบุความเร่งด่วน'] += 1
        for tag in record.tags or []:
            if tag and tag.tag:
                tag_counts[tag.tag] += 1

        created_at = arrow.get(record.created_at).to('Asia/Bangkok').datetime
        age_days = max((now.date() - created_at.date()).days, 0)
        oldest_open_days = max(oldest_open_days, age_days)
        if age_days >= 7:
            aged_7_plus += 1
        if age_days >= 14:
            aged_14_plus += 1
        if age_days >= 30:
            aged_30_plus += 1

        if not record.status:
            no_status_count += 1

        if not any([record.assignees, record.investigators, record.coordinators, record.handlers]):
            no_owner_count += 1

        if not record.deadline:
            no_deadline_count += 1
            continue

        deadline = arrow.get(record.deadline).to('Asia/Bangkok').datetime
        if deadline < now:
            overdue_count += 1
        elif deadline.date() == now.date():
            due_today_count += 1
        elif deadline <= due_soon_limit:
            due_soon_count += 1

    for record in completed_query.yield_per(200):
        completed_last_7_days += 1
        completed_category_counts[
            record.topic.category.category if record.topic and record.topic.category else 'ไม่ระบุหมวด'
        ] += 1
        completed_topic_counts[record.topic.topic if record.topic else 'ไม่ระบุหัวข้อ'] += 1
        completed_org_counts[record.organization or 'ไม่ระบุหน่วยงาน'] += 1
        for tag in record.tags or []:
            if tag and tag.tag:
                completed_tag_counts[tag.tag] += 1

    def _top_items(source, limit=5):
        return [
            {'label': key, 'count': value}
            for key, value in sorted(source.items(), key=lambda item: (-item[1], item[0]))[:limit]
        ]

    return {
        'generated_at': now.strftime('%Y-%m-%d %H:%M'),
        'scope_topic_ids': topic_ids or [],
        'total_open_records': total_open_records,
        'completed_last_7_days': completed_last_7_days,
        'status_counts': dict(sorted(status_counts.items(), key=lambda item: (-item[1], item[0]))),
        'category_counts': dict(sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))),
        'topic_counts': dict(sorted(topic_counts.items(), key=lambda item: (-item[1], item[0]))),
        'organization_counts': dict(sorted(org_counts.items(), key=lambda item: (-item[1], item[0]))),
        'priority_counts': dict(sorted(priority_counts.items(), key=lambda item: (-item[1], item[0]))),
        'tag_counts': dict(sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))),
        'overdue_count': overdue_count,
        'due_today_count': due_today_count,
        'due_soon_count': due_soon_count,
        'no_deadline_count': no_deadline_count,
        'no_owner_count': no_owner_count,
        'no_status_count': no_status_count,
        'aged_7_plus': aged_7_plus,
        'aged_14_plus': aged_14_plus,
        'aged_30_plus': aged_30_plus,
        'oldest_open_days': oldest_open_days,
        'top_categories': _top_items(category_counts),
        'top_topics': _top_items(topic_counts),
        'top_organizations': _top_items(org_counts),
        'top_tags': _top_items(tag_counts),
        'completed_top_categories': _top_items(completed_category_counts),
        'completed_top_topics': _top_items(completed_topic_counts),
        'completed_top_organizations': _top_items(completed_org_counts),
        'completed_top_tags': _top_items(completed_tag_counts),
    }


def _build_typhoon_complaint_summary_prompt(snapshot):
    return [
        {
            'role': 'system',
            'content': (
                'You are writing a short executive email summary in Thai for high-level administrators. '
                'Summarize the overall picture of unfinished complaint/request handling and recently finished work. '
                'Do not include complaint IDs, names, phone numbers, emails, raw descriptions, or case-by-case details. '
                'Focus on risk, backlog shape, timing pressure, recent closure momentum, related tags that hint at specific issues, and what leadership should monitor. '
                'Write plain Thai suitable for an internal email. '
                'Keep it concise. '
                'Use this structure only: '
                '1) ภาพรวม 1 short paragraph, '
                '2) ประเด็นที่ควรติดตาม 3 bullet points, '
                '3) สิ่งที่ควรเฝ้าระวังวันนี้ 1 short paragraph. '
                'Mention the number of requests completed within the last 7 days when relevant. '
                'When tags show recurring patterns, mention the most relevant tags as hints for investigation. '
                'If the backlog is small, say so plainly without overstating urgency.'
            )
        },
        {
            'role': 'user',
            'content': (
                'สรุปข้อมูลต่อไปนี้เป็นภาษาไทยสำหรับผู้บริหารระดับสูง โดยไม่ลงรายละเอียดรายกรณี:\n'
                f'{json.dumps(snapshot, ensure_ascii=False, indent=2)}'
            )
        }
    ]


def _call_typhoon_complaint_summary(snapshot):
    api_key = os.environ.get('SCB_TYPHOON_API_KEY')
    if not api_key:
        raise RuntimeError('SCB_TYPHOON_API_KEY is not configured.')

    response = requests.post(
        TYPHOON_API_URL,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': TYPHOON_MODEL,
            'temperature': 0.2,
            'max_tokens': 900,
            'messages': _build_typhoon_complaint_summary_prompt(snapshot),
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload['choices'][0]['message']['content']
    if not content or not content.strip():
        raise ValueError('Empty Typhoon summary response.')
    return content.strip()


def _build_fallback_complaint_summary(snapshot):
    top_categories = ', '.join(
        f"{item['label']} {item['count']} เรื่อง" for item in snapshot['top_categories'][:3]
    ) or 'ไม่มีประเด็นค้าง'
    top_orgs = ', '.join(
        f"{item['label']} {item['count']} เรื่อง" for item in snapshot['top_organizations'][:3]
    ) or 'ไม่มีข้อมูลหน่วยงาน'
    top_tags = ', '.join(
        f"{item['label']} {item['count']} เรื่อง" for item in snapshot['top_tags'][:5]
    ) or 'ไม่มีแท็กเด่น'
    completed_categories = ', '.join(
        f"{item['label']} {item['count']} เรื่อง" for item in snapshot['completed_top_categories'][:3]
    ) or 'ไม่มีเรื่องที่ปิดแล้วในช่วง 7 วันที่ผ่านมา'
    completed_tags = ', '.join(
        f"{item['label']} {item['count']} เรื่อง" for item in snapshot['completed_top_tags'][:5]
    ) or 'ไม่มีแท็กจากงานที่ปิดล่าสุด'

    return (
        f"ภาพรวม\n"
        f"ขณะนี้มีเรื่องที่ยังไม่แล้วเสร็จทั้งหมด {snapshot['total_open_records']} เรื่อง "
        f"โดยกลุ่มประเด็นที่พบมากคือ {top_categories} และหน่วยงานที่มีภาระติดตามมากคือ {top_orgs} "
        f"ขณะเดียวกันในช่วง 7 วันที่ผ่านมามีเรื่องที่ปิดแล้ว {snapshot['completed_last_7_days']} เรื่อง "
        f"ซึ่งส่วนใหญ่เป็น {completed_categories} ส่วนแท็กที่พบซ้ำในงานคงค้างได้แก่ {top_tags}\n\n"
        f"ประเด็นที่ควรติดตาม\n"
        f"- เรื่องเกินกำหนดมี {snapshot['overdue_count']} เรื่อง และเรื่องที่จะถึงกำหนดภายใน 3 วันมี {snapshot['due_soon_count']} เรื่อง\n"
        f"- เรื่องที่ยังไม่ระบุสถานะมี {snapshot['no_status_count']} เรื่อง และเรื่องที่ยังไม่พบผู้รับผิดชอบชัดเจนมี {snapshot['no_owner_count']} เรื่อง โดยแท็กที่อาจช่วยชี้ประเด็นคือ {top_tags}\n"
        f"- เรื่องที่ไม่มี deadline มี {snapshot['no_deadline_count']} เรื่อง มีเรื่องค้างเกิน 14 วันจำนวน {snapshot['aged_14_plus']} เรื่อง และมีเรื่องปิดใน 7 วันล่าสุด {snapshot['completed_last_7_days']} เรื่อง โดยแท็กของงานที่ปิดแล้วล่าสุดได้แก่ {completed_tags}\n\n"
        f"สิ่งที่ควรเฝ้าระวังวันนี้\n"
        f"ควรติดตามเรื่องที่เกินกำหนดหรือใกล้ครบกำหนดก่อนเป็นลำดับแรก พร้อมตรวจสอบการกำหนดสถานะ "
        f"deadline และผู้รับผิดชอบของเรื่องที่ยังเปิดอยู่ ควบคู่กับดูจังหวะการปิดงานในช่วง 7 วันที่ผ่านมา เพื่อให้ทุกคำขอเดินหน้าได้ทันเวลา."
    )


def _build_complaint_summary_email_body(snapshot, ai_summary):
    scope_topics = snapshot.get('scope_topics') or []
    scope_line = ', '.join(scope_topics) if scope_topics else 'ทุกหัวข้อที่รับผิดชอบ'
    status_lines = '\n'.join(
        f"- {label}: {count} เรื่อง" for label, count in snapshot['status_counts'].items()
    ) or '- ไม่มีข้อมูล'
    completed_lines = '\n'.join(
        f"- {item['label']}: {item['count']} เรื่อง" for item in snapshot['completed_top_categories']
    ) or '- ไม่มีข้อมูล'
    tag_lines = '\n'.join(
        f"- {item['label']}: {item['count']} เรื่อง" for item in snapshot['top_tags']
    ) or '- ไม่มีข้อมูล'
    return (
        f"สรุปภาพรวมเรื่องร้องเรียน/คำขอที่ยังไม่แล้วเสร็จ ณ {snapshot['generated_at']}\n\n"
        f"รายงานฉบับนี้จัดทำขึ้นโดยระบบอัตโนมัติร่วมกับ AI เพื่อช่วยสรุปภาพรวมสำหรับการติดตามงาน\n\n"
        f"ขอบเขตความรับผิดชอบ: {scope_line}\n\n"
        f"{ai_summary}\n\n"
        f"ตัวเลขประกอบการติดตาม\n"
        f"- เรื่องคงค้างทั้งหมด: {snapshot['total_open_records']} เรื่อง\n"
        f"- ปิดงานแล้วในช่วง 7 วันที่ผ่านมา: {snapshot['completed_last_7_days']} เรื่อง\n"
        f"- เกินกำหนด: {snapshot['overdue_count']} เรื่อง\n"
        f"- ครบกำหนดวันนี้: {snapshot['due_today_count']} เรื่อง\n"
        f"- จะครบกำหนดภายใน 3 วัน: {snapshot['due_soon_count']} เรื่อง\n"
        f"- ยังไม่กำหนด deadline: {snapshot['no_deadline_count']} เรื่อง\n"
        f"- ยังไม่ระบุสถานะ: {snapshot['no_status_count']} เรื่อง\n"
        f"- ยังไม่พบผู้รับผิดชอบชัดเจน: {snapshot['no_owner_count']} เรื่อง\n"
        f"- ค้างเกิน 7 วัน: {snapshot['aged_7_plus']} เรื่อง\n"
        f"- ค้างเกิน 14 วัน: {snapshot['aged_14_plus']} เรื่อง\n"
        f"- ค้างเกิน 30 วัน: {snapshot['aged_30_plus']} เรื่อง\n"
        f"- อายุค้างนานที่สุด: {snapshot['oldest_open_days']} วัน\n\n"
        f"สถานะปัจจุบัน\n"
        f"{status_lines}\n\n"
        f"แท็กที่พบซ้ำในงานคงค้าง\n"
        f"{tag_lines}\n\n"
        f"กลุ่มเรื่องที่ปิดแล้วใน 7 วันล่าสุด\n"
        f"{completed_lines}\n"
    )


def _build_summary_scope_label(recipient):
    topic_names = recipient.get('topic_names') or []
    if not topic_names:
        return 'หัวข้อที่อยู่ในความรับผิดชอบทั้งหมด'
    if len(topic_names) <= 3:
        return 'หัวข้อที่ครอบคลุม: {}'.format(', '.join(topic_names))
    return 'หัวข้อที่ครอบคลุม: {} และอีก {} หัวข้อ'.format(
        ', '.join(topic_names[:3]),
        len(topic_names) - 3,
    )


def _build_recipient_summary_package(recipient, snapshot_cache=None):
    snapshot_cache = snapshot_cache if snapshot_cache is not None else {}
    topic_ids = recipient.get('topic_ids') or []
    cache_key = tuple(topic_ids)
    snapshot = snapshot_cache.get(cache_key)
    if snapshot is None:
        snapshot = _build_unfinished_records_snapshot(topic_ids=topic_ids)
        snapshot_cache[cache_key] = snapshot
    snapshot = dict(snapshot)
    snapshot['scope_topics'] = recipient.get('topic_names') or []
    if _should_call_typhoon_summary(snapshot):
        try:
            ai_summary = _call_typhoon_complaint_summary(snapshot)
        except Exception:
            current_app.logger.exception(
                'Failed to generate complaint summary with Typhoon AI for %s.',
                recipient.get('email'),
            )
            ai_summary = _build_fallback_complaint_summary(snapshot)
    else:
        current_app.logger.info(
            'skip_typhoon_summary recipient=%s reason=all_key_metrics_zero',
            recipient.get('email'),
        )
        ai_summary = _build_fallback_complaint_summary(snapshot)

    scope_label = _build_summary_scope_label(recipient)
    subject = (
        'สรุปภาพรวมเรื่องร้องเรียน/คำขอที่ยังไม่แล้วเสร็จ '
        f'({scope_label}) '
        f"ณ {arrow.now('Asia/Bangkok').strftime('%d/%m/%Y %H:%M')}"
    )
    message = _build_complaint_summary_email_body(snapshot, ai_summary)
    return {
        'recipient': recipient,
        'snapshot': snapshot,
        'subject': subject,
        'message': message,
        'scope_label': scope_label,
    }


def _render_dry_run_chart(snapshot):
    values = [
        ('คงค้างทั้งหมด', snapshot['total_open_records'], '#1f77b4'),
        ('รอดำเนินการ/ค้าง', snapshot['status_counts'].get('รับเรื่อง/รอดำเนินการ', 0), '#ff7f0e'),
        ('ยังไม่ระบุสถานะ', snapshot['no_status_count'], '#d62728'),
        ('เกินกำหนด', snapshot['overdue_count'], '#9467bd'),
        ('ใกล้ครบกำหนด 3 วัน', snapshot['due_soon_count'], '#2ca02c'),
    ]
    max_value = max([value for _, value, _ in values] + [1])
    chart_width = 360
    bar_height = 20
    gap = 16
    rows = []
    y = 0
    for label, value, color in values:
        bar_width = int((value / max_value) * chart_width) if max_value else 0
        rows.append(
            f'<text x="0" y="{y + 14}" font-size="13" fill="#334155">{escape(label)} ({value})</text>'
            f'<rect x="170" y="{y}" width="{chart_width}" height="{bar_height}" rx="6" fill="#e2e8f0"></rect>'
            f'<rect x="170" y="{y}" width="{bar_width}" height="{bar_height}" rx="6" fill="{color}"></rect>'
        )
        y += bar_height + gap
    svg_height = max(y, 1)
    return (
        f'<svg viewBox="0 0 540 {svg_height}" width="100%" height="{svg_height}" role="img" '
        f'aria-label="Unfinished request chart">{"".join(rows)}</svg>'
    )


def _get_unfinished_chart_values(snapshot):
    return [
        ('คงค้างทั้งหมด', snapshot['total_open_records'], '#1f77b4'),
        ('รอดำเนินการ/ค้าง', snapshot['status_counts'].get('รับเรื่อง/รอดำเนินการ', 0), '#ff7f0e'),
        ('ยังไม่ระบุสถานะ', snapshot['no_status_count'], '#d62728'),
        ('เกินกำหนด', snapshot['overdue_count'], '#9467bd'),
        ('ใกล้ครบกำหนด 3 วัน', snapshot['due_soon_count'], '#2ca02c'),
    ]


def _should_call_typhoon_summary(snapshot):
    key_values = [
        snapshot.get('total_open_records', 0),
        snapshot.get('status_counts', {}).get('รับเรื่อง/รอดำเนินการ', 0),
        snapshot.get('no_status_count', 0),
        snapshot.get('overdue_count', 0),
        snapshot.get('due_soon_count', 0),
    ]
    return any(value > 0 for value in key_values)


def _render_email_chart_html(snapshot):
    values = _get_unfinished_chart_values(snapshot)
    max_value = max([value for _, value, _ in values] + [1])
    chart_width = 320
    rows = []
    for label, value, color in values:
        bar_width = max(int((value / max_value) * chart_width), 0) if max_value else 0
        if value > 0 and bar_width == 0:
            bar_width = 12
        remainder_width = max(chart_width - bar_width, 0)
        rows.append(f'''
        <tr>
          <td style="padding:6px 12px 6px 0;font-size:13px;color:#334155;white-space:nowrap;">{escape(label)} ({value})</td>
          <td style="padding:6px 0;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="{chart_width}" style="width:{chart_width}px;border-collapse:collapse;">
              <tr>
                <td width="{bar_width}" bgcolor="{color}" style="width:{bar_width}px;height:16px;line-height:16px;font-size:0;">&nbsp;</td>
                <td width="{remainder_width}" bgcolor="#e2e8f0" style="width:{remainder_width}px;height:16px;line-height:16px;font-size:0;">&nbsp;</td>
              </tr>
            </table>
          </td>
        </tr>
        ''')
    return f'''
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse;">
      {''.join(rows)}
    </table>
    '''


def _render_dry_run_html(packages, should_send):
    cards = []
    for package in packages:
        recipient = package['recipient']
        snapshot = package['snapshot']
        chart_html = _render_dry_run_chart(snapshot)
        message_html = escape(package['message']).replace('\n', '<br>')
        recipient_emails = recipient.get('emails') or [recipient.get('email')]
        recipients_label = ', '.join(email for email in recipient_emails if email)
        cards.append(f'''
        <section class="card">
            <div class="card-header">
                <div class="pill">{escape(package['scope_label'])}</div>
            </div>
            <div class="summary-card">
                <h3>ตัวเลขสำคัญ</h3>
                <div class="summary-metrics">
                    <span><strong>{snapshot['total_open_records']}</strong> เรื่องคงค้าง</span>
                    <span><strong>{snapshot['overdue_count']}</strong> เกินกำหนด</span>
                    <span><strong>{snapshot['due_soon_count']}</strong> ใกล้ครบกำหนด</span>
                    <span><strong>{snapshot['completed_last_7_days']}</strong> ปิดใน 7 วัน</span>
                </div>
            </div>
            <div class="chart-wrap">
                <h3>ภาพรวมงานคงค้าง</h3>
                {chart_html}
            </div>
            <div class="meta">
                <p><strong>Subject:</strong> {escape(package['subject'])}</p>
                <p><strong>Recipients:</strong> {escape(recipients_label)}</p>
            </div>
            <div class="message">
                <h3>Message Preview</h3>
                <div class="message-body">{message_html}</div>
            </div>
        </section>
        ''')

    return f'''<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Complaint Summary Dry Run</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --panel: #ffffff;
      --line: #dbe4ee;
      --text: #0f172a;
      --muted: #64748b;
      --accent: #0f766e;
    }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); }}
    .page {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px 60px; }}
    .hero {{ margin-bottom: 24px; }}
    .hero h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .hero p {{ margin: 0; color: var(--muted); }}
    .notice {{ margin-top: 14px; background: #ecfeff; color: #115e59; border: 1px solid #99f6e4; border-radius: 14px; padding: 14px 16px; line-height: 1.6; }}
    .grid {{ display: grid; gap: 20px; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 20px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06); }}
    .card-header {{ display: flex; justify-content: flex-start; gap: 16px; align-items: start; margin-bottom: 16px; }}
    .muted {{ color: var(--muted); }}
    .pill {{ background: #ecfeff; color: var(--accent); border: 1px solid #99f6e4; border-radius: 999px; padding: 8px 12px; font-size: 13px; }}
    .summary-card {{ background: #f8fafc; border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; margin-bottom: 18px; }}
    .summary-card h3 {{ margin: 0 0 10px; font-size: 16px; }}
    .summary-metrics {{ display: flex; flex-wrap: wrap; gap: 10px 18px; }}
    .summary-metrics span {{ color: var(--muted); font-size: 14px; }}
    .summary-metrics strong {{ color: var(--text); font-size: 20px; margin-right: 4px; }}
    .chart-wrap h3, .message h3 {{ margin: 0 0 12px; font-size: 16px; }}
    .meta {{ margin: 16px 0; font-size: 14px; }}
    .message-body {{ background: #f8fafc; color: #0f172a; border: 1px solid var(--line); border-radius: 14px; padding: 16px; line-height: 1.65; font-size: 14px; }}
    @media (max-width: 800px) {{
      .card-header {{ flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header class="hero">
      <h1>Dry Run: Complaint Summary Email</h1>
      <p>Send flag: {str(should_send)} | Email group count: {len(packages)}</p>
      <div class="notice">รายงานตัวอย่างนี้และเนื้อหาสรุปในอีเมลจัดทำขึ้นโดยระบบอัตโนมัติร่วมกับ AI เพื่อช่วยสรุปภาพรวมสำหรับการติดตามงาน</div>
    </header>
    <div class="grid">
      {''.join(cards) if cards else '<section class="card"><p>No recipients found.</p></section>'}
    </div>
  </main>
</body>
</html>'''


def _render_summary_email_html(package):
    recipient = package['recipient']
    snapshot = package['snapshot']
    chart_html = _render_email_chart_html(snapshot)
    message_html = escape(package['message']).replace('\n', '<br>')
    return f'''<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(package['subject'])}</title>
</head>
<body style="margin:0;padding:24px;background:#f8fafc;color:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:900px;margin:0 auto;">
    <div style="margin-bottom:20px;">
      <h1 style="margin:0 0 8px;font-size:28px;">สรุปรายงานเรื่องร้องเรียน/คำขอ</h1>
      <div style="margin-top:14px;background:#ecfeff;color:#115e59;border:1px solid #99f6e4;border-radius:14px;padding:14px 16px;line-height:1.6;">
        รายงานฉบับนี้จัดทำขึ้นโดยระบบอัตโนมัติร่วมกับ AI เพื่อช่วยสรุปภาพรวมสำหรับการติดตามงาน
      </div>
    </div>
    <section style="background:#ffffff;border:1px solid #dbe4ee;border-radius:18px;padding:20px;box-shadow:0 10px 30px rgba(15,23,42,0.06);">
      <div style="display:flex;justify-content:flex-start;gap:16px;align-items:flex-start;margin-bottom:16px;">
        <div style="background:#ecfeff;color:#0f766e;border:1px solid #99f6e4;border-radius:999px;padding:8px 12px;font-size:13px;">
          {escape(package['scope_label'])}
        </div>
      </div>
      <div style="background:#f8fafc;border:1px solid #dbe4ee;border-radius:14px;padding:14px 16px;margin-bottom:18px;">
        <h3 style="margin:0 0 10px;font-size:16px;">ตัวเลขสำคัญ</h3>
        <div style="font-size:14px;color:#64748b;line-height:1.9;">
          <span style="display:inline-block;margin-right:18px;"><strong style="color:#0f172a;font-size:20px;margin-right:4px;">{snapshot['total_open_records']}</strong>เรื่องคงค้าง</span>
          <span style="display:inline-block;margin-right:18px;"><strong style="color:#0f172a;font-size:20px;margin-right:4px;">{snapshot['overdue_count']}</strong>เกินกำหนด</span>
          <span style="display:inline-block;margin-right:18px;"><strong style="color:#0f172a;font-size:20px;margin-right:4px;">{snapshot['due_soon_count']}</strong>ใกล้ครบกำหนด</span>
          <span style="display:inline-block;margin-right:18px;"><strong style="color:#0f172a;font-size:20px;margin-right:4px;">{snapshot['completed_last_7_days']}</strong>ปิดใน 7 วัน</span>
        </div>
      </div>
      <div style="margin-bottom:16px;">
        <h3 style="margin:0 0 12px;font-size:16px;">ภาพรวมงานคงค้าง</h3>
        {chart_html}
      </div>
      <div style="margin:16px 0;font-size:14px;">
        <p style="margin:0 0 8px;"><strong>Subject:</strong> {escape(package['subject'])}</p>
      </div>
      <div>
        <h3 style="margin:0 0 12px;font-size:16px;">รายงานสรุป</h3>
        <div style="background:#f8fafc;color:#0f172a;border:1px solid #dbe4ee;border-radius:14px;padding:16px;line-height:1.65;font-size:14px;">{message_html}</div>
      </div>
    </section>
  </div>
</body>
</html>'''


# def initialize_gdrive():
#     try:
#         gauth = GoogleAuth()
#         scopes = ['https://www.googleapis.com/auth/drive']
#         gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scopes)
#         return GoogleDrive(gauth)
#     except Exception as e:
#         print(f"เกิดข้อผิดพลาดในการเชื่อมต่อ Google Drive: {e}")
#         return None


@complaint_tracker.route('/api/committee/position')
@login_required
def get_position():
    staff_id = request.args.get('staff_id')
    staff = StaffAccount.query.filter_by(id=staff_id).first()
    position = staff.personal_info.position if staff else ''
    return jsonify({"position": position})


@complaint_tracker.route('/')
def index():
    categories = ComplaintCategory.query.all()
    return render_template('complaint_tracker/index.html', categories=categories)


@complaint_tracker.route('/issue/<int:topic_id>', methods=['GET', 'POST'])
def new_record(topic_id, room=None, procurement=None):
    topic = ComplaintTopic.query.get(topic_id)
    ComplaintRecordForm = create_record_form(record_id=None, topic_id=topic_id)
    form = ComplaintRecordForm()
    room_number = request.values.get('number')
    location = request.values.get('location')
    procurement_no = request.values.get('procurement_no')
    pro_number = request.values.get('pro_number')
    is_admin = False
    if not current_user.is_authenticated and topic.topic == 'แจ้งครุภัณฑ์ชำรุด':
        return redirect(url_for('auth.login'))
    if current_user.is_authenticated:
        is_admin = True if ComplaintAdmin.query.filter_by(admin=current_user, topic_id=topic_id).first() else False
    if room_number and location:
        room = RoomResource.query.filter_by(number=room_number, location=location).first()
    elif procurement_no or pro_number:
        procurement = ProcurementDetail.query.filter_by(
            procurement_no=procurement_no if procurement_no else pro_number).first()
    if form.validate_on_submit():
        record = ComplaintRecord()
        form.populate_obj(record)
        file = form.file_upload.data
        record.topic = topic
        record.created_at = arrow.now('Asia/Bangkok').datetime
        if current_user.is_authenticated:
            record.complainant = current_user
        if file and allowed_file(file.filename):
            mime_type = file.mimetype
            file_name = '{}.{}'.format(uuid.uuid4().hex, file.filename.split('.')[-1])
            file_data = file.stream.read()
            response = s3.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=file_name,
                Body=file_data,
                ContentType=mime_type
            )
            record.url = file_name
        if topic.code == 'room' and room:
            record.room = room
        elif topic.code == 'runied' and procurement:
            record.procurements.append(procurement)
        if (((form.is_contact.data and form.fl_name.data and (form.telephone.data or form.email.data)) or
             (not form.is_contact.data and (form.fl_name.data or form.telephone.data or form.email.data))) or
                (not form.is_contact.data and not form.fl_name.data and not form.telephone.data and not form.email.data)):
            db.session.add(record)
            db.session.commit()
            flash('รับเรื่องแจ้งเรียบร้อย', 'success')
            scheme = 'http' if current_app.debug else 'https'
            complaint_link = url_for("comp_tracker.edit_record_admin", record_id=record.id, _external=True,
                                     _scheme=scheme)
            msg = ('มีการแจ้งเรื่องในส่วนของ{} หัวข้อ{}' \
                   '\nเวลาแจ้ง : วันที่ {} เวลา {}' \
                   '\nซึ่งมีรายละเอียด ดังนี้ {}' \
                   '\nคลิกที่ Link เพื่อดำเนินการ {}'.format(topic.category, topic.topic,
                                                             record.created_at.astimezone(localtz).strftime('%d/%m/%Y'),
                                                             record.created_at.astimezone(localtz).strftime('%H:%M'),
                                                             form.desc.data,
                                                             complaint_link)
                   )
            if not current_app.debug:
                for a in topic.admins:
                    if a.is_supervisor == False:
                        try:
                            line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                        except LineBotApiError:
                            pass
            else:
                print('msg:', msg, 'line_id', [a.admin.line_id for a in topic.admins if a.is_supervisor == False])
            if current_user.is_authenticated:
                return redirect(url_for('comp_tracker.complainant_index'))
            else:
                return redirect(url_for('comp_tracker.closing_page'))
        else:
            flash('กรุณากรอกชื่อ-นามสกุล และเบอร์โทรศัพท์ หรืออีเมล', 'danger')
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('complaint_tracker/record_form.html', form=form, topic=topic, room=room,
                           is_admin=is_admin, procurement=procurement)


@complaint_tracker.route('issue/closing-page')
def closing_page():
    return render_template('complaint_tracker/closing.html')


@complaint_tracker.route('/issue/records/<int:record_id>', methods=['GET', 'POST', 'PATCH'])
@login_required
def edit_record_admin(record_id):
    tab = request.args.get('tab')
    procurement_no = request.args.get('procurement_no')
    pro_number = request.args.get('pro_number')
    statuses = ComplaintStatus.query.all()
    record = ComplaintRecord.query.get(record_id)
    if record:
        old_status = record.status
        admins = True if ComplaintAdmin.query.filter_by(admin=current_user, topic=record.topic).first() else False
        investigators = []
        if procurement_no or pro_number:
            procurement = ProcurementDetail.query.filter_by(procurement_no=procurement_no if procurement_no
                            else pro_number).first()
            record.procurements.clear()
            record.procurements.append(procurement)
        coordinators = ComplaintCoordinator.query.filter_by(coordinator=current_user, record_id=record_id).first() \
            if ComplaintCoordinator.query.filter_by(coordinator=current_user, record_id=record_id).first() else None
        for i in record.investigators:
            if i.admin.admin == current_user:
                investigators.append(i)
        if record.repair_approvals:
            for repair_approval in record.repair_approvals:
                repair_approval_id = repair_approval.id
        else:
            repair_approval_id = None
        ComplaintRecordForm = create_record_form(record_id=record_id, topic_id=None)
        form = ComplaintRecordForm(obj=record)
        form.deadline.data = form.deadline.data.astimezone(localtz) if form.deadline.data else None
        if record.url and len(record.url) > 0:
            file_url = generate_url(record.url)
        else:
            file_url = None
        if request.method == 'PATCH':
            if record.closed_at is None:
                record.closed_at = arrow.now('Asia/Bangkok').datetime
                flash('ปิดรายการเรียบร้อย', 'success')
            else:
                record.closed_at = None
                flash('เปิดรายการอีกครั้งเรียบร้อย', 'success')
            db.session.add(record)
            db.session.commit()
            resp = make_response()
            resp.headers['HX-Refresh'] = 'true'
            return resp
        if form.validate_on_submit():
            old_priority = record.priority.priority if record.priority else None
            new_status = form.status.data
            if new_status and new_status.no != 4:
                if old_status and new_status:
                    if (old_status.no > new_status.no) or (old_status.no + 1 < new_status.no):
                        form.status.data = old_status
                        flash('ไม่สามารถย้อนหรือข้ามลำดับสถานะได้ กรุณาเลือกสถานะถัดไปเท่านั้น', 'danger')
                        return render_template('complaint_tracker/admin_record_form.html', form=form, record=record,
                                               tab=tab, file_url=file_url, admins=admins, investigators=investigators,
                                               coordinators=coordinators, repair_approval_id=repair_approval_id, statuses=statuses)
                elif old_status and not new_status:
                    form.status.data = old_status
                    flash('ไม่สามารถย้อนหรือข้ามลำดับสถานะได้ กรุณาเลือกสถานะถัดไปเท่านั้น', 'danger')
                    return render_template('complaint_tracker/admin_record_form.html', form=form, record=record,
                                           tab=tab, file_url=file_url, admins=admins, investigators=investigators,
                                           coordinators=coordinators, repair_approval_id=repair_approval_id,
                                           statuses=statuses)
                elif not old_status and new_status:
                    first_status = ComplaintStatus.query.filter_by(no=1).first()
                    if not first_status:
                        current_app.logger.error(
                            'complaint_status_config_missing_first_status record_id=%s new_status_id=%s',
                            record_id,
                            new_status.id,
                        )
                        form.status.data = None
                        flash('ไม่พบสถานะแรกของกระบวนการ กรุณาติดต่อผู้ดูแลระบบ', 'danger')
                        return render_template('complaint_tracker/admin_record_form.html', form=form, record=record, tab=tab,
                                               file_url=file_url, admins=admins, investigators=investigators, coordinators=coordinators,
                                               repair_approval_id=repair_approval_id, statuses=statuses)
                    if (first_status.no != new_status.no):
                        form.status.data = None
                        flash('ไม่สามารถย้อนหรือข้ามลำดับสถานะได้ กรุณาเลือกสถานะถัดไปเท่านั้น', 'danger')
                        return render_template('complaint_tracker/admin_record_form.html', form=form, record=record,
                                               tab=tab, file_url=file_url, admins=admins, investigators=investigators,
                                               coordinators=coordinators, repair_approval_id=repair_approval_id,
                                               statuses=statuses)
            form.populate_obj(record)
            record.deadline = arrow.get(form.deadline.data, 'Asia/Bangkok').datetime if form.deadline.data else None
            db.session.add(record)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            new_priority = record.priority.priority if record.priority else None
            if old_priority != 2 and new_priority == 2:
                if not current_app.debug:
                    complaint_link = url_for("comp_tracker.edit_record_admin", record_id=record_id, _external=True
                                             , _scheme='https')
                    create_at = arrow.get(record.created_at, 'Asia/Bangkok').datetime
                    msg = ('มีการแจ้งเรื่องในส่วนของ{} หัวข้อ{}' \
                           '\nเวลาแจ้ง : วันที่ {} เวลา {}' \
                           '\nซึ่งมีรายละเอียด ดังนี้ {}' \
                           '\nคลิกที่ Link เพื่อดำเนินการ {}'.format(record.topic.category, record.topic,
                                                                     create_at.astimezone(localtz).strftime('%d/%m/%Y'),
                                                                     create_at.astimezone(localtz).strftime('%H:%M'),
                                                                     record.desc, complaint_link)
                           )
                    for a in record.topic.admins:
                        if a.is_supervisor:
                            try:
                                line_bot_api.push_message(to=a.admin.line_id, messages=TextSendMessage(text=msg))
                            except LineBotApiError:
                                pass
            if record.status != old_status and record.complainant:
                if record.status_id:
                    rec = ComplaintRecordStatusAssociation(status_id=record.status_id, record_id=record_id,
                                                           updated_at=arrow.now('Asia/Bangkok').datetime)
                    db.session.add(rec)
                    db.session.commit()
                scheme = 'http' if current_app.debug else 'https'
                link = url_for("comp_tracker.view_record_complaint", record_id=record_id, _external=True,
                               _scheme=scheme)
                msg = (f'มีการอัปเดตสถานะคำร้องขอ{record.topic.topic}\n'
                       f'รายละเอียด : {record.desc}\n'
                       f'สถานะปัจจุบัน : {record.status or "ยังไม่ดำเนินการ"}\n'
                       f'คลิกที่ Link เพื่อตรวจสอบ {link}')
                title = f'''แจ้งอัปเดตสถานะคำร้องขอ{record.topic.topic}'''
                message = f'''เจ้าหน้าที่ได้ทำการอัปเดตสถานะคำร้องขอ{record.topic.topic} ของ{record.desc}เป็น "{record.status or 'ยังไม่ดำเนินการ'}" เรียบร้อยแล้ว\n\n'''
                message += f'''ท่านสามารถตรวจสอบรายละเอียดเพิ่มเติมได้ที่ลิงก์ด้านล่าง\n'''
                message += f'''{link}\n\n'''
                message += f'''ขอบคุณค่ะ\n'''
                message += f'''ระบบรับแจ้งปัญหาหรือข้อร้องเรียน\n'''
                message += f'''คณะเทคนิคการแพทย์'''
                send_mail([record.complainant.email + '@mahidol.ac.th'], title, message)
                if not current_app.debug:
                    try:
                        line_bot_api.push_message(to=record.complainant.line_id, messages=TextSendMessage(text=msg))
                    except LineBotApiError:
                        pass
                else:
                    print('line_id :', record.complainant.line_id, 'msg :', msg)
        return render_template('complaint_tracker/admin_record_form.html', form=form, record=record, tab=tab,
                               file_url=file_url, admins=admins, investigators=investigators, coordinators=coordinators,
                               statuses=statuses)
    else:
        return render_template('complaint_tracker/record_cancelled_page.html', record_id=record_id,
                               tab=tab)


@complaint_tracker.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_index():
    tab = request.args.get('tab')
    admin_rows = ComplaintAdmin.query.with_entities(
        ComplaintAdmin.id,
        ComplaintAdmin.topic_id
    ).filter(ComplaintAdmin.staff_account == current_user.id).all()
    admin_ids = {admin_id for admin_id, _ in admin_rows}
    admin_topic_ids = {topic_id for _, topic_id in admin_rows if topic_id}

    record_ids = set()
    if admin_topic_ids:
        record_ids.update(
            record_id for record_id, in db.session.query(ComplaintRecord.id)
            .filter(ComplaintRecord.topic_id.in_(admin_topic_ids))
            .all()
        )
    if admin_ids:
        record_ids.update(
            record_id for record_id, in db.session.query(ComplaintInvestigator.record_id)
            .filter(ComplaintInvestigator.admin_id.in_(admin_ids))
            .all()
            if record_id
        )
    record_ids.update(
        record_id for record_id, in db.session.query(ComplaintCoordinator.record_id)
        .filter(ComplaintCoordinator.coordinator_id == current_user.id)
        .all()
        if record_id
    )

    records = []
    new_record_count = 0
    pending_record_count = 0
    progress_record_count = 0
    repair_record_count = 0
    admin_record_ids = set()

    if record_ids:
        status_counts = dict(
            db.session.query(ComplaintStatus.code, func.count(ComplaintRecord.id))
            .outerjoin(ComplaintRecord.status)
            .filter(ComplaintRecord.id.in_(record_ids))
            .group_by(ComplaintStatus.code)
            .all()
        )
        new_record_count = status_counts.get(None, 0)
        pending_record_count = status_counts.get('pending', 0)
        progress_record_count = status_counts.get('progress', 0)

        repair_record_count = db.session.query(
            func.count(func.distinct(ComplaintRecord.id))
        ).outerjoin(
            ComplaintRepair, ComplaintRepair.record_id == ComplaintRecord.id
        ).outerjoin(
            ComplaintRepairApproval, ComplaintRepairApproval.record_id == ComplaintRecord.id
        ).filter(
            ComplaintRecord.id.in_(record_ids),
            or_(
                and_(ComplaintRepair.id.isnot(None), ComplaintRepair.is_print.is_(False)),
                and_(ComplaintRepairApproval.id.isnot(None), ComplaintRepairApproval.is_print.is_(False))
            )
        ).scalar() or 0

        query = ComplaintRecord.query.options(
            selectinload(ComplaintRecord.topic)
            .selectinload(ComplaintTopic.admins)
            .selectinload(ComplaintAdmin.admin),
            joinedload(ComplaintRecord.type),
            joinedload(ComplaintRecord.priority),
            joinedload(ComplaintRecord.status),
            selectinload(ComplaintRecord.tags),
            selectinload(ComplaintRecord.repairs),
            selectinload(ComplaintRecord.repair_approvals)
        ).filter(ComplaintRecord.id.in_(record_ids))

        if tab == 'new':
            query = query.filter(ComplaintRecord.status_id.is_(None))
        elif tab == 'repair_record':
            query = query.filter(or_(ComplaintRecord.repairs.any(), ComplaintRecord.repair_approvals.any()))
        elif tab in ('pending', 'progress', 'completed', 'cancelled'):
            query = query.join(ComplaintStatus).filter(ComplaintStatus.code == tab)
        else:
            query = query.filter(ComplaintRecord.id.is_(None))

        records = query.order_by(ComplaintRecord.id.desc()).all()
        if admin_topic_ids and records:
            admin_record_ids = {
                record.id for record in records
                if record.topic_id in admin_topic_ids
            }
    return render_template('complaint_tracker/admin_index.html', records=records, tab=tab,
                           new_record_count=new_record_count, pending_record_count=pending_record_count,
                           progress_record_count=progress_record_count, repair_record_count=repair_record_count,
                           admin_record_ids=admin_record_ids)


@complaint_tracker.route('/topics/<code>')
def scan_qr_code_room(code):
    topic = ComplaintTopic.query.filter_by(code=code).first()
    return redirect(url_for('comp_tracker.new_record', topic_id=topic.id, **request.args))


@complaint_tracker.route('/scan-qrcode/complaint/<code>', methods=['GET', 'POST'])
@csrf.exempt
def scan_qr_code_complaint(code):
    cat = request.args.get('cat')
    tab = request.args.get('tab')
    record_id = request.args.get('record_id', type=int)
    topic = ComplaintTopic.query.filter_by(code=code).first()
    return render_template('complaint_tracker/qr_code_scan_to_complaint.html', topic_id=topic.id, cat=cat,
                           tab=tab, record_id=record_id)


@complaint_tracker.route('/issue/comment/add/<int:record_id>', methods=['GET', 'POST'])
@complaint_tracker.route('/issue/comment/edit/<int:action_id>', methods=['GET', 'POST'])
@login_required
def edit_comment(record_id=None, action_id=None):
    if record_id:
        record = ComplaintRecord.query.get(record_id)
        admin = ComplaintAdmin.query.filter_by(admin=current_user, topic=record.topic).first()
        if not admin:
            misc_topic = ComplaintTopic.query.filter_by(code='misc').first()
            admin = ComplaintAdmin.query.filter_by(admin=current_user, topic=misc_topic).first()
        form = ComplaintActionRecordForm()
    elif action_id:
        action = ComplaintActionRecord.query.get(action_id)
        form = ComplaintActionRecordForm(obj=action)
    if form.validate_on_submit():
        if record_id:
            action = ComplaintActionRecord()
        form.populate_obj(action)
        if record_id:
            action.record_id = record_id
            action.reviewer_id = admin.id
        action.comment_datetime = arrow.now('Asia/Bangkok').datetime
        db.session.add(action)
        db.session.commit()
        if record_id:
            flash('เพิ่มข้อมูลสำเร็จ', 'success')
            resp = make_response(render_template('complaint_tracker/comment_template.html', action=action))
            resp.headers['HX-Trigger'] = 'closeModal'
        else:
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
            resp = make_response()
            resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('complaint_tracker/modal/comment_record_modal.html', record_id=record_id,
                           action_id=action_id, form=form)


@complaint_tracker.route('/issue/comment/delete/<int:action_id>', methods=['GET', 'DELETE'])
@login_required
def delete_comment(action_id):
    if request.method == 'DELETE':
        action = ComplaintActionRecord.query.get(action_id)
        db.session.delete(action)
        db.session.commit()
        flash('ลบข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@complaint_tracker.route('/issue/invited/add/<int:record_id>', methods=['GET', 'POST'])
@complaint_tracker.route('/issue/invited/delete/<int:investigator_id>', methods=['GET', 'DELETE'])
@complaint_tracker.route('/issue/coordinators/delete/<int:coordinator_id>', methods=['GET', 'DELETE'])
@login_required
def edit_invited(record_id=None, investigator_id=None, coordinator_id=None):
    form = ComplaintInvestigatorForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            invites = []
            coordinators = []
            for admin_id in form.invites.data:
                admin = ComplaintAdmin.query.filter_by(staff_account=admin_id.id).first()
                if admin:
                    investigator = ComplaintInvestigator(inviter_id=current_user.id, admin_id=admin.id,
                                                         record_id=record_id)
                    db.session.add(investigator)
                    invites.append(investigator)
                else:
                    coordinator = ComplaintCoordinator(coordinator_id=admin_id.id, record_id=record_id,
                                                       recorder_id=current_user.id)
                    db.session.add(coordinator)
                    coordinators.append(coordinator)
            db.session.commit()
            record = ComplaintRecord.query.get(record_id)
            create_at = arrow.get(record.created_at, 'Asia/Bangkok').datetime
            complaint_link = url_for('comp_tracker.edit_record_admin', record_id=record_id, _external=True
                                     , _scheme='https')
            msg = ('มีการแจ้งเรื่องในส่วนของ{} หัวข้อ{}' \
                   '\nเวลาแจ้ง : วันที่ {} เวลา {}' \
                   '\nซึ่งมีรายละเอียด ดังนี้ {}'
                   '\nคลิกที่ Link เพื่อดำเนินการ {}'.format(record.topic.category, record.topic.topic,
                                                             create_at.astimezone(localtz).strftime('%d/%m/%Y'),
                                                             create_at.astimezone(localtz).strftime('%H:%M'),
                                                             record.desc, complaint_link))
            title = f'''แจ้งปัญหาในส่วนของ{record.topic.category}'''
            message = f'''มีการแจ้งปัญหามาในเรื่องของ{record.topic} โดยมีรายละเอียดปัญหาที่พบ ได้แก่ {record.desc}\n\n'''
            message += f'''กรุณาดำเนินการแก้ไขปัญหาตามที่ได้รับแจ้งจากผู้ใช้งาน\n\n\n'''
            message += f'''ลิงค์สำหรับดำเนินการแก้ไขปัญหา : {complaint_link}'''
            if invites:
                invited = [invite.admin.admin.email + '@mahidol.ac.th' for invite in invites]
                send_mail(invited, title, message)
            if coordinators:
                cor = [coordinator.coordinator.email + '@mahidol.ac.th' for coordinator in coordinators]
                send_mail(cor, title, message)
            if not current_app.debug:
                for invite in invites:
                    try:
                        line_bot_api.push_message(to=invite.admin.admin.line_id, messages=TextSendMessage(text=msg))
                    except LineBotApiError:
                        pass
            flash('เพิ่มรายชื่อผู้เกี่ยวข้องสำเร็จ', 'success')
            resp = make_response(render_template('complaint_tracker/invite_template.html',
                                                 invites=invites, coordinators=coordinators))
            resp.headers['HX-Trigger'] = 'closePopup'
            return resp
    elif request.method == 'DELETE':
        if investigator_id:
            investigator = ComplaintInvestigator.query.get(investigator_id)
            db.session.delete(investigator)
            title = f'''แจ้งยกเลิกการเป็นผู้เกี่ยวข้องการดำเนินการแก้ไขปัญหา'''
            message = f'''ท่านได้ถูกยกเลิกในการเป็นผู้เกี่ยวข้องการดำเนินการแก้ไขปัญหาในหัวข้อ{investigator.record.topic} โดยมีรายละเอียดปัญหา ดังนี้ {investigator.record.desc}\n\n'''
            send_mail([investigator.admin.admin.email + '@mahidol.ac.th'], title, message)
        else:
            coordinator = ComplaintCoordinator.query.get(coordinator_id)
            db.session.delete(coordinator)
            title = f'''แจ้งยกเลิกการเป็นผู้เกี่ยวข้องการดำเนินการแก้ไขปัญหา'''
            message = f'''ท่านได้ถูกยกเลิกในการเป็นผู้เกี่ยวข้องการดำเนินการแก้ไขปัญหาในหัวข้อ{coordinator.record.topic} โดยมีรายละเอียดปัญหา ดังนี้ {coordinator.record.desc}\n\n'''
            send_mail([coordinator.coordinator.email + '@mahidol.ac.th'], title, message)
        db.session.commit()
        flash('ลบรายชื่อผู้เกี่ยวข้องสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('complaint_tracker/modal/invite_record_modal.html', record_id=record_id,
                           form=form)


@complaint_tracker.route('/complaint/user', methods=['GET'])
@login_required
def complainant_index():
    records = ComplaintRecord.query.filter_by(complainant=current_user)
    is_admin = True if ComplaintAdmin.query.filter_by(admin=current_user).first() else False
    return render_template('complaint_tracker/complainant_index.html', records=records, is_admin=is_admin)


@complaint_tracker.route('/api/priority')
@login_required
def check_priority():
    priority_id = request.args.get('priorityID')
    priority = ComplaintPriority.query.get(priority_id)
    template = f'<span class="tag is-light">{priority.priority_detail}</span>'
    template += f'<span id="priority" class="tags"></span>'
    resp = make_response(template)
    return resp


@complaint_tracker.route('/issue/spare-part/add/<int:record_id>', methods=['GET', 'POST'])
@complaint_tracker.route('/issue/spare-part/edit/<int:spare_part_id>', methods=['GET', 'POST'])
@login_required
def create_spare_part(record_id=None, spare_part_id=None):
    if record_id:
        form = ComplaintSparePartForm()
    else:
        spare_part = ComplaintSparePart.query.get(spare_part_id)
        form = ComplaintSparePartForm(obj=spare_part)
    if form.validate_on_submit():
        if record_id:
            spare_part = ComplaintSparePart()
        form.populate_obj(spare_part)
        if record_id:
            spare_part.record_id = record_id
            spare_part.created_at = arrow.now('Asia/Bangkok').datetime
        else:
            spare_part.updated_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(spare_part)
        db.session.commit()
        if record_id:
            flash('เพิ่มข้อมูลสำเร็จ', 'success')
            resp = make_response(render_template('complaint_tracker/spare_part_template.html',
                                                 spare_part=spare_part))
            resp.headers['HX-Trigger'] = 'closeSparePart'
        else:
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
            resp = make_response()
            resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('complaint_tracker/modal/create_spare_part_modal.html', form=form,
                           record_id=record_id, spare_part_id=spare_part_id)


@complaint_tracker.route('/issue/spare-part/delete/<int:spare_part_id>', methods=['GET', 'DELETE'])
@login_required
def delete_spare_part(spare_part_id):
    if request.method == 'DELETE':
        spare_part = ComplaintSparePart.query.get(spare_part_id)
        db.session.delete(spare_part)
        db.session.commit()
        flash('ลบข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@complaint_tracker.route('/issue/report/add/<int:record_id>', methods=['GET', 'POST'])
@complaint_tracker.route('/issue/report/edit/<int:report_id>', methods=['GET', 'POST'])
@login_required
def create_report(record_id=None, report_id=None):
    if record_id:
        record = ComplaintRecord.query.get(record_id)
        admin = ComplaintAdmin.query.filter_by(admin=current_user, topic=record.topic).first()
        if not admin:
            misc_topic = ComplaintTopic.query.filter_by(code='misc').first()
            admin = ComplaintAdmin.query.filter_by(admin=current_user, topic=misc_topic).first()
        form = ComplaintPerformanceReportForm()
    elif report_id:
        report = ComplaintPerformanceReport.query.get(report_id)
        form = ComplaintPerformanceReportForm(obj=report)
    if form.validate_on_submit():
        if record_id:
            report = ComplaintPerformanceReport()
        form.populate_obj(report)
        if record_id:
            report.record_id = record_id
            report.reporter_id = admin.id
        report.report_datetime = arrow.now('Asia/Bangkok').datetime
        db.session.add(report)
        db.session.commit()
        if record_id:
            flash('เพิ่มข้อมูลสำเร็จ', 'success')
            resp = make_response(render_template('complaint_tracker/performance_report_template.html',
                                                 report=report))
            resp.headers['HX-Trigger'] = 'closeReport'
        else:
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
            resp = make_response()
            resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('complaint_tracker/modal/performance_report_modal.html', record_id=record_id,
                           report_id=report_id, form=form)


@complaint_tracker.route('/issue/report/delete/<int:report_id>', methods=['GET', 'DELETE'])
@login_required
def delete_report(report_id):
    if request.method == 'DELETE':
        report = ComplaintPerformanceReport.query.get(report_id)
        db.session.delete(report)
        db.session.commit()
        flash('ลบข้อมูลสำเร็จ', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@complaint_tracker.route('/issue/record/coordinator/complaint-acknowledgment/<int:coordinator_id>',
                         methods=['GET', 'POST'])
@login_required
def acknowledge_complaint(coordinator_id):
    if request.method == 'POST':
        coordinator = ComplaintCoordinator.query.get(coordinator_id)
        coordinator.received_datetime = arrow.now('Asia/Bangkok').datetime
        db.session.add(coordinator)
        db.session.commit()
        flash('ยืนยันเรียบร้อย', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp


@complaint_tracker.route('/issue/record/coordinator/note/add/<int:coordinator_id>', methods=['GET', 'POST'])
@login_required
def edit_note(coordinator_id):
    coordinator = ComplaintCoordinator.query.get(coordinator_id)
    form = ComplaintCoordinatorForm(obj=coordinator)
    if request.method == 'GET':
        template = '''
            <tr>
                <td style="width: 100%;">
                    <label class="label">รายงานผลการดำเนินงาน</label>{}
                </td>
                <td>
                    <a class="button is-success is-outlined"
                        hx-post="{}" hx-include="closest tr">
                        <span class="icon"><i class="fas fa-save"></i></span>
                        <span class="has-text-success">บันทึก</span>
                    </a>
                </td>
            </tr>
            '''.format(form.note(class_="textarea"),
                       url_for('comp_tracker.edit_note', coordinator_id=coordinator.id)
                       )
    if request.method == 'POST':
        coordinator.note = request.form.get('note')
        db.session.add(coordinator)
        db.session.commit()
        flash('บันทึกรายงานผลการดำเนินงานสำเร็จ', 'success')
        template = '''
            <tr>
                <td style="width: 100%;">
                    <label class="label">รายงานผลการดำเนินงาน</label>
                    <p class="notification">{}</p>
                </td>
                <td>
                    <div class="field has-addons">
                        <div class="control">
                            <a class="button is-light is-outlined"
                               hx-get="{}">
                                <span class="icon">
                                   <i class="fas fa-pencil has-text-dark"></i>
                                </span>
                                <span class="has-text-dark">ร่าง</span>
                            </a>
                        </div>
                        <div class="control">
                            <a class="button is-light is-outlined"
                                style="width: 5em"
                                hx-patch="{}"
                                hx-confirm="ท่านต้องการส่งรายงานผลการดำเนินงานหรือไม่">
                                <span class="icon">
                                    <i class="fas fa-paper-plane has-text-info"></i>
                                </span>
                                <span class="has-text-info">ส่ง</span>
                            </a>
                        </div>
                    </div>
                </td>
            </tr>
            '''.format(coordinator.note, url_for('comp_tracker.edit_note', coordinator_id=coordinator.id),
                       url_for('comp_tracker.submit_note', coordinator_id=coordinator.id))
    resp = make_response(template)
    return resp


@complaint_tracker.route('/issue/record/coordinator/note/note-submission/<int:coordinator_id>',
                         methods=['GET', 'PATCH'])
@login_required
def submit_note(coordinator_id):
    coordinator = ComplaintCoordinator.query.get(coordinator_id)
    if request.method == 'PATCH':
        coordinator.submitted_datetime = arrow.now('Asia/Bangkok').datetime
        flash('ปิดรายงานผลการดำเนินงานเรียบร้อย', 'success')
        db.session.add(coordinator)
        db.session.commit()
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@complaint_tracker.route('/issue/complainant/email-sending/<int:record_id>', methods=['GET', 'POST'])
@login_required
def send_email(record_id):
    record = ComplaintRecord.query.get(record_id)
    form = request.form
    if request.method == 'POST':
        title = f'''{form.get('title')}'''
        message = f'''{form.get('detail')}'''
        send_mail([record.email], title, message)
        flash('ส่งอีเมลเรียบร้อย', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('complaint_tracker/modal/send_email_modal.html', record_id=record_id)


@complaint_tracker.route('/issue/report/assignee/add/<int:record_id>/<int:assignee_id>',
                         methods=['GET', 'POST', 'DELETE'])
@login_required
def edit_assignee(record_id, assignee_id):
    if request.method == 'POST':
        assignees = ComplaintAssignee(assignee_id=assignee_id, record_id=record_id,
                                      assignee_datetime=arrow.now('Asia/Bangkok').datetime)
        db.session.add(assignees)
        db.session.commit()
        flash('มอบหมายงานสำเร็จ', 'success')
        complaint_link = url_for('comp_tracker.edit_record_admin', record_id=record_id, _external=True, _scheme='https')
        msg = ('ท่านได้รับมอบหมายให้ดำเนินการแก้ไขปัญหา'
               '\nกรุณาคลิกที่ Link เพื่อดำเนินการ {}'.format(complaint_link))
        if not current_app.debug:
            try:
                line_bot_api.push_message(to=assignees.assignee.admin.line_id, messages=TextSendMessage(text=msg))
            except LineBotApiError:
                pass
    elif request.method == 'DELETE':
        assignee = ComplaintAssignee.query.filter_by(assignee_id=assignee_id, record_id=record_id).first()
        db.session.delete(assignee)
        db.session.commit()
        flash('ยกเลิกการมอบหมายงานสำเร็จ', 'success')
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@complaint_tracker.route('/issue/report/hendler/add/<int:record_id>', methods=['GET', 'POST'])
@login_required
def add_handler(record_id):
    ComplaintHandler.query.filter_by(record_id=record_id).delete()
    for h_id in request.form.getlist('handlers'):
        handlers = ComplaintHandler(record_id=record_id, handler_id=h_id, handled_at=arrow.now('Asia/Bangkok').datetime)
        db.session.add(handlers)
        db.session.commit()
    flash('บันทึกผู้ดำเนินการเรียบร้อยแล้ว', 'success')
    record = ComplaintRecord.query.get(record_id)
    return render_template('complaint_tracker/handler_template.html', record=record)


@complaint_tracker.route('/complaint/user/view/<int:record_id>', methods=['GET'])
@login_required
def view_record_complaint(record_id):
    statuses = ComplaintStatus.query.all()
    record = ComplaintRecord.query.get(record_id)
    if record.url and len(record.url) > 0:
        file_url = generate_url(record.url)
    else:
        file_url = None
    return render_template('complaint_tracker/view_record_complaint.html', record=record, file_url=file_url,
                           statuses=statuses)


@complaint_tracker.route('/complaint/report/view/<int:record_id>')
@login_required
def view_performance_report(record_id):
    record = ComplaintRecord.query.get(record_id)
    return render_template('complaint_tracker/modal/view_performance_report_modal.html', record=record)


@complaint_tracker.route('/complaint/user/cancel/<int:record_id>', methods=['POST'])
@login_required
def cancel_complaint(record_id):
    status = ComplaintStatus.query.filter_by(code='cancelled').first()
    record = ComplaintRecord.query.get(record_id)
    record.status = status
    record.closed_at = arrow.now('Asia/Bangkok').datetime
    db.session.add(record)
    db.session.commit()
    if record.status_id:
        rec = ComplaintRecordStatusAssociation(status_id=record.status_id, record_id=record_id,
                                               updated_at=arrow.now('Asia/Bangkok').datetime)
        db.session.add(rec)
        db.session.commit()
    flash('ยกเลิกรายการแจ้งปัญหาสำเร็จ', 'success')
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@complaint_tracker.route('/admin/complaint/index')
@admin_permission.require()
@login_required
def admin_record_complaint_index():
    menu = request.args.get('menu')
    topics = ComplaintTopic.query.all()
    grouped_topics = defaultdict(list)
    for topic in topics:
        if topic.code != 'misc':
            grouped_topics[topic.category].append(topic)
    return render_template('complaint_tracker/admin_record_complaint_index.html', menu=menu,
                           grouped_topics=grouped_topics)


@complaint_tracker.route('/api/records')
@login_required
def get_records():
    menu = request.args.get('menu')
    query = ComplaintRecord.query.filter(
        ComplaintRecord.topic.has(code=menu)) if menu != 'all' else ComplaintRecord.query
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ComplaintRecord.desc.contains(search))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        tags = []
        if item.tags:
            for tag in item.tags:
                tag_html = f'''
                        <span class ="tag is-rounded is-info is-light mb-1" >
                            {tag.tag}
                        </span><br>'''
                tags.append(tag_html)
        else:
            tag_html = ''
        item_data['tag'] = ''.join(tags) if tags else ''
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': records_total,
                    'draw': request.args.get('draw', type=int),
                    })


@complaint_tracker.route('/admin/complaint/view/<int:record_id>')
@login_required
def view_record_complaint_for_admin(record_id):
    menu = request.args.get('menu')
    statuses = ComplaintStatus.query.all()
    record = ComplaintRecord.query.get(record_id)
    if record.url and len(record.url) > 0:
        file_url = generate_url(record.url)
    else:
        file_url = None
    return render_template('complaint_tracker/view_record_complaint_for_admin.html', file_url=file_url,
                           record=record, menu=menu, statuses=statuses)


@complaint_tracker.route('/add-procurement-number/complaint/<code>', methods=['GET', 'POST'])
def add_procurement_number(code):
    cat = request.args.get('cat')
    tab = request.args.get('tab')
    record_id = request.args.get('record_id', type=int)
    topic = ComplaintTopic.query.filter_by(code=code).first()
    if request.method == 'POST':
        pro_number = request.form.get('pro_number')
        if cat and cat == 'admin':
            return redirect(url_for('comp_tracker.edit_record_admin', tab=tab, record_id=record_id,
                                    pro_number=pro_number))
        else:
            return redirect(url_for('comp_tracker.new_record', topic_id=topic.id, pro_number=pro_number))
    return render_template('complaint_tracker/add_procurement_number.html', code=code, topic_id=topic.id,
                           cat=cat, tab=tab, record_id=record_id)


@complaint_tracker.route('/admin/record-complaint-summary')
@login_required
def admin_record_complaint_summary():
    menu = request.args.get('menu')
    topics = ComplaintTopic.query.filter(ComplaintTopic.code != 'misc')
    code = []
    topic = []
    for t in topics:
        if menu == t.code:
            topic.append(t.topic)
            code.append(t.code)
    return render_template('complaint_tracker/admin_record_complaint_summary.html', menu=menu, code=' '.join(code),
                           topic=' '.join(topic), topics=topics,
                           can_send_summary=current_user.is_authenticated and admin_permission.can())


# External scheduler endpoint: must remain accessible to token-authenticated
# background jobs and should not be protected with @login_required.
@complaint_tracker.route('/admin/email-unfinished-summary', methods=['GET', 'POST'])
def email_unfinished_summary():
    current_app.logger.info(
        'complaint_email_unfinished_summary_start method=%s remote_addr=%s',
        request.method,
        request.remote_addr,
    )
    scheduler_request = _is_valid_summary_scheduler_request()
    if not scheduler_request:
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if not admin_permission.can():
            abort(403)

    recipients = _get_high_level_admin_recipients()
    recipient_groups = _group_high_level_admin_recipients_by_topic_scope(recipients)
    should_send = _request_flag('send')
    dry_run = _request_flag('dry_run')
    current_app.logger.info(
        'complaint_email_unfinished_summary_checkpoint scheduler_request=%s recipients=%s recipient_groups=%s should_send=%s dry_run=%s',
        scheduler_request,
        len(recipients),
        len(recipient_groups),
        should_send,
        dry_run,
    )

    snapshot_cache = {}

    if dry_run:
        packages = [
            _build_recipient_summary_package(recipient_group, snapshot_cache=snapshot_cache)
            for recipient_group in recipient_groups
        ]
        response = make_response(_render_dry_run_html(packages, should_send))
        response.mimetype = 'text/html'
        return response

    if not should_send:
        response = make_response(
            'Email was not sent. Add send=true to trigger delivery, or dry_run=true to preview recipients.\n',
            400
        )
        response.mimetype = 'text/plain'
        return response

    if not recipient_groups:
        message = 'ไม่พบอีเมลของผู้บริหารระดับสูงสำหรับส่งสรุป'
        if request.method == 'POST':
            flash(message, 'danger')
            return redirect(request.referrer or url_for('comp_tracker.admin_record_complaint_summary'))
        response = make_response(message + '\n', 404)
        response.mimetype = 'text/plain'
        return response

    sent_group_count = 0
    sent_recipient_count = 0
    for recipient_group in recipient_groups:
        package = _build_recipient_summary_package(recipient_group, snapshot_cache=snapshot_cache)
        recipient_emails = recipient_group.get('emails') or [recipient_group['email']]
        try:
            current_app.logger.info(
                'complaint_email_send_start recipient_group=%s recipient_count=%s',
                recipient_group['email'],
                len(recipient_emails),
            )
            send_mail(
                recipient_emails,
                package['subject'],
                package['message'],
                html=_render_summary_email_html(package),
            )
            sent_group_count += 1
            sent_recipient_count += len(recipient_emails)
        except Exception:
            current_app.logger.exception('complaint_email_send_failed recipient_group=%s', recipient_group['email'])
            raise
    success_message = f'ส่งอีเมลสรุปให้ผู้บริหารระดับสูงแล้ว {len(recipients)} ราย'
    current_app.logger.info(
        'complaint_email_unfinished_summary_end sent_group_count=%s sent_recipient_count=%s total_recipients=%s',
        sent_group_count,
        sent_recipient_count,
        len(recipients),
    )
    if request.method == 'GET':
        response = make_response(success_message + '\n')
        response.mimetype = 'text/plain'
        return response
    flash(success_message, 'success')

    if request.headers.get('HX-Request'):
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return redirect(request.referrer or url_for('comp_tracker.admin_record_complaint_summary'))


# External scheduler endpoint: must remain accessible to token-authenticated
# background jobs and should not be protected with @login_required.
@complaint_tracker.route('/admin/line-remind-no-status-today', methods=['GET', 'POST'])
def line_remind_no_status_today():
    current_app.logger.info(
        'complaint_line_reminder_start method=%s remote_addr=%s',
        request.method,
        request.remote_addr,
    )
    scheduler_request = _is_valid_summary_scheduler_request()
    if not scheduler_request:
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if not admin_permission.can():
            abort(403)

    recipient_stats = _get_low_level_line_recipient_stats()
    global_snapshot = _build_today_no_status_records_snapshot()
    packages = []
    matched_packages = []
    snapshot_cache = {}
    for recipient in _get_low_level_line_recipients():
        package = _build_low_level_line_reminder_package(recipient, snapshot_cache=snapshot_cache)
        packages.append(package)
        if package['snapshot']['total_records'] > 0 and package['message']:
            matched_packages.append(package)

    should_send = _request_flag('send')
    dry_run = _request_flag('dry_run', default=(request.method == 'GET' and not should_send))
    current_app.logger.info(
        'complaint_line_reminder_checkpoint scheduler_request=%s recipients=%s matched_recipients=%s should_send=%s dry_run=%s',
        scheduler_request,
        len(packages),
        len(matched_packages),
        should_send,
        dry_run,
    )

    if dry_run:
        return _render_line_reminder_dry_run_html(
            packages,
            matched_packages,
            should_send,
            recipient_stats,
            global_snapshot,
        )

    if not should_send:
        response = make_response(
            'Line reminder was not sent. Add send=true to trigger delivery, or dry_run=true to preview recipients.\n',
            400
        )
        response.mimetype = 'text/plain'
        return response

    if not matched_packages:
        message = 'ไม่พบผู้รับหรือไม่พบเรื่องที่เข้าเงื่อนไขสำหรับส่ง Line reminder'
        if request.method == 'POST':
            flash(message, 'warning')
            return redirect(request.referrer or url_for('comp_tracker.admin_record_complaint_summary', menu='all'))
        response = make_response(message + '\n', 404)
        response.mimetype = 'text/plain'
        return response

    sent_count = 0
    failed_count = 0
    for package in matched_packages:
        try:
            current_app.logger.info(
                'complaint_line_reminder_push_start line_id=%s',
                _mask_line_id(package['recipient']['line_id']),
            )
            line_bot_api.push_message(
                to=package['recipient']['line_id'],
                messages=TextSendMessage(text=package['message'])
            )
            sent_count += 1
        except LineBotApiError:
            failed_count += 1
            current_app.logger.exception(
                'Failed to send no-status-today reminder to line_id=%s',
                _mask_line_id(package['recipient']['line_id'])
            )

    success_message = f'ส่ง Line reminder แล้ว {sent_count} ราย'
    if failed_count:
        success_message += f' และส่งไม่สำเร็จ {failed_count} ราย'

    if request.method == 'GET':
        response = make_response(success_message + '\n')
        response.mimetype = 'text/plain'
        return response

    flash(success_message, 'success' if failed_count == 0 else 'warning')
    current_app.logger.info(
        'complaint_line_reminder_end sent_count=%s failed_count=%s',
        sent_count,
        failed_count,
    )
    if request.headers.get('HX-Request'):
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return redirect(request.referrer or url_for('comp_tracker.admin_record_complaint_summary', menu='all'))


@complaint_tracker.route('/repair/index')
@login_required
def repair_index():
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    org = current_user.personal_info.org
    query = (ComplaintRepair.query.join(ComplaintRepair.owner).join(StaffAccount.personal_info)
    .filter(
        or_(ComplaintRepair.owner_id == current_user.id,
            StaffPersonalInfo.org == org)
    ))
    if tab == 'waiting_process':
        repairs = query.filter(ComplaintRepair.is_print == False)
    elif tab == 'waiting_approval':
        repairs = (query.join(ComplaintRepair.record)
                            .outerjoin(ComplaintRecord.status)
                            .filter(or_(
                                        ComplaintRecord.status_id == None,
                                        and_(
                                            ComplaintStatus.code != 'cancelled',
                                            ComplaintStatus.code != 'completed'
                                        )
                                    ),
                                    ComplaintRepair.is_print == True
                                    )
                            )
    elif tab == 'completed':
        repairs = (query.join(ComplaintRepair.record).join(ComplaintRecord.status)
                            .filter(or_(ComplaintStatus.code == 'cancelled',
                                        ComplaintStatus.code == 'completed'),
                                    ComplaintRepair.is_print == True)
                            )
    else:
        repairs = query
    new_record_count = query.filter(ComplaintRepair.is_print == False).count()
    waiting_record_count = (query.join(ComplaintRepair.record)
                            .outerjoin(ComplaintRecord.status)
                            .filter(or_(
                                        ComplaintRecord.status_id == None,
                                        and_(
                                            ComplaintStatus.code != 'cancelled',
                                            ComplaintStatus.code != 'completed'
                                        )
                                    ),
                                    ComplaintRepair.is_print == True
                                    )
                            ).count()
    return render_template('complaint_tracker/repair_index.html', tab=tab, menu=menu,
                           new_record_count=new_record_count, waiting_record_count=waiting_record_count,
                           repairs=repairs)


@complaint_tracker.route('/admin/repair/add/<int:record_id>', methods=['GET', 'POST'])
@login_required
def create_repair(record_id):
    record = ComplaintRecord.query.get(record_id)
    org_name = record.complainant.personal_info.org.name if record.complainant else current_user.personal_info.org.name
    org = Org.query.filter_by(name=org_name).first()
    if ((org.parent and org.parent.parent and org.parent.parent.name == 'สำนักงานคณบดี') or
            (org.parent and org.parent.name == 'สำนักงานคณบดี') or (org.name == 'สำนักงานคณบดี')):
        staff = StaffAccount.query.filter_by(email=current_user.personal_info.org.head).first()
        owner_id = staff.id
    else:
        user = record.complainant or current_user
        owner_id = user.id
    repair = ComplaintRepair(record_id=record_id, created_at=arrow.now('Asia/Bangkok').datetime, owner_id=owner_id)
    db.session.add(repair)
    db.session.commit()
    if repair.get_other_org == True:
        scheme = 'http' if current_app.debug else 'https'
        link = url_for("comp_tracker.repair_index", tab='new', _external=True, _scheme=scheme)
        title = f'''แจ้งออกใบแจ้งซ่อมรายการเลขที่ {repair.record.id}'''
        message = f'''เจ้าหน้าที่ได้ดำเนินการออกใบแจ้งซ่อมสำหรับรายการเลขที่ {repair.record.id} เรียบร้อยแล้ว กรุณาดำเนินการในขั้นตอนถัดไปตามกระบวนการที่เกี่ยวข้อง\n'''
        message += f'''ท่านสามารถดำเนินการพิมพ์เอกสารได้ที่ลิงก์ด้านล่าง\n{link}\n\n'''
        message += f'''ขอบคุณค่ะ\nระบบรับแจ้งปัญหาหรือข้อร้องเรียน\nคณะเทคนิคการแพทย์'''
        if repair.record.complainant:
            msg = (
                f'เจ้าหน้าที่ได้ดำเนินการออกใบแจ้งซ่อมสำหรับรายการเลขที่ {repair.record.id} เรียบร้อยแล้ว\n\n'
                f'ขอบคุณค่ะ\nระบบรับแจ้งปัญหาหรือข้อร้องเรียน\nคณะเทคนิคการแพทย์')
            message_for_complainant = f'''เจ้าหน้าที่ได้ดำเนินการออกใบแจ้งซ่อมสำหรับรายการเลขที่ {repair.record.id} เรียบร้อยแล้ว\n\n'''
            message_for_complainant += f'''ขอบคุณค่ะ\nระบบรับแจ้งปัญหาหรือข้อร้องเรียน\nคณะเทคนิคการแพทย์'''

            send_mail([repair.record.complainant.email + '@mahidol.ac.th'], title,
                          message_for_complainant)
            if not current_app.debug:
                try:
                    line_bot_api.push_message(to=repair.record.complainant.line_id,
                                                messages=TextSendMessage(text=msg))
                except LineBotApiError:
                    pass
            else:
                print('msg :', msg, 'line :', repair.record.complainant.line_id)
        if repair.record.complainant.personal_info.org.secretary_staff:
            send_mail(
                [secretary.email + '@mahidol.ac.th' for secretary in repair.record.complainant.personal_info.org.secretary_staff],
                title, message)
    flash('ออกใบแจ้งซ่อมสำเร็จ', 'success')
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


def generate_repair_pdf(repair):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer,
                            pagesize=A4,
                            rightMargin=45,
                            leftMargin=50,
                            topMargin=30,
                            bottomMargin=30
                            )

    data = []

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=14,
        leading=25,
        alignment=TA_LEFT,
    )

    detail_style = ParagraphStyle(
        'DetailStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=16,
        leading=25,
        alignment=TA_LEFT,
    )

    received_at = None

    for record in repair.record.record_status_updates:
        if record.status.no == 1:
            received_at = arrow.get(record.updated_at.astimezone(localtz)).format(fmt='DD/MM/YYYY', locale='th-th')
        else:
            received_at = None

    code = f"เลขที่&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{repair.record_id}<br/>วันที่รับเรื่อง {received_at}"

    code_table = Table(
        [[Paragraph(code, style=header_style)]],
        colWidths=[123],
        rowHeights=[62]
    )
    code_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 13),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10)
    ]))
    code_table.hAlign = 'RIGHT'

    title = Paragraph(
        '<para align=center><font size=18>ใบส่งซ่อมและการให้บริการ</font></para>',
        style=style_sheet['ThaiStyleBold']
    )

    if repair.record.complainant:
        org_name = repair.record.complainant.personal_info.org.name
        complainant = repair.record.complainant.fullname
        phone_number = repair.record.complainant.personal_info.org.phone_number or ''
        head = repair.get_head_org
    else:
        org_name = current_user.personal_info.org.name
        complainant = current_user.fullname
        phone_number = current_user.personal_info.org.phone_number or ''
        head = repair.get_head_org

    created_at = arrow.get(repair.record.created_at.astimezone(localtz)).format(fmt='DD/MM/YYYY', locale='th-th')
    erp_code = ''
    procurement_name = ''
    location = ''
    floor = ''
    room = ''

    if repair.record.procurements:
        for procurement in repair.record.procurements:
            erp_code = procurement.erp_code
            procurement_name = procurement.name
            if procurement.records:
                for record in procurement.records:
                    location = record.location.location or ''
                    floor = record.location.floor or ''
                    room = record.location.number or ''
            else:
                location = ''
                floor = ''
                room = ''
    else:
        erp_code = ''
        procurement_name = ''
        location = ''
        floor = ''
        room = ''

    detail_table =  Table([
        [
            Paragraph(f'ภาควิชา/หน่วยงาน&nbsp;&nbsp;{org_name}', style=detail_style),
            Paragraph(f'วันที่แจ้ง&nbsp;&nbsp;{created_at}', style=detail_style)
        ],
        [
            Paragraph(f'ผู้แจ้ง&nbsp;&nbsp;{complainant}', style=detail_style),
            Paragraph(f'โทร&nbsp;&nbsp;{phone_number}', style=detail_style)
        ],
    ], colWidths=[240, 260])
    detail_table.hAlign = 'LEFT'

    procurement_table = Table([
        [
            Paragraph(f'หมายเลขครุภัณฑ์&nbsp;&nbsp;{erp_code}', style=detail_style)
        ],
        [
            Paragraph(f'ชื่อเครื่อง/บริการ&nbsp;&nbsp;{procurement_name}', style=detail_style)
        ],
    ], colWidths=[500])

    procurement_table.hAlign = 'LEFT'

    location_table = Table([
        [
            Paragraph(f'สถานที่ตั้ง&nbsp;&nbsp;{location}', style=detail_style),
            Paragraph(f'ชั้น&nbsp;&nbsp;{floor}', style=detail_style),
            Paragraph(f'ห้อง&nbsp;&nbsp;{room}', style=detail_style)
        ],
    ], colWidths=[220, 120, 160])
    location_table.hAlign = 'LEFT'

    description_table =  Table([
        [
            Paragraph(f'รายละเอียดการแจ้ง&nbsp;&nbsp;{repair.record.desc}', style=detail_style),
        ]
    ], colWidths=[500])
    description_table.hAlign = 'LEFT'

    head_org_table = Table([
        [
            Paragraph(f'หัวหน้าภาควิชา/หน่วยงาน&nbsp;&nbsp;{head}', style=detail_style),
            Paragraph(f'วันที่&nbsp;&nbsp;.............................................................', style=detail_style)
        ],
    ], colWidths=[250, 250])
    head_org_table.hAlign = 'CENTER'

    comment = ''
    if repair.record.comments:
        for index, c in enumerate(repair.record.comments):
            if len(repair.record.comments) > 1:
                comment += (f'- {c.review_comment}<br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
                            f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;')
            else:
                comment = c.review_comment
    else:
        comment = ''

    report = ''
    if repair.record.reports:
        report_date = arrow.get(repair.record.reports[-1].report_datetime.astimezone(localtz)).format(fmt='DD/MM/YYYY', locale='th-th')
        for index, r in enumerate(repair.record.reports):
            if len(repair.record.reports) > 1:
                report += (f'- {r.report_comment}<br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
                           f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;')
            else:
                report = r.report_comment
    else:
        report_date = ''
        report = ''

    survey_table = Table([
        [
            Paragraph(f'การตรวจสอบ&nbsp;&nbsp;{comment}', style=detail_style),
        ]
    ], colWidths=[500])
    survey_table.hAlign = 'LEFT'

    report_table = Table([
        [
            Paragraph(f'รายละเอียดการซ่อม&nbsp;&nbsp;{report}', style=detail_style),
        ]
    ], colWidths=[500])
    report_table.hAlign = 'LEFT'

    report_date_table = Table([
        [
            Paragraph(f'วันที่ซ่อม&nbsp;&nbsp;{report_date}', style=detail_style),
        ]
    ], colWidths=[500])
    report_date_table.hAlign = 'LEFT'

    staff = StaffAccount.query.filter_by(email=current_user.personal_info.org.head).first()
    head_repair_table =  Table([
        [
            Paragraph(f'ลงชื่อ&nbsp;&nbsp;{staff.fullname} (หัวหน้า{staff.personal_info.org.name})', style=detail_style),
        ]
    ], colWidths=[500])
    head_repair_table.hAlign = 'LEFT'

    data.append(code_table)
    data.append(KeepTogether(Spacer(20, 20)))
    data.append(KeepTogether(title))
    data.append(KeepTogether(Spacer(24, 24)))
    data.append(detail_table)
    data.append(KeepTogether(Spacer(1, 1)))
    data.append(procurement_table)
    data.append(KeepTogether(Spacer(1, 1)))
    data.append(location_table)
    data.append(KeepTogether(Spacer(1, 1)))
    data.append(description_table)
    data.append(KeepTogether(Spacer(37, 37)))
    data.append(head_org_table)
    data.append((KeepTogether(Spacer(15, 15))))
    data.append(HRFlowable(width="100%", color=colors.black, thickness=1))
    data.append((KeepTogether(Spacer(15, 15))))
    data.append(survey_table)
    data.append((KeepTogether(Spacer(40, 40))))
    data.append(report_table)
    data.append((KeepTogether(Spacer(50, 50))))
    data.append(report_date_table)
    data.append(KeepTogether(Spacer(1, 1)))
    data.append(head_repair_table)
    doc.build(data, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


@complaint_tracker.route('/admin/repair/pdf/<int:repair_id>', methods=['GET'])
@login_required
def export_repair_pdf(repair_id):
    repair = ComplaintRepair.query.get(repair_id)
    buffer = generate_repair_pdf(repair)
    if not repair.reviewed_at:
        repair.is_print = True
        repair.reviewed_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(repair)
        db.session.commit()
    return send_file(buffer, download_name=f'Repair Form {repair.record_id}.pdf', as_attachment=True)


@complaint_tracker.route('/repair_approval/index')
@login_required
def repair_approval_index():
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    org = current_user.personal_info.org
    query = (ComplaintRepairApproval.query.join(ComplaintRepairApproval.owner).join(StaffAccount.personal_info)
    .filter(
        or_(ComplaintRepairApproval.owner_id == current_user.id,
            StaffPersonalInfo.org == org)
    ))
    if tab == 'waiting_process':
        repair_approvals = query.filter(ComplaintRepairApproval.is_print == False)
    elif tab == 'waiting_approval':
        repair_approvals = (query.join(ComplaintRepairApproval.record)
                            .outerjoin(ComplaintRecord.status)
                            .filter(or_(ComplaintRecord.status_id == None,
                                        and_(
                                            ComplaintStatus.code != 'cancelled',
                                            ComplaintStatus.code != 'completed'
                                        )
                                    ),
                                    ComplaintRepairApproval.is_print == True,
                                    ComplaintRepairApproval.cancelled_at == None
                                    )
                            )
    elif tab == 'completed':
        repair_approvals = (query.join(ComplaintRepairApproval.record).join(ComplaintRecord.status)
                            .filter(or_(ComplaintStatus.code == 'cancelled',
                                        ComplaintStatus.code == 'completed'),
                                    ComplaintRepairApproval.is_print == True,
                                    ComplaintRepairApproval.cancelled_at == None)
                            )
    elif tab == 'cancelled':
        repair_approvals = query.filter(ComplaintRepairApproval.cancelled_at != None)
    else:
        repair_approvals = query
    new_record_count = query.filter(ComplaintRepairApproval.is_print == False).count()
    waiting_record_count = (query.join(ComplaintRepairApproval.record)
                            .outerjoin(ComplaintRecord.status)
                            .filter(or_(ComplaintRecord.status_id == None,
                                        and_(
                                            ComplaintStatus.code != 'cancelled',
                                            ComplaintStatus.code != 'completed'
                                        )
                                    ),
                                    ComplaintRepairApproval.is_print == True,
                                    ComplaintRepairApproval.cancelled_at == None
                                    )
                            ).count()
    return render_template('complaint_tracker/repair_approval_index.html', tab=tab, menu=menu,
                           new_record_count=new_record_count, waiting_record_count=waiting_record_count,
                           repair_approvals=repair_approvals)


@complaint_tracker.route('/admin/repair-approval/add/<int:record_id>', methods=['GET', 'POST'])
@complaint_tracker.route('/admin/repair-approval/edit/<int:record_id>/<int:repair_approval_id>', methods=['GET', 'POST'])
@login_required
def create_repair_approval(record_id, repair_approval_id=None):
    requester_id = None
    approver_id = None
    record = ComplaintRecord.query.get(record_id)
    has_procurement = True if record.procurements else False
    requester = record.complainant if record.complainant else current_user
    owner_id = requester.id

    if repair_approval_id:
        rep_approval = ComplaintRepairApproval.query.get(repair_approval_id)
        form = ComplaintRepairApprovalForm(obj=rep_approval)
    else:
        form = ComplaintRepairApprovalForm()

    if record.procurements:
        for procurement in record.procurements:
            cost_center= procurement.cost_center[:-1]
            cost_center_auth = StaffCostCenterAuthority.query.filter(StaffCostCenterAuthority.cost_center == cost_center).first()
            org = Org.query.filter_by(name=requester.personal_info.org.name).first()
            if not form.item.data:
                form.item.data = f'เลขครุภัณฑ์ {procurement.procurement_no} {procurement.name}'
            if cost_center_auth:
                if ((org.parent and org.parent.parent and org.parent.parent.name == 'สำนักงานคณบดี') or
                        (org.parent and org.parent.name == 'สำนักงานคณบดี') or (org.name == 'สำนักงานคณบดี')):
                    owner_id = cost_center_auth.secretary_id
                    requester_id = cost_center_auth.secretary_id
                    approver_id = cost_center_auth.head_id
                    form.name.data = cost_center_auth.secretary.fullname
                    form.position.data = f"หัวหน้า{cost_center_auth.secretary.personal_info.org.name}"
                    get_organization(org=cost_center_auth.secretary.personal_info.org, form=form)
                else:
                    owner_id = requester.id
                    requester_id = requester.id
                    approver_id = cost_center_auth.head_id
                    form.name.data = requester.fullname
                    form.position.data = requester.personal_info.position
                    get_organization(org=requester.personal_info.org, form=form)

    if form.validate_on_submit():
        if not repair_approval_id:
            rep_approval = ComplaintRepairApproval()
        form.populate_obj(rep_approval)

        if not form.repair_type.data:
            flash('กรุณาเลือกประเภทใบอนุมัติหลักการซ่อม', 'danger')
            return render_template('complaint_tracker/repair_approval_form.html', form=form,
                                   record_id=record_id, repair_approval_id=repair_approval_id)
        elif form.repair_type.data == 'ไม่เร่งด่วน (ซื้อ/จ้าง)' and not form.principle_approval_type.data:
            flash('กรุณาเลือกประเภทการขออนุมัติ', 'danger')
            return render_template('complaint_tracker/repair_approval_form.html', form=form,
                                   record_id=record_id, repair_approval_id=repair_approval_id)

        rep_approval.receipt_date = arrow.get(form.receipt_date.data,
                                              'Asia/Bangkok').date() if form.receipt_date.data else None
        if not repair_approval_id:
            rep_approval.record_id = record_id
            rep_approval.created_at = arrow.now('Asia/Bangkok').datetime
            rep_approval.creator_id = current_user.id
            rep_approval.requester_id = requester_id
            rep_approval.approver_id = approver_id
            rep_approval.owner_id = owner_id
        else:
            rep_approval.updated_at = arrow.now('Asia/Bangkok').datetime

        if form.repair_type.data == 'เร่งด่วน':
            rep_approval.principle_approval_type = None
            rep_approval.purpose = None
        else:
            rep_approval.book_number = None
            rep_approval.receipt_number = None
            rep_approval.receipt_date = None
            rep_approval.supplier = None
            rep_approval.loan_no = None
        rep_approval.is_print = False
        rep_approval.reviewed_at = None
        db.session.add(rep_approval)
        db.session.commit()
            # if rep_approval.get_other_org == True:
            #     scheme = 'http' if current_app.debug else 'https'
            #     link = url_for("comp_tracker.repair_approval_index", tab='new', _external=True, _scheme=scheme)
            #     if repair_approval_id:
            #         title = f'''แจ้งแก้ไขใบอนุมัติหลักการซ่อม {rep_approval.item}'''
            #         message = f'''เจ้าหน้าที่ได้ดำเนินการแก้ไขข้อมูลใบอนุมัติหลักการซ่อมสำหรับรายการ {rep_approval.item} เรียบร้อยแล้ว กรุณาดำเนินการในขั้นตอนถัดไปตามกระบวนการที่เกี่ยวข้อง\n'''
            #         message += f'''ท่านสามารถดำเนินการพิมพ์เอกสารได้ที่ลิงก์ด้านล่าง\n{link}\n\n'''
            #         message += f'''ขอบคุณค่ะ\nระบบรับแจ้งปัญหาหรือข้อร้องเรียน\nคณะเทคนิคการแพทย์'''
            #     else:
            #         title = f'''แจ้งออกใบอนุมัติหลักการซ่อม {rep_approval.item}'''
            #         message = f'''เจ้าหน้าที่ได้ดำเนินการออกใบอนุมัติหลักการซ่อมสำหรับรายการ {rep_approval.item} เรียบร้อยแล้ว กรุณาดำเนินการในขั้นตอนถัดไปตามกระบวนการที่เกี่ยวข้อง\n'''
            #         message += f'''ท่านสามารถดำเนินการพิมพ์เอกสารได้ที่ลิงก์ด้านล่าง\n{link}\n\n'''
            #         message += f'''ขอบคุณค่ะ\nระบบรับแจ้งปัญหาหรือข้อร้องเรียน\nคณะเทคนิคการแพทย์'''
            #         if rep_approval.record.complainant:
            #             msg = (f'เจ้าหน้าที่ได้ดำเนินการออกใบอนุมัติหลักการซ่อมสำหรับรายการ {rep_approval.item} เรียบร้อยแล้ว\n\n'
            #                    f'ขอบคุณค่ะ\nระบบรับแจ้งปัญหาหรือข้อร้องเรียน\nคณะเทคนิคการแพทย์')
            #             message_for_complainant = f'''เจ้าหน้าที่ได้ดำเนินการออกใบอนุมัติหลักการซ่อมสำหรับรายการ {rep_approval.item} เรียบร้อยแล้ว\n\n'''
            #             message_for_complainant += f'''ขอบคุณค่ะ\nระบบรับแจ้งปัญหาหรือข้อร้องเรียน\nคณะเทคนิคการแพทย์'''
            #
            #             send_mail([rep_approval.record.complainant.email + '@mahidol.ac.th'], title,
            #                       message_for_complainant)
            #             if not current_app.debug:
            #                 try:
            #                     line_bot_api.push_message(to=rep_approval.record.complainant.line_id, messages=TextSendMessage(text=msg))
            #                 except LineBotApiError:
            #                     pass
            #             else:
            #                 print('msg :', msg, 'line :', rep_approval.record.complainant.line_id)
            #     if rep_approval.owner.personal_info.org.secretary_staff:
            #         send_mail([secretary.email + '@mahidol.ac.th' for secretary in rep_approval.owner.personal_info.org.secretary_staff],
            #                   title, message)
        flash('บันทึกข้อมูลสำเร็จ', 'success')
        return redirect(url_for('comp_tracker.edit_record_admin', record_id=record_id))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('complaint_tracker/repair_approval_form.html', form=form, record_id=record_id,
                           repair_approval_id=repair_approval_id, record=record, has_procurement=has_procurement)


@complaint_tracker.route('/repair-approval/edit/<int:repair_approval_id>', methods=['GET', 'POST'])
@login_required
def edit_repair_approval(repair_approval_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    temp = request.args.get('temp')
    repair_approval = ComplaintRepairApproval.query.get(repair_approval_id)
    form = ComplaintRepairApprovalForm(obj=repair_approval)
    if form.validate_on_submit():
        form.populate_obj(repair_approval)
        if (form.cost_center.data and form.io_code.data and form.product_code.data and form.approver.data and
            form.requester.data):
            repair_approval.is_print = True
            repair_approval.updated_at = arrow.now('Asia/Bangkok').datetime
            db.session.add(repair_approval)
            db.session.commit()
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
            if repair_approval.repair_type == 'เร่งด่วน':
                if temp == 'index':
                    return redirect(url_for('comp_tracker.repair_approval_index', tab=tab, menu=menu))
                else:
                    return redirect(url_for('comp_tracker.edit_record_admin', record_id=repair_approval.record_id,
                                            tab=tab))
            else:
                return redirect(url_for('comp_tracker.edit_committee', repair_approval_id=repair_approval.id,
                                        temp=temp, tab=tab, menu=menu, repair_approval=repair_approval))
        else:
            flash('กรุณากรอกข้อมูลให้ครบถ้วน', 'danger')
            return render_template('complaint_tracker/edit_repair_approval.html',
                                   repair_approval_id=repair_approval_id, form=form, record_id=repair_approval.record_id,
                                   tamp=temp, tab=tab, menu=menu, repair_approval=repair_approval)
    return render_template('complaint_tracker/edit_repair_approval.html',
                           repair_approval_id=repair_approval_id, form=form, record_id=repair_approval.record_id, temp=temp,
                           tab=tab, menu=menu, repair_approval=repair_approval)


@complaint_tracker.route('/admin/repair-approval/committee/add/<int:repair_approval_id>', methods=['GET', 'POST'])
@login_required
def edit_committee(repair_approval_id):
    tab = request.args.get('tab')
    menu = request.args.get('menu')
    temp = request.args.get('temp')
    rep_approval = ComplaintRepairApproval.query.get(repair_approval_id)
    committees = ComplaintCommittee.query.filter_by(repair_approval_id=repair_approval_id).all()
    if rep_approval.price > 500000:
        min_entries = 9
        default_positions = ['ประธาน', 'กรรมการ', 'กรรมการ', 'ประธาน', 'กรรมการ', 'กรรมการ', 'ประธาน', 'กรรมการ',
                             'กรรมการ']
    elif rep_approval.price > 30000 and rep_approval.price <= 500000:
        min_entries = 3
        default_positions = ['ประธาน', 'กรรมการ', 'กรรมการ']
    else:
        min_entries = 1
        default_positions = ['ผู้ตรวจรับพัสดุ']
    form = ComplaintCommitteeGroupForm(obj=committees)
    if request.method == 'GET':
        current_count = len(committees)
        if committees:
            for committee in committees:
                c_form = form.committees.append_entry()
                c_form.form.id.data = committee.id
                c_form.form.staff.data = committee.staff
                c_form.form.position.data = committee.position
                c_form.form.committee_position.data = committee.committee_position
            for i in range(min_entries - current_count):
                c_form = form.committees.append_entry()
                if i < len(default_positions):
                    c_form.form.committee_position.data = default_positions[i]
        else:
            for i in range(min_entries):
                c_form = form.committees.append_entry()
                if i < len(default_positions):
                    c_form.form.committee_position.data = default_positions[i]
    if form.validate_on_submit():
        ComplaintCommittee.query.filter_by(repair_approval_id=rep_approval.id).delete()
        for i, c_form in enumerate(form.committees.entries):
            if not c_form.form.staff.data:
                continue
            committee = ComplaintCommittee(
                staff=c_form.form.staff.data,
                position=c_form.form.position.data,
                committee_position=c_form.form.committee_position.data,
                repair_approval_id=rep_approval.id,
                committee_name=request.form.get(f'committee_name_{i // 3}', 'ผู้ตรวจรับพัสดุ')
            )
            db.session.add(committee)
            db.session.commit()
        flash('บันทึกข้อมูลสำเร็จ', 'success')
        # if rep_approval.get_other_org == True:
        #     scheme = 'http' if current_app.debug else 'https'
        #     link = url_for("comp_tracker.repair_approval_index", tab='new', _external=True, _scheme=scheme)
        #     if committees:
        #         title = f'''แจ้งแก้ไขใบอนุมัติหลักการซ่อม {rep_approval.item}'''
        #         message = f'''เจ้าหน้าที่ได้ดำเนินการแก้ไขข้อมูลใบอนุมัติหลักการซ่อมสำหรับรายการ {rep_approval.item} กรุณาดำเนินการในขั้นตอนถัดไปตามกระบวนการที่เกี่ยวข้อง\n'''
        #         message += f'''ท่านสามารถดำเนินการพิมพ์เอกสารได้ที่ลิงก์ด้านล่าง\n{link}\n\n'''
        #         message += f'''ขอบคุณค่ะ\nระบบรับแจ้งปัญหาหรือข้อร้องเรียน\nคณะเทคนิคการแพทย์'''
        #     else:
        #         title = f'''แจ้งออกใบอนุมัติหลักการซ่อม {rep_approval.item}'''
        #         message = f'''เจ้าหน้าที่ได้ดำเนินการออกใบอนุมัติหลักการซ่อมสำหรับรายการ {rep_approval.item} กรุณาดำเนินการในขั้นตอนถัดไปตามกระบวนการที่เกี่ยวข้อง\n'''
        #         message += f'''ท่านสามารถดำเนินการพิมพ์เอกสารได้ที่ลิงก์ด้านล่าง\n{link}\n\n'''
        #         message += f'''ขอบคุณค่ะ\nระบบรับแจ้งปัญหาหรือข้อร้องเรียน\nคณะเทคนิคการแพทย์'''
        #         if rep_approval.record.complainant:
        #             msg = (
        #                 f'เจ้าหน้าที่ได้ดำเนินการออกใบอนุมัติหลักการซ่อมสำหรับรายการ {rep_approval.item} เรียบร้อยแล้ว\n\n'
        #                 f'ขอบคุณค่ะ\nระบบรับแจ้งปัญหาหรือข้อร้องเรียน\nคณะเทคนิคการแพทย์')
        #             message_for_complainant = f'''เจ้าหน้าที่ได้ดำเนินการออกใบอนุมัติหลักการซ่อมสำหรับรายการ {rep_approval.item} เรียบร้อยแล้ว\n\n'''
        #             message_for_complainant += f'''ขอบคุณค่ะ\nระบบรับแจ้งปัญหาหรือข้อร้องเรียน\nคณะเทคนิคการแพทย์'''
        #
        #             send_mail([rep_approval.record.complainant.email + '@mahidol.ac.th'], title,
        #                       message_for_complainant)
        #             if not current_app.debug:
        #                 try:
        #                     line_bot_api.push_message(to=rep_approval.record.complainant.line_id,
        #                                               messages=TextSendMessage(text=msg))
        #                 except LineBotApiError:
        #                     pass
        #             else:
        #                 print('msg :', msg, 'line :', rep_approval.record.complainant.line_id)
        #     if rep_approval.owner.personal_info.org.secretary_staff:
        #         send_mail([secretary.email + '@mahidol.ac.th' for secretary in rep_approval.owner.personal_info.org.secretary_staff],
        #                   title, message)
        if temp == 'index':
            return redirect(url_for('comp_tracker.repair_approval_index', tab=tab, menu=menu))
        else:
            return redirect(url_for('comp_tracker.edit_record_admin', record_id=rep_approval.record_id, tab=tab))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('complaint_tracker/committee_form.html', form=form, temp=temp,
                           tab=tab, menu=menu, repair_approval_id=repair_approval_id, rep_approval=rep_approval)


@complaint_tracker.route('/repair_approval/note/edit/<int:repair_approval_id>', methods=['GET', 'POST'])
@login_required
def create_note(repair_approval_id):
    status = ComplaintStatus.query.filter_by(code='completed').first()
    repair_approval = ComplaintRepairApproval.query.get(repair_approval_id)
    form = ComplaintRepairApprovalForm(obj=repair_approval)
    if form.validate_on_submit():
        form.populate_obj(repair_approval)
        repair_approval.is_print = True
        repair_approval.record.status = status
        repair_approval.canceller_id = current_user.id
        repair_approval.cancelled_at = arrow.now('Asia/Bangkok').datetime
        repair_approval.record.closed_at = arrow.now('Asia/Bangkok').datetime
        repair_approval.updated_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(repair_approval)
        db.session.commit()
        flash('ยกเลิกเรียบร้อยแล้ว', 'success')
        title = f'''แจ้งยกใบอนุมัติหลักการซ่อม {repair_approval.item}'''
        message = f'''ใบอนุมัติหลักการซ่อมสำหรับรายการ {repair_approval.item} ได้ถูกยกเลิกเรียบร้อยแล้ว\n\n'''
        message += f'''ขอบคุณค่ะ\nระบบรับแจ้งปัญหาหรือข้อร้องเรียน\nคณะเทคนิคการแพทย์'''
        if not current_app.debug:
            send_mail([admin.admin.email + '@mahidol.ac.th' for admin in repair_approval.record.topic.admins
                       if admin.admin.email == 'adisak.nun' and admin.admin.email == 'thanapat.nop'], title,
                      message)
        else:
            print('mail :', message, 'user :', [admin.admin.email + '@mahidol.ac.th' for admin in repair_approval.record.topic.admins
                       if admin.admin.email == 'adisak.nun' or admin.admin.email == 'thanapat.nop'])
        for admin in repair_approval.record.topic.admins:
            if admin.admin.email == 'adisak.nun' or admin.admin.email == 'thanapat.nop':
                if not current_app.debug:
                    try:
                        line_bot_api.push_message(to=admin.admin.line_id,
                                                  messages=TextSendMessage(text=message))
                    except LineBotApiError:
                        pass
                else:
                    print('msg :', message, 'line :', repair_approval.record.complainant.line_id)
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('complaint_tracker/modal/create_note_modal.html',
                           repair_approval_id=repair_approval_id, form=form)


def generate_repair_approval_pdf(repair_approval):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer,
                            pagesize=A4,
                            rightMargin=38,
                            leftMargin=38,
                            topMargin=38,
                            bottomMargin=38
                            )

    data = []

    header_right_style = ParagraphStyle(
        'HeaderRightStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=16,
        leading=20,
        alignment=TA_RIGHT,
    )
    content_style = ParagraphStyle(
        'ContentStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=16,
        leading=20,
    )
    bold_style = ParagraphStyle(
        'BoldStyle',
        parent=style_sheet['ThaiStyleBold'],
        fontSize=16,
        leading=20,
        alignment=TA_CENTER
    )
    approver_style = ParagraphStyle(
        'ApproverStyle',
        parent=style_sheet['ThaiStyleBold'],
        fontSize=16,
        leading=50,
        alignment=TA_CENTER
    )
    center_style = ParagraphStyle(
        'CenterStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=16,
        leading=20,
        alignment=TA_CENTER
    )
    item_style = ParagraphStyle(
        'ItemStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=16,
        leading=20,
        firstLineIndent=-37,
        leftIndent=37,
        alignment=TA_LEFT
    )
    item_detail_style = ParagraphStyle(
        'ItemDetailStyle',
        parent=style_sheet['ThaiStyle'],
        fontSize=16,
        leading=20,
        firstLineIndent=35,
        leftIndent=0,
    )

    logo = Image('app/static/img/logo-MU_black-white-2-1.png', 60, 60)
    mhesi_no = '''<font name="SarabunBold">ที่</font>'''

    if repair_approval.requester:
        org_name = repair_approval.requester.personal_info.org.name
        org = Org.query.filter_by(name=org_name).first()
        requester = f"{repair_approval.requester.fullname}"
        if org.name == 'หน่วยข้อมูลและสารสนเทศ':
            organization_text = f"{org.name}<br/>งานยุทธศาสตร์\u00A0และการบริหารพัฒนาทรัพยากร\u00A0{org.parent.parent.name}<br/>โทร {org.phone_number or ''}"
        elif org.parent and org.parent.parent:
            organization_text = f"{org.name}<br/>{org.parent.name}\u00A0{org.parent.parent.name}<br/>โทร {org.phone_number or ''}"
        elif org.parent and not org.parent.parent:
            organization_text = f"{org.name}<br/>{org.parent.name}<br/>โทร {org.phone_number or ''}"
        else:
            organization_text = f"{org.name}<br/>โทร {org.phone_number or ''}"
    else:
        requester = f""
        organization_text = f"{repair_approval.organization}"

    if repair_approval.approver:
        approver = f"{repair_approval.approver.fullname}"
    else:
        approver = f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
    organization_info = Paragraph(organization_text, style=header_right_style)
    person = Table([
        [Paragraph('ลงชื่อ', center_style), Paragraph('ผู้ขออนุมัติ', center_style)],
        [Paragraph(f'({requester})', center_style), ''],
        ['', ''],
        ['', ''],
        ['', ''],
        [Paragraph('ลงชื่อ', center_style), Paragraph('หัวหน้าภาค / ศูนย์ฯ', center_style)],
        [Paragraph(f'({approver})', center_style), ''],
    ], colWidths=[160, 160])
    person.setStyle(TableStyle([
        ('SPAN', (0, 1), (1, 1)),
        ('SPAN', (0, 6), (1, 6)),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    purchase_type = f'<font name="DejaVuSans">☑</font> รายได้ส่วนงาน <font name="DejaVuSans">☐</font> เงินงบประมาณแผ่นดิน' if repair_approval.purchase_type == 'รายได้ส่วนงาน' else \
        f'<font name="DejaVuSans">☐</font> รายได้ส่วนงาน <font name="DejaVuSans">☑</font> เงินงบประมาณแผ่นดิน'

    price_thai = bahttext(repair_approval.price)

    formatted_price = f"{int(repair_approval.price):,}" if repair_approval.price == int(repair_approval.price) \
        else f"{repair_approval.price:,.2f}"

    mhesi_no_date_info = '''<font name="SarabunBold">วันที่</font>'''

    if repair_approval.repair_type == 'เร่งด่วน':
        indent = 47
        text_style = item_detail_style

        form_code = Table(
            [[Paragraph("MTPC-001", style=bold_style)]],
            colWidths=[70],
            rowHeights=[30]
        )
        form_code.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        item = (
            '<font name="SarabunBold">เรื่อง</font>&nbsp;&nbsp;&nbsp;&nbsp;รายงานขออนุมัติซื้อ {item} กรณีจำเป็นเร่งด่วน ไม่คาดหมายไว้ก่อน ซึ่งไม่อาจดำเนินการตามปกติได้ทัน'
            .format(item=repair_approval.item))

        item_detail = '''ด้วย ข้าพเจ้า {name} ตำแหน่ง {position} สังกัด {org} ซึ่งเป็นผู้รับผิดชอบในการซื้อ {item} ไปก่อนแล้ว จึงขอรายงานเหตุ
                        ผลและความจำเป็น กรณีเร่งด่วน โดยมีรายละเอียด ดังนี้'''.format(
            name=repair_approval.name,
            item=repair_approval.item,
            position=repair_approval.position,
            org=repair_approval.organization)

        reason_title = '<para leftIndent=35><font name="SarabunBold">1. เหตุผลและความจำเป็นเร่งด่วนที่ต้องซื้อหรือจ้าง</font></para>'

        detail_title = '<para leftIndent=35><font name="SarabunBold">2. รายละเอียดของพัสดุที่ซื้อหรือจ้าง</font></para>'

        receipt_date = arrow.get(repair_approval.receipt_date).format(fmt='DD MMMM YYYY', locale='th-th')
        price = (
            '<font name="SarabunBold">3. วงเงินที่ซื้อหรือจ้างในครั้งนี้เป็นเงิน</font> {price} บาท ({price_thai}) จาก {supplier} ตามใบส่งของ/ใบเสร็จรับเงิน '
            'เล่มที่ {book_number} เลขที่ {receipt_number} วันที่ {receipt_date} ทั้งนี้ ข้าพเจ้าพร้อมหัวหน้าหน่วยงานได้ลงนามรับรองในใบส่ง'
            'ของหรือใบเสร็จรับเงินว่า “ได้ตรวจรับพัสดุไว้ถูกต้องครบถ้วนแล้ว”'
            .format(price=formatted_price, price_thai=price_thai, supplier=repair_approval.supplier,
                    book_number=repair_approval.book_number if repair_approval.book_number else '&nbsp;&nbsp;&nbsp;&nbsp;'
                    '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;',
                    receipt_number=repair_approval.receipt_number, receipt_date=receipt_date))

        receipt = (
            '<para leftIndent=35><font name="SarabunBold">4. โดยขอเบิกจ่ายจากเงิน</font> {purchase_type} ประจำปีงบประมาณ {budget_year} </para>'
            .format(purchase_type=purchase_type, budget_year=repair_approval.budget_year))

        remark = (
            '<font name="SarabunBold">5. ขออนุมัติขยายระยะเวลาเบิกจ่ายเงินเกิน 30 วัน</font> ไม่เป็นไปตามข้อบังคับมหาวิทยาลัยมหิดล ว่าด้วยการ'
            'บริหารงบประมาณและการเงิน (ฉบับที่ 2) พ.ศ.2556 ข้อ 32 เนื่องจาก {remark}'
            .format(remark=repair_approval.remark))
        if repair_approval.remark:
            description = (
                '<para leftIndent=55>จึงเรียนมาเพื่อโปรดพิจารณา <font name="SarabunBold">หากเห็นชอบโปรด</font><br/>'
                '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">1. อนุมัติซื้อหรือจ้างตามรายการข้างต้น</font><br/>'
                '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">2. ทราบผลการตรวจรับพัสดุ และอนุมัติเบิกจ่ายเงิน</font> '
                'ให้แก่ เงินทดรองจ่ายคณะเทคนิคการแพทย์<br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;เลขที่ บย.{loan_no} '
                'เป็นเงินทั้งสิ้น {price} บาท ({price_thai})) โดยส่งใช้เงินยืมทดรองจ่ายใน<br/>'
                '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;นาม "เงินทดรองจ่ายคณะเทคนิคการแพทย์ เลขที่ บย.{loan_no}" '
                '<font name="SarabunBold">และให้ถือว่ารายงานฉบับนี้เป็น<br/>'
                '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;หลักฐานกาตรวจรับโดยอนุโลม</font><br/>'
                '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">3. อนุมัติขยายระยะเวลาเบิกจ่ายเงิน</font>'
                '</para>').format(loan_no=repair_approval.loan_no, price=formatted_price, price_thai=price_thai)
        else:
            description = ('<para leftIndent=55>จึงเรียนมาเพื่อโปรดพิจารณา หากเห็นชอบโปรด<br/>'
                            '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">1. อนุมัติซื้อหรือจ้างตามรายการข้างต้น</font><br/>'
                            '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">2. ทราบผลการตรวจรับพัสดุ และอนุมัติเบิกจ่ายเงิน</font> '
                            'ให้แก่ เงินทดรองจ่ายคณะเทคนิคการแพทย์<br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;เลขที่ บย.{loan_no} '
                            'เป็นเงินทั้งสิ้น {price} บาท ({price_thai})) โดยส่งใช้เงินยืมทดรองจ่ายใน<br/>'
                            '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;นาม "เงินทดรองจ่ายคณะเทคนิคการแพทย์ เลขที่ บย.{loan_no}" '
                            '<font name="SarabunBold">และให้ถือว่ารายงานฉบับนี้เป็น<br/>'
                            '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;หลักฐานกาตรวจรับโดยอนุโลม</font><br/>'
                           '</para>').format(loan_no=repair_approval.loan_no, price=formatted_price, price_thai=price_thai)
    elif repair_approval.principle_approval_type == 'ซื้อ' or repair_approval.principle_approval_type == 'จ้าง':
        indent = 14
        text_style = content_style
        if repair_approval.price <= 30000:
            mtpc = 'MTPC-002'
        elif repair_approval.price > 30000 and repair_approval.price <= 500000:
            mtpc = 'MTPC-003'
        else:
            mtpc = 'MTPC-004'
        form_code = Table(
            [[Paragraph(mtpc, style=bold_style)]],
            colWidths=[70],
            rowHeights=[30]
        )
        form_code.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        checkbox = f'<font name="DejaVuSans">☑</font> ซื้อ <font name="DejaVuSans">☐</font> จ้าง' if repair_approval.principle_approval_type == 'ซื้อ' else \
            f'<font name="DejaVuSans">☐</font> ซื้อ <font name="DejaVuSans">☑</font> จ้าง'
        item = (
            '''<font name="SarabunBold">เรื่อง</font>&nbsp;&nbsp;&nbsp;&nbsp;ขออนุมัติในหลักการ {checkbox} รายการ {item}'''
            .format(checkbox=checkbox, item=repair_approval.item))

        item_detail = '''ด้วย {org} มีความประสงค์จะจัดซื้อหรือจ้าง {purpose} รายละเอียดดังนี้'''.format(org=repair_approval.organization,
                                                                                        purpose=repair_approval.purpose)

        reason_title = '<font name="SarabunBold">1. เหตุผลและความจำเป็นต้องซื้อ</font>'

        detail_title = '<font name="SarabunBold">2. รายละเอียดคุณลักษณะเฉพาะของพัสดุที่ซื้อหรือจ้าง</font>'

        price = ('<font name="SarabunBold">3. วงเงินที่ซื้อหรือจ้างในครั้งนี้เป็นเงิน</font> {price} บาท ({price_thai})'
                 .format(price=formatted_price, price_thai=price_thai))

        receipt = (
            '<font name="SarabunBold">4. โดยขอเบิกจ่ายจากเงิน</font> {purchase_type} ประจำปีงบประมาณ {budget_year}'
            .format(purchase_type=purchase_type, budget_year=repair_approval.budget_year))
        remark_checkbox = f'<font name="DejaVuSans">☑</font>' if repair_approval.remark else f'<font name="DejaVuSans">☐</font>'
        remark = (
            '<font name="SarabunBold">6. ตามแนวทางปฏิบัติตามกฎกระทรวงกำหนดพัสดุและวิธีการจัดซื้อจัดจ้างพัสดุที่รัฐต้องการส่งเสริมหรือสนับสนุน '
            '(ฉบับที่ 2) พ.ศ. 2563</font><br/>'
            '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
            '{remark_checkbox} มีความจำเป็นจะต้องมีการใช้พัสดุที่ผลิตจากต่างประเทศหรือนำเข้าพัสดุจากต่างประเทศ เนื่องจาก {remark}'
            .format(remark_checkbox=remark_checkbox, remark=repair_approval.remark if repair_approval.remark else
            '<br/>(กรณีไม่สามารถใช้สินค้าจาก SME หรือ Made In Thailand ได้)'))

        description = (
            '<para leftIndent=45>จึงเรียนมาเพื่อโปรดพิจารณา <font name="SarabunBold">หากเห็นชอบโปรด</font><br/>'
            '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">1. อนุมัติในหลักการซื้อหรือจ้างตามรายการข้างต้น</font><br/>'
            '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">2. อนุมัติตามข้อ 6</font> กรณีที่มีความจำเป็นต้องมีการใช้พัสดุที่ผลิตจากต่างประเทศหรือนำเข้าพัสดุจาก<br/>ต่างประเทศเท่านั้น<br/>'
            '</para>')
    else:
        indent = 14
        text_style = content_style

        form_code = Table(
            [[Paragraph("MTPC-007", style=bold_style)]],
            colWidths=[70],
            rowHeights=[30]
        )
        form_code.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        item = '''<font name="SarabunBold">เรื่อง</font>&nbsp;&nbsp;&nbsp;&nbsp;ขออนุมัติในหลักการ <font name="DejaVuSans">☑</font> 
                    จ้างซ่อม ครุภัณฑ์ {item}'''.format(item=repair_approval.item)

        item_detail = ('''ด้วย {org} มีความประสงค์จะจ้างซ่อมครุภัณฑ์ {item} รายละเอียดดังนี้'''
                       .format(org=repair_approval.organization, item=repair_approval.item))

        reason_title = '<font name="SarabunBold">1. เหตุผลและความจำเป็นต้องจ้างซ่อม</font>'

        detail_title = '<font name="SarabunBold">2. รายละเอียดการซ่อม</font>'

        price = ('<font name="SarabunBold">3. วงเงินที่ซ่อมในครั้งนี้เป็นเงิน</font> {price} บาท ({price_thai})'
                 .format(price=formatted_price, price_thai=price_thai))

        receipt = (
            '<font name="SarabunBold">4. โดยขอเบิกจ่ายจากเงิน</font> {purchase_type} ประจำปีงบประมาณ {budget_year}'
            .format(purchase_type=purchase_type, budget_year=repair_approval.budget_year))

        remark_checkbox = f'<font name="DejaVuSans">☑</font>' if repair_approval.remark else f'<font name="DejaVuSans">☐</font>'
        remark = (
            '<font name="SarabunBold">6. ตามแนวทางปฏิบัติตามกฎกระทรวงกำหนดพัสดุและวิธีการจัดซื้อจัดจ้างพัสดุที่รัฐต้องการส่งเสริมหรือสนับสนุน '
            '(ฉบับที่ 2) พ.ศ. 2563</font><br/>'
            '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
            '{remark_checkbox} มีความจำเป็นจะต้องมีการใช้พัสดุที่ผลิตจากต่างประเทศหรือนำเข้าพัสดุจากต่างประเทศ เนื่องจาก {remark}'
            .format(remark_checkbox=remark_checkbox, remark=repair_approval.remark if repair_approval.remark else
            '<br/>(กรณีไม่สามารถใช้สินค้าจาก SME หรือ Made In Thailand ได้)'))

        description = (
            '<para leftIndent=45>จึงเรียนมาเพื่อโปรดพิจารณา <font name="SarabunBold">หากเห็นชอบโปรด</font><br/>'
            '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">1. อนุมัติในหลักการซื้อหรือจ้างตามรายการข้างต้น</font><br/>'
            '&nbsp;&nbsp;&nbsp;&nbsp;<font name="SarabunBold">2. อนุมัติตามข้อ 6</font> กรณีที่มีความจำเป็นต้องมีการใช้พัสดุที่ผลิตจากต่างประเทศหรือนำเข้าพัสดุจาก<br/>ต่างประเทศเท่านั้น<br/>'
            '</para>')
    if repair_approval.product_code:
        code_detail = ('รหัสศูนย์ต้นทุน {cost_center} รหัสใบสั่งงานภายใน {io_code} ผลผลิต {product_code}'
                       .format(cost_center=repair_approval.cost_center, io_code=repair_approval.io_code.id,
                               product_code=repair_approval.product_code))
    else:
        code_detail = ('รหัสศูนย์ต้นทุน {cost_center} รหัสใบสั่งงานภายใน {io_code}'
                       .format(cost_center=repair_approval.cost_center, io_code=repair_approval.io_code.id))
    logo_cell = [[logo]]
    logo_table = Table(logo_cell, colWidths=[60])
    logo_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('VALIGN', (0, 0), (0, 0), 'TOP'),
    ]))

    header_right_table = Table([
        [form_code],
        [organization_info]
    ])
    header_right_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    header_table = Table([
        [Spacer(1, 1), logo_table, header_right_table]
    ], colWidths=[160, 180, 200])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
    ]))

    approval = Table([
        [Paragraph('อนุมัติ', style=approver_style)],
        [Paragraph('(ผู้ช่วยศาสตราจารย์ ดร.โชติรส พลับพลึง)<br/>คณบดีคณะเทคนิคการแพทย์', style=center_style)]
    ], colWidths=195)

    approval.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))

    footer_table = Table([
        [approval, Spacer(10, 0), person]
    ], colWidths=[180, 10, 330])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 60)
    ]))

    data.append(header_table)
    data.append(Spacer(1, 12))
    data.append(Paragraph(mhesi_no, style=content_style))
    data.append(Paragraph(mhesi_no_date_info, style=content_style))
    data.append(Paragraph(item, style=item_style))
    data.append(Paragraph(f'<font name="SarabunBold">เรียน</font>&nbsp;&nbsp;&nbsp;&nbsp;คณบดีคณะเทคนิคการแพทย์',
                          style=content_style))
    data.append(Paragraph(item_detail, style=item_detail_style))
    data.append(Paragraph(reason_title, style=content_style))
    data.append(Paragraph(f'<para leftIndent={indent}>{repair_approval.reason}</para>', style=content_style))
    data.append(Paragraph(detail_title, style=content_style))
    data.append(Paragraph(f'<para leftIndent={indent}>{repair_approval.detail}</para>', style=content_style))
    data.append(Paragraph(price, style=text_style))
    data.append(Paragraph(receipt, style=content_style))
    data.append(Paragraph(code_detail, style=content_style))
    if repair_approval.repair_type != 'เร่งด่วน':
        if repair_approval.price > 500000:
            committee_title = '<font name="SarabunBold">5. ขอแต่งตั้งผู้มีรายนามต่อไปนี้ เป็นผู้ตรวจรับพัสดุ</font>'
            data.append(Paragraph(committee_title, style=content_style))
            ordered_committee_names = [
                'คณะกรรมการกำหนดรายละเอียดคุณลักษณะเฉพาะ',
                'คณะกรรมการพิจารณาผลการประกวดราคาอิเล็กทรอนิกส์',
                'คณะกรรมการตรวจรับพัสดุ'
            ]

            for committee_name in ordered_committee_names:
                committee_members = [
                    c for c in repair_approval.committees
                    if c.committee_name.strip() == committee_name
                ]

                if committee_members:
                    data.append(Paragraph(committee_name, style=content_style))
                    count = 2
                    for c in committee_members:
                        if c.committee_position == "ประธาน":
                            para = f'<para leftIndent=35>1) {c.staff.fullname} ตำแหน่ง {c.position} {c.committee_position}</para>'
                            data.append(Paragraph(para, style=content_style))
                    for c in committee_members:
                        if c.committee_position == "กรรมการ":
                            para = f'<para leftIndent=35>{count}) {c.staff.fullname} ตำแหน่ง {c.position} {c.committee_position}</para>'
                            data.append(Paragraph(para, style=content_style))
                            count += 1
        elif repair_approval.price > 30000 and repair_approval.price <= 500000:
            committee_title = '<font name="SarabunBold">5. ขอแต่งตั้งผู้มีรายนามต่อไปนี้ เป็นคณะกรรมการตรวจรับพัสดุ</font>'
            data.append(Paragraph(committee_title, style=content_style))
            count = 2
            for c in repair_approval.committees:
                if c.committee_position == "ประธาน":
                    committee = ('<para leftIndent=35>5.1 {committee} ตำแหน่ง {position} {committee_position}</para>'
                                 .format(committee=c.staff.fullname, position=c.position,
                                         committee_position=c.committee_position))
                elif c.committee_position == "กรรมการ":
                    committee = (
                        '<para leftIndent=35>5.{num} {committee} ตำแหน่ง {position} {committee_position}</para>'
                        .format(num=count, committee=c.staff.fullname, position=c.position,
                                committee_position=c.committee_position))
                    count += 1
                else:
                    committee = ('<para leftIndent=35>5.1 {committee} ตำแหน่ง {position} {committee_position}</para>'
                                 .format(committee=c.staff.fullname, position=c.position,
                                         committee_position=c.committee_position))
                data.append(Paragraph(committee, style=content_style))
        else:
            committee_title = '<font name="SarabunBold">5. ขอแต่งตั้งผู้มีรายนามต่อไปนี้ เป็นผู้ตรวจรับพัสดุ</font>'
            data.append(Paragraph(committee_title, style=content_style))
            for c in repair_approval.committees:
                committee = ('<para leftIndent=35>5.1 {committee} ตำแหน่ง {position} {committee_position}</para>'
                             .format(committee=c.staff.fullname, position=c.position,
                                     committee_position=c.committee_position))
                data.append(Paragraph(committee, style=content_style))
    if (repair_approval.repair_type == 'เร่งด่วน' and repair_approval.remark) or repair_approval.principle_approval_type == 'ซื้อ' \
            or repair_approval.principle_approval_type == 'จ้าง' or repair_approval.repair_type == 'จ้างซ่อม':
        data.append(Paragraph(remark, style=text_style))
    data.append(Paragraph(description, style=content_style))
    data.append(Spacer(1, 12))
    data.append(footer_table)
    doc.build(data, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer


@complaint_tracker.route('/admin/repair-approval/pdf/<int:repair_approval_id>', methods=['GET'])
@login_required
def export_repair_approval_pdf(repair_approval_id):
    repair_approval = ComplaintRepairApproval.query.get(repair_approval_id)
    buffer = generate_repair_approval_pdf(repair_approval)
    if not repair_approval.reviewed_at:
        repair_approval.is_print = True
        repair_approval.reviewed_at = arrow.now('Asia/Bangkok').datetime
        repair_approval.updated_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(repair_approval)
        db.session.commit()
    return send_file(buffer, download_name='Repair_approval_form.pdf', as_attachment=True)


@complaint_tracker.route('/repair-approval/print/<int:repair_approval_id>', methods=['GET', 'POST'])
@login_required
def print_repair_approval(repair_approval_id):
    repair_approval = ComplaintRepairApproval.query.get(repair_approval_id)
    repair_approval.is_print = True
    db.session.add(repair_approval)
    db.session.commit()
    return ''


@complaint_tracker.route('/api/admin/new-record-complaint')
@login_required
def get_new_record_complaint():
    code = request.args.get('code')
    return _build_calendar_chart_json(
        ComplaintRecord.created_at,
        include_unset_status=True,
        code=code
    )


@complaint_tracker.route('/api/admin/pending-record-complaint')
@login_required
def get_pending_record_complaint():
    code = request.args.get('code')
    return _build_calendar_chart_json(
        ComplaintRecord.created_at,
        status_code='pending',
        code=code
    )


@complaint_tracker.route('/api/admin/progress-record-complaint')
@login_required
def get_progress_record_complaint():
    code = request.args.get('code')
    return _build_calendar_chart_json(
        ComplaintRecord.created_at,
        status_code='progress',
        code=code
    )


@complaint_tracker.route('/api/admin/success-record-complaint')
@login_required
def get_success_record_complaint():
    code = request.args.get('code')
    return _build_calendar_chart_json(
        ComplaintRecord.closed_at,
        status_code='completed',
        code=code
    )


@complaint_tracker.route('/api/admin/pie-chart')
@login_required
def get_pie_chart_for_record_complaint():
    code = request.args.get('code')
    description = {'status': ("string", "Status"), 'heads': ("number", "heads")}
    start_fiscal_date, end_fiscal_date = get_fiscal_date(datetime.today())
    query = db.session.query(
        ComplaintStatus.status.label('status'),
        func.count(ComplaintRecord.id).label('heads')
    ).outerjoin(ComplaintStatus, ComplaintRecord.status_id == ComplaintStatus.id).filter(
        or_(
            ComplaintRecord.closed_at.between(start_fiscal_date, end_fiscal_date),
            ComplaintRecord.created_at.between(start_fiscal_date, end_fiscal_date)
        )
    )
    query = _apply_topic_code_filter(query, code)
    rows = query.group_by(ComplaintStatus.status).all()

    count_data = []
    for row in rows:
        count_data.append({
            'status': row.status or 'ยังไม่ดำเนินการ',
            'heads': row.heads
        })
    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon(columns_order=('status', 'heads'))


@complaint_tracker.route('/api/admin/bar-chart')
@login_required
def get_bar_chart_for_record_complaint():
    code = request.args.get('code')
    start_fiscal_date, end_fiscal_date = get_fiscal_date(datetime.today())
    month_expr = func.date_trunc('month', ComplaintRecord.created_at)

    query = db.session.query(
        month_expr.label('month_start'),
        ComplaintStatus.status.label('status'),
        func.count(ComplaintRecord.id).label('heads')
    ).outerjoin(ComplaintStatus, ComplaintRecord.status_id == ComplaintStatus.id).filter(
        or_(
            ComplaintRecord.closed_at.between(start_fiscal_date, end_fiscal_date),
            ComplaintRecord.created_at.between(start_fiscal_date, end_fiscal_date)
        )
    )
    query = _apply_topic_code_filter(query, code)
    rows = query.group_by('month_start', ComplaintStatus.status).order_by('month_start').all()

    statuses = []
    status_seen = set()
    description = {'month': ('string', 'Month')}
    data = defaultdict(dict)
    month_order = []

    for row in rows:
        month_label = row.month_start.strftime('%B %Y')
        status = row.status or 'ยังไม่ดำเนินการ'
        if month_label not in data:
            month_order.append(month_label)
        data[month_label][status] = row.heads
        if status not in status_seen:
            status_seen.add(status)
            statuses.append(status)

    for status in statuses:
        description[status] = ('number', status)

    count_data = []
    for month in month_order:
        row = {'month': month}
        for status in statuses:
            row[status] = data[month].get(status, 0)
        count_data.append(row)
    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon(columns_order=['month'] + statuses)


@complaint_tracker.route('/api/admin/tag-bar-chart')
@login_required
def get_tag_bar_chart_for_record_complaint():
    description = {'tag': ("string", "Tag"), 'amount': ("number", "amount")}
    rows = db.session.query(
        ComplaintTag.tag.label('tag'),
        func.count(complaint_record_tag_assoc.c.record_id).label('amount')
    ).join(
        complaint_record_tag_assoc,
        complaint_record_tag_assoc.c.tag_id == ComplaintTag.id
    ).group_by(
        ComplaintTag.id,
        ComplaintTag.tag
    ).order_by(
        func.count(complaint_record_tag_assoc.c.record_id).desc(),
        ComplaintTag.tag
    ).limit(10).all()

    count_sort_data = [{'tag': row.tag, 'amount': row.amount} for row in rows]
    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_sort_data)
    return data_table.ToJSon(columns_order=('tag', 'amount'))


@complaint_tracker.route('/api/admin/unfinished-repair-approval-chart')
@login_required
def get_unfinished_repair_approval_chart():
    code = request.args.get('code')
    description = {'status': ('string', 'Status'), 'heads': ('number', 'heads')}
    start_fiscal_date, end_fiscal_date = get_fiscal_date(datetime.today())

    query = db.session.query(
        ComplaintStatus.status.label('status'),
        func.count(func.distinct(ComplaintRecord.id)).label('heads')
    ).join(
        ComplaintRepairApproval, ComplaintRepairApproval.record_id == ComplaintRecord.id
    ).outerjoin(
        ComplaintStatus, ComplaintRecord.status_id == ComplaintStatus.id
    ).filter(
        ComplaintRecord.created_at.between(start_fiscal_date, end_fiscal_date),
        or_(
            ComplaintRecord.status_id.is_(None),
            ComplaintStatus.code != 'completed'
        )
    )

    query = _apply_topic_code_filter(query, code)
    rows = query.group_by(ComplaintStatus.status).all()

    count_data = [
        {
            'status': row.status or 'ยังไม่ดำเนินการ',
            'heads': row.heads
        }
        for row in rows
    ]

    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon(columns_order=('status', 'heads'))
