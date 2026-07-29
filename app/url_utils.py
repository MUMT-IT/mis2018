from urllib.parse import urljoin

from flask import current_app, url_for


def external_url(endpoint, **values):
    base_url = current_app.config.get('PUBLIC_BASE_URL')
    if not base_url:
        raise RuntimeError('PUBLIC_BASE_URL must be configured for external URL generation')
    return urljoin(f"{base_url.rstrip('/')}/", url_for(endpoint, **values).lstrip('/'))
