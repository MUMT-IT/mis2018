from urllib.parse import urljoin, urlsplit

from flask import current_app, has_request_context, url_for


def external_url(endpoint, **values):
    base_url = current_app.config.get('PUBLIC_BASE_URL')
    if not base_url:
        raise RuntimeError('PUBLIC_BASE_URL must be configured for external URL generation')
    if has_request_context():
        path = url_for(endpoint, **values)
    else:
        # CLI jobs have an application context but no request URL adapter.
        # Bind to the configured public host instead of requiring SERVER_NAME.
        public_url = urlsplit(base_url)
        adapter = current_app.url_map.bind(public_url.netloc, url_scheme=public_url.scheme)
        path = adapter.build(endpoint, values, force_external=False)
    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip('/'))
