from collections import defaultdict
from html import escape
import json
import os
import re
from datetime import timedelta
import arrow
import  pytz
import requests
from dateutil import parser
from app.main import mail
from flask_mail import Message
from sqlalchemy import or_, func, case, and_
from sqlalchemy.orm import joinedload
from flask import render_template, redirect, flash, url_for, jsonify, request, make_response, current_app
from flask_login import login_required, current_user
from app.auth.views import line_bot_api
from app.linebot_compat import LineBotApiError, TextSendMessage
from app.roles import it_permission, software_request_permission
from app.software_request import software_request
from app.software_request.forms import create_request_form, create_timeline_form, SoftwareRequestIssueForm, \
    create_test_result_form, create_bdd_feature_form
from app.software_request.models import *
from app.staff.models import Role
from app.google_credential_utils import load_google_credentials_json
from werkzeug.utils import secure_filename
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive

localtz = pytz.timezone('Asia/Bangkok')
TYPHOON_API_URL = 'https://api.opentyphoon.ai/v1/chat/completions'
TYPHOON_MODEL = os.getenv('SCB_TYPHOON_MODEL', 'typhoon-v2.5-30b-a3b-instruct')

gauth = GoogleAuth()
keyfile_dict = load_google_credentials_json()
scopes = ['https://www.googleapis.com/auth/drive']
if keyfile_dict:
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scopes)
    drive = GoogleDrive(gauth)
else:
    drive = None

FOLDER_ID = '1832el0EAqQ6NVz2wB7Ade6wRe-PsHQsu'

json_keyfile = load_google_credentials_json()

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'docx', 'doc'}


def send_mail(recp, title, message, html=None):
    message = Message(subject=title, body=message, recipients=recp, html=html)
    mail.send(message)


def initialize_gdrive():
    if not json_keyfile:
        return None
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scopes)
    return GoogleDrive(gauth)


def _request_flag(name, default=False):
    raw_value = request.values.get(name)
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _normalize_internal_email(email_value):
    if not email_value:
        return None
    email_value = email_value.strip()
    if not email_value:
        return None
    if '@' not in email_value:
        email_value = f'{email_value}@mahidol.ac.th'
    return email_value


def _mask_line_id(line_id):
    if not line_id:
        return None
    if len(line_id) <= 6:
        return '***'
    return f'{line_id[:3]}***{line_id[-3:]}'


def _is_valid_notification_scheduler_request():
    configured_token = os.environ.get('JOB_TOKEN')
    request_token = request.values.get('job_token')
    return bool(configured_token and request_token and request_token == configured_token)


def _get_software_request_role_accounts():
    role = Role.query.filter_by(role_need='software_request', action_need=None, resource_id=None).first()
    if not role:
        return []
    accounts = []
    for account in role.staff_account.all():
        if account and account.is_active and not account.is_retired:
            accounts.append(account)
    return accounts


def _get_software_request_email_recipients():
    recipients = {}
    for account in _get_software_request_role_accounts():
        email = _normalize_internal_email(account.email if account else None)
        if not email:
            continue
        recipients[email] = {
            'email': email,
            'staff_name': account.fullname if account else email,
        }
    return sorted(recipients.values(), key=lambda item: item['email'])


def _get_software_request_line_recipients():
    recipients = {}
    for account in _get_software_request_role_accounts():
        line_id = account.line_id if account else None
        if not line_id:
            continue
        if line_id not in recipients:
            recipients[line_id] = {
                'line_id': line_id,
                'staff_name': account.fullname if account else line_id,
            }
    return sorted(recipients.values(), key=lambda item: item['staff_name'])


def _serialize_software_request_item(detail):
    return {
        'id': detail.id,
        'title': detail.title,
        'status': detail.status,
        'system': detail.system.system if detail.system else 'ไม่ระบุ',
        'type': detail.type or 'ไม่ระบุ',
        'priority': detail.priority or 'ไม่ระบุ',
        'user_group': detail.user_group or 'ไม่ระบุ',
        'created_by': detail.created_by.fullname if detail.created_by else None,
        'created_date': detail.created_date.isoformat() if detail.created_date else None,
        'updated_date': detail.updated_date.isoformat() if detail.updated_date else None,
    }


def _pick_software_request_group_label(detail):
    if detail.system and detail.system.system:
        return detail.system.system
    if detail.type:
        return detail.type
    if detail.user_group:
        return detail.user_group
    return 'ไม่ระบุ'


def _build_software_request_summary_snapshot():
    now = arrow.now('Asia/Bangkok')
    week_ago = now.shift(days=-7).datetime
    pending_status = 'ส่งคำขอแล้ว'
    consider_status = 'อยู่ระหว่างพิจารณา'
    approve_status = 'อนุมัติ'
    complete_status = 'เสร็จสิ้น'

    pending_query = SoftwareRequestDetail.query.filter_by(status=pending_status)
    consider_query = SoftwareRequestDetail.query.filter_by(status=consider_status)
    approve_query = SoftwareRequestDetail.query.filter_by(status=approve_status)
    completed_recent_query = SoftwareRequestDetail.query.filter(
        SoftwareRequestDetail.status == complete_status,
        SoftwareRequestDetail.updated_date.isnot(None),
        SoftwareRequestDetail.updated_date >= week_ago,
        SoftwareRequestDetail.updated_date <= now.datetime,
    )

    sample_options = (
        joinedload(SoftwareRequestDetail.created_by).joinedload(StaffAccount.personal_info),
        joinedload(SoftwareRequestDetail.system),
    )
    pending_samples = pending_query.options(*sample_options).order_by(
        SoftwareRequestDetail.created_date.desc().nullslast()
    ).limit(5).all()
    consider_samples = consider_query.options(*sample_options).order_by(
        SoftwareRequestDetail.created_date.desc().nullslast()
    ).limit(5).all()
    approve_samples = approve_query.options(*sample_options).order_by(
        SoftwareRequestDetail.created_date.desc().nullslast()
    ).limit(5).all()
    completed_samples = completed_recent_query.options(*sample_options).order_by(
        SoftwareRequestDetail.updated_date.desc().nullslast()
    ).limit(5).all()

    completed_group_counter = defaultdict(int)
    for item in completed_recent_query.options(joinedload(SoftwareRequestDetail.system)).all():
        completed_group_counter[_pick_software_request_group_label(item)] += 1
    completed_top_groups = [
        {'label': label, 'count': count}
        for label, count in sorted(completed_group_counter.items(), key=lambda item: (-item[1], item[0]))[:3]
    ]

    pending_count = pending_query.count()
    consider_count = consider_query.count()
    approve_count = approve_query.count()
    completed_last_7_days = completed_recent_query.count()

    return {
        'generated_at': now.to('Asia/Bangkok').format('DD/MM/YYYY HH:mm'),
        'pending_count': pending_count,
        'consider_count': consider_count,
        'approve_count': approve_count,
        'completed_last_7_days': completed_last_7_days,
        'total_open_records': pending_count + consider_count + approve_count,
        'status_counts': {
            'รอดำเนินการ': pending_count,
            'อยู่ระหว่างพิจารณา': consider_count,
            'อนุมัติ': approve_count,
            'ปิดงานใน 7 วันที่ผ่านมา': completed_last_7_days,
        },
        'pending_samples': [_serialize_software_request_item(item) for item in pending_samples],
        'consider_samples': [_serialize_software_request_item(item) for item in consider_samples],
        'approve_samples': [_serialize_software_request_item(item) for item in approve_samples],
        'completed_samples': [_serialize_software_request_item(item) for item in completed_samples],
        'completed_top_groups': completed_top_groups,
    }


def _get_software_request_dominant_status(snapshot):
    candidates = [
        ('รอดำเนินการ', snapshot['pending_count'], 'ยังไม่ดำเนินการ'),
        ('อยู่ระหว่างพิจารณา', snapshot['consider_count'], 'อยู่ระหว่างพิจารณา'),
        ('อนุมัติ', snapshot['approve_count'], 'อนุมัติแล้ว'),
        ('ปิดงานแล้วในช่วง 7 วันที่ผ่านมา', snapshot['completed_last_7_days'], 'ปิดงานแล้ว'),
    ]
    label, count, display = max(
        enumerate(candidates),
        key=lambda item: (item[1][1], -item[0]),
    )[1]
    return {
        'label': label,
        'count': count,
        'display': display,
    }


def _build_software_request_summary_prompt(snapshot):
    return [
        {
            'role': 'system',
            'content': (
                'You are writing a concise executive email summary in Thai for senior administrators. '
                'Summarize the overall status of software request work using only the aggregated snapshot provided. '
                'Do not mention request IDs, personal names, or raw descriptions. '
                'Focus on volume, trends, blocking risks, recently closed momentum, and what leadership should watch next. '
                'Use plain Thai and keep the message concise but useful. '
                'Return plain text only. '
                'Structure the answer as: one short overview paragraph, three bullet points of key issues, and one short closing paragraph. '
                'Mention the four status buckets and the count of items closed in the last 7 days.'
            )
        },
        {
            'role': 'user',
            'content': (
                'สรุปข้อมูลต่อไปนี้เป็นภาษาไทยสำหรับผู้บริหาร โดยยึดตามตัวเลขและตัวอย่างงานที่ให้มาเท่านั้น:\n'
                f'{json.dumps(snapshot, ensure_ascii=False, indent=2)}'
            )
        }
    ]


def _call_typhoon_software_request_summary(snapshot):
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
            'messages': _build_software_request_summary_prompt(snapshot),
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload['choices'][0]['message']['content']
    if not content or not content.strip():
        raise ValueError('Empty Typhoon summary response.')
    return content.strip()


