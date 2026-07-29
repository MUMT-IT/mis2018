from __future__ import annotations

import json
import os
from pathlib import Path

import requests


def load_google_credentials_json(env_var: str = 'GOOGLE_APPLICATION_CREDENTIALS') -> dict:
    """Load Google service-account JSON without requiring network access at import time."""
    value = os.environ.get(env_var)
    if not value:
        return {}

    try:
        if value.lstrip().startswith('{'):
            return json.loads(value)
        path = Path(value)
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
        if value.startswith(('http://', 'https://')):
            return requests.get(value, timeout=10).json()
    except Exception:
        return {}
    return {}
