#!/usr/bin/env python3
import argparse
import json
import os
import sys
from typing import Any

import requests


DEFAULT_BASE_URL = "https://webmt.mahidol.ac.th/api"
DEFAULT_ENDPOINT = "/ConditionInterprets"


def get_base_url() -> str:
    return os.getenv("COMHEALTH_ONLINE_RESULTS_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def get_api_key() -> str | None:
    for env_name in (
        "COMHEALTH_ONLINE_RESULTS_API_KEY",
        "COMHEALTH_RESULTS_API_KEY",
        "WEBMT_API_KEY",
    ):
        value = os.getenv(env_name)
        if value:
            return value
    return None


def api_url(path: str) -> str:
    return f"{get_base_url()}/{path.lstrip('/')}"


def extract_token(payload: Any) -> str | None:
    if isinstance(payload, str):
        return payload

    if not isinstance(payload, dict):
        return None

    for key in ("access_token", "accessToken", "token", "bearerToken", "bearer_token"):
        token = payload.get(key)
        if token:
            return token

    for nested_key in ("data", "result"):
        token = extract_token(payload.get(nested_key))
        if token:
            return token

    return None


def fetch_bearer_token(timeout: int) -> str:
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "Missing API key. Set COMHEALTH_ONLINE_RESULTS_API_KEY, "
            "COMHEALTH_RESULTS_API_KEY, or WEBMT_API_KEY."
        )

    response = requests.post(
        api_url("/apiclients/token"),
        json={"apiKey": api_key},
        timeout=timeout,
    )
    response.raise_for_status()

    payload = response.json()
    token = extract_token(payload)
    if not token:
        raise RuntimeError(f"Token response did not include a bearer token: {payload}")

    return token


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe the ComHealth online results API using the same auth flow as app/comhealth/views.py."
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"API path to test after auth. Default: {DEFAULT_ENDPOINT}",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP timeout in seconds. Default: 10",
    )
    parser.add_argument(
        "--token-only",
        action="store_true",
        help="Only test the token exchange and skip the follow-up API request.",
    )
    args = parser.parse_args()

    print(f"Base URL: {get_base_url()}")

    try:
        token = fetch_bearer_token(timeout=args.timeout)
    except Exception as exc:
        print(f"Token request failed: {exc}", file=sys.stderr)
        return 1

    print("Token request: OK")
    print(f"Bearer token prefix: {token[:12]}...")

    if args.token_only:
        return 0

    try:
        response = requests.get(
            api_url(args.endpoint),
            headers={"Authorization": f"Bearer {token}"},
            timeout=args.timeout,
        )
    except Exception as exc:
        print(f"Endpoint request failed: {exc}", file=sys.stderr)
        return 2

    print(f"Endpoint: {args.endpoint}")
    print(f"Status: {response.status_code}")

    try:
        payload = response.json()
        print("JSON preview:")
        print(json.dumps(payload, indent=2, ensure_ascii=False)[:2000])
    except ValueError:
        print("Response preview:")
        print(response.text[:2000])

    return 0 if response.ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
