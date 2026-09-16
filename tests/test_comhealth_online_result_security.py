import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / 'app' / 'comhealth' / 'online_result_security.py'
SPEC = importlib.util.spec_from_file_location('comhealth_online_result_security_test', MODULE_PATH)
online_result_security = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(online_result_security)
access_token_hash = online_result_security.access_token_hash
normalize_pending_result = online_result_security.normalize_pending_result


def test_pending_result_is_normalized_and_bound_to_expected_email():
    result = normalize_pending_result(
        {
            'email': ' Customer@Example.com ',
            'serviceNo': ' 42 ',
            'serviceDate': '2026-09-16',
            'age': ' 35 ',
        },
        expected_email='customer@example.com',
    )

    assert result == {
        'email': 'customer@example.com',
        'serviceNo': '42',
        'serviceDate': '2026-09-16',
        'age': '35',
    }


def test_pending_result_rejects_a_different_authenticated_email():
    assert normalize_pending_result(
        {
            'email': 'customer@example.com',
            'serviceNo': '42',
            'serviceDate': '2026-09-16',
        },
        expected_email='attacker@example.com',
    ) is None


def test_pending_result_rejects_invalid_report_coordinates():
    assert normalize_pending_result({
        'email': 'customer@example.com',
        'serviceNo': 'not-a-number',
        'serviceDate': '2026-09-16',
    }) is None


def test_access_token_hash_does_not_store_the_bearer_token():
    token = 'signed-secret-token'
    digest = access_token_hash(token)

    assert digest != token
    assert len(digest) == 64
    assert digest == access_token_hash(token)
    assert digest != access_token_hash('another-token')
