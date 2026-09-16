import hashlib


def normalize_pending_result(value, expected_email=None):
    """Validate and normalize a signed notification's report destination."""
    if not isinstance(value, dict):
        return None
    email = str(value.get('email') or '').strip().lower()
    service_no = str(value.get('serviceNo') or '').strip()
    service_date = str(value.get('serviceDate') or '').strip()
    age = str(value.get('age') or '').strip()
    if not email or not service_no.isdigit() or not service_date:
        return None
    if expected_email and email != str(expected_email).strip().lower():
        return None
    return {
        'email': email,
        'serviceNo': service_no,
        'serviceDate': service_date,
        'age': age if age.isdigit() else '',
    }


def access_token_hash(token):
    """Return the non-reversible value stored for a magic-link token."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()
