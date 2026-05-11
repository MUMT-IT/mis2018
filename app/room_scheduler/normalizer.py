import json
import os
import re

import requests

from .organization_context import ORG_CONTEXT

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


def _build_normalization_prompt(user_input):
    return [
        {
            'role': 'system',
            'content': (
                'You normalize room-finding requests for a university organization. '
                'Use the organization context below to clarify wording before deterministic parsing. '
                'Do not search for rooms. Do not invent facts not supported by the input or the context. '
                'If something is uncertain, put it in uncertain_items instead of guessing. '
                'Return JSON only with keys: normalized_text, inferred_context, uncertain_items.\n\n'
                f'ORGANIZATION_CONTEXT:\n{ORG_CONTEXT}\n'
            )
        },
        {
            'role': 'user',
            'content': (
                'Normalize this room request into clearer Thai for downstream rule-based parsing. '
                'Rewrite the request so time, purpose, location clues, and equipment clues are easier to parse '
                'while preserving uncertainty. Keep it concise.\n\n'
                f'User input: {user_input}'
            )
        }
    ]


def normalize_user_request(user_input: str) -> dict:
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
            'temperature': 0.1,
            'max_tokens': 900,
            'messages': _build_normalization_prompt(user_input),
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

    return {
        'normalized_text': normalized_text,
        'inferred_context': _normalize_string_list(parsed.get('inferred_context')),
        'uncertain_items': _normalize_string_list(parsed.get('uncertain_items')),
    }
