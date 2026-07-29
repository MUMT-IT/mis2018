import json
import os
import re
from datetime import datetime

import requests

from .organization_context import ORG_CONTEXT

TYPHOON_API_URL = 'https://api.opentyphoon.ai/v1/chat/completions'
TYPHOON_MODEL = os.getenv('SCB_TYPHOON_MODEL', 'typhoon-v2.5-30b-a3b-instruct')


def _get_runtime_date_context():
    today = datetime.now()
    return today.strftime('%Y-%m-%d'), today.strftime('%A')


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


def _normalize_string_list(value):
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


def _build_normalization_prompt(user_input: str, current_date: str, current_day: str) -> str:
    return (
        '1. SYSTEM INSTRUCTIONS\n'
        'You normalize room-finding requests for a university organization before deterministic parsing.\n'
        'Do not search for rooms.\n'
        'Do not hallucinate unsupported facts.\n'
        'If something is uncertain or missing, put it in uncertain_items instead of guessing.\n'
        'Resolve relative dates using the runtime date context below.\n'
        'If the user specifies both a weekday and a numeric date, prioritize the numeric date.\n'
        'Output resolved dates in ISO format YYYY-MM-DD.\n'
        'Return JSON only with keys: normalized_text, inferred_context, uncertain_items, resolved_date.\n'
        'Use null for resolved_date when no single date can be resolved.\n\n'
        '2. ORGANIZATION CONTEXT\n'
        f'{ORG_CONTEXT.strip()}\n\n'
        '3. CURRENT RUNTIME DATE CONTEXT\n'
        f'Current date: {current_date}\n'
        f'Current weekday: {current_day}\n'
        'Interpret relative dates based on the current date above.\n'
        'Treat calendar weeks as Monday through Sunday.\n'
        '"วันนี้" means the current date.\n'
        '"พรุ่งนี้" means the next day.\n'
        '"วันพุธนี้" means Wednesday in the current calendar week.\n'
        '"วันพุธหน้า" always means Wednesday in the next calendar week, never the nearest upcoming Wednesday in the current week.\n'
        '"วันศุกร์นี้" means Friday in the current calendar week.\n'
        '"วันศุกร์หน้า" always means Friday in the next calendar week, never this coming Friday if it is still in the current week.\n'
        'For any phrase in the form "วัน<weekday>หน้า", resolve it to that weekday in the next calendar week.\n'
        'If today is Monday and the user says "วันพุธหน้า", do not use this week\'s Wednesday; use Wednesday of next week.\n'
        'If today is Tuesday and the user says "วันศุกร์หน้า", do not use this week\'s Friday; use Friday of next week.\n'
        'If the user specifies both weekday and numeric date, prioritize the numeric date.\n'
        'Output resolved dates in ISO format YYYY-MM-DD.\n\n'
        '4. USER INPUT\n'
        f'{user_input}'
    )


def build_normalization_prompt(user_input: str) -> str:
    current_date, current_day = _get_runtime_date_context()
    return _build_normalization_prompt(user_input, current_date, current_day)


def normalize_user_request(user_input: str) -> dict:
    api_key = os.environ.get('SCB_TYPHOON_API_KEY')
    if not api_key:
        raise RuntimeError('SCB_TYPHOON_API_KEY is not configured.')
    current_date, current_day = _get_runtime_date_context()
    prompt = _build_normalization_prompt(user_input, current_date, current_day)

    response = requests.post(
        TYPHOON_API_URL,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': TYPHOON_MODEL,
            'temperature': 0.1,
            'max_tokens': 900,
            'messages': [
                {
                    'role': 'system',
                    'content': 'Return JSON only. No markdown. No extra commentary.',
                },
                {
                    'role': 'user',
                    'content': prompt,
                }
            ],
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload['choices'][0]['message']['content']
    parsed = _extract_json_payload(content)

    normalized_text = str(parsed.get('normalized_text') or '').strip()
    if not normalized_text:
        raise ValueError('Missing normalized_text in normalization response.')
    resolved_date = parsed.get('resolved_date')
    resolved_date = str(resolved_date).strip() if resolved_date not in (None, '') else None

    return {
        'current_date': current_date,
        'current_day': current_day,
        'normalized_text': normalized_text,
        'inferred_context': _normalize_string_list(parsed.get('inferred_context')),
        'uncertain_items': _normalize_string_list(parsed.get('uncertain_items')),
        'resolved_date': resolved_date,
    }
