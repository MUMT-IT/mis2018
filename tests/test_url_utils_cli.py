import importlib.util
from pathlib import Path

import pytest
from flask import Flask

spec = importlib.util.spec_from_file_location('url_utils_cli_test', Path(__file__).resolve().parents[1] / 'app/url_utils.py')
url_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(url_utils)


@pytest.mark.parametrize('base', ['https://example.test', 'https://example.test/mis'])
@pytest.mark.parametrize('request_context', [True, False])
def test_external_url_works_in_web_and_cli_contexts(base, request_context):
    app = Flask(__name__)
    app.config['PUBLIC_BASE_URL'] = base
    app.add_url_rule('/staff/checkin/<int:staff_id>', endpoint='checkin', view_func=lambda staff_id: '')
    context = app.test_request_context(base_url='https://internal.test') if request_context else app.app_context()
    with context:
        assert app.config['SERVER_NAME'] is None
        assert url_utils.external_url('checkin', staff_id=1588, mode='geo') == base + '/staff/checkin/1588?mode=geo'


def test_external_url_still_requires_public_base_url():
    app = Flask(__name__)
    with app.app_context(), pytest.raises(RuntimeError, match='PUBLIC_BASE_URL'):
        url_utils.external_url('checkin')
