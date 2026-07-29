from __future__ import annotations

import json
import os
import re

import requests

from .health_risk_copy import get_health_risk_copy

TYPHOON_API_URL = 'https://api.opentyphoon.ai/v1/chat/completions'
TYPHOON_MODEL = os.getenv('SCB_TYPHOON_MODEL', 'typhoon-v2.5-30b-a3b-instruct')


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


def _format_issue_snapshot(issue):
    return {
        'key': issue.get('key'),
        'name': issue.get('issue_name'),
        'concern_level': issue.get('concern_level'),
        'concern_score': issue.get('concern_score'),
        'evidence_completeness': issue.get('evidence_completeness'),
        'short_explanation': issue.get('short_explanation'),
        'supporting_lab_results': [
            {
                'label': item.get('label'),
                'value': item.get('value'),
                'unit': item.get('unit'),
                'status': item.get('status'),
            }
            for item in issue.get('supporting_lab_results', [])
        ],
        'missing_evidence': issue.get('missing_evidence', []),
    }


def _build_typhoon_summary_prompt(report, copy):
    top_issues = [_format_issue_snapshot(issue) for issue in report.get('top_issues', [])]
    issues = [_format_issue_snapshot(issue) for issue in report.get('issues', [])]
    language = 'Thai' if report.get('lang') == 'th' else 'English'
    return [
        {
            'role': 'system',
            'content': (
                'You are summarizing a health checkup report for a patient portal. '
                'Use only the provided structured report data. '
                'Do not diagnose. '
                'Do not invent risks, thresholds, or medical advice beyond the data. '
                'Focus on the top health concerns and what matters most from the available evidence. '
                'If evidence is incomplete, say so plainly. '
                'Write in {language} only. '
                'Return JSON only with keys summary_title, summary_paragraph, top_concerns, what_matters, caution_note. '
                'top_concerns and what_matters must be arrays of short strings.'
            ).format(language=language)
        },
        {
            'role': 'user',
            'content': json.dumps(
                {
                    'language': language,
                    'copy_labels': {
                        'no_concern': copy['no_concern'],
                        'mild': copy['mild'],
                        'moderate': copy['moderate'],
                        'high': copy['high'],
                        'not_diagnosis': copy['not_diagnosis'],
                    },
                    'top_issues': top_issues,
                    'issues': issues,
                },
                ensure_ascii=False,
                indent=2,
            ),
        },
    ]


def _build_fallback_health_summary(report, copy):
    top_issues = report.get('top_issues', [])[:3]
    if not top_issues:
        if report.get('lang') == 'th':
            return {
                'summary_title': 'สรุปสิ่งที่สำคัญ',
                'summary_paragraph': 'ยังไม่พบประเด็นที่น่ากังวลจากผลตรวจที่มีอยู่ในตอนนี้',
                'top_concerns': ['ยังไม่พบความเสี่ยงเด่น'],
                'what_matters': ['ตัวบ่งชี้ที่มีอยู่ยังไม่แสดงความผิดปกติที่ชัดเจน'],
                'caution_note': copy['not_diagnosis'],
            }
        return {
            'summary_title': 'What matters most',
            'summary_paragraph': 'No current concern stands out from the available results.',
            'top_concerns': ['No major concern stands out'],
            'what_matters': ['The available indicators do not show a clear pattern of abnormality.'],
            'caution_note': copy['not_diagnosis'],
        }

    if report.get('lang') == 'th':
        summary_title = 'สรุปสิ่งที่สำคัญ'
        summary_paragraph = (
            f"จุดที่ควรจับตาคือ {top_issues[0]['issue_name']} "
            f"อยู่ในระดับ {top_issues[0]['concern_level']} "
            f"และผลตรวจโดยรวมชี้ว่าควรติดตาม {len(top_issues)} ประเด็นหลัก"
        )
        top_concerns = [
            f"{issue['issue_name']} · {issue['concern_level']} · คะแนน {issue['concern_score']}"
            for issue in top_issues
        ]
        what_matters = []
        for issue in top_issues:
            evidence_names = [item['label'] for item in issue.get('supporting_lab_results', [])[:3]]
            if evidence_names:
                what_matters.append(f"{issue['issue_name']}: {', '.join(evidence_names)}")
            else:
                what_matters.append(f"{issue['issue_name']}: {copy['evidence_incomplete']}")
        caution_note = copy['not_diagnosis']
    else:
        summary_title = 'What matters most'
        summary_paragraph = (
            f"The main item to watch is {top_issues[0]['issue_name']} "
            f"at {top_issues[0]['concern_level']} level, with {len(top_issues)} top issues standing out overall."
        )
        top_concerns = [
            f"{issue['issue_name']} · {issue['concern_level']} · score {issue['concern_score']}"
            for issue in top_issues
        ]
        what_matters = []
        for issue in top_issues:
            evidence_names = [item['label'] for item in issue.get('supporting_lab_results', [])[:3]]
            if evidence_names:
                what_matters.append(f"{issue['issue_name']}: {', '.join(evidence_names)}")
            else:
                what_matters.append(f"{issue['issue_name']}: {copy['evidence_incomplete']}")
        caution_note = copy['not_diagnosis']

    return {
        'summary_title': summary_title,
        'summary_paragraph': summary_paragraph,
        'top_concerns': top_concerns,
        'what_matters': what_matters,
        'caution_note': caution_note,
    }


def _call_typhoon_health_summary(report, copy):
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
            'max_tokens': 700,
            'messages': _build_typhoon_summary_prompt(report, copy),
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload['choices'][0]['message']['content']
    parsed = _extract_json_payload(content)
    summary_title = str(parsed.get('summary_title') or '').strip()
    summary_paragraph = str(parsed.get('summary_paragraph') or '').strip()
    top_concerns = [str(item).strip() for item in parsed.get('top_concerns') or [] if str(item).strip()]
    what_matters = [str(item).strip() for item in parsed.get('what_matters') or [] if str(item).strip()]
    caution_note = str(parsed.get('caution_note') or '').strip()
    if not summary_title or not summary_paragraph:
        raise ValueError('Missing summary_title or summary_paragraph in Typhoon response.')
    return {
        'summary_title': summary_title,
        'summary_paragraph': summary_paragraph,
        'top_concerns': top_concerns,
        'what_matters': what_matters,
        'caution_note': caution_note or copy['not_diagnosis'],
    }


def build_health_risk_summary(report, lang='en'):
    copy = get_health_risk_copy(lang)
    try:
        return _call_typhoon_health_summary(report, copy)
    except Exception:
        return _build_fallback_health_summary(report, copy)