def _build_fallback_software_request_summary(snapshot):
    dominant_status = _get_software_request_dominant_status(snapshot)
    dominant_sentence = (
        f"โดยกลุ่มสถานะที่พบมากคือ {dominant_status['display']} {dominant_status['count']} เรื่อง"
        if dominant_status['count'] > 0
        else "โดยภาพรวมยังไม่พบสถานะที่เด่นชัด"
    )
    return (
        f"ภาพรวม\n"
        f"ขณะนี้มีงานที่ยังไม่แล้วเสร็จทั้งหมด {snapshot['total_open_records']} เรื่อง โดยแบ่งเป็นรอดำเนินการ {snapshot['pending_count']} เรื่อง "
        f"อยู่ระหว่างพิจารณา {snapshot['consider_count']} เรื่อง และอนุมัติแล้ว {snapshot['approve_count']} เรื่อง "
        f"ขณะเดียวกันมีเงานที่ปิดแล้วในช่วง 7 วันที่ผ่านมา {snapshot['completed_last_7_days']} เรื่อง {dominant_sentence}\n\n"
        f"ประเด็นที่ควรติดตาม\n"
        f"- เร่งติดตามงานที่ยังอยู่ในสถานะรอดำเนินการและอยู่ระหว่างพิจารณา เพื่อลดปริมาณงานคงค้าง\n"
        f"- ทบทวนและเร่งรัดงานที่อนุมัติแล้วแต่ยังไม่เริ่มดำเนินการ หรืออยู่ระหว่างดำเนินการ เพื่อให้สามารถปิดงานได้ตามแผน\n"
        f"- เร่งติดตามงานที่ดำเนินการเสร็จแล้วแต่ยังอยู่ระหว่างรอการทดสอบ เพื่อให้สามารถปิดงานได้ตามแผน\n\n"
        f"สิ่งที่ควรเฝ้าระวัง\n"
        f"ควรติดตามงานที่อยู่ในสถานะรอดำเนินการ อยู่ระหว่างการพิจารณา หรือดำเนินการแล้วแต่ยังรอการทดสอบอย่างต่อเนื่อง "
        f"โดยเฉพาะรายการที่ค้างอยู่เป็นเวลานาน เพื่อป้องกันการสะสมของงานคงค้างและลดความเสี่ยงที่การปิดงานจะล่าช้ากว่าแผนที่กำหนด"
    )


def _build_software_request_summary_email_body(snapshot, ai_summary):
    status_lines = '\n'.join(
        f"- {label}: {count} เรื่อง" for label, count in snapshot['status_counts'].items()
    ) or '- ไม่มีข้อมูล'
    completed_group_lines = '\n'.join(
        f"- {item['label']}: {item['count']} เรื่อง" for item in snapshot['completed_top_groups']
    ) or '- ไม่มีข้อมูล'
    return (
        f"สรุปภาพรวมเรื่องคงค้าง/คำขอพัฒนา Software ณ {snapshot['generated_at']}\n\n"
        f"รายงานฉบับนี้จัดทำขึ้นโดยระบบอัตโนมัติร่วมกับ AI เพื่อช่วยสรุปภาพรวมสำหรับการติดตามงาน\n\n"
        f"{ai_summary}\n\n"
        f"ตัวเลขประกอบการติดตาม\n"
        f"- งานคงค้างทั้งหมด: {snapshot['total_open_records']} รายการ\n"
        f"- รอดำเนินการ: {snapshot['pending_count']} รายการ\n"
        f"- อยู่ระหว่างพิจารณา: {snapshot['consider_count']} รายการ\n"
        f"- อนุมัติ: {snapshot['approve_count']} รายการ\n"
        f"- ปิดงานแล้วในช่วง 7 วันที่ผ่านมา: {snapshot['completed_last_7_days']} รายการ\n\n"
        f"กลุ่มเรื่องที่ปิดแล้วใน 7 วันล่าสุด\n"
        f"{completed_group_lines}\n"
    )


def _get_software_request_chart_values(snapshot):
    return [
        ('คงค้างทั้งหมด', snapshot['total_open_records'], '#334155'),
        ('รอดำเนินการ', snapshot['pending_count'], '#2563eb'),
        ('อยู่ระหว่างพิจารณา', snapshot['consider_count'], '#f59e0b'),
        ('อนุมัติ', snapshot['approve_count'], '#22c55e'),
        # ('ปิดงานใน 7 วัน', snapshot['completed_last_7_days'], '#8b5cf6'),
    ]


def _render_software_request_email_chart_html(snapshot):
    values = _get_software_request_chart_values(snapshot)
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
          <td style="padding:6px 12px 6px 0;font-size:13px;color:#334155;white-space:nowrap;font-weight:600;">{escape(label)} ({value})</td>
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


def _render_software_request_summary_email_html(package):
    snapshot = package['snapshot']
    chart_html = _render_software_request_email_chart_html(snapshot)
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
      <h1 style="margin:0 0 8px;font-size:28px;">สรุปรายงานเรื่องคงค้าง/คำขอ</h1>
      <div style="margin-top:14px;background:#ecfeff;color:#115e59;border:1px solid #99f6e4;border-radius:14px;padding:14px 16px;line-height:1.6;">
        รายงานฉบับนี้จัดทำขึ้นโดยระบบอัตโนมัติร่วมกับ AI เพื่อช่วยสรุปภาพรวมสำหรับการติดตามงาน
      </div>
    </div>
    <section style="background:#ffffff;border:1px solid #dbe4ee;border-radius:18px;padding:20px;box-shadow:0 10px 30px rgba(15,23,42,0.06);">
      <div style="background:#f8fafc;border:1px solid #dbe4ee;border-radius:14px;padding:14px 16px;margin-bottom:18px;">
        <h3 style="margin:0 0 10px;font-size:16px;">ตัวเลขสำคัญ</h3>
        <div style="font-size:14px;color:#64748b;line-height:1.9;">
          <span style="display:inline-block;margin-right:18px;"><strong style="color:#0f172a;font-size:20px;margin-right:4px;">{snapshot['total_open_records']}</strong>งานคงค้าง</span>
          <span style="display:inline-block;margin-right:18px;"><strong style="color:#0f172a;font-size:20px;margin-right:4px;">{snapshot['pending_count']}</strong>รอดำเนินการ</span>
          <span style="display:inline-block;margin-right:18px;"><strong style="color:#0f172a;font-size:20px;margin-right:4px;">{snapshot['consider_count']}</strong>อยู่ระหว่างพิจารณา</span>
          <span style="display:inline-block;margin-right:18px;"><strong style="color:#0f172a;font-size:20px;margin-right:4px;">{snapshot['approve_count']}</strong>อนุมัติ</span>
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
        <div style="background:#f8fafc;color:#0f172a;border:1px solid #dbe4ee;border-radius:14px;padding:16px;line-height:1.65;font-size:14px;white-space:pre-wrap;">{message_html}</div>
      </div>
    </section>
  </div>
</body>
</html>'''


def _build_software_request_line_reminder_message(snapshot):
    if snapshot['total_open_records'] == 0:
        return None
    return (
        f"แจ้งเตือนรายการคงค้าง/คำขอพัฒนา Software วันที่ {snapshot['generated_at']}\n"
        f"มีทั้งหมด {snapshot['total_open_records']} เรื่อง"
    )


def _render_software_request_line_reminder_dry_run_html(packages, should_send, snapshot):
    cards = []
    for package in packages:
        recipient = package['recipient']
        message_html = escape(package['message'] or 'ไม่มีรายการที่ต้องส่ง').replace('\n', '<br>')
        cards.append(f'''
        <section class="card">
            <div class="card-header">
                <div class="pill">{escape(recipient['staff_name'])}</div>
                <div class="meta">LINE: {escape(recipient['line_id'])}</div>
            </div>
            <div class="summary-card">
                <h3>สรุปตัวเลข</h3>
                <div class="summary-metrics">
                    <span><strong>{snapshot['pending_count']}</strong> รอดำเนินการ</span>
                    <span><strong>{snapshot['consider_count']}</strong> อยู่ระหว่างพิจารณา</span>
                    <span><strong>{snapshot['approve_count']}</strong> อนุมัติ</span>
                    <span><strong>{snapshot['completed_last_7_days']}</strong> ปิดงานใน 7 วัน</span>
                </div>
            </div>
            <div class="message">
                <h3>ข้อความที่จะส่ง</h3>
                <div class="message-body">{message_html}</div>
            </div>
        </section>
        ''')

    return f'''<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dry Run: Software Request Line Reminder</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#f8fafc; color:#0f172a; }}
    .page {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px 60px; }}
    .hero {{ margin-bottom: 24px; }}
    .hero h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .hero p {{ margin: 0; color: #64748b; }}
    .notice {{ margin-top: 14px; background: #ecfeff; color: #115e59; border: 1px solid #99f6e4; border-radius: 14px; padding: 14px 16px; line-height: 1.6; }}
    .grid {{ display: grid; gap: 20px; }}
    .card {{ background: #ffffff; border: 1px solid #dbe4ee; border-radius: 18px; padding: 20px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06); }}
    .card-header {{ display: flex; justify-content: space-between; gap: 16px; align-items: start; margin-bottom: 16px; }}
    .pill {{ background: #ecfeff; color: #0f766e; border: 1px solid #99f6e4; border-radius: 999px; padding: 8px 12px; font-size: 13px; }}
    .summary-card {{ background: #f8fafc; border: 1px solid #dbe4ee; border-radius: 14px; padding: 14px 16px; margin-bottom: 18px; }}
    .summary-card h3, .message h3 {{ margin: 0 0 12px; font-size: 16px; }}
    .summary-metrics {{ display: flex; flex-wrap: wrap; gap: 10px 18px; }}
    .summary-metrics span {{ color: #64748b; font-size: 14px; }}
    .summary-metrics strong {{ color: #0f172a; font-size: 20px; margin-right: 4px; }}
    .message-body {{ background: #f8fafc; border: 1px solid #dbe4ee; border-radius: 14px; padding: 16px; line-height: 1.65; font-size: 14px; }}
    .meta {{ color: #64748b; font-size: 13px; }}
    @media (max-width: 800px) {{ .card-header {{ flex-direction: column; }} }}
  </style>
</head>
<body>
  <main class="page">
    <header class="hero">
      <h1>Dry Run: Software Request Line Reminder</h1>
      <p>Send flag: {str(should_send)} | Recipient count: {len(packages)} | Open total: {snapshot['total_open_records']}</p>
      <div class="notice">รายงานตัวอย่างนี้ใช้ตรวจสอบข้อความก่อนส่งจริง และสรุปจากสถานะในระบบขอรับบริการพัฒนา software โดยเฉพาะ</div>
    </header>
    <div class="grid">
      {''.join(cards) if cards else '<section class="card"><p>No recipients found.</p></section>'}
    </div>
  </main>
</body>
</html>'''


def _render_software_request_summary_dry_run_html(packages, should_send, snapshot):
    cards = []
    for package in packages:
        recipient = package['recipient']
        message_html = escape(package['message'] or 'ไม่มีข้อความสรุป').replace('\n', '<br>')
        cards.append(f'''
        <section class="card">
            <div class="card-header">
                <div class="pill">{escape(recipient['staff_name'])}</div>
                <div class="meta">{escape(recipient['email'])}</div>
            </div>
            <div class="summary-card">
                <h3>สรุปตัวเลข</h3>
                <div class="summary-metrics">
                    <span><strong>{snapshot['pending_count']}</strong> รอดำเนินการ</span>
                    <span><strong>{snapshot['consider_count']}</strong> อยู่ระหว่างพิจารณา</span>
                    <span><strong>{snapshot['approve_count']}</strong> อนุมัติ</span>
                    <span><strong>{snapshot['completed_last_7_days']}</strong> ปิดงานใน 7 วัน</span>
                </div>
            </div>
            <div class="message">
                <h3>ข้อความที่จะส่ง</h3>
                <div class="message-body">{message_html}</div>
            </div>
        </section>
        ''')

    return f'''<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dry Run: Software Request Summary</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#f8fafc; color:#0f172a; }}
    .page {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px 60px; }}
    .hero {{ margin-bottom: 24px; }}
    .hero h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .hero p {{ margin: 0; color: #64748b; }}
    .notice {{ margin-top: 14px; background: #ecfeff; color: #115e59; border: 1px solid #99f6e4; border-radius: 14px; padding: 14px 16px; line-height: 1.6; }}
    .grid {{ display: grid; gap: 20px; }}
    .card {{ background: #ffffff; border: 1px solid #dbe4ee; border-radius: 18px; padding: 20px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06); }}
    .card-header {{ display: flex; justify-content: space-between; gap: 16px; align-items: start; margin-bottom: 16px; }}
    .pill {{ background: #ecfeff; color: #0f766e; border: 1px solid #99f6e4; border-radius: 999px; padding: 8px 12px; font-size: 13px; }}
    .summary-card {{ background: #f8fafc; border: 1px solid #dbe4ee; border-radius: 14px; padding: 14px 16px; margin-bottom: 18px; }}
    .summary-card h3, .message h3 {{ margin: 0 0 12px; font-size: 16px; }}
    .summary-metrics {{ display: flex; flex-wrap: wrap; gap: 10px 18px; }}
    .summary-metrics span {{ color: #64748b; font-size: 14px; }}
    .summary-metrics strong {{ color: #0f172a; font-size: 20px; margin-right: 4px; }}
    .message-body {{ background: #f8fafc; border: 1px solid #dbe4ee; border-radius: 14px; padding: 16px; line-height: 1.65; font-size: 14px; }}
    .meta {{ color: #64748b; font-size: 13px; }}
    @media (max-width: 800px) {{ .card-header {{ flex-direction: column; }} }}
  </style>
</head>
<body>
  <main class="page">
    <header class="hero">
      <h1>Dry Run: Software Request Summary Email</h1>
      <p>Send flag: {str(should_send)} | Recipient count: {len(packages)} | Open total: {snapshot['total_open_records']}</p>
      <div class="notice">รายงานตัวอย่างนี้ใช้ตรวจสอบเนื้อหาก่อนส่งสรุปประจำสัปดาห์ให้ผู้บริหาร</div>
    </header>
    <div class="grid">
      {''.join(cards) if cards else '<section class="card"><p>No recipients found.</p></section>'}
    </div>
  </main>
</body>
</html>'''


def update_test_result(test_result, status, note):
    old_note = test_result.note
    old_status = test_result.status
    test_result.status = status
    test_result.note = note
    if test_result.recorded_at and status == old_status and note == old_note:
        test_result.recorded_at = arrow.get(test_result.recorded_at, 'Asia/Bangkok').datetime
        test_result.recorder_id = current_user.id
    elif status or note:
        test_result.recorded_at = arrow.now('Asia/Bangkok').datetime
        test_result.recorder_id = current_user.id
    else:
        test_result.recorded_at = None
        test_result.recorder_id = None
    db.session.add(test_result)
    db.session.commit()


def _get_drive_embed_url(file_id):
    # Avoid a metadata round-trip just to render an already-known Drive file link.
    return f'https://drive.google.com/file/d/{file_id}/preview'


def _extract_typhoon_json(raw_text):
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


def _build_bdd_feature_prompt(issue, requirement_text=None):
    request_detail = issue.software_request_detail
    request_title = (request_detail.title or '').strip() if request_detail else ''
    request_description = (request_detail.description or '').strip() if request_detail else ''
    issue_text = (requirement_text if requirement_text is not None else issue.issue or '').strip()
    issue_label = (issue.label or '').strip()
    phase_name = issue.phase.phase if issue.phase else ''
    deadline = issue.deadline.isoformat() if issue.deadline else ''

    return [
        {
            'role': 'system',
            'content': (
                'You are an expert business analyst and BDD author. '
                'The source requirement text may be Thai, but the output must be English only. Do not use Thai in the output. '
                'Generate a realistic Gherkin feature for a software request using the details provided. '
                'Do not write a simple rule or a generic template. '
                'Capture the user goal, behavior, acceptance criteria, and sensible edge cases. '
                'Write concise but useful Gherkin with a clear feature title and multiple scenarios when appropriate. '
                'Return JSON only with keys feature_title and gherkin_text. '
                'The gherkin_text value must start with "Feature:" and contain valid Gherkin structure. '
                'Keep all output in English.'
            )
        },
        {
            'role': 'user',
            'content': json.dumps({
                'software_request_title': request_title,
                'software_request_description': request_description,
                'requirement_text': issue_text,
                'requirement_type': issue_label,
                'phase': phase_name,
                'deadline': deadline,
            }, ensure_ascii=False, indent=2),
        }
    ]


def _call_typhoon_bdd_feature(issue, requirement_text=None):
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
            'max_tokens': 1200,
            'messages': _build_bdd_feature_prompt(issue, requirement_text=requirement_text),
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload['choices'][0]['message']['content']
    parsed = _extract_typhoon_json(content)
    feature_title = str(parsed.get('feature_title') or '').strip()
    gherkin_text = str(parsed.get('gherkin_text') or '').strip()
    if not feature_title or not gherkin_text:
        raise ValueError('Missing feature_title or gherkin_text in Typhoon response.')
    if not gherkin_text.startswith('Feature:'):
        raise ValueError('Typhoon response must return Gherkin text starting with "Feature:".')
    return {
        'feature_title': feature_title,
        'gherkin_text': gherkin_text,
    }


def _build_bdd_feature_form(issue, feature, feature_exists):
    BDDFeatureForm = create_bdd_feature_form()
    form = BDDFeatureForm(obj=feature) if feature else BDDFeatureForm()
    form.issue_id.data = issue.id
    if feature and feature.id:
        form.feature_id.data = feature.id
    elif feature_exists:
        # Keep editing the existing saved record even when the UI is showing a fresh Typhoon draft.
        existing_feature = _get_bdd_feature_for_issue(issue)
        if existing_feature:
            form.feature_id.data = existing_feature.id
    return form


def _set_bdd_feature_form_defaults(form, issue, requirement_text=None, reviewed_by_human=None):
    form.requirement.data = requirement_text if requirement_text is not None else (issue.issue or '')
    if reviewed_by_human is not None:
        form.reviewed_by_human.data = bool(reviewed_by_human)


def _render_bdd_feature_modal(issue, feature, feature_exists, generation_error=None, form=None,
                              requirement_text=None, reviewed_by_human=None):
    form = form or _build_bdd_feature_form(issue, feature, feature_exists)
    _set_bdd_feature_form_defaults(
        form,
        issue,
        requirement_text=requirement_text,
        reviewed_by_human=reviewed_by_human,
    )
    return render_template(
        'software_request/modal/create_bdd_feature_modal.html',
        form=form,
        issue=issue,
        feature=feature,
        feature_exists=feature_exists,
        generation_error=generation_error,
    )


def _build_admin_request_query(tab):
    query = SoftwareRequestDetail.query
    if tab == 'pending':
        return query.filter_by(status='ส่งคำขอแล้ว')
    elif tab == 'consider':
        return query.filter_by(status='อยู่ระหว่างพิจารณา')
    elif tab == 'approve':
        return query.filter_by(status='อนุมัติ')
    elif tab == 'complete':
        return query.filter_by(status='เสร็จสิ้น')
    elif tab == 'disapprove':
        return query.filter_by(status='ไม่อนุมัติ')
    elif tab == 'cancel':
        return query.filter_by(status='ยกเลิก')
    elif tab == 'private':
        return query.outerjoin(SoftwareRequestDetail.timelines).outerjoin(SoftwareRequestDetail.staffs).filter(
            or_(SoftwareRequestTimeline.admin_id == current_user.id,
                StaffAccount.id == current_user.id)
        ).distinct()
    return query


def _build_admin_request_listing_query(base_query):
    # Aggregate counts in SQL so the admin table does not trigger N+1 queries for each row.
    active_timeline_counts = db.session.query(
        SoftwareRequestTimeline.request_id.label('request_id'),
        func.count(SoftwareRequestTimeline.id).label('num_timelines')
    ).filter(
        SoftwareRequestTimeline.status.notin_(['ยกเลิกการพัฒนา', 'เสร็จสิ้น'])
    ).group_by(SoftwareRequestTimeline.request_id).subquery()

    open_issue_counts = db.session.query(
        SoftwareIssues.software_request_detail_id.label('request_id'),
        func.sum(
            case(
                [(SoftwareIssues.closed_at.is_(None), 1)],
                else_=0
            )
        ).label('open_issues')
    ).group_by(SoftwareIssues.software_request_detail_id).subquery()

    return base_query.options(
        # Eager-load requester/org data because the table always renders these fields.
        joinedload(SoftwareRequestDetail.created_by)
            .joinedload(StaffAccount.personal_info)
            .joinedload('org')
    ).outerjoin(
        active_timeline_counts,
        active_timeline_counts.c.request_id == SoftwareRequestDetail.id
    ).outerjoin(
        open_issue_counts,
        open_issue_counts.c.request_id == SoftwareRequestDetail.id
    ).add_columns(
        func.coalesce(active_timeline_counts.c.num_timelines, 0).label('num_timelines'),
        func.coalesce(open_issue_counts.c.open_issues, 0).label('open_issues')
    )


@software_request.route('/')
@login_required
def index():
    org = current_user.personal_info.org
    api = request.args.get('api', 'false')
    query = SoftwareRequestDetail.query.filter(or_(
        SoftwareRequestDetail.created_id == current_user.id,
        SoftwareRequestDetail.created_by.has(
            StaffAccount.personal_info.has(org=org)
        )
    ))

    if api == 'true':
        records_total = query.count()
        search = request.args.get('search[value]')
        if search:
            search_term = u'%{}%'.format(search)
            query = query.filter(or_(
                SoftwareRequestDetail.title.ilike(search_term),
                SoftwareRequestDetail.type.ilike(search_term),
                SoftwareRequestDetail.description.ilike(search_term),
                SoftwareRequestDetail.status.ilike(search_term)
            ))

        start = request.args.get('start', type=int)
        length = request.args.get('length', type=int)
        total_filtered = query.count()

        sort_columns = {
            0: SoftwareRequestDetail.title,
            1: SoftwareRequestDetail.type,
            2: SoftwareRequestDetail.description,
            3: SoftwareRequestDetail.created_date,
            4: SoftwareRequestDetail.status,
        }
        sort_column_index = request.args.get('order[0][column]', default=3, type=int)
        sort_direction = request.args.get('order[0][dir]', default='desc')
        sort_column = sort_columns.get(sort_column_index, SoftwareRequestDetail.created_date)
        if sort_direction == 'asc':
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        if start:
            query = query.offset(start)
        if length and length > 0:
            query = query.limit(length)

        data = []
        for item in query.all():
            data.append({
                'id': item.id,
                'title': item.title,
                'type': item.type,
                'description': item.description,
                'created_date': item.created_date,
                'status': item.status,
                'status_color': item.status_color,
            })

        return jsonify({
            'data': data,
            'recordsFiltered': total_filtered,
            'recordsTotal': records_total,
            'draw': request.args.get('draw', type=int)
        })

    return render_template('software_request/index.html', org=org)


@software_request.route('/condition')
def condition_for_service_request():
    return render_template('software_request/condition_page.html')


@software_request.route('/request/view/<int:detail_id>', methods=['GET', 'POST'])
@login_required
def view_request(detail_id):
    count = 0
    detail = SoftwareRequestDetail.query.get(detail_id)
    datetime_now = arrow.now('Asia/Bangkok').datetime
    if request.method == 'POST':
        for form in request.form:
            if form.startswith("result_") :
                item_id = form.replace("result_", "")
                test_result = SoftwareRequestTestResult.query.get(item_id)
                value = request.form.get(form)
                update_test_result(test_result=test_result, status=value, note=test_result.note if test_result.note else '')
                recorded_at = arrow.get(test_result.recorded_at, 'Asia/Bangkok').datetime if test_result.recorded_at else None
                if datetime_now == recorded_at:
                    count += 1
            if form.startswith("note_") :
                item_id = form.replace("note_", "")
                test_result = SoftwareRequestTestResult.query.get(item_id)
                value = request.form.get(form)
                update_test_result(test_result=test_result, status=test_result.status if test_result.status else '',
                                   note=value)
        flash('บันทึกผลเรียบร้อยแล้ว', 'success')
        if detail.staffs and count > 0:
            scheme = 'http' if current_app.debug else 'https'
            link = url_for("software_request.update_request", detail_id=detail_id, tab='approve', _external=True, _scheme=scheme)
            title = f'''แจ้งผลการทดสอบ{detail.title}'''
            message = f'''ผลการทดสอบ{detail.title} เสร็จสิ้นแล้ว\n'''
            message += f'''โดยมีจำนวนรายการที่ทำการทดสอบทั้งหมด {count} รายการ\n'''
            message += f'''กรุณาตรวจสอบรายละเอียดผลการทดสอบในระบบ\n'''
            message += f'''{link}\n\n'''
            message += f'''ขอบคุณค่ะ\n'''
            message += f'''ระบบขอรับบริการพัฒนา Software\n'''
            message += f'''คณะเทคนิคการแพทย์'''
            send_mail([staff.email + '@mahidol.ac.th' for staff in detail.staffs], title, message)
    return render_template('software_request/view_request.html', detail=detail)


@software_request.route('/request/add', methods=['GET', 'POST'])
def create_request():
    SoftwareRequestDetailForm = create_request_form(detail_id=None)
    form = SoftwareRequestDetailForm()
    if form.validate_on_submit():
        detail = SoftwareRequestDetail()
        form.populate_obj(detail)
        file = form.file_upload.data
        drive = initialize_gdrive()
        if form.type.data == 'ปรับปรุงระบบที่มีอยู่' and not form.system.data:
            flash('กรุณาเลือกระบบที่ต้องการปรับปรุง', 'danger')
            return render_template('software_request/create_request.html', form=form)
        if file:
            file_name = secure_filename(file.filename)
            file.save(file_name)
            file_drive = drive.CreateFile({'title': file_name,
                                           'parents': [{'id': FOLDER_ID, "kind": "drive#fileLink"}]})
            file_drive.SetContentFile(file_name)
            file_drive.Upload()
            file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
            detail.url = file_drive['id']
            detail.file_name = file_name
        if form.system.data:
            system_id = request.form.getlist('system')
            system = SoftwareRequestSystem.query.get(system_id)
            detail.title = system.system
            detail.system_id = system.id
        detail.status = 'ส่งคำขอแล้ว'
        detail.created_date = arrow.now('Asia/Bangkok').datetime
        detail.created_id = current_user.id
        db.session.add(detail)
        db.session.commit()
        flash('ส่งคำขอสำเร็จ', 'success')
        return redirect(url_for('software_request.index'))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('software_request/create_request.html', form=form)


@software_request.route('/api/system', methods=['GET'])
@login_required
def get_systems():
    search_term = request.args.get('term', '')
    key = request.args.get('key', 'id')
    results = []
    systems = SoftwareRequestSystem.query.all()
    for system in systems:
        if search_term in system.system:
            index_ = getattr(system, key) if hasattr(system, key) else getattr(system.system, key)
            results.append({
                "id": index_,
                "text": system.system
            })
    return jsonify({'results': results})


@software_request.route('/admin/index')
@software_request_permission.require()
@login_required
def admin_index():
    tab = request.args.get('tab')
    api = request.args.get('api', 'false')
    timelines = SoftwareRequestTimeline.query.filter_by(admin_id=current_user.id)
    pending_query = SoftwareRequestDetail.query.filter_by(status='ส่งคำขอแล้ว')
    consider_query = SoftwareRequestDetail.query.filter_by(status='อยู่ระหว่างพิจารณา')
    approve_query = SoftwareRequestDetail.query.filter_by(status='อนุมัติ')
    complete_query = SoftwareRequestDetail.query.filter_by(status='เสร็จสิ้น')
    disapprove_query = SoftwareRequestDetail.query.filter_by(status='ไม่อนุมัติ')
    cancel_query = SoftwareRequestDetail.query.filter_by(status='ยกเลิก')
    if api == 'true':
        query = _build_admin_request_query(tab)
        records_total = query.count()
        search = request.args.get('search[value]')
        if search:
            search_term = u'%{}%'.format(search)
            query = query.filter(or_(
                SoftwareRequestDetail.title.ilike(search_term),
                SoftwareRequestDetail.type.ilike(search_term),
                SoftwareRequestDetail.description.ilike(search_term),
                SoftwareRequestDetail.status.ilike(search_term)
            ))

        start = request.args.get('start', type=int)
        length = request.args.get('length', type=int)
        total_filtered = query.count()
        # Apply pagination after building the enriched query used by DataTables.
        query = _build_admin_request_listing_query(query)

        sort_columns = {
            0: SoftwareRequestDetail.title,
            1: SoftwareRequestDetail.type,
            2: SoftwareRequestDetail.description,
            5: SoftwareRequestDetail.created_date,
        }
        sort_column_index = request.args.get('order[0][column]', default=5, type=int)
        sort_direction = request.args.get('order[0][dir]', default='desc')
        sort_column = sort_columns.get(sort_column_index, SoftwareRequestDetail.created_date)
        if sort_direction == 'asc':
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        if start:
            query = query.offset(start)
        if length and length > 0:
            query = query.limit(length)

        data = []
        for item, num_timelines, open_issues in query.all():
            data.append(item.to_dict(
                num_timelines=num_timelines,
                open_issues=open_issues,
                has_timeline=bool(num_timelines)
            ))
        return jsonify({'data': data,
                        'recordsFiltered': total_filtered,
                        'recordsTotal': records_total,
                        'draw': request.args.get('draw', type=int)
                        })
    return render_template('software_request/admin_index.html', tab=tab, pending_count=pending_query.count(),
                           consider_count=consider_query.count(), approve_count=approve_query.count(),
                           complete_count=complete_query.count(), disapprove_count=disapprove_query.count(),
                           cancel_count=cancel_query.count(), timelines=timelines,
                           notification_line_recipients=len(_get_software_request_line_recipients()),
                           notification_email_recipients=len(_get_software_request_email_recipients()))


@software_request.route('/admin/line-remind-admins', methods=['GET', 'POST'])
def line_remind_software_request_admins():
    scheduler_request = _is_valid_notification_scheduler_request()
    if not scheduler_request:
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if not software_request_permission.can():
            return current_app.response_class('Forbidden', status=403)

    snapshot = _build_software_request_summary_snapshot()
    message = _build_software_request_line_reminder_message(snapshot)
    recipients = _get_software_request_line_recipients()
    packages = [
        {
            'recipient': recipient,
            'message': message,
        }
        for recipient in recipients
    ]
    matched_packages = [package for package in packages if package['message']]
    should_send = _request_flag('send')
    dry_run = _request_flag('dry_run', default=(request.method == 'GET' and not should_send))

    if dry_run:
        return _render_software_request_line_reminder_dry_run_html(packages, should_send, snapshot)

    if not should_send:
        response = make_response(
            'Line reminder was not sent. Add send=true to trigger delivery, or dry_run=true to preview recipients.\n',
            400
        )
        response.mimetype = 'text/plain'
        return response

    if not matched_packages:
        message_text = 'ไม่พบผู้รับหรือไม่พบเรื่องที่เข้าเงื่อนไขสำหรับส่ง Line reminder'
        if request.method == 'POST':
            flash(message_text, 'warning')
            return redirect(url_for('software_request.admin_index', tab='all'))
        response = make_response(message_text + '\n', 404)
        response.mimetype = 'text/plain'
        return redirect(url_for('software_request.admin_index', tab='all'))

    sent_count = 0
    failed_count = 0
    for package in matched_packages:
        try:
            line_bot_api.push_message(
                to=package['recipient']['line_id'],
                messages=TextSendMessage(text=package['message'])
            )
            sent_count += 1
        except LineBotApiError:
            failed_count += 1
            current_app.logger.exception(
                'Failed to send software request line reminder to line_id=%s',
                _mask_line_id(package['recipient']['line_id'])
            )

    success_message = f'ส่ง Line reminder แล้ว {sent_count} ราย'
    if failed_count:
        success_message += f' และส่งไม่สำเร็จ {failed_count} ราย'

    if request.method == 'GET':
        response = make_response(success_message + '\n')
        response.mimetype = 'text/plain'
        return redirect(url_for('software_request.admin_index', tab='all'))

    flash(success_message, 'success' if failed_count == 0 else 'warning')
    if request.headers.get('HX-Request'):
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return redirect(url_for('software_request.admin_index', tab='all'))


@software_request.route('/admin/email-unfinished-summary', methods=['GET', 'POST'])
def email_unfinished_summary():
    scheduler_request = _is_valid_notification_scheduler_request()
    if not scheduler_request:
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if not software_request_permission.can():
            return current_app.response_class('Forbidden', status=403)

    snapshot = _build_software_request_summary_snapshot()
    recipients = _get_software_request_email_recipients()
    should_send = _request_flag('send')
    dry_run = _request_flag('dry_run', default=(request.method == 'GET' and not should_send))

    if dry_run:
        dry_run_packages = []
        ai_summary = _build_fallback_software_request_summary(snapshot)
        for recipient in recipients:
            dry_run_packages.append({
                'recipient': recipient,
                'subject': f"สรุปภาพรวมเรื่องคงค้างระบบขอรับบริการพัฒนา software ณ {snapshot['generated_at']}",
                'message': _build_software_request_summary_email_body(snapshot, ai_summary),
            })
        return _render_software_request_summary_dry_run_html(dry_run_packages, should_send, snapshot)

    if not should_send:
        response = make_response(
            'Email was not sent. Add send=true to trigger delivery, or dry_run=true to preview recipients.\n',
            400
        )
        response.mimetype = 'text/plain'
        return redirect(url_for('software_request.admin_index', tab='all'))

    if not recipients:
        message_text = 'ไม่พบอีเมลของผู้รับที่มี role software_request สำหรับส่งสรุป'
        if request.method == 'POST':
            flash(message_text, 'danger')
            return redirect(request.referrer or url_for('software_request.admin_index', tab='all'))
        response = make_response(message_text + '\n', 404)
        response.mimetype = 'text/plain'
        return response

    if snapshot['total_open_records'] > 0 or snapshot['completed_last_7_days'] > 0:
        try:
            ai_summary = _call_typhoon_software_request_summary(snapshot)
        except Exception as exc:
            current_app.logger.warning('Failed to generate software request summary with Typhoon AI: %s', exc)
            ai_summary = _build_fallback_software_request_summary(snapshot)
    else:
        ai_summary = _build_fallback_software_request_summary(snapshot)

    subject = f"สรุปภาพรวมเรื่องคงค้าง/คำขอพัฒนา Software ณ {snapshot['generated_at']}"
    body = _build_software_request_summary_email_body(snapshot, ai_summary)
    package = {
        'recipient': {'email': ', '.join(recipient['email'] for recipient in recipients)},
        'subject': subject,
        'message': body,
        'snapshot': snapshot,
        'scope_label': 'สรุปภาพรวมงานคงค้าง',
    }
    html_body = _render_software_request_summary_email_html(package)

    recipient_emails = [recipient['email'] for recipient in recipients]
    try:
        send_mail(recipient_emails, subject, body, html=html_body)
        success_message = f'ส่งอีเมลสรุปเรื่องคงค้างแล้ว 1 ฉบับถึง {len(recipient_emails)} ราย'
    except Exception:
        current_app.logger.exception(
            'Failed to send software request summary email to recipients=%s',
            recipient_emails,
        )
        success_message = 'ส่งอีเมลสรุปเรื่องคงค้างไม่สำเร็จ'

    if request.method == 'GET':
        response = make_response(success_message + '\n')
        response.mimetype = 'text/plain'
        return redirect(url_for('software_request.admin_index', tab='all'))

    flash(success_message, 'success' if success_message.startswith('ส่งอีเมลสรุปเรื่องคงค้างแล้ว') else 'danger')
    if request.headers.get('HX-Request'):
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return redirect(url_for('software_request.admin_index', tab='all'))


@software_request.route('/api/timelines/<tab>')
@login_required
def get_timelines(tab):
    start = request.args.get('start')
    end = request.args.get('end')

    if start:
        start = parser.isoparse(start)
    if end:
        end = parser.isoparse(end)

    all_timelines = []
    # Eager-load related objects used to render calendar labels to avoid per-event queries.
    timelines = SoftwareRequestTimeline.query.options(
        joinedload(SoftwareRequestTimeline.request),
        joinedload(SoftwareRequestTimeline.admin).joinedload(StaffAccount.personal_info)
    ).filter(
        SoftwareRequestTimeline.start <= end,
        SoftwareRequestTimeline.estimate >= start,
        SoftwareRequestTimeline.status != 'ยกเลิกการพัฒนา'
    )
    if tab == 'private':
        timelines = timelines.filter(SoftwareRequestTimeline.admin_id == current_user.id)

    for timeline in timelines:
        all_timelines.append({
            'id': timeline.id,
            'detail_id': timeline.request_id,
            'title': '{} ({}) - {}'.format(timeline.task, timeline.request.title, timeline.admin.fullname),
            'start': timeline.start.isoformat(),
            'end': (timeline.estimate + timedelta(days=1)).isoformat(),
            'borderColor': '#aed581' if timeline.status == 'เสร็จสิ้น' else '#b3e5fc',
            'backgroundColor': '#aed581' if timeline.status == 'เสร็จสิ้น' else '#b3e5fc',
            'textColor': '#000000',
        })
    return jsonify(all_timelines)


@software_request.route('/timelines/<int:timeline_id>')
def show_timeline_detail(timeline_id):
    tab = request.args.get('tab')
    timeline = SoftwareRequestTimeline.query.get(timeline_id)
    return render_template('software_request/timeline_detail.html', tab=tab, timeline=timeline)


@software_request.route('/admin/request/edit/<int:detail_id>', methods=['GET', 'POST'])
def update_request(detail_id):
    tab = request.args.get('tab')
    detail = SoftwareRequestDetail.query.get(detail_id)
    status = detail.status
    required_information = detail.required_information
    suggestion = detail.suggestion
    old_created_by = detail.created_by
    SoftwareRequestDetailForm = create_request_form(detail_id=detail_id)
    form = SoftwareRequestDetailForm(obj=detail)
    if detail.url:
        file_url = _get_drive_embed_url(detail.url)
    else:
        file_url = None
    appointment_date = form.appointment_date.data.astimezone(localtz) if form.appointment_date.data else None
    if form.validate_on_submit():
        form.populate_obj(detail)
        if not form.created_by.data or not detail.created_by:
            flash('กรุณาเลือกผู้ส่งคำขอ', 'danger')
            return render_template('software_request/update_request.html', form=form, tab=tab, detail=detail,
                                   file_url=file_url, appointment_date=appointment_date)
        detail.updated_date = arrow.now('Asia/Bangkok').datetime
        detail.approver_id = current_user.id
        detail.appointment_date = arrow.get(form.appointment_date.data, 'Asia/Bangkok').datetime if form.appointment_date.data else None
        detail.status = form.status.data if form.status.data else status
        if form.status.data in ['เสร็จสิ้น', 'ยกเลิก', 'ไม่อนุมัติ']:
            if detail.timelines:
                for timeline in detail.timelines:
                    if timeline.status not in ('ยกเลิกการพัฒนา', 'เสร็จสิ้น'):
                        timeline.status = 'เสร็จสิ้น'
                        db.session.add(timeline)
            if detail.issues:
                for issue in detail.issues:
                    if not (issue.closed_at or issue.cancelled_at):
                        issue.closed_at = arrow.now('Asia/Bangkok').datetime
                        issue.updated_at = arrow.now('Asia/Bangkok').datetime
                        issue.tested_at = None
                        issue.accepted_at = None
                        db.session.add(issue)
        db.session.add(detail)
        db.session.commit()
        scheme = 'http' if current_app.debug else 'https'
        link = url_for("software_request.view_request", detail_id=detail_id, _external=True, _scheme=scheme)

        # Consolidate notifications so submit does not block on multiple synchronous mail sends.
        message_sections = []
        if old_created_by != detail.created_by:
            message_sections.append(
                 '''ทางหน่วยงานไอทีได้ปรับเปลี่ยนให้ท่านเป็นผู้รับผิดชอบคำขอการพัฒนานี้'''
            )
        if required_information != detail.required_information:
            message_sections.append(
                f'''ทางหน่วยงานไอทีมีความประสงค์ขอข้อมูลเพิ่มเติมเพื่อใช้ประกอบการดำเนินงาน ดังนี้\n{detail.required_information}'''
            )
        if suggestion != detail.suggestion:
            message_sections.append(
                f'''ทางหน่วยงานไอทีมีข้อเสนอแนะเพิ่มเติมเพื่อประกอบการพัฒนาระบบ ดังนี้\n{detail.suggestion}'''
            )
        if form.status.data:
            message_sections.append(
                f'''{detail.approver.fullname} ได้ทำการอัปเดตสถานะคำร้องขอรับบริการพัฒนา Software ของ {detail.title} เป็น "{detail.status}"'''
            )

        if message_sections and not detail.created_by.is_retired:
            title = f'''แจ้งอัปเดตคำร้องขอรับบริการพัฒนา Software'''
            message = f'''เรียน {detail.created_by.fullname}\n\n'''
            message += f'''ตามที่ท่านได้ดำเนินการขอรับบริการพัฒนา Software สำหรับ {detail.title} นั้น มีการอัปเดตดังต่อไปนี้\n\n'''
            message += '\n\n'.join(message_sections)
            message += f'''\n\nท่านสามารถตรวจสอบรายละเอียดและความคืบหน้าเพิ่มเติมได้ที่ลิงก์ด้านล่าง\n'''
            message += f'''{link}\n\n'''
            message += f'''หากมีข้อสงสัยหรือต้องการสอบถามข้อมูลเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ที่รับผิดชอบ\n\n'''
            message += f'''ขอบคุณค่ะ\n'''
            message += f'''ระบบขอรับบริการพัฒนา Software\n'''
            message += f'''คณะเทคนิคการแพทย์'''
            send_mail([detail.created_by.email + '@mahidol.ac.th'], title, message)

        # PRG avoids re-running the heavy page setup on POST and prevents duplicate submits on refresh.
        if form.status.data:
            flash('อัพเดตสถานะสำเร็จ', 'success')
        else:
            flash('อัพเดตข้อมูลสำเร็จ  ', 'success')
        return redirect(url_for('software_request.update_request', detail_id=detail_id, tab=tab))
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('software_request/update_request.html', form=form, tab=tab, detail=detail,
                           file_url=file_url, appointment_date=appointment_date)


def _get_bdd_feature_for_issue(issue):
    return BDDFeature.query.filter_by(software_issue_id=issue.id).order_by(
        BDDFeature.version.desc(),
        BDDFeature.id.desc(),
    ).first()


@software_request.route('/admin/request/bdd_feature/create/<int:issue_id>', methods=['GET', 'POST'])
def create_bdd_feature(issue_id):
    issue = SoftwareIssues.query.get_or_404(issue_id)
    existing_feature = _get_bdd_feature_for_issue(issue)
    feature_exists = existing_feature is not None
    generation_error = None
    feature = existing_feature
    requirement_text = (issue.issue or '').strip()
    reviewed_by_human = existing_feature.reviewed_by_human if existing_feature else False
    if request.method == 'POST':
        requirement_text = (request.form.get('requirement') or requirement_text).strip()
        reviewed_by_human = _request_flag('reviewed_by_human')
    if not feature:
        try:
            typhoon_feature = _call_typhoon_bdd_feature(issue, requirement_text=requirement_text)
            feature = BDDFeature(
                software_request_id=issue.software_request_detail_id,
                software_issue_id=issue.id,
                feature_title=typhoon_feature['feature_title'],
                gherkin_text=typhoon_feature['gherkin_text'],
                generated_by_ai=True,
                reviewed_by_human=False,
                version=1,
                created_at=arrow.now('Asia/Bangkok').datetime,
                updated_at=arrow.now('Asia/Bangkok').datetime,
            )
        except Exception as exc:
            current_app.logger.warning('Typhoon BDD feature generation failed for issue %s: %s', issue.id, exc)
            generation_error = 'BDD feature generation is currently unavailable. Please try again later.'
    form = _build_bdd_feature_form(issue, feature, feature_exists)
    form_html = _render_bdd_feature_modal(
        issue=issue,
        feature=feature,
        feature_exists=feature_exists,
        generation_error=generation_error,
        form=form,
        requirement_text=requirement_text,
        reviewed_by_human=reviewed_by_human,
    )
    if request.method == 'POST' and form.validate_on_submit():
        feature_id = form.feature_id.data
        if feature_id:
            feature = BDDFeature.query.get_or_404(int(feature_id))
        else:
            if generation_error:
                flash(generation_error, 'danger')
                return make_response(_render_bdd_feature_modal(
                    issue=issue,
                    feature=None,
                    feature_exists=False,
                    generation_error=generation_error,
                    form=_build_bdd_feature_form(issue, None, False),
                    requirement_text=form.requirement.data,
                    reviewed_by_human=form.reviewed_by_human.data,
                ))
            next_version = (db.session.query(func.max(BDDFeature.version)).filter(
                BDDFeature.software_issue_id == issue.id,
            ).scalar() or 0) + 1
            feature = BDDFeature(
                software_request_id=issue.software_request_detail_id,
                software_issue_id=issue.id,
                version=next_version,
                generated_by_ai=True,
                created_at=arrow.now('Asia/Bangkok').datetime,
            )
        issue.issue = (form.requirement.data or '').strip()
        issue.updated_at = arrow.now('Asia/Bangkok').datetime
        issue.updater = current_user
        db.session.add(issue)
        feature.feature_title = form.feature_title.data
        feature.gherkin_text = form.gherkin_text.data
        feature.reviewed_by_human = bool(form.reviewed_by_human.data)
        feature.software_request_id = issue.software_request_detail_id
        feature.software_issue_id = issue.id
        feature.generated_by_ai = True
        feature.updated_at = arrow.now('Asia/Bangkok').datetime
        if not feature.version:
            feature.version = 1
        if not feature.created_at:
            feature.created_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(feature)
        db.session.commit()
        flash('บันทึก Gherkin feature เรียบร้อยแล้ว', 'success')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    elif request.method == 'POST':
        if generation_error and not feature_exists:
            flash(generation_error, 'danger')
        else:
            flash(f'{form.errors}', 'danger')
    return form_html


@software_request.route('/admin/request/bdd_feature/regenerate/<int:issue_id>', methods=['GET'])
@software_request.route('/admin/request/bdd_feature/regenerate/<int:issue_id>', methods=['POST'])
def regenerate_bdd_feature(issue_id):
    issue = SoftwareIssues.query.get_or_404(issue_id)
    existing_feature = _get_bdd_feature_for_issue(issue)
    feature_exists = existing_feature is not None
    requirement_text = (request.values.get('requirement') or issue.issue or '').strip()
    reviewed_by_human = _request_flag('reviewed_by_human')
    try:
        typhoon_feature = _call_typhoon_bdd_feature(issue, requirement_text=requirement_text)
        feature = BDDFeature(
            software_request_id=issue.software_request_detail_id,
            software_issue_id=issue.id,
            feature_title=typhoon_feature['feature_title'],
            gherkin_text=typhoon_feature['gherkin_text'],
            generated_by_ai=True,
            reviewed_by_human=reviewed_by_human,
            version=existing_feature.version if existing_feature else 1,
            created_at=existing_feature.created_at if existing_feature and existing_feature.created_at else arrow.now('Asia/Bangkok').datetime,
            updated_at=arrow.now('Asia/Bangkok').datetime,
        )
        return _render_bdd_feature_modal(
            issue=issue,
            feature=feature,
            feature_exists=feature_exists,
            form=_build_bdd_feature_form(issue, feature, feature_exists),
            requirement_text=requirement_text,
            reviewed_by_human=reviewed_by_human,
        )
    except Exception as exc:
        current_app.logger.warning('Typhoon BDD feature regeneration failed for issue %s: %s', issue.id, exc)
        flash('BDD feature generation is currently unavailable. Please try again later.', 'danger')
        return _render_bdd_feature_modal(
            issue=issue,
            feature=existing_feature,
            feature_exists=feature_exists,
            generation_error='BDD feature generation is currently unavailable. Please try again later.',
            form=_build_bdd_feature_form(issue, existing_feature, feature_exists),
            requirement_text=requirement_text,
            reviewed_by_human=reviewed_by_human,
        )


@software_request.route('/admin/request/timeline/add/<int:detail_id>', methods=['GET', 'POST'])
@software_request.route('/admin/request/timeline/edit/<int:timeline_id>', methods=['GET', 'POST'])
def create_timeline(detail_id=None, timeline_id=None):
    tab = request.args.get('tab')
    template = request.args.get('template')
    if detail_id:
        SoftwareRequestTimelineForm = create_timeline_form(detail_id=detail_id)
        form = SoftwareRequestTimelineForm()
        sequence_no = SoftwareRequestNumberID.get_number('Num', db, software_request='software_request_'+str(detail_id))
    else:
        timeline = SoftwareRequestTimeline.query.get(timeline_id)
        SoftwareRequestTimelineForm = create_timeline_form(detail_id=timeline.request_id)
        form = SoftwareRequestTimelineForm(obj=timeline)
        status = timeline.status
    if form.validate_on_submit():
        if detail_id:
            timeline = SoftwareRequestTimeline()
        form.populate_obj(timeline)
        if detail_id:
            timeline.sequence = sequence_no.number
            timeline.request_id = detail_id
            timeline.created_at = arrow.now('Asia/Bangkok').datetime
            sequence_no.count += 1
        timeline.start = arrow.get(form.start.data, 'Asia/Bangkok').date()
        timeline.estimate = arrow.get(form.estimate.data, 'Asia/Bangkok').date()
        db.session.add(timeline)
        db.session.commit()
        timeline.request.updated_date = arrow.now('Asia/Bangkok').datetime
        timeline.request.approver_id = current_user.id
        db.session.add(timeline)
        db.session.commit()
        scheme = 'http' if current_app.debug else 'https'
        link = url_for("software_request.view_request", detail_id=timeline.request_id, _external=True,
                       _scheme=scheme)
        if detail_id:
            if not timeline.request.created_by.is_retired:
                title = f'''แจ้งเพิ่มความคืบหน้า (Timeline) คำร้องขอรับบริการพัฒนา Software'''
                message = f'''เรียน {timeline.request.created_by.fullname}\n\n'''
                message += f'''{timeline.request.approver.fullname} ได้ทำการเพิ่มความคืบหน้า (Timeline) ของคำร้องขอรับบริการพัฒนา \n\n'''
                message += f'''โดยมีรายละเอียดข้อมูลดังต่อไปนี้\n'''
                message += f'''  – งานที่ต้องดำเนินการ (Task): {timeline.task}\n'''
                message += f'''  – สถานะการดำเนินงาน: {timeline.status}\n'''
                message += f'''  – วันที่เริ่มต้น: {timeline.start.strftime('%d/%m/%Y')}\n'''
                message += f'''  – วันที่คาดว่าจะแล้วเสร็จ: {timeline.estimate.strftime('%d/%m/%Y')}\n'''
                message += f'''  – สถานะ: {timeline.status}\n'''
                message += f'''ท่านสามารถตรวจสอบรายละเอียดและความคืบหน้าเพิ่มเติมได้ที่ลิงก์ด้านล่าง\n\n'''
                message += f'''{link}\n\n'''
                message += f'''หากมีข้อสงสัยหรือต้องการสอบถามข้อมูลเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ที่รับผิดชอบ\n\n'''
                message += f'''ขอบคุณค่ะ\n'''
                message += f'''ระบบขอรับบริการพัฒนา Software\n'''
                message += f'''คณะเทคนิคการแพทย์'''
                send_mail([timeline.request.created_by.email + '@mahidol.ac.th'], title, message)
            flash('เพิ่มข้อมูลสำเร็จ', 'success')
            resp = make_response(render_template('software_request/timeline_template.html',tab=tab,
                                                 timeline=timeline, template=template))
            resp.headers['HX-Trigger'] = 'closeTimelineModal '
        else:
            if status != timeline.status and not timeline.request.created_by.is_retired:
                title = f'''แจ้งอัปเดตสถานะความคืบหน้า (Timeline) คำร้องขอรับบริการพัฒนา Software'''
                message = f'''เรียน {timeline.request.created_by.fullname}\n\n'''
                message += f'''{timeline.request.approver.fullname} ได้ทำการอัปเดตความคืบหน้า (Timeline) ของคำร้องขอรับบริการพัฒนา Software ของ{timeline.request.title}เป็น "{timeline.status}"\n\n'''
                message += f'''ท่านสามารถตรวจสอบรายละเอียดและความคืบหน้าเพิ่มเติมได้ที่ลิงก์ด้านล่าง\n'''
                message += f'''{link}\n\n'''
                message += f'''หากมีข้อสงสัยหรือต้องการสอบถามข้อมูลเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ที่รับผิดชอบ\n\n'''
                message += f'''ขอบคุณค่ะ\n'''
                message += f'''ระบบขอรับบริการพัฒนา Software\n'''
                message += f'''คณะเทคนิคการแพทย์'''
                send_mail([timeline.request.created_by.email + '@mahidol.ac.th'], title, message)
            flash('แก้ไขข้อมูลสำเร็จ', 'success')
            resp = make_response()
            resp.headers['HX-Refresh'] = 'true'
        return resp
    else:
        for er in form.errors:
            flash(er, 'danger')
    return render_template('software_request/modal/create_timeline_modal.html', form=form, tab=tab,
                           detail_id=detail_id, timeline_id=timeline_id, template=template)


@software_request.route('/admin/request/timeline/update/<int:timeline_id>', methods=['GET', 'POST'])
def update_timeline_status(timeline_id):
    status = request.form.get('status')
    timeline = SoftwareRequestTimeline.query.get(timeline_id)
    timeline.status = status
    timeline.request.updated_date = arrow.now('Asia/Bangkok').datetime
    timeline.request.approver_id = current_user.id
    db.session.add(timeline)
    db.session.commit()
    scheme = 'http' if current_app.debug else 'https'
    link = url_for("software_request.view_request", detail_id=timeline.request_id, _external=True, _scheme=scheme)
    if not timeline.request.created_by.is_retired:
        title = f'''แจ้งอัปเดตสถานะความคืบหน้า (Timeline) คำร้องขอรับบริการพัฒนา Software'''
        message = f'''เรียน {timeline.request.created_by.fullname}\n\n'''
        message += f'''{timeline.request.approver.fullname} ได้ทำการอัปเดตความคืบหน้า (Timeline) ของคำร้องขอรับบริการพัฒนา Software ของท่านเป็น "{timeline.status}"\n\n'''
        message += f'''ท่านสามารถตรวจสอบรายละเอียดและความคืบหน้าเพิ่มเติมได้ที่ลิงก์ด้านล่าง\n'''
        message += f'''{link}\n\n'''
        message += f'''หากมีข้อสงสัยหรือต้องการสอบถามข้อมูลเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ที่รับผิดชอบ\n\n'''
        message += f'''ขอบคุณค่ะ\n'''
        message += f'''ระบบขอรับบริการพัฒนา Software\n'''
        message += f'''คณะเทคนิคการแพทย์'''
        send_mail([timeline.request.created_by.email + '@mahidol.ac.th'], title, message)
    flash('อัพเดตสถานะสำเร็จ', 'success')
    resp = make_response()
    resp.headers['HX-Redirect'] = 'true'
    return resp


@software_request.route('/admin/request/timeline/delete/<int:timeline_id>', methods=['GET', 'DELETE'])
def delete_timeline(timeline_id):
    tab = request.args.get('tab')
    cancel = request.args.get('cancel', 'false')
    timeline = SoftwareRequestTimeline.query.get(timeline_id)
    timeline.status = 'ยกเลิกการพัฒนา'
    timeline.request.updated_date = arrow.now('Asia/Bangkok').datetime
    timeline.request.approver_id = current_user.id
    db.session.add(timeline)
    db.session.commit()
    scheme = 'http' if current_app.debug else 'https'
    link = url_for("software_request.view_request", detail_id=timeline.request_id, _external=True, _scheme=scheme)
    if not timeline.request.created_by.is_retired:
        title = f'''แจ้งการยกเลิกพัฒนาความคืบหน้า (Timeline) คำร้องขอรับบริการพัฒนา Software'''
        message = f'''เรียน {timeline.request.created_by.fullname}\n\n'''
        message += f'''{timeline.request.approver.fullname} ได้ทำการยกเลิกพัฒนาความคืบหน้า (Timeline) ของคำร้องขอรับบริการพัฒนา \n\n'''
        message += f'''โดยมีรายละเอียดข้อมูลดังต่อไปนี้\n'''
        message += f'''  – งานที่ต้องดำเนินการ (Task): {timeline.task}\n'''
        message += f'''  – สถานะการดำเนินงาน: {timeline.status}\n'''
        message += f'''  – วันที่เริ่มต้น: {timeline.start.strftime('%d/%m/%Y')}\n'''
        message += f'''  – วันที่คาดว่าจะแล้วเสร็จ: {timeline.estimate.strftime('%d/%m/%Y')}\n'''
        message += f'''  – สถานะ: {timeline.status}\n'''
        message += f'''ท่านสามารถตรวจสอบรายละเอียดเพิ่มเติมได้ที่ลิงก์ด้านล่าง\n'''
        message += f'''{link}\n\n'''
        message += f'''หากมีข้อสงสัยหรือต้องการสอบถามข้อมูลเพิ่มเติม กรุณาติดต่อเจ้าหน้าที่ที่รับผิดชอบ\n\n'''
        message += f'''ขอบคุณค่ะ\n'''
        message += f'''ระบบขอรับบริการพัฒนา Software\n'''
        message += f'''คณะเทคนิคการแพทย์'''
        send_mail([timeline.request.created_by.email + '@mahidol.ac.th'], title, message)
    db.session.delete(timeline)
    db.session.commit()
    resp = make_response()
    if cancel == 'true':
        flash('ยกเลิกรายการสำเร็จ', 'success')
        resp.headers['HX-Redirect'] = url_for('software_request.admin_index', tab=tab)
    else:
        flash('ลบข้อมูลสำเร็จ', 'success')
        resp.headers['HX-Refresh'] = 'true'
    return resp


@software_request.route('/admin/request/issues/<int:issue_id>', methods=['GET', 'POST'])
@software_request.route('/admin/request/details/<int:detail_id>/issues', methods=['GET', 'POST'])
def create_issue(detail_id=None, issue_id=None):
    form = SoftwareRequestIssueForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            if issue_id:
                issue =  SoftwareIssues.query.get(issue_id)
                current_status = issue.status
                issue.updated_at = arrow.now('Asia/Bangkok').datetime
                issue.updater = current_user
            else:
                issue = SoftwareIssues(software_request_detail_id=detail_id)
                issue.created_at = arrow.now('Asia/Bangkok').datetime
                issue.creator = current_user
                current_status = ''
            form.populate_obj(issue)

            if form.status_.data != current_status:
                if form.status_.data == 'Cancelled':
                    issue.cancelled_at = arrow.now('Asia/Bangkok').datetime
                    issue.closed_at = None
                    issue.accepted_at = None
                    issue.tested_at = None
                    if issue.timelines:
                        for timeline in issue.timelines:
                            timeline.status = 'ยกเลิกการพัฒนา'
                            db.session.add(timeline)
                        db.session.commit()
                elif form.status_.data == 'Closed':
                    issue.closed_at = arrow.now('Asia/Bangkok').datetime
                    issue.cancelled_at = None
                    issue.accepted_at = None
                    issue.tested_at = None
                    if issue.timelines:
                        for timeline in issue.timelines:
                            timeline.status = 'เสร็จสิ้น'
                            db.session.add(timeline)
                        db.session.commit()
                elif form.status_.data == 'Working':
                    issue.accepted_at = arrow.now('Asia/Bangkok').datetime
                    issue.closed_at = None
                    issue.cancelled_at = None
                    issue.tested_at = None
                    if issue.timelines:
                        for timeline in issue.timelines:
                            timeline.status = 'รอดำเนินการ'
                            db.session.add(timeline)
                        db.session.commit()
                elif form.status_.data == 'Testing':
                    issue.tested_at = arrow.now('Asia/Bangkok').datetime
                    issue.accepted_at = None
                    issue.closed_at = None
                    issue.cancelled_at = None
                    if issue.timelines:
                        for timeline in issue.timelines:
                            timeline.status = 'เสร็จสิ้น'
                            db.session.add(timeline)
                        db.session.commit()
                else:
                    issue.accepted_at = None
                    issue.closed_at = None
                    issue.cancelled_at = None
                    issue.tested_at = None

            db.session.add(issue)
            db.session.commit()
            issue.deadline = arrow.get(form.deadline.data, 'Asia/Bangkok').date() if form.deadline.data else None
            issue.software_request_detail.updated_date = arrow.now('Asia/Bangkok').datetime
            issue.software_request_detail.approver_id = current_user.id
            db.session.add(issue)
            db.session.commit()
        else:
            flash(f'{form.errors}', 'danger')
        resp = make_response()
        resp.headers['HX-Refresh'] = 'true'
        return resp
    if issue_id:
        issue = SoftwareIssues.query.get(issue_id)
        form = SoftwareRequestIssueForm(obj=issue)
        form.status_.data = issue.status
        form.populate_obj(issue)
    return render_template('software_request/modal/create_issue_modal.html',
                           form=form, issue_id=issue_id, detail_id=detail_id)


@software_request.route('/request/test_result/add/<int:detail_id>', methods=['GET', 'POST'])
@software_request.route('/request/test_result/edit/<int:test_result_id>', methods=['GET', 'POST'])
def create_test_result(detail_id=None, test_result_id=None):
    if detail_id:
        SoftwareRequestTestResultForm = create_test_result_form(detail_id=detail_id, has_note=False)
        form = SoftwareRequestTestResultForm()
    else:
        test_result = SoftwareRequestTestResult.query.get(test_result_id)
        SoftwareRequestTestResultForm = create_test_result_form(detail_id=test_result.request_id, has_note=False)
        form = SoftwareRequestTestResultForm(obj=test_result)
    if form.validate_on_submit():
        if detail_id:
           test_result = SoftwareRequestTestResult()
        form.populate_obj(test_result)
        if detail_id:
            test_result.request_id = detail_id
            test_result.created_at = arrow.now('Asia/Bangkok').datetime
            test_result.creator_id = current_user.id
        else:
            test_result.updated_at = arrow.now('Asia/Bangkok').datetime
            test_result.updater_id = current_user.id
        db.session.add(test_result)
        db.session.commit()
        scheme = 'http' if current_app.debug else 'https'
        link = url_for("software_request.view_request", detail_id=test_result.request_id, _external=True,
                       _scheme=scheme)
        if detail_id:
            if not test_result.request.created_by.is_retired:
                title = f'''แจ้งดำเนินการทดสอบของ{test_result.request.title}'''
                message = f'''ขณะนี้ได้มีการจัดเตรียมรายการทดสอบสำหรับ "{test_result.request.title}" เรียบร้อยแล้ว\n'''
                message += f'''โดยมีรายละเอียดรายการทดสอบ ดังนี้ {test_result.issue.issue}\n'''
                message += f'''ท่านสามารถบันทึกผลการทดสอบได้ที่ลิงก์ด้านล่าง\n'''
                message += f'''{link}\n\n'''
                message += f'''ขอบคุณค่ะ\n'''
                message += f'''ระบบขอรับบริการพัฒนา Software\n'''
                message += f'''คณะเทคนิคการแพทย์'''
                send_mail([test_result.request.created_by.email + '@mahidol.ac.th'], title, message)
            flash('บันทึกข้อมูลผลการทดสอบสำเร็จ', 'success')
            resp = make_response(render_template('software_request/test_result_template.html',
                                                 test_result=test_result))
            resp.headers['HX-Trigger'] = 'closeTestResultModal'
        else:
            if not test_result.request.created_by.is_retired:
                title = f'''แจ้งแก้ไขรายการทดสอบของ{test_result.request.title}'''
                message = f'''รายการทดสอบสำหรับ "{test_result.request.title}" ได้รับการแก้ไขแล้ว\n'''
                message += f'''โดยมีรายละเอียดรายการทดสอบ ดังนี้ {test_result.issue.issue}\n'''
                message += f'''ท่านสามารถบันทึกผลการทดสอบได้ที่ลิงก์ด้านล่าง\n'''
                message += f'''{link}\n\n'''
                message += f'''ขอบคุณค่ะ\n'''
                message += f'''ระบบขอรับบริการพัฒนา Software\n'''
                message += f'''คณะเทคนิคการแพทย์'''
                send_mail([test_result.request.created_by.email + '@mahidol.ac.th'], title, message)
            flash('อัพเดตข้อมูลผลการทดสอบสำเร็จ', 'success')
            resp = make_response()
            resp.headers['HX-Refresh'] = 'true'
        return resp
    return render_template('software_request/modal/create_test_result_modal.html', detail_id=detail_id,
                           test_result_id=test_result_id, form=form)


@software_request.route('/request/test_result/delete/<int:test_result_id>', methods=['GET', 'DELETE'])
def delete_test_result(test_result_id):
    test_result = SoftwareRequestTestResult.query.get(test_result_id)
    if not test_result.request.created_by.is_retired:
        title = f'''แจ้งยกเลิกรายการทดสอบของ{test_result.request.title}'''
        message = f'''รายการทดสอบสำหรับ "{test_result.request.title}" ได้ถูกยกเลิกแล้ว\n'''
        message += f'''โดยมีรายละเอียดรายการทดสอบ ดังนี้ {test_result.issue.issue}\n'''
        message += f'''ขอบอภับในความไม่สะดวก\n'''
        message += f'''ระบบขอรับบริการพัฒนา Software\n'''
        message += f'''คณะเทคนิคการแพทย์'''
        send_mail([test_result.request.created_by.email + '@mahidol.ac.th'], title, message)
    db.session.delete(test_result)
    db.session.commit()
    flash('ลบผลการทดสอบสำเร็จ', 'success')
    resp = make_response()
    resp.headers['HX-Refresh'] = 'true'
    return resp


@software_request.route('/request/test_result/note/edit/<int:test_result_id>', methods=['GET', 'POST'])
def create_note(test_result_id):
    test_result = SoftwareRequestTestResult.query.get(test_result_id)
    SoftwareRequestTestResultForm = create_test_result_form(detail_id=test_result.request_id, has_note=True)
    form = SoftwareRequestTestResultForm(obj=test_result)
    if form.validate_on_submit():
        form.populate_obj(test_result)
        db.session.add(test_result)
        db.session.commit()
        flash('บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
        resp = make_response(render_template('software_request/note_template.html',
                                             test_result=test_result))
        resp.headers['HX-Trigger'] = 'closeNoteModal'
        return resp
    return render_template('software_request/modal/create_note_modal.html', form=form,
                           test_result_id=test_result_id)
